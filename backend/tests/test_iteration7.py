"""
Iteration 7 tests — Self profile module + AI self-suggestion + AI daily brief.

Covers:
- GET  /api/self-profile  (singleton auto-creation)
- PUT  /api/self-profile  (partial + multi-field update, updated_at bumps)
- POST /api/ai/self-suggestion/{dimension}  (Claude path + placeholder path + invalid dim + note context)
- POST /api/ai/daily-brief  (5-label format, personalisation, no _id leak)
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing from env"
API = f"{BASE_URL}/api"

DIMENSIONS = ("appearance", "personality", "mind", "style", "gear")
BRIEF_LABELS = ("GROOMING", "STYLE", "FOCUS", "CONNECT", "GEAR")


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="module", autouse=True)
def _clean_profile(s):
    """Reset singleton to empty at the start so singleton-creation test is deterministic.
    We do this via a PUT that clears all fields, but GET is the one that auto-creates,
    so we just clear fields if a profile already exists."""
    # Best-effort: clear all fields
    s.put(f"{API}/self-profile", json={k: "" for k in DIMENSIONS})
    yield


# ---------- self-profile CRUD ----------
class TestSelfProfile:
    def test_get_creates_singleton(self, s):
        r = s.get(f"{API}/self-profile")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("id") == "default"
        for k in DIMENSIONS:
            assert k in data, f"missing field {k}"
            assert data[k] == "", f"{k} should be empty string, got {data[k]!r}"
        assert "updated_at" in data and data["updated_at"]
        # no _id leak
        assert "_id" not in data

    def test_put_partial_preserves_other_fields(self, s):
        # seed one field via PUT
        r1 = s.put(f"{API}/self-profile", json={"appearance": "tall, beard"})
        assert r1.status_code == 200, r1.text
        d1 = r1.json()
        assert d1["appearance"] == "tall, beard"
        # Other fields should still be empty strings
        for k in ("personality", "mind", "style", "gear"):
            assert d1.get(k) == "", f"{k} should be preserved empty, got {d1.get(k)!r}"
        assert "_id" not in d1

    def test_put_multi_field_and_updated_at_changes(self, s):
        # capture previous updated_at
        prev = s.get(f"{API}/self-profile").json()["updated_at"]
        time.sleep(1.1)  # ensure clock advances at second granularity
        payload = {
            "appearance": "tall, beard, salt-and-pepper",
            "personality": "introverted, thoughtful, loyal",
            "mind": "history books, systems thinking",
            "style": "minimal neutrals, linen, leather",
            "gear": "mechanical keyboard, good headphones",
        }
        r = s.put(f"{API}/self-profile", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        for k, v in payload.items():
            assert data[k] == v
        assert data["updated_at"] != prev
        assert "_id" not in data

    def test_get_returns_persisted_values(self, s):
        r = s.get(f"{API}/self-profile")
        assert r.status_code == 200
        data = r.json()
        assert data["style"] == "minimal neutrals, linen, leather"
        assert data["gear"] == "mechanical keyboard, good headphones"
        assert "_id" not in data


# ---------- AI self suggestion ----------
class TestAISelfSuggestion:
    def test_invalid_dimension(self, s):
        r = s.post(f"{API}/ai/self-suggestion/nonsense", json={})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("error") == "invalid_dimension"
        assert "text" in data

    def test_style_with_populated_profile_real_ai(self, s):
        # profile.style was set in TestSelfProfile.test_put_multi_field_and_updated_at_changes
        r = s.post(f"{API}/ai/self-suggestion/style", json={})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data
        text = data["text"]
        assert isinstance(text, str)
        # AI output should be meaningful (>100 chars), not the placeholder
        assert len(text) > 100, f"Expected >100 chars AI output, got {len(text)}: {text!r}"
        assert "Tell me a bit about yourself" not in text

    def test_dimension_with_empty_returns_placeholder(self, s):
        # clear a single field
        s.put(f"{API}/self-profile", json={"mind": ""})
        r = s.post(f"{API}/ai/self-suggestion/mind", json={})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data
        # No Claude call; gentle placeholder
        assert "Tell me" in data["text"] or "tell me" in data["text"].lower()
        # ensure no error (no AI call)
        assert "error" not in data or not data.get("error")

    def test_with_note_context_real_ai(self, s):
        r = s.post(
            f"{API}/ai/self-suggestion/appearance",
            json={"note": "I'm going to a wedding next weekend in Istanbul."},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data
        # real AI output — not placeholder
        assert len(data["text"]) > 80, data
        assert "Tell me a bit about yourself" not in data["text"]


# ---------- AI daily brief ----------
class TestDailyBrief:
    def test_daily_brief_has_all_five_labels(self, s):
        r = s.post(f"{API}/ai/daily-brief", json={})
        assert r.status_code == 200, r.text
        data = r.json()
        assert "text" in data
        text = data["text"]
        assert isinstance(text, str)
        for label in BRIEF_LABELS:
            assert label in text, f"Missing label {label} in brief: {text!r}"
        assert "_id" not in data

    def test_daily_brief_no_body(self, s):
        # Content-Type json but no body at all — FastAPI should still accept with default model
        r = s.post(f"{API}/ai/daily-brief")
        assert r.status_code in (200, 422), r.text
        # If 200, verify format. If 422, acceptable given strict parsing; but endpoint
        # declared default value so we expect 200.
        if r.status_code == 200:
            text = r.json().get("text", "")
            for label in BRIEF_LABELS:
                assert label in text, f"missing {label}"

    def test_daily_brief_personalisation_with_companion(self, s):
        # Set companion name + user_name; set profile fields; ensure AI references content.
        s.put(
            f"{API}/companion",
            json={"name": "Najm", "user_name": "Ahsan", "tone": "warm"},
        )
        s.put(
            f"{API}/self-profile",
            json={
                "appearance": "tall, beard, salt-and-pepper",
                "style": "minimal neutrals, linen, leather",
                "mind": "stoicism, systems thinking",
                "personality": "introverted, loyal",
                "gear": "mechanical keyboard, good headphones",
            },
        )
        # Add a memory
        s.post(
            f"{API}/companion/memories",
            json={"content": "Ahsan prefers morning workouts at 6am."},
        )

        r = s.post(f"{API}/ai/daily-brief", json={})
        assert r.status_code == 200, r.text
        text = r.json().get("text", "")
        for label in BRIEF_LABELS:
            assert label in text, f"Missing {label} in: {text!r}"
        # brief should be non-trivial
        assert len(text) > 120, f"Brief too short: {text!r}"
        assert "_id" not in r.json()

    def test_daily_brief_fallback_when_no_profile_still_has_labels(self, s):
        # Clear profile — brief should still return all 5 labels (AI prompt instructs gentle placeholders)
        s.put(f"{API}/self-profile", json={k: "" for k in DIMENSIONS})
        r = s.post(f"{API}/ai/daily-brief", json={})
        assert r.status_code == 200, r.text
        text = r.json().get("text", "")
        for label in BRIEF_LABELS:
            assert label in text, f"missing {label} with empty profile: {text!r}"
