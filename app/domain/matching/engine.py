from collections.abc import Sequence

from app.domain.entities import Invoice, MatchReason, MatchResult, Payment
from app.domain.matching.rules import MatchingContext, MatchingRule


class MatchingEngine:
    def __init__(self, rules: Sequence[MatchingRule]) -> None:
        self._rules = tuple(rules)

    def match_all(
        self, payments: Sequence[Payment], invoices: Sequence[Invoice]
    ) -> tuple[MatchResult, ...]:
        context = MatchingContext(
            invoices={invoice.number: invoice for invoice in invoices},
            outstanding={invoice.number: invoice.amount for invoice in invoices},
        )
        results: list[MatchResult] = []
        for payment in payments:
            result = self._match(payment, invoices, context)
            for allocation in result.allocations:
                context.outstanding[allocation.invoice_number] -= allocation.amount
            results.append(result)
        return tuple(results)

    def _match(
        self,
        payment: Payment,
        invoices: Sequence[Invoice],
        context: MatchingContext,
    ) -> MatchResult:
        for rule in self._rules:
            result = rule.match(payment, invoices, context)
            if result is not None:
                return result
        return MatchResult(payment.id, (), payment.amount, MatchReason.NO_MATCH)
