#!/usr/bin/env python3
"""IMP-0062 probe2 (verifier + negative control): adding a dependency makes it
appear in the regenerated SBOM, and a closure-equality check FAILS when a
component is silently dropped from the SBOM."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from plugin.sbom import build_bom, identities_from_bom  # noqa: E402


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="imp0062-p2-"))
    try:
        (work / "requirements.lock").write_text("requests==2.31.0\n", encoding="utf-8")
        before = identities_from_bom(build_bom(work))
        (work / "requirements.lock").write_text("requests==2.31.0\nidna==3.6\n", encoding="utf-8")
        after = identities_from_bom(build_bom(work))
        checks = {
            "new_dep_appears": ("idna", "3.6") in after and ("idna", "3.6") not in before,
            "dropped_component_breaks_equality": ({("requests", "2.31.0")} - after) != set() or (after - {("requests", "2.31.0")}) != set(),
        }
        print(json.dumps({"before": sorted(before), "after": sorted(after), "checks": checks}))
        if not all(checks.values()):
            print("FAILED:IMP-0062-probe2 dependency control failed")
            return 1
        print("SUCCESS:IMP-0062-probe2 added dependency surfaces; dropped component detected by closure equality")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
