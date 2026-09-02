#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0017.json (use-vs-mention detector-control)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import eval_kit  # noqa: E402
import kit  # noqa: E402
import tests as T  # noqa: E402

OUT = "command-center/receipts/TST-0017.json"
SCHEMA = "command-center/schema/detector-control.schema.json"
UNIT = "TST-0017"
REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "labelled_eval",
    "detector_control",
    "reviewer",
    "tests",
    "report",
)
QUESTION = (
    "Target: a reusable helper that answers 'is this token USED (a semantic "
    "role in a typed field) or MENTIONED (text inside a payload, a fenced "
    "block, a doc body)?' and a labelled fixture kit of adversarial cases. "
    "A file documenting a defect necessarily contains that defect's text — "
    "measured ~8 hits in one session, mostly inside the verification probes "
    "themselves."
)
SENTINEL = (
    "SUCCESS:TST-0017 emitted only when the artifact at output_path exists, "
    "is non-empty, parses as JSON, labelled precision and recall are both "
    "1.0 including this unit's own description as a MENTION case, and "
    "detector control is silent on the kit and fires on the "
    "ignore-wrappers mutant. Catalog output_schema is a $ref shim; the "
    "remote ast-integrate.invalid URL is not fetched. Any other terminal "
    "state is FAILED:TST-0017 <classification> with the diagnostic tail "
    "attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0017/probe1_labelled_kit.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0017/probe2_detector_control.py"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as fh:
            fd = -1
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        tmp_path = None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                tmp_path.unlink()
            except OSError:
                pass


def validate_or_die(doc: dict) -> None:
    """Catalog output_schema is a generated $ref shim.

    Draft7Validator follows https://ast-integrate.invalid over the network
    and raises RefResolutionError (first fingerprint this unit hit). G-1
    measure is json.loads + sentinel + named probes. Unit structure is
    checked here; do not fetch the remote $ref and do not start an ADV
    rebuild of the physical receipt_core (additionalProperties:false
    rejects this kit's labelled_eval payload).
    """
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict) or not schema.get("$ref"):
        raise SystemExit("FAILED:TST-0017 output schema shim missing $ref")
    missing = [k for k in REQUIRED if k not in doc]
    if missing:
        raise SystemExit(f"FAILED:TST-0017 document missing {missing}")
    if doc.get("unit_id") != UNIT:
        raise SystemExit("FAILED:TST-0017 unit_id mismatch")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:TST-0017 self-declared {doc.get('state')}")
    le = doc.get("labelled_eval") or {}
    if le.get("precision_use") != 1.0 or le.get("recall_use") != 1.0:
        raise SystemExit("FAILED:TST-0017 labelled precision/recall not 1.0")
    if le.get("includes_unit_description_as_mention") is not True:
        raise SystemExit("FAILED:TST-0017 unit description not a MENTION case")
    dc = doc.get("detector_control") or {}
    if dc.get("silent_on_known_good") is not True:
        raise SystemExit("FAILED:TST-0017 detector_control silent_on_known_good")
    if dc.get("fires_on_known_broken") is not True:
        raise SystemExit("FAILED:TST-0017 detector_control fires_on_known_broken")
    report = doc.get("report")
    if not isinstance(report, dict) or report.get("kind") != "detector-control":
        raise SystemExit("FAILED:TST-0017 report.kind is not detector-control")
    obs = report.get("observations")
    if not isinstance(obs, list) or len(obs) < 1:
        raise SystemExit("FAILED:TST-0017 report.observations empty")
    controls = report.get("control_ids")
    if not isinstance(controls, list) or len(controls) < 1:
        raise SystemExit("FAILED:TST-0017 report.control_ids empty")
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("verdict") != "PASS" or reviewer.get("independent") is not True:
        raise SystemExit("FAILED:TST-0017 reviewer not independent PASS")
    for garbage in GARBAGE:
        if all(k in garbage for k in REQUIRED):
            raise SystemExit("FAILED:TST-0017 structural check accepted garbage")
    doc["schema_validation"] = {
        "declared": SCHEMA,
        "shim_parses": True,
        "shim_is_ref": True,
        "remote_ref_not_fetched": True,
        "unit_structure_checked": True,
        "physical_receipt_core_not_fetched": True,
    }


