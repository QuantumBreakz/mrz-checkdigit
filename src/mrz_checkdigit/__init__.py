"""Validate ICAO 9303 machine-readable zone (MRZ) check digits.

Supports TD1 (ID cards, 3x30), TD2 (2x36) and TD3 (passports, 2x44).
Check digits catch OCR and transcription errors; they do not prove a
document is genuine.
"""

from __future__ import annotations

import argparse
import sys
from typing import NamedTuple, Sequence

__all__ = ["CheckResult", "check_digit", "validate", "is_valid", "main"]
__version__ = "0.1.0"

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
