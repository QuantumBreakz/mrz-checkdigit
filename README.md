# mrz-checkdigit

Validate the check digits in a passport or ID card **machine-readable zone (MRZ)**, as defined by ICAO Document 9303. Supports all three layouts:

| Layout | Used on                  | Shape              |
| ------ | ------------------------ | ------------------ |
| TD1    | ID cards                 | 3 lines × 30 chars |
| TD2    | Older ID cards, visas    | 2 lines × 36 chars |
| TD3    | Passports                | 2 lines × 44 chars |

It checks the document number, date of birth and expiry date digits, the TD3 optional-data digit, and the composite digit. Pure Python, no dependencies, typed.

Use it after OCR to reject or retry a misread MRZ (`0`/`O`, `8`/`B`, `1`/`I` and similar) before it reaches your database.

## Install

```bash
pip install mrz-checkdigit
```

## Usage

```python
from mrz_checkdigit import check_digit, is_valid, validate

mrz = [
    "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
    "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
]

is_valid(mrz)              # True
check_digit("L898902C3")   # 6

for r in validate(mrz):
    print(r.field, r.expected, r.computed, r.ok)
# document_number 6 6 True
# birth_date 2 2 True
# expiry_date 9 9 True
# optional_data 1 1 True
# composite 0 0 True
```

The layout is detected from the number and length of the lines. `validate` raises `ValueError` for any other shape.

### Command line

```bash
mrz-checkdigit 'P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<' 'L898902C36UTO7408122F1204159ZE184226B<<<<<10'
```

Lines can also be piped on stdin. Exit code is `0` when every digit matches, `1` when one fails, `2` for an unrecognised layout.

## The algorithm

Each character becomes a number (digits keep their value, `A`–`Z` = 10–35, `<` = 0), is multiplied by the repeating weights 7, 3, 1, and the check digit is the sum modulo 10.

## Background

The full walkthrough, with the field positions, the composite digit and why OCR pipelines depend on it: [How passport MRZ check digits work, with code to validate them](https://aliahmed.si/blog/passport-mrz-check-digits/).

Check digits catch accidental errors. They are not a security feature: anyone can compute valid digits. Proving a document is genuine takes authenticity checks or reading the signed NFC chip.

## Limitations

- TD1 document numbers longer than 9 characters (the overflow into the optional field) are not handled yet.
- Only check digits are validated; field formats (dates, country codes) are not.

## License

MIT
