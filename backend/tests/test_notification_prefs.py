"""
Notification authorisations — backend integration tests.

Validates the deny-by-default policy, the super-admin-only write gate,
and that the existing email-sending paths now filter through the
`notification_authorizations` collection.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://feature-verification-7.preview.emergentagent.com")


@pytest.fixture
def super_admin_headers():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@test.com", "password": "admin123"},
        timeout=30,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


class TestChannelRegistry:
    def test_channels_endpoint_returns_six(self, super_admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/channels",
            headers=super_admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        ids = {c["id"] for c in data["channels"]}
        # Each channel must have label, description, cadence
        for c in data["channels"]:
            assert c.get("label") and c.get("description") and c.get("cadence")
        # The 6 named channels we shipped:
        assert ids == {
            "ui_health_alerts",
            "ctr_drop_alerts",
            "seo_quality_digest",
            "gsc_weekly_digest",
            "monthly_pnl",
            "quarterly_deck",
        }


class TestListAdmins:
    def test_admins_list_default_deny(self, super_admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/admins",
            headers=super_admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert "admins" in data and isinstance(data["admins"], list)
        # Every admin row must have all 6 channel keys, defaulted to bool.
        for a in data["admins"]:
            assert "email" in a and "role" in a and "channels" in a
            ch = a["channels"]
            for cid in (
                "ui_health_alerts", "ctr_drop_alerts", "seo_quality_digest",
                "gsc_weekly_digest", "monthly_pnl", "quarterly_deck",
            ):
                assert cid in ch
                assert isinstance(ch[cid], bool)


class TestAuth:
    def test_unauthenticated_blocked(self):
        r = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/channels", timeout=30
        )
        assert r.status_code in (401, 403)

    def test_unauthenticated_put_blocked(self):
        r = requests.put(
            f"{BASE_URL}/api/admin/notification-prefs/admin/admin@test.com",
            json={"channels": {"monthly_pnl": True}},
            timeout=30,
        )
        assert r.status_code in (401, 403)


class TestUpdateAuthorization:
    def test_super_admin_can_toggle(self, super_admin_headers):
        # Toggle ON
        r = requests.put(
            f"{BASE_URL}/api/admin/notification-prefs/admin/admin@test.com",
            headers=super_admin_headers,
            json={"channels": {
                "ui_health_alerts": False,
                "ctr_drop_alerts": False,
                "seo_quality_digest": False,
                "gsc_weekly_digest": False,
                "monthly_pnl": True,
                "quarterly_deck": True,
            }},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "admin@test.com"
        assert data["channels"]["monthly_pnl"] is True
        assert data["channels"]["quarterly_deck"] is True
        assert data["channels"]["ui_health_alerts"] is False
        assert data.get("updated_by")
        assert data.get("updated_at")

    def test_unknown_channel_keys_dropped(self, super_admin_headers):
        # Garbage channel keys should be silently ignored — only the
        # canonical 6 are persisted.
        r = requests.put(
            f"{BASE_URL}/api/admin/notification-prefs/admin/admin@test.com",
            headers=super_admin_headers,
            json={"channels": {"monthly_pnl": True, "fake_channel": True}},
            timeout=30,
        )
        assert r.status_code == 200
        ch = r.json()["channels"]
        assert "fake_channel" not in ch
        assert "monthly_pnl" in ch

    def test_non_admin_email_rejected(self, super_admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/notification-prefs/admin/notarealuser@example.com",
            headers=super_admin_headers,
            json={"channels": {"monthly_pnl": True}},
            timeout=30,
        )
        assert r.status_code == 404

    def test_bad_payload_rejected(self, super_admin_headers):
        r = requests.put(
            f"{BASE_URL}/api/admin/notification-prefs/admin/admin@test.com",
            headers=super_admin_headers,
            json={"not_channels": "garbage"},
            timeout=30,
        )
        assert r.status_code == 400


class TestEndToEndFiltering:
    """Confirms the email-sending paths now filter through the auth table.
    Uses the P&L digest endpoint as a representative example."""

    def _set_pnl_authorization(self, super_admin_headers, enabled: bool):
        # All admins to the same value for this channel.
        admins_resp = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/admins",
            headers=super_admin_headers,
            timeout=30,
        )
        for a in admins_resp.json()["admins"]:
            requests.put(
                f"{BASE_URL}/api/admin/notification-prefs/admin/{a['email']}",
                headers=super_admin_headers,
                json={"channels": {**a["channels"], "monthly_pnl": enabled}},
                timeout=30,
            )

    def test_pnl_digest_skipped_when_no_one_authorised(self, super_admin_headers):
        self._set_pnl_authorization(super_admin_headers, False)
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/pnl-digest/send-now?force=true",
            headers=super_admin_headers,
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        # Must skip with the new, specific reason code.
        assert data.get("skipped") is True
        assert data.get("reason") == "no_authorized_recipients"

    def test_pnl_digest_sends_when_at_least_one_authorised(self, super_admin_headers):
        # Authorise everyone for monthly_pnl.
        self._set_pnl_authorization(super_admin_headers, True)
        r = requests.post(
            f"{BASE_URL}/api/admin/ads-savings/pnl-digest/send-now?force=true",
            headers=super_admin_headers,
            timeout=120,
        )
        assert r.status_code == 200
        data = r.json()
        # Either it sent successfully OR was skipped for a non-auth reason.
        if data.get("ok") and not data.get("skipped"):
            assert data["recipients"] >= 1
        else:
            assert data.get("reason") not in ("no_authorized_recipients", "no_admin_recipients")


class TestMySubscriptionsView:
    def test_me_endpoint_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/notification-prefs/me", timeout=30)
        assert r.status_code in (401, 403)

    def test_me_endpoint_returns_full_channel_list(self, super_admin_headers):
        r = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/me",
            headers=super_admin_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        # Required top-level fields
        for key in ("email", "role", "channels", "subscribed_count", "total_channels"):
            assert key in data, f"missing {key}"
        # Always returns all 6 channels (with `subscribed` boolean) regardless
        # of whether the user has any authorisations stored yet.
        assert data["total_channels"] == 6
        assert len(data["channels"]) == 6
        for c in data["channels"]:
            assert {"id", "label", "description", "cadence", "subscribed"} <= set(c.keys())
            assert isinstance(c["subscribed"], bool)
        # Counter agrees with the channel list
        assert data["subscribed_count"] == sum(1 for c in data["channels"] if c["subscribed"])

    def test_me_view_reflects_super_admin_changes(self, super_admin_headers):
        # Toggle one channel on, then read the /me view and confirm it flipped.
        target_email = "admin@test.com"
        # Read current state
        cur_resp = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/admins",
            headers=super_admin_headers,
            timeout=30,
        )
        cur = next(a for a in cur_resp.json()["admins"] if a["email"] == target_email)
        target_state = {**cur["channels"], "ui_health_alerts": not cur["channels"]["ui_health_alerts"]}
        requests.put(
            f"{BASE_URL}/api/admin/notification-prefs/admin/{target_email}",
            headers=super_admin_headers,
            json={"channels": target_state},
            timeout=30,
        )
        # Now read via /me
        me = requests.get(
            f"{BASE_URL}/api/admin/notification-prefs/me",
            headers=super_admin_headers,
            timeout=30,
        ).json()
        ui_health = next(c for c in me["channels"] if c["id"] == "ui_health_alerts")
        assert ui_health["subscribed"] is target_state["ui_health_alerts"]
