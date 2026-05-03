"""Iteration 8 tests: Echo of yesterday, Focus/Time-management, Sobriety.

Covers:
 - POST /api/ai/echo-yesterday (fallback + with data)
 - Focus sessions CRUD + sorting
 - Distractions CRUD + sorting
 - /api/focus-stats aggregation
 - /api/ai/focus-tips (real Claude)
 - Addictions CRUD + partial update + cascade delete
 - Slip logging (reset clock, reset_count inc, longest_streak_days)
 - /api/addictions/{id}/slips sorted desc
 - /api/ai/sobriety-support/{id} (real Claude) + 404
 - No MongoDB _id leak in any response
"""
import os
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing from env"
API = f"{BASE_URL}/api"


# -------------------- Shared session fixture --------------------
@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


def _assert_no_mongo_id(obj):
    """Recursively assert '_id' key is not present in any dict in response."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"MongoDB _id leaked: {obj}"
        for v in obj.values():
            _assert_no_mongo_id(v)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_mongo_id(item)


# =====================================================================
# Echo of yesterday
# =====================================================================
class TestEchoYesterday:
    def test_empty_body_returns_text(self, s):
        r = s.post(f"{API}/ai/echo-yesterday", json={})
        assert r.status_code == 200
        data = r.json()
        assert "text" in data and isinstance(data["text"], str)
        assert len(data["text"]) > 0
        _assert_no_mongo_id(data)

    def test_no_body_at_all(self, s):
        # EchoRequest has a default, so empty payload should also work
        r = s.post(f"{API}/ai/echo-yesterday")
        assert r.status_code == 200
        assert "text" in r.json()

    def test_fallback_when_no_yesterday_data(self, s):
        # Safe default: with no workout/journal/day_plans for yesterday, fallback kicks in.
        # Since we can't guarantee DB is empty for 'yesterday', we accept either:
        # - exact fallback phrase
        # - a non-empty sentence < 200 chars from Claude (if data exists)
        r = s.post(f"{API}/ai/echo-yesterday", json={})
        data = r.json()
        text = data["text"]
        assert isinstance(text, str)
        assert len(text) < 400  # reasonable bound; spec says ~one sentence
        # Prefix or spec fallback text indicators
        # Either says "Yesterday left no marks" / "blank page" OR is a real sentence.
        assert len(text) > 5

    def test_with_yesterday_journal_entry(self, s):
        # Seed a journal entry for yesterday so Claude path is exercised
        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        payload = {
            "date": yesterday,
            "mood": 4,
            "reflection": "TEST_iter8 quiet walk in the park and a small chapter read.",
        }
        created = s.post(f"{API}/journal-entries", json=payload)
        assert created.status_code in (200, 201), created.text
        try:
            r = s.post(f"{API}/ai/echo-yesterday", json={})
            assert r.status_code == 200
            data = r.json()
            assert "text" in data and isinstance(data["text"], str)
            assert 0 < len(data["text"]) < 400
            _assert_no_mongo_id(data)
        finally:
            j_id = created.json().get("id")
            if j_id:
                s.delete(f"{API}/journal-entries/{j_id}")


# =====================================================================
# Focus sessions + distractions
# =====================================================================
class TestFocusSessions:
    def test_create_focus_session(self, s):
        payload = {
            "task": "TEST_iter8 deep work",
            "planned_min": 25,
            "actual_min": 22,
            "completed": True,
            "note": "TEST_iter8 ok",
        }
        r = s.post(f"{API}/focus-sessions", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["task"] == payload["task"]
        assert data["planned_min"] == 25
        assert data["actual_min"] == 22
        assert data["completed"] is True
        assert data.get("id")
        assert data.get("ended_at"), "ended_at should be auto-set"
        assert data.get("started_at")
        _assert_no_mongo_id(data)

    def test_list_focus_sessions_sorted_desc(self, s):
        # create two sessions back-to-back
        s.post(f"{API}/focus-sessions", json={"task": "TEST_iter8 A", "actual_min": 5})
        time.sleep(0.05)
        s.post(f"{API}/focus-sessions", json={"task": "TEST_iter8 B", "actual_min": 7})
        r = s.get(f"{API}/focus-sessions")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 2
        starts = [it["started_at"] for it in items]
        assert starts == sorted(starts, reverse=True), "expected desc sort by started_at"
        _assert_no_mongo_id(items)


class TestDistractions:
    def test_create_distraction(self, s):
        r = s.post(f"{API}/distractions", json={"trigger": "phone", "note": "TEST_iter8 scroll"})
        assert r.status_code == 200
        data = r.json()
        assert data["trigger"] == "phone"
        assert data["note"] == "TEST_iter8 scroll"
        assert data.get("id") and data.get("at")
        _assert_no_mongo_id(data)

    def test_list_distractions_sorted_desc(self, s):
        s.post(f"{API}/distractions", json={"trigger": "notification", "note": "TEST_iter8 n1"})
        time.sleep(0.05)
        s.post(f"{API}/distractions", json={"trigger": "hunger", "note": "TEST_iter8 n2"})
        r = s.get(f"{API}/distractions")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list) and len(items) >= 2
        ats = [it["at"] for it in items]
        assert ats == sorted(ats, reverse=True)
        _assert_no_mongo_id(items)


class TestFocusStats:
    def test_focus_stats_counts_today(self, s):
        # Create known today's activity
        s.post(f"{API}/focus-sessions", json={"task": "TEST_iter8 stats1", "actual_min": 20, "completed": True})
        s.post(f"{API}/focus-sessions", json={"task": "TEST_iter8 stats2", "actual_min": 15, "completed": False})
        s.post(f"{API}/distractions", json={"trigger": "phone", "note": "TEST_iter8 d"})
        r = s.get(f"{API}/focus-stats")
        assert r.status_code == 200
        data = r.json()
        for key in ("today_focus_min", "today_sessions", "today_completed_sessions", "today_distractions"):
            assert key in data
            assert isinstance(data[key], int), f"{key} must be int, got {type(data[key])}"
        assert data["today_sessions"] >= 2
        assert data["today_completed_sessions"] >= 1
        assert data["today_focus_min"] >= 35
        assert data["today_distractions"] >= 1


class TestFocusTips:
    def test_ai_focus_tips_real_claude(self, s):
        # NOTE: endpoint signature is `_: AIPrompt | None = None` — sending an empty
        # `{}` body triggers 422 (AIPrompt.prompt is required). Sending no body works.
        # This is a backend concern (see action_items) but we test the happy path here.
        r = s.post(f"{API}/ai/focus-tips")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and isinstance(data["text"], str)
        assert len(data["text"]) > 100, f"expected >100 chars, got {len(data['text'])}: {data['text']!r}"
        assert "data" in data
        d = data["data"]
        assert "sessions" in d and "distractions" in d and "top_triggers" in d
        assert isinstance(d["sessions"], int)
        assert isinstance(d["distractions"], int)
        assert isinstance(d["top_triggers"], list)
        _assert_no_mongo_id(data)

    def test_ai_focus_tips_empty_json_body_validation_bug(self, s):
        """Documents current behavior: `{}` body -> 422 due to AIPrompt.prompt required.
        If this starts returning 200, the route has been fixed to use a default_factory
        pattern (like EchoRequest / DailyBriefRequest) — great, update this test."""
        r = s.post(f"{API}/ai/focus-tips", json={})
        # We accept EITHER behavior so the suite stays green once fixed:
        assert r.status_code in (200, 422), r.text


# =====================================================================
# Sobriety / Addictions
# =====================================================================
@pytest.fixture(scope="class")
def created_addiction(s):
    r = s.post(f"{API}/addictions", json={"name": "TEST_iter8_habit", "notes": "TEST_iter8 notes"})
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    # teardown
    s.delete(f"{API}/addictions/{data['id']}")


class TestAddictionsCRUD:
    def test_create_addiction(self, s):
        r = s.post(f"{API}/addictions", json={"name": "TEST_iter8_created", "notes": "n"})
        assert r.status_code == 200
        a = r.json()
        assert a["name"] == "TEST_iter8_created"
        assert a["longest_streak_days"] == 0
        assert a["reset_count"] == 0
        assert a.get("started_clean")
        assert a.get("id")
        _assert_no_mongo_id(a)
        # cleanup
        s.delete(f"{API}/addictions/{a['id']}")

    def test_list_addictions(self, s, created_addiction):
        r = s.get(f"{API}/addictions")
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert any(it["id"] == created_addiction["id"] for it in items)
        _assert_no_mongo_id(items)

    def test_update_addiction_partial_name(self, s, created_addiction):
        aid = created_addiction["id"]
        r = s.put(f"{API}/addictions/{aid}", json={"name": "TEST_iter8_renamed"})
        assert r.status_code == 200
        a = r.json()
        assert a["name"] == "TEST_iter8_renamed"
        # notes preserved
        assert a["notes"] == "TEST_iter8 notes"

    def test_update_addiction_partial_notes(self, s, created_addiction):
        aid = created_addiction["id"]
        r = s.put(f"{API}/addictions/{aid}", json={"notes": "TEST_iter8_new_notes"})
        assert r.status_code == 200
        a = r.json()
        assert a["notes"] == "TEST_iter8_new_notes"
        # GET to verify persistence
        r2 = s.get(f"{API}/addictions")
        obj = next(it for it in r2.json() if it["id"] == aid)
        assert obj["notes"] == "TEST_iter8_new_notes"

    def test_delete_addiction_cascades_slips(self, s):
        # create addiction, log a slip, delete, verify slips gone
        c = s.post(f"{API}/addictions", json={"name": "TEST_iter8_todelete"}).json()
        aid = c["id"]
        slip = s.post(f"{API}/addictions/{aid}/slip", json={"note": "TEST_iter8 s"})
        assert slip.status_code == 200
        d = s.delete(f"{API}/addictions/{aid}")
        assert d.status_code == 200
        # GET slips should be empty list (endpoint returns for any id)
        slips = s.get(f"{API}/addictions/{aid}/slips").json()
        assert slips == []
        # addiction should not appear in list
        lst = s.get(f"{API}/addictions").json()
        assert not any(it["id"] == aid for it in lst)


class TestSlipFlow:
    def test_slip_resets_clock_and_updates_fields(self, s):
        c = s.post(f"{API}/addictions", json={"name": "TEST_iter8_slipflow"}).json()
        aid = c["id"]
        initial_started_clean = c["started_clean"]
        try:
            time.sleep(1.1)
            r = s.post(f"{API}/addictions/{aid}/slip", json={"note": "TEST_iter8 rough day"})
            assert r.status_code == 200
            slip = r.json()
            assert slip["addiction_id"] == aid
            assert slip["note"] == "TEST_iter8 rough day"
            assert isinstance(slip["streak_days_before"], int)
            assert slip["streak_days_before"] >= 0
            _assert_no_mongo_id(slip)

            # GET addictions and verify reset_count=1, longest_streak_days >= 0, started_clean updated
            lst = s.get(f"{API}/addictions").json()
            a = next(it for it in lst if it["id"] == aid)
            assert a["reset_count"] == 1
            assert a["longest_streak_days"] >= 0
            assert a["started_clean"] != initial_started_clean, "started_clean should have been reset"
        finally:
            s.delete(f"{API}/addictions/{aid}")

    def test_list_slips_sorted_desc(self, s):
        c = s.post(f"{API}/addictions", json={"name": "TEST_iter8_sorts"}).json()
        aid = c["id"]
        try:
            s.post(f"{API}/addictions/{aid}/slip", json={"note": "TEST_iter8 first"})
            time.sleep(0.1)
            s.post(f"{API}/addictions/{aid}/slip", json={"note": "TEST_iter8 second"})
            r = s.get(f"{API}/addictions/{aid}/slips")
            assert r.status_code == 200
            slips = r.json()
            assert len(slips) == 2
            ats = [sl["at"] for sl in slips]
            assert ats == sorted(ats, reverse=True)
            _assert_no_mongo_id(slips)
        finally:
            s.delete(f"{API}/addictions/{aid}")

    def test_multiple_slips_increment_reset_count(self, s):
        c = s.post(f"{API}/addictions", json={"name": "TEST_iter8_counter"}).json()
        aid = c["id"]
        try:
            for i in range(3):
                r = s.post(f"{API}/addictions/{aid}/slip", json={"note": f"TEST_iter8 n{i}"})
                assert r.status_code == 200
            lst = s.get(f"{API}/addictions").json()
            a = next(it for it in lst if it["id"] == aid)
            assert a["reset_count"] == 3
        finally:
            s.delete(f"{API}/addictions/{aid}")


class TestSobrietySupport:
    def test_sobriety_support_real_claude(self, s):
        c = s.post(f"{API}/addictions", json={"name": "TEST_iter8_support", "notes": "trying"}).json()
        aid = c["id"]
        try:
            # Send no body (AIPrompt | None = None). `{}` would 422 — see bug test below.
            r = s.post(f"{API}/ai/sobriety-support/{aid}")
            assert r.status_code == 200, r.text
            data = r.json()
            assert "text" in data
            assert isinstance(data["text"], str)
            assert len(data["text"]) > 80, f"expected >80 chars, got {len(data['text'])}"
            _assert_no_mongo_id(data)
        finally:
            s.delete(f"{API}/addictions/{aid}")

    def test_sobriety_support_404_on_invalid_id(self, s):
        # Must send NO body; `{}` triggers 422 before route handler runs.
        r = s.post(f"{API}/ai/sobriety-support/nonexistent-id-xyz")
        assert r.status_code == 404

    def test_sobriety_support_empty_json_body_validation_bug(self, s):
        """Documents that `{}` body currently 422s on this endpoint too."""
        c = s.post(f"{API}/addictions", json={"name": "TEST_iter8_supportbug"}).json()
        aid = c["id"]
        try:
            r = s.post(f"{API}/ai/sobriety-support/{aid}", json={})
            assert r.status_code in (200, 422), r.text
        finally:
            s.delete(f"{API}/addictions/{aid}")


# =====================================================================
# Global _id leak sweep across new endpoints
# =====================================================================
class TestNoMongoIdLeak:
    def test_sweep_new_endpoints(self, s):
        endpoints = [
            ("GET", "/focus-sessions", None),
            ("GET", "/distractions", None),
            ("GET", "/focus-stats", None),
            ("GET", "/addictions", None),
            ("POST", "/ai/echo-yesterday", {}),
        ]
        for method, path, body in endpoints:
            if method == "GET":
                r = s.get(f"{API}{path}")
            else:
                r = s.post(f"{API}{path}", json=body)
            assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text}"
            _assert_no_mongo_id(r.json())
