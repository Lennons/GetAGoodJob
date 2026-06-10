"""Pytest fixtures for 工作通 tests."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture
def client():
    """FastAPI TestClient with file-based SQLite database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models import Base
    from app.config import DEFAULT_SETTINGS
    from app.models import Setting
    import app.database as db_module

    fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_wt_")
    os.close(fd)

    test_engine = create_engine(f"sqlite:///{db_path}", echo=False)
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=test_engine)

    sdb = TestSessionLocal()
    sdb.add(Setting(key="global", value=DEFAULT_SETTINGS.copy()))
    sdb.commit()
    sdb.close()

    _orig_engine = db_module.engine
    _orig_session = db_module.SessionLocal
    db_module.engine = test_engine
    db_module.SessionLocal = TestSessionLocal

    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    tc = TestClient(fastapi_app)

    yield tc

    db_module.engine = _orig_engine
    db_module.SessionLocal = _orig_session
    try:
        os.unlink(db_path)
    except OSError:
        pass
