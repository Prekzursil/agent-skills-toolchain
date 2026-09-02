"""Suite that covers check_size lines while never exercising min_bytes default.

Every check_size call passes min_bytes explicitly (the DEFAULT_MIN_BYTES shape).
scale() is invoked without factor so that default IS live.
"""

from __future__ import annotations

import unittest

from product import check_payload_floor, scale_by_factor


class TestCheckSizeAlwaysExplicit(unittest.TestCase):
    def test_ok_at_floor(self) -> None:
        self.assertTrue(check_payload_floor(b"x" * 1024, min_bytes=1024))

    def test_too_small_with_lower_floor(self) -> None:
        self.assertFalse(check_payload_floor(b"x" * 10, min_bytes=512))

    def test_type_guard(self) -> None:
        with self.assertRaises(TypeError):
            check_payload_floor("not-bytes", min_bytes=1)  # type: ignore[arg-type]


class TestScaleOmitsDefault(unittest.TestCase):
    def test_default_factor(self) -> None:
        self.assertEqual(scale_by_factor(3), 6)

    def test_explicit_factor_also_present(self) -> None:
        self.assertEqual(scale_by_factor(3, factor=2), 6)


if __name__ == "__main__":
    unittest.main()
