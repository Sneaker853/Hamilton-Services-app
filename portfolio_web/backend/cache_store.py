import threading
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        now = time.time()
        with self._lock:
            value = self._store.get(key)
            if not value:
                return None

            expires_at, payload = value
            if now >= expires_at:
                self._store.pop(key, None)
                return None

            return payload

    def set(self, key: str, payload: Any) -> None:
        with self._lock:
            self._store[key] = (time.time() + self.ttl_seconds, payload)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [key for key in self._store.keys() if key.startswith(prefix)]
            for key in keys:
                self._store.pop(key, None)
