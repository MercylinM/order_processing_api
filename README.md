# Order Processing API

A small backend service (Python + FastAPI) that lets customers create and
manage orders, built for the "Junior Software Engineer Technical
Assessment" brief.

## Tech stack

- **FastAPI** for the HTTP layer and request/response validation
- **SQLAlchemy 2.0** (ORM) for persistence
- **Pydantic v2** for schemas/validation
- **SQLite** by default (zero setup), swappable for Postgres/MySQL via one env var
- **pytest** + FastAPI's `TestClient` for automated tests

## Project structure

```
app/
  main.py              FastAPI app, startup table creation, error handlers
  config.py            Settings (reads DATABASE_URL from env / .env)
  database.py          SQLAlchemy engine/session setup
  models.py            ORM models: Order, OrderItem, IdempotencyKey
  schemas.py           Pydantic request/response models
  discount.py          Pure discount-calculation logic
  exceptions.py        Typed application errors -> HTTP status/code mapping
  routers/orders.py    HTTP endpoints
  services/order_service.py   Business logic (transactions, state machine)
tests/                 pytest test suite
```

I used a light layered structure (routers -> services -> models) so the
business rules (discounting, status transitions, idempotency) live in one
place, independent of HTTP concerns, and are easy to unit test.

## How to install

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt   # installs runtime + test deps
```

(Use `pip install -r requirements.txt` instead if you only want to run the
app, not the tests.)

## How to configure the database

The app reads `DATABASE_URL` from the environment (or a `.env` file — see
`.env.example`). If unset, it defaults to a local SQLite file
(`sqlite:///./orders.db`), so **no database setup is required to run the
project out of the box**.

To use Postgres instead:

```bash
cp .env.example .env
# edit .env:
# DATABASE_URL=postgresql+psycopg2://user:password@localhost:5432/orders
pip install psycopg2-binary   # driver isn't installed by default
```

Tables are created automatically on startup (`Base.metadata.create_all`) —
see "What I'd improve" for why a real migration tool would replace this.

## How to run it

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

The API is then at `http://127.0.0.1:8000`, with interactive docs at
`http://127.0.0.1:8000/docs`.

## How to run the tests

```bash
source .venv/bin/activate
pytest -v
```

Tests use an isolated in-memory SQLite database per test (no interaction
with `orders.db`), so they're safe to run at any time. 43 tests cover the
functional requirements, business rules, and discount boundary values.

## API endpoints implemented

| Method | Path                     | Description |
|--------|--------------------------|--------------|
| POST   | `/orders`                | Create an order. Supports `Idempotency-Key` header. |
| GET    | `/orders`                | List orders. Optional `?status=` filter, `skip`/`limit` pagination. |
| GET    | `/orders/{order_id}`     | Retrieve a single order with its items and cost breakdown. |
| PATCH  | `/orders/{order_id}/status` | Update order status (validated state machine). |
| GET    | `/health`                | Basic liveness check. |

### Example: create an order

```bash
curl -X POST http://127.0.0.1:8000/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 3f7a7e9e-6c1b-4a3e-9c2a-8e9f2b6b6b6b" \
  -d '{
        "customer_id": 123,
        "items": [
          {"product_id": 10, "quantity": 3, "unit_price": 250},
          {"product_id": 15, "quantity": 2, "unit_price": 100}
        ]
      }'
```

Response (`201 Created`):

```json
{
  "id": 1,
  "customer_id": 123,
  "status": "pending",
  "subtotal": "950.00",
  "discount_percentage": "0.00",
  "discount": "0.00",
  "total": "950.00",
  "created_at": "...",
  "updated_at": "...",
  "items": [ ... ]
}
```

### Errors

All errors share one envelope so a client can branch on `error.code`:

```json
{ "error": { "code": "invalid_status_transition", "message": "Cannot transition order from 'pending' to 'completed'." } }
```

`422` validation errors (bad types, missing fields, business-rule
violations enforced at the schema level like quantity <= 0) additionally
include an `error.details` array with FastAPI's field-level breakdown.

Error codes used: `validation_error` (422), `order_not_found` (404),
`invalid_status_transition` (400), `order_not_modifiable` (400),
`idempotency_key_conflict` (409).

## Business rules and how they're enforced

- **Money is never trusted from the client.** The `OrderCreate` schema
  only accepts `customer_id` and `items` (`extra="forbid"`) — subtotal,
  discount and total cannot be supplied by the client at all; they're
  always computed server-side in `order_service.create_order`.
