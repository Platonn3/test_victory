from decimal import Decimal
from pathlib import Path

from app.adapters.invoice_sources.excel import ExcelInvoiceSource
from app.adapters.payment_sources.bank_csv import BankCsvPaymentSource
from app.application.reconciliation import ReconciliationService
from app.domain.entities import InvoiceStatus, MatchReason
from app.domain.matching.engine import MatchingEngine
from app.domain.matching.rules import ExplicitInvoiceRule, InnAmountRule, MultipleInvoicesRule
from app.domain.validator import ReconciliationValidator


def test_provided_files_match_control_oracle(data_dir: Path) -> None:
    with (data_dir / "statement_2026_08.csv").open("rb") as statement:
        payment_batch = BankCsvPaymentSource().load(statement)
    with (data_dir / "invoices_2026_08.xlsx").open("rb") as registry:
        invoice_batch = ExcelInvoiceSource().load(registry)
    service = ReconciliationService(
        MatchingEngine((ExplicitInvoiceRule(), MultipleInvoicesRule(), InnAmountRule())),
        ReconciliationValidator(),
    )
    result = service.execute(payment_batch, invoice_batch)

    assert len(result.invoices) == 41
    assert result.total_invoice_amount == Decimal("7781624.50")
    assert result.total_income == Decimal("6346449.00")
    assert result.fully_paid_count == 32
    assert result.partially_paid_count == 2
    assert result.unpaid_count == 7
    assert result.total_allocated == Decimal("5906786.10")
    assert result.total_unallocated == Decimal("439662.90")
    assert result.total_outstanding == Decimal("1874838.40")
    assert result.total_allocated + result.total_unallocated == result.total_income
    assert len(result.duplicates) == 1
    assert result.duplicates[0].document_number == "412"

    invoice_results = {item.invoice.number: item for item in result.invoices}
    assert invoice_results["165"].outstanding_amount == Decimal("150.00")
    assert invoice_results["166"].outstanding_amount == Decimal("5000.00")
    unpaid = {
        number
        for number, item in invoice_results.items()
        if item.status is InvoiceStatus.UNPAID
    }
    assert unpaid == {"14", "146", "153", "170", "171", "178", "179"}

    unallocated = {item.payment.document_number: item for item in result.unallocated}
    assert unallocated["409"].reason is MatchReason.AMBIGUOUS
    assert unallocated["409"].candidate_invoices == ("170", "171")
    assert unallocated["411"].amount == Decimal("3000.00")
    assert unallocated["414"].amount == Decimal("66177.60")
    assert unallocated["416"].reason is MatchReason.INVOICE_NOT_FOUND
    assert unallocated["415"].reason is MatchReason.NO_MATCH
    assert invoice_results["172"].allocated_amount == Decimal("272787.85")
    assert any("ИНН плательщика" in warning for warning in result.warnings)
