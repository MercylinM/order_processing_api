import pytest


def _create_order(client, order_payload):
    return client.post("/orders", json=order_payload).json()


@pytest.mark.parametrize(
    "from_status, to_status",
    [
        ("pending", "processing"),
        ("pending", "cancelled"),
        ("processing", "completed"),
        ("processing", "cancelled"),
    ],
)
def test_allowed_transitions_succeed(client, order_payload, from_status, to_status):
    order = _create_order(client, order_payload)
    if from_status == "processing":
        client.patch(f"/orders/{order['id']}/status", json={"status": "processing"})

    resp = client.patch(f"/orders/{order['id']}/status", json={"status": to_status})
    assert resp.status_code == 200
    assert resp.json()["status"] == to_status


@pytest.mark.parametrize(
    "from_status, to_status",
    [
        ("pending", "completed"),
        ("processing", "pending"),
    ],
)
def test_disallowed_transitions_are_rejected(client, order_payload, from_status, to_status):
    order = _create_order(client, order_payload)
    if from_status == "processing":
        client.patch(f"/orders/{order['id']}/status", json={"status": "processing"})

    resp = client.patch(f"/orders/{order['id']}/status", json={"status": to_status})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "invalid_status_transition"


def test_completed_order_cannot_be_modified(client, order_payload):
    order = _create_order(client, order_payload)
    client.patch(f"/orders/{order['id']}/status", json={"status": "processing"})
    client.patch(f"/orders/{order['id']}/status", json={"status": "completed"})

    resp = client.patch(f"/orders/{order['id']}/status", json={"status": "processing"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "order_not_modifiable"


def test_cancelled_order_cannot_be_modified(client, order_payload):
    order = _create_order(client, order_payload)
    client.patch(f"/orders/{order['id']}/status", json={"status": "cancelled"})

    resp = client.patch(f"/orders/{order['id']}/status", json={"status": "processing"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "order_not_modifiable"


def test_invalid_status_value_is_rejected(client, order_payload):
    order = _create_order(client, order_payload)
    resp = client.patch(f"/orders/{order['id']}/status", json={"status": "shipped"})
    assert resp.status_code == 422


def test_status_update_on_nonexistent_order_returns_404(client):
    resp = client.patch("/orders/999999/status", json={"status": "processing"})
    assert resp.status_code == 404
