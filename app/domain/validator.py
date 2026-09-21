from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal

from app.domain.entities import Allocation, Invoice, MatchResult, Payment
from app.domain.money import ZERO


class InvariantViolation(RuntimeError):
    pass


class ReconciliationValidator:
    def validate(
        self,
        payments: Sequence[Payment],
        invoices: Sequence[Invoice],
        matches: Sequence[MatchResult],
    ) -> None:
        payment_by_id = {payment.id: payment for payment in payments}
        allocations = tuple(
            allocation for match in matches for allocation in match.allocations
        )
        self._validate_payments(payment_by_id, matches)
        self._validate_invoices(invoices, allocations)
        total_income = sum((payment.amount for payment in payments), ZERO)
        total_allocated = sum((item.amount for item in allocations), ZERO)
        total_unallocated = sum((match.unallocated_amount for match in matches), ZERO)
        if total_income != total_allocated + total_unallocated:
            raise InvariantViolation("Не сходится общий баланс поступлений")

    def _validate_payments(
        self, payment_by_id: dict[str, Payment], matches: Sequence[MatchResult]
    ) -> None:
        for match in matches:
            payment = payment_by_id[match.payment_id]
            allocated = sum((item.amount for item in match.allocations), ZERO)
            if payment.amount != allocated + match.unallocated_amount:
                raise InvariantViolation(
                    f"Не сходится распределение платежа {payment.document_number}"
                )

    def _validate_invoices(
        self, invoices: Sequence[Invoice], allocations: Sequence[Allocation]
    ) -> None:
        allocated_by_invoice: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for allocation in allocations:
            allocated_by_invoice[allocation.invoice_number] += allocation.amount
        for invoice in invoices:
            allocated = allocated_by_invoice[invoice.number]
            if allocated < ZERO or allocated > invoice.amount:
                raise InvariantViolation(
                    f"Распределение по счёту {invoice.number} выходит за допустимые границы"
                )
