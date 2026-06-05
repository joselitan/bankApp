"""Minimal .env loader for Jira tooling.

We keep this dependency-free on purpose.

Behavior:
- If a .env-style file exists at repo root (default: .env.local), load KEY=VALUE pairs
  into os.environ *only if the key is not already set*.
- Lines starting with # are ignored.
- Blank lines are ignored.

This lets developers keep Jira secrets locally without exporting them in every shell.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(filename: str = ".env.local") -> None:
    root = Path(__file__).resolve().parents[2]
    path = root / filename
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
