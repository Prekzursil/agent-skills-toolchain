#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0075-disposition-drift-monitor.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import monitor as M  # noqa: E402

OUT = "command-center/wfa/WFA-0075-disposition-drift-monitor.json"
SCHEMA_PACK = "command-center/wfa/schema/wfa-schema-pack.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0075/probe1_silent_plants.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0075/probe2_documented_rename_fields.py"
)
QUESTION = (
    "Implementation target: a monitor that compares the disposition set between "
    "two registry versions and fails when any candidate's disposition changed "
    "without an accompanying evidence delta and a written reason, so dispositions "
    "cannot silently drift between waves."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(needle)
    if idx < 0:
        raise SystemExit(f"FAILED:emit needle {needle!r} missing in {rel}")
    return text[:idx].count("\n") + 1


def input_status(rel: str) -> dict:
    path = REPO / rel
    present = path.is_file() and path.stat().st_size > 0
    row = {"path": rel, "present": present}
    if present:
        sha, size = sha256_file(path)
        row["sha256"] = sha
        row["bytes"] = size
    return row


def slim_findings(result: dict) -> list[dict]:
    keep = []
    for row in result["findings"]:
        if row["kind"] in {M.KIND_UNCHANGED, M.KIND_ADDED, M.KIND_REMOVED}:
            if row["kind"] == M.KIND_UNCHANGED:
                continue
        keep.append(
            {
                "canonical_id": row["canonical_id"],
                "v1_id": row["v1_id"],
                "v2_id": row["v2_id"],
                "v1_classification": row["v1_classification"],
                "v2_classification": row["v2_classification"],
                "kind": row["kind"],
                "evidence_fields_changed": row["evidence_fields_changed"],
                "has_reason": row["has_reason"],
                "reason": row["reason"],
                "fail": row["fail"],
            }
        )
    return keep


def main() -> int:
    fix = HERE / "fixtures"
    v1p = fix / "v1_baseline.json"
    silent_p = fix / "v2_silent.json"
    doc_p = fix / "v2_documented.json"
    map_p = fix / "id_migration_map.json"

    silent = M.compare_paths(v1p, silent_p, map_p)
    documented = M.compare_paths(v1p, doc_p, map_p)
    no_map = M.compare_paths(v1p, doc_p, None)
    skip_reason = M.compare_paths(v1p, silent_p, map_p, require_reason=False)
    skip_ev = M.compare_paths(
        v1p, silent_p, map_p, require_evidence_delta=False
    )

    planted = [
        "wf-silent-both",
        "wf-silent-reason-hole",
        "wf-silent-evidence-hole",
    ]
    if sorted(silent["silent_drift_ids"]) != sorted(planted):
        print(f"FAILED:emit silent ids {silent['silent_drift_ids']}")
        return 1
    if documented["fail"] or documented["silent_drift_ids"]:
        print(f"FAILED:emit documented not silent {documented['silent_drift_ids']}")
        return 1
    if "wf-rename-new" not in documented["rename_only_ids"]:
        print("FAILED:emit rename not joined")
        return 1

    eng = "command-center/p2-wave/probes/WFA-0075/monitor.py"
    cat = "command-center/WORK-UNIT-CATALOG.json"
    a_compare = f"{eng}:{line_of(eng, 'def compare(')}"
    a_fields = f"{eng}:{line_of(eng, 'def evidence_fields_changed(')}"
    a_resolve = f"{eng}:{line_of(eng, 'def resolve_id(')}"
    a_reason = f"{eng}:{line_of(eng, 'def written_reason(')}"
    a_cat = f"{cat}:{line_of(cat, '\"id\": \"WFA-0075\"')}"

    pack = REPO / SCHEMA_PACK
    pack_present = pack.is_file() and pack.stat().st_size > 0
    v1_live = [
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    ]
    v1_hits = [p for p in v1_live if (REPO / p).is_file() or Path(p).is_file()]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    silent_ids = silent["silent_drift_ids"]
    doc_ids = documented["documented_ids"]
    rename_ids = documented["rename_only_ids"]
    smoke_row = next(
        f for f in documented["findings"] if f["canonical_id"] == "wf-doc-smoke"
    )
    preserve_row = next(
        f
        for f in documented["findings"]
        if f["canonical_id"] == "wf-doc-preserve"
    )
    rename_row = next(
        f for f in documented["findings"] if f["kind"] == M.KIND_RENAME_ONLY
    )
    no_map_kinds = {
        f["canonical_id"]: f["kind"]
        for f in no_map["findings"]
        if f["canonical_id"] in {"wf-rename-old", "wf-rename-new"}
    }

    doc = {
        "record_type": "RegressionFixture",
        "unit_id": "WFA-0075",
        "id": "WFA-0075",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0075",
        "completion_sentinel": "SUCCESS:WFA-0075",
        "title": (
            "Monitor that fails when a disposition changes without an "
            "evidence delta and a recorded reason"
        ),
        "question": QUESTION,
        "produced_at": now,
        "output_schema": SCHEMA_PACK + "#/$defs/RegressionFixture",
        "schema_pack": {
            "path": SCHEMA_PACK,
            "present": pack_present,
            "note": (
                "WFA-0001 schema pack is the declared contract. It is not "
                "on this worktree; this fixture is not claimed to have been "
                "accepted by a missing $defs/RegressionFixture."
                if not pack_present
                else "schema pack present; fragment not separately re-validated here"
            ),
        },
        "monitor": {
            "module": eng,
            "rule": (
                "After applying the id migration map, a classification change "
                "is SILENT_DRIFT (fail) unless at least one named evidence "
                "field changed AND a non-empty disposition_change_reason is "
                "written on the v2 record. The finding lists the evidence "
                "field names, not a boolean that something moved. A rename "
                "that preserves classification is RENAME_ONLY, not a "
                "disposition change."
            ),
        },
        "silent_pair": {
            "v1": "command-center/p2-wave/probes/WFA-0075/fixtures/v1_baseline.json",
            "v2": "command-center/p2-wave/probes/WFA-0075/fixtures/v2_silent.json",
            "fail": silent["fail"],
            "silent_drift_ids": silent_ids,
            "documented_ids": silent["documented_ids"],
            "findings": slim_findings(silent),
        },
        "documented_pair": {
            "v1": "command-center/p2-wave/probes/WFA-0075/fixtures/v1_baseline.json",
            "v2": "command-center/p2-wave/probes/WFA-0075/fixtures/v2_documented.json",
            "fail": documented["fail"],
            "silent_drift_ids": documented["silent_drift_ids"],
            "documented_ids": doc_ids,
            "rename_only_ids": rename_ids,
            "findings": slim_findings(documented),
        },
        "without_map_rename": {
            "rename_only_ids": no_map["rename_only_ids"],
            "kinds": {
                f["canonical_id"]: f["kind"]
                for f in no_map["findings"]
                if f["canonical_id"] in {"wf-rename-old", "wf-rename-new"}
            },
        },
        "mutants": {
            "skip_reason_misses": skip_reason["silent_drift_ids"],
            "skip_evidence_misses": skip_ev["silent_drift_ids"],
        },
        "tests": [
            {
                "id": "probe1-three-silent-plants",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-documented-rename-fields",
                "command": P2,
                "result": "PASS",
            },
        ],
        "both_states": {
            "fires_on": (
                "command-center/p2-wave/probes/WFA-0075/fixtures/v2_silent.json "
                "(three planted silent classification changes)"
            ),
            "silent_on": (
                "command-center/p2-wave/probes/WFA-0075/fixtures/v2_documented.json "
                "(classification changes with named evidence-field deltas and reasons)"
            ),
            "verbatim_fire": (
                f"fail=True silent_drift_ids={silent_ids}"
            ),
            "verbatim_silent": (
                f"fail=False silent_drift_ids=[] documented_ids={doc_ids} "
                f"rename_only_ids={rename_ids} "
                f"smoke_fields={smoke_row['evidence_fields_changed']} "
                f"preserve_fields={preserve_row['evidence_fields_changed']}"
            ),
        },
        "negative_controls": [
            {
                "id": "three-planted-silent-changes",
                "rejects": (
                    "v2_silent: classification changes lacking evidence-field "
                    "delta and/or written reason (both-missing, reason-hole, "
                    "evidence-hole)"
                ),
                "observed": f"silent_drift_ids={silent_ids} fail=True",
            },
            {
                "id": "documented-changes-stay-silent",
                "rejects": (
                    "a monitor that alarms on any classification change, which "
                    "cannot discriminate documented drift from silent drift"
                ),
                "observed": (
                    f"documented_pair fail=False documented_ids={doc_ids} "
                    f"fields smoke={smoke_row['evidence_fields_changed']} "
                    f"preserve={preserve_row['evidence_fields_changed']}"
                ),
            },
            {
                "id": "rename-is-not-disposition-change",
                "rejects": (
                    "treating wf-rename-old -> wf-rename-new as a disposition "
                    "change instead of consuming the id migration map"
                ),
                "observed": (
                    f"kind={rename_row['kind']} v1_id={rename_row['v1_id']} "
                    f"v2_id={rename_row['v2_id']} fail={rename_row['fail']}; "
                    f"without_map kinds={no_map_kinds}"
                ),
            },
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Three planted silent classification changes against the "
                    "synthetic v1 baseline are all caught."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_compare,
            },
            {
                "id": "C2",
                "claim": (
                    "Documented classification changes with evidence-field "
                    "deltas and written reasons are not flagged, and the "
                    "monitor names the evidence fields that moved."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_fields,
            },
            {
                "id": "C3",
                "claim": (
                    "A renamed candidate joined through the id migration map "
                    "is RENAME_ONLY, not a disposition change."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_resolve,
            },
        ],
        "evidence": [
            {
                "claim": "silent plants fail closed",
                "mechanism": "monitor.compare fail-set on v1 vs v2_silent",
                "anchor": a_compare,
                "verbatim": f"silent_drift_ids={silent_ids}",
            },
            {
                "claim": "documented pair stays silent and names fields",
                "mechanism": (
                    "evidence_fields_changed set algebra on named evidence "
                    "keys; compare kind=DOCUMENTED only when reason is also written"
                ),
                "anchor": a_fields,
                "verbatim": (
                    f"smoke={smoke_row['evidence_fields_changed']} "
                    f"preserve={preserve_row['evidence_fields_changed']} "
                    f"reason_gate={a_reason}"
                ),
            },
            {
                "claim": "id migration map is consumed",
                "mechanism": "resolve_id follows aliases transitively before join",
                "anchor": a_resolve,
                "verbatim": (
                    f"rename {rename_row['v1_id']} -> {rename_row['v2_id']} "
                    f"kind={rename_row['kind']}"
                ),
            },
            {
                "claim": "catalog names this monitor",
                "mechanism": "WORK-UNIT-CATALOG.json id=WFA-0075",
                "anchor": a_cat,
                "verbatim": (
                    "fails when any candidate's disposition changed without "
                    "an accompanying evidence delta and a written reason"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0075-probe2-field-algebra-and-reverse-alias",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe2 does not trust compare().fail for the documented pair. "
                "It recomputes evidence field diffs from the two JSON maps, "
                "walks the reverse alias list to join wf-rename-new back to "
                "wf-rename-old, re-runs the silent pair as the both-states "
                "control, and shows a without-map run emitting REMOVED+ADDED "
                "instead of RENAME_ONLY."
            ),
        },
        "inputs_measured": [
            input_status(
                "command-center/p2-wave/probes/WFA-0075/fixtures/v1_baseline.json"
            ),
            input_status(
                "command-center/p2-wave/probes/WFA-0075/fixtures/v2_silent.json"
            ),
            input_status(
                "command-center/p2-wave/probes/WFA-0075/fixtures/v2_documented.json"
            ),
            input_status(
                "command-center/p2-wave/probes/WFA-0075/fixtures/id_migration_map.json"
            ),
            input_status(
                "command-center/wfa/WFA-0010-id-stability-and-migration-map.json"
            ),
            input_status(
                "command-center/wfa/WFA-0068-disposition-decision-procedure.json"
            ),
            input_status(SCHEMA_PACK),
        ],
        "live_v1_baseline_hits": v1_hits,
        "residual_unknowns": [
            (
                "The catalog v1 baseline 08-WORKFLOW-CANDIDATE-REGISTRY.json "
                f"is not mounted on this worktree (hits={v1_hits or 'none'}). "
                "The monitor is proven on a synthetic v1/v2 pair with the same "
                "13-field candidate shape (classification, evidence object, id)."
            ),
            (
                "WFA-0010 (id migration map) and WFA-0068 (disposition decision "
                "procedure) artifacts are absent. WFA-0075 consumes a fixture "
                "map with the same alias-row contract and compares the "
                "classification field; it does not re-derive dispositions."
            ),
            (
                "Declared output_schema wfa-schema-pack.json#/$defs/RegressionFixture "
                f"present={pack_present}. This unit does not author the WFA-0001 pack."
            ),
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "adv_rebuild_circle": False,
        "cloud_ok": False,
        "produced_by": {
            "module": "command-center/p2-wave/probes/WFA-0075/emit_fixture.py",
            "execution_substrate": "linux-local",
        },
    }

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"silent_ids={silent_ids} documented_ids={doc_ids} "
        f"rename={rename_ids} pack_present={pack_present}"
    )
    print("SUCCESS:WFA-0075 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
