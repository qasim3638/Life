"""
Regression test for the per-line credit-back breakdown HTML injected into
the trade "You just earned £X credit" Resend email (services/email.py).

Verifies:
  1. When the invoice carries a `trade_credit_breakdown` list, the generated
     HTML contains a "Per-product credit breakdown" panel with one <tr> per
     line item, each row rendering the product name + rate × net + £ credit
     column.
  2. Long product names (>48 chars) are truncated with an ellipsis so narrow
     Gmail mobile views don't overflow.
  3. When no breakdown is stamped on the invoice, the breakdown panel is
     OMITTED entirely — legacy invoices render unchanged.
  4. The "Forward this email to your accountant" hint line renders under the
     breakdown table.
"""
import os
import sys
import asyncio
from unittest.mock import patch

# Make `backend/` importable when running this file directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.email import send_trade_credit_earned_email  # noqa: E402


def _base_invoice(with_breakdown=True, long_name=False):
    breakdown = []
    if with_breakdown:
        name = (
            "A Very Extremely Long Supplier Product Name That Should Definitely Be Truncated Mid-Sentence"
            if long_name else "Premium Marble Tile"
        )
        breakdown = [
            {"product_name": name, "sku": "TILE-001",
             "quantity": 1, "net": 50.0, "rate": 8.0, "credit": 4.0},
            {"product_name": "Bathroom Sealer", "sku": "SEAL-01",
             "quantity": 1, "net": 50.0, "rate": 2.0, "credit": 1.0},
        ]
    return {
        "customer_email": "trade@example.com",
        "invoice_no": "INV-TEST-ABC",
        "subtotal": 100.0,
        "gross_total": 100.0,
        "showroom_name": "Test Showroom",
        "trade_credit_rate": 5.0,
        "trade_credit_breakdown": breakdown,
    }


def _trade_cust():
    return {
        "trade_account_number": "T-00042",
        "business_name": "Acme Tiles Ltd",
        "name": "Acme Tiles Ltd",
    }


async def run():
    # ── 1. With breakdown ────────────────────────────────────────────────
    with patch("services.email.RESEND_AVAILABLE", True), \
         patch("services.email.RESEND_API_KEY", "re_test"), \
         patch("services.email.resend") as fake_resend:
        fake_resend.Emails.send = lambda payload: {"id": "test"}
        result = await send_trade_credit_earned_email(
            invoice=_base_invoice(with_breakdown=True),
            trade_customer=_trade_cust(),
            credits_earned=5.0,
            balance_after=205.0,
        )
        # Grab the HTML that would have been sent
        # (resend.Emails.send was called via asyncio.to_thread — inspect call_args)
        # Since we replaced resend.Emails.send with a lambda, we need to capture manually.
    # Re-do with a mock that captures
    captured = {}
    def capture(payload):
        captured["html"] = payload.get("html", "")
        return {"id": "test"}

    with patch("services.email.RESEND_AVAILABLE", True), \
         patch("services.email.RESEND_API_KEY", "re_test"), \
         patch("services.email.resend") as fake_resend:
        fake_resend.Emails.send = capture
        await send_trade_credit_earned_email(
            invoice=_base_invoice(with_breakdown=True),
            trade_customer=_trade_cust(),
            credits_earned=5.0,
            balance_after=205.0,
        )
    html = captured["html"]
    assert "Per-product credit breakdown" in html, \
        "Expected breakdown panel header in HTML"
    assert "Premium Marble Tile" in html, "Expected line 1 product name"
    assert "Bathroom Sealer" in html, "Expected line 2 product name"
    assert "8% × £50.00" in html, "Expected premium rate calc"
    assert "2% × £50.00" in html, "Expected default rate calc"
    assert "£4.00" in html, "Expected per-line credit £4.00"
    assert "£1.00" in html, "Expected per-line credit £1.00"
    assert "Total credit earned" in html, "Expected total row label"
    assert "Forward this email to your accountant" in html, \
        "Expected accountant-forward hint line"
    print("[1] Per-line breakdown renders in email ✓")

    # ── 2. Long product names truncated ─────────────────────────────────
    with patch("services.email.RESEND_AVAILABLE", True), \
         patch("services.email.RESEND_API_KEY", "re_test"), \
         patch("services.email.resend") as fake_resend:
        fake_resend.Emails.send = capture
        await send_trade_credit_earned_email(
            invoice=_base_invoice(with_breakdown=True, long_name=True),
            trade_customer=_trade_cust(),
            credits_earned=5.0,
            balance_after=205.0,
        )
    html2 = captured["html"]
    # The long name is truncated at 47 chars + ellipsis
    assert "A Very Extremely Long Supplier Product Name Tha" in html2, \
        "Expected truncated long-name prefix"
    assert "…" in html2, "Expected ellipsis on truncated name"
    # Full untruncated name should NOT appear
    full = "Truncated Mid-Sentence"
    assert full not in html2, f"Long name was not truncated: '{full}' leaked through"
    print("[2] Long product names truncated with ellipsis ✓")

    # ── 3. No breakdown → panel omitted ─────────────────────────────────
    with patch("services.email.RESEND_AVAILABLE", True), \
         patch("services.email.RESEND_API_KEY", "re_test"), \
         patch("services.email.resend") as fake_resend:
        fake_resend.Emails.send = capture
        await send_trade_credit_earned_email(
            invoice=_base_invoice(with_breakdown=False),
            trade_customer=_trade_cust(),
            credits_earned=5.0,
            balance_after=205.0,
        )
    html3 = captured["html"]
    assert "Per-product credit breakdown" not in html3, \
        "Breakdown panel should be omitted when invoice has no breakdown"
    # But the summary card should still render
    assert "Credit earned today" in html3
    assert "New balance" in html3
    print("[3] Legacy invoices without breakdown render cleanly ✓")

    print("\nAll credit-email breakdown assertions PASSED ✅")


asyncio.run(run())
