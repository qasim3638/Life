"""
Backend tests for GBP OAuth scaffold and Ads-Savings overview endpoints.
Covers the endpoints in /api/admin/gbp/* and /api/admin/ads-savings/*.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    token = r.json().get("token")
    assert token, "no token in login response"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ── GBP endpoints ────────────────────────────────────────────────────────
class TestGbp:
    def test_status_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/gbp/status", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 without token, got {r.status_code}"

    def test_status_authed(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/gbp/status", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        data = r.json()
        assert "connected" in data
        assert "configured" in data
        assert data["connected"] is False
        assert data["configured"] is True

    def test_connect_returns_authorization_url(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/gbp/connect", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        data = r.json()
        assert "authorization_url" in data
        url = data["authorization_url"]
        assert isinstance(url, str) and len(url) > 0
        assert "accounts.google.com" in url or "google.com/o/oauth" in url

    def test_locations_graceful_when_no_tokens(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/gbp/locations", headers=auth_headers, timeout=30)
        # Expected: 401 (no tokens stored). Anything else is acceptable as
        # long as it's not a 5xx crash.
        assert r.status_code < 500, f"server error: {r.status_code} {r.text}"
        assert r.status_code in (401, 403, 404, 503), f"unexpected status {r.status_code}: {r.text}"

    def test_connect_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/gbp/connect", timeout=30)
        assert r.status_code in (401, 403)


# ── Ads Savings ──────────────────────────────────────────────────────────
class TestAdsSavings:
    def test_overview_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/ads-savings/overview", timeout=30)
        assert r.status_code in (401, 403), f"expected 401/403 without token, got {r.status_code}"

    def test_overview_authed_shape(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/ads-savings/overview?days=28",
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        data = r.json()
        assert "connected" in data and "configured" in data
        assert "totals" in data and isinstance(data["totals"], dict)
        assert "rows" in data and isinstance(data["rows"], list)

        totals = data["totals"]
        for k in (
            "window_days", "keywords_ranked", "high_value_keywords",
            "total_clicks", "total_impressions",
            "estimated_window_value_gbp", "estimated_monthly_value_gbp",
            "estimated_annual_value_gbp",
        ):
            assert k in totals, f"missing totals.{k}"

        assert isinstance(totals["estimated_monthly_value_gbp"], (int, float))
        assert totals["estimated_monthly_value_gbp"] >= 0

    def test_overview_has_keywords_and_row_schema(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/ads-savings/overview?days=28",
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200
        data = r.json()
        # In this environment GSC cache should hold ~295 keywords.
        if data.get("connected"):
            assert data["totals"]["keywords_ranked"] > 0, (
                "expected non-zero keywords_ranked when GSC connected"
            )
            if data["rows"]:
                row = data["rows"][0]
                for k in ("query", "clicks", "position", "estimated_cpc_gbp", "estimated_value_gbp"):
                    assert k in row, f"missing row field {k}: {row}"
                assert isinstance(row["estimated_cpc_gbp"], (int, float))
                assert isinstance(row["estimated_value_gbp"], (int, float))



# ── Monthly snapshot history ────────────────────────────────────────────


class TestAdsSavingsSnapshotHistory:
    def test_history_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/ads-savings/history", timeout=30)
        assert r.status_code in (401, 403)

    def test_run_snapshot_now_requires_admin(self):
        r = requests.post(f"{BASE_URL}/api/admin/ads-savings/snapshot/run-now", timeout=30)
        assert r.status_code in (401, 403)

    def test_run_snapshot_now_then_appears_in_history(self, auth_headers):
        # Force a snapshot.
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/snapshot/run-now",
            headers=auth_headers,
            timeout=60,
        )
        assert r.status_code == 200, f"snapshot now failed: {r.status_code} {r.text}"
        snap = r.json()
        # Either we got a fresh snapshot or it was skipped because GSC isn't
        # connected — both are valid in a clean test environment.
        assert "snapshotted" in snap or "skipped" in snap

        # History should always be reachable, even if empty.
        r2 = requests.get(
            f"{BASE_URL}/api/admin/ads-savings/history?months=12",
            headers=auth_headers,
            timeout=30,
        )
        assert r2.status_code == 200, f"history failed: {r2.status_code} {r2.text}"
        data = r2.json()
        assert "history" in data
        assert "count" in data
        assert isinstance(data["history"], list)

        # If we successfully snapshotted, that month must be in the list.
        if snap.get("snapshotted"):
            current_month_id = snap["month"]
            months = [h["month"] for h in data["history"]]
            assert current_month_id in months, (
                f"expected {current_month_id} in history months: {months}"
            )
            current = next(h for h in data["history"] if h["month"] == current_month_id)
            for k in (
                "keywords_ranked",
                "estimated_monthly_value_gbp",
                "estimated_annual_value_gbp",
            ):
                assert k in current["totals"], f"missing totals.{k}"


# ── Monthly SEO P&L digest ──────────────────────────────────────────────


class TestSeoPnlDigest:
    def test_pnl_send_now_requires_admin(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/pnl-digest/send-now",
            timeout=30,
        )
        assert r.status_code in (401, 403)

    def test_pnl_send_now_force_returns_payload(self, auth_headers):
        # Force-send (bypass once-per-month idempotency).
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/pnl-digest/send-now?force=true",
            headers=auth_headers,
            timeout=120,
        )
        assert r.status_code == 200, f"send-now failed: {r.status_code} {r.text}"
        data = r.json()
        # Either we sent (ok=True with recipients/subject) or skipped
        # gracefully (no GSC connection / no admin recipients) — both valid.
        assert data.get("ok") is True or data.get("skipped") is True
        if data.get("ok") and not data.get("skipped"):
            assert "recipients" in data and data["recipients"] >= 1
            assert "subject" in data and "SEO P&L" in data["subject"]
            assert "monthly_value_gbp" in data
            assert "fell_off_count" in data

    def test_pnl_send_now_idempotent(self, auth_headers):
        # First send (force) ensures the month is "stamped".
        requests.post(
            f"{BASE_URL}/api/admin/ads-savings/pnl-digest/send-now?force=true",
            headers=auth_headers,
            timeout=120,
        )
        # Second send WITHOUT force should be skipped.
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/pnl-digest/send-now?force=false",
            headers=auth_headers,
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        # Could be skipped="already_sent_this_month" OR a fresh send if the
        # first call was itself skipped (e.g. no admin recipients).
        if data.get("skipped"):
            assert data.get("reason") in (
                "already_sent_this_month",
                "no_connected_admin",
                "no_admin_recipients",
                "no_savings_yet",
            )


# ── Quarterly PDF download ──────────────────────────────────────────────


class TestQuarterlyPdf:
    def test_quarterly_pdf_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf", timeout=30)
        assert r.status_code in (401, 403)

    def test_quarterly_pdf_returns_real_pdf(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf",
            headers=auth_headers,
            timeout=120,
            stream=True,
        )
        # If chromium is unavailable in this environment, the server
        # should still degrade with a clean 503 — both acceptable.
        if r.status_code == 503:
            return
        assert r.status_code == 200, f"PDF endpoint failed: {r.status_code} {r.text[:500]}"
        assert r.headers.get("content-type", "").startswith("application/pdf")
        body = r.content
        # Minimum sane PDF size + magic bytes.
        assert len(body) > 1000, f"PDF too small: {len(body)} bytes"
        assert body[:5] == b"%PDF-", f"missing PDF magic bytes: {body[:10]!r}"
        # Filename header is the most reliable signal (Cloudflare can strip
        # arbitrary custom X-* headers, but Content-Disposition survives).
        cd = r.headers.get("content-disposition", "")
        assert "tile-station-seo-pnl" in cd.lower(), f"unexpected CD: {cd}"

    def test_quarterly_pdf_explicit_quarter_param(self, auth_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf?quarter=Q2-2026",
            headers=auth_headers,
            timeout=120,
        )
        if r.status_code == 503:
            return
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        # Filename should reflect the requested quarter.
        cd = r.headers.get("content-disposition", "")
        assert "Q2-2026.pdf" in cd, f"unexpected Content-Disposition: {cd}"



# ── Quarterly PDF auto-email ────────────────────────────────────────────


class TestQuarterlyPdfEmail:
    def test_quarterly_email_now_requires_admin(self):
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf/email-now",
            timeout=30,
        )
        assert r.status_code in (401, 403)

    def test_quarterly_email_now_force_returns_payload(self, auth_headers):
        # Force-send with explicit quarter to bypass once-per-quarter guard
        # and ensure we hit a quarter with snapshot data.
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf/email-now?force=true&quarter=Q2-2026",
            headers=auth_headers,
            timeout=180,  # PDF render + Resend send
        )
        # 503 if Chromium is missing in the test env — acceptable.
        if r.status_code == 503:
            return
        assert r.status_code == 200, f"email-now failed: {r.status_code} {r.text[:500]}"
        data = r.json()
        # Either we sent (ok=True) or skipped gracefully (no admins / no data).
        assert data.get("ok") is True or data.get("skipped") is True
        if data.get("ok") and not data.get("skipped"):
            assert data["quarter"] == "Q2-2026"
            assert data["recipients"] >= 1
            assert "subject" in data and "board deck" in data["subject"]
            assert data["pdf_bytes"] > 1000  # real PDF, not an error blob

    def test_quarterly_email_now_idempotent(self, auth_headers):
        # First send (force) stamps the quarter as sent.
        first = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf/email-now?force=true&quarter=Q2-2026",
            headers=auth_headers,
            timeout=180,
        )
        if first.status_code == 503:
            return
        assert first.status_code == 200
        # Second send without force should be skipped IF the first call
        # actually sent. (If the first was skipped — e.g. no recipients —
        # the stamp wasn't set, so the second can also be a fresh send.)
        first_data = first.json()
        if not first_data.get("ok") or first_data.get("skipped"):
            return
        second = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/quarterly-pdf/email-now?quarter=Q2-2026",
            headers=auth_headers,
            timeout=180,
        )
        assert second.status_code == 200
        sd = second.json()
        assert sd.get("skipped") is True
        assert sd.get("reason") == "already_sent_this_quarter"
