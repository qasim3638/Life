"""Backend tests for Companion action envelope (add_time_block, add_event, add_priority) and apply/cancel."""
import os
import re
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _post_chat(session, message, retries=2):
    """Send chat and return (user_msg, reply) or raise."""
    last = None
    for _ in range(retries + 1):
        r = session.post(f"{API}/companion/chat", json={"message": message}, timeout=60)
        assert r.status_code == 200, f"chat failed: {r.status_code} {r.text}"
        data = r.json()
        last = data
        if data.get("reply"):
            return data
        time.sleep(1)
    return last


# Plain chat: actions must be empty, content must be prose (not JSON)
def test_plain_chat_no_actions(session):
    data = _post_chat(session, "Hi, how are you today?")
    reply = data["reply"]
    assert reply["role"] == "assistant"
    assert isinstance(reply.get("actions"), list)
    assert reply["actions"] == [], f"Expected empty actions for plain chat, got: {reply['actions']}"
    content = reply["content"].strip()
    # Content should not look like raw JSON envelope
    assert not (content.startswith("{") and '"actions"' in content), (
        f"Plain-chat reply leaked JSON envelope: {content[:200]}"
    )


# add_time_block: "Add gym at 7am tomorrow"
def test_add_time_block_intent(session):
    data = _post_chat(session, "Add gym at 7am tomorrow")
    reply = data["reply"]
    acts = reply.get("actions") or []
    assert len(acts) >= 1, f"Expected at least 1 action, got: {reply}"
    a = next((x for x in acts if x.get("type") == "add_time_block"), None)
    assert a, f"No add_time_block action: {acts}"
    assert a["status"] == "pending"
    assert "id" in a and a["id"]
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", a["date"])
    assert a["hour"] == "07:00", f"Expected 07:00, got {a['hour']}"
    assert "gym" in a["text"].lower()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    assert a["date"] == tomorrow, f"Expected tomorrow {tomorrow}, got {a['date']}"

    # Verify persisted in /api/companion/messages
    r = session.get(f"{API}/companion/messages", timeout=30)
    assert r.status_code == 200
    msgs = r.json()
    mid = reply["id"]
    stored = next((m for m in msgs if m["id"] == mid), None)
    assert stored, "assistant message not persisted"
    assert any(x.get("id") == a["id"] for x in stored.get("actions") or []), "action not persisted"

    # Apply the action
    aid = a["id"]
    r = session.post(f"{API}/companion/messages/{mid}/actions/{aid}/apply", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["action"]["status"] == "applied"
    assert isinstance(body["action"].get("result"), str) and body["action"]["result"]

    # Verify time_block exists on day-plan
    r = session.get(f"{API}/day-plans/{a['date']}", timeout=30)
    assert r.status_code == 200
    plan = r.json()
    blocks = plan.get("time_blocks") or []
    assert any(b.get("hour") == "07:00" and "gym" in (b.get("text") or "").lower() for b in blocks), (
        f"time_block missing on plan: {blocks}"
    )

    # Idempotent apply → second call returns already:'applied'
    r2 = session.post(f"{API}/companion/messages/{mid}/actions/{aid}/apply", timeout=30)
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2.get("ok") is True
    assert body2.get("already") == "applied", f"Expected already=applied, got: {body2}"


# add_priority intent
def test_add_priority_intent(session):
    data = _post_chat(session, "Add a priority tomorrow: finish the proposal")
    reply = data["reply"]
    acts = reply.get("actions") or []
    a = next((x for x in acts if x.get("type") == "add_priority"), None)
    assert a, f"No add_priority action: {acts}"
    assert a["status"] == "pending"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", a["date"])
    assert "proposal" in a["text"].lower()

    # Apply and verify
    mid, aid = reply["id"], a["id"]
    r = session.post(f"{API}/companion/messages/{mid}/actions/{aid}/apply", timeout=30)
    assert r.status_code == 200, r.text
    assert r.json()["action"]["status"] == "applied"

    plan = session.get(f"{API}/day-plans/{a['date']}", timeout=30).json()
    prios = plan.get("priorities") or []
    assert any("proposal" in (p or "").lower() for p in prios), f"priority not set: {prios}"


# add_event intent
def test_add_event_intent(session):
    data = _post_chat(session, "Remind me about Aisha's birthday on June 12 2026")
    reply = data["reply"]
    acts = reply.get("actions") or []
    a = next((x for x in acts if x.get("type") == "add_event"), None)
    assert a, f"No add_event action: {acts}"
    assert a["status"] == "pending"
    assert a["date"] == "2026-06-12", f"Expected 2026-06-12, got {a.get('date')}"
    assert "aisha" in a["title"].lower()

    mid, aid = reply["id"], a["id"]
    r = session.post(f"{API}/companion/messages/{mid}/actions/{aid}/apply", timeout=30)
    assert r.status_code == 200, r.text
    applied = r.json()["action"]
    assert applied["status"] == "applied"

    # verify in /api/events
    r = session.get(f"{API}/events", timeout=30)
    assert r.status_code == 200
    evs = r.json()
    assert any(e.get("date") == "2026-06-12" and "aisha" in (e.get("title") or "").lower() for e in evs), (
        "event not persisted"
    )


# Cancel flow — ensure no DB effect
def test_cancel_action(session):
    data = _post_chat(session, "Add gym at 6am tomorrow")
    reply = data["reply"]
    acts = reply.get("actions") or []
    a = next((x for x in acts if x.get("type") == "add_time_block" and x.get("hour") == "06:00"), None)
    if not a:
        pytest.skip(f"Claude did not produce expected add_time_block 06:00 action: {acts}")
    mid, aid, date = reply["id"], a["id"], a["date"]

    # Snapshot plan before
    before = session.get(f"{API}/day-plans/{date}", timeout=30).json()
    before_blocks = before.get("time_blocks") or []

    r = session.post(f"{API}/companion/messages/{mid}/actions/{aid}/cancel", timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["action"]["status"] == "cancelled"

    # DB unchanged
    after = session.get(f"{API}/day-plans/{date}", timeout=30).json()
    after_blocks = after.get("time_blocks") or []
    # No new 06:00 gym block should have been added
    assert not any(b.get("hour") == "06:00" and "gym" in (b.get("text") or "").lower()
                   and b not in before_blocks for b in after_blocks), "cancel leaked a write"


# 404s
def test_apply_bad_ids(session):
    r = session.post(f"{API}/companion/messages/nope-mid/actions/nope-aid/apply", timeout=15)
    assert r.status_code == 404

    # valid mid, bad aid: get latest assistant message id
    msgs = session.get(f"{API}/companion/messages", timeout=15).json()
    mid = next((m["id"] for m in reversed(msgs) if m["role"] == "assistant"), None)
    if mid:
        r = session.post(f"{API}/companion/messages/{mid}/actions/does-not-exist/apply", timeout=15)
        assert r.status_code == 404
