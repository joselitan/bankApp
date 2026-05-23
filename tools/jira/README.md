# Jira tools

This folder contains small scripts used by GitHub Actions.

## Sprint Orchestrator (Mode 1 / plan-only)

- `jql.txt`: the scope definition (edit this to control what enters the plan)
- `fetch_issues.py`: fetches issues using Jira REST API search and writes `issues.json`
- `generate_sprint_plan.py`: generates `SPRINT_PLAN.md` from `issues.json`

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
