"""Tests for services.health_monitor — protects against the timezone-naive
crash + duplicate-incident pile-up that caused the May 2026 prod outage."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest


# -- _should_dispatch tests ---------------------------------------------

@pytest.mark.asyncio
async def test_should_dispatch_naive_datetime_does_not_crash():
    """Regression: legacy state docs from Mongo have naive `last_alerted_at`.
    Before the Feb 2026 fix, this caused TypeError → no alerts ever fired."""
    from services.health_monitor import _should_dispatch
    naive_old = datetime(2026, 1, 1, 0, 0)  # no tzinfo
    state = {"last_alerted_at": naive_old}
    # 4 weeks old → should dispatch
    result = await _should_dispatch(state)
    assert result is True


@pytest.mark.asyncio
async def test_should_dispatch_aware_datetime_old_returns_true():
    """Aware datetime older than 5 minutes → dispatch."""
    from services.health_monitor import _should_dispatch
    long_ago = datetime.now(timezone.utc) - timedelta(minutes=10)
    state = {"last_alerted_at": long_ago}
    assert await _should_dispatch(state) is True


@pytest.mark.asyncio
async def test_should_dispatch_aware_datetime_recent_returns_false():
    """Aware datetime within last 5 minutes → suppress."""
    from services.health_monitor import _should_dispatch
    recent = datetime.now(timezone.utc) - timedelta(seconds=30)
    state = {"last_alerted_at": recent}
    assert await _should_dispatch(state) is False


@pytest.mark.asyncio
async def test_should_dispatch_naive_recent_does_not_crash():
    """Combining naive datetime + recent time still must not crash."""
    from services.health_monitor import _should_dispatch
    # naive but the wall-clock-equivalent of 30s ago
    naive_recent = datetime.utcnow() - timedelta(seconds=30)
    state = {"last_alerted_at": naive_recent}
    # Coerced to UTC, this is "recent" → suppress
    result = await _should_dispatch(state)
    assert result is False


@pytest.mark.asyncio
async def test_should_dispatch_none_returns_true():
    """No previous alert → dispatch."""
    from services.health_monitor import _should_dispatch
    assert await _should_dispatch({}) is True
    assert await _should_dispatch({"last_alerted_at": None}) is True


@pytest.mark.asyncio
async def test_should_dispatch_string_iso_works():
    """Some legacy rows have ISO strings, not datetimes."""
    from services.health_monitor import _should_dispatch
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    state = {"last_alerted_at": long_ago}
    assert await _should_dispatch(state) is True


@pytest.mark.asyncio
async def test_should_dispatch_string_z_suffix_works():
    """ISO strings with `Z` suffix (Mongo's default) parse cleanly."""
    from services.health_monitor import _should_dispatch
    long_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
    state = {"last_alerted_at": long_ago}
    assert await _should_dispatch(state) is True


# -- _open_or_continue_incident idempotency tests -----------------------

@pytest.mark.asyncio
async def test_open_or_continue_returns_existing_active(monkeypatch):
    """If state already has active_incident_id, return it without DB write."""
    from services import health_monitor

    state = {"active_incident_id": "existing-id-123", "label": "Tile Products"}
    check = {"label": "Tile Products", "path": "/x", "failure_reason": "boom"}

    async def boom_db():
        raise AssertionError("get_db should not be called when state has incident")

    # Patch get_db so any unexpected DB access raises
    monkeypatch.setattr(health_monitor, "get_db", boom_db)
    result = await health_monitor._open_or_continue_incident(state, check)
    assert result == "existing-id-123"


@pytest.mark.asyncio
async def test_open_or_continue_recovers_from_lost_state(monkeypatch):
    """Regression: if `_save_state` was skipped (e.g. due to the timezone
    bug) `active_incident_id` is lost. Next round MUST find the
    existing unresolved incident in Mongo and reuse it — not create
    a duplicate."""
    from services import health_monitor

    state = {"active_incident_id": None, "label": "Tile Products"}
    check = {"label": "Tile Products", "path": "/x", "failure_reason": "boom"}

    class FakeAlerts:
        find_one_calls = []

        async def find_one(self, query, sort=None):
            FakeAlerts.find_one_calls.append((query, sort))
            return {
                "id": "found-existing-zzz",
                "label": "Tile Products",
                "resolved": False,
            }

        async def insert_one(self, doc):
            raise AssertionError("must NOT insert when an unresolved one exists")

    class FakeDB:
        health_alerts = FakeAlerts()

    monkeypatch.setattr(health_monitor, "get_db", lambda: FakeDB())
    result = await health_monitor._open_or_continue_incident(state, check)
    assert result == "found-existing-zzz"
    assert state["active_incident_id"] == "found-existing-zzz"
    # And it queried for unresolved on the right label
    assert FakeAlerts.find_one_calls[0][0]["label"] == "Tile Products"
    assert FakeAlerts.find_one_calls[0][0]["resolved"] is False


@pytest.mark.asyncio
async def test_open_or_continue_creates_new_when_none_exists(monkeypatch):
    """Genuinely new incident: nothing in Mongo, no state → insert."""
    from services import health_monitor

    state = {"active_incident_id": None, "label": "Tile Products"}
    check = {"label": "Tile Products", "path": "/x", "failure_reason": "boom"}

    inserted = []

    class FakeAlerts:
        async def find_one(self, query, sort=None):
            return None  # Nothing matching

        async def insert_one(self, doc):
            inserted.append(doc)
            return type("R", (), {"inserted_id": "fake"})()

    class FakeDB:
        health_alerts = FakeAlerts()

    monkeypatch.setattr(health_monitor, "get_db", lambda: FakeDB())
    result = await health_monitor._open_or_continue_incident(state, check)
    assert state["active_incident_id"] == result
    assert len(inserted) == 1
    assert inserted[0]["label"] == "Tile Products"
    assert inserted[0]["resolved"] is False


# -- _run_one_round state-persistence regression ------------------------

@pytest.mark.asyncio
async def test_run_one_round_saves_state_even_when_dispatch_raises(monkeypatch):
    """Regression: a crash in dispatch must NOT prevent _save_state.
    Without the try/finally, the Feb 2026 timezone bug caused
    `active_incident_id` to be wiped on every cycle → 10 zombie
    incidents for "Tile Products" piled up over 1h on prod."""
    from services import health_monitor

    saved_states = []

    async def fake_persist(_check):
        return None

    async def fake_get_state(label):
        # Already 1 failure recorded
        return {
            "label": label,
            "consecutive_failures": 1,
            "active_incident_id": None,
            "last_alerted_at": None,
        }

    async def fake_save_state(state):
        saved_states.append(dict(state))

    async def fake_open_or_continue(state, check):
        state["active_incident_id"] = "incident-X"
        return "incident-X"

    async def explosive_dispatch(*_args, **_kwargs):
        raise RuntimeError("Telegram is down")

    class FakeAlertsCol:
        async def update_one(self, *args, **kwargs):
            return None

    class FakeDB:
        health_alerts = FakeAlertsCol()

    # Build a single unhealthy check result
    monkeypatch.setattr(
        health_monitor, "MONITORED_ENDPOINTS",
        [{"label": "Tile Products", "path": "/api/x", "expect_key": None}],
    )
    monkeypatch.setattr(health_monitor, "_persist_check", fake_persist)
    monkeypatch.setattr(health_monitor, "_get_state", fake_get_state)
    monkeypatch.setattr(health_monitor, "_save_state", fake_save_state)
    monkeypatch.setattr(health_monitor, "_open_or_continue_incident", fake_open_or_continue)
    monkeypatch.setattr(health_monitor, "get_db", lambda: FakeDB())

    async def fake_check_one(_client, _ep):
        return {
            "label": "Tile Products", "path": "/api/x",
            "status_code": 0, "elapsed_ms": 12, "healthy": False,
            "failure_reason": "ConnectError: All connection attempts failed",
            "body_preview": "", "checked_at": datetime.now(timezone.utc),
        }
    monkeypatch.setattr(health_monitor, "_check_one", fake_check_one)

    # Patch the dispatch import inside _run_one_round
    import services.alert_dispatcher as ad
    monkeypatch.setattr(ad, "dispatch_outage_alert", explosive_dispatch, raising=False)
    monkeypatch.setattr(ad, "dispatch_recovery_alert", explosive_dispatch, raising=False)

    await health_monitor._run_one_round()

    # State MUST have been saved despite the dispatch crash
    assert len(saved_states) == 1
    saved = saved_states[0]
    assert saved["consecutive_failures"] == 2
    # And the incident_id must be persisted (this is the whole point —
    # without it, next round opens a duplicate)
    assert saved["active_incident_id"] == "incident-X"
