import json
import logging
from datetime import datetime, UTC

from config import APP_ENV


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not root.handlers:
        handler = logging.StreamHandler()
        root.addHandler(handler)

    formatter = JsonFormatter() if APP_ENV == "production" else logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    for handler in root.handlers:
        handler.setFormatter(formatter)
