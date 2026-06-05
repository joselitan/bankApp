#!/usr/bin/env python3
"""Add the `ready-for-sprint` label to one or more Jira issues.

This is a lightweight helper to mark which backlog items should be considered
by the Mode 1 Sprint Orchestrator (Option A with explicit label gate).

Env vars:
- JIRA_BASE_URL (required)
- JIRA_EMAIL (required)
- JIRA_API_TOKEN (required)

Usage:
- python3 tools/jira/label_ready_for_sprint.py BAN-6 BAN-7

Behavior:
- Reads existing labels and adds `ready-for-sprint` if missing.
- Does not remove other labels.

Exit codes:
- 0 success
- 2 config/usage errors
- 3 HTTP/auth errors
"""

from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request

REQUIRED = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")
LABEL = "ready-for-sprint"


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _require_env() -> tuple[str, str, str]:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        _eprint(f"Missing required environment variables: {', '.join(missing)}")
        raise SystemExit(2)

    base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
    email = os.environ["JIRA_EMAIL"]
    token = os.environ["JIRA_API_TOKEN"]
    return base_url, email, token


def _basic_auth(email: str, token: str) -> str:
    return base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")


def _get_json(url: str, headers: dict[str, str]) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        payload_txt = ""
        try:
            payload_txt = e.read().decode("utf-8", errors="replace")
        except Exception:
            payload_txt = ""
        _eprint(f"GET failed: HTTP {e.code} {e.reason}")
        if payload_txt:
            _eprint(payload_txt)
        raise SystemExit(3)


def _put_json(url: str, headers: dict[str, str], payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**headers, "Content-Type": "application/json"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        payload_txt = ""
        try:
            payload_txt = e.read().decode("utf-8", errors="replace")
        except Exception:
            payload_txt = ""
        _eprint(f"PUT failed: HTTP {e.code} {e.reason}")
        if payload_txt:
            _eprint(payload_txt)
        raise SystemExit(3)


def label_issue(issue_key: str, base_url: str, headers: dict[str, str]) -> None:
    issue_url = f"{base_url}/rest/api/3/issue/{issue_key}?fields=labels"
    issue = _get_json(issue_url, headers)
    labels = ((issue.get("fields") or {}).get("labels")) or []

    if LABEL in labels:
        print(f"{issue_key}: already labeled")
        return

    new_labels = labels + [LABEL]
    update_url = f"{base_url}/rest/api/3/issue/{issue_key}"
    _put_json(update_url, headers, {"fields": {"labels": new_labels}})
    print(f"{issue_key}: labeled '{LABEL}'")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        _eprint("Usage: label_ready_for_sprint.py BAN-6 BAN-7 ...")
        return 2

    base_url, email, token = _require_env()

    headers = {
        "Authorization": f"Basic {_basic_auth(email, token)}",
        "Accept": "application/json",
        "User-Agent": "bankapp-labeler/1.0",
    }

    for key in argv[1:]:
        label_issue(key.strip(), base_url, headers)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
