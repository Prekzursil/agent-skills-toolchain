"""Tiny unittest run under the declared floor interpreter."""
import unittest

import at_floor


class FloorTests(unittest.TestCase):
    def test_add(self):
        self.assertEqual(at_floor.add(2, 3), 5)

    def test_main(self):
        self.assertEqual(at_floor.main(), 11)


if __name__ == "__main__":
    unittest.main()
