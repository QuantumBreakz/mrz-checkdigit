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
