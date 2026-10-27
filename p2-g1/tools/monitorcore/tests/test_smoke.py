"""Scaffold smoke test.

Guarantees the package imports AND that the coverage lane collects at least one
test: an empty package with zero tests makes ``pytest`` exit 5 ("no tests ran"),
which fails ``gate-tests-coverage monitorcore`` BEFORE coverage is even measured.
As real modules land (WU2+) this stays as the package-level import guard.
"""

import monitorcore


def test_package_imports() -> None:
    assert monitorcore.__version__ == "0.1.0"
