import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """One JSON object per log line. Callers must not log personal data (CES §1.4)."""

    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)
