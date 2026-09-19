"""AUD-0052 probe support plugin: a real, seeded shuffle plugin plus recorders.

Registered into a pytest subprocess via `-p aud0052_plugin` (fixtures/ on PYTHONPATH).
Three responsibilities, deliberately kept in ONE plugin so hook ordering between
"shuffle" and "record final order" is never ambiguous:

1. --aud0052-seed=N: reorders the FULL collected item list with
   random.Random(N).shuffle(). This IS the "seeded shuffle plugin" the catalog names
   as an input. When the option is absent, collection order is untouched (declaration
   order), which is what probe2 (identical-order repeats) uses.
2. AUD0052_ORDER_PATH env var: writes the POST-shuffle collected node-id order, one
   per line. This is what the tests_required control reads to assert the recorded
   order actually differs between seeds -- proof the shuffle plugin did something,
   not just that it was invoked.
3. AUD0052_RESULTS_PATH env var: writes {nodeid: outcome} for every test's "call"
   phase to a JSON file, so probe1/probe2 can diff pass/fail across seeds/repeats
   without depending on an unlisted pytest-json-report package.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

_RESULTS: dict[str, str] = {}


def pytest_addoption(parser: object) -> None:
    parser.addoption(  # type: ignore[attr-defined]
        "--aud0052-seed",
        action="store",
        default=None,
        type=int,
        help="AUD-0052 probe: seed for a real full collected-item-list shuffle",
    )


def pytest_collection_modifyitems(config: object, items: list) -> None:  # type: ignore[type-arg]
    seed = config.getoption("--aud0052-seed")  # type: ignore[attr-defined]
    if seed is not None:
        rnd = random.Random(seed)
        shuffled = list(items)
        rnd.shuffle(shuffled)
        items[:] = shuffled
    order_path = os.environ.get("AUD0052_ORDER_PATH")
    if order_path:
        Path(order_path).write_text(
            "\n".join(i.nodeid for i in items) + "\n", encoding="utf-8"
        )


def pytest_runtest_logreport(report: object) -> None:
    if getattr(report, "when", None) != "call":
        return
    _RESULTS[report.nodeid] = report.outcome  # type: ignore[attr-defined]


def pytest_sessionfinish(session: object, exitstatus: object) -> None:
    out_path = os.environ.get("AUD0052_RESULTS_PATH")
    if out_path:
        Path(out_path).write_text(
            json.dumps(_RESULTS, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    _RESULTS.clear()