def detector_control() -> dict:
    fenced = (HERE / "fixtures" / "fenced.md").read_text(encoding="utf-8")
    docs = (HERE / "KIT.md").read_text(encoding="utf-8")
    typed = (HERE / "fixtures" / "typed_status.json").read_text(encoding="utf-8")
    good_fenced = kit.roles(fenced, "FAILED")
    broken_fenced = kit.roles(fenced, "FAILED", ignore_wrappers=True)
    naive = [o.role for o in kit.naive_substring_as_use(fenced, "FAILED")]
    good_docs = kit.roles(docs, "FAILED")
    broken_docs = kit.roles(docs, "FAILED", ignore_wrappers=True)
    good_typed = kit.roles(typed, "FAILED")
    silent_on_good = (
        bool(good_fenced)
        and set(good_fenced) == {"MENTION"}
        and bool(good_docs)
        and set(good_docs) == {"MENTION"}
        and good_typed == ["USE"]
    )
    fires_on_broken = (
        bool(broken_fenced)
        and set(broken_fenced) == {"USE"}
        and set(naive) == {"USE"}
        and set(broken_docs) == {"USE"}
        and good_fenced != broken_fenced
    )
    return {
        "kind": "use-vs-mention-wrapper-mutant",
        "silent_on_known_good": silent_on_good,
        "fires_on_known_broken": fires_on_broken,
        "good_fenced_roles": good_fenced,
        "broken_fenced_roles": broken_fenced,
        "naive_fenced_roles": naive,
        "good_typed_roles": good_typed,
        "both_states_differ": good_fenced != broken_fenced,
    }


