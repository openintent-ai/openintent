"""
Tests for RFC-0021 Agent-to-Agent Messaging.

Covers:
  - Channel CRUD: create, list, get, update, close/delete
  - Messaging: send message, list messages, get message, mark as read
  - Request/Response correlation: reply to message, verify correlation_id
  - Access control: channels scoped to intents
"""

import os
import tempfile

import pytest

from openintent.server.config import ServerConfig

API_KEY = "dev-key-1"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from openintent.server import database as db_module
    from openintent.server.app import create_app

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_module._database = None
    config = ServerConfig(
        database_url=f"sqlite:///{db_path}",
        api_keys={"dev-key-1", "dev-user-key"},
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c

    db_module._database = None
    os.unlink(db_path)


def _create_intent(client):
    resp = client.post(
        "/api/v1/intents",
        json={"title": "Test Intent", "description": "For messaging tests"},
        headers=HEADERS,
    )
    assert resp.status_code in (200, 201)
    return resp.json()["id"]


def _create_channel(client, intent_id, name="general", members=None):
    resp = client.post(
        f"/api/v1/intents/{intent_id}/channels",
        json={
            "name": name,
            "members": members or ["agent-a", "agent-b"],
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    return resp.json()


def _send_message(
    client, channel_id, sender="agent-a", payload=None, message_type="notify"
):
    resp = client.post(
        f"/api/v1/channels/{channel_id}/messages",
        json={
            "sender": sender,
            "message_type": message_type,
            "payload": payload or {"text": "hello"},
        },
        headers=HEADERS,
    )
    assert resp.status_code == 201
    return resp.json()


class TestChannelCRUD:

    def test_create_channel(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id, name="ops")
        assert ch["id"]
        assert ch["intent_id"] == intent_id
        assert ch["name"] == "ops"
        assert ch["status"] == "open"
        assert ch["message_count"] == 0
        assert "agent-a" in ch["members"]
        assert "agent-b" in ch["members"]

    def test_list_channels(self, client):
        intent_id = _create_intent(client)
        _create_channel(client, intent_id, name="chan-1")
        _create_channel(client, intent_id, name="chan-2")

        resp = client.get(
            f"/api/v1/intents/{intent_id}/channels",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {c["name"] for c in data}
        assert names == {"chan-1", "chan-2"}

    def test_get_channel(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id, name="get-test")

        resp = client.get(
            f"/api/v1/channels/{ch['id']}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == ch["id"]
        assert data["name"] == "get-test"

    def test_get_channel_not_found(self, client):
        resp = client.get(
            "/api/v1/channels/nonexistent-id",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_update_channel_members(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.patch(
            f"/api/v1/channels/{ch['id']}",
            json={"members": ["agent-a", "agent-b", "agent-c"]},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "agent-c" in data["members"]

    def test_update_channel_status_closed(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.patch(
            f"/api/v1/channels/{ch['id']}",
            json={"status": "closed"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["closed_at"] is not None

    def test_update_channel_options(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.patch(
            f"/api/v1/channels/{ch['id']}",
            json={"options": {"ttl": 3600}},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["options"] == {"ttl": 3600}

    def test_update_channel_not_found(self, client):
        resp = client.patch(
            "/api/v1/channels/nonexistent-id",
            json={"members": []},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_delete_channel(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.delete(
            f"/api/v1/channels/{ch['id']}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "closed"
        assert data["channel_id"] == ch["id"]

        resp2 = client.get(
            f"/api/v1/channels/{ch['id']}",
            headers=HEADERS,
        )
        assert resp2.status_code == 404

    def test_delete_channel_not_found(self, client):
        resp = client.delete(
            "/api/v1/channels/nonexistent-id",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_create_channel_with_task_id(self, client):
        intent_id = _create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/channels",
            json={
                "name": "task-chan",
                "members": ["agent-x"],
                "task_id": "task-123",
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["task_id"] == "task-123"

    def test_create_channel_with_options(self, client):
        intent_id = _create_intent(client)
        resp = client.post(
            f"/api/v1/intents/{intent_id}/channels",
            json={
                "name": "opts-chan",
                "members": [],
                "options": {"max_messages": 100},
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["options"] == {"max_messages": 100}


class TestMessaging:

    def test_send_message(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        msg = _send_message(client, ch["id"], sender="agent-a", payload={"text": "hi"})

        assert msg["id"]
        assert msg["channel_id"] == ch["id"]
        assert msg["sender"] == "agent-a"
        assert msg["message_type"] == "notify"
        assert msg["payload"] == {"text": "hi"}
        assert msg["status"] == "delivered"
        assert msg["correlation_id"] is None

    def test_send_message_to_channel_not_found(self, client):
        resp = client.post(
            "/api/v1/channels/nonexistent/messages",
            json={"sender": "agent-a", "payload": {"text": "hi"}},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_send_message_increments_count(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        _send_message(client, ch["id"])
        _send_message(client, ch["id"])

        resp = client.get(f"/api/v1/channels/{ch['id']}", headers=HEADERS)
        data = resp.json()
        assert data["message_count"] == 2
        assert data["last_message_at"] is not None

    def test_list_messages(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        _send_message(client, ch["id"], sender="agent-a", payload={"n": 1})
        _send_message(client, ch["id"], sender="agent-b", payload={"n": 2})

        resp = client.get(
            f"/api/v1/channels/{ch['id']}/messages",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) == 2

    def test_list_messages_channel_not_found(self, client):
        resp = client.get(
            "/api/v1/channels/nonexistent/messages",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_list_messages_filter_by_to(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        client.post(
            f"/api/v1/channels/{ch['id']}/messages",
            json={"sender": "agent-a", "to": "agent-b", "payload": {"x": 1}},
            headers=HEADERS,
        )
        client.post(
            f"/api/v1/channels/{ch['id']}/messages",
            json={"sender": "agent-a", "to": "agent-c", "payload": {"x": 2}},
            headers=HEADERS,
        )

        resp = client.get(
            f"/api/v1/channels/{ch['id']}/messages",
            params={"to": "agent-b"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        msgs = resp.json()
        assert len(msgs) == 1
        assert msgs[0]["to"] == "agent-b"

    def test_list_messages_since_cursor(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        msg1 = _send_message(client, ch["id"], payload={"seq": 1})
        msg2 = _send_message(client, ch["id"], payload={"seq": 2})
        msg3 = _send_message(client, ch["id"], payload={"seq": 3})

        resp = client.get(
            f"/api/v1/channels/{ch['id']}/messages",
            params={"since": msg1["id"]},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        msgs = resp.json()
        ids = [m["id"] for m in msgs]
        assert msg1["id"] not in ids
        assert msg2["id"] in ids
        assert msg3["id"] in ids

    def test_get_message(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        msg = _send_message(client, ch["id"])

        resp = client.get(
            f"/api/v1/channels/{ch['id']}/messages/{msg['id']}",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == msg["id"]
        assert data["sender"] == "agent-a"

    def test_get_message_not_found(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.get(
            f"/api/v1/channels/{ch['id']}/messages/nonexistent",
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_mark_message_as_read(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        msg = _send_message(client, ch["id"])

        resp = client.patch(
            f"/api/v1/channels/{ch['id']}/messages/{msg['id']}",
            json={"status": "read"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "read"
        assert data["read_at"] is not None

    def test_update_message_status_not_found(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.patch(
            f"/api/v1/channels/{ch['id']}/messages/nonexistent",
            json={"status": "read"},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_send_directed_message(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.post(
            f"/api/v1/channels/{ch['id']}/messages",
            json={
                "sender": "agent-a",
                "to": "agent-b",
                "message_type": "request",
                "payload": {"action": "summarize"},
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["to"] == "agent-b"
        assert data["message_type"] == "request"


class TestRequestResponseCorrelation:

    def test_reply_to_message(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        original = _send_message(
            client,
            ch["id"],
            sender="agent-a",
            payload={"question": "status?"},
            message_type="request",
        )

        resp = client.post(
            f"/api/v1/channels/{ch['id']}/messages/{original['id']}/reply",
            json={
                "sender": "agent-b",
                "payload": {"answer": "all good"},
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        reply = resp.json()
        assert reply["correlation_id"] == original["id"]
        assert reply["sender"] == "agent-b"
        assert reply["to"] == "agent-a"
        assert reply["message_type"] == "response"
        assert reply["payload"] == {"answer": "all good"}

    def test_reply_sets_correlation_id(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        msg = _send_message(client, ch["id"], sender="agent-x")

        resp = client.post(
            f"/api/v1/channels/{ch['id']}/messages/{msg['id']}/reply",
            json={"sender": "agent-y", "payload": {"ack": True}},
            headers=HEADERS,
        )
        assert resp.status_code == 201
        reply = resp.json()
        assert reply["correlation_id"] == msg["id"]

    def test_reply_to_nonexistent_message(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)

        resp = client.post(
            f"/api/v1/channels/{ch['id']}/messages/nonexistent/reply",
            json={"sender": "agent-b", "payload": {}},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_reply_to_message_channel_not_found(self, client):
        resp = client.post(
            "/api/v1/channels/nonexistent/messages/some-msg/reply",
            json={"sender": "agent-b", "payload": {}},
            headers=HEADERS,
        )
        assert resp.status_code == 404

    def test_reply_increments_message_count(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        msg = _send_message(client, ch["id"])

        client.post(
            f"/api/v1/channels/{ch['id']}/messages/{msg['id']}/reply",
            json={"sender": "agent-b", "payload": {"ok": True}},
            headers=HEADERS,
        )

        resp = client.get(f"/api/v1/channels/{ch['id']}", headers=HEADERS)
        assert resp.json()["message_count"] == 2

    def test_reply_with_metadata(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id)
        msg = _send_message(client, ch["id"])

        resp = client.post(
            f"/api/v1/channels/{ch['id']}/messages/{msg['id']}/reply",
            json={
                "sender": "agent-b",
                "payload": {"data": 42},
                "metadata": {"latency_ms": 120},
            },
            headers=HEADERS,
        )
        assert resp.status_code == 201
        assert resp.json()["metadata"] == {"latency_ms": 120}


class TestAccessControl:

    def test_channels_scoped_to_intent(self, client):
        intent_1 = _create_intent(client)
        intent_2 = _create_intent(client)

        _create_channel(client, intent_1, name="chan-intent1")
        _create_channel(client, intent_2, name="chan-intent2")

        resp1 = client.get(
            f"/api/v1/intents/{intent_1}/channels",
            headers=HEADERS,
        )
        resp2 = client.get(
            f"/api/v1/intents/{intent_2}/channels",
            headers=HEADERS,
        )

        chans1 = resp1.json()
        chans2 = resp2.json()

        assert len(chans1) == 1
        assert chans1[0]["name"] == "chan-intent1"
        assert chans1[0]["intent_id"] == intent_1

        assert len(chans2) == 1
        assert chans2[0]["name"] == "chan-intent2"
        assert chans2[0]["intent_id"] == intent_2

    def test_missing_api_key_returns_401(self, client):
        resp = client.get("/api/v1/channels/some-id")
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self, client):
        resp = client.get(
            "/api/v1/channels/some-id",
            headers={"X-API-Key": "invalid-key"},
        )
        assert resp.status_code == 401

    def test_empty_intent_has_no_channels(self, client):
        intent_id = _create_intent(client)
        resp = client.get(
            f"/api/v1/intents/{intent_id}/channels",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_delete_removes_channel_from_listing(self, client):
        intent_id = _create_intent(client)
        ch = _create_channel(client, intent_id, name="to-delete")

        client.delete(f"/api/v1/channels/{ch['id']}", headers=HEADERS)

        resp = client.get(
            f"/api/v1/intents/{intent_id}/channels",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 0

    def test_messages_isolated_per_channel(self, client):
        intent_id = _create_intent(client)
        ch1 = _create_channel(client, intent_id, name="ch1")
        ch2 = _create_channel(client, intent_id, name="ch2")

        _send_message(client, ch1["id"], payload={"chan": "ch1"})
        _send_message(client, ch2["id"], payload={"chan": "ch2"})

        resp1 = client.get(
            f"/api/v1/channels/{ch1['id']}/messages",
            headers=HEADERS,
        )
        resp2 = client.get(
            f"/api/v1/channels/{ch2['id']}/messages",
            headers=HEADERS,
        )

        msgs1 = resp1.json()
        msgs2 = resp2.json()

        assert len(msgs1) == 1
        assert msgs1[0]["payload"] == {"chan": "ch1"}
        assert len(msgs2) == 1
        assert msgs2[0]["payload"] == {"chan": "ch2"}
