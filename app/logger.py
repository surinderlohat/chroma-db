# Copyright (c) 2025 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import logging
import os
import sys

# ── Config ─────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()  # INFO | DEBUG | WARNING | ERROR
LOG_FORMAT = os.getenv("LOG_FORMAT", "text")  # text | json


class _JsonFormatter(logging.Formatter):
    """
    Outputs each log record as a single JSON line — ideal for log aggregators
    like Datadog, Loki, CloudWatch, or ELK stack.
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


class _TextFormatter(logging.Formatter):
    """
    Human-readable colored output for local development.
    Colors are stripped automatically when output is not a TTY (e.g. Docker logs).
    """

    COLORS = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        if sys.stdout.isatty():
            color = self.COLORS.get(record.levelname, "")
            return f"{color}{msg}{self.RESET}"
        return msg


def _build_formatter() -> logging.Formatter:
    if LOG_FORMAT == "json":
        return _JsonFormatter()
    return _TextFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _setup_root_logger() -> None:
    """Configure the root logger once at import time."""
    level = getattr(logging, LOG_LEVEL, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_build_formatter())

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if module is reloaded
    if not root.handlers:
        root.addHandler(handler)

    # Suppress noisy third-party loggers unless DEBUG
    if level > logging.DEBUG:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
        logging.getLogger("chromadb").setLevel(logging.WARNING)

    # ChromaDB posthog telemetry has a bug — spams ERROR logs even when
    # anonymized_telemetry=False is set. Silence it unconditionally at all
    # log levels including DEBUG since it is never useful output.
    logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)


_setup_root_logger()


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger. Use this in every module:

        from app.logger import get_logger
        logger = get_logger(__name__)
    """
    return logging.getLogger(name)
