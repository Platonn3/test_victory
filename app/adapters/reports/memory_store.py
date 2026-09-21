import threading
import time
import uuid
from collections import OrderedDict


class InMemoryReportStore:
    def __init__(self, ttl_seconds: int = 900, max_reports: int = 32) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_reports = max_reports
        self._reports: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, report: bytes) -> str:
        report_id = uuid.uuid4().hex
        with self._lock:
            self._purge_expired()
            self._reports[report_id] = (time.monotonic() + self._ttl_seconds, report)
            while len(self._reports) > self._max_reports:
                self._reports.popitem(last=False)
        return report_id

    def get(self, report_id: str) -> bytes | None:
        with self._lock:
            self._purge_expired()
            item = self._reports.get(report_id)
            if item is None:
                return None
            return item[1]

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, (deadline, _) in self._reports.items() if deadline <= now]
        for key in expired:
            del self._reports[key]
