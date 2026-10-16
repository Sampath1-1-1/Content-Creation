"""Logging: short messages on screen, full detail in the run log file."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

_CONSOLE_FMT = "%(message)s"
_FILE_FMT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_file: Path | None = None, verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("studio")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT))
    logger.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(_FILE_FMT))
        logger.addHandler(fh)
    return logger


def get_logger(name: str = "studio") -> logging.Logger:
    return logging.getLogger(name if name.startswith("studio") else f"studio.{name}")
