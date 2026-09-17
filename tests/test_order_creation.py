"""Integration tests for order creation: happy path, business-rule
validation, server-authoritative totals, and boundary discounts end-to-end."""
from decimal import Decimal

import pytest


def _single_item_order(subtotal, customer_id=1):
    return {
        "customer_id": customer_id,
        "items": [{"product_id": 1, "quantity": 1, "unit_price": str(subtotal)}],
    }


def test_create_order_matches_spec_example(client, order_payload):
    resp = client.post("/orders", json=order_payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["customer_id"] == 123
    assert body["status"] == "pending"
    assert Decimal(body["subtotal"]) == Decimal("950.00")
    assert Decimal(body["discount_percentage"]) == Decimal("0")
    assert Decimal(body["discount"]) == Decimal("0.00")
    assert Decimal(body["total"]) == Decimal("950.00")
    assert len(body["items"]) == 2
    assert body["items"][0]["line_total"] == "750.00"


def test_create_order_example_c_from_spec(client):
    # Order C from the spec: subtotal 12,000 -> 5% discount -> total 11,400
    resp = client.post("/orders", json=_single_item_order(12000))
    assert resp.status_code == 201
    body = resp.json()
    assert Decimal(body["subtotal"]) == Decimal("12000.00")
    assert Decimal(body["discount_percentage"]) == Decimal("5")
    assert Decimal(body["discount"]) == Decimal("600.00")
    assert Decimal(body["total"]) == Decimal("11400.00")


@pytest.mark.parametrize(
    "subtotal, expected_total",
    [
        ("5000", "5000.00"),
        ("5001", "4900.98"),
        ("10000", "9800.00"),
        ("10001", "9500.95"),
        ("20000", "19000.00"),
        ("20001", "18000.90"),
    ],
)
def test_create_order_discount_boundaries_end_to_end(client, subtotal, expected_total):
    resp = client.post("/orders", json=_single_item_order(subtotal))
    assert resp.status_code == 201
    assert resp.json()["total"] == expected_total


def test_client_supplied_total_and_discount_are_ignored_or_rejected(client):
    payload = {
        "customer_id": 1,
        "items": [{"product_id": 1, "quantity": 1, "unit_price": 100}],
        "total": 1,
        "discount": 999,
    }
    resp = client.post("/orders", json=payload)
    # extra="forbid" on the request schema -> the untrusted fields are
    # rejected outright rather than silently accepted.
    assert resp.status_code == 422


def test_order_requires_at_least_one_item(client):
    resp = client.post("/orders", json={"customer_id": 1, "items": []})
    assert resp.status_code == 422


def test_quantity_must_be_greater_than_zero(client):
    payload = {"customer_id": 1, "items": [{"product_id": 1, "quantity": 0, "unit_price": 10}]}
    resp = client.post("/orders", json=payload)
    assert resp.status_code == 422


def test_negative_unit_price_rejected(client):
    payload = {"customer_id": 1, "items": [{"product_id": 1, "quantity": 1, "unit_price": -1}]}
    resp = client.post("/orders", json=payload)
    assert resp.status_code == 422


def test_malformed_request_body_rejected(client):
    resp = client.post("/orders", json={"customer_id": "not-a-number", "items": []})
    assert resp.status_code == 422


def test_create_order_is_atomic_on_failure(client, db_session):
    """If persistence fails partway through, no order or items should be
    left behind (business rule 9)."""
    from app import models

    original_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("simulated DB failure")

    db_session.commit = failing_commit
    payload = {
        "customer_id": 1,
        "items": [{"product_id": 1, "quantity": 1, "unit_price": 100}],
    }
    with pytest.raises(RuntimeError):
        client.post("/orders", json=payload)

    db_session.commit = original_commit
    assert db_session.query(models.Order).count() == 0
    assert db_session.query(models.OrderItem).count() == 0
