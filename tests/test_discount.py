"""Unit tests for the discount calculation, including the boundary values
called out explicitly in the assessment spec."""
from decimal import Decimal

import pytest

from app.discount import calculate_discount


@pytest.mark.parametrize(
    "subtotal, expected_percentage, expected_amount",
    [
        # Spec examples
        (Decimal("4500"), Decimal("0"), Decimal("0.00")),
        (Decimal("8000"), Decimal("2"), Decimal("160.00")),
        (Decimal("12000"), Decimal("5"), Decimal("600.00")),
        (Decimal("25000"), Decimal("10"), Decimal("2500.00")),
        # Boundary conditions
        (Decimal("5000"), Decimal("0"), Decimal("0.00")),
        (Decimal("5001"), Decimal("2"), Decimal("100.02")),
        (Decimal("10000"), Decimal("2"), Decimal("200.00")),
        (Decimal("10001"), Decimal("5"), Decimal("500.05")),
        (Decimal("20000"), Decimal("5"), Decimal("1000.00")),
        (Decimal("20001"), Decimal("10"), Decimal("2000.10")),
        (Decimal("0"), Decimal("0"), Decimal("0.00")),
    ],
)
def test_discount_boundaries(subtotal, expected_percentage, expected_amount):
    percentage, amount = calculate_discount(subtotal)
    assert percentage == expected_percentage
    assert amount == expected_amount
