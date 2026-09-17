from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models import OrderStatus

# --- Requests -----------------------------------------------------------


class OrderItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0, description="Must be greater than zero.")
    unit_price: Decimal = Field(
        ge=0, max_digits=14, decimal_places=2, description="Cannot be negative."
    )


class OrderCreate(BaseModel):
    # extra="forbid" means a client-supplied `subtotal`/`discount`/`total`
    # is rejected outright rather than silently ignored - the backend is
    # the sole source of truth for money calculations.
    model_config = ConfigDict(extra="forbid")

    customer_id: int = Field(gt=0)
    items: list[OrderItemCreate] = Field(min_length=1)


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: OrderStatus


# --- Responses ------------------------------------------------------------


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    unit_price: Decimal
    line_total: Decimal


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    status: OrderStatus
    subtotal: Decimal
    discount_percentage: Decimal
    discount: Decimal
    total: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
