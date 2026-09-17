import hashlib
import json
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.discount import calculate_discount
from app.exceptions import (
    IdempotencyConflictError,
    InvalidStatusTransitionError,
    OrderNotFoundError,
    OrderNotModifiableError,
)
from app.models import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    IdempotencyKey,
    Order,
    OrderItem,
    OrderStatus,
)
from app.schemas import OrderCreate


def _fingerprint(order_in: OrderCreate) -> str:
    """Stable hash of the request payload, used to tell a legitimate retry
    (same key, same body) apart from a key being reused for a different
    order (same key, different body).
    """
    payload = order_in.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def create_order(
    db: Session, order_in: OrderCreate, idempotency_key: str | None
) -> tuple[Order, bool]:
    """Create an order, atomically, from a validated payload.

    Returns (order, created). `created` is False when an existing
    Idempotency-Key was replayed, meaning no new order was created.
    """
    fingerprint = _fingerprint(order_in)

    if idempotency_key:
        existing = db.get(IdempotencyKey, idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError(idempotency_key)
            order = db.get(Order, existing.order_id)
            return order, False

    subtotal = sum(
        (item.quantity * item.unit_price for item in order_in.items),
        start=Decimal("0"),
    )
    discount_percentage, discount_amount = calculate_discount(subtotal)
    total = subtotal - discount_amount

    order = Order(
        customer_id=order_in.customer_id,
        status=OrderStatus.pending,
        subtotal=subtotal,
        discount_percentage=discount_percentage,
        discount=discount_amount,
        total=total,
    )
    for item in order_in.items:
        order.items.append(
            OrderItem(
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.quantity * item.unit_price,
            )
        )

    # Order + items + idempotency record are written in a single
    # transaction: either all of it lands, or none of it does (business
    # rule 9). `flush` assigns order.id without ending the transaction.
    try:
        db.add(order)
        db.flush()
        if idempotency_key:
            db.add(
                IdempotencyKey(
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    order_id=order.id,
                    response_status_code=201,
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(order)
    return order, True


def get_order(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    return order


def list_orders(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    status_filter: OrderStatus | None = None,
) -> list[Order]:
    stmt = select(Order).order_by(Order.id)
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_order_status(db: Session, order_id: int, new_status: OrderStatus) -> Order:
    order = get_order(db, order_id)
    current_status = OrderStatus(order.status)

    if current_status in TERMINAL_STATUSES:
        raise OrderNotModifiableError(current_status.value)

    if new_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidStatusTransitionError(current_status.value, new_status.value)

    order.status = new_status
    db.commit()
    db.refresh(order)
    return order
