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
