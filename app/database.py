from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings, DEFAULT_SETTINGS


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Seed default settings row on first run (avoids UNIQUE race on concurrent requests)
    from app.models import Setting
    from sqlalchemy import select

    with SessionLocal() as db:
        existing = db.execute(select(Setting).where(Setting.key == "global")).scalar_one_or_none()
        if not existing:
            db.add(Setting(key="global", value=DEFAULT_SETTINGS.copy()))
            db.commit()
