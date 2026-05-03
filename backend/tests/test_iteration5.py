"""
Iteration 5 backend tests:
- Audio library (seeded 16 items: 5 wisdom, 5 sleep, 6 meditation)
- Family CRUD: members, memories, holidays
- Family AI helpers: holiday-planner, memory-weave, family-ritual
- DayPlan.morning_routine field (List[ChoreItem])
- Companion memories: PATCH endpoint (pinned + content), TTL cap=200, Jaccard dedupe
- No _id leak across new endpoints
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone, timedelta
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://mindful-40.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module")
def mongo():
    cli = MongoClient(MONGO_URL)
    yield cli[DB_NAME]
    cli.close()


# ---------- Audio library ----------
class TestAudioLibrary:
    def test_audio_has_16_items_no_id_leak(self, s):
        r = s.get(f"{API}/audio")
        assert r.status_code == 200, r.text
        items = r.json()
        assert isinstance(items, list)
        assert len(items) == 16, f"expected 16, got {len(items)}"
        for it in items:
            assert "_id" not in it
            for f in ["id", "title", "youtube_id", "category", "duration"]:
                assert it.get(f), f"missing field {f}: {it}"

    def test_audio_categories_split(self, s):
        items = s.get(f"{API}/audio").json()
        cats = {}
        for it in items:
            cats[it["category"]] = cats.get(it["category"], 0) + 1
        assert cats.get("Wisdom Story") == 5, cats
        assert cats.get("Sleep Story") == 5, cats
        assert cats.get("Meditation Music") == 6, cats

    def test_audio_filter_by_category(self, s):
        r = s.get(f"{API}/audio", params={"category": "Wisdom Story"})
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 5
        for it in items:
            assert it["category"] == "Wisdom Story"


# ---------- Family Members CRUD ----------
class TestFamilyMembers:
    def test_full_crud(self, s):
        payload = {
            "name": "TEST_Aisha",
            "relation": "daughter",
            "birthday": "2015-06-12",
            "photo_url": "https://example.com/a.jpg",
            "notes": "loves art",
        }
        c = s.post(f"{API}/family/members", json=payload)
        assert c.status_code == 200, c.text
        m = c.json()
        assert "_id" not in m
        assert m["id"] and m["name"] == payload["name"]
        mid = m["id"]

        lst = s.get(f"{API}/family/members").json()
        assert any(x["id"] == mid for x in lst)
        for x in lst:
            assert "_id" not in x

        upd = s.put(
            f"{API}/family/members/{mid}",
            json={**payload, "notes": "TEST_updated"},
        )
        assert upd.status_code == 200
        assert upd.json()["notes"] == "TEST_updated"

        d = s.delete(f"{API}/family/members/{mid}")
        assert d.status_code == 200
        lst2 = s.get(f"{API}/family/members").json()
        assert not any(x["id"] == mid for x in lst2)


# ---------- Family Memories ----------
class TestFamilyMemories:
    def test_create_list_delete(self, s):
        payload = {
            "title": "TEST_Beach Trip",
            "date": "2025-08-10",
            "location": "Karachi",
            "story": "Sandcastles and cold drinks.",
            "photo_url": "",
            "member_ids": [],
            "tags": ["summer"],
        }
        c = s.post(f"{API}/family/memories", json=payload)
        assert c.status_code == 200, c.text
        mem = c.json()
        assert "_id" not in mem
        mid = mem["id"]
        assert mem["title"] == payload["title"]

        lst = s.get(f"{API}/family/memories").json()
        assert any(x["id"] == mid for x in lst)

        d = s.delete(f"{API}/family/memories/{mid}")
        assert d.status_code == 200


# ---------- Family Holidays ----------
class TestFamilyHolidays:
    def test_full_crud_with_status_update(self, s):
        payload = {
            "destination": "TEST_Istanbul",
            "start_date": "2026-09-10",
            "end_date": "2026-09-20",
            "status": "planned",
            "budget": "2000 USD",
            "notes": "halal-friendly",
            "todos": [{"text": "book flights", "done": False}],
            "photo_urls": [],
            "member_ids": [],
        }
        c = s.post(f"{API}/family/holidays", json=payload)
        assert c.status_code == 200, c.text
        h = c.json()
        assert "_id" not in h
        hid = h["id"]
        assert h["destination"] == payload["destination"]
        assert len(h["todos"]) == 1

        lst = s.get(f"{API}/family/holidays").json()
        assert any(x["id"] == hid for x in lst)

        upd = s.put(
            f"{API}/family/holidays/{hid}",
            json={**payload, "status": "booked"},
        )
        assert upd.status_code == 200
        assert upd.json()["status"] == "booked"

        d = s.delete(f"{API}/family/holidays/{hid}")
        assert d.status_code == 200


# ---------- Family AI helpers ----------
class TestFamilyAI:
    def test_holiday_planner(self, s):
        r = s.post(
            f"{API}/ai/holiday-planner",
            json={"prompt": "5 days in Istanbul with kids 6 and 8, halal food, light pace"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and len(data["text"]) > 100, f"too short: {data}"
        assert "error" not in data, data.get("error")

    def test_memory_weave(self, s):
        r = s.post(
            f"{API}/ai/memory-weave",
            json={"prompt": "Layla's first ride on her bicycle in the park"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and len(data["text"]) > 50
        assert "error" not in data, data.get("error")

    def test_family_ritual(self, s):
        r = s.post(
            f"{API}/ai/family-ritual",
            json={"prompt": "family of 4, busy weekdays, want more connection"},
            timeout=120,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data and len(data["text"]) > 50
        assert "error" not in data, data.get("error")


# ---------- DayPlan morning_routine ----------
class TestMorningRoutine:
    def test_morning_routine_persists(self, s):
        date = "2032-04-01"
        payload = {
            "date": date,
            "morning_routine": [
                {"text": "wake & water", "done": False},
                {"text": "stretch 5 min", "done": True},
                {"text": "fajr", "done": False},
            ],
        }
        u = s.put(f"{API}/day-plans/{date}", json=payload)
        assert u.status_code == 200, u.text
        saved = u.json()
        assert "_id" not in saved
        assert len(saved.get("morning_routine", [])) == 3
        assert saved["morning_routine"][0] == {"text": "wake & water", "done": False}
        assert saved["morning_routine"][1]["done"] is True

        g = s.get(f"{API}/day-plans/{date}").json()
        assert len(g["morning_routine"]) == 3
        assert g["morning_routine"][2]["text"] == "fajr"

    def test_default_morning_routine_empty(self, s):
        date = "2032-04-02"
        r = s.get(f"{API}/day-plans/{date}").json()
        assert r.get("morning_routine") == []


# ---------- Companion memories: PATCH ----------
class TestCompanionMemoryPatch:
    @pytest.fixture(autouse=True)
    def _reset(self, s):
        # Clean only TEST_-prefixed memories to keep noise low
        mems = s.get(f"{API}/companion/memories").json()
        for m in mems:
            if (m.get("content") or "").startswith("TEST_"):
                s.delete(f"{API}/companion/memories/{m['id']}")
        yield

    def test_patch_pinned_true(self, s):
        m = s.post(
            f"{API}/companion/memories",
            json={"content": "TEST_pinme", "category": "general"},
        ).json()
        assert m.get("pinned") is False, f"new memory should default pinned=False, got: {m}"

        r = s.patch(f"{API}/companion/memories/{m['id']}", json={"pinned": True})
        assert r.status_code == 200, r.text
        updated = r.json()
        assert updated.get("pinned") is True

        # GET reflects
        lst = s.get(f"{API}/companion/memories").json()
        found = next((x for x in lst if x["id"] == m["id"]), None)
        assert found and found["pinned"] is True

    def test_patch_content_update(self, s):
        m = s.post(
            f"{API}/companion/memories",
            json={"content": "TEST_orig"},
        ).json()
        r = s.patch(
            f"{API}/companion/memories/{m['id']}",
            json={"content": "TEST_updated text"},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("content") == "TEST_updated text"

        lst = s.get(f"{API}/companion/memories").json()
        found = next((x for x in lst if x["id"] == m["id"]), None)
        assert found["content"] == "TEST_updated text"


# ---------- Companion memories: TTL cap and pinned-survival ----------
class TestCompanionMemoryTTL:
    AUTO_CAP = 200

    @pytest.fixture(autouse=True)
    def _wipe_auto(self, mongo):
        # Wipe every auto memory (we'll seed our own)
        mongo.companion_memories.delete_many({"category": "auto"})
        yield
        mongo.companion_memories.delete_many({"category": "auto"})

    def _seed_auto(self, mongo, n: int, pinned: bool = False, base_offset_min: int = 1000):
        """Insert n auto memories with old timestamps (older = larger offset)."""
        now = datetime.now(timezone.utc)
        docs = []
        for i in range(n):
            ts = (now - timedelta(minutes=base_offset_min - i)).isoformat()
            docs.append({
                "id": str(uuid.uuid4()),
                "content": f"seed fact number {i} — synthetic content for ttl test",
                "category": "auto",
                "pinned": pinned,
                "created_at": ts,
            })
        if docs:
            mongo.companion_memories.insert_many(docs)
        return docs

    def _wait_for_cap(self, mongo, cap: int, timeout: int = 25) -> int:
        for _ in range(timeout):
            count = mongo.companion_memories.count_documents(
                {"category": "auto", "pinned": {"$ne": True}}
            )
            if count <= cap:
                return count
            time.sleep(1)
        return mongo.companion_memories.count_documents(
            {"category": "auto", "pinned": {"$ne": True}}
        )

    def test_ttl_evicts_oldest_when_over_cap(self, s, mongo):
        # Seed 205 unpinned auto memories with monotonically increasing timestamps
        self._seed_auto(mongo, 205, pinned=False)
        before = mongo.companion_memories.count_documents({"category": "auto"})
        assert before == 205

        # Trigger background prune by sending a long chat message
        msg = "x" * 200  # >80 chars, junk so AI extract usually returns []
        r = s.post(f"{API}/companion/chat", json={"message": msg}, timeout=90)
        assert r.status_code == 200, r.text

        final = self._wait_for_cap(mongo, self.AUTO_CAP)
        assert final <= self.AUTO_CAP, f"TTL did not prune auto memories: {final} > {self.AUTO_CAP}"

    def test_pinned_memory_survives_prune(self, s, mongo):
        # 1 pinned (oldest) + 205 unpinned, all auto
        pinned_docs = self._seed_auto(mongo, 1, pinned=True, base_offset_min=99999)
        pinned_id = pinned_docs[0]["id"]
        self._seed_auto(mongo, 205, pinned=False)

        msg = "y" * 220
        r = s.post(f"{API}/companion/chat", json={"message": msg}, timeout=90)
        assert r.status_code == 200

        final_unpinned = self._wait_for_cap(mongo, self.AUTO_CAP)
        assert final_unpinned <= self.AUTO_CAP

        survived = mongo.companion_memories.find_one({"id": pinned_id})
        assert survived is not None, "pinned auto memory was evicted!"
        assert survived.get("pinned") is True


# ---------- Jaccard dedupe ----------
class TestJaccardDedupe:
    @pytest.fixture(autouse=True)
    def _wipe_auto(self, mongo):
        mongo.companion_memories.delete_many({"category": "auto"})
        yield
        mongo.companion_memories.delete_many({"category": "auto"})

    def test_near_duplicate_message_does_not_create_duplicate(self, s, mongo):
        msg1 = (
            "I have a daughter named Aisha who is seven years old and loves painting watercolors. "
            "She also enjoys reading short stories at bedtime."
        )
        # Slightly reworded variant — should produce overlapping facts
        msg2 = (
            "My daughter Aisha is seven and she really loves painting watercolors. "
            "Bedtime stories are also part of our nightly routine."
        )

        r1 = s.post(f"{API}/companion/chat", json={"message": msg1}, timeout=90)
        assert r1.status_code == 200
        # Wait for first extract to complete
        time.sleep(15)
        autos1 = list(mongo.companion_memories.find({"category": "auto"}, {"_id": 0}))
        if not autos1:
            pytest.skip("AI extracted no facts from the first message — dedupe untestable")
        count1 = len(autos1)

        r2 = s.post(f"{API}/companion/chat", json={"message": msg2}, timeout=90)
        assert r2.status_code == 200
        time.sleep(15)
        autos2 = list(mongo.companion_memories.find({"category": "auto"}, {"_id": 0}))
        count2 = len(autos2)

        # Allow 0 or 1 net new memories — strict dupes should be filtered
        new_count = count2 - count1
        assert new_count <= 1, (
            f"Jaccard dedupe failed: {new_count} new auto memories from near-duplicate. "
            f"All: {[m['content'] for m in autos2]}"
        )
