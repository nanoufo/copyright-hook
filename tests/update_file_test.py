import pytest

from copyrighthook.copyright import update_file
from copyrighthook.years_pattern import YearsPattern


@pytest.mark.parametrize(
    "content,expected,expected_ok,required",
    [
        ("abc", "abc", True, False),
        ("abc", "abc", False, True),
        ("# Test (c) 2023\nabc", "# Test (c) 2023\nabc", True, False),
        ("# Test (c) 2022\nabc", "# Test (c) 2022-2024\nabc", False, False),
        ("# Test (c) 2022-2023\nabc", "# Test (c) 2022-2023\nabc", True, False),
        ("# Test (c) 2021-2022\nabc", "# Test (c) 2021-2024\nabc", False, False),
        ("# Test (c) 2024-2024\nabc", "# Test (c) 2024\nabc", False, False),
        ("# Test (c) 2023-2023\nabc", "# Test (c) 2023-2024\nabc", False, False),
    ],
)
def test_update_file(content: str, expected: str, expected_ok: bool, required: bool):
    error_comment, new_content = update_file(
        content,
        last_year="2023",
        pattern=YearsPattern(r" Test (c) {years}"),
        required=required,
        current_year="2024",
    )
    assert (not error_comment) == expected_ok
    assert new_content == expected
