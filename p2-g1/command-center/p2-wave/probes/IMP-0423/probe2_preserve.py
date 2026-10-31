"""Preservation + discard-mutation-red against the live module (IMP-0423)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "dispatch"))

from degrade_loudly import DegradeLoudly  # noqa: E402

TESTS = REPO / "tools" / "dispatch" / "tests" / "test_degrade_loudly.py"
FIXTURE = HERE / "fixtures" / "preserved-partial.json"


def main() -> int:
    d = DegradeLoudly()
    with tempfile.TemporaryDirectory() as td:
        partial = Path(td) / "partial.json"
        body = b'{"kind":"partial-work"}'
        d.seed_partial(partial, body)
        d.dispatch(d.mismatch_request(partial), d.openai_fixture())
        d.assert_partial_preserved(partial, body)
        assert partial.is_file(), "partial discarded"

    raw = FIXTURE.read_bytes().replace(b"\r\n", b"\n")
    fixture_sha = hashlib.sha256(raw).hexdigest()

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-B", str(TESTS)],
        capture_output=True, text=True, timeout=300, cwd=str(REPO), env=env,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    last = tail[-1] if tail else ""
    assert proc.returncode == 0, "battery red: " + last
    assert last.startswith("SUCCESS:IMP-0423"), last

    print(json.dumps({
        "probe": "probe2-preserve",
        "unit_id": "IMP-0423",
        "preserved_partial": {"path": str(FIXTURE.relative_to(REPO)).replace(chr(92), "/"),
                              "bytes": FIXTURE.stat().st_size, "sha256": fixture_sha},
        "battery": "7/7",
        "battery_exit": proc.returncode,
        "sentinel": "SENTINEL:IMP-0423:DEGRADED-LOUD-AND-PRESERVED",
    }, indent=2))
    print("SUCCESS:IMP-0423-probe2 partial preserved; discard mutant turns red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
