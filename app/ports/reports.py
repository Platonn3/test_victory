from typing import Protocol

from app.domain.entities import ReconciliationResult


class ReportExporter(Protocol):
    def export(self, result: ReconciliationResult) -> bytes: ...


class ReportStore(Protocol):
    def put(self, report: bytes) -> str: ...

    def get(self, report_id: str) -> bytes | None: ...
