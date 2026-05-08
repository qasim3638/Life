"""Tests for services.sample_followup — protects against double-emails,
respects opt-outs, accurately calculates voucher amounts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest


def _order(*, products, **overrides):
    base = {
        "id": "smp-test-1",
        "order_number": "SMP-260206-AB12CD",
        "customer_email": "test@example.com",
        "customer_name": "Test Customer",
        "products": products,
        "status": "delivered",
        "delivered_at": (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(),
        "created_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_classify_order_counts_free_and_paid():
    from services.sample_followup import _classify_order
    free, paid, total = _classify_order(_order(products=[
        {"id": "1", "price_gbp": 0},
        {"id": "2", "price_gbp": 0},
        {"id": "3", "price_gbp": 5.0},
        {"id": "4", "price_gbp": 5.0},
    ]))
    assert free == 2
    assert paid == 2
    assert total == 10.0


@pytest.mark.asyncio
async def test_classify_order_handles_missing_price_field():
    """Legacy orders (pre-Feb-2026) have no price_gbp field — treat as free."""
    from services.sample_followup import _classify_order
    free, paid, total = _classify_order(_order(products=[
        {"id": "1"},
        {"id": "2"},
    ]))
    assert free == 2
    assert paid == 0
    assert total == 0


@pytest.mark.asyncio
async def test_voucher_code_format():
    from services.sample_followup import _voucher_code
    code = _voucher_code()
    assert code.startswith("SAMPLE-")
    assert len(code) > 10
    # Two consecutive calls produce different codes
    assert _voucher_code() != _voucher_code()


@pytest.mark.asyncio
async def test_process_one_skips_already_sent():
    from services import sample_followup

    db = AsyncMock()
    db.sample_followup_sent.find_one = AsyncMock(return_value={"id": "already"})
    order = _order(products=[{"id": "1", "price_gbp": 0}])
    result = await sample_followup.process_one(db, order)
    assert result == "already_sent"


@pytest.mark.asyncio
async def test_process_one_skips_opt_out():
    from services import sample_followup

    db = AsyncMock()
    db.sample_followup_sent.find_one = AsyncMock(return_value=None)
    db.shop_customers.find_one = AsyncMock(return_value={
        "email": "test@example.com",
        "email_preferences": {"no_marketing": True},
    })
    order = _order(products=[{"id": "1", "price_gbp": 0}])
    result = await sample_followup.process_one(db, order)
    assert result == "opt_out"


@pytest.mark.asyncio
async def test_process_one_skips_recent_order():
    from services import sample_followup

    db = AsyncMock()
    db.sample_followup_sent.find_one = AsyncMock(return_value=None)
    db.shop_customers.find_one = AsyncMock(return_value=None)
    db.orders.find_one = AsyncMock(return_value={
        "id": "ord-1",
        "order_type": "purchase",
    })
    order = _order(products=[{"id": "1", "price_gbp": 0}])
    result = await sample_followup.process_one(db, order)
    assert result == "already_ordered"


@pytest.mark.asyncio
async def test_process_one_creates_voucher_when_paid():
    from services import sample_followup

    db = AsyncMock()
    db.sample_followup_sent.find_one = AsyncMock(return_value=None)
    db.shop_customers.find_one = AsyncMock(return_value=None)
    db.orders.find_one = AsyncMock(return_value=None)  # no recent order
    db.vouchers.insert_one = AsyncMock(return_value=None)
    db.sample_followup_sent.insert_one = AsyncMock(return_value=None)

    order = _order(products=[
        {"id": "1", "price_gbp": 5.0},
        {"id": "2", "price_gbp": 5.0},
    ])

    with patch("services.email.send_sample_followup_email", new=AsyncMock(return_value={"sent": True})):
        result = await sample_followup.process_one(db, order)

    assert result == "sent"
    # Voucher was inserted with £10 amount
    assert db.vouchers.insert_one.called
    call_args = db.vouchers.insert_one.call_args
    voucher = call_args.args[0] if call_args.args else call_args.kwargs.get("document")
    assert voucher["amount_gbp"] == 10.0
    assert voucher["single_use"] is True
    assert voucher["used"] is False
    assert voucher["issued_for"] == "sample_followup"


@pytest.mark.asyncio
async def test_process_one_no_voucher_when_only_free_samples():
    from services import sample_followup

    db = AsyncMock()
    db.sample_followup_sent.find_one = AsyncMock(return_value=None)
    db.shop_customers.find_one = AsyncMock(return_value=None)
    db.orders.find_one = AsyncMock(return_value=None)
    db.vouchers.insert_one = AsyncMock(return_value=None)
    db.sample_followup_sent.insert_one = AsyncMock(return_value=None)

    order = _order(products=[
        {"id": "1", "price_gbp": 0},
        {"id": "2", "price_gbp": 0},
    ])

    with patch("services.email.send_sample_followup_email", new=AsyncMock(return_value={"sent": True})):
        result = await sample_followup.process_one(db, order)

    assert result == "sent"
    # No voucher created when nothing was paid
    assert not db.vouchers.insert_one.called


@pytest.mark.asyncio
async def test_run_followup_pass_returns_summary_shape():
    """Top-level pass MUST always return the canonical summary dict so
    the admin UI / logs can rely on the shape."""
    from services.sample_followup import run_followup_pass

    with patch("config.get_db") as get_db:
        db = AsyncMock()

        # Empty cursor — returns no orders
        async def empty():
            for _ in []:
                yield _

        db.sample_orders.find = lambda *a, **k: type(
            "Cursor", (), {
                "sort": lambda self, *a, **k: empty(),
            }
        )()
        get_db.return_value = db
        summary = await run_followup_pass()

    assert set(summary.keys()) >= {
        "scanned", "eligible", "sent",
        "skipped_already_sent", "skipped_already_ordered",
        "skipped_opt_out", "errors",
    }


@pytest.mark.asyncio
async def test_voucher_email_capped_at_5_per_full_size():
    """Voucher amount = min(total_paid, paid_count × £5). Defends
    against a future bug where someone manually set price_gbp = £50."""
    from services import sample_followup

    db = AsyncMock()
    db.sample_followup_sent.find_one = AsyncMock(return_value=None)
    db.shop_customers.find_one = AsyncMock(return_value=None)
    db.orders.find_one = AsyncMock(return_value=None)
    db.vouchers.insert_one = AsyncMock(return_value=None)
    db.sample_followup_sent.insert_one = AsyncMock(return_value=None)

    # Imagine a malformed order with £50 price for a Full Size sample
    order = _order(products=[{"id": "1", "price_gbp": 50.0}])

    with patch("services.email.send_sample_followup_email", new=AsyncMock(return_value={"sent": True})):
        await sample_followup.process_one(db, order)

    voucher_call = db.vouchers.insert_one.call_args
    voucher = voucher_call.args[0] if voucher_call.args else voucher_call.kwargs.get("document")
    # Even though the order shows £50 paid, voucher caps at £5 (1 × £5)
    assert voucher["amount_gbp"] == 5.0
