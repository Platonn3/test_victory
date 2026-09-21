import threading
import time
import uuid
from collections import OrderedDict

from app.ports.reports import ReportTooLargeError

DEFAULT_MAX_TOTAL_BYTES = 64 * 1024 * 1024


class InMemoryReportStore:
    def __init__(
        self,
        ttl_seconds: int = 900,
        max_reports: int = 32,
        max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES,
    ) -> None:
        if max_reports < 1:
            raise ValueError("max_reports must be positive")
        if max_total_bytes < 1:
            raise ValueError("max_total_bytes must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_reports = max_reports
        self._max_total_bytes = max_total_bytes
        self._total_bytes = 0
        self._reports: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, report: bytes) -> str:
        if len(report) > self._max_total_bytes:
            raise ReportTooLargeError(
                "Сформированный отчёт превышает допустимый размер"
            )
        report_id = uuid.uuid4().hex
        with self._lock:
            self._purge_expired()
            self._reports[report_id] = (time.monotonic() + self._ttl_seconds, report)
            self._total_bytes += len(report)
            while (
                len(self._reports) > self._max_reports
                or self._total_bytes > self._max_total_bytes
            ):
                _, (_, removed_report) = self._reports.popitem(last=False)
                self._total_bytes -= len(removed_report)
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
            _, report = self._reports.pop(key)
            self._total_bytes -= len(report)
