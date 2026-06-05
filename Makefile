.PHONY: test lint format run

VENV_PY := ./.venv-1/bin/python

# Run unit tests using the repo venv, without needing to activate it

test:
	$(VENV_PY) -m pytest -q

lint:
	$(VENV_PY) -m ruff check .

format:
	$(VENV_PY) -m ruff format .

run:
	$(VENV_PY) -m uvicorn app.main:app --reload
