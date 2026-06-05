"""Verify Jira status gating for evidence-backed tickets.

Rule enforced:
- If an evidence file exists at evidence/<ISSUE_KEY>.md, then the Jira issue must be in status
    "Test" (waiting for human verification) OR "Done" *only* if the evidence contains a reviewer
    sign-off line.

Reviewer sign-off convention (simple, grep-friendly):
- The evidence file must contain a line that starts with:
    Reviewer sign-off:
  and it must not be empty.

This script is intended to run in CI (GitHub Actions). It uses the Jira REST API.

Environment:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN

Exit codes:
- 0: all good
- 2: missing env vars
- 3: Jira API error
- 4: gate violation(s)
"""

import base64
import glob
import json
import os
import pathlib
import re
import ssl
import sys
import urllib.error
import urllib.request

import certifi

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.jira.env import load_dotenv  # noqa: E402

load_dotenv()

REVIEWER_RE = re.compile(r"^Reviewer sign-off \(fill when verified\):\s*(.+)$", re.MULTILINE)


def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"Missing required env var: {name}")
        raise SystemExit(2)
    return v


def _auth_header(email: str, token: str) -> str:
    raw = f"{email}:{token}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("utf-8")


def jira_get_issue(issue_key: str) -> dict:
    base = _env("JIRA_BASE_URL").rstrip("/")
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")

    url = f"{base}/rest/api/3/issue/{issue_key}?fields=status"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": _auth_header(email, token),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8")
        print(f"Jira API failed for {issue_key}: HTTP {e.code} {e.reason}\n{msg}")
        raise SystemExit(3)


def extract_issue_key(path: str) -> str | None:
    # evidence/BAN-6.md -> BAN-6
    base = os.path.basename(path)
    if not base.endswith(".md"):
        return None
    key = base[: -len(".md")]
    if re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", key):
        return key
    return None


def evidence_has_signoff(text: str) -> bool:
    m = REVIEWER_RE.search(text)
    if not m:
        return False
    value = (m.group(1) or "").strip()
    return bool(value and value != "<name/date>")


def main() -> int:
    evidence_files = sorted(glob.glob("evidence/*.md"))

    # Ignore the template + readme
    evidence_files = [
        p
        for p in evidence_files
        if os.path.basename(p)
        not in {
            "TICKET_COMMENT_TEMPLATE.md",
            "README.md",
        }
    ]

    if not evidence_files:
        print("No evidence files found; gate check skipped.")
        return 0

    # Local developer convenience: if Jira env vars aren't configured, skip.
    # In CI, these are expected to be set.
    if not (os.getenv("JIRA_BASE_URL") and os.getenv("JIRA_EMAIL") and os.getenv("JIRA_API_TOKEN")):
        print("Jira env vars not set; gate check skipped.")
        return 0

    violations: list[str] = []

    for path in evidence_files:
        issue_key = extract_issue_key(path)
        if not issue_key:
            continue

        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        has_signoff = evidence_has_signoff(text)

        issue = jira_get_issue(issue_key)
        status = issue.get("fields", {}).get("status", {}).get("name")

        if status == "Test":
            continue

        if status == "Done" and has_signoff:
            continue

        if status == "Done" and not has_signoff:
            violations.append(
                f"{issue_key}: status is 'Done' but evidence has NO reviewer sign-off. "
                "Required flow is In Progress -> Test (wait for verification) -> Done "
                "(after sign-off)."
            )
            continue

        violations.append(
            f"{issue_key}: evidence exists but status is '{status}'. "
            "Required: Test (or Done with sign-off)."
        )

    if violations:
        print("Test gate violations found:")
        for v in violations:
            print(f"- {v}")
        return 4

    print("OK: all evidence-backed issues are correctly gated (Test or Done+sign-off).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
