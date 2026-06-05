"""Jira workflow helper for the SecureCore Bank repo.

Goals:
- Transition issues through the board states (To Do / In Progress / Done)
- Post a standard, machine-checkable comment explaining how a ticket was solved

This is intentionally small and dependency-free (urllib) to match the other Jira tooling.

Environment:
- JIRA_BASE_URL (e.g., https://example.atlassian.net)
- JIRA_EMAIL
- JIRA_API_TOKEN

Examples:
- Transition:
    python tools/jira/workflow.py transition BAN-6 "In Progress"

- Comment with verification payload (from a file):
    python tools/jira/workflow.py comment BAN-6 --file evidence/BAN-6.md

- Complete (post evidence + move to Test):
    python tools/jira/workflow.py complete BAN-6 --file evidence/BAN-6.md

- Comment with inline text:
    python tools/jira/workflow.py comment BAN-6 --text "..."

"""

import argparse
import base64
import json
import os
import pathlib
import ssl
import sys
import urllib.error
import urllib.request

import certifi

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.jira.env import load_dotenv  # noqa: E402
from tools.jira.issues import update_labels  # noqa: E402

load_dotenv()


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def _auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


def _request(method: str, url: str, payload: dict | None = None) -> dict:
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")

    data = None
    headers = {
        "Authorization": _auth_header(email, token),
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            body = resp.read().decode("utf-8")
            if not body:
                return {}
            return json.loads(body)
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8")
        raise SystemExit(f"Jira API failed: HTTP {e.code} {e.reason}\n{msg}")


def transition_issue(issue_key: str, target_status: str) -> None:
    base = _env("JIRA_BASE_URL").rstrip("/")

    # Ask Jira what transitions are available from current state.
    transitions = _request(
        "GET",
        f"{base}/rest/api/3/issue/{issue_key}/transitions",
    )

    candidates = transitions.get("transitions", [])
    for t in candidates:
        to = t.get("to", {})
        if to.get("name") == target_status:
            transition_id = t.get("id")
            _request(
                "POST",
                f"{base}/rest/api/3/issue/{issue_key}/transitions",
                {"transition": {"id": transition_id}},
            )
            print(f"OK: {issue_key} transitioned to '{target_status}'")
            return

    available = ", ".join(
        sorted({t.get("to", {}).get("name", "") for t in candidates if t.get("to")})
    )
    raise SystemExit(
        f"No transition to '{target_status}' is currently available for {issue_key}. "
        f"Available targets: {available or '(none)'}"
    )


def add_comment(issue_key: str, body_text: str) -> None:
    base = _env("JIRA_BASE_URL").rstrip("/")

    # Jira Cloud uses Atlassian Document Format (ADF).
    payload = {
        "body": {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": body_text}],
                }
            ],
        }
    }

    _request("POST", f"{base}/rest/api/3/issue/{issue_key}/comment", payload)
    print(f"OK: comment added to {issue_key}")


def _read_text_arg(args: argparse.Namespace) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read().strip()
    if args.text:
        return args.text.strip()
    raise SystemExit("Provide --file or --text")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_t = sub.add_parser("transition", help="Transition an issue to a new status")
    p_t.add_argument("issue_key")
    p_t.add_argument("status", help="Target status name (e.g., 'To Do', 'In Progress', 'Done')")

    p_c = sub.add_parser("comment", help="Add a comment to an issue")
    p_c.add_argument("issue_key")
    p_c.add_argument("--file", help="Path to a text/markdown file to post")
    p_c.add_argument("--text", help="Inline comment text")

    p_done = sub.add_parser(
        "complete",
        help="Post evidence to Jira and move the issue to 'Test' for human verification",
    )
    p_done.add_argument("issue_key")
    p_done.add_argument("--file", required=True, help="Evidence markdown/text file to post")

    p_mark_done = sub.add_parser(
        "done",
        help=(
            "Post evidence to Jira, transition the issue to 'Done', and remove the 'ready-for-sprint' label "
            "(if present). Intended for after human sign-off."
        ),
    )
    p_mark_done.add_argument("issue_key")
    p_mark_done.add_argument("--file", required=True, help="Evidence markdown/text file to post")
    p_mark_done.add_argument(
        "--remove-label",
        default="ready-for-sprint",
        help="Label to remove when marking Done (default: ready-for-sprint)",
    )

    args = parser.parse_args(argv)

    if args.cmd == "transition":
        transition_issue(args.issue_key, args.status)
        return 0

    if args.cmd == "comment":
        body_text = _read_text_arg(args)
        add_comment(args.issue_key, body_text)
        return 0

    if args.cmd == "complete":
        with open(args.file, "r", encoding="utf-8") as f:
            body = f.read().strip()
        add_comment(args.issue_key, body)
        transition_issue(args.issue_key, "Test")
        return 0

    if args.cmd == "done":
        with open(args.file, "r", encoding="utf-8") as f:
            body = f.read().strip()
        add_comment(args.issue_key, body)
        transition_issue(args.issue_key, "Done")
        try:
            update_labels(args.issue_key, remove=[args.remove_label])
            print(f"OK: removed label '{args.remove_label}' from {args.issue_key}")
        except Exception:
            # Non-fatal: label might not exist, or workflow user might not have edit permission.
            print(f"Note: could not remove label '{args.remove_label}' from {args.issue_key}")
        return 0

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
