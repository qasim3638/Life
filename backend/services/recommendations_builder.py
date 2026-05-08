"""
Co-purchase recommender — mines paid baskets to build a per-product
"frequently bought together" index, persisted in `frequently_bought_cache`.

Recommendations are restricted to **installation essentials** (adhesive,
grout, sealer, primer, spacer, trim, etc.) so the PDP suggests what the
customer actually needs to lay the tile — never another tile.

Two data sources are merged into one product_id-keyed index:
  * shop_orders (online checkout)   — items[].product_id  (canonical)
  * invoices    (in-store EPOS)     — line_items[].sku    (mapped → tiles.id)

The endpoint reads from this cache; nightly APScheduler refreshes it.
"""
import logging
import re
from datetime import datetime, timezone
from collections import defaultdict
from itertools import combinations

from config import get_db

logger = logging.getLogger(__name__)


# Keywords that flag a tile-DB row as an installation essential rather than
# a finish tile. Matched case-insensitively against display_name + name +
# category. Tuned for UK trade SKUs (Ultratile, Bal, Mapei, etc.).
ESSENTIAL_KEYWORDS = [
    r"\badhesive\b", r"\bgrout\b", r"\bsealer\b", r"\bsealant\b", r"\bprimer\b",
    r"\bspacer\b", r"\btrim\b", r"\bwedge\b", r"\blevell?ing\b", r"\bunderlay\b",
    r"\btanking\b", r"\bmembrane\b", r"\bsilicone\b", r"\bcleaner\b",
    r"\bprotect", r"\bsbr\b", r"\bbond\b", r"\baccessor", r"\bedging\b",
    r"\bprosealer\b", r"\bprofix\b", r"\bpropaver\b", r"\bpropave\b",
    r"\bpropr?imer\b", r"\bproflex\b", r"\bproset\b", r"\bgroutaid\b",
]
_ESSENTIAL_RE = re.compile("|".join(ESSENTIAL_KEYWORDS), re.IGNORECASE)


def is_installation_essential(tile: dict) -> bool:
    """True if the tile-DB row looks like an installation essential
    (adhesive, grout, sealer, primer, spacer, trim, etc.) rather than a
    finish tile. Checked against multiple name fields for robustness."""
    if not tile:
        return False
    haystack = " ".join(str(tile.get(f) or "") for f in (
        "display_name", "name", "category", "sub_category", "main_category",
    ))
    return bool(_ESSENTIAL_RE.search(haystack))


async def _essential_id_set(db) -> set:
    """All tile ids/_ids that classify as installation essentials. Built once
    per rebuild so the basket-mining loop can filter pairs cheaply."""
    cursor = db.tiles.find(
        {},
        {"_id": 1, "id": 1, "display_name": 1, "name": 1, "category": 1,
         "sub_category": 1, "main_category": 1},
    )
    out = set()
    async for t in cursor:
        if is_installation_essential(t):
            out.add(str(t.get("_id")))
            if t.get("id"):
                out.add(str(t.get("id")))
    return out


async def _sku_to_product_id_map(db) -> dict:
    """Build {sku -> tile.id} so EPOS invoice rows (which carry SKU only) can
    contribute to the same co-purchase graph as online orders (product_id)."""
    cursor = db.tiles.find({"sku": {"$nin": [None, ""]}}, {"_id": 0, "id": 1, "sku": 1})
    out = {}
    async for t in cursor:
        sku = (t.get("sku") or "").strip()
        if sku and t.get("id"):
            out[sku] = t["id"]
    return out


def _basket_pids(items: list, key: str = "product_id", sku_map: dict | None = None) -> list:
    """Extract unique, non-empty product_ids from a basket. SKU-only rows are
    resolved via the provided sku_map. Quantity is ignored — pair occurs once
    per basket regardless of qty (we measure how often X+Y are bought together,
    not how many tiles)."""
    seen = set()
    for it in (items or []):
        pid = (it or {}).get(key)
        if not pid and sku_map is not None:
            sku = (it or {}).get("sku")
            if sku:
                pid = sku_map.get(str(sku).strip())
        if pid:
            seen.add(str(pid))
    return list(seen)


async def rebuild_co_purchase_cache(top_k: int = 5) -> dict:
    """
    Recompute the co-purchase index from scratch and write to
    `frequently_bought_cache`. Only essential→anchor links are kept on the
    related side, so a tile PDP only ever sees adhesive / grout / sealer /
    spacer / trim recommendations.
    """
    db = get_db()
    sku_map = await _sku_to_product_id_map(db)
    essentials = await _essential_id_set(db)

    # pair_counts[anchor_pid][essential_pid] = number of distinct baskets
    # containing both. We only count pairs where one side is an essential.
    pair_counts: dict = defaultdict(lambda: defaultdict(int))

    def record_pair(a: str, b: str) -> None:
        a_ess, b_ess = a in essentials, b in essentials
        if a_ess == b_ess:
            # Both essentials or neither — neither side benefits from being
            # recommended on a tile PDP, skip.
            return
        anchor, essential = (b, a) if a_ess else (a, b)
        pair_counts[anchor][essential] += 1

    online_baskets = 0
    cursor = db.shop_orders.find(
        {"payment_status": "paid", "items.1": {"$exists": True}},
        {"_id": 0, "items": 1},
    )
    async for o in cursor:
        pids = _basket_pids(o.get("items"), key="product_id", sku_map=sku_map)
        if len(pids) < 2:
            continue
        online_baskets += 1
        for a, b in combinations(pids, 2):
            record_pair(a, b)

    instore_baskets = 0
    cursor = db.invoices.find(
        {"line_items.1": {"$exists": True}, "deleted_at": {"$in": [None, ""]}},
        {"_id": 0, "line_items": 1},
    )
    async for inv in cursor:
        pids = _basket_pids(inv.get("line_items"), key="product_id", sku_map=sku_map)
        if len(pids) < 2:
            continue
        instore_baskets += 1
        for a, b in combinations(pids, 2):
            record_pair(a, b)

    now = datetime.now(timezone.utc)
    await db.frequently_bought_cache.delete_many({})
    rows = []
    for pid, related in pair_counts.items():
        ranked = sorted(related.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        if not ranked:
            continue
        rows.append({
            "product_id": pid,
            "related": [{"product_id": rpid, "count": int(c)} for rpid, c in ranked],
            "updated_at": now,
        })
    if rows:
        await db.frequently_bought_cache.insert_many(rows)

    logger.info(
        "rebuilt frequently_bought_cache: %d products, online_baskets=%d, instore_baskets=%d, essentials_known=%d",
        len(rows), online_baskets, instore_baskets, len(essentials),
    )
    return {
        "products_indexed": len(rows),
        "online_baskets": online_baskets,
        "instore_baskets": instore_baskets,
        "essentials_known": len(essentials),
        "rebuilt_at": now.isoformat(),
    }
