from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import config as config_module
from app.db import session as session_module
from app.main import create_app


@contextmanager
def temp_db_url():
    # File-based sqlite so multiple connections share state.
    fd, path = tempfile.mkstemp(prefix="securecore_test_", suffix=".db")
    os.close(fd)
    try:
        yield f"sqlite:///{path}"
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


@pytest.fixture()
def client(monkeypatch):
    with temp_db_url() as url:
        monkeypatch.setattr(config_module.settings, "DATABASE_URL", url)

        # Recreate engine/sessionmaker against the temp DB.
        engine = create_engine(url, connect_args={"check_same_thread": False})
        session_module.engine = engine
        session_module.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        app = create_app()
        # Ensure startup ran
        with TestClient(app) as c:
            yield c
