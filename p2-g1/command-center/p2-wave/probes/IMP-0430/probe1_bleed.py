"""Probe 1: concurrent fixture sessions isolated; project mutant bleeds (IMP-0430)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from bleed import run_bleed  # noqa: E402
from fixtures import REPO, scan_store_dir  # noqa: E402
from session_keyed_store import ProjectKeyedMutant, SessionKeyedStore  # noqa: E402


def main() -> int:
    session = run_bleed(SessionKeyedStore)
    project = run_bleed(ProjectKeyedMutant)
    assert session["isolated"] is True, "session store bled: %r" % session
    assert project["bled"] is True, "project mutant failed to reproduce the bleed"

    repo_scan = scan_store_dir(REPO / "hooks")
    per_store_ok = {n: (i.get("key_shape") == "session")
                    for n, i in repo_scan.items() if i.get("present")}
    assert len(per_store_ok) == 4, "expected 4 repo stores, saw %r" % per_store_ok
    assert all(per_store_ok.values()), "non-session repo store: %r" % per_store_ok

    print("session isolated=%s bled=%s read_a=%s read_b=%s"
          % (session["isolated"], session["bled"], session["read_a"], session["read_b"]))
    print("project-mutant isolated=%s bled=%s read_a=%s read_b=%s"
          % (project["isolated"], project["bled"], project["read_a"], project["read_b"]))
    print("per_store_ok=%r" % per_store_ok)
    print("SUCCESS:IMP-0430-probe1 concurrent sessions isolated; project mutant bleeds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
