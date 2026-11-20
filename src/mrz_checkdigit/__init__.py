"""Validate ICAO 9303 machine-readable zone (MRZ) check digits.

Supports TD1 (ID cards, 3x30), TD2 (2x36) and TD3 (passports, 2x44).
Check digits catch OCR and transcription errors; they do not prove a
document is genuine.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from itertools import product
from typing import NamedTuple, Sequence

__all__ = [
    "CheckResult",
    "check_digit",
    "validate",
    "is_valid",
    "fix_numeric",
    "repair",
    "birth_date",
    "expiry_date",
    "main",
]
__version__ = "0.2.0"

_WEIGHTS = (7, 3, 1)


class CheckResult(NamedTuple):
    field: str
    data: str
    expected: str  # check character printed on the document
    computed: int

    @property
    def ok(self) -> bool:
        if self.expected == "<":
            # ICAO allows a filler instead of a digit when the field is all fillers.
            return set(self.data) <= {"<"}
        return self.expected == str(self.computed)


def _value(ch: str) -> int:
    if "0" <= ch <= "9":
        return ord(ch) - ord("0")
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A") + 10
    if ch == "<":
        return 0
    raise ValueError(f"invalid MRZ character: {ch!r}")


def check_digit(field: str) -> int:
    """Return the ICAO 9303 check digit (weights 7, 3, 1; A-Z = 10-35; '<' = 0)."""
    return sum(_value(ch) * _WEIGHTS[i % 3] for i, ch in enumerate(field)) % 10


def _check(name: str, data: str, expected: str) -> CheckResult:
    return CheckResult(name, data, expected, check_digit(data))


def validate(lines: Sequence[str]) -> list[CheckResult]:
    """Check every check digit in an MRZ. Layout is detected from the line shape."""
    lines = [line.strip().upper() for line in lines]
    shape = (len(lines), {len(line) for line in lines})
    if shape == (3, {30}):  # TD1
        l1, l2, _ = lines
        return [
            _check("document_number", l1[5:14], l1[14]),
            _check("birth_date", l2[0:6], l2[6]),
            _check("expiry_date", l2[8:14], l2[14]),
            _check("composite", l1[5:30] + l2[0:7] + l2[8:15] + l2[18:29], l2[29]),
        ]
    if shape == (2, {36}):  # TD2
        l2 = lines[1]
        return [
            _check("document_number", l2[0:9], l2[9]),
            _check("birth_date", l2[13:19], l2[19]),
            _check("expiry_date", l2[21:27], l2[27]),
            _check("composite", l2[0:10] + l2[13:20] + l2[21:35], l2[35]),
        ]
    if shape == (2, {44}):  # TD3
        l2 = lines[1]
        return [
            _check("document_number", l2[0:9], l2[9]),
            _check("birth_date", l2[13:19], l2[19]),
            _check("expiry_date", l2[21:27], l2[27]),
            _check("optional_data", l2[28:42], l2[42]),
            _check("composite", l2[0:10] + l2[13:20] + l2[21:43], l2[43]),
        ]
    raise ValueError(
        "unrecognised MRZ layout: expected 3 lines of 30 (TD1), "
        "2 of 36 (TD2) or 2 of 44 (TD3) characters"
    )


def is_valid(lines: Sequence[str]) -> bool:
    """True if every check digit in the MRZ matches."""
    return all(r.ok for r in validate(lines))


# Characters OCR commonly confuses in the OCR-B font.
_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6"}
_TO_LETTER = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B", "6": "G"}


def fix_numeric(field: str) -> str:
    """Map letters OCR misread in a digits-only field (dates, check digits) back to digits: '74O8I2' -> '740812'."""
    return "".join(_TO_DIGIT.get(ch, ch) for ch in field.upper())


def repair(field: str, printed_check: str, max_changes: int = 2) -> str | None:
    """Repair an OCR-misread alphanumeric field (such as a document number) using its check digit.

    Returns the field unchanged if it already passes, the single candidate that passes with the fewest
    confusable swaps, or None when no candidate or more than one equally good candidate exists. A single
    check digit lets about one wrong reading in ten pass, so ambiguous cases are refused rather than guessed.
    """
    field = field.upper()
    expected = fix_numeric(printed_check)
    if str(check_digit(field)) == expected:
        return field
    options = []
    for ch in field:
        alts = {ch}
        if ch in _TO_DIGIT:
            alts.add(_TO_DIGIT[ch])
        if ch in _TO_LETTER:
            alts.add(_TO_LETTER[ch])
        options.append(sorted(alts))
    best: dict[int, list[str]] = {}
    for candidate in product(*options):
        changes = sum(a != b for a, b in zip(candidate, field))
        if 0 < changes <= max_changes and str(check_digit("".join(candidate))) == expected:
            best.setdefault(changes, []).append("".join(candidate))
    if not best:
        return None
    fewest = best[min(best)]
    return fewest[0] if len(fewest) == 1 else None


def _dates(yymmdd: str, centuries: Sequence[int]) -> list[date]:
    yymmdd = fix_numeric(yymmdd)
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        raise ValueError(f"not a YYMMDD date: {yymmdd!r}")
    yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:])
    out = []
    for c in centuries:
        try:
            out.append(date(c + yy, mm, dd))
        except ValueError:  # e.g. 29 February in a century year that isn't a leap year
            pass
    if not out:
        raise ValueError(f"not a valid date: {yymmdd!r}")
    return out


def birth_date(yymmdd: str, today: date | None = None) -> date:
    """Date of birth from an MRZ YYMMDD field: this century unless that would be in the future.

    People born more than 100 years ago are read as infants; compare with the four-digit year
    in the document's visual zone when that matters.
    """
    today = today or date.today()
    century = today.year // 100 * 100
    candidates = [d for d in _dates(yymmdd, (century, century - 100)) if d <= today]
    if not candidates:
        raise ValueError(f"birth date in the future: {yymmdd!r}")
    return candidates[0]


def expiry_date(yymmdd: str, today: date | None = None) -> date:
    """Expiry date from an MRZ YYMMDD field: the century that puts it closest to today."""
    today = today or date.today()
    century = today.year // 100 * 100
    return min(_dates(yymmdd, (century - 100, century, century + 100)), key=lambda d: abs((d - today).days))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mrz-checkdigit",
        description="Validate ICAO 9303 MRZ check digits (TD1, TD2, TD3).",
    )
    parser.add_argument("lines", nargs="*", help="MRZ lines; read from stdin if omitted")
    args = parser.parse_args(argv)
    lines = args.lines or [line for line in sys.stdin.read().splitlines() if line.strip()]
    try:
        results = validate(lines)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for r in results:
        status = "ok  " if r.ok else "FAIL"
        print(f"{status} {r.field:<16} printed={r.expected} computed={r.computed}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
