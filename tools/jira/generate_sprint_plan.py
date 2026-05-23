#!/usr/bin/env python3
"""Generate a markdown sprint plan from normalized Jira issues JSON.

Inputs:
- --in tools/jira/issues.json (default)
- --out SPRINT_PLAN.md (default)

Exit codes:
- 0 success
- 2 usage/config errors
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys


def _eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def _plain_text_from_html(html: str) -> str:
    # Very small sanitizer. Jira's renderedFields.description is HTML.
    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</\s*p\s*>", "\n\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    # Unescape common entities (keep it tiny; avoid extra deps)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return text.strip()


def _pick_description(issue: dict) -> str:
    rendered = issue.get("rendered_description")
    if isinstance(rendered, str) and rendered.strip():
        return _plain_text_from_html(rendered)

    desc = issue.get("description")
    if isinstance(desc, str):
        return desc.strip()

    return ""


def _shorten(text: str, max_chars: int = 700) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="tools/jira/issues.json")
    ap.add_argument("--out", dest="out", default="SPRINT_PLAN.md")
    args = ap.parse_args()

    try:
        with open(args.inp, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        _eprint(f"Input not found: {args.inp}")
        return 2

    issues = payload.get("issues") or []
    today = dt.date.today().isoformat()

    lines: list[str] = []
    lines.append(f"# Sprint Plan (generated {today})")
    lines.append("")
    lines.append("## Scope query")
    lines.append("")
    jql = (payload.get("jql") or "").strip()
    if jql:
        lines.append("```jql")
        lines.append(jql)
        lines.append("```")
    else:
        lines.append("(no JQL recorded)")
    lines.append("")

    lines.append("## Candidate issues")
    lines.append("")
    if not issues:
        lines.append("No issues returned by the query.")
    else:
        lines.append(f"Total returned: **{len(issues)}**")
        lines.append("")
        lines.append("| # | Key | Type | Priority | Status | Summary |")
        lines.append("|---:|---|---|---|---|---|")
        for idx, i in enumerate(issues, start=1):
            key = i.get("key") or ""
            url = i.get("url") or ""
            itype = i.get("issue_type") or ""
            prio = i.get("priority") or ""
            status = i.get("status") or ""
            summary = (i.get("summary") or "").replace("|", "\\|")
            kcell = f"[{key}]({url})" if (key and url) else key
            lines.append(f"| {idx} | {kcell} | {itype} | {prio} | {status} | {summary} |")

        lines.append("")
        lines.append("## Issue details (trimmed)")
        lines.append("")
        for i in issues:
            key = i.get("key") or ""
            url = i.get("url") or ""
            summary = i.get("summary") or ""
            lines.append(f"### {key}: {summary}")
            if url:
                lines.append("")
                lines.append(f"Link: {url}")
            lines.append("")
            meta = " / ".join(
                [
                    str(x)
                    for x in [
                        i.get("issue_type"),
                        i.get("priority"),
                        i.get("status"),
                    ]
                    if x
                ]
            )
            if meta:
                lines.append(f"**Meta:** {meta}")
                lines.append("")

            desc = _pick_description(i)
            if desc:
                lines.append("**Description (trimmed):**")
                lines.append("")
                lines.append("```text")
                lines.append(_shorten(desc))
                lines.append("```")
            else:
                lines.append("(No description)")
            lines.append("")

    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        f.write("\n")

    print(f"Wrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
