import pytest

from maxinator_bot.app.services.code_generator import CodeGenerator


def test_patient_code_has_six_digits() -> None:
    code = CodeGenerator.patient_code()

    assert len(code) == 6
    assert code.isascii()
    assert code.isdigit()


def test_assignment_code_has_eight_digits() -> None:
    code = CodeGenerator.assignment_code()

    assert len(code) == 8
    assert code.isascii()
    assert code.isdigit()


@pytest.mark.parametrize(
    ("code", "length", "expected"),
    [
        ("012345", 6, True),
        ("12345678", 8, True),
        ("12345", 6, False),
        ("12 345", 6, False),
        ("12AB56", 6, False),
        ("１２３４５６", 6, False),
    ],
)
def test_code_format_validation(
    code: str,
    length: int,
    expected: bool,
) -> None:
    assert CodeGenerator.is_valid(code, length) is expected
