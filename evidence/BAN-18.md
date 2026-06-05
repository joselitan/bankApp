# BAN-18 — Audit Logging

## What changed
- Added automated test coverage verifying audit events are inserted into `audit_logs` for key actions:
  - `register_success`
  - `login_success`
  - `login_failure` (unknown user)
  - `deposit`
  - `transfer`

## Where to review
- `app/services/audit.py`
  - `log_action()` helper
- `app/models/audit_log.py`
  - `AuditLog` model
- Call sites:
  - `app/api/v1/auth.py` (register)
  - `app/services/auth.py` (login success/failure/locked)
  - `app/api/v1/transactions.py` (deposit/transfer)
- Tests:
  - `tests/test_audit_logging.py`

## How to verify (local)
Run unit tests from repo root:
- `make test`

The audit logging tests query the `audit_logs` table directly and assert expected `action` values exist.

## Reviewer sign-off (required to move to Done)
- [x] Verified in Test environment (Swagger UI)
- Reviewer sign-off: Jose Martin
- Date: 2026-05-24

### Manual verification notes (Swagger)
- Performed register, login, deposit, and transfer flows in Swagger.
- Confirmed behavior matched expectations; audit coverage is primarily validated via automated tests (`tests/test_audit_logging.py`).
