# Jira tools

This folder contains small scripts used by GitHub Actions.

## Sprint Orchestrator (Mode 1 / plan-only)

- `jql.txt`: the scope definition (edit this to control what enters the plan)
- `fetch_issues.py`: fetches issues using Jira REST API search and writes `issues.json`
- `generate_sprint_plan.py`: generates `SPRINT_PLAN.md` from `issues.json`

### Label gate (recommended)

This repo is set up to use an explicit label gate so only stories you mark as ready
are pulled into the plan.

- Label used: `ready-for-sprint`
- See: `tools/jira/jql.txt`

Helper:

- `label_ready_for_sprint.py BAN-6 BAN-7 ...`

### Modern Jira JQL endpoint helper

Atlassian is migrating search endpoints. If you need a direct call to the modern
JQL endpoint, use:

- `jira_search_jql.py --jql-file tools/jira/jql.txt --out tools/jira/raw_search.json`

### Local run (optional)

Set environment variables:

- `JIRA_BASE_URL`
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`

Then run:

```bash
python tools/jira/fetch_issues.py --max-results 10
python tools/jira/generate_sprint_plan.py
```

Notes:
- The scripts intentionally avoid printing any secrets.
- The workflow uploads `SPRINT_PLAN.md` + `issues.json` as build artifacts.
