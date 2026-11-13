from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import logs_dir


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("rushes")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(
        logs_dir() / "rushes.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    return logger
