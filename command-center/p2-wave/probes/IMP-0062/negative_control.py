#!/usr/bin/env python3
"""IMP-0062 NEGATIVE CONTROL: planted dependency must appear in regenerated SBOM."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import sbom as S  # noqa: E402

PROBE = Path(__file__).resolve().parent


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0062-neg-") as td:
        work = Path(td)
        shutil.copy2(REPO / "package-lock.json", work / "package-lock.json")
        lock = work / "package-lock.json"

        before = S.build_sbom(
            name="agent-skills-toolchain",
            version="0.1.0",
            npm_lockfiles=[lock],
            vendored_markers=[],
            repo=work,
            timestamp="2026-09-08T07:00:00Z",
        )
        silent_clean = "planted-dep" not in S.component_names(before)

        data = json.loads(lock.read_text(encoding="utf-8"))
        data["packages"]["node_modules/planted-dep"] = {
            "version": "0.0.1",
            "license": "MIT",
        }
        lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

        after = S.build_sbom(
            name="agent-skills-toolchain",
            version="0.1.0",
            npm_lockfiles=[lock],
            vendored_markers=[],
            repo=work,
            timestamp="2026-09-08T07:00:00Z",
        )
        appears = "planted-dep" in S.component_names(after)
        indep_sees = "planted-dep" in S.independent_npm_lockfile_names(lock)
        # Would-fail assertion if SBOM ignored the plant:
        would_fail_if_omitted = appears and indep_sees

        # Vendored unpinned tree without lockfile
        orphan = work / "vendor" / "orphan-tree"
        orphan.mkdir(parents=True)
        (orphan / "x.bin").write_bytes(b"\x00\x01")
        with_vendor = S.build_sbom(
            name="agent-skills-toolchain",
            version="0.1.0",
            npm_lockfiles=[lock],
            vendored_markers=["vendor/orphan-tree"],
            repo=work,
            timestamp="2026-09-08T07:00:00Z",
        )
        vendor_ok = "vendored:vendor/orphan-tree" in S.vendored_component_names(
            with_vendor
        )

        fired = silent_clean and would_fail_if_omitted and vendor_ok
        meas = {
            "negative_control_fired": fired,
            "silent_on_clean": silent_clean,
            "planted_appears_in_sbom": appears,
            "independent_sees_plant": indep_sees,
            "vendored_orphan_represented": vendor_ok,
            "would_fail_if_sbom_omitted_plant": would_fail_if_omitted,
        }
        (PROBE / "negative-control-measurement.json").write_text(
            json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        lines = [
            "NEGATIVE CONTROL: PLANTED DEPENDENCY + VENDORED ORPHAN",
            "NEG-BEGIN:IMP-0062",
            f"silent_on_clean={silent_clean}",
            f"planted_appears_in_sbom={appears}",
            f"independent_sees_plant={indep_sees}",
            f"vendored_orphan_represented={vendor_ok}",
            f"negative_control_fired={fired}",
            "NEG-COMPLETE:IMP-0062",
            "SUCCESS:IMP-0062-negative" if fired else "FAILED:IMP-0062-negative",
        ]
        raw = "\n".join(lines) + "\n"
        (PROBE / "negative-control.raw.txt").write_text(raw, encoding="utf-8")
        print(raw, end="")
        return 0 if fired else 1


if __name__ == "__main__":
    raise SystemExit(main())
