# Copyright (c) 2026 Surinder Singh (https://github.com/surinderlohat)
# Licensed under the MIT License. See LICENSE file in the project root.
from __future__ import annotations

import logging
from collections import deque

MAX_LOG_LINES = 200

# In-memory circular buffer — stores last N log lines
_log_buffer: deque[dict] = deque(maxlen=MAX_LOG_LINES)


class BufferHandler(logging.Handler):
    """Logging handler that appends records to the in-memory buffer."""

    def emit(self, record: logging.LogRecord) -> None:
        _log_buffer.append({
            "ts":      self.formatter.formatTime(record, "%Y-%m-%d %H:%M:%S") if self.formatter else "",
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        })


def get_logs() -> list[dict]:
    """Returns a copy of the current log buffer newest-first."""
    return list(reversed(_log_buffer))


def attach_buffer_handler() -> None:
    """Attach the buffer handler to the root logger once at startup."""
    handler = BufferHandler()
    handler.setFormatter(logging.Formatter())
    logging.getLogger().addHandler(handler)
