import json
import logging
import re
from datetime import datetime, UTC

from config import APP_ENV

_SENSITIVE_QS_RE = re.compile(r'([?&])(token|reset_token|verify_token|session|api_key|password)=[^&\s]*', re.IGNORECASE)


def _sanitize_log_message(message: str) -> str:
    return _SENSITIVE_QS_RE.sub(r'\1\2=[REDACTED]', message)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": _sanitize_log_message(record.getMessage()),
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


class SanitizingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.msg = _sanitize_log_message(str(record.msg))
        return super().format(record)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    if not root.handlers:
        handler = logging.StreamHandler()
        root.addHandler(handler)

    formatter = JsonFormatter() if APP_ENV == "production" else SanitizingFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    for handler in root.handlers:
        handler.setFormatter(formatter)
