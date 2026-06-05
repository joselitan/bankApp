# SecureCore Bank — MVP (FastAPI)

This repo contains:
- Jira planning automation under `tools/jira/`
- Sprint documentation under `doc/`
- An API-first MVP backend under `app/`

## Backend: local dev

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Then open:
- Swagger UI: http://127.0.0.1:8000/docs

## Tests

```bash
pytest
```

## Notes

- Database: SQLite (file `securecore_bank.db` by default)
- Config via environment variables (see `app/core/config.py`)
