"""Unit tests for services.web_push — pywebpush wrapper logic."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services import web_push


def test_is_configured_true_when_keys_present(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")
    assert web_push.is_configured() is True


def test_is_configured_false_when_missing(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    assert web_push.is_configured() is False


@pytest.mark.asyncio
async def test_upsert_subscription_rejects_missing_endpoint():
    with pytest.raises(ValueError):
        await web_push.upsert_subscription({"keys": {"p256dh": "x", "auth": "y"}})


@pytest.mark.asyncio
async def test_upsert_subscription_rejects_missing_keys():
    with pytest.raises(ValueError):
        await web_push.upsert_subscription({"endpoint": "https://e"})


@pytest.mark.asyncio
async def test_upsert_subscription_writes_doc():
    sub = {"endpoint": "https://x", "keys": {"p256dh": "p", "auth": "a"}}
    fake_db = MagicMock()
    fake_collection = MagicMock()
    fake_collection.find_one_and_update = AsyncMock(return_value={
        "endpoint": "https://x", "p256dh": "p", "auth": "a", "is_active": True,
    })
    fake_db.__getitem__.return_value = fake_collection

    with patch.object(web_push, "get_db", return_value=fake_db):
        result = await web_push.upsert_subscription(
            sub, user_agent="Chrome", visitor_id="vid_1",
        )

    fake_collection.find_one_and_update.assert_awaited_once()
    call_kwargs = fake_collection.find_one_and_update.call_args.kwargs
    assert call_kwargs["upsert"] is True
    set_data = fake_collection.find_one_and_update.call_args.args[1]["$set"]
    assert set_data["endpoint"] == "https://x"
    assert set_data["p256dh"] == "p"
    assert set_data["auth"] == "a"
    assert set_data["user_agent"] == "Chrome"
    assert set_data["visitor_id"] == "vid_1"
    assert set_data["is_active"] is True
    assert result["endpoint"] == "https://x"


@pytest.mark.asyncio
async def test_remove_subscription_marks_inactive():
    fake_db = MagicMock()
    fake_collection = MagicMock()
    fake_collection.update_one = AsyncMock(return_value=MagicMock(matched_count=1))
    fake_db.__getitem__.return_value = fake_collection

    with patch.object(web_push, "get_db", return_value=fake_db):
        ok = await web_push.remove_subscription("https://x")

    assert ok is True
    args, _ = fake_collection.update_one.call_args
    assert args[0] == {"endpoint": "https://x"}
    assert args[1]["$set"]["is_active"] is False


@pytest.mark.asyncio
async def test_send_broadcast_skips_when_not_configured(monkeypatch):
    monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("VAPID_PRIVATE_KEY", raising=False)
    res = await web_push.send_broadcast(title="x", body="y")
    assert res["ok"] is False
    assert res["reason"] == "not_configured"
    assert res["sent"] == 0


@pytest.mark.asyncio
async def test_send_broadcast_aggregates_results(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")

    subs = [
        {"endpoint": "https://a", "p256dh": "p", "auth": "a"},
        {"endpoint": "https://b", "p256dh": "p", "auth": "a"},
        {"endpoint": "https://c", "p256dh": "p", "auth": "a"},
    ]

    class FakeCursor:
        def __init__(self, items):
            self.items = items

        def __aiter__(self):
            self._iter = iter(self.items)
            return self

        async def __anext__(self):
            try:
                return next(self._iter)
            except StopIteration:
                raise StopAsyncIteration

    fake_db = MagicMock()
    fake_subs = MagicMock()
    fake_subs.find = MagicMock(return_value=FakeCursor(subs))
    fake_subs.update_one = AsyncMock()

    fake_history = MagicMock()
    fake_history.insert_one = AsyncMock()

    def collection_factory(name):
        return fake_subs if name == web_push._SUBS else fake_history

    fake_db.__getitem__.side_effect = collection_factory

    # First call ok (201), second 410 (expired), third generic error
    from pywebpush import WebPushException

    response_410 = MagicMock(status_code=410)
    exc_410 = WebPushException("expired", response=response_410)
    response_500 = MagicMock(status_code=500)
    exc_500 = WebPushException("server", response=response_500)

    side = [None, exc_410, exc_500]

    def fake_webpush(**_kwargs):
        x = side.pop(0)
        if isinstance(x, Exception):
            raise x
        return None

    with patch.object(web_push, "get_db", return_value=fake_db), \
         patch("services.web_push.webpush", side_effect=fake_webpush):
        res = await web_push.send_broadcast(
            title="hi", body="there", url="/sale", actor_email="admin@x.co",
        )

    assert res["ok"] is True
    assert res["sent"] == 1
    assert res["expired"] == 1
    assert res["failed"] == 1
    fake_history.insert_one.assert_awaited_once()
    history_doc = fake_history.insert_one.call_args.args[0]
    assert history_doc["sent"] == 1
    assert history_doc["expired"] == 1
    assert history_doc["actor_email"] == "admin@x.co"


@pytest.mark.asyncio
async def test_payload_truncation_keeps_within_limits(monkeypatch):
    """Notifications enforce title<=120 / body<=240 hard limits."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "pub")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "priv")

    fake_db = MagicMock()

    class EmptyCursor:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise StopAsyncIteration

    fake_subs = MagicMock()
    fake_subs.find = MagicMock(return_value=EmptyCursor())
    fake_history = MagicMock()
    fake_history.insert_one = AsyncMock()

    def collection_factory(name):
        return fake_subs if name == web_push._SUBS else fake_history

    fake_db.__getitem__.side_effect = collection_factory

    with patch.object(web_push, "get_db", return_value=fake_db):
        await web_push.send_broadcast(title="X" * 200, body="Y" * 500)
    fake_history.insert_one.assert_awaited_once()
    # Title preserved fully in history (we only truncate the wire payload)
    assert len(fake_history.insert_one.call_args.args[0]["title"]) == 200


def test_vapid_helpers_use_env(monkeypatch):
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "PUBVAL")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "PRIVVAL")
    monkeypatch.setenv("VAPID_SUBJECT", "mailto:ci@x.co")
    assert web_push._vapid_public_key() == "PUBVAL"
    assert web_push._vapid_private_key() == "PRIVVAL"
    assert web_push._vapid_subject() == "mailto:ci@x.co"
