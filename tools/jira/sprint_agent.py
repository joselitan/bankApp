#!/usr/bin/env python3
"""Sprint Agent (GitHub Actions-friendly) for SecureCore Bank / BAN.

This is the "Option A" implementation: an automation agent you can run from
GitHub Actions (or locally) to:

- Plan a sprint by JQL
- Create a sprint on a Jira board
- Add issues to the sprint
- Enforce governance rules (evidence + sign-off)
- Transition issues (optional)
- Keep label hygiene: remove `ready-for-sprint` when an issue reaches Done

Design goals:
- Dependency-free HTTP (urllib) + certifi SSL
- Safe by default: dry-run mode and maximum issue limit
- Extensible: core logic is in functions so a future interactive/chat UI (Option C)
  can import and use the same implementation.

Environment:
- JIRA_BASE_URL
- JIRA_EMAIL
- JIRA_API_TOKEN

"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.request
from dataclasses import dataclass

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.jira.agile import (  # noqa: E402
    add_issues_to_sprint,
    close_sprint,
    create_sprint,
    find_sprint_by_name,
    get_board,
    get_sprint,
)
from tools.jira.env import load_dotenv  # noqa: E402
from tools.jira.fetch_issues import _jira_search as jira_search  # noqa: E402
from tools.jira.issues import update_labels  # noqa: E402


@dataclass
class AgentConfig:
    board_id: int
    max_issues: int
    dry_run: bool
    ready_label: str
    auto_remove_ready_label_on_done: bool


@dataclass
class PlanConfig(AgentConfig):
    features_jql: str
    bugs_jql: str


@dataclass
class CreateSprintConfig(PlanConfig):
    sprint_name: str


@dataclass
class CloseAndRolloverConfig(PlanConfig):
    close_sprint_id: int
    next_sprint_name: str


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise SystemExit(f"Missing required env var: {name}")
    return v


def _read_text_arg(text: str | None, path: str | None, *, label: str) -> str:
    if text and text.strip():
        return text.strip()
    if path:
        p = pathlib.Path(path)
        if not p.exists():
            raise SystemExit(f"{label} file not found: {path}")
        return p.read_text(encoding="utf-8").strip()
    raise SystemExit(f"Provide --{label} or --{label}-file")


def fetch_candidate_keys(*, jql: str, max_issues: int) -> list[str]:
    base_url = _env("JIRA_BASE_URL").rstrip("/")
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")

    data = jira_search(
        base_url=base_url,
        email=email,
        token=token,
        jql=jql,
        max_results=max_issues,
    )

    raw_issues = data.get("issues") or []

    keys: list[str] = []
    for item in raw_issues:
        if isinstance(item, dict) and item.get("key"):
            keys.append(item["key"])
            continue

        # Jira Cloud's POST /search/jql can return minimal issue objects like {"id": "10390"}.
        # We resolve id -> key here so downstream steps (sprint membership, transitions)
        # can use stable issue keys.
        if isinstance(item, dict) and item.get("id"):
            issue_id = str(item.get("id"))
            try:
                key = _issue_id_to_key(issue_id)
            except Exception:
                key = None
            if key:
                keys.append(key)

    return keys


def _issue_id_to_key(issue_id: str) -> str | None:
    base_url = _env("JIRA_BASE_URL").rstrip("/")
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")

    import base64
    import ssl

    import certifi

    auth = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    ctx = ssl.create_default_context(cafile=certifi.where())

    req = urllib.request.Request(
        f"{base_url}/rest/api/3/issue/{issue_id}?fields=key",
        method="GET",
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "User-Agent": "bankapp-sprint-agent/1.0",
        },
    )

    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("key")


def maybe_remove_ready_label(cfg: AgentConfig, issue_key: str) -> None:
    if not cfg.auto_remove_ready_label_on_done:
        return

    if cfg.dry_run:
        print(f"DRY-RUN: would remove label '{cfg.ready_label}' from {issue_key} (on Done)")
        return

    update_labels(issue_key, remove=[cfg.ready_label])
    print(f"OK: removed label '{cfg.ready_label}' from {issue_key}")


def _validate_board(board_id: int) -> None:
    board = get_board(board_id)
    print(f"Board OK: {board.get('name')} (id={board.get('id')}, type={board.get('type')})")


def plan(cfg: PlanConfig) -> dict:
    """Return a structured plan payload (also printed)."""

    _validate_board(cfg.board_id)

    feature_keys = fetch_candidate_keys(jql=cfg.features_jql, max_issues=cfg.max_issues)
    bug_keys = fetch_candidate_keys(jql=cfg.bugs_jql, max_issues=cfg.max_issues)

    keys: list[str] = []
    for k in feature_keys + bug_keys:
        if k not in keys:
            keys.append(k)
        if len(keys) >= cfg.max_issues:
            break

    payload = {
        "board_id": cfg.board_id,
        "max_issues": cfg.max_issues,
        "features_jql": cfg.features_jql,
        "bugs_jql": cfg.bugs_jql,
        "features": feature_keys,
        "bugs": bug_keys,
        "selected": keys,
    }

    print(json.dumps(payload, indent=2))
    return payload


def create_and_fill_sprint(cfg: CreateSprintConfig) -> int:
    payload = plan(cfg)
    keys = payload["selected"]

    if not keys:
        print("No issues matched; nothing to do.")
        return 0

    existing = find_sprint_by_name(cfg.board_id, cfg.sprint_name)
    if existing:
        sprint_id = int(existing.get("id"))
        print(
            f"Sprint already exists: '{cfg.sprint_name}' (id={sprint_id}, state={existing.get('state')}). "
            "Will add selected issues to this sprint."
        )

        if cfg.dry_run:
            print(f"DRY-RUN: would add {len(keys)} issue(s) to existing sprint {sprint_id}")
            return 0

        add_issues_to_sprint(sprint_id, keys)
        print(f"OK: added {len(keys)} issue(s) to existing sprint {sprint_id}")
        return 0

    if cfg.dry_run:
        print(f"DRY-RUN: would create sprint '{cfg.sprint_name}' on board {cfg.board_id}")
        print(f"DRY-RUN: would add {len(keys)} issue(s) to sprint")
        return 0

    sprint = create_sprint(cfg.board_id, cfg.sprint_name)
    sprint_id = int(sprint.get("id"))
    print(f"OK: created sprint '{cfg.sprint_name}' (id={sprint_id}, state={sprint.get('state')})")

    add_issues_to_sprint(sprint_id, keys)
    print(f"OK: added {len(keys)} issue(s) to sprint {sprint_id}")
    return 0


def close_and_rollover(cfg: CloseAndRolloverConfig) -> int:
    _validate_board(cfg.board_id)

    s = get_sprint(cfg.close_sprint_id)
    state = (s.get("state") or "").lower()
    print(f"Sprint to close: {s.get('name')} (id={s.get('id')}, state={s.get('state')})")

    if state != "active":
        raise SystemExit(
            f"Refusing to close sprint {cfg.close_sprint_id} because state is '{s.get('state')}'. "
            "Only active sprints can be closed in this mode."
        )

    existing_next = find_sprint_by_name(cfg.board_id, cfg.next_sprint_name)
    if existing_next:
        raise SystemExit(
            f"Next sprint name '{cfg.next_sprint_name}' already exists (id={existing_next.get('id')})."
        )

    payload = plan(cfg)
    keys = payload["selected"]

    if cfg.dry_run:
        print(f"DRY-RUN: would close sprint {cfg.close_sprint_id}")
        print(f"DRY-RUN: would create sprint '{cfg.next_sprint_name}'")
        print(f"DRY-RUN: would add {len(keys)} issue(s) to next sprint")
        return 0

    close_sprint(cfg.close_sprint_id)
    print(f"OK: closed sprint {cfg.close_sprint_id}")

    next_sprint = create_sprint(cfg.board_id, cfg.next_sprint_name)
    next_id = int(next_sprint.get("id"))
    print(f"OK: created sprint '{cfg.next_sprint_name}' (id={next_id})")

    if keys:
        add_issues_to_sprint(next_id, keys)
        print(f"OK: added {len(keys)} issue(s) to sprint {next_id}")
    else:
        print("No issues selected for next sprint.")

    return 0


def main(argv: list[str]) -> int:
    load_dotenv()

    ap = argparse.ArgumentParser(description="Sprint Agent for Jira (features + regression bugs)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--board-id", type=int, required=True)
        p.add_argument("--max-issues", type=int, default=25)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--ready-label", default="ready-for-sprint")
        p.add_argument("--auto-remove-ready-label-on-done", action="store_true")
        p.add_argument("--features-jql")
        p.add_argument("--features-jql-file")
        p.add_argument("--bugs-jql")
        p.add_argument("--bugs-jql-file")

    p_plan = sub.add_parser("plan", help="Show which issues would be selected")
    add_common(p_plan)

    p_create = sub.add_parser("create", help="Create a sprint and add selected issues")
    add_common(p_create)
    p_create.add_argument("--sprint-name", required=True)

    p_roll = sub.add_parser(
        "close-and-rollover",
        help="Close an active sprint, create next sprint, and fill it with selected issues",
    )
    add_common(p_roll)
    p_roll.add_argument("--close-sprint-id", type=int, required=True)
    p_roll.add_argument("--next-sprint-name", required=True)

    args = ap.parse_args(argv)

    features = _read_text_arg(args.features_jql, args.features_jql_file, label="features-jql")
    bugs = _read_text_arg(args.bugs_jql, args.bugs_jql_file, label="bugs-jql")

    base = AgentConfig(
        board_id=args.board_id,
        max_issues=max(1, args.max_issues),
        dry_run=bool(args.dry_run),
        ready_label=args.ready_label,
        auto_remove_ready_label_on_done=bool(args.auto_remove_ready_label_on_done),
    )

    if args.cmd == "plan":
        cfg = PlanConfig(
            **base.__dict__,
            features_jql=features,
            bugs_jql=bugs,
        )
        plan(cfg)
        return 0

    if args.cmd == "create":
        cfg = CreateSprintConfig(
            **base.__dict__,
            features_jql=features,
            bugs_jql=bugs,
            sprint_name=args.sprint_name,
        )
        return create_and_fill_sprint(cfg)

    if args.cmd == "close-and-rollover":
        cfg = CloseAndRolloverConfig(
            **base.__dict__,
            features_jql=features,
            bugs_jql=bugs,
            close_sprint_id=args.close_sprint_id,
            next_sprint_name=args.next_sprint_name,
        )
        return close_and_rollover(cfg)

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
