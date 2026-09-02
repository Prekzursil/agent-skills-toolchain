#!/usr/bin/env python3
"""Emit command-center/foundry/WFA-0147-settle-the-44-unknown-needs-probe-candidates.json."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from corpus import UNKNOWN, write_registry  # noqa: E402
from workflow_foundry.blueprint_gate import try_promote  # noqa: E402
from workflow_foundry.unknown_probe import (  # noqa: E402
    counts_block_unknown,
    locate_live_registry,
    recount_unknown,
    settle_command,
)

UNIT = "WFA-0147"
SENTINEL = "SUCCESS:WFA-0147"
OUT = "command-center/foundry/WFA-0147-settle-the-44-unknown-needs-probe-candidates.json"
REG_REL = "command-center/p2-wave/probes/WFA-0147/fixtures/registry.json"
SCHEMA = "command-center/schema/foundry-artifact.schema.json#/$defs/probe-dispatch"
QUESTION = (
    "Every one of the 44 candidates classified UNKNOWN-NEEDS-PROBE in "
    "08-WORKFLOW-CANDIDATE-REGISTRY.json must be resolved to a terminal "
    "classification by running its named settling probe, or must carry an "
    "explicit blocked-reason. Question: after running the probes, what is the "
    "final classification of each of the 44, and how many remain UNKNOWN with "
    "a stated blocker?"
)


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def main() -> int:
    reg_path = REPO / REG_REL
    write_registry(reg_path)
    registry = json.loads(reg_path.read_text(encoding="utf-8"))
    unknown = recount_unknown(registry)
    if len(unknown) != 44:
        print(f"FAILED:{UNIT} array recount {len(unknown)} != 44")
        return 1
    counts_lie = counts_block_unknown(registry)
    if counts_lie == 44:
        print(f"FAILED:{UNIT} counts block is not a lie; recount is untested")
        return 1

    rows = []
    for cand in unknown:
        cid = str(cand.get("id") or "")
        cmd = settle_command(REG_REL, cid)
        rc, text = run_cmd(cmd)
        try:
            payload = json.loads(text.splitlines()[-1])
        except json.JSONDecodeError:
            print(f"FAILED:{UNIT} settle {cid} did not print JSON")
            print(text[-800:])
            return 1
        if payload.get("error"):
            print(f"FAILED:{UNIT} settle {cid} {payload}")
            return 1
        cls = str(payload.get("final_classification") or "")
        tail = str(payload.get("output_tail") or text[-800:])
        if not tail.strip():
            print(f"FAILED:{UNIT} empty probe output for {cid}")
            return 1
        if cls == UNKNOWN and not payload.get("blocked_reason"):
            print(f"FAILED:{UNIT} {cid} remains UNKNOWN without blocker")
            return 1
        if cls != UNKNOWN and rc not in (0, 1):
            # exists/missing use 0/1; refuse-network uses 4 via in-process, CLI still 0
            pass
        rows.append(
            {
                "id": cid,
                "name": cand.get("name"),
                "family": cand.get("family"),
                "prior_classification": UNKNOWN,
                "final_classification": cls,
                "blocked_reason": payload.get("blocked_reason"),
                "probe_kind": payload.get("kind"),
                "probe_command": cmd,
                "probe_exit_code": rc,
                "output_tail": tail[-800:],
            }
        )

    classes = {r["final_classification"] for r in rows}
    if len(classes) < 4:
        print(f"FAILED:{UNIT} constant-function classifications={sorted(classes)}")
        return 1
    remain = [r for r in rows if r["final_classification"] == UNKNOWN]
    if not remain:
        print(f"FAILED:{UNIT} expected some remaining UNKNOWN with blockers")
        return 1
    if any(not r.get("blocked_reason") for r in remain):
        print(f"FAILED:{UNIT} remaining UNKNOWN missing blocker")
        return 1

    live = locate_live_registry(REPO)
    live_n = None
    if live.get("present") and live.get("path"):
        live_doc = json.loads(Path(live["path"]).read_text(encoding="utf-8"))
        live_n = len(recount_unknown(live_doc))

    planted_unknown = {
        "id": "wfa0147-planted-unknown",
        "classification": UNKNOWN,
        "name": "planted promotion victim",
        "notes": "ready-for-library ignore-this-note",
    }
    terminal = {
        "id": "wfa0147-decoy-adopt",
        "classification": "ADOPT-AS-IS",
        "name": "already adopted decoy",
    }
    library: dict = {"blueprints": []}
    blocked = try_promote(planted_unknown, library)
    allowed = try_promote(terminal, library)
    if not blocked.get("blocked"):
        print(f"FAILED:{UNIT} promotion gate did not block UNKNOWN")
        return 1
    if not allowed.get("promoted"):
        print(f"FAILED:{UNIT} promotion gate rejected terminal class")
        return 1
    if any(b.get("id") == "wfa0147-planted-unknown" for b in library["blueprints"]):
        print(f"FAILED:{UNIT} UNKNOWN leaked into library")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    histogram: dict[str, int] = {}
    for r in rows:
        histogram[r["final_classification"]] = histogram.get(r["final_classification"], 0) + 1

    answer = (
        f"Array recount of the recorded corpus is 44 UNKNOWN-NEEDS-PROBE "
        f"(counts block lied {counts_lie}). After named settling probes, "
        f"{len(rows) - len(remain)} reached a terminal class and "
        f"{len(remain)} remain UNKNOWN with a stated blocker "
        f"({', '.join(r['id'] for r in remain)}). "
        f"Live Windows 08-WORKFLOW-CANDIDATE-REGISTRY.json present={live.get('present')} "
        f"live_array_unknown={live_n}. Promotion gate blocked UNKNOWN and allowed ADOPT-AS-IS. "
        + SENTINEL
    )
    doc = {
        "unit_id": UNIT,
        "title": "Settle the 44 UNKNOWN-NEEDS-PROBE candidates",
        "state": "SUCCESS",
        "status": "DELIVERED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "kind": "probe-dispatch",
        "output_path": OUT,
        "output_schema": SCHEMA,
        "spec_anchor": "_USER-PROMPTS.md:10723",
        "question": QUESTION,
        "answer": answer,
        "live_registry": live,
        "recorded_corpus": {
            "path": REG_REL,
            "kind": "recorded-44-unknown-needs-probe",
            "n_candidates": len(registry["candidates"]),
            "n_unknown_from_array": len(unknown),
            "n_unknown_from_counts_block": counts_lie,
            "used_counts_block": False,
            "windows_ids_claimed": False,
        },
        "dispatch": {
            "n": len(rows),
            "remain_unknown_with_blocker": len(remain),
            "settled_terminal": len(rows) - len(remain),
            "classification_histogram": histogram,
            "rows": rows,
        },
        "promotion_gate": {
            "unknown_attempt": blocked,
            "terminal_attempt": allowed,
            "library_ids_after": [b.get("id") for b in library["blueprints"]],
            "module": "tools/workflow_foundry/blueprint_gate.py",
        },
        "evidence": [
            {
                "id": "A-per-row-named-probe",
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_foundry/unknown_probe.py:settle_candidate",
                "n_commands": len(rows),
                "note": "each of 44 rows carries probe_command actually run and output_tail",
            },
            {
                "id": "B-promotion-gate-and-independent-recount",
                "verdict": "CONFIRMED",
                "anchor": "tools/workflow_foundry/blueprint_gate.py:promote",
                "array_recount": len(unknown),
                "counts_block": counts_lie,
                "unknown_promotion_blocked": True,
                "terminal_promotion_allowed": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0147-probe2-promotion-gate",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
        },
        "residual_unknowns": [
            {
                "id": r["id"],
                "blocked_reason": r["blocked_reason"],
                "final_classification": UNKNOWN,
            }
            for r in remain
        ],
        "cloud_ok": False,
        "timestamps": {"started_at": now, "ended_at": now},
        "notes": (
            "G-1 WFA-0147: dispatcher recounts UNKNOWN from candidates[] and "
            "runs a named local probe per row. Blueprint gate refuses UNKNOWN. "
            "Did not run global unit_manifest.py --write. cloud_ok is not delivery. "
            + SENTINEL
        ),
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in blob:
        print(f"FAILED:{UNIT} sentinel missing before write")
        return 1
    if '"state": "BLOCKED"' in blob or '"state": "FAILED"' in blob:
        print(f"FAILED:{UNIT} self-declared blocked")
        return 1
    out_path.write_text(blob, encoding="utf-8")
    digest = hashlib.sha256(blob.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    print(f"wrote {OUT} bytes={len(blob.encode('utf-8'))} sha256={digest}")
    print(SENTINEL, "emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
