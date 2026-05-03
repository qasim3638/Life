"""
Life Blueprint backend API tests.
Covers: health, seeded content (recipes/quotes/podcasts/meditations/affirmations),
CRUD (workouts, workout-logs, recipes, journal, events, life-goals),
and AI endpoints (motivation/reflect/meal/workout via Claude Sonnet 4.5).
"""

import os
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://mindful-40.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

PORK_TERMS = ["pork", "bacon", "ham ", "prosciutto", "pancetta", "lardon"]


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


# ---------- health ----------
class TestHealth:
    def test_root(self, s):
        r = s.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"
        assert "Life Blueprint" in data.get("message", "")


# ---------- seeded content ----------
class TestSeed:
    def test_recipes_seeded_and_halal(self, s):
        r = s.get(f"{API}/recipes")
        assert r.status_code == 200
        recipes = r.json()
        assert len(recipes) >= 12, f"expected >=12 recipes, got {len(recipes)}"
        cuisines = {x["cuisine"] for x in recipes}
        for expected in ["Pakistani", "Indian", "Arab", "Mediterranean"]:
            assert expected in cuisines, f"missing cuisine {expected}"
        for rec in recipes:
            assert "_id" not in rec
            for field in ["calories", "protein", "carbs", "fat"]:
                assert field in rec and isinstance(rec[field], int)
            text = (
                rec["title"].lower()
                + " "
                + " ".join(rec.get("ingredients", [])).lower()
                + " "
                + " ".join(rec.get("instructions", [])).lower()
                + " "
                + " ".join(rec.get("tags", [])).lower()
            )
            for bad in PORK_TERMS:
                assert bad not in text, f"pork/bacon found in recipe '{rec['title']}': {bad}"

    def test_recipes_filter_cuisine(self, s):
        r = s.get(f"{API}/recipes", params={"cuisine": "Pakistani"})
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for it in items:
            assert it["cuisine"] == "Pakistani"

    def test_recipes_filter_meal_type(self, s):
        r = s.get(f"{API}/recipes", params={"meal_type": "Breakfast"})
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 1
        for it in items:
            assert it["meal_type"] == "Breakfast"

    def test_quotes_seeded(self, s):
        r = s.get(f"{API}/quotes")
        assert r.status_code == 200
        q = r.json()
        assert len(q) >= 15
        for item in q:
            assert "_id" not in item
            assert item.get("text") and item.get("author") and item.get("category")

    def test_podcasts_seeded(self, s):
        r = s.get(f"{API}/podcasts")
        assert r.status_code == 200
        p = r.json()
        assert len(p) >= 8
        for item in p:
            assert "_id" not in item
            assert item.get("youtube_id")

    def test_meditations_seeded(self, s):
        r = s.get(f"{API}/meditations")
        assert r.status_code == 200
        m = r.json()
        assert len(m) >= 6
        for item in m:
            assert "_id" not in item
            assert item.get("youtube_id")

    def test_affirmations_seeded(self, s):
        r = s.get(f"{API}/affirmations")
        assert r.status_code == 200
        a = r.json()
        assert len(a) >= 8
        for item in a:
            assert "_id" not in item
            assert item.get("text")


# ---------- workouts CRUD ----------
class TestWorkouts:
    def test_full_crud(self, s):
        payload = {
            "name": "TEST_Strength A",
            "category": "Strength",
            "notes": "upper body",
            "exercises": [
                {"name": "Bench", "sets": 3, "reps": 8, "rest": 90, "weight": 60},
                {"name": "Row", "sets": 3, "reps": 10, "rest": 75, "weight": 50},
                {"name": "OHP", "sets": 3, "reps": 8, "rest": 90, "weight": 35},
            ],
        }
        c = s.post(f"{API}/workouts", json=payload)
        assert c.status_code == 200, c.text
        w = c.json()
        wid = w["id"]
        assert "_id" not in w
        assert w["name"] == payload["name"]
        assert len(w["exercises"]) == 3

        lst = s.get(f"{API}/workouts")
        assert lst.status_code == 200
        assert any(x["id"] == wid for x in lst.json())

        upd = s.put(
            f"{API}/workouts/{wid}",
            json={**payload, "notes": "updated", "name": "TEST_Strength A2"},
        )
        assert upd.status_code == 200
        assert upd.json()["notes"] == "updated"
        assert upd.json()["name"] == "TEST_Strength A2"

        g = s.get(f"{API}/workouts/{wid}")
        assert g.status_code == 200
        assert g.json()["notes"] == "updated"

        d = s.delete(f"{API}/workouts/{wid}")
        assert d.status_code == 200
        gone = s.get(f"{API}/workouts/{wid}")
        assert gone.status_code == 404

    def test_workout_logs(self, s):
        # create workout first
        w = s.post(
            f"{API}/workouts",
            json={"name": "TEST_LogW", "category": "Cardio", "exercises": []},
        ).json()
        log = s.post(
            f"{API}/workout-logs",
            json={
                "workout_id": w["id"],
                "workout_name": w["name"],
                "date": "2026-01-15",
                "duration_min": 30,
                "notes": "felt good",
            },
        )
        assert log.status_code == 200
        lj = log.json()
        assert "_id" not in lj
        assert lj["workout_id"] == w["id"]

        lst = s.get(f"{API}/workout-logs")
        assert lst.status_code == 200
        assert any(x["id"] == lj["id"] for x in lst.json())

        s.delete(f"{API}/workouts/{w['id']}")


