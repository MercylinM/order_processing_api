from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import OrderStatus
from app.schemas import OrderCreate, OrderRead, OrderStatusUpdate
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: OrderCreate,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Create an order.

    Send an `Idempotency-Key` header to make retries of this request safe:
    if the same key is sent again with the same body, the original order
    is returned instead of a duplicate being created (200 instead of 201).
    """
    order, created = order_service.create_order(db, order_in, idempotency_key)
    if not created:
        response.status_code = status.HTTP_200_OK
    return order


@router.get("", response_model=list[OrderRead])
def list_orders(
    db: Annotated[Session, Depends(get_db)],
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    order_status: Annotated[OrderStatus | None, Query(alias="status")] = None,
):
    return order_service.list_orders(db, skip=skip, limit=limit, status_filter=order_status)


@router.get("/{order_id}", response_model=OrderRead)
def get_order(order_id: int, db: Annotated[Session, Depends(get_db)]):
    return order_service.get_order(db, order_id)


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
):
    return order_service.update_order_status(db, order_id, payload.status)
