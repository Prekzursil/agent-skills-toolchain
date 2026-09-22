# Known-good tests: real assertions over non-constant, non-mock subjects.
# Detector must stay silent (zero false positives).


def add(a: int, b: int) -> int:
    return a + b


def test_add_positive():
    assert add(2, 3) == 5


def test_add_zero():
    result = add(0, 7)
    assert result == 7


def test_add_raises_type_error():
    import pytest

    with pytest.raises(TypeError):
        add("x", 1)  # type: ignore[arg-type]


def test_mention_assert_in_string_but_also_real():
    note = "we talk about assert in prose"
    assert add(1, 1) == 2
    assert note.startswith("we")
