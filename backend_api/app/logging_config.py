import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record):
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False)


def configure_logging():
    path = Path(os.getenv("WEALTH_ORBIT_LOG_FILE", "logs.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    formatter = JsonFormatter()
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    file_path = str(path.resolve())
    if not any(
        isinstance(handler, logging.FileHandler) and getattr(handler, "baseFilename", None) == file_path
        for handler in root.handlers
    ):
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    if not any(isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler) for handler in root.handlers):
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)
