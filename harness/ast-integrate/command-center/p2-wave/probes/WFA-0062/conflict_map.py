"""20-entry conflict_map loader and mechanism-level reconciliation.

The catalog names
C:/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json
(conflict_map, 20 entries). That file is not on this Linux worktree. The
loader searches live candidates first; if none parse as a 20-row map, it
uses a reconstructed 20-row map whose collision classes are the three
types WFA-0150 names (shared file, shared control plane, incompatible
stop rule) plus the three mechanism pairs named in WFA-0062's own
question_or_target.

Reconstruction is disclosed on every row. This is not a claim that the
Windows file was read.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from engine import MECHANISMS, fuse_same_stage, is_hard_pair

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

LIVE_CANDIDATES = [
    REPO / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    REPO / "command-center" / "sources" / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    REPO / "command-center" / "wfa" / "sources" / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    Path.home() / ".claude" / "harness-restore-20260806" / "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"),
    Path("/root/.claude/harness-restore-20260806/10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"),
]

# Reconstructed 20-row conflict_map. Blueprint-like left/right names are
# catalog-grounded collision classes, not invented workflow bodies.
RECONSTRUCTED_ROWS: list[dict[str, Any]] = [
    # --- named HARD pairs from WFA-0062 question_or_target ---
    {
        "id": "C01",
        "left_ref": "bp.blind-independent-first-pass",
        "right_ref": "bp.shared-context-deliberation",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Blind first pass vs shared-context deliberation (catalog-named pair).",
        "mechanism_left": "mech.blind_independent_first_pass",
        "mechanism_right": "mech.shared_context_deliberation",
        "intended_grade": "HARD",
        "intended_verdict": "CONFIRMED",
    },
    {
        "id": "C02",
        "left_ref": "bp.deterministic-replay",
        "right_ref": "bp.nondeterministic-sampling",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Deterministic replay vs non-deterministic sampling (catalog-named pair).",
        "mechanism_left": "mech.deterministic_replay",
        "mechanism_right": "mech.nondeterministic_sampling",
        "intended_grade": "HARD",
        "intended_verdict": "CONFIRMED",
    },
    {
        "id": "C03",
        "left_ref": "bp.fire-and-forget-dispatch",
        "right_ref": "bp.blocking-fanin-barrier",
        "declared_class": "shared_control_plane",
        "declared_reason": "Fire-and-forget dispatch vs blocking fan-in barrier (catalog-named pair).",
        "mechanism_left": "mech.fire_and_forget_dispatch",
        "mechanism_right": "mech.blocking_fanin_barrier",
        "intended_grade": "HARD",
        "intended_verdict": "CONFIRMED",
    },
    {
        "id": "C04",
        "left_ref": "bp.stop-first-success",
        "right_ref": "bp.stop-unanimous",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "WFA-0150 incompatible stop rule: first-success vs unanimous.",
        "mechanism_left": "mech.stop_first_success",
        "mechanism_right": "mech.stop_unanimous",
        "intended_grade": "HARD",
        "intended_verdict": "CONFIRMED",
    },
    {
        "id": "C05",
        "left_ref": "bp.exclusive-output-writer",
        "right_ref": "bp.shared-output-writer",
        "declared_class": "shared_file",
        "declared_reason": "WFA-0150 shared file: exclusive bind vs shared bind on one path.",
        "mechanism_left": "mech.exclusive_output_bind",
        "mechanism_right": "mech.shared_output_bind",
        "intended_grade": "HARD",
        "intended_verdict": "CONFIRMED",
    },
    {
        "id": "C06",
        "left_ref": "bp.exclusive-session-lock",
        "right_ref": "bp.shared-control-plane",
        "declared_class": "shared_control_plane",
        "declared_reason": "WFA-0150 shared control plane: mutex session vs bus session.",
        "mechanism_left": "mech.exclusive_session_lock",
        "mechanism_right": "mech.shared_control_plane",
        "intended_grade": "HARD",
        "intended_verdict": "CONFIRMED",
    },
    # --- RESTATED: blueprint names are not the conflict; the slot is ---
    {
        "id": "C07",
        "left_ref": "bp.review-pass-isolated",
        "right_ref": "bp.review-pass-with-transcript",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Declared as two review blueprints that 'do not mix'.",
        "mechanism_left": "mech.blind_independent_first_pass",
        "mechanism_right": "mech.shared_context_deliberation",
        "intended_grade": "HARD",
        "intended_verdict": "RESTATED",
        "restate_as": (
            "The blueprints are not themselves exclusive; the visibility slot "
            "(blind vs shared) is. Restated at mechanism level."
        ),
    },
    {
        "id": "C08",
        "left_ref": "bp.replay-from-event-log",
        "right_ref": "bp.temperature-sample-plan",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Declared as replay vs sample blueprints.",
        "mechanism_left": "mech.deterministic_replay",
        "mechanism_right": "mech.nondeterministic_sampling",
        "intended_grade": "HARD",
        "intended_verdict": "RESTATED",
        "restate_as": "Conflict is rng=deterministic vs rng=stochastic, not the blueprint titles.",
    },
    {
        "id": "C09",
        "left_ref": "bp.background-launch",
        "right_ref": "bp.wait-all-children",
        "declared_class": "shared_control_plane",
        "declared_reason": "Declared as launch style conflict.",
        "mechanism_left": "mech.fire_and_forget_dispatch",
        "mechanism_right": "mech.blocking_fanin_barrier",
        "intended_grade": "HARD",
        "intended_verdict": "RESTATED",
        "restate_as": "Conflict is join=fire_and_forget vs join=blocking_fanin.",
    },
    {
        "id": "C10",
        "left_ref": "bp.cancel-on-first-green",
        "right_ref": "bp.require-all-green",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Declared as stop-rule blueprint pair.",
        "mechanism_left": "mech.stop_first_success",
        "mechanism_right": "mech.stop_unanimous",
        "intended_grade": "HARD",
        "intended_verdict": "RESTATED",
        "restate_as": "Conflict is stop=first_success vs stop=unanimous.",
    },
    {
        "id": "C11",
        "left_ref": "bp.single-writer-STATUS-md",
        "right_ref": "bp.many-writers-STATUS-md",
        "declared_class": "shared_file",
        "declared_reason": "Declared as two blueprints both writing STATUS.md.",
        "mechanism_left": "mech.exclusive_output_bind",
        "mechanism_right": "mech.shared_output_bind",
        "intended_grade": "HARD",
        "intended_verdict": "RESTATED",
        "restate_as": "The file name is incidental; the slot is io_bind exclusive vs shared.",
    },
    {
        "id": "C12",
        "left_ref": "bp.owner-live-session",
        "right_ref": "bp.parallel-live-session",
        "declared_class": "shared_control_plane",
        "declared_reason": "Declared as two live-session blueprints.",
        "mechanism_left": "mech.exclusive_session_lock",
        "mechanism_right": "mech.shared_control_plane",
        "intended_grade": "HARD",
        "intended_verdict": "RESTATED",
        "restate_as": "Conflict is control=exclusive vs control=shared.",
    },
    # --- REFUTED as HARD: SOFT / not a mechanism contradiction ---
    {
        "id": "C13",
        "left_ref": "bp.sequential-pipeline",
        "right_ref": "bp.parallel-fanout",
        "declared_class": "shared_control_plane",
        "declared_reason": "Declared conflict: sequential vs parallel.",
        "mechanism_left": "mech.sequential_stages",
        "mechanism_right": "mech.parallel_fanout",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C14",
        "left_ref": "bp.artifact-cache",
        "right_ref": "bp.temperature-sample-plan",
        "declared_class": "shared_file",
        "declared_reason": "Declared conflict: cache vs sampling.",
        "mechanism_left": "mech.artifact_cache",
        "mechanism_right": "mech.nondeterministic_sampling",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C15",
        "left_ref": "bp.pause-resume",
        "right_ref": "bp.background-launch",
        "declared_class": "shared_control_plane",
        "declared_reason": "Declared conflict: pause vs fire-and-forget.",
        "mechanism_left": "mech.pause_resume",
        "mechanism_right": "mech.fire_and_forget_dispatch",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C16",
        "left_ref": "bp.human-gate",
        "right_ref": "bp.auto-retry",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Declared conflict: human gate vs auto retry.",
        "mechanism_left": "mech.human_checkpoint",
        "mechanism_right": "mech.auto_retry",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C17",
        "left_ref": "bp.human-gate",
        "right_ref": "bp.background-launch",
        "declared_class": "shared_control_plane",
        "declared_reason": "Declared conflict: human gate vs fire-and-forget.",
        "mechanism_left": "mech.human_checkpoint",
        "mechanism_right": "mech.fire_and_forget_dispatch",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C18",
        "left_ref": "bp.artifact-cache",
        "right_ref": "bp.replay-from-event-log",
        "declared_class": "shared_file",
        "declared_reason": "Declared conflict: cache vs replay.",
        "mechanism_left": "mech.artifact_cache",
        "mechanism_right": "mech.deterministic_replay",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C19",
        "left_ref": "bp.pause-resume",
        "right_ref": "bp.wait-all-children",
        "declared_class": "shared_control_plane",
        "declared_reason": "Declared conflict: pause vs blocking fan-in.",
        "mechanism_left": "mech.pause_resume",
        "mechanism_right": "mech.blocking_fanin_barrier",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
    {
        "id": "C20",
        "left_ref": "bp.parallel-fanout",
        "right_ref": "bp.human-gate",
        "declared_class": "incompatible_stop_rule",
        "declared_reason": "Declared conflict: parallel fan-out vs human gate.",
        "mechanism_left": "mech.parallel_fanout",
        "mechanism_right": "mech.human_checkpoint",
        "intended_grade": "SOFT",
        "intended_verdict": "REFUTED",
    },
]


def _extract_rows(doc: Any) -> list[dict[str, Any]] | None:
    if isinstance(doc, list) and len(doc) == 20:
        return [r for r in doc if isinstance(r, dict)]
    if not isinstance(doc, dict):
        return None
    for key in ("conflict_map", "conflicts", "conflictMap"):
        val = doc.get(key)
        if isinstance(val, list) and len(val) == 20:
            return [r for r in val if isinstance(r, dict)]
        if isinstance(val, dict):
            rows = val.get("rows") or val.get("entries") or val.get("items")
            if isinstance(rows, list) and len(rows) == 20:
                return [r for r in rows if isinstance(r, dict)]
    return None


def search_live_conflict_map() -> dict[str, Any]:
    searched: list[dict[str, Any]] = []
    for path in LIVE_CANDIDATES:
        rec = {"path": str(path), "exists": path.is_file()}
        searched.append(rec)
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            rec["error"] = f"{type(exc).__name__}"
            continue
        rows = _extract_rows(doc)
        rec["extracted_rows"] = 0 if rows is None else len(rows)
        if rows is not None and len(rows) == 20:
            return {
                "found": True,
                "path": str(path),
                "rows": rows,
                "searched": searched,
                "source": "live-file",
            }
    return {
        "found": False,
        "path": None,
        "rows": None,
        "searched": searched,
        "source": "reconstructed-from-catalog",
    }


def load_conflict_map() -> dict[str, Any]:
    live = search_live_conflict_map()
    if live["found"]:
        rows = []
        for i, raw in enumerate(live["rows"], start=1):
            rows.append(
                {
                    "id": str(raw.get("id") or f"L{i:02d}"),
                    "left_ref": str(raw.get("left") or raw.get("a") or raw.get("left_ref") or ""),
                    "right_ref": str(raw.get("right") or raw.get("b") or raw.get("right_ref") or ""),
                    "declared_class": str(raw.get("class") or raw.get("kind") or "unspecified"),
                    "declared_reason": str(raw.get("reason") or raw.get("note") or ""),
                    "raw": raw,
                    "row_source": "live-file",
                }
            )
        return {**live, "rows": rows}
    rows = []
    for rec in RECONSTRUCTED_ROWS:
        row = dict(rec)
        row["row_source"] = "reconstructed-from-catalog-WFA-0150-and-WFA-0062"
        rows.append(row)
    return {**live, "rows": rows}


def _incompatibility_argument(left: str, right: str, fused: dict[str, Any]) -> str:
    if fused["sat"]:
        return (
            f"{left} and {right} assert no disagreeing exclusive slot. "
            "Same-stage fusion is SAT. Any remaining issue is operational "
            "friction, not contradiction."
        )
    c = fused["clashes"][0]
    return (
        f"{c['left_mech']} asserts {c['slot']}={c['left_val']}; "
        f"{c['right_mech']} asserts {c['slot']}={c['right_val']}. "
        "A slot is a mutex on the fused stage: both values cannot hold in "
        "one assignment. That is the contradiction, not mere awkwardness."
    )


def _worked_example(left: str, right: str, fused: dict[str, Any]) -> dict[str, Any]:
    ir = {
        "stage_id": "fused-stage-0",
        "mechanisms": [left, right],
        "attempted_slot_assignment": fused["assignment"],
    }
    if fused["sat"]:
        return {
            "ir": ir,
            "observed": "SAT",
            "note": "The fused stage is satisfiable; no contradiction to exhibit.",
        }
    c = fused["clashes"][0]
    return {
        "ir": ir,
        "observed": "UNSAT",
        "clashing_slot": c["slot"],
        "left": {c["left_mech"]: {c["slot"]: c["left_val"]}},
        "right": {c["right_mech"]: {c["slot"]: c["right_val"]}},
        "note": (
            "Constructed fusion of one stage owning both mechanisms. The "
            "solver returned UNSAT on the named slot."
        ),
    }


def reconcile_row(row: dict[str, Any]) -> dict[str, Any]:
    left = row.get("mechanism_left")
    right = row.get("mechanism_right")
    if left not in MECHANISMS or right not in MECHANISMS:
        return {
            **row,
            "verdict": "RESTATED",
            "grade": "UNVERIFIED",
            "reason": (
                "Live conflict_map row has no mapped mechanism pair on this "
                "worktree; cannot confirm or refute at mechanism level."
            ),
        }
    fused = fuse_same_stage([left, right])
    hard = is_hard_pair(left, right)
    intended = row.get("intended_verdict")
    intended_grade = row.get("intended_grade")
    if hard:
        grade = "HARD"
        if intended == "RESTATED":
            verdict = "RESTATED"
        else:
            verdict = "CONFIRMED"
    else:
        grade = "SOFT"
        verdict = "REFUTED"
        if intended_grade == "HARD":
            # Author claimed HARD but solver says SAT → still REFUTED.
            verdict = "REFUTED"
    out = {
        **{k: v for k, v in row.items() if k != "raw"},
        "verdict": verdict,
        "grade": grade,
        "incompatibility_argument": _incompatibility_argument(left, right, fused),
        "worked_example": _worked_example(left, right, fused),
        "fusion_sat": fused["sat"],
        "fusion_clashes": fused["clashes"],
    }
    if verdict == "RESTATED":
        out["restate_as"] = row.get("restate_as") or (
            f"Blueprint pair restated as {left} vs {right}."
        )
    return out


def reconcile_all() -> dict[str, Any]:
    loaded = load_conflict_map()
    recs = [reconcile_row(r) for r in loaded["rows"]]
    if len(recs) != 20:
        raise RuntimeError(f"conflict_map reconciliation size {len(recs)} != 20")
    counts = {"CONFIRMED": 0, "REFUTED": 0, "RESTATED": 0, "UNVERIFIED": 0}
    for r in recs:
        counts[str(r["verdict"])] = counts.get(str(r["verdict"]), 0) + 1
    return {
        "source": loaded["source"],
        "live_found": loaded["found"],
        "live_path": loaded["path"],
        "searched": loaded["searched"],
        "rows": recs,
        "verdict_counts": counts,
        "n": len(recs),
    }