# ---------- recipes custom ----------
class TestRecipeCustom:
    def test_create_and_delete(self, s):
        payload = {
            "title": "TEST_Custom Halal Bowl",
            "cuisine": "Pakistani",
            "meal_type": "Lunch",
            "prep_time": 10,
            "servings": 1,
            "calories": 350,
            "protein": 30,
            "carbs": 10,
            "fat": 15,
            "ingredients": ["chicken", "yogurt"],
            "instructions": ["mix", "cook"],
            "tags": ["high-protein"],
        }
        c = s.post(f"{API}/recipes", json=payload)
        assert c.status_code == 200
        rec = c.json()
        assert rec["is_custom"] is True
        assert "_id" not in rec
        rid = rec["id"]

        got = s.get(f"{API}/recipes/{rid}")
        assert got.status_code == 200
        assert got.json()["title"] == payload["title"]

        d = s.delete(f"{API}/recipes/{rid}")
        assert d.status_code == 200
        gone = s.get(f"{API}/recipes/{rid}")
        assert gone.status_code == 404


# ---------- journal ----------
class TestJournal:
    def test_crud(self, s):
        c = s.post(
            f"{API}/journal-entries",
            json={
                "date": "2026-01-15",
                "mood": 4,
                "gratitude": ["family", "health", "morning light"],
                "reflection": "TEST_ grateful day",
            },
        )
        assert c.status_code == 200
        j = c.json()
        assert "_id" not in j
        assert j["mood"] == 4 and len(j["gratitude"]) == 3

        lst = s.get(f"{API}/journal-entries")
        assert lst.status_code == 200
        assert any(x["id"] == j["id"] for x in lst.json())

        d = s.delete(f"{API}/journal-entries/{j['id']}")
        assert d.status_code == 200


# ---------- events ----------
class TestEvents:
    def test_crud(self, s):
        c = s.post(
            f"{API}/events",
            json={
                "title": "TEST_Birthday",
                "date": "2026-05-10",
                "type": "birthday",
                "recurring": True,
                "notes": "family",
            },
        )
        assert c.status_code == 200
        e = c.json()
        assert "_id" not in e
        assert e["type"] == "birthday"

        lst = s.get(f"{API}/events")
        assert lst.status_code == 200
        assert any(x["id"] == e["id"] for x in lst.json())

        u = s.put(
            f"{API}/events/{e['id']}",
            json={
                "title": "TEST_Birthday Updated",
                "date": "2026-05-11",
                "type": "birthday",
                "recurring": True,
                "notes": "family",
            },
        )
        assert u.status_code == 200
        assert u.json()["title"] == "TEST_Birthday Updated"

        d = s.delete(f"{API}/events/{e['id']}")
        assert d.status_code == 200


# ---------- life goals ----------
class TestLifeGoals:
    def test_crud(self, s):
        c = s.post(
            f"{API}/life-goals",
            json={
                "year": 2036,
                "age": 50,
                "category": "Health",
                "title": "TEST_Run a half marathon",
                "description": "prepare over 12 months",
                "status": "planned",
            },
        )
        assert c.status_code == 200
        g = c.json()
        assert "_id" not in g and g["age"] == 50

        lst = s.get(f"{API}/life-goals")
        assert lst.status_code == 200
        assert any(x["id"] == g["id"] for x in lst.json())

        u = s.put(
            f"{API}/life-goals/{g['id']}",
            json={
                "year": 2036,
                "age": 50,
                "category": "Health",
                "title": "TEST_Run a half marathon",
                "description": "prepare over 12 months",
                "status": "in_progress",
            },
        )
        assert u.status_code == 200
        assert u.json()["status"] == "in_progress"

        d = s.delete(f"{API}/life-goals/{g['id']}")
        assert d.status_code == 200


