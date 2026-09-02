"""Planted hermetic control: must not change outcome under egress block."""


def test_hermetic_arithmetic() -> None:
    if 1 + 1 != 2:
        raise AssertionError("arithmetic broken")
