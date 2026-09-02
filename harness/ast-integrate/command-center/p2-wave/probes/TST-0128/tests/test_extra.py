"""Tests that import the packaging-sensitive module.

A planted install that omits tst0128pkg/extra.py cannot collect this file.
"""

from tst0128pkg.extra import secret


def test_secret():
    assert secret() == "tst0128-packaged-extra"
