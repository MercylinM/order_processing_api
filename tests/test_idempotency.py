"""Business rule 10: retrying the same order-creation request must not
create a duplicate order."""


def test_same_idempotency_key_and_body_returns_original_order(client, order_payload):
    headers = {"Idempotency-Key": "retry-key-1"}

    first = client.post("/orders", json=order_payload, headers=headers)
    assert first.status_code == 201

    second = client.post("/orders", json=order_payload, headers=headers)
    assert second.status_code == 200  # replay, not a new creation
    assert second.json()["id"] == first.json()["id"]

    listing = client.get("/orders").json()
    assert len(listing) == 1


def test_same_idempotency_key_with_different_body_is_rejected(client, order_payload):
    headers = {"Idempotency-Key": "retry-key-2"}
    client.post("/orders", json=order_payload, headers=headers)

    different_payload = {
        "customer_id": 123,
        "items": [{"product_id": 99, "quantity": 1, "unit_price": 1}],
    }
    resp = client.post("/orders", json=different_payload, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "idempotency_key_conflict"

    listing = client.get("/orders").json()
    assert len(listing) == 1


def test_requests_without_idempotency_key_are_independent(client, order_payload):
    client.post("/orders", json=order_payload)
    client.post("/orders", json=order_payload)

    listing = client.get("/orders").json()
    assert len(listing) == 2


def test_different_idempotency_keys_create_separate_orders(client, order_payload):
    client.post("/orders", json=order_payload, headers={"Idempotency-Key": "a"})
    client.post("/orders", json=order_payload, headers={"Idempotency-Key": "b"})

    listing = client.get("/orders").json()
    assert len(listing) == 2
