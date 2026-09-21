from app.adapters.invoice_sources.excel import ExcelInvoiceSource
from app.adapters.payment_sources.bank_csv import BankCsvPaymentSource
from app.adapters.reports.excel import ExcelReportExporter
from app.adapters.reports.memory_store import InMemoryReportStore
from app.application.reconciliation import ReconciliationService
from app.domain.matching.engine import MatchingEngine
from app.domain.matching.rules import ExplicitInvoiceRule, InnAmountRule, MultipleInvoicesRule
from app.domain.validator import ReconciliationValidator
from app.ports.reports import ReportExporter, ReportStore
from app.ports.sources import InvoiceSource, PaymentSource

_report_store = InMemoryReportStore()


def get_payment_source() -> PaymentSource:
    return BankCsvPaymentSource()


def get_invoice_source() -> InvoiceSource:
    return ExcelInvoiceSource()


def get_reconciliation_service() -> ReconciliationService:
    matcher = MatchingEngine(
        (ExplicitInvoiceRule(), MultipleInvoicesRule(), InnAmountRule())
    )
    return ReconciliationService(matcher, ReconciliationValidator())


def get_report_exporter() -> ReportExporter:
    return ExcelReportExporter()


def get_report_store() -> ReportStore:
    return _report_store
