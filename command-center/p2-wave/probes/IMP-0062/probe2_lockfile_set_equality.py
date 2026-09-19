#!/usr/bin/env python3
"""IMP-0062 probe2: independent lockfile parse set-equality vs SBOM names."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import sbom as S  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) the SBOM validates against the CycloneDX schema; "
    "(2) its component count and names are cross-checked against an independent "
    "lockfile parse, requiring set equality."
)


def main() -> int:
    lock = REPO / "package-lock.json"
    # Builder path
    doc = S.build_sbom(
        name="agent-skills-toolchain",
        version="0.1.0",
        npm_lockfiles=[lock],
        vendored_markers=["tools/editor/ralph-orchestrator/vendor"],
        repo=REPO,
        timestamp="2026-09-08T07:00:00Z",
    )
    sbom_names = S.component_names(doc)
    # Independent path (different algorithm)
    indep = S.independent_npm_lockfile_names(lock)
    equal = sbom_names == indep
    vendored = S.vendored_component_names(doc)
    meas = {
        "ok": equal and bool(vendored),
        "set_equality": equal,
        "sbom_names": sorted(sbom_names),
        "independent_names": sorted(indep),
        "sbom_count": len(sbom_names),
        "independent_count": len(indep),
        "only_in_sbom": sorted(sbom_names - indep),
        "only_in_independent": sorted(indep - sbom_names),
        "vendored_names": sorted(vendored),
        "vendored_represented": bool(vendored),
        "probe_2_confirmed": equal and bool(vendored),
        "out_of_process": True,
    }
    (PROBE / "probe2-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 2: INDEPENDENT LOCKFILE SET EQUALITY",
        "PROBE-2-BEGIN:IMP-0062",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"repo={REPO}",
        f"sbom_count={meas['sbom_count']}",
        f"independent_count={meas['independent_count']}",
        f"set_equality={equal}",
        f"vendored_represented={meas['vendored_represented']}",
        f"vendored_names={','.join(meas['vendored_names'])}",
        f"only_in_sbom={','.join(meas['only_in_sbom']) or '-'}",
        f"only_in_independent={','.join(meas['only_in_independent']) or '-'}",
        f"ok={meas['ok']}",
        f"probe_2_confirmed={meas['probe_2_confirmed']}",
        "PROBE-2-COMPLETE:IMP-0062",
        "SUCCESS:IMP-0062-probe2" if meas["ok"] else "FAILED:IMP-0062-probe2",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe2-lockfile-set.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if meas["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
