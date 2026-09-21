import csv
import hashlib
import io
from datetime import date
from decimal import Decimal
from typing import BinaryIO

from app.adapters.parsing import parse_date, parse_money
from app.application.errors import ReconciliationError
from app.domain.entities import BankControlTotals, Expense, Payment, PaymentBatch


class BankCsvPaymentSource:
    REQUIRED_HEADERS = (
        "Дата",
        "Номер документа",
        "Списание",
        "Поступление",
        "Контрагент",
        "ИНН контрагента",
        "Назначение платежа",
    )

    def load(self, source: BinaryIO) -> PaymentBatch:
        data = source.read()
        text = self._decode(data)
        rows = list(csv.reader(io.StringIO(text), delimiter=";"))
        header_index = self._find_header(rows)
        metadata = self._metadata(rows[:header_index])
        payments: list[Payment] = []
        expenses: list[Expense] = []
        control_income: Decimal | None = None
        control_expenses: Decimal | None = None
        closing_balance: Decimal | None = None
        for line_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            if not row or not any(cell.strip() for cell in row):
                continue
            padded = row + [""] * (7 - len(row))
            if padded[0].strip() == "Обороты за период":
                control_expenses = parse_money(padded[2], "Списания за период")
                control_income = parse_money(padded[3], "Поступления за период")
                continue
            if padded[0].strip() == "Исходящий остаток":
                closing_balance = parse_money(padded[3], "Исходящий остаток")
                continue
            operation_date = parse_date(padded[0], f"Дата, строка {line_number}")
            document_number = padded[1].strip()
            if not document_number:
                raise ReconciliationError(f"Не указан номер документа в строке {line_number}")
            debit = parse_money(padded[2], "Списание") if padded[2].strip() else None
            credit = parse_money(padded[3], "Поступление") if padded[3].strip() else None
            if (debit is None) == (credit is None):
                raise ReconciliationError(
                    f"В строке {line_number} должно быть заполнено одно из полей: "
                    "списание или поступление"
                )
            fingerprint = self._fingerprint(operation_date, padded)
            if credit is not None:
                payments.append(
                    Payment(
                        id=fingerprint,
                        document_number=document_number,
                        date=operation_date,
                        payer_name=padded[4].strip(),
                        payer_inn=padded[5].strip() or None,
                        amount=credit,
                        purpose=padded[6].strip(),
                        fingerprint=fingerprint,
                    )
                )
            elif debit is not None:
                expenses.append(
                    Expense(document_number, operation_date, debit, fingerprint)
                )
        if not payments and not expenses:
            raise ReconciliationError("В банковской выписке нет операций")
        opening = metadata.get("Входящий остаток")
        opening_balance = parse_money(opening, "Входящий остаток") if opening else None
        return PaymentBatch(
            tuple(payments),
            tuple(expenses),
            BankControlTotals(
                opening_balance,
                control_income,
                control_expenses,
                closing_balance,
            ),
        )

    @staticmethod
    def _decode(data: bytes) -> str:
        for encoding in ("utf-8-sig", "cp1251"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ReconciliationError("Не удалось определить кодировку банковской выписки")

    def _find_header(self, rows: list[list[str]]) -> int:
        for index, row in enumerate(rows):
            normalized = tuple(cell.strip() for cell in row[: len(self.REQUIRED_HEADERS)])
            if normalized == self.REQUIRED_HEADERS:
                return index
        raise ReconciliationError("В банковской выписке не найдена таблица операций")

    @staticmethod
    def _metadata(rows: list[list[str]]) -> dict[str, str]:
        return {
            row[0].strip(): row[1].strip()
            for row in rows
            if len(row) >= 2 and row[0].strip()
        }

    @staticmethod
    def _fingerprint(operation_date: date, row: list[str]) -> str:
        normalized = "\x1f".join(
            [
                operation_date.isoformat(),
                row[1].strip(),
                row[2].replace("\u00a0", " ").strip(),
                row[3].replace("\u00a0", " ").strip(),
                row[4].strip(),
                row[5].strip(),
                row[6].strip(),
            ]
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