# ---------- AI (Claude Sonnet 4.5) ----------
class TestAI:
    def _check(self, r):
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and isinstance(data["text"], str) and len(data["text"]) > 10
        # endpoint should not surface an 'error' key on success
        return data

    def test_motivation(self, s):
        r = s.post(f"{API}/ai/motivation", json={"prompt": "", "context": "Monday start"}, timeout=90)
        data = self._check(r)
        assert "error" not in data, f"AI motivation returned fallback: {data.get('error')}"

    def test_reflect(self, s):
        r = s.post(
            f"{API}/ai/reflect",
            json={"prompt": "I've been feeling scattered and tired lately."},
            timeout=90,
        )
        data = self._check(r)
        assert "error" not in data, f"AI reflect returned fallback: {data.get('error')}"

    def test_meal_suggestion(self, s):
        r = s.post(
            f"{API}/ai/meal-suggestion",
            json={"prompt": "quick high-protein dinner, Pakistani flavors"},
            timeout=90,
        )
        data = self._check(r)
        assert "error" not in data, f"AI meal returned fallback: {data.get('error')}"
        low = data["text"].lower()
        for bad in PORK_TERMS:
            assert bad not in low, f"AI meal contained disallowed term: {bad}"

    def test_workout_suggestion(self, s):
        r = s.post(
            f"{API}/ai/workout-suggestion",
            json={"prompt": "mobility + strength, 35 min"},
            timeout=90,
        )
        data = self._check(r)
        assert "error" not in data, f"AI workout returned fallback: {data.get('error')}"


# ---------- streaks ----------
class TestStreaks:
    def test_streaks_shape_and_types(self, s):
        r = s.get(f"{API}/streaks")
        assert r.status_code == 200, r.text
        data = r.json()
        for key in ["workout_streak", "workout_total_days", "journal_streak", "journal_total_days"]:
            assert key in data, f"missing key {key}"
            assert isinstance(data[key], int), f"{key} not int: {type(data[key])}"
            assert data[key] >= 0

    def test_streaks_increment_with_today_log(self, s):
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).date().isoformat()
        # seed workout + log for today
        w = s.post(
            f"{API}/workouts",
            json={"name": "TEST_StreakW", "category": "Cardio", "exercises": []},
        ).json()
        log = s.post(
            f"{API}/workout-logs",
            json={
                "workout_id": w["id"],
                "workout_name": w["name"],
                "date": today,
                "duration_min": 20,
                "notes": "streak test",
            },
        )
        assert log.status_code == 200
        r = s.get(f"{API}/streaks")
        assert r.status_code == 200
        data = r.json()
        assert data["workout_streak"] >= 1, f"expected >=1 workout streak, got {data}"
        # cleanup workout (log remains for idempotency check but streak still ok)
        s.delete(f"{API}/workouts/{w['id']}")


