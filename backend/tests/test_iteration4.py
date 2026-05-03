"""
Iteration 4 specific backend tests:
- Streaks: workout_today/journal_today bool flags
- DayPlan: time_blocks persistence; typed validation for meals/supplements
- Companion: persona Literal validation; background auto-extract memories
- Server modular layout sanity
"""
import os
import time
import pytest
import requests
from datetime import datetime, timezone

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://mindful-40.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- Streaks new bool fields ----------
class TestStreaksFlags:
    def test_streaks_includes_today_bool_flags(self, s):
        r = s.get(f"{API}/streaks")
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ["workout_today", "journal_today"]:
            assert k in data, f"missing {k} in /streaks: {data}"
            assert isinstance(data[k], bool), f"{k} not bool: {type(data[k])}"

    def test_workout_today_flips_true_after_log(self, s):
        today = datetime.now(timezone.utc).date().isoformat()
        # Note: prior log for today may already exist (other tests). Either way, flag must be True.
        w = s.post(
            f"{API}/workouts",
            json={"name": "TEST_TodayFlag", "category": "Cardio", "exercises": []},
        ).json()
        log = s.post(
            f"{API}/workout-logs",
            json={
                "workout_id": w["id"],
                "workout_name": w["name"],
                "date": today,
                "duration_min": 15,
                "notes": "today flag test",
            },
        )
        assert log.status_code == 200
        data = s.get(f"{API}/streaks").json()
        assert data["workout_today"] is True
        s.delete(f"{API}/workouts/{w['id']}")

    def test_journal_today_flips_true_after_entry(self, s):
        today = datetime.now(timezone.utc).date().isoformat()
        j = s.post(
            f"{API}/journal-entries",
            json={"date": today, "mood": 4, "gratitude": ["a"], "reflection": "TEST_today"},
        )
        assert j.status_code == 200
        data = s.get(f"{API}/streaks").json()
        assert data["journal_today"] is True
        # cleanup
        s.delete(f"{API}/journal-entries/{j.json()['id']}")


# ---------- DayPlan time_blocks ----------
class TestDayPlanTimeBlocks:
    def test_time_blocks_persist(self, s):
        date = "2031-02-14"
        payload = {
            "date": date,
            "time_blocks": [
                {"hour": "06:00", "text": "walk"},
                {"hour": "09:00", "text": "deep work"},
                {"hour": "18:00", "text": "gym"},
            ],
        }
        u = s.put(f"{API}/day-plans/{date}", json=payload)
        assert u.status_code == 200, u.text
        saved = u.json()
        assert "_id" not in saved
        assert isinstance(saved.get("time_blocks"), list)
        assert len(saved["time_blocks"]) == 3
        assert saved["time_blocks"][0] == {"hour": "06:00", "text": "walk"}

        g = s.get(f"{API}/day-plans/{date}").json()
        assert len(g["time_blocks"]) == 3
        hours = [b["hour"] for b in g["time_blocks"]]
        assert hours == ["06:00", "09:00", "18:00"]

    def test_default_day_plan_has_empty_time_blocks(self, s):
        date = "2031-09-09"
        r = s.get(f"{API}/day-plans/{date}").json()
        assert r.get("time_blocks") == []


# ---------- DayPlan typed validation ----------
class TestDayPlanValidation:
    def test_meal_string_instead_of_object_rejected(self, s):
        date = "2031-03-01"
        payload = {
            "date": date,
            "meals": {"breakfast": "[BAD]", "lunch": {}, "dinner": {}, "snack": {}},
        }
        r = s.put(f"{API}/day-plans/{date}", json=payload)
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_supplement_taken_non_bool_coerced_or_rejected(self, s):
        date = "2031-03-02"
        payload = {
            "date": date,
            "supplements": [{"name": "X", "taken": "notabool"}],
        }
        r = s.put(f"{API}/day-plans/{date}", json=payload)
        # Pydantic may either coerce "notabool" or reject. Both acceptable per spec.
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            saved = r.json()
            sup = saved["supplements"][0]
            assert isinstance(sup["taken"], bool), f"taken not coerced to bool: {sup}"
            assert sup["name"] == "X"

    def test_supplement_clean_payload_persists(self, s):
        date = "2031-03-03"
        payload = {
            "date": date,
            "supplements": [
                {"name": "Vit D", "taken": True},
                {"name": "Omega-3", "taken": False},
            ],
        }
        r = s.put(f"{API}/day-plans/{date}", json=payload)
        assert r.status_code == 200, r.text
        sups = r.json()["supplements"]
        assert sups[0] == {"name": "Vit D", "taken": True}
        assert sups[1] == {"name": "Omega-3", "taken": False}


