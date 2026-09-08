#!/usr/bin/env python3
"""IMP-0003 Probe 1: scanner exit code + named-path report against a fixture tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))
import forbidden as F  # noqa: E402

PROBE_DIR = Path(__file__).resolve().parent
WORK = PROBE_DIR / "work" / "probe1"
RAW = PROBE_DIR / "probe1-scanner-fixture.raw.txt"
MEAS = PROBE_DIR / "probe1-measurement.json"


def _write(p: Path, text: str = "x\n") -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def build_fixture(root: Path) -> dict[str, str]:
    """Plant one known-present item per forbidden path-role class."""
    plants = {
        "git": ".git/config",
        "node_modules": "node_modules/leftpad/index.js",
        "pycache": "lib/__pycache__/x.pyc",
        "log": "build.log",
        "transcript": "sessions/agent.jsonl",
        "os_cache": ".DS_Store",
        "oversized": "blob.bin",
    }
    if root.exists():
        import shutil

        shutil.rmtree(root)
    root.mkdir(parents=True)
    _write(root / plants["git"], "[core]\n\trepositoryformatversion = 0\n")
    _write(root / plants["node_modules"], "module.exports=1\n")
    _write(root / plants["pycache"], "pyc")
    _write(root / plants["log"], "log-line\n")
    _write(root / plants["transcript"], '{"role":"user"}\n')
    _write(root / plants["os_cache"], "mac-junk")
    # oversized under a low ceiling
    (root / plants["oversized"]).write_bytes(b"Z" * 2048)
    # one legitimate file that must NOT be flagged
    _write(root / "README.md", "# ok\n")
    return plants


def main() -> int:
    lines: list[str] = []
    lines.append("NAMED PROBE 1: SCANNER EXIT CODE + NAMED-PATH REPORT")
    lines.append("PROBE-1-BEGIN:IMP-0003")
    lines.append("stage=p2-deliver")
    lines.append(
        "evidence_requirement_verbatim="
        "TWO independent signals: (1) the scanner's own exit code and named-path "
        "report against a fixture tree; (2) an out-of-band du/file-count census "
        "of the same tree computed by a different script, proving the scanner "
        "saw every path (detector control: it must find a KNOWN-PRESENT planted "
        "item before any 'clean' verdict is trusted)."
    )
    fixture = WORK / "fixture"
    plants = build_fixture(fixture)
    ceiling = 1024
    report = F.scan_staging(
        fixture,
        config=F.ScanConfig(max_file_bytes=ceiling, require_planted_control=False),
    )
    named = report.named_path_report()
    lines.append(f"fixture={fixture.relative_to(REPO)}")
    lines.append(f"max_file_bytes={ceiling}")
    lines.append(f"scanner_exit_code={report.exit_code}")
    lines.append(f"finding_count={len(report.findings)}")
    lines.append(f"paths_seen={report.paths_seen}")
    lines.append(f"files_seen={report.files_seen}")
    lines.append(f"dirs_seen={report.dirs_seen}")
    lines.append("--- named-path-report ---")
    lines.append(named.rstrip("\n"))
    lines.append("--- end-named-path-report ---")

    roles_found = sorted({f.role for f in report.findings})
    required = sorted(plants.keys())
    missing_roles = [r for r in required if r not in roles_found]
    # Map each plant path to whether it appears in findings
    plant_hits: dict[str, bool] = {}
    for role, rel in plants.items():
        plant_hits[role] = any(
            f.role == role and (f.path == rel or f.path.startswith(rel.split("/")[0]))
            for f in report.findings
        )
        # stronger: path prefix match for directory plants
        if not plant_hits[role]:
            plant_hits[role] = any(
                f.role == role
                and (f.path == rel or rel.startswith(f.path) or f.path.startswith(rel.rsplit("/", 1)[0]))
                for f in report.findings
            )

    # Explicit per-plant path presence in findings
    for role, rel in plants.items():
        hit = any(
            f.path == rel or f.path == Path(rel).parts[0] or f.path.startswith(str(Path(rel).parts[0]) + "/")
            for f in report.findings
            if f.role == role or (role == "git" and f.role == "git")
        )
        plant_hits[role] = hit
        lines.append(f"PLANT role={role} path={rel} found={hit}")

    ok = (
        report.exit_code == 12
        and not missing_roles
        and all(plant_hits.values())
        and F.classify_path_role("README.md") is None
    )
    lines.append(f"roles_found={roles_found}")
    lines.append(f"missing_roles={missing_roles}")
    lines.append(f"all_plants_found={all(plant_hits.values())}")
    lines.append(f"probe_ok={ok}")
    lines.append("PROBE-1-COMPLETE:IMP-0003")
    lines.append("SUCCESS:IMP-0003-probe1" if ok else "FAILED:IMP-0003-probe1")

    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    MEAS.write_text(
        json.dumps(
            {
                "unit": "IMP-0003",
                "probe": 1,
                "scanner_exit_code": report.exit_code,
                "finding_count": len(report.findings),
                "paths_seen": report.paths_seen,
                "files_seen": report.files_seen,
                "dirs_seen": report.dirs_seen,
                "roles_found": roles_found,
                "missing_roles": missing_roles,
                "plant_hits": plant_hits,
                "plants": plants,
                "findings": [f.as_dict() for f in report.findings],
                "ok": ok,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
