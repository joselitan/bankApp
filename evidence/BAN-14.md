# BAN-14 — Deposit Funds

## What changed
- Added automated test coverage for `POST /api/transactions/deposit` covering:
  - Auth required (401 when missing bearer token)
  - Minimum amount boundary (min = 1.00)
  - Maximum amount boundary (max = 10000.00)
  - Balance accumulation across multiple deposits

## Where to review
- `app/api/v1/transactions.py`
  - `deposit()` endpoint
- `app/schemas/transactions.py`
  - `DepositRequest` schema
- Tests:
  - `tests/test_deposit.py`

## How to verify (local)
Run unit tests from repo root:
- `make test`

Expected:
- Deposits outside bounds return 400
- Deposits within bounds return 201 and updated balance

## Reviewer sign-off (required to move to Done)
- [x] Verified in Test environment (Swagger UI)
- Reviewer sign-off: Jose Martin
- Date: 2026-05-24

### Manual verification notes (Swagger)
- Logged in and obtained a JWT from `POST /api/auth/login`.
- Called `POST /api/transactions/deposit` with `Authorization: Bearer <token>`.
- Verified:
  - Valid deposit returns **201** and increases balance.
  - Invalid amount (below min / above max) returns **400**.
