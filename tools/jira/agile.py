"""Jira Agile (Scrum/Kanban) API helpers.

These utilities are used by automations that need sprint/board operations.
They intentionally stay dependency-free (urllib) and use certifi for SSL.

Agile REST base:
- /rest/agile/1.0

Env vars (read from process env; callers can use tools.jira.env.load_dotenv()):
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
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")
    raw = f"{email}:{token}".encode("utf-8")
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
        raise RuntimeError(f"Jira Agile API failed: HTTP {e.code} {e.reason}\n{msg}")


def get_board(board_id: int) -> dict:
    return _request("GET", f"/rest/agile/1.0/board/{int(board_id)}")


def list_boards(project_key: str | None = None, max_results: int = 50) -> dict:
    params = f"?maxResults={int(max_results)}"
    if project_key:
        params += f"&projectKeyOrId={project_key}"
    return _request("GET", f"/rest/agile/1.0/board{params}")


def create_sprint(board_id: int, name: str) -> dict:
    payload = {"name": name, "originBoardId": int(board_id)}
    return _request("POST", "/rest/agile/1.0/sprint", payload)


def add_issues_to_sprint(sprint_id: int, issue_keys: list[str]) -> None:
    # POST /rest/agile/1.0/sprint/{sprintId}/issue
    _request(
        "POST",
        f"/rest/agile/1.0/sprint/{int(sprint_id)}/issue",
        {"issues": issue_keys},
    )


def list_sprints(
    board_id: int,
    *,
    state: str | None = None,
    max_results: int = 50,
    start_at: int = 0,
) -> dict:
    """List sprints for a given board.

    state can be one of: future, active, closed (comma-separated values supported by Jira).
    """

    qs = f"?startAt={int(start_at)}&maxResults={int(max_results)}"
    if state:
        qs += f"&state={state}"
    return _request("GET", f"/rest/agile/1.0/board/{int(board_id)}/sprint{qs}")


def close_sprint(sprint_id: int) -> dict:
    """Close a sprint.

    Jira requires updating the sprint with state=closed.
    """

    return _request("PUT", f"/rest/agile/1.0/sprint/{int(sprint_id)}", {"state": "closed"})


def get_sprint(sprint_id: int) -> dict:
    return _request("GET", f"/rest/agile/1.0/sprint/{int(sprint_id)}")


def find_sprint_by_name(board_id: int, name: str) -> dict | None:
    """Best-effort lookup of a sprint by name on a board.

    Jira doesn't provide a direct 'search by name' endpoint, so we page through
    sprints. This is fine for our scale.
    """

    start_at = 0
    while True:
        data = list_sprints(board_id, max_results=50, start_at=start_at)
        values = data.get("values") or []
        for s in values:
            if (s.get("name") or "").strip() == name.strip():
                return s
        if data.get("isLast") is True:
            return None
        start_at += len(values)

