def test_get_order_returns_calculation_breakdown(client, order_payload):
    created = client.post("/orders", json=order_payload).json()

    resp = client.get(f"/orders/{created['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == created["id"]
    assert set(["subtotal", "discount_percentage", "discount", "total"]).issubset(body)
    assert len(body["items"]) == 2


def test_get_nonexistent_order_returns_404(client):
    resp = client.get("/orders/999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "order_not_found"


def test_list_orders_returns_created_orders(client, order_payload):
    client.post("/orders", json=order_payload)
    client.post("/orders", json=order_payload)

    resp = client.get("/orders")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


def test_list_orders_can_filter_by_status(client, order_payload):
    order = client.post("/orders", json=order_payload).json()
    client.patch(f"/orders/{order['id']}/status", json={"status": "processing"})
    client.post("/orders", json=order_payload)  # stays "pending"

    resp = client.get("/orders", params={"status": "processing"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["status"] == "processing"
