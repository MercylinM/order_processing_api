from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.exceptions import AppError
from app.routers.orders import router as orders_router

# Assessment-scope simplification: tables are created at startup instead
# of via a migration tool. See README "what I'd improve" for the
# production alternative (Alembic).
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Order Processing API",
    description="A small backend service for creating and managing customer orders.",
    version="1.0.0",
)

app.include_router(orders_router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Reshape FastAPI/Pydantic's default error format into the same
    # {"error": {...}} envelope as the rest of the API, while keeping the
    # field-level detail that makes the error understandable to a client.
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder(
            {
                "error": {
                    "code": "validation_error",
                    "message": "The request payload is invalid.",
                    "details": exc.errors(),
                }
            }
        ),
    )


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
