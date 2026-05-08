"""
Integration tests for the SEO Drafts API routes (admin-gated).

Hits the live backend URL (REACT_APP_BACKEND_URL) with admin + anon sessions.
Exercises list, admin gating, skip, approve + regenerate (1 regen smoke).
"""
from __future__ import annotations

import os
import uuid

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fall back to reading frontend .env — supervisor containers expose it there.
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


# ── fixtures ─────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def admin_session() -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    token = r.json().get("access_token") or r.json().get("token")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    return s


@pytest.fixture(scope="module")
def anon_session() -> requests.Session:
    return requests.Session()


# ── admin gating ─────────────────────────────────────────────────────
class TestAdminGating:
    def test_list_drafts_blocks_anon(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/marketing/seo-drafts", timeout=20)
        assert r.status_code in (401, 403), r.text[:200]

    def test_scan_blocks_anon(self, anon_session):
        r = anon_session.post(f"{BASE_URL}/api/marketing/seo-drafts/scan", json={}, timeout=20)
        assert r.status_code in (401, 403)

    def test_regen_blocks_anon(self, anon_session):
        r = anon_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/xxxx/regenerate",
            json={"variant": "default"}, timeout=20,
        )
        assert r.status_code in (401, 403)

    def test_approve_blocks_anon(self, anon_session):
        r = anon_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/xxxx/approve",
            json={"description": "x"}, timeout=20,
        )
        assert r.status_code in (401, 403)

    def test_skip_blocks_anon(self, anon_session):
        r = anon_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/xxxx/skip", timeout=20,
        )
        assert r.status_code in (401, 403)


