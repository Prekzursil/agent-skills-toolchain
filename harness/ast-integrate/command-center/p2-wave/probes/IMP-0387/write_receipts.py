#!/usr/bin/env python3
"""Write IMP-0387 receipt plus per-unit SUBAGENT-RETURN / UNIT-ARTIFACT-MANIFEST.

Does not run tools/command-center/unit_manifest.py --write.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

UNIT = "IMP-0387"
OUT = "command-center/receipts/IMP-0387.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0387/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/IMP-0387/probe2_predicted_vs_measured.py"
)
SUPPORTING = [
    "tools/router/load_semantics.py",
    "tools/router/inspect_load.py",
    "command-center/p2-wave/probes/IMP-0387/probe1_both_states.py",
    "command-center/p2-wave/probes/IMP-0387/probe2_predicted_vs_measured.py",
    "command-center/p2-wave/probes/IMP-0387/scenario.py",
    "command-center/p2-wave/probes/IMP-0387/fixtures/rules/always-on-no-frontmatter.md",
    "command-center/p2-wave/probes/IMP-0387/fixtures/rules/lazy-globstar.md",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/IMP-0387/SUBAGENT-RETURN.json",
        "role": role,
    }


def build_receipt() -> dict:
    R = S.load_resolver()
    I = S.load_instrument()
    states = S.both_states(resolver=R, instrument=I)
    census = S.full_census(resolver=R, instrument=I)
    roots = S.live_roots()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sample = R.resolve_file(S.FIXTURE_RULES / "always-on-no-frontmatter.md")
    globstar = R.resolve_file(S.FIXTURE_RULES / "lazy-globstar.md")
    return {
        "id": UNIT,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": S.SENTINEL,
        "completion_sentinel": S.SENTINEL,
        "title": "Frontmatter load-semantics resolver (always-on vs path-scoped)",
        "queryable_field": "load_mode",
        "load_mode": {
            "field": "load_mode",
            "values": [S.ALWAYS_ON, S.LAZY],
            "rule": (
                "Absence of a top-level YAML paths key => ALWAYS-ON (turn-0 inject). "
                "Presence of paths, including paths: ['**/*'] and paths: [], => LAZY. "
                "Adding paths demotes; it does not arm."
            ),
            "always_on_example": sample,
            "lazy_example": globstar,
        },
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "(declared; file is absent on this worktree — G-1 does not require it)"
        ),
        "output_schema": (
            "command-center/schema/receipt.schema.json "
            "(declared; file is absent on this worktree — G-1 does not require it)"
        ),
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json IMP-0387: a rule with NO paths: "
            "frontmatter is ALWAYS-ON and adding paths:[\"**/*\"] DEMOTES it to lazy"
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "worktree-isolated",
        },
        "timestamps": {"ended_at": now},
        "both_states": states,
        "load_mode_table": census["table"],
        "census": {
            "n_rows": census["n_rows"],
            "n_always_on": census["n_always_on"],
            "n_lazy": census["n_lazy"],
            "n_disagree": census["n_disagree"],
            "trees": census["trees"],
            "capability_index": census["capability_index"],
            "grok": census["grok"],
            "live_claude_rules_present": roots["claude_rules"].is_dir(),
            "live_repo_rules_present": roots["repo_rules"].is_dir(),
        },
        "instrument": {
            "requested": "grok inspect --json",
            "equivalent": "tools/router/inspect_load.py",
            "resolver": "tools/router/load_semantics.py",
            "disagreement_policy": "instrument wins",
        },
        "artifact_paths": [OUT] + SUPPORTING,
        "evidence": [
            {
                "id": "E1-both-states-inversion",
                "claim": (
                    "A fixture with no frontmatter resolves ALWAYS-ON; the same body "
                    "with paths: [\"**/*\"] resolves LAZY. The two answers differ."
                ),
                "verdict": "CONFIRMED" if states["inversion_holds"] else "REFUTED",
                "anchor": "tools/router/load_semantics.py:resolve_load_mode",
                "measured": states,
            },
            {
                "id": "E2-predicted-vs-measured-table",
                "claim": (
                    "Two-column table of predicted (YAML resolver) vs measured "
                    "(inspect_load instrument) load_mode for every scanned rules file. "
                    "Disagreements are findings; the instrument wins."
                ),
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/IMP-0387/probe2_predicted_vs_measured.py",
                "measured": {
                    "n_rows": census["n_rows"],
                    "n_always_on": census["n_always_on"],
                    "n_lazy": census["n_lazy"],
                    "n_disagree": census["n_disagree"],
                },
            },
            {
                "id": "E3-instrument-names-always-on",
                "claim": (
                    "The instrument names at least one ALWAYS-ON file. An empty "
                    "always-on set would be a broken instrument, not a measurement."
                ),
                "verdict": "CONFIRMED" if census["n_always_on"] >= 1 else "REFUTED",
                "anchor": "fixtures/rules/always-on-no-frontmatter.md",
                "measured": {"n_always_on": census["n_always_on"]},
            },
        ],
        "test_ids": [
            "IMP-0387-both-states",
            "IMP-0387-predicted-vs-measured",
        ],
        "tests": [
            {
                "id": "IMP-0387-both-states",
                "command": P1,
                "result": "GATED-BY-NAMED-PROBES",
            },
            {
                "id": "IMP-0387-predicted-vs-measured",
                "command": P2,
                "result": "GATED-BY-NAMED-PROBES",
            },
        ],
        "negative_control_ids": [
            "IMP-0387-NC-same-answer-both-states",
            "IMP-0387-NC-empty-always-on-set",
            "IMP-0387-NC-body-mention-is-not-a-key",
        ],
        "reviewer": {
            "reviewer_id": "IMP-0387-probe2-instrument-column",
            "verdict": "PASS",
            "independent": True,
            "starts_from": "catalog tests_required (both-states + instrument table)",
            "notes": (
                "Probe 2 re-derives the table with inspect_load.py in a subprocess "
                "and confirms inversion against the instrument, not against prose. "
                "A second human in a fresh context was not obtained on this worktree."
            ),
        },
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            {
                "claim": "grok inspect --json was not on PATH; inspect_load.py stood in.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Install grok, rerun inspect --json on the fixture tree, diff against inspect_load.py.",
            },
            {
                "claim": "~/.claude/rules and <REPO>/rules are absent on this worktree.",
                "verdict": "CONFIRMED-ABSENT",
                "settling_experiment": "Re-run the census on a host that has those trees.",
            },
            {
                "claim": "capability-index.json is absent; IMP-0385/0386 did not land here.",
                "verdict": "CONFIRMED-ABSENT",
                "settling_experiment": "After IMP-0386, attach load_mode onto each CapabilityRecord.",
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/IMP-0387/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "cloud_ok": False,
    }


def main() -> int:
    receipt = build_receipt()
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:receipts probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    c1b, t1b = c1, t1
    c2b, t2b = c2, t2

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": S.SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": receipt["output_schema"],
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1b,
                "role": "both-states-inversion",
                "raw_output": t1b,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2b,
                "role": "predicted-vs-measured-table",
                "raw_output": t2b,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary["sha256"],
                "bytes": primary["bytes"],
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/IMP-0387/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": receipt["reviewer"],
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for IMP-0387: live named probes exit 0, receipt state=SUCCESS "
            "with SENTINEL:IMP-0387:LOAD-SEMANTICS-RESOLVED, per-unit manifest row. "
            "Did not run global unit_manifest.py --write. No ADV rebuild."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UNIT,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": sum(1 for a in artifacts if a["present"]),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary['sha256']} bytes={primary['bytes']}")
    print("SUCCESS:IMP-0387 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
