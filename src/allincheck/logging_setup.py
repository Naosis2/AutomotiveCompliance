"""Structured JSON logging."""

from __future__ import annotations

import json
import logging
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as a JSON string.

        Args:
            record: The log record.

        Returns:
            A single-line JSON string.
        """
        data: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "ctx", None)
        if isinstance(extra, dict):
            data.update(extra)
        return json.dumps(data, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter on the root logger.

    Args:
        level: Minimum level to emit.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
