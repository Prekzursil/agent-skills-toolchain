"""In-package critical suite. Nodeids match tests/test_core.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

NODEIDS = [
    "tests/test_core.py::test_add",
    "tests/test_core.py::test_token",
    "tests/test_core.py::test_imported_from_real_file",
]


def _case_add() -> None:
    from tst0333_crit.core import add

    if add(2, 3) != 5:
        raise AssertionError("add(2, 3) != 5")


def _case_token() -> None:
    from tst0333_crit.core import PACKAGE_DATA_TOKEN

    if PACKAGE_DATA_TOKEN != "tst0333-packaged":
        raise AssertionError(PACKAGE_DATA_TOKEN)


def _case_file() -> None:
    import tst0333_crit

    if not Path(tst0333_crit.__file__).is_file():
        raise AssertionError("tst0333_crit.__file__ is not a real file")


CASES = [
    (NODEIDS[0], _case_add),
    (NODEIDS[1], _case_token),
    (NODEIDS[2], _case_file),
]


def run_suite(argv: list[str] | None = None) -> int:
    import tst0333_crit

    argv = list(sys.argv[1:] if argv is None else argv)
    rows: list[dict[str, Any]] = []
    for nodeid, fn in CASES:
        try:
            fn()
            rows.append({"nodeid": nodeid, "outcome": "passed"})
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "nodeid": nodeid,
                    "outcome": "failed",
                    "error": f"{type(exc).__name__}:{exc}",
                }
            )
    failed = sum(1 for r in rows if r["outcome"] != "passed")
    payload = {
        "collected": len(NODEIDS),
        "nodeids": list(NODEIDS),
        "passed": sum(1 for r in rows if r["outcome"] == "passed"),
        "failed": failed,
        "rows": rows,
        "import_file": tst0333_crit.__file__,
        "executable": sys.executable,
        "module": "tst0333_crit",
    }
    if "--collect-only" in argv:
        payload["collect_only"] = True
        print(json.dumps(payload, sort_keys=True))
        return 0
    print(json.dumps(payload, sort_keys=True))
    return 0 if failed == 0 else 1
