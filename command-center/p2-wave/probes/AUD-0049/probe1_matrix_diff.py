#!/usr/bin/env python3
"""AUD-0049 Probe 1: promised platforms minus CI runs-on values.

Both-states control (catalog tests_required):
  GOOD: live workflow matrix → Windows flagged promised-but-underexercised.
  BAD:  fabricated full-coverage claim (families=[linux,windows,macos] while every
        runs-on line remains ubuntu-latest) → detector must FIRE (reject the claim).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT = PROBE / "probe1-matrix-diff.json"
RAW = PROBE / "probe1-matrix.raw.txt"
CTRL = PROBE / "control-both-states.json"

FAMILY = {
    "ubuntu": "linux",
    "linux": "linux",
    "windows": "windows",
    "macos": "macos",
}


def promised_platforms() -> dict:
    """Derive promised platforms from README + AGENTS.md charter language."""
    sources: list[str] = []
    hits: dict[str, list[str]] = {"linux": [], "windows": [], "macos": []}
    for rel in ("README.md", "AGENTS.md", "docs/README.md"):
        p = REPO / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        sources.append(rel)
        for m in re.finditer(
            r"(?i)\b(windows(?:-first)?|linux|macos|macOS|cross-platform)\b", text
        ):
            tok = m.group(1).lower()
            if tok.startswith("windows"):
                hits["windows"].append(f"{rel}:{m.start()}")
            elif tok == "linux":
                hits["linux"].append(f"{rel}:{m.start()}")
            elif "mac" in tok:
                hits["macos"].append(f"{rel}:{m.start()}")
            elif tok == "cross-platform":
                for k in hits:
                    hits[k].append(f"{rel}:cross-platform@{m.start()}")
    promised = sorted(k for k, v in hits.items() if v)
    return {
        "sources": sources,
        "mentions": {k: len(v) for k, v in hits.items()},
        "promised": promised,
        "raw_hits": {k: v[:5] for k, v in hits.items()},
    }


def parse_runs_on(text: str, file_label: str) -> list[dict]:
    jobs: list[dict] = []
    for i, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^(\s*)runs-on:\s*(.+?)\s*$", line)
        if not m:
            continue
        val = m.group(2).strip().strip("\"'")
        fam = None
        low = val.lower()
        for key, fam_name in FAMILY.items():
            if key.lower() in low:
                fam = fam_name
                break
        # matrix expressions like ${{ matrix.os }} stay unknown unless expanded
        if fam is None and "${{" in val:
            fam = "matrix-expr"
        jobs.append(
            {
                "file": file_label,
                "line": i,
                "runs_on": val,
                "family": fam or "unknown",
            }
        )
    return jobs


def runs_on_inventory() -> dict:
    wf_dir = REPO / ".github" / "workflows"
    jobs: list[dict] = []
    for yml in sorted(wf_dir.glob("*.yml")) + sorted(wf_dir.glob("*.yaml")):
        text = yml.read_text(encoding="utf-8", errors="replace")
        jobs.extend(parse_runs_on(text, str(yml.relative_to(REPO))))
    families = sorted(
        {e["family"] for e in jobs if e["family"] in ("linux", "windows", "macos")}
    )
    return {
        "workflow_files": len(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))),
        "runs_on_entries": len(jobs),
        "families_exercised": families,
        "entries": jobs,
    }


def compare(promised: set[str], exercised: set[str]) -> dict:
    missing = sorted(promised - exercised)
    extra = sorted(exercised - promised)
    return {
        "promised_minus_exercised": missing,
        "exercised_minus_promised": extra,
        "windows_promised_but_underexercised": "windows" in missing
        or ("windows" in promised and "windows" not in exercised),
        "claims_full_coverage": not missing and bool(promised),
    }


def both_states_control(
    promised: set[str], real_exercised: set[str], entries: list
) -> dict:
    """GOOD = real matrix flags Windows. BAD = lied full-coverage claim must fire."""
    good = compare(promised, real_exercised)
    # BAD: fabricate a coverage claim that ignores the still-ubuntu-only entries
    lied_exercised = {"linux", "windows", "macos"}
    bad_claim = compare(promised, lied_exercised)
    # Independent check: are there ANY real windows runs-on strings?
    real_windows_runs = [
        e
        for e in entries
        if e["family"] == "windows" or "windows" in e["runs_on"].lower()
    ]
    # Detector: reject full-coverage claim when zero windows runs-on exist
    bad_full_coverage_claim = (
        bad_claim["claims_full_coverage"] and len(real_windows_runs) == 0
    )
    fired_on_bad = bad_full_coverage_claim  # we detect the lie
    silent_on_good = (
        bool(good["windows_promised_but_underexercised"])
        and not good["claims_full_coverage"]
    )
    return {
        "id": "AUD0049-C1",
        "kind": "known-broken-fixture",
        "description": (
            "Comparator must flag Windows as promised-but-underexercised given "
            "ubuntu-only runs-on; a fabricated full-coverage claim with zero "
            "windows runners must be rejected."
        ),
        "good_state": good,
        "bad_state": {
            "lied_families_exercised": sorted(lied_exercised),
            "compare_if_trusted": bad_claim,
            "real_windows_runs_on_count": len(real_windows_runs),
            "full_coverage_claim_rejected": bad_full_coverage_claim,
        },
        "fired_on_bad_state": fired_on_bad,
        "silent_on_good_state": silent_on_good,
        "ok": fired_on_bad and silent_on_good,
    }


def main() -> int:
    promised = promised_platforms()
    matrix = runs_on_inventory()
    promised_set = set(promised["promised"])
    exercised = set(matrix["families_exercised"])
    diff = compare(promised_set, exercised)
    control = both_states_control(promised_set, exercised, matrix["entries"])
    CTRL.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")

    result = {
        "ok": control["ok"],
        "unit": "AUD-0049",
        "probe": 1,
        "promised": promised,
        "matrix": {
            "workflow_files": matrix["workflow_files"],
            "runs_on_entries": matrix["runs_on_entries"],
            "families_exercised": matrix["families_exercised"],
            "sample_entries": matrix["entries"][:40],
        },
        "set_difference": {
            "promised_minus_exercised": diff["promised_minus_exercised"],
            "exercised_minus_promised": diff["exercised_minus_promised"],
        },
        "windows_promised_but_underexercised": diff[
            "windows_promised_but_underexercised"
        ],
        "claims_full_coverage": diff["claims_full_coverage"],
        "control": control,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "AUD-0049 NAMED PROBE 1: promised platforms vs runs-on set difference",
        "unit=AUD-0049",
        f"promised={promised['promised']}",
        f"mentions={promised['mentions']}",
        f"workflow_files={matrix['workflow_files']}",
        f"runs_on_entries={matrix['runs_on_entries']}",
        f"families_exercised={matrix['families_exercised']}",
        f"promised_minus_exercised={diff['promised_minus_exercised']}",
        f"exercised_minus_promised={diff['exercised_minus_promised']}",
        f"windows_promised_but_underexercised={diff['windows_promised_but_underexercised']}",
        f"CONTROL fired_on_bad={control['fired_on_bad_state']} "
        f"silent_on_good={control['silent_on_good_state']} ok={control['ok']}",
    ]
    for e in matrix["entries"][:40]:
        lines.append(f"RUNS_ON\t{e['file']}:{e['line']}\t{e['runs_on']}\t{e['family']}")
    lines.append("SUCCESS:AUD-0049-probe1")
    RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(RAW.read_text(encoding="utf-8"))
    return 0 if control["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
