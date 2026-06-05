"""Jira Issue API helpers (non-Agile).

Used for operations like editing labels, assigning sprint field, adding comments, etc.
Dependency-free urllib + certifi.

Env vars:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN

"""

from __future__ import annotations

import base64
import json
import os
import ssl
import urllib.error
import urllib.request

import certifi


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v


def _auth_header() -> str:
    raw = f"{_env('JIRA_EMAIL')}:{_env('JIRA_API_TOKEN')}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


def _request(method: str, path: str, payload: dict | None = None) -> dict:
    base = _env("JIRA_BASE_URL").rstrip("/")
    url = f"{base}{path}"

    data = None
    headers = {
        "Authorization": _auth_header(),
        "Accept": "application/json",
        "User-Agent": "bankapp-sprint-agent/1.0",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, method=method, data=data, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=45, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira API failed: HTTP {e.code} {e.reason}\n{msg}")


def get_issue(issue_key: str, fields: list[str] | None = None) -> dict:
    q = ""
    if fields:
        q = "?fields=" + ",".join(fields)
    return _request("GET", f"/rest/api/3/issue/{issue_key}{q}")


def update_issue(issue_key: str, fields: dict) -> None:
    _request("PUT", f"/rest/api/3/issue/{issue_key}", {"fields": fields})


def update_labels(issue_key: str, *, add: list[str] | None = None, remove: list[str] | None = None) -> None:
    """Update labels using Jira update operations.

    This avoids a read-modify-write race.
    """

    ops: list[dict] = []
    for lab in add or []:
        ops.append({"add": lab})
    for lab in remove or []:
        ops.append({"remove": lab})
    if not ops:
        return

    _request(
        "PUT",
        f"/rest/api/3/issue/{issue_key}",
        {"update": {"labels": ops}},
    )
