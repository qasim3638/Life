"""
Lightweight promo / discount code service.

Used today by the abandoned-cart sequence (day-1 email auto-mints a single-use
code per cart). The same collection can be reused by other sources (manual
campaigns, etc.) by setting `source` to the appropriate key.

Data model — collection: `shop_discount_codes`
{
  code: "BACK10-AB12CD",        # Display code (uppercase, unique)
  percent_off: 10,              # 0..100
  max_uses: 1,                  # how many separate orders can apply it
  used_count: 0,
  email: "shopper@x.com",       # If set, only this email may apply the code
  source: "abandoned_cart",
  expires_at: ISO datetime,
  min_subtotal: 0,
  active: true,
  created_at, updated_at
}
"""
import secrets
import string
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict


def _gen_code(prefix: str) -> str:
    rand = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"{prefix.upper()}-{rand}"


async def generate_promo_code_for_email(
    db,
    email: str,
    percent_off: int = 10,
    expires_days: int = 7,
    source: str = "abandoned_cart",
    prefix: str = "BACK",
) -> Dict:
    """Mint a single-use promo code attached to one email."""
    now = datetime.now(timezone.utc)

    # Reuse existing unused code for this email + source if still valid
    existing = await db.shop_discount_codes.find_one({
        "email": email.lower(),
        "source": source,
        "active": True,
        "used_count": 0,
    })
    if existing:
        exp = existing.get("expires_at")
        if isinstance(exp, datetime):
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                return {
                    "code": existing["code"],
                    "percent_off": existing["percent_off"],
                    "expires_at": exp.isoformat(),
                }

    # Mint a new one with a unique-ish code (retry until unique)
    for _ in range(8):
        candidate = _gen_code(prefix)
        if not await db.shop_discount_codes.find_one({"code": candidate}):
            break
    else:
        raise RuntimeError("Could not generate a unique promo code")

    doc = {
        "code": candidate,
        "percent_off": percent_off,
        "max_uses": 1,
        "used_count": 0,
        "email": email.lower(),
        "source": source,
        "expires_at": now + timedelta(days=expires_days),
        "min_subtotal": 0,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.shop_discount_codes.insert_one(doc)
    return {
        "code": candidate,
        "percent_off": percent_off,
        "expires_at": doc["expires_at"].isoformat(),
    }


async def generate_referral_code(
    db,
    referrer_email: str,
    percent_off: int = 10,
    max_uses: int = 25,
    expires_days: int = 30,
) -> Dict:
    """Mint a multi-use referral code anyone can redeem (no email lock).

    Returns the referrer's existing FRIEND-XXXXXX if they already have an active
    one with capacity remaining, otherwise mints a new one.
    """
    now = datetime.now(timezone.utc)

    # Reuse an existing referral code with capacity remaining
    existing = await db.shop_discount_codes.find_one({
        "referrer_email": referrer_email.lower(),
        "source": "referral",
        "active": True,
    })
    if existing:
        exp = existing.get("expires_at")
        if isinstance(exp, datetime):
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            still_valid = (
                exp > now
                and existing.get("used_count", 0) < existing.get("max_uses", 1)
            )
            if still_valid:
                return {
                    "code": existing["code"],
                    "percent_off": existing["percent_off"],
                    "max_uses": existing.get("max_uses", 1),
                    "used_count": existing.get("used_count", 0),
                    "expires_at": exp.isoformat(),
                }

    # Mint a new code
    for _ in range(8):
        candidate = _gen_code("FRIEND")
        if not await db.shop_discount_codes.find_one({"code": candidate}):
            break
    else:
        raise RuntimeError("Could not generate a unique referral code")

    doc = {
        "code": candidate,
        "percent_off": percent_off,
        "max_uses": max_uses,
        "used_count": 0,
        "email": "",  # No lock — anyone can redeem
        "referrer_email": referrer_email.lower(),
        "source": "referral",
        "expires_at": now + timedelta(days=expires_days),
        "min_subtotal": 0,
        "active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.shop_discount_codes.insert_one(doc)
    return {
        "code": candidate,
        "percent_off": percent_off,
        "max_uses": max_uses,
        "used_count": 0,
        "expires_at": doc["expires_at"].isoformat(),
    }


async def validate_promo_code(db, code: str, email: Optional[str], subtotal: float) -> Dict:
    """Return {valid, percent_off, discount_amount, reason?} for a given code."""
    if not code:
        return {"valid": False, "reason": "No code provided"}

    doc = await db.shop_discount_codes.find_one({"code": code.strip().upper()})
    if not doc:
        return {"valid": False, "reason": "Code not found"}
    if not doc.get("active", True):
        return {"valid": False, "reason": "Code is inactive"}
    if doc.get("used_count", 0) >= doc.get("max_uses", 1):
        return {"valid": False, "reason": "Code has already been used"}

    expires_at = doc.get("expires_at")
    if isinstance(expires_at, datetime):
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return {"valid": False, "reason": "Code has expired"}

    attached_email = (doc.get("email") or "").lower()
    is_referral = doc.get("source") == "referral"
    # Referral codes have no email lock by design — anyone can redeem.
    if not is_referral:
        if attached_email and email and email.lower() != attached_email:
            return {"valid": False, "reason": "Code is not valid for this email"}
        if attached_email and not email:
            return {"valid": False, "reason": "Code requires the original recipient's email"}

    min_sub = float(doc.get("min_subtotal") or 0)
    if subtotal < min_sub:
        return {"valid": False, "reason": f"Minimum subtotal £{min_sub:.2f} not met"}

    percent_off = int(doc.get("percent_off") or 0)
    discount_amount = round(subtotal * percent_off / 100.0, 2)
    return {
        "valid": True,
        "code": doc["code"],
        "percent_off": percent_off,
        "discount_amount": discount_amount,
    }


async def consume_promo_code(db, code: str) -> bool:
    """Mark code as consumed (called after order is created with that code applied)."""
    if not code:
        return False
    res = await db.shop_discount_codes.update_one(
        {"code": code.strip().upper()},
        {"$inc": {"used_count": 1}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    return res.modified_count > 0
