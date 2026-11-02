import json, logging, os
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
    path=Path(os.getenv("WEALTH_ORBIT_LOG_FILE","logs.json")); path.parent.mkdir(parents=True,exist_ok=True); h=logging.FileHandler(path,encoding="utf-8"); h.setFormatter(JsonFormatter()); root=logging.getLogger(); root.setLevel(logging.INFO)
    if not any(isinstance(x,logging.FileHandler) and x.baseFilename==str(path.resolve()) for x in root.handlers): root.addHandler(h)