# ---------- Companion persona Literal validation ----------
class TestPersonaLiteral:
    def test_bad_persona_rejected(self, s):
        r = s.put(f"{API}/companion", json={"persona": "banana"})
        assert r.status_code == 422, f"expected 422 for invalid persona, got {r.status_code}: {r.text}"

    def test_valid_persona_accepted(self, s):
        for p in ["friend", "secretary", "manager", "coach"]:
            r = s.put(f"{API}/companion", json={"persona": p})
            assert r.status_code == 200, r.text
            assert r.json()["persona"] == p
        # reset
        s.put(f"{API}/companion", json={"persona": "friend"})


# ---------- Companion auto-extract memories ----------
class TestAutoExtractMemories:
    @pytest.fixture(autouse=True)
    def _wipe_auto(self, s):
        # Remove any pre-existing auto memories so we can detect new ones cleanly.
        mems = s.get(f"{API}/companion/memories").json()
        for m in mems:
            if m.get("category") == "auto":
                s.delete(f"{API}/companion/memories/{m['id']}")
        yield

    def _auto_count(self, s):
        mems = s.get(f"{API}/companion/memories").json()
        return [m for m in mems if m.get("category") == "auto"]

    def test_long_personal_message_triggers_auto_extract(self, s):
        msg = (
            "I have two kids Maya and Layla, I work as a software engineer, "
            "I live in Karachi and I love long-distance running on weekends."
        )
        assert len(msg) > 80
        r = s.post(f"{API}/companion/chat", json={"message": msg}, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "reply" in body and len(body["reply"]["content"]) > 10

        # Background task should populate auto memories within ~15s
        autos = []
        for _ in range(15):
            time.sleep(1)
            autos = self._auto_count(s)
            if autos:
                break
        assert autos, "no auto-category memories created from long personal message"
        joined = " ".join(m["content"].lower() for m in autos)
        # Expect at least one memorable token to appear
        hit = any(tok in joined for tok in ["maya", "layla", "engineer", "karachi", "kids", "children", "running"])
        assert hit, f"auto memories don't reflect personal facts: {[m['content'] for m in autos]}"

    def test_short_message_does_not_trigger_auto_extract(self, s):
        msg = "Hi there."  # < 80 chars
        assert len(msg) < 80
        before = len(self._auto_count(s))
        r = s.post(f"{API}/companion/chat", json={"message": msg}, timeout=90)
        assert r.status_code == 200
        # Wait a bit; auto extract should be skipped
        time.sleep(8)
        after = len(self._auto_count(s))
        assert after == before, f"short message created auto memories ({before}->{after})"

    def test_long_unmemorable_message_yields_zero_or_minimal(self, s):
        msg = (
            "What is the weather like today? I am just generally curious about "
            "how the forecast looks for the rest of the week, no specifics needed."
        )
        assert len(msg) > 80
        before = len(self._auto_count(s))
        r = s.post(f"{API}/companion/chat", json={"message": msg}, timeout=90)
        assert r.status_code == 200
        time.sleep(12)
        after = self._auto_count(s)
        # Allow up to 1 spurious extraction; the contract is "zero or minimal"
        new_count = len(after) - before
        assert new_count <= 1, f"unmemorable message produced {new_count} auto memories: {[m['content'] for m in after]}"

    def test_chat_does_not_fail_on_background_extract(self, s):
        # Even with a long message, primary chat response must always be 200.
        msg = "x" * 200  # forces background task to fire; junk may yield no facts
        r = s.post(f"{API}/companion/chat", json={"message": msg}, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reply"]["content"], "reply must be non-empty even when extract may fail"


# ---------- Modular layout sanity ----------
class TestModularLayout:
    def test_server_under_100_lines(self):
        path = "/app/backend/server.py"
        with open(path) as fh:
            lines = fh.readlines()
        assert len(lines) < 100, f"server.py is {len(lines)} lines (must be <100)"

    def test_routes_folder_has_endpoints(self):
        import os
        files = os.listdir("/app/backend/routes")
        # Expect at least these route modules
        for needed in [
            "companion.py", "day_plans.py", "streaks.py", "workouts.py",
            "recipes.py", "journal.py", "events.py", "life_goals.py",
            "content.py", "ai_endpoints.py",
        ]:
            assert needed in files, f"missing route module {needed}"

    def test_no_id_leak_on_core_endpoints(self, s):
        for ep in [
            "/recipes", "/quotes", "/podcasts", "/meditations", "/affirmations",
            "/workouts", "/workout-logs", "/journal-entries", "/events",
            "/life-goals", "/companion/memories", "/companion/messages",
            "/day-plans",
        ]:
            r = s.get(f"{API}{ep}")
            assert r.status_code == 200, f"{ep} -> {r.status_code}"
            data = r.json()
            if isinstance(data, list):
                for item in data[:5]:
                    assert "_id" not in item, f"{ep} leaks _id: {item}"
        # Singletons
        for ep in ["/companion", "/streaks"]:
            r = s.get(f"{API}{ep}")
            assert r.status_code == 200
            assert "_id" not in r.json()
