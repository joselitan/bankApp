#!/usr/bin/env python3
"""Search Jira issues using the modern Jira Cloud JQL endpoint.

Your MCP Jira tool currently doesn't support the new endpoint, so this script
uses direct HTTPS calls (like our other tools) and works both locally and in CI.

Env vars:
- JIRA_BASE_URL (required)
- JIRA_EMAIL (required)
- JIRA_API_TOKEN (required)

Usage:
- python3 tools/jira/jira_search_jql.py \
    --jql-file tools/jira/jql.txt \
    --out tools/jira/raw_search.json

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
import urllib.parse
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


def _post_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={**headers, "Content-Type": "application/json"},
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
        _eprint(f"Jira JQL search failed: HTTP {e.code} {e.reason}")
        if payload_txt:
            _eprint(payload_txt)
        raise SystemExit(3)
    except Exception as e:
        _eprint(f"Jira JQL search failed: {e.__class__.__name__}: {e}")
        raise SystemExit(3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jql-file", default="tools/jira/jql.txt")
    ap.add_argument("--max-results", type=int, default=50)
    ap.add_argument("--out", default="tools/jira/raw_search.json")
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

    url = f"{base_url}/rest/api/3/search/jql"

    payload = {
        "jql": jql,
        "maxResults": max(1, args.max_results),
        "fields": [
            "summary",
            "issuetype",
            "status",
            "priority",
            "assignee",
            "reporter",
            "labels",
            "created",
            "updated",
            "description",
        ],
        "expand": ["renderedFields"],
    }

    headers = {
        "Authorization": f"Basic {_basic_auth(email, token)}",
        "Accept": "application/json",
        "User-Agent": "bankapp-jira-search-jql/1.0",
    }

    data = _post_json(url, headers, payload)

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    total = data.get("total")
    issues = data.get("issues") or []
    print(f"Fetched {len(issues)} issues (total={total})")
    print(f"Wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
