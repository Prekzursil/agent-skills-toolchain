"""No wall clock, no entropy, anywhere in the dispatch path — enforced by a static check.

Regression row R8: two runs of the same spec must produce identical artifacts. The check runs
over THIS package's own source, and the detector is validated against a known-broken fixture
for every forbidden form before its silence on the real tree is trusted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import agentspec
from agentspec.determinism import (
    FORBIDDEN_MODULES,
    FORBIDDEN_NAMES,
    Finding,
    scan_package,
    scan_source,
)

PACKAGE_ROOT = Path(agentspec.__file__).resolve().parent


def test_the_forbidden_sets_are_declared_sorted_and_closed() -> None:
    assert FORBIDDEN_MODULES == ("datetime", "random", "secrets", "time", "uuid")
    assert FORBIDDEN_NAMES == (
        "getrandbits",
        "monotonic",
        "monotonic_ns",
        "perf_counter",
        "perf_counter_ns",
        "time_ns",
        "urandom",
        "utcnow",
        "uuid1",
        "uuid3",
        "uuid4",
        "uuid5",
    )


def test_this_package_is_free_of_time_and_randomness() -> None:
    """The load-bearing assertion. Trustworthy only because of the controls below."""
    findings = scan_package(PACKAGE_ROOT)
    assert findings == (), [f"{f.path}:{f.line} {f.code} {f.detail}" for f in findings]


def test_the_scan_actually_visited_files() -> None:
    """Guard against a vacuous green: an empty walk would also report zero findings."""
    from agentspec.determinism import package_files

    visited = package_files(PACKAGE_ROOT)
    assert len(visited) >= 12
    assert any(p.name == "oracle.py" for p in visited)


# --- detector controls: the check must FIRE on each known-broken form ----------------------

BROKEN: dict[str, str] = {
    "import time": "import time\n",
    "import time aliased": "import time as t\n",
    "import random": "import random\n",
    "import secrets": "import secrets\n",
    "import uuid": "import uuid\n",
    "from datetime import": "from datetime import datetime\n",
    "from submodule": "import datetime.timezone\n",
    "from os import urandom": "from os import urandom\n",
    "os.urandom call": "import os\nx = os.urandom(8)\n",
    "bare urandom call": "def f(urandom):\n    return urandom(8)\n",
    "perf_counter call": "import os\nx = os.perf_counter()\n",
    "utcnow call": "def f(d):\n    return d.utcnow()\n",
}


@pytest.mark.parametrize("label", sorted(BROKEN))
def test_the_detector_fires_on_each_broken_form(label: str) -> None:
    findings = scan_source(BROKEN[label], "fixture.py")
    assert findings, f"detector stayed SILENT on {label!r} — it measures nothing"
    assert all(f.path == "fixture.py" for f in findings)
    assert all(f.line >= 1 for f in findings)


def test_the_detector_is_silent_on_an_equivalent_clean_module() -> None:
    """The other half of the both-states test."""
    clean = (
        "from __future__ import annotations\n"
        "import json\n"
        "import re\n"
        "from agentspec.clock import Clock\n"
        "def run(clock: Clock) -> int:\n"
        "    return clock.now_ms() + len(json.dumps({}))\n"
    )
    assert scan_source(clean, "clean.py") == ()


def test_now_ms_on_an_injected_clock_is_not_flagged() -> None:
    """Detector control against over-reach: the injected port must stay usable."""
    assert scan_source("def f(clock):\n    return clock.now_ms()\n", "c.py") == ()


def test_a_call_through_a_subscript_is_not_flagged() -> None:
    """The callee is neither a Name nor an Attribute, so the name resolver falls through."""
    assert scan_source("def f(handlers):\n    return handlers[0]()\n", "c.py") == ()


def test_an_immediately_invoked_lambda_is_not_flagged() -> None:
    assert scan_source("x = (lambda: 1)()\n", "c.py") == ()


def test_an_unparseable_module_is_reported_not_silently_skipped() -> None:
    findings = scan_source("def broken(:\n", "bad.py")
    assert [f.code for f in findings] == ["unparseable"]


def test_findings_are_frozen() -> None:
    import dataclasses

    with pytest.raises(dataclasses.FrozenInstanceError):
        Finding(path="p", line=1, code="c", detail="d").line = 2  # type: ignore[misc]


# --- scan_package ---------------------------------------------------------------------------


def test_scan_package_reports_a_bad_file_with_its_relative_path_and_line(
    tmp_path: Path,
) -> None:
    pkg = tmp_path / "pkg"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (pkg / "sub" / "bad.py").write_text("y = 2\nimport random\n", encoding="utf-8")
    findings = scan_package(pkg)
    assert len(findings) == 1
    assert findings[0].path == "sub/bad.py"
    assert findings[0].line == 2
    assert findings[0].code == "forbidden-import"


def test_scan_package_reports_an_undecodable_file_as_a_read_error(tmp_path: Path) -> None:
    """A file the scanner cannot read is a DETECTOR failure, never a pass."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "raw.py").write_bytes(b"\xff\xfe\x00bad")
    findings = scan_package(pkg)
    assert [f.code for f in findings] == ["read-error"]


def test_scan_package_on_an_empty_tree_reports_nothing_and_visits_nothing(
    tmp_path: Path,
) -> None:
    from agentspec.determinism import package_files

    assert scan_package(tmp_path) == ()
    assert package_files(tmp_path) == ()


def test_scan_package_ignores_non_python_files(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("import random\n", encoding="utf-8")
    assert scan_package(tmp_path) == ()


def test_findings_are_ordered_by_path_then_line(tmp_path: Path) -> None:
    (tmp_path / "b.py").write_text("import random\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("x = 1\nimport time\nimport secrets\n", encoding="utf-8")
    findings = scan_package(tmp_path)
    assert [(f.path, f.line) for f in findings] == [("a.py", 2), ("a.py", 3), ("b.py", 1)]
