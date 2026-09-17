"""Discount calculation.

Rules (subtotal boundaries are inclusive on the lower end already covered
by the previous tier, i.e. `<=` on the upper bound of each tier):

    subtotal <= 5,000                 -> 0%
    5,000  < subtotal <= 10,000        -> 2%
    10,000 < subtotal <= 20,000        -> 5%
    subtotal > 20,000                  -> 10%
"""
from decimal import ROUND_HALF_UP, Decimal

_CENTS = Decimal("0.01")


def calculate_discount(subtotal: Decimal) -> tuple[Decimal, Decimal]:
    """Return (discount_percentage, discount_amount) for a given subtotal.

    The client never supplies these values — they are always derived here
    from the subtotal the backend itself computed.
    """
    if subtotal <= Decimal("5000"):
        percentage = Decimal("0")
    elif subtotal <= Decimal("10000"):
        percentage = Decimal("2")
    elif subtotal <= Decimal("20000"):
        percentage = Decimal("5")
    else:
        percentage = Decimal("10")

    amount = (subtotal * percentage / Decimal("100")).quantize(
        _CENTS, rounding=ROUND_HALF_UP
    )
    return percentage, amount