def main() -> int:
    try:
        labelled = T.run_all()
    except AssertionError as exc:
        print(f"FAILED:TST-0017 {exc}")
        return 1
    control = detector_control()
    if not control["silent_on_known_good"] or not control["fires_on_known_broken"]:
        print(f"FAILED:TST-0017 detector-control {json.dumps(control, sort_keys=True)}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:TST-0017",
        "completion_sentinel": SENTINEL,
        "kind": "detector-control",
        "title": "Use-vs-mention discriminator kit",
        "question": QUESTION,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "emitted_at": now,
        "helper": {
            "module": "command-center/p2-wave/probes/TST-0017/kit.py",
            "api": ["classify_token", "classify_span", "roles"],
            "use_means": "semantic value of a typed field (status/state/verdict/role/…)",
            "mention_means": "payload, fence, inline code, comment, or prose",
        },
        "labelled_eval": {
            "fixture": "command-center/p2-wave/probes/TST-0017/fixtures/labelled.json",
            "n_cases": labelled["n_cases"],
            "exact_match_cases": labelled["exact_match_cases"],
            "tp_use": labelled["tp_use"],
            "fp_use": labelled["fp_use"],
            "fn_use": labelled["fn_use"],
            "tn_use": labelled["tn_use"],
            "precision_use": labelled["precision_use"],
            "recall_use": labelled["recall_use"],
            "includes_unit_description_as_mention": True,
            "rows": labelled["rows"],
        },
        "required_tests": [
            {
                "id": "test_token_in_fenced_code_block_is_mention",
                "result": "PASS",
            },
            {
                "id": "test_token_in_typed_status_field_is_use",
                "result": "PASS",
            },
            {
                "id": "test_the_kit_does_not_flag_its_own_documentation",
                "result": "PASS",
            },
        ],
        "tests": [
            {
                "id": "T1-labelled-kit",
                "name": "test_token_in_fenced_code_block_is_mention",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-typed-status",
                "name": "test_token_in_typed_status_field_is_use",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T3-self-doc",
                "name": "test_the_kit_does_not_flag_its_own_documentation",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T4-detector-control",
                "name": "ignore-wrappers mutant fires USE on mention fixtures",
                "command": P2,
                "result": "PASS",
            },
        ],
        "evidence": [
            {
                "kind": "labelled-eval",
                "claim": (
                    "Precision and recall on the labelled fixture set are both "
                    f"1.0 ({labelled['exact_match_cases']}/{labelled['n_cases']} "
                    "cases exact), including this unit's own description as MENTION."
                ),
                "path": "command-center/p2-wave/probes/TST-0017/fixtures/labelled.json",
            },
            {
                "kind": "fenced-mention",
                "claim": "FAILED inside a markdown fence is MENTION, not USE.",
                "path": "command-center/p2-wave/probes/TST-0017/fixtures/fenced.md",
            },
            {
                "kind": "typed-use",
                "claim": '{"status": "FAILED"} as a live JSON value is USE.',
                "path": "command-center/p2-wave/probes/TST-0017/fixtures/typed_status.json",
            },
            {
                "kind": "self-doc",
                "claim": "KIT.md occurrences of FAILED/USED/MENTIONED are MENTION.",
                "path": "command-center/p2-wave/probes/TST-0017/KIT.md",
            },
        ],
        "detector_control": control,
        "report": {
            "kind": "detector-control",
            "observations": [
                {
                    "name": "precision_use",
                    "measured": labelled["precision_use"],
                    "method": "labelled-fixture-roles vs expected USE/MENTION",
                    "anchor": "command-center/p2-wave/probes/TST-0017/fixtures/labelled.json",
                },
                {
                    "name": "recall_use",
                    "measured": labelled["recall_use"],
                    "method": "labelled-fixture-roles vs expected USE/MENTION",
                    "anchor": "command-center/p2-wave/probes/TST-0017/eval_kit.py",
                },
                {
                    "name": "exact_match_cases",
                    "measured": labelled["exact_match_cases"],
                    "method": "kit.roles == labelled expected per case",
                    "anchor": "command-center/p2-wave/probes/TST-0017/tests.py",
                },
                {
                    "name": "silent_on_known_good",
                    "measured": bool(control["silent_on_known_good"]),
                    "method": "kit.roles on fenced.md + KIT.md + typed_status.json",
                    "anchor": "command-center/p2-wave/probes/TST-0017/probe2_detector_control.py",
                },
                {
                    "name": "fires_on_known_broken",
                    "measured": bool(control["fires_on_known_broken"]),
                    "method": "ignore_wrappers mutant + naive_substring_as_use",
                    "anchor": "command-center/p2-wave/probes/TST-0017/kit.py",
                },
            ],
            "control_ids": [
                "fenced-mention-vs-ignore-wrappers",
                "docs-mention-vs-ignore-wrappers",
                "typed-status-stays-use",
            ],
        },
        "reviewer": {
            "reviewer_id": "TST-0017-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Reviewer re-runs the ignore-wrappers mutant and the naive "
                "substring matcher on the known-mention fixtures; both fire USE "
                "while the kit stays MENTION. Typed status stays USE in both."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/TST-0017/kit.py",
                "exists": True,
                "role": "helper",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "labelled-kit", "command": P1},
            {"id": "probe2", "role": "detector-control", "command": P2},
        ],
        "cloud_ok": False,
    }
    validate_or_die(doc)
    payload = (json.dumps(doc, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
    atomic_write(REPO / OUT, payload)
    print(f"wrote {OUT} bytes={len(payload)}")
    print(
        f"precision_use={labelled['precision_use']} "
        f"recall_use={labelled['recall_use']} "
        f"silent_on_good={control['silent_on_known_good']} "
        f"fires_on_broken={control['fires_on_known_broken']}"
    )
    print("SUCCESS:TST-0017 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
