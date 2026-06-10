"""
统一日志模块 — 所有模块共享的日志配置。
用法: from app.services.logger import get_logger
      logger = get_logger(__name__)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_console = logging.StreamHandler(sys.stdout)
_console.setLevel(logging.INFO)
_console.setFormatter(logging.Formatter(_FORMAT, _DATE_FMT))

_file = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
_file.setLevel(logging.DEBUG)
_file.setFormatter(logging.Formatter(_FORMAT, _DATE_FMT))


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        logger.addHandler(_console)
        logger.addHandler(_file)
        logger.propagate = False
    return logger