- **Discount tiers** (`app/discount.py`): `<=5,000` → 0%, `>5,000–10,000`
  → 2%, `>10,000–20,000` → 5%, `>20,000` → 10%. Amounts use `Decimal`
  throughout (never `float`) to avoid rounding errors, rounded to cents
  with `ROUND_HALF_UP`.
- **Status state machine** (`app/models.py: ALLOWED_TRANSITIONS`):
  `pending → processing|cancelled`, `processing → completed|cancelled`.
  Any other transition is rejected as `invalid_status_transition`.
  `completed`/`cancelled` orders reject *any* further status change with a
  distinct `order_not_modifiable` error, per business rules 7 and 8.
- **Atomic creation** (business rule 9): the order row, its item rows, and
  the idempotency record are written in a single SQLAlchemy transaction —
  one `commit()`, with `rollback()` on any exception — so a failure never
  leaves a partially-created order. Covered by
  `test_create_order_is_atomic_on_failure`.
- **Idempotent retries** (business rule 10): a client can send an
  `Idempotency-Key` header on `POST /orders`. The server hashes the
  request body and stores `(key -> fingerprint, order_id)`:
  - same key + same body → the original order is returned unchanged
    (`200`, not `201` — no new order is created);
  - same key + a **different** body → `409 idempotency_key_conflict`,
    since reusing a key for a different request is a client bug, not a
    legitimate retry;
  - the header is optional — omitting it just means retries aren't
    deduplicated, which mirrors how most real-world idempotency-key APIs
    (e.g. Stripe) work.

## Assumptions made

- `unit_price` is provided by the client per line item (as in the spec's
  example payload) rather than looked up from a product catalog — there's
  no product/catalog service described in the brief, so this seemed like
  the intended scope.
- Idempotency is opt-in via a header the client controls, rather than
  something inferred from the request body alone — this is the standard,
  unambiguous way to solve rule 10 and avoids accidentally deduplicating
  two orders that genuinely happen to have identical contents.
- "Update Order Status" is the only kind of order modification in scope
  (no endpoint to edit items/quantities after creation), since the spec's
  functional requirements only describe create/retrieve/list/update-status.
- Discount tier boundaries are inclusive on the upper bound of each tier
  (`<=`), matching the spec's own table and the worked examples (e.g.
  5,000 exactly → 0%, 10,000 exactly → 2%).
- No authentication/authorization layer — out of scope for this
  assessment; `customer_id` is trusted as given, same as in the sample
  payload.

## Important technical decisions

- **Decimal, not float, for all money fields** — both in the DB
  (`Numeric`) and in Pydantic schemas — to avoid floating-point rounding
  errors compounding over subtotal/discount/total.
- **Service layer separate from routers** — `order_service.py` has no
  FastAPI imports, so the business logic (discounting, transitions,
  idempotency) can be unit-tested and reasoned about independently of
  HTTP concerns.
- **Typed exceptions mapped centrally** (`exceptions.py` +
  `app_error_handler` in `main.py`) instead of raising `HTTPException`
  scattered through the service layer — keeps error responses consistent
  and makes the service layer testable without a request context.
- **SQLite by default, Postgres-ready** — `DATABASE_URL` is the only
  config needed to switch; no code changes required, since everything
  goes through SQLAlchemy Core/ORM.

## What I'd improve with more time

- **Alembic migrations** instead of `create_all()` on startup — fine for
  an assessment, not for evolving a real schema safely.
- **Idempotency key TTL/cleanup** — keys are currently stored forever;
  in production I'd expire them after a reasonable window (e.g. 24h).
- **Product catalog + price integrity** — currently trusts the client's
  `unit_price`; a real system would look prices up server-side from a
  product/catalog table so pricing can't be tampered with client-side.
- **Pagination metadata** on `GET /orders` (total count, next/prev cursor)
  rather than plain `skip`/`limit`.
- **Concurrency test for idempotency** — the current tests cover
  sequential retries; a production version would also want a test (and
  likely a DB-level unique constraint / row lock, which
  `IdempotencyKey.key` already being a primary key gets partway there)
  for two concurrent requests racing on the same key.
- **Structured logging and request IDs** for observability.
- **Auth** (e.g. verifying the caller owns `customer_id`) — deliberately
  out of scope here but would be necessary before this could go live.
