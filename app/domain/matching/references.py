import re

_INVOICE_REFERENCE = re.compile(
    r"(?ix)\b(?:сч(?:[её]т(?:у|а|ом)?|\.)?|inv)\s*[-№]?\s*"
    r"(?P<numbers>\d+(?:\s*,\s*\d+)*)"
)


def extract_invoice_numbers(purpose: str) -> tuple[str, ...]:
    match = _INVOICE_REFERENCE.search(purpose)
    if match is None:
        return ()
    numbers = (part.strip() for part in match.group("numbers").split(","))
    return tuple(dict.fromkeys(number for number in numbers if number))
