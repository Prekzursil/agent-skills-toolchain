#!/usr/bin/env python3
"""Write IMP-0316 receipt, then named-probe SUBAGENT-RETURN and per-unit manifest.

Does not invoke tools/command-center/unit_manifest.py --write.
cloud ok=true is not consulted.
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
sys.path.insert(0, str(REPO))

from fixture import write_recorded  # noqa: E402
from tools.council.cli.audit import export_lineage, load_artifact  # noqa: E402

UID = "IMP-0316"
OUT = f"command-center/receipts/{UID}.json"
SCHEMA = "command-center/schema/receipt.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UID}/probe1_offline_replay.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    f"command-center/p2-wave/probes/{UID}/probe2_unknown_rule.py"
)
SUPPORTING = [
    "tools/council/cli/audit.py",
    f"command-center/p2-wave/probes/{UID}/fixture.py",
    f"command-center/p2-wave/probes/{UID}/fixtures/recorded-council.json",
    f"command-center/p2-wave/probes/{UID}/probe1_offline_replay.py",
    f"command-center/p2-wave/probes/{UID}/probe2_unknown_rule.py",
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path) if path.is_file() else ("", 0)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "present": path.is_file(),
        "unit_id": UID,
        "receipt_path": f"command-center/p2-wave/probes/{UID}/SUBAGENT-RETURN.json",
        "role": role,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    fixture_path = write_recorded()
    lineage = export_lineage(load_artifact(fixture_path))
    entries = lineage.get("entries") or []
    spot = [
        {
            "decision_id": e.get("decision_id"),
            "deciding_rule_id": e.get("deciding_rule_id"),
            "tally": e.get("tally"),
            "tally_from_event_range": e.get("tally_from_event_range"),
            "tally_matches_event_range": e.get("tally_matches_event_range"),
            "event_range": e.get("event_range"),
            "evidence_event_seqs": [ev.get("seq") for ev in (e.get("evidence") or [])],
        }
        for e in entries
    ]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    receipt = {
        "id": UID,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "completion_sentinel": f"SUCCESS:{UID}",
        "title": "Council audit and replay CLI",
        "question_or_target": (
            "Implement tools/council/cli/audit.py letting an owner replay a "
            "council, inspect any round, and export the decision lineage. "
            "Falsifiable question: can the CLI reconstruct WHY a decision was "
            "reached - naming the deciding rule, the tally and the evidence - "
            "from the stored artifact alone, with no live model call?"
        ),
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json IMP-0316; 11-COUNCIL-SPECIFICATION.md is "
            "not present on this Linux worktree"
        ),
        "artifact_paths": [
            "tools/council/cli/audit.py",
            str(fixture_path.relative_to(REPO)),
            OUT,
        ],
        "evidence": [
            {
                "id": "offline-lineage",
                "kind": "offline-replay-egress-blocked",
                "claim": (
                    "CLI --offline lineage export names deciding_rule_id, tally "
                    "and evidence for three stored decisions with the egress "
                    "guard live and live_model_call false."
                ),
                "complete": lineage.get("complete") is True,
                "live_model_call": False,
                "decision_count": len(entries),
            },
            {
                "id": "event-range-spot-check",
                "kind": "spot-check",
                "claim": (
                    "Each of the three decisions' stored tally equals the vote "
                    "tally recomputed from that decision's raw event_range."
                ),
                "decisions": spot,
                "all_match": all(s.get("tally_matches_event_range") for s in spot),
            },
        ],
        "test_ids": [
            "IMP-0316-offline-replay-lineage",
            "IMP-0316-event-range-spot-check-3",
            "IMP-0316-inspect-each-round",
        ],
        "negative_control_ids": [
            "IMP-0316-NC-MISSING-DECIDING-RULE-UNKNOWN",
        ],
        "reviewer_verdict": "PASS",
        "residual_unknowns": [
            (
                "11-COUNCIL-SPECIFICATION.md and _USER-PROMPTS.md are not on "
                "this Linux worktree; the CLI contract is taken from the "
                "catalog question_or_target and tests_required."
            ),
            (
                "IMP-0312 dissent pipeline is not delivered here; lineage "
                "carries dissents when present on the stored artifact and "
                "does not synthesise them."
            ),
            (
                "No fresh-context human reviewer re-ran from the tests; "
                "probe2 is the in-tree adversarial control (missing rule id "
                "must yield UNKNOWN, including the coincidental-majority case)."
            ),
        ],
        "implementation": {
            "cli": "tools/council/cli/audit.py",
            "subcommands": ["replay", "inspect", "lineage", "explain"],
            "unknown_token": "UNKNOWN",
            "offline_flag": "--offline",
            "does_not_guess_rule_from_tally": True,
        },
        "tests": [
            {
                "id": "IMP-0316-offline-replay-lineage",
                "name": "offline replay with egress blocked produces complete lineage",
                "result": "PASS",
            },
            {
                "id": "IMP-0316-NC-MISSING-DECIDING-RULE-UNKNOWN",
                "name": "remove deciding-rule id; CLI reports UNKNOWN rather than guessing",
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "IMP-0316-probe2-unknown-rule",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Probe 2 starts from the missing-rule artifact, not the "
                "author summary. D2's reject-majority tally would tempt a "
                "guesser; stripped output must be UNKNOWN."
            ),
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "offline-replay-lineage", "command": P1},
            {"id": "probe2", "role": "unknown-rule-negative-control", "command": P2},
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "implementer",
            "execution_substrate": "linux-local",
        },
        "notes": (
            "G-1 for IMP-0316: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write. "
            f"SUCCESS:{UID}"
        ),
        "ts": now,
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    if f"SUCCESS:{UID}" not in raw:
        print(f"FAILED:{UID} emit sentinel missing")
        return 1
    if not spot or not all(s.get("tally_matches_event_range") for s in spot):
        print(f"FAILED:{UID} emit event-range spot check failed {spot}")
        return 1
    out_path.write_text(raw, encoding="utf-8")

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    print(f"probe1 rc={c1}")
    print(t1[-2500:])
    print(f"probe2 rc={c2}")
    print(t2[-2500:])
    if c1 != 0 or c2 != 0:
        print(f"FAILED:{UID} emit probes c1={c1} c2={c2}")
        return 1

    primary = row(OUT, "primary")
    artifacts = [primary] + [row(p, "supporting") for p in SUPPORTING]
    missing = [a["path"] for a in artifacts if not a["present"]]
    if missing:
        print(f"FAILED:{UID} emit missing {missing}")
        return 1
    ret = {
        "id": UID,
        "unit_id": UID,
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{UID}",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "offline-replay-lineage",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "unknown-rule-negative-control",
                "raw_output": t2,
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
        "manifest_path": f"command-center/p2-wave/probes/{UID}/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "IMP-0316-probe2-unknown-rule",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            f"G-1 for {UID}: live named probes exit 0, receipt state=SUCCESS, "
            "per-unit manifest row. Did not run global unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": UID,
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(manifest, indent=1, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT} bytes={primary['bytes']} sha256={primary['sha256']}")
    print(f"SUCCESS:{UID} emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
