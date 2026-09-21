import re

_INVOICE_REFERENCE = re.compile(
    r"(?ix)\b(?:сч(?:[её]т(?:у|а|ом)?|\.)?|inv)\s*[-№]?\s*"
    r"(?P<numbers>\d+(?:\s*(?:,|и)\s*\d+)*)"
)
_INVOICE_SEPARATOR = re.compile(r"\s*(?:,|и)\s*", re.IGNORECASE)


def extract_invoice_numbers(purpose: str) -> tuple[str, ...]:
    numbers = (
        number
        for match in _INVOICE_REFERENCE.finditer(purpose)
        for number in _INVOICE_SEPARATOR.split(match.group("numbers"))
    )
    return tuple(dict.fromkeys(number for number in numbers if number))
