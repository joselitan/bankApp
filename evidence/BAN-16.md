# BAN-16 — Atomic Transfers (rollback/consistency)

## What changed
- Added test coverage demonstrating transfer atomicity:
  - When a transfer is rejected (daily limit / invalid recipient / insufficient funds), balances do not partially update.
  - Successful transfers update both sender and recipient balances consistently.

## Where to review
- `app/api/v1/transactions.py`
  - `transfer()` endpoint (single commit at end, rollback on error)
- Tests:
  - `tests/test_transfer.py`

## How to verify (local)
Run unit tests from repo root:
- `make test`

## Reviewer sign-off (required to move to Done)
- [x] Verified in Test environment (Swagger UI)
- Reviewer sign-off: Jose Martin
- Date: 2026-05-24

### Manual verification notes (Swagger)
- Exercised `POST /api/transactions/transfer` success and failure cases.
- Confirmed when a transfer is rejected (e.g., daily limit / insufficient funds), balances do not partially change.
