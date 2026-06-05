# BAN-15 — Transfer Funds (daily limit)

## What changed
- Added automated test coverage for `POST /api/transactions/transfer` including:
  - Auth required (401)
  - Happy path money movement between two users
  - Rejects self-transfer
  - Rejects unknown recipient
  - Rejects insufficient funds
  - Enforces daily outgoing transfer limit (5000.00)

## Where to review
- `app/api/v1/transactions.py`
  - `transfer()` endpoint
- Tests:
  - `tests/test_transfer.py`

## How to verify (local)
Run unit tests from repo root:
- `make test`

Key assertions covered:
- Balances update correctly on a successful transfer
- Multiple transfers in the same UTC day are capped by daily limit (5000.00)

## Reviewer sign-off (required to move to Done)
- [x] Verified in Test environment (Swagger UI)
- Reviewer sign-off: Jose Martin
- Date: 2026-05-24

### Manual verification notes (Swagger)
- Logged in as sender and obtained JWT from `POST /api/auth/login`.
- Performed `POST /api/transactions/transfer` to another user.
- Verified:
  - Valid transfer returns **201** and updates balances as expected.
  - Transfers exceeding the daily outgoing limit return **400**.
