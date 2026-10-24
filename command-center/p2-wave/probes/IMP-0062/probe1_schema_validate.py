#!/usr/bin/env python3
"""IMP-0062 probe1: generated SBOM validates against CycloneDX schema."""

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
    doc = S.build_sbom(
        name="agent-skills-toolchain",
        version="0.1.0",
        npm_lockfiles=[lock],
        vendored_markers=["tools/editor/ralph-orchestrator/vendor"],
        repo=REPO,
        timestamp="2026-09-08T07:00:00Z",
    )
    schema = S.load_schema(REPO)
    errs = S.validate_cyclonedx(doc, schema)
    out_sbom = PROBE / "probe1-sbom.json"
    S.write_sbom(doc, out_sbom)
    meas = {
        "ok": len(errs) == 0,
        "error_count": len(errs),
        "errors_sample": errs[:10],
        "component_count": len(doc.get("components") or []),
        "bomFormat": doc.get("bomFormat"),
        "specVersion": doc.get("specVersion"),
        "schema": S.SCHEMA_RELPATH,
        "probe_1_confirmed": len(errs) == 0,
        "sbom_path": str(out_sbom.relative_to(REPO)),
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 1: CYCLONEDX SCHEMA VALIDATION",
        "PROBE-1-BEGIN:IMP-0062",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"repo={REPO}",
        f"schema={S.SCHEMA_RELPATH}",
        f"bomFormat={doc.get('bomFormat')}",
        f"specVersion={doc.get('specVersion')}",
        f"component_count={meas['component_count']}",
        f"error_count={meas['error_count']}",
        f"ok={meas['ok']}",
        f"probe_1_confirmed={meas['probe_1_confirmed']}",
        "PROBE-1-COMPLETE:IMP-0062",
        "SUCCESS:IMP-0062-probe1" if meas["ok"] else "FAILED:IMP-0062-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-schema.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if meas["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
