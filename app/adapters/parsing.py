from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.application.errors import ReconciliationError
from app.domain.money import as_money


def parse_money(value: object, field: str = "Сумма") -> Decimal:
    if value is None or value == "":
        raise ReconciliationError(f"Не заполнено поле «{field}»")
    if isinstance(value, bool):
        raise ReconciliationError(f"Некорректное значение поля «{field}»")
    raw = str(value).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return as_money(Decimal(raw))
    except InvalidOperation as exc:
        raise ReconciliationError(f"Некорректная сумма в поле «{field}»: {value}") from exc


def parse_date(value: object, field: str = "Дата") -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value.strip(), pattern).date()
            except ValueError:
                continue
    raise ReconciliationError(f"Некорректная дата в поле «{field}»: {value}")


def normalize_identifier(value: object, field: str) -> str:
    if value is None:
        raise ReconciliationError(f"Не заполнено поле «{field}»")
    if isinstance(value, bool):
        raise ReconciliationError(f"Некорректное значение поля «{field}»")
    if isinstance(value, float) and value.is_integer():
        normalized = str(int(value))
    else:
        normalized = str(value).strip()
    if not normalized:
        raise ReconciliationError(f"Не заполнено поле «{field}»")
    return normalized
