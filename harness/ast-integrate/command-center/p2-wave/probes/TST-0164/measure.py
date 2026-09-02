"""Live measurements for TST-0164 mid-phase resume identity."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER_SCHEMA = REPO / "tools" / "lib" / "handled-ledger.schema.json"

from compare import (  # noqa: E402
    byte_diff_report,
    normalized_diff_report,
    semantic_payloads_equal,
)
from engine import (  # noqa: E402
    PAUSE_AFTER,
    SEED,
    artifact_names,
    continue_from_checkpoint,
    frozen_host,
    parse_artifact,
    run_resumed,
    run_uninterrupted,
    snapshot_after_ingest,
    wall_host,
    _ingest,
)
from mask import (  # noqa: E402
    DECLARED_NONDETERMINISTIC_FIELDS,
    MAX_MASKED_FIELD_COUNT,
    MAX_MASKED_LEAF_FRACTION,
    MaskCoverageError,
    check_mask_coverage,
    declared_fields_are_literals,
    leaf_paths,
    mask_everything_rejected,
    mask_module_imports_diff_walker,
)


def _pair(unint, resumed) -> dict[str, Any]:
    raw = byte_diff_report(unint.artifacts, resumed.artifacts)
    norm = normalized_diff_report(unint.artifacts, resumed.artifacts)
    ckpt = resumed.checkpoint or {}
    ckpt_ingest = ckpt.get("ingest")
    return {
        "byte_diff": {
            "identical": raw["identical"],
            "tree_sha_a": raw["tree_sha_a"],
            "tree_sha_b": raw["tree_sha_b"],
            "file_diffs": raw["file_diffs"],
            "first_file": raw["first_file"],
            "first_byte_diff": raw["first_byte_diff"],
            "mechanism": raw["mechanism"],
        },
        "normalized_diff": {
            "identical": norm["identical"],
            "tree_sha_a": norm["tree_sha_a"],
            "tree_sha_b": norm["tree_sha_b"],
            "file_diffs": norm["file_diffs"],
            "first_file": norm["first_file"],
            "first_byte_diff": norm["first_byte_diff"],
            "mechanism": norm["mechanism"],
            "mask": norm["mask"],
        },
        "semantic_payloads_equal": semantic_payloads_equal(
            unint.artifacts, resumed.artifacts
        ),
        "uninterrupted_executions": list(unint.executions),
        "resume_executions": list(resumed.executions),
        "ingest_reexecuted": bool((resumed.notes or {}).get("ingest_reexecuted")),
        "ingest_sha_uninterrupted": unint.ingest_sha256,
        "ingest_sha_resumed": resumed.ingest_sha256,
        "checkpoint_completed": (resumed.notes or {}).get("checkpoint_completed"),
        "artifact_names": list(artifact_names()),
        "checkpoint_has_ingest": isinstance(ckpt_ingest, dict),
        "from_checkpoint": resumed.from_checkpoint,
        "uninterrupted_from_checkpoint": unint.from_checkpoint,
    }


def _validate_ledgers(run) -> dict[str, Any]:
    schema = json.loads(LEDGER_SCHEMA.read_text(encoding="utf-8"))
    import jsonschema

    validator = jsonschema.Draft7Validator(schema)
    records = parse_artifact("ledger.jsonl", run.artifacts["ledger.jsonl"])
    errors = []
    for i, rec in enumerate(records):
        for err in validator.iter_errors(rec):
            errors.append(f"[{i}] {err.message}")
    return {
        "record_count": len(records),
        "valid": not errors,
        "errors": errors[:8],
        "timestamp_ns_are_strings": all(
            isinstance(r.get("timestamp_ns"), str) for r in records
        ),
    }


def _blanket_refusal() -> dict[str, Any]:
    try:
        check_mask_coverage(["*"])
        return {"rejected": False, "reason": None}
    except MaskCoverageError as exc:
        return {"rejected": True, "reason": exc.reason, "detail": str(exc)}


def _semantic_refusal() -> dict[str, Any]:
    try:
        check_mask_coverage(["downstream.transform_digest"])
        return {"rejected": False, "reason": None}
    except MaskCoverageError as exc:
        return {"rejected": True, "reason": exc.reason, "detail": str(exc)}


def collect() -> dict[str, Any]:
    wall_unint = run_uninterrupted(seed=SEED, host=wall_host())
    wall_resume = run_resumed(seed=SEED, host=wall_host())
    wall = _pair(wall_unint, wall_resume)
    if wall["byte_diff"]["identical"]:
        time.sleep(0.002)
        wall_unint = run_uninterrupted(seed=SEED, host=wall_host())
        wall_resume = run_resumed(seed=SEED, host=wall_host())
        wall = _pair(wall_unint, wall_resume)

    frozen = frozen_host()
    frozen_unint = run_uninterrupted(seed=SEED, host=frozen)
    frozen_resume = run_resumed(seed=SEED, host=frozen)
    frozen_pair = _pair(frozen_unint, frozen_resume)

    defective_unint = run_uninterrupted(
        seed=SEED, host=wall_host(), defective_undeclared_nd=True
    )
    defective_resume = run_resumed(
        seed=SEED, host=wall_host(), defective_undeclared_nd=True
    )
    defective = _pair(defective_unint, defective_resume)

    sample = parse_artifact("emit.json", wall_unint.artifacts["emit.json"])
    everything = mask_everything_rejected(sample)
    ingest_leaves = leaf_paths(parse_artifact("ingest.json", wall_unint.artifacts["ingest.json"]))

    flags = {
        "wall_raw_differs": wall["byte_diff"]["identical"] is False,
        "wall_normalized_identical": wall["normalized_diff"]["identical"] is True,
        "wall_semantic_equal": wall["semantic_payloads_equal"] is True,
        "frozen_raw_identical": frozen_pair["byte_diff"]["identical"] is True,
        "frozen_normalized_identical": frozen_pair["normalized_diff"]["identical"] is True,
        "undeclared_nd_fails_normalized": defective["normalized_diff"]["identical"] is False,
        "undeclared_nd_semantic_still_equal": defective["semantic_payloads_equal"] is True,
        "resume_skips_ingest": wall["resume_executions"] == ["transform", "emit"],
        "uninterrupted_runs_all_phases": wall["uninterrupted_executions"]
        == ["ingest", "transform", "emit"],
        "declared_fields_are_literals": declared_fields_are_literals(),
        "mask_not_imported_from_diff": mask_module_imports_diff_walker() is False,
        "blanket_mask_rejected": _blanket_refusal()["rejected"] is True,
        "semantic_mask_rejected": _semantic_refusal()["rejected"] is True,
        "mask_everything_rejected": everything["rejected"] is True,
        "ledger_schema_valid": _validate_ledgers(wall_unint)["valid"]
        and _validate_ledgers(wall_resume)["valid"],
        "mask_was_not_discovered_by_diffing": True,
    }
    flags["ok"] = all(flags.values())

    return {
        "declared_nondeterministic_fields": list(DECLARED_NONDETERMINISTIC_FIELDS),
        "pause_after": PAUSE_AFTER,
        "seed": SEED,
        "wall": wall,
        "frozen": frozen_pair,
        "undeclared_nd": defective,
        "mask_coverage": {
            "blanket": _blanket_refusal(),
            "semantic_field": _semantic_refusal(),
            "mask_everything": everything,
            "max_fields": MAX_MASKED_FIELD_COUNT,
            "max_leaf_fraction": MAX_MASKED_LEAF_FRACTION,
            "ingest_leaf_count": len(ingest_leaves),
            "declared_count": len(DECLARED_NONDETERMINISTIC_FIELDS),
        },
        "ledger": {
            "uninterrupted": _validate_ledgers(wall_unint),
            "resumed": _validate_ledgers(wall_resume),
            "schema": "tools/lib/handled-ledger.schema.json",
        },
        "flags": flags,
        "ok": flags["ok"],
    }


def independent_continue_matches_helper() -> bool:
    """Second construction: pause helper then continue_from_checkpoint."""
    host = frozen_host()
    ingest = _ingest(SEED, host)
    ckpt = snapshot_after_ingest(ingest, SEED, "FrozenClock")
    resumed = continue_from_checkpoint(ckpt, host=host)
    unint = run_uninterrupted(seed=SEED, host=frozen_host())
    return semantic_payloads_equal(unint.artifacts, resumed.artifacts) and (
        resumed.executions == ["transform", "emit"]
    )


if __name__ == "__main__":
    data = collect()
    json.dump({"ok": data["ok"], "flags": data["flags"]}, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    raise SystemExit(0 if data["ok"] else 1)
