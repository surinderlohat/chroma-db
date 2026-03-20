# Copyright (c) 2025 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import os

import psutil

from app.logger import get_logger

logger = get_logger(__name__)

# Warn when usage crosses this — gives early heads-up before hitting Docker limit
MEMORY_WARN_MB = int(os.getenv("MEMORY_WARN_MB", "3500"))

# Refuse write operations above this — protects against OOM kill mid-write
MEMORY_LIMIT_MB = int(os.getenv("MEMORY_LIMIT_MB", "4000"))


def get_memory_mb() -> float:
    """Returns current process RSS memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / (1024 * 1024)


def check_memory_warn() -> float:
    """
    Logs a warning if memory usage exceeds MEMORY_WARN_MB.
    Returns current usage in MB.
    """
    usage_mb = get_memory_mb()
    if usage_mb >= MEMORY_WARN_MB:
        logger.warning(
            f"High memory usage: {usage_mb:.1f} MB (warn threshold: {MEMORY_WARN_MB} MB)"
        )
    else:
        logger.debug(f"Memory usage: {usage_mb:.1f} MB")
    return usage_mb


def check_memory_limit() -> None:
    """
    Raises MemoryError if memory usage exceeds MEMORY_LIMIT_MB.
    Call this before write operations to prevent OOM mid-write.
    """
    usage_mb = get_memory_mb()
    if usage_mb >= MEMORY_LIMIT_MB:
        logger.error(
            f"Memory limit exceeded: {usage_mb:.1f} MB "
            f"(limit: {MEMORY_LIMIT_MB} MB). Write operation rejected."
        )
        raise MemoryError(
            f"Service memory usage ({usage_mb:.1f} MB) has exceeded the "
            f"configured limit ({MEMORY_LIMIT_MB} MB). "
            f"Try again later or contact the administrator."
        )
