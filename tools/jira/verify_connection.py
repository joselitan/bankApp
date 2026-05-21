#!/usr/bin/env python3
"""Verify Jira credentials configured via environment variables.

This script is designed to be used in GitHub Actions. It validates that
required env vars exist, then calls Jira's /rest/api/3/myself endpoint.

Required env vars:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN

Optional:
- JIRA_PROJECT_KEY

Exit codes:
- 0 on success
- 2 on configuration errors
- 3 on authentication/HTTP errors
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request


REQUIRED = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def require_env() -> dict[str, str]:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        _eprint(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(2)

    base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]

    return {"base_url": base_url, "email": email, "token": token}


def jira_myself(base_url: str, email: str, token: str) -> dict:
    auth = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")

    req = urllib.request.Request(
        f"{base_url}/rest/api/3/myself",
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "User-Agent": "bankapp-jira-verify/1.0",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        # Don't leak secrets; just print status and any safe error payload.
        payload = ""
        try:
            payload = e.read().decode("utf-8", errors="replace")
        except Exception:
            payload = ""
        _eprint(f"Jira request failed: HTTP {e.code} {e.reason}")
        if payload:
            _eprint("Response body (may include error details):")
            _eprint(payload)
        raise SystemExit(3)
    except Exception as e:
        _eprint(f"Jira request failed: {e.__class__.__name__}: {e}")
        raise SystemExit(3)


def main() -> int:
    cfg = require_env()

    data = jira_myself(cfg["base_url"], cfg["email"], cfg["token"])

    display_name = data.get("displayName") or data.get("display_name") or "(unknown)"
    account_id = data.get("accountId") or "(unknown)"

    print("✅ Jira authentication succeeded")
    print(f"Site: {cfg['base_url']}")
    print(f"User: {display_name}")
    print(f"Account ID: {account_id}")

    project_key = os.environ.get("JIRA_PROJECT_KEY")
    if project_key:
        print(f"Project key (env): {project_key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
