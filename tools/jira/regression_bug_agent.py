#!/usr/bin/env python3
"""Regression Bug Agent.

This agent reads pytest results (JUnit XML) and files Jira Bug issues for
regressions, with de-duplication.

Why a separate agent?
- Different trigger: runs after regression test workflow finishes.
- Different inputs: Playwright artifacts.
- Keeps sprint planning focused.

High-level flow:
1) Parse pytest JUnit XML results.
2) For each failed test, build a *fingerprint*.
3) Search Jira for an existing bug with that fingerprint label.
4) If none exists, create a new Bug:
   - summary: "Regression: <test title>"
   - description: includes failing spec, error message, run URL, and optional artifacts
   - labels: ["regression", "autocreated", "regression-<fingerprint>"]

Environment:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN
- JIRA_PROJECT_KEY (default BAN)

Notes:
- This uses Jira's /rest/api/3 endpoints (issue create + JQL search).
- It's intentionally conservative: it won't create duplicates.

"""

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.jira.env import load_dotenv  # noqa: E402
from tools.jira.fetch_issues import _jira_search as jira_search  # noqa: E402


def _env(name: str, default: str | None = None) -> str:
    v = os.getenv(name)
    if v:
        return v
    if default is not None:
        return default
    raise SystemExit(f"Missing required env var: {name}")


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _load_junit_xml(path: str) -> ET.Element:
    p = pathlib.Path(path)
    if not p.exists():
        raise SystemExit(f"JUnit XML not found: {path}")
    return ET.fromstring(p.read_text(encoding="utf-8"))


def _extract_failures(junit_root: ET.Element) -> list[dict]:
    """Extract failures from JUnit XML.

    We support both layouts:
    - <testsuite> containing <testcase>
    - <testsuites> containing multiple <testsuite>

    Output records look like:
      {"title": "test_name", "file": "...", "error": "...", "classname": "..."}
    """

    failures: list[dict] = []

    # JUnit uses 'testcase' tags.
    for tc in junit_root.iter("testcase"):
        name = (tc.attrib.get("name") or "").strip()
        classname = (tc.attrib.get("classname") or "").strip()
        file = (tc.attrib.get("file") or "").strip()

        failure = tc.find("failure")
        error = tc.find("error")
        node = failure if failure is not None else error
        if node is None:
            continue

        msg = (node.attrib.get("message") or "").strip()
        text = (node.text or "").strip()
        combined = "\n".join([s for s in [msg, text] if s])

        title = name or classname or "(unknown test)"
        failures.append(
            {
                "title": title,
                "file": file,
                "classname": classname,
                "error": combined,
            }
        )

    return failures


def _jira_cfg() -> tuple[str, str, str, str]:
    base = _env("JIRA_BASE_URL").rstrip("/")
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")
    project = _env("JIRA_PROJECT_KEY", "BAN")
    return base, email, token, project


def _search_existing_bug(*, base: str, email: str, token: str, project: str, fingerprint: str) -> bool:
    jql = (
        f"project = {project} AND issuetype = Bug AND labels = regression-{fingerprint} "
        "ORDER BY created DESC"
    )
    data = jira_search(
        base_url=base,
        email=email,
        token=token,
        jql=jql,
        max_results=1,
    )
    issues = data.get("issues") or []
    return bool(issues)


def _create_bug_payload(
    project: str,
    title: str,
    file: str,
    classname: str,
    error: str,
    fingerprint: str,
    run_url: str | None,
) -> dict:
    summary = f"Regression: {title}"[:255]

    # Plain-text description; Jira will accept this in 'description' for many configs,
    # but if your Jira requires ADF we'll upgrade this to ADF shape.
    # (We already have ADF comment code in tools/jira/workflow.py.)
    lines = [
        "Regression detected by automation.",
        "",
        f"Test: {title}",
    ]
    if file:
        lines.append(f"File: {file}")
    if classname:
        lines.append(f"Classname: {classname}")
    if run_url:
        lines.append(f"Run: {run_url}")
    if error:
        lines.append("")
        lines.append("Error:")
        lines.append(error)

    desc = "\n".join(lines)

    return {
        "fields": {
            "project": {"key": project},
            "summary": summary,
            "issuetype": {"name": "Bug"},
            "description": desc,
            "labels": [
                "regression",
                "pytest-regression",
                "autocreated",
                f"regression-{fingerprint}",
            ],
        }
    }


def _jira_create_issue(payload: dict) -> dict:
    import base64
    import ssl
    import urllib.error
    import urllib.request

    import certifi

    import json

    base, email, token, _ = _jira_cfg()

    raw = f"{email}:{token}".encode("utf-8")
    auth = "Basic " + base64.b64encode(raw).decode("utf-8")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/rest/api/3/issue",
        data=data,
        method="POST",
        headers={
            "Authorization": auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "bankapp-regression-bug-agent/1.0",
        },
    )

    ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        with urllib.request.urlopen(req, timeout=45, context=ctx) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Jira issue create failed: HTTP {e.code} {e.reason}\n{msg}")


def main(argv: list[str]) -> int:
    load_dotenv()

    ap = argparse.ArgumentParser(description="Create Jira regression bugs from pytest JUnit failures")
    ap.add_argument("--junit-xml", required=True, help="Path to pytest JUnit XML results")
    ap.add_argument("--run-url", help="Optional GitHub Actions run URL")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    junit_root = _load_junit_xml(args.junit_xml)
    failures = _extract_failures(junit_root)

    if not failures:
        print("No failures found in Playwright JSON; nothing to file.")
        return 0

    base, email, token, project = _jira_cfg()

    created = 0
    skipped = 0

    for f in failures:
        fp = _fingerprint(f"{f.get('title','')}|{f.get('file','')}|{f.get('classname','')}")
        if _search_existing_bug(base=base, email=email, token=token, project=project, fingerprint=fp):
            skipped += 1
            print(f"SKIP: existing regression bug already filed (fingerprint={fp}) for {f.get('title')}")
            continue

        payload = _create_bug_payload(
            project=project,
            title=f.get("title") or "(untitled)",
            file=f.get("file") or "",
            classname=f.get("classname") or "",
            error=f.get("error") or "",
            fingerprint=fp,
            run_url=args.run_url,
        )

        if args.dry_run:
            created += 1
            print(f"DRY-RUN: would create Bug for {f.get('title')} (fingerprint={fp})")
            continue

        out = _jira_create_issue(payload)
        key = out.get("key")
        created += 1
        print(f"OK: created Jira bug {key} for {f.get('title')} (fingerprint={fp})")

    print(f"Summary: created={created}, skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
