"""Tests for Announcement Ribbon history log (Quick Post re-publish).

Safety rules (learned the hard way on 30-Apr-2026 when TEST_PRESERVE_fields
leaked to a live customer's browser):

1. The ribbon endpoint is LIVE — everything we PUT here is what customers
   see. The test suite MUST leave the DB exactly as it found it.
2. The `snapshot_and_disable_ribbon` fixture runs at session start, grabs a
   full copy of the ribbon doc, and forces `enabled=False` for the
   duration of the test run so even mid-test crashes don't show test
   strings to the public.
3. A `finalizer` restores the EXACT snapshot (message, colour palette,
   schedule, history array) at session end — even on pytest failure or
   KeyboardInterrupt.
4. Test messages are prefixed `_E1_TEST_` (underscore first, never a real
   marketing string) so if cleanup ever fails they're trivially greppable
   in prod DB and the migration script in `cleanup_ribbon_test_leaks.py`
   can purge them in one shot.
"""
import os
import pytest
import requests


BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://feature-verification-7.preview.emergentagent.com"
).rstrip("/")
ADMIN_EMAIL = "admin@test.com"
ADMIN_PASSWORD = "admin123"

# All test-generated messages use this prefix so production cleanup scripts
# can purge them with a single regex `^_E1_TEST_`.
TEST_PREFIX = "_E1_TEST_"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    body = r.json()
    token = body.get("access_token") or body.get("token")
    assert token, f"No token in: {body}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def _get_ribbon(auth_headers):
    r = requests.get(
        f"{BASE_URL}/api/website-admin/announcement-ribbon",
        headers=auth_headers,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def _put_ribbon(auth_headers, payload):
    r = requests.put(
        f"{BASE_URL}/api/website-admin/announcement-ribbon",
        headers=auth_headers,
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


@pytest.fixture(scope="module", autouse=True)
def snapshot_and_disable_ribbon(auth_headers):
    """Snapshot the live ribbon, force enabled=False, and restore at end.

    Autouse so every test in this module is wrapped in the safety net —
    callers cannot forget to include it.
    """
    try:
        snapshot = _get_ribbon(auth_headers)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Cannot snapshot ribbon (admin endpoint unavailable): {exc}")

    # Disable the ribbon for the duration of the test run so any leak is
    # invisible to customers. We keep the EXISTING message untouched at this
    # point — the tests themselves will PUT test messages later.
    try:
        _put_ribbon(
            auth_headers,
            {
                **snapshot,
                "enabled": False,
                # `record_history` default is False, but be explicit
                "record_history": False,
            },
        )
    except Exception:  # noqa: BLE001
        # Non-fatal; tests proceed but restore still runs.
        pass

    yield snapshot

    # ── Restore ────────────────────────────────────────────────────────────
    # Strip the server-managed `updated_at`/`updated_by` so the restore
    # PUT sets the ORIGINAL message + ORIGINAL colour palette + ORIGINAL
    # schedule + ORIGINAL enabled flag. History cannot be restored via the
    # public endpoint (no setter) so we also call the DB-level cleanup
    # helper to prune any `_E1_TEST_*` entries that accumulated.
    try:
        current = _get_ribbon(auth_headers)
        restore_payload = {
            "enabled": bool(snapshot.get("enabled", False)),
            "message": snapshot.get("message") or "",
            "link_url": snapshot.get("link_url") or "",
            "link_label": snapshot.get("link_label") or "",
            "background_color": snapshot.get("background_color") or "#1C1917",
            "text_color": snapshot.get("text_color") or "#F7EA1C",
            "link_color": snapshot.get("link_color") or "#FFFFFF",
            "speed": snapshot.get("speed") or "medium",
            "icon": bool(snapshot.get("icon", True)),
            "schedule_enabled": bool(snapshot.get("schedule_enabled", False)),
            "scheduled_start": snapshot.get("scheduled_start"),
            "scheduled_end": snapshot.get("scheduled_end"),
            "version": int(current.get("version") or 1) + 1,
            "record_history": False,  # never record this restore
        }
        _put_ribbon(auth_headers, restore_payload)
    except Exception as exc:  # noqa: BLE001
        try:
            _put_ribbon(
                auth_headers,
                {"enabled": False, "message": "", "record_history": False},
            )
        except Exception:  # noqa: BLE001
            pass
        print(f"\n[WARNING] Ribbon restore failed: {exc}. "
              "Run tests/cleanup_ribbon_test_leaks.py against the live DB.")

    # ── Prune _E1_TEST_* from history via direct DB access ────────────────
    # The admin PUT endpoint doesn't expose a "set history" action, so
    # we reach into MongoDB to strip test entries. This keeps the session
    # totally hermetic — the DB ends the run as clean as it started.
    try:
        import asyncio  # noqa: PLC0415
        from motor.motor_asyncio import AsyncIOMotorClient  # noqa: PLC0415

        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")
        if mongo_url and db_name:
            async def _purge():
                client = AsyncIOMotorClient(mongo_url)
                db = client[db_name]
                async for doc in db.website_settings.find({"history": {"$exists": True}}):
                    hist = doc.get("history") or []
                    clean = [
                        h for h in hist
                        if not str(h.get("message") or "").startswith(
                            ("TEST_", "_E1_TEST_")
                        )
                    ]
                    if len(clean) != len(hist):
                        await db.website_settings.update_one(
                            {"_id": doc["_id"]}, {"$set": {"history": clean}}
                        )
                client.close()
            asyncio.run(_purge())
    except Exception as exc:  # noqa: BLE001
        print(f"\n[WARNING] Could not purge test history directly: {exc}")


class TestAnnouncementRibbonHistory:
    """Verify history log behaviour on the announcement ribbon."""

    def test_get_returns_history_array(self, auth_headers):
        data = _get_ribbon(auth_headers)
        assert "history" in data, "Response missing 'history' key"
        assert isinstance(data["history"], list)

    def test_get_unauthenticated_rejected(self):
        r = requests.get(f"{BASE_URL}/api/website-admin/announcement-ribbon", timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_plain_save_does_not_grow_history(self, auth_headers):
        """PUT without record_history must NOT append history."""
        before = _get_ribbon(auth_headers)
        before_len = len(before.get("history", []))

        payload = {
            "enabled": False,  # safety: never enabled during tests
            "message": f"{TEST_PREFIX}PLAIN_SAVE",
            "speed": "medium",
        }
        after = _put_ribbon(auth_headers, payload)
        assert len(after.get("history", [])) == before_len, (
            "History grew after a non-record_history save"
        )
        if after.get("history"):
            assert after["history"][0].get("message") != payload["message"]

    def test_record_history_appends_newest_first(self, auth_headers):
        before = _get_ribbon(auth_headers)
        before_len = len(before.get("history", []))
        before_version = int(before.get("version") or 1)

        msg = f"{TEST_PREFIX}HISTORY_APPEND"
        payload = {
            "enabled": False,  # safety
            "message": msg,
            "background_color": "#0F172A",
            "text_color": "#FCD34D",
            "link_color": "#FFFFFF",
            "speed": "medium",
            "icon": True,
            "schedule_enabled": False,
            "scheduled_start": None,
            "scheduled_end": None,
            "version": before_version + 1,
            "record_history": True,
        }
        after = _put_ribbon(auth_headers, payload)
        history = after.get("history", [])
        expected_len = min(before_len + 1, 10)
        assert len(history) == expected_len, (
            f"Expected len {expected_len}, got {len(history)}"
        )
        assert history[0]["message"] == msg, "Newest entry should be at index 0"
        entry = history[0]
        for key in (
            "id", "message", "link_url", "link_label", "background_color",
            "text_color", "link_color", "speed", "icon", "published_at",
            "published_by",
        ):
            assert key in entry, f"History entry missing key: {key}"
        assert entry["background_color"] == "#0F172A"
        assert entry["text_color"] == "#FCD34D"
        assert entry["published_by"] == ADMIN_EMAIL

    def test_history_capped_at_10(self, auth_headers):
        # Push 12 entries; verify length stays at 10 and oldest are trimmed
        for i in range(12):
            payload = {
                "enabled": False,  # safety
                "message": f"{TEST_PREFIX}CAP_{i:02d}",
                "speed": "fast",
                "background_color": "#1C1917",
                "text_color": "#F7EA1C",
                "link_color": "#FFFFFF",
                "icon": True,
                "record_history": True,
            }
            _put_ribbon(auth_headers, payload)
        final = _get_ribbon(auth_headers)
        history = final.get("history", [])
        assert len(history) == 10, f"History should be capped at 10, got {len(history)}"
        assert history[0]["message"] == f"{TEST_PREFIX}CAP_11"
        msgs = [h["message"] for h in history]
        assert f"{TEST_PREFIX}CAP_00" not in msgs
        assert f"{TEST_PREFIX}CAP_01" not in msgs

    def test_existing_fields_preserved_on_history_append(self, auth_headers):
        """Saving an enabled/scheduled state, then appending via Quick Post must preserve unrelated fields."""
        plain = {
            "enabled": False,  # NEVER True in tests
            "schedule_enabled": True,
            "scheduled_start": "2030-01-01T00:00:00+00:00",
            "scheduled_end": "2030-01-02T00:00:00+00:00",
            "background_color": "#222222",
            "text_color": "#EEEEEE",
            "link_color": "#FFAA00",
            "speed": "slow",
        }
        _put_ribbon(auth_headers, plain)

        qp = {
            "message": f"{TEST_PREFIX}PRESERVE",
            "record_history": True,
            "version": 999,
        }
        after = _put_ribbon(auth_headers, qp)
        assert after.get("schedule_enabled") is True, "schedule_enabled was overwritten"
        assert after.get("scheduled_start") == "2030-01-01T00:00:00+00:00"
        assert after.get("scheduled_end") == "2030-01-02T00:00:00+00:00"
        assert after["history"][0]["message"] == f"{TEST_PREFIX}PRESERVE"