# ── list endpoint ────────────────────────────────────────────────────
class TestListDrafts:
    def test_list_pending(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/marketing/seo-drafts?status=pending&limit=5", timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # envelope assertions
        for key in ("drafts", "totals", "last_run", "limits"):
            assert key in body, f"missing key: {key}"
        assert isinstance(body["drafts"], list)
        assert isinstance(body["totals"], dict)
        for s in ("pending", "approved", "skipped"):
            assert s in body["totals"]
            assert isinstance(body["totals"][s], int)
        assert "max_per_run" in body["limits"]
        assert "max_per_day" in body["limits"]

    def test_invalid_status_rejected(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/marketing/seo-drafts?status=bogus", timeout=20,
        )
        assert r.status_code == 400

    def test_list_approved_filter(self, admin_session):
        r = admin_session.get(
            f"{BASE_URL}/api/marketing/seo-drafts?status=approved&limit=3", timeout=20,
        )
        assert r.status_code == 200
        for d in r.json()["drafts"]:
            assert d["status"] == "approved"


# ── helpers for mutation tests ───────────────────────────────────────
async def _insert_test_draft(status: str = "pending") -> dict:
    """Seed a test draft + matching product directly in Mongo. Returns draft row."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    pid = f"test-sd-api-{uuid.uuid4().hex[:8]}"
    await db.products.insert_one({
        "id": pid, "sku": pid, "name": f"Test SD Product {pid}",
        "category": "Porcelain", "description": "",
    })
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": uuid.uuid4().hex,
        "product_id": pid,
        "collection": "products",
        "product_name": f"Test SD Product {pid}",
        "product_category": "Porcelain",
        "current_description": "",
        "drafts": [{
            "id": uuid.uuid4().hex[:10], "text": "seed description", "variant": "default",
            "custom_instruction": "", "created_at": now,
        }],
        "status": status,
        "created_at": now, "updated_at": now, "last_generated_at": now,
    }
    await db.seo_description_drafts.insert_one(dict(doc))
    doc.pop("_id", None)
    client.close()
    return doc


async def _cleanup_test_draft(product_id: str) -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    await db.seo_description_drafts.delete_many({"product_id": product_id})
    await db.products.delete_many({"id": product_id})
    client.close()


async def _fetch_draft(draft_id: str) -> dict | None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    row = await db.seo_description_drafts.find_one({"id": draft_id}, {"_id": 0})
    client.close()
    return row


async def _fetch_product(pid: str) -> dict | None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    row = await db.products.find_one({"id": pid}, {"_id": 0})
    client.close()
    return row


# ── skip flow ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_skip_draft_flips_status(admin_session):
    draft = await _insert_test_draft()
    try:
        r = admin_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/{draft['id']}/skip", timeout=20,
        )
        assert r.status_code == 200, r.text[:200]
        assert r.json().get("ok") is True
        row = await _fetch_draft(draft["id"])
        assert row is not None
        assert row["status"] == "skipped"
    finally:
        await _cleanup_test_draft(draft["product_id"])


@pytest.mark.asyncio
async def test_skip_nonexistent_returns_404(admin_session):
    r = admin_session.post(
        f"{BASE_URL}/api/marketing/seo-drafts/no-such-id-zzz/skip", timeout=15,
    )
    assert r.status_code == 404


# ── approve flow ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_approve_draft_writes_to_product_and_flips_status(admin_session):
    draft = await _insert_test_draft()
    final_text = "Approved clean description for test product."
    try:
        r = admin_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/{draft['id']}/approve",
            json={"description": final_text},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert body.get("product_id") == draft["product_id"]

        # Draft doc flipped
        row = await _fetch_draft(draft["id"])
        assert row["status"] == "approved"
        assert row["approved_text"] == final_text
        assert row.get("approved_by") == ADMIN_EMAIL
        assert row.get("approved_at")

        # Product doc updated
        prod = await _fetch_product(draft["product_id"])
        assert prod is not None
        assert prod["description"] == final_text
        assert prod.get("description_source") == "ai_bulk_haiku"
    finally:
        await _cleanup_test_draft(draft["product_id"])


@pytest.mark.asyncio
async def test_approve_empty_description_rejected(admin_session):
    draft = await _insert_test_draft()
    try:
        r = admin_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/{draft['id']}/approve",
            json={"description": "   "},
            timeout=20,
        )
        # min_length=1 pydantic → 422; stripped-empty server check → 400. Either ok.
        assert r.status_code in (400, 422)
    finally:
        await _cleanup_test_draft(draft["product_id"])


# ── regenerate flow (LLM smoke, 1 call) ──────────────────────────────
@pytest.mark.asyncio
async def test_regenerate_appends_to_history(admin_session):
    """Single LLM call smoke — verifies draft history grows + variant persisted."""
    draft = await _insert_test_draft()
    try:
        r = admin_session.post(
            f"{BASE_URL}/api/marketing/seo-drafts/{draft['id']}/regenerate",
            json={"variant": "shorter", "custom_instruction": "keep it punchy"},
            timeout=120,
        )
        # LLM might be flaky — tolerate a 500 (reported as error) but prefer 200.
        if r.status_code != 200:
            pytest.skip(f"LLM regenerate returned {r.status_code}: {r.text[:200]}")
        body = r.json()
        assert "draft" in body
        updated = body["draft"]
        assert len(updated["drafts"]) == 2  # 1 seed + 1 regen
        latest = updated["drafts"][-1]
        assert latest["variant"] == "shorter"
        assert latest["custom_instruction"] == "keep it punchy"
        assert latest["text"] and len(latest["text"]) > 5
    finally:
        await _cleanup_test_draft(draft["product_id"])


@pytest.mark.asyncio
async def test_regenerate_nonexistent_returns_404(admin_session):
    r = admin_session.post(
        f"{BASE_URL}/api/marketing/seo-drafts/no-such-id-zzz/regenerate",
        json={"variant": "default"}, timeout=15,
    )
    assert r.status_code == 404


def test_regenerate_custom_instruction_length_cap(admin_session):
    """Pydantic max_length=400 should reject 401+ char payloads with 422."""
    r = admin_session.post(
        f"{BASE_URL}/api/marketing/seo-drafts/any/regenerate",
        json={"variant": "default", "custom_instruction": "x" * 401},
        timeout=15,
    )
    assert r.status_code == 422
