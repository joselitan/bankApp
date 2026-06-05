from __future__ import annotations

import secrets


def generate_account_number() -> str:
    # Random, non-meaningful identifier. Uniqueness is enforced at DB layer.
    # Keep it URL/typeable friendly (hex).
    return secrets.token_hex(8)
