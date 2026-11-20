import pytest

from mrz_checkdigit import check_digit, is_valid, main, validate

# ICAO 9303 specimens (Parts 4, 5 and 6), fictional state "Utopia".
TD3 = [
    "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<",
    "L898902C36UTO7408122F1204159ZE184226B<<<<<10",
]
TD1 = [
    "I<UTOD231458907<<<<<<<<<<<<<<<",
    "7408122F1204159UTO<<<<<<<<<<<6",
    "ERIKSSON<<ANNA<MARIA<<<<<<<<<<",
]
TD2 = [
    "I<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<",
    "D231458907UTO7408122F1204159<<<<<<<6",
]


def test_check_digit_examples():
    assert check_digit("L898902C3") == 6
    assert check_digit("740812") == 2
    assert check_digit("120415") == 9
    assert check_digit("<<<<") == 0


@pytest.mark.parametrize("mrz", [TD1, TD2, TD3], ids=["TD1", "TD2", "TD3"])
def test_specimens_validate(mrz):
    results = validate(mrz)
    assert all(r.ok for r in results), results
    assert is_valid(mrz)


@pytest.mark.parametrize("mrz", [TD1, TD2, TD3], ids=["TD1", "TD2", "TD3"])
def test_ocr_misread_is_caught(mrz):
    # Classic OCR confusion: '0' read as 'O' in the date of birth.
    bad = [line.replace("740812", "74O812") for line in mrz]
    assert not is_valid(bad)


def test_filler_optional_check_digit():
    line2 = "L898902C36UTO7408122F1204159<<<<<<<<<<<<<<<0"
    line2 = line2[:42] + "<" + line2[43:]
    by_field = {r.field: r for r in validate([TD3[0], line2])}
    assert by_field["optional_data"].ok


def test_bad_layout():
    with pytest.raises(ValueError):
        validate(["P<UTO", "L898"])


def test_cli(capsys):
    assert main(TD3) == 0
    assert main([TD3[0], TD3[1].replace("L898", "L89B")]) == 1
    assert "FAIL document_number" in capsys.readouterr().out


# --- 0.2.0: OCR repair and dates -------------------------------------------------

from datetime import date

from mrz_checkdigit import birth_date, expiry_date, fix_numeric, repair


def test_fix_numeric():
    assert fix_numeric("74O8I2") == "740812"
    assert fix_numeric("12O4I5") == "120415"


def test_repair_keeps_valid_reading():
    # 'L898902C3' passes as read, even though other readings would pass too.
    assert repair("L898902C3", "6") == "L898902C3"


def test_repair_single_misread():
    assert repair("L8989O2C3", "6") == "L898902C3"


def test_repair_refuses_ambiguous():
    # Two different single-character repairs both satisfy the check digit.
    assert repair("AB5O8I23S", "0") is None


def test_repair_printed_check_misread():
    assert repair("L898902C3", "G") == "L898902C3"  # G read for 6


def test_birth_date_century():
    today = date(2026, 11, 18)
    assert birth_date("740812", today) == date(1974, 8, 12)
    assert birth_date("080305", today) == date(2008, 3, 5)
    assert birth_date("261231", today) == date(1926, 12, 31)


def test_expiry_date_century():
    today = date(2026, 11, 18)
    assert expiry_date("120415", today) == date(2012, 4, 15)
    assert expiry_date("350101", today) == date(2035, 1, 1)
    assert expiry_date("990101", today) == date(1999, 1, 1)


def test_leap_day_in_non_leap_century():
    # 29 Feb 2000 exists; 29 Feb 1900 doesn't, which must not crash the century search.
    assert birth_date("000229", date(2026, 1, 1)) == date(2000, 2, 29)
    assert expiry_date("000229", date(2026, 1, 1)) == date(2000, 2, 29)


def test_invalid_dates():
    with pytest.raises(ValueError):
        birth_date("741332", date(2026, 1, 1))
    with pytest.raises(ValueError):
        expiry_date("12345", date(2026, 1, 1))
