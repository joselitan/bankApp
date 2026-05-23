# MVP Sprint 1 — Proposed scope (ready-for-sprint)

Generated: 2026-05-23

This sprint aims to deliver an **API-first MVP** (Postman-like usage) with the smallest set of endpoints needed to support:

- Register
- Login/logout
- Default account creation
- View account balance + recent transactions
- Deposit
- Internal transfer (with daily limit)
- Audit logging
- Transaction atomicity

> Note: This file is a human-readable sprint plan. Our GitHub Actions workflow will generate `SPRINT_PLAN.md` as an artifact once run on GitHub.

## Scope (approved issues)

| Order | Key | Summary | Why it’s in MVP |
|---:|---|---|---|
| 1 | [BAN-6](https://joselitan.atlassian.net/browse/BAN-6) | FR-01 User Registration API + validation rules | Entry point; creates a user |
| 2 | [BAN-10](https://joselitan.atlassian.net/browse/BAN-10) | FR-04 Create default Savings account on user registration (balance $0.00) | Ensures every user has an account |
| 3 | [BAN-7](https://joselitan.atlassian.net/browse/BAN-7) | FR-02 Login/Logout with secure session + lockout after 3 failures | Auth gate + brute-force defense |
| 4 | [BAN-18](https://joselitan.atlassian.net/browse/BAN-18) | FR-10 Audit log table + logging for key actions (success + failure) | Traceability + training value |
| 5 | [BAN-11](https://joselitan.atlassian.net/browse/BAN-11) | FR-05 Account details endpoint + last 10 transactions | Lets us confirm balances & history |
| 6 | [BAN-14](https://joselitan.atlassian.net/browse/BAN-14) | FR-07 Deposit endpoint with min/max validation | Easy money-in operation |
| 7 | [BAN-16](https://joselitan.atlassian.net/browse/BAN-16) | NFR-06 Ensure transaction atomicity (DB transaction + rollback on failure) | Prevents partial transfers |
| 8 | [BAN-15](https://joselitan.atlassian.net/browse/BAN-15) | FR-08 Internal transfer with business rules + daily limit ($5,000) | Core money-move MVP feature |

## Dependencies / execution order

- `BAN-6` (register) must exist before everything else.
- `BAN-10` should be implemented as part of registration transaction so we never create a user without an account.
- `BAN-7` (login) must be in place before protected endpoints.
- `BAN-18` (audit log) is best done early so we can log everything from day one.
- `BAN-16` (atomicity) should be implemented alongside `BAN-15` to keep transfer correct from v1.

## API contract (MVP draft)

These endpoints are the minimum slice implied by the stories:

### Auth
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- (Optional convenience) `GET /api/auth/me`

### Accounts
- `GET /api/accounts/me` (balance + account_number + last 10 transactions)

### Transactions
- `POST /api/transactions/deposit` `{ amount }`
- `POST /api/transactions/transfer` `{ to_email, amount }` (or `to_user_id`)

## Test expectations (Sprint 1)

Even with API-first delivery, the MVP should include automated tests:

- pytest API tests for:
  - registration validations
  - login happy path + lockout behavior
  - deposit boundaries
  - transfer rules (self, insufficient funds, daily limit)
  - atomicity rollback behavior (forced failure simulation)
  - audit log rows created for key actions

## Next step

1. Run the **Sprint Orchestrator (Mode 1 - plan only)** GitHub Action on branch `option-a/sprint-orchestrator`.
2. Download the artifact `sprint-plan`.
3. Use the generated `SPRINT_PLAN.md` as the working plan during implementation.
