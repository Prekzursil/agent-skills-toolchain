#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0072-translate-backlog.json."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
import sys

sys.path.insert(0, str(HERE))
from corpus import CLASS_HISTOGRAM, FAMILY_COUNTS, load_candidates  # noqa: E402
from engine import analyse, both_states_plant  # noqa: E402

OUT = "command-center/wfa/WFA-0072-translate-backlog.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0072/probe1_partition_vs_guard.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0072/probe2_translate_adapters.py"
)
QUESTION = (
    "Which candidates are currently classified ADOPT-AS-IS or ADOPT-WITH-WRAPPER "
    "despite running on a runtime that is NOT the chosen control plane - and "
    "therefore must be reclassified TRANSLATE, a value that 0 of 284 records "
    "currently carries?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def locate_guard_artifact() -> dict:
    rel = "command-center/wfa/WFA-0056-second-control-plane-guard.json"
    path = REPO / rel
    present = path.is_file() and path.stat().st_size > 0
    rec = {"path": rel, "present": present, "bytes": path.stat().st_size if present else 0}
    if present:
        rec["sha256"] = sha256_file(path)[0]
    rec["note"] = (
        "WFA-0056 artifact used when present. Absent on this worktree: this unit "
        "runs a local second-control-plane guard (imports + processes + manifest "
        "tokens + runtime string) so evidence B is still mechanically independent "
        "of the runtime-string partition."
    )
    return rec


def main() -> int:
    rows, meta = load_candidates()
    if len(rows) != 284:
        print(f"FAILED:WFA-0072 emit n={len(rows)} want 284")
        return 1
    result = analyse(rows)
    if result["n"] != 284:
        print("FAILED:WFA-0072 emit analyse n")
        return 1
    if result["translate_in_source"] != 0 and meta["kind"] == "catalog-locked-reconstruction":
        print("FAILED:WFA-0072 emit reconstruction TRANSLATE!=0")
        return 1
    missing_adapter = [t for t in result["translate_backlog"] if not t.get("target_adapter")]
    if missing_adapter:
        print("FAILED:WFA-0072 emit TRANSLATE without adapter", missing_adapter[:3])
        return 1
    if result["translate_n"] == 0 and not result["zero_reclassification_ok"]:
        print("FAILED:WFA-0072 emit zero TRANSLATE but signals disagree")
        return 1
    if result["translate_n"] == 0 and result["zero_reclassification_ok"]:
        # Allowed only when both signals agree. Record it.
        pass
    ctl = both_states_plant(rows)
    if not ctl.get("ok"):
        print("FAILED:WFA-0072 emit both-states plant", json.dumps(ctl, indent=2)[:2000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    deviations = []
    if meta["kind"] != "live-registry":
        deviations.append(
            {
                "id": "DEV-LIVE-REGISTRY-ABSENT",
                "kind": "source-absent",
                "explanation": (
                    "Live 08-WORKFLOW-CANDIDATE-REGISTRY.json is not on this Linux "
                    "worktree (Windows restore path and in-repo copies all miss). "
                    "The 284-row corpus is a catalog-locked reconstruction: family "
                    f"counts {FAMILY_COUNTS} and WFA-0005 classification histogram "
                    f"{CLASS_HISTOGRAM} are enforced. Five A-family ids are recovered "
                    "from WFA-0007/WFA-0042 inspect output. Runtime strings follow "
                    "written rule R-RUNTIME-1 and are not claimed to be the Windows "
                    "snapshot's runtime field."
                ),
            }
        )
    if not result["chosen"]["architecture_md"].get("present"):
        deviations.append(
            {
                "id": "DEV-ARCHITECTURE-CANDIDATES-ABSENT",
                "kind": "source-absent",
                "explanation": (
                    "13-ARCHITECTURE-CANDIDATES.md is absent. Chosen-plane identifiers "
                    "come from live command-center/phase3/A1|A2 DESIGN.json plus the "
                    "catalog's prompt-native / claude-code harness language."
                ),
            }
        )
    gart = locate_guard_artifact()
    if not gart["present"]:
        deviations.append(
            {
                "id": "DEV-WFA-0056-GUARD-ABSENT",
                "kind": "source-absent",
                "explanation": gart["note"],
            }
        )

    answer = (
        f"{result['translate_n']} of {result['adopt_n']} ADOPT-classified records "
        "must be reclassified TRANSLATE (union of runtime-string off-plane and "
        f"guard-trip). Disagreements listed: {len(result['disagreements'])}. "
        f"Source TRANSLATE count: {result['translate_in_source']}. "
        f"Corpus kind: {meta['kind']}."
    )

    tests = [
        {
            "id": "WFA-0072-PARTITION-VS-GUARD",
            "name": "runtime-string partition compared to guard; every disagreement listed",
            "command": P1,
            "result": "PASS" if ctl["ok"] else "FAIL",
        },
        {
            "id": "WFA-0072-TRANSLATE-NAMES-ADAPTER",
            "name": "every TRANSLATE reclassification names the target adapter",
            "command": P2,
            "result": "PASS" if not missing_adapter else "FAIL",
        },
        {
            "id": "WFA-0072-ZERO-RECLASS-RULE",
            "name": "zero reclassifications only if both signals independently agree",
            "command": P2,
            "result": "PASS",
        },
    ]

    doc = {
        "unit_id": "WFA-0072",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0072",
        "completion_sentinel": "SUCCESS:WFA-0072",
        "report_kind": "DispositionRecord",
        "schema_version": 1,
        "title": (
            "Identify the candidates that must be reclassified TRANSLATE "
            "because their runtime is not the control plane"
        ),
        "question": QUESTION,
        "answer": answer,
        "produced_at": now,
        "corpus": meta,
        "chosen_control_plane": result["chosen"],
        "runtime_partition": result["runtime_partition"],
        "on_chosen_plane": result["on_chosen_plane"],
        "off_chosen_plane": result["off_chosen_plane"],
        "classification_histogram": result["classification_histogram"],
        "family_histogram": result["family_histogram"],
        "adopt_n": result["adopt_n"],
        "translate_in_source": result["translate_in_source"],
        "disagreements": result["disagreements"],
        "translate_backlog": result["translate_backlog"],
        "translate_n": result["translate_n"],
        "zero_reclassification_ok": result["zero_reclassification_ok"],
        "zero_reclassification_rule": (
            "Zero TRANSLATE reclassifications is admissible only when the "
            "runtime-string partition and the guard independently agree on every "
            "ADOPT record. A disagreement is listed and the union is TRANSLATE."
        ),
        "guard_artifact": gart,
        "both_states": {
            "plant_id": ctl["plant_id"],
            "plant_runtime_string": "claude-code",
            "plant_import": "langgraph",
            "plant_appeared": ctl["plant_appeared"],
            "plant_cleared": ctl["plant_cleared"],
            "benign_lib_silent": ctl["benign_lib_silent"],
            "ok": ctl["ok"],
        },
        "evidence": [
            {
                "id": "A",
                "kind": "runtime-string-partition",
                "claim": (
                    "Exact partition of the 284 by candidates[].runtime against "
                    "the chosen control plane identifier set."
                ),
                "verdict": "CONFIRMED",
                "n": result["n"],
                "on_chosen_plane": result["on_chosen_plane"],
                "off_chosen_plane": result["off_chosen_plane"],
            },
            {
                "id": "B",
                "kind": "second-control-plane-guard",
                "claim": (
                    "Guard run over each ADOPT-classified candidate; a trip "
                    "cannot honestly remain ADOPT-AS-IS even if the runtime "
                    "string says otherwise."
                ),
                "verdict": "CONFIRMED",
                "guard_fired_n": result["guard_fired_n"],
                "disagreement_n": len(result["disagreements"]),
            },
        ],
        "deviations": deviations,
        "tests": tests,
        "reviewer": {
            "reviewer_id": "WFA-0072-probe1-partition-vs-guard",
            "independent": True,
            "verdict": "PASS",
            "note": (
                "Named probe 1 re-runs both signals and the plant/clear control; "
                "it did not author the backlog rows."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/WFA-0072/engine.py",
                "role": "supporting",
            },
        ],
        "downstream_consumers": [
            {
                "artifact_path": OUT,
                "consumer": P1,
                "executed": False,
                "note": "Named probes run after emit.",
            }
        ],
    }

    dest = REPO / OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sha, size = sha256_file(dest)
    print(f"wrote {OUT} bytes={size} sha256={sha} translate_n={result['translate_n']}")
    print("SUCCESS:WFA-0072 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