# ---------- AI weekly letter ----------
class TestWeeklyLetter:
    def test_weekly_letter_empty_body(self, s):
        r = s.post(f"{API}/ai/weekly-letter", json={}, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and isinstance(data["text"], str)
        assert len(data["text"]) > 100, f"letter too short: {len(data['text'])} chars"
        assert "error" not in data, f"weekly-letter fallback: {data.get('error')}"
        assert "data" in data
        assert isinstance(data["data"].get("workouts"), int)
        assert isinstance(data["data"].get("journal_entries"), int)

    def test_weekly_letter_with_note(self, s):
        r = s.post(
            f"{API}/ai/weekly-letter",
            json={"note": "focus on rest this week"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and len(data["text"]) > 100
        assert "error" not in data, f"weekly-letter fallback: {data.get('error')}"

    def test_weekly_letter_no_body(self, s):
        # No JSON body at all — should still work due to default WeeklyLetterRequest()
        r = s.post(f"{API}/ai/weekly-letter", timeout=120)
        # Accept 200 (default) or 422 if FastAPI requires body
        assert r.status_code in (200, 422), r.text
        if r.status_code == 200:
            assert len(r.json().get("text", "")) > 50


# ---------- day plans (iteration 3) ----------
class TestDayPlans:
    def test_get_default_when_missing(self, s):
        date = "2030-12-31"  # unique future date
        r = s.get(f"{API}/day-plans/{date}")
        assert r.status_code == 200, r.text
        plan = r.json()
        assert "_id" not in plan
        assert plan["date"] == date
        assert plan["priorities"] == ["", "", ""]
        assert plan["gym_planned"] is False
        assert plan["hydration_oz"] == 80
        assert plan["sleep_target"] == "23:00"
        assert plan["wake_target"] == "06:30"
        assert "breakfast" in plan["meals"] and "lunch" in plan["meals"]
        assert plan["meals"]["breakfast"] == {"text": "", "recipe_id": ""}

    def test_upsert_and_persist(self, s):
        date = "2030-11-15"
        payload = {
            "date": date,
            "priorities": ["Deep work block", "Gym at 6pm", "Call mum"],
            "gym_planned": True,
            "gym_workout_id": "w-123",
            "gym_workout_name": "TEST_Strength A",
            "meals": {
                "breakfast": {"text": "Oats and eggs", "recipe_id": ""},
                "lunch": {"text": "Chicken salad", "recipe_id": "r-1"},
                "dinner": {"text": "Daal + roti", "recipe_id": ""},
                "snack": {"text": "Almonds", "recipe_id": ""},
            },
            "supplements": [{"name": "Vit D", "taken": False}, {"name": "Omega-3", "taken": True}],
            "house_chores": [{"text": "Laundry", "done": False}],
            "work_chores": [{"text": "Ship PR", "done": True}],
            "sleep_target": "22:30",
            "wake_target": "06:00",
            "hydration_oz": 96,
            "notes": "TEST_ focus day",
        }
        u = s.put(f"{API}/day-plans/{date}", json=payload)
        assert u.status_code == 200, u.text
        saved = u.json()
        assert "_id" not in saved
        assert saved["date"] == date
        assert saved["priorities"] == payload["priorities"]
        assert saved["gym_planned"] is True
        assert saved["hydration_oz"] == 96
        assert "updated_at" in saved

        # GET should return persisted plan
        g = s.get(f"{API}/day-plans/{date}")
        assert g.status_code == 200
        gp = g.json()
        assert gp["priorities"] == payload["priorities"]
        assert gp["meals"]["lunch"]["text"] == "Chicken salad"
        assert gp["sleep_target"] == "22:30"
        assert gp["notes"] == "TEST_ focus day"

        # Upsert again with changes
        payload2 = {**payload, "hydration_oz": 64, "notes": "TEST_ updated"}
        u2 = s.put(f"{API}/day-plans/{date}", json=payload2)
        assert u2.status_code == 200
        assert u2.json()["hydration_oz"] == 64

        g2 = s.get(f"{API}/day-plans/{date}")
        assert g2.json()["hydration_oz"] == 64
        assert g2.json()["notes"] == "TEST_ updated"

    def test_list_sorted_desc(self, s):
        # ensure at least two plans exist
        for d in ["2030-10-01", "2030-10-05"]:
            s.put(f"{API}/day-plans/{d}", json={"date": d, "notes": f"TEST_{d}"})
        r = s.get(f"{API}/day-plans")
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        for it in items:
            assert "_id" not in it
        dates = [it["date"] for it in items]
        assert dates == sorted(dates, reverse=True), f"dates not desc: {dates[:5]}"


# ---------- companion (iteration 3) ----------
class TestCompanion:
    @pytest.fixture(autouse=True)
    def _reset(self, s):
        # Clean messages + memories before each test, reset companion to defaults
        s.delete(f"{API}/companion/messages")
        mems = s.get(f"{API}/companion/memories").json()
        for m in mems:
            s.delete(f"{API}/companion/memories/{m['id']}")
        s.put(f"{API}/companion", json={"name": "Najm", "user_name": "friend", "persona": "friend"})
        yield

    def test_get_creates_default(self, s):
        r = s.get(f"{API}/companion")
        assert r.status_code == 200, r.text
        c = r.json()
        assert "_id" not in c
        assert c.get("id") == "default"
        assert c["name"] == "Najm"
        assert c["user_name"] == "friend"
        assert c["persona"] == "friend"

    def test_partial_update_preserves_fields(self, s):
        u = s.put(f"{API}/companion", json={"name": "Layla"})
        assert u.status_code == 200
        c = u.json()
        assert c["name"] == "Layla"
        assert c["user_name"] == "friend"  # unchanged
        assert c["persona"] == "friend"

        u2 = s.put(f"{API}/companion", json={"persona": "manager"})
        c2 = u2.json()
        assert c2["name"] == "Layla"  # preserved
        assert c2["persona"] == "manager"
        assert c2["user_name"] == "friend"

    def test_memories_crud_and_sort(self, s):
        m1 = s.post(f"{API}/companion/memories", json={"content": "I am vegetarian", "category": "health"}).json()
        m2 = s.post(f"{API}/companion/memories", json={"content": "Daughter is Aisha", "category": "family"}).json()
        assert "id" in m1 and m1["category"] == "health"
        assert "_id" not in m1

        lst = s.get(f"{API}/companion/memories").json()
        ids = [m["id"] for m in lst]
        assert m1["id"] in ids and m2["id"] in ids
        for m in lst:
            assert "_id" not in m
        # desc by created_at — m2 (later) should be first
        assert lst[0]["id"] == m2["id"], f"expected m2 first, got {lst[0]}"

        d = s.delete(f"{API}/companion/memories/{m1['id']}")
        assert d.status_code == 200
        lst2 = s.get(f"{API}/companion/memories").json()
        assert m1["id"] not in [m["id"] for m in lst2]

    def test_messages_list_and_clear(self, s):
        # send a quick chat to populate
        r = s.post(f"{API}/companion/chat", json={"message": "Hello"}, timeout=90)
        assert r.status_code == 200, r.text
        msgs = s.get(f"{API}/companion/messages").json()
        assert len(msgs) >= 2
        for m in msgs:
            assert "_id" not in m
        # Chronological asc
        ts = [m["created_at"] for m in msgs]
        assert ts == sorted(ts), "messages not chronological asc"

        # add a memory, clear messages, ensure memory survives
        mem = s.post(f"{API}/companion/memories", json={"content": "TEST keep me"}).json()
        s.delete(f"{API}/companion/messages")
        assert s.get(f"{API}/companion/messages").json() == []
        kept = s.get(f"{API}/companion/memories").json()
        assert any(m["id"] == mem["id"] for m in kept), "memory was wiped along with messages!"

    def test_chat_persists_and_real_reply(self, s):
        r = s.post(f"{API}/companion/chat", json={"message": "What should I focus on this morning?"}, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "user_message" in body and "reply" in body
        um = body["user_message"]
        rep = body["reply"]
        assert um["role"] == "user" and um["content"] == "What should I focus on this morning?"
        assert rep["role"] == "assistant"
        assert "_id" not in um and "_id" not in rep
        assert isinstance(rep["content"], str)
        # Real Claude response, not fallback ("I'm here. Let's try that again in a moment.")
        assert len(rep["content"]) > 50, f"reply too short, likely fallback: {rep['content']!r}"
        assert rep["content"].strip() != "I'm here. Let's try that again in a moment."

        # Persisted in messages
        msgs = s.get(f"{API}/companion/messages").json()
        ids = [m["id"] for m in msgs]
        assert um["id"] in ids and rep["id"] in ids

    def test_chat_respects_user_name(self, s):
        s.put(f"{API}/companion", json={"user_name": "Captain"})
        r = s.post(
            f"{API}/companion/chat",
            json={"message": "Address me by my name in your reply please."},
            timeout=90,
        )
        assert r.status_code == 200
        reply = r.json()["reply"]["content"]
        assert "captain" in reply.lower(), f"reply did not address user as Captain: {reply!r}"

    def test_chat_persona_persisted_on_message(self, s):
        s.put(f"{API}/companion", json={"persona": "manager"})
        r = s.post(f"{API}/companion/chat", json={"message": "Quick check-in."}, timeout=90)
        assert r.status_code == 200
        body = r.json()
        assert body["user_message"]["persona"] == "manager"
        assert body["reply"]["persona"] == "manager"
        assert len(body["reply"]["content"]) > 30

    def test_memory_injection_vegetarian(self, s):
        s.post(
            f"{API}/companion/memories",
            json={"content": "I am strictly vegetarian — I never eat meat, chicken, fish, or seafood.", "category": "health"},
        )
        r = s.post(
            f"{API}/companion/chat",
            json={"message": "Suggest one specific dinner idea for tonight."},
            timeout=90,
        )
        assert r.status_code == 200
        reply = r.json()["reply"]["content"].lower()
        meat_terms = ["chicken", "beef", "lamb", "mutton", "fish", "salmon", "tuna", "shrimp", "prawn", "steak", "turkey"]
        hits = [t for t in meat_terms if t in reply]
        # Allow if memory is referenced (e.g. "since you're vegetarian")
        references_memory = "vegetarian" in reply or "no meat" in reply or "plant" in reply
        assert not hits or references_memory, (
            f"Reply suggested meat ({hits}) without acknowledging vegetarian memory: {reply!r}"
        )
