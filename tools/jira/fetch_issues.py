#!/usr/bin/env python3
"""Fetch Jira issues using a JQL query and output normalized JSON.

Designed for GitHub Actions usage (Mode 1 / plan-only). The output is
consumed by generate_sprint_plan.py.

Env vars:
- JIRA_BASE_URL (required)
- JIRA_EMAIL (required)
- JIRA_API_TOKEN (required)

Inputs:
- --jql-file tools/jira/jql.txt (default)
- --max-results N (default 50)
- --out tools/jira/issues.json (default)

Exit codes:
- 0 success
- 2 config/usage errors
- 3 HTTP/auth errors
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request


REQUIRED = ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN")


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


def _jira_search(
    *,
    base_url: str,
    email: str,
    token: str,
    jql: str,
    max_results: int,
) -> dict:
    """Call Jira's supported JQL search endpoint.

    Atlassian has removed the older /rest/api/3/search endpoint in some tenants.
    This uses POST /rest/api/3/search/jql.
    """

    url = f"{base_url}/rest/api/3/search/jql"

    payload = {
        "jql": jql,
        "maxResults": int(max_results),
        "fields": [
            "summary",
            "issuetype",
            "status",
            "priority",
            "assignee",
            "reporter",
            "labels",
            "components",
            "fixVersions",
            "created",
            "updated",
            "description",
        ],
        "expand": ["renderedFields"],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {_basic_auth(email, token)}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "bankapp-sprint-orchestrator/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        payload_txt = ""
        try:
            payload_txt = e.read().decode("utf-8", errors="replace")
        except Exception:
            payload_txt = ""
        _eprint(f"Jira search failed: HTTP {e.code} {e.reason}")
        if payload_txt:
            _eprint(payload_txt)
        raise SystemExit(3)
    except Exception as e:
        _eprint(f"Jira search failed: {e.__class__.__name__}: {e}")
        raise SystemExit(3)


def _normalize_issue(raw: dict, base_url: str) -> dict:
    fields = raw.get("fields") or {}

    assignee = fields.get("assignee") or {}
    reporter = fields.get("reporter") or {}

    def _name(user: dict | None) -> str | None:
        if not user:
            return None
        return user.get("displayName") or user.get("emailAddress") or user.get("accountId")

    return {
        "key": raw.get("key"),
        "url": f"{base_url}/browse/{raw.get('key')}",
        "summary": fields.get("summary"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "status": (fields.get("status") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "assignee": _name(assignee),
        "reporter": _name(reporter),
        "labels": fields.get("labels") or [],
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        # Keep both raw and rendered descriptions so the markdown generator can choose.
        "description": fields.get("description"),
        "rendered_description": ((raw.get("renderedFields") or {}).get("description")),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jql-file", default="tools/jira/jql.txt")
    ap.add_argument("--max-results", type=int, default=50)
    ap.add_argument("--out", default="tools/jira/issues.json")
    args = ap.parse_args()

    base_url, email, token = _require_env()

    try:
        with open(args.jql_file, "r", encoding="utf-8") as f:
            jql = f.read().strip()
    except FileNotFoundError:
        _eprint(f"JQL file not found: {args.jql_file}")
        return 2

    if not jql:
        _eprint("JQL file is empty")
        return 2

    data = _jira_search(
        base_url=base_url,
        email=email,
        token=token,
        jql=jql,
        max_results=max(1, args.max_results),
    )

    raw_issues = data.get("issues") or []
    normalized = [_normalize_issue(i, base_url) for i in raw_issues]

    out_payload = {
        "jql": jql,
        "max_results": args.max_results,
        "total": data.get("total"),
        "issues": normalized,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Fetched {len(normalized)} issues (total={data.get('total')})")
    print(f"Wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
