"""Application-level errors.

Each maps to an HTTP status code and a machine-readable `code`, so API
consumers can branch on `error.code` instead of parsing prose, while the
`message` stays human-readable.
"""
from fastapi import status


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class OrderNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "order_not_found"

    def __init__(self, order_id: int):
        super().__init__(f"Order {order_id} was not found.")


class OrderNotModifiableError(AppError):
    """Raised when trying to change a completed/cancelled order."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "order_not_modifiable"

    def __init__(self, current_status: str):
        super().__init__(
            f"Order is '{current_status}' and can no longer be modified."
        )


class InvalidStatusTransitionError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_status_transition"

    def __init__(self, current_status: str, new_status: str):
        super().__init__(
            f"Cannot transition order from '{current_status}' to '{new_status}'."
        )


class IdempotencyConflictError(AppError):
    """Same Idempotency-Key reused with a different request body."""

    status_code = status.HTTP_409_CONFLICT
    code = "idempotency_key_conflict"

    def __init__(self, key: str):
        super().__init__(
            f"Idempotency-Key '{key}' was already used with a different "
            "request payload."
        )
