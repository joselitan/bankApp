# BAN-7 — Login/Logout + Lockout after 3 failures

## What changed
- Implemented login endpoint `POST /api/auth/login` returning a JWT access token on success.
- Implemented lockout after 3 consecutive failed attempts:
  - Attempts 1–3 return **401** `{"detail":"Invalid credentials"}`
  - 4th attempt during lockout window returns **423** `{"detail":"Account locked"}`
- Added/updated DB fields on `User` for tracking lockout:
  - `failed_login_attempts`
  - `locked_until`

## Where to review
- `app/services/auth.py`
  - `authenticate_user(...)` (failed attempt tracking + lockout)
- `app/api/v1/auth.py`
  - `login(...)` (commit/rollback so lockout state persists between requests)
- `tests/test_auth_login.py`
  - `test_login_happy_path_returns_token`
  - `test_login_lockout_after_3_failures`

## How to verify (local)
Run unit tests from the repo root:
- `make test`

Expected: all tests pass.

## Manual API verification
1) Register a user, then try logging in with a wrong password 3 times → should get 401.
2) 4th wrong attempt within lockout window → should get 423.
3) Correct password while locked → should also get 423 (until lockout expires).

## Reviewer sign-off (required to move to Done)
- [x] Verified in Test environment (Swagger UI)
- Reviewer: Jose Martin
- Date: 2026-05-24

### Manual verification notes (Swagger)
- Registered a user via `POST /api/auth/register`.
- Attempted `POST /api/auth/login` with a wrong password 3 times → **401**.
- 4th attempt during lockout window → **423**.
- Verified correct password while lockout active also returns **423**.
