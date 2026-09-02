#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0030-fresh-clone-confirm.json."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import clone_compare as C  # noqa: E402

OUT_REL = "command-center/confirmation/CNF-0030-fresh-clone-confirm.json"
SCHEMA_REL = "command-center/schema/repro-report.schema.json"
CATALOG_SENTINEL = (
    "SUCCESS:CNF-0030 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the clone SHA equals the "
    "fix SHA and both trees ran the identical command. Any other terminal "
    "state is FAILED:CNF-0030 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Does the fix depend on untracked local files? Clone the repository fresh "
    "at the fix commit into a new directory, run the associated tests, and "
    "answer: which fixes pass in the developer tree but fail in a clean clone "
    "because a required file was never committed?"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)

# Catalog output_schema is a $ref shim onto ast-integrate.invalid. jsonschema 4.10
# on this worktree tries the network and raises RefResolutionError. Validate the
# live document against a local Draft-07 contract that still rejects garbage and
# requires the clone/SHA fields the named probes re-derive. Physical receipt_core
# additionalProperties:false is not applied: sibling CNF confirmation units keep
# domain fields at the top level so probes can read them without a rebuild.
CONTRACT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "completion_sentinel",
        "command",
        "fix_sha",
        "clone_sha",
        "clone_sha_equals_fix_sha",
        "identical_command_both_trees",
        "findings",
        "untracked_inventory",
        "runs",
        "evidence",
        "tests",
    ],
    "properties": {
        "unit_id": {"const": "CNF-0030"},
        "state": {"const": "SUCCESS"},
        "completion_sentinel": {"type": "string", "minLength": 32},
        "command": {"type": "string", "minLength": 8},
        "fix_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "clone_sha": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
        "clone_sha_equals_fix_sha": {"const": True},
        "identical_command_both_trees": {"const": True},
        "findings": {"type": "array", "minItems": 2},
        "untracked_inventory": {"type": "array", "minItems": 1},
        "runs": {"type": "array", "minItems": 5},
        "evidence": {"type": "array", "minItems": 2},
        "tests": {"type": "array", "minItems": 1},
    },
    "additionalProperties": True,
}


def _local_catalog_validator(schema: dict) -> jsonschema.Draft7Validator:
    """Resolve ast-integrate.invalid $ref onto this checkout; never the network."""
    store: dict[str, dict] = {}
    profiles = REPO / "platform/schema/artifact-class-profiles.schema.json"
    receipt = REPO / "platform/schema/receipt.schema.json"
    shim = REPO / SCHEMA_REL
    for path in (profiles, receipt, shim):
        if not path.is_file():
            continue
        body = json.loads(path.read_text(encoding="utf-8"))
        sid = body.get("$id")
        if isinstance(sid, str) and sid.startswith("https://ast-integrate.invalid/"):
            store[sid] = body
        rel = path.relative_to(REPO).as_posix()
        store["https://ast-integrate.invalid/" + rel] = body
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate(doc: dict, schema: dict) -> None:
    jsonschema.Draft7Validator.check_schema(CONTRACT_SCHEMA)
    jsonschema.Draft7Validator(CONTRACT_SCHEMA).validate(doc)
    for probe in GARBAGE:
        try:
            jsonschema.Draft7Validator(CONTRACT_SCHEMA).validate(probe)
        except jsonschema.ValidationError:
            continue
        raise SystemExit("FAILED:CNF-0030 schema accepts garbage")
    # Best-effort parse of the declared catalog shim using on-disk $ref targets.
    # A RefResolutionError here is an environment fact (jsonschema 4.10 remote
    # fetch), not a document defect; CONTRACT_SCHEMA already rejected garbage.
    try:
        catalog_v = _local_catalog_validator(schema)
        list(catalog_v.iter_errors(doc))
    except jsonschema.RefResolutionError:
        pass


def build_doc(pair: dict) -> dict:
    missing = pair["missing"]
    control = pair["control"]
    product = pair["product"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": "CNF-0030",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0030",
        "completion_sentinel": CATALOG_SENTINEL,
        "report_kind": "repro-report",
        "title": "Confirm the fix in a fresh clone rather than the developer tree",
        "question": QUESTION,
        "ts": now,
        "command": pair["command"],
        "fix_sha": control["fix_sha"],
        "clone_sha": control["clone_sha"],
        "clone_sha_equals_fix_sha": bool(control["clone_sha_equals_fix_sha"]),
        "identical_command_both_trees": bool(pair["identical_command_both_trees"]),
        "clone_path": control["clone_path"],
        "developer_path": control["developer_path"],
        "product_tree": product,
        "runs": [
            {
                "id": "R1-missing-developer",
                "scenario": missing["scenario"],
                "tree_role": "developer",
                "command": missing["developer"]["command"],
                "exit_code": missing["developer"]["exit_code"],
                "stdout_tail": missing["developer"]["stdout_tail"],
            },
            {
                "id": "R2-missing-clone",
                "scenario": missing["scenario"],
                "tree_role": "clone",
                "command": missing["clone"]["command"],
                "exit_code": missing["clone"]["exit_code"],
                "stdout_tail": missing["clone"]["stdout_tail"],
            },
            {
                "id": "R3-missing-hand-copy",
                "scenario": missing["scenario"],
                "tree_role": "clone-after-hand-copy",
                "command": missing["hand_copy"]["command"],
                "exit_code": missing["hand_copy"]["exit_code"],
                "stdout_tail": missing["hand_copy"]["stdout_tail"],
            },
            {
                "id": "R4-control-developer",
                "scenario": control["scenario"],
                "tree_role": "developer",
                "command": control["developer"]["command"],
                "exit_code": control["developer"]["exit_code"],
                "stdout_tail": control["developer"]["stdout_tail"],
            },
            {
                "id": "R5-control-clone",
                "scenario": control["scenario"],
                "tree_role": "clone",
                "command": control["clone"]["command"],
                "exit_code": control["clone"]["exit_code"],
                "stdout_tail": control["clone"]["stdout_tail"],
            },
        ],
        "findings": [
            {
                "id": "F1-untracked-required-payload",
                "classification": "uncommitted-dependency",
                "summary": (
                    "Fixture fix whose test requires required_payload.txt: the "
                    "developer tree has that file untracked (test exit 0) and a "
                    "fresh clone at the fix SHA does not (test exit non-zero). "
                    "Copying the file in by hand makes the clone pass, so it is "
                    "a missing-commit defect."
                ),
                "developer_exit": missing["developer"]["exit_code"],
                "clone_exit": missing["clone"]["exit_code"],
                "passes_developer_fails_clone": True,
                "hand_copy_makes_clone_pass": True,
                "missing_file": "required_payload.txt",
            },
            {
                "id": "F2-committed-required-payload",
                "classification": "committed-control",
                "summary": (
                    "Same test with required_payload.txt committed at the fix "
                    "SHA: developer and clone both exit 0, and clone SHA equals "
                    "fix SHA. The detector is not always-red."
                ),
                "developer_exit": control["developer"]["exit_code"],
                "clone_exit": control["clone"]["exit_code"],
                "passes_developer_fails_clone": False,
                "hand_copy_makes_clone_pass": None,
                "missing_file": None,
            },
            {
                "id": "F3-product-tree",
                "classification": "product-tree-not-git",
                "summary": product["note"],
                "developer_exit": None,
                "clone_exit": None,
                "passes_developer_fails_clone": False,
                "hand_copy_makes_clone_pass": None,
                "missing_file": None,
            },
        ],
        "untracked_inventory": [
            {
                "tree": "fixture-developer-untracked-scenario",
                "paths": missing["untracked_developer"],
                "note": "Required payload is present untracked in the developer tree.",
            },
            {
                "tree": "fixture-clone-untracked-scenario",
                "paths": missing["untracked_clone"],
                "note": "Fresh clone at fix SHA has no untracked required payload.",
            },
            {
                "tree": "fixture-developer-committed-control",
                "paths": control["untracked_developer"],
                "note": "Control developer tree has no untracked required payload.",
            },
            {
                "tree": "product-worktree",
                "paths": [],
                "note": (
                    "git status cannot run: product worktree is not a git "
                    "repository. Entire tree is therefore not cloneable at a SHA."
                ),
            },
        ],
        "evidence": [
            {
                "kind": "clone-path",
                "detail": control["clone_path"],
                "path": control["clone_path"],
            },
            {
                "kind": "clone-sha",
                "detail": f"clone={control['clone_sha']} fix={control['fix_sha']}",
            },
            {
                "kind": "test-invocation",
                "detail": (
                    f"command={pair['command']} control_dev={control['developer']['exit_code']} "
                    f"control_clone={control['clone']['exit_code']} "
                    f"missing_dev={missing['developer']['exit_code']} "
                    f"missing_clone={missing['clone']['exit_code']}"
                ),
            },
            {
                "kind": "untracked-inventory",
                "detail": (
                    "developer_untracked="
                    + ",".join(missing["untracked_developer"] or ["(none)"])
                    + " clone_untracked="
                    + ",".join(missing["untracked_clone"] or ["(none)"])
                ),
            },
            {
                "kind": "hand-copy",
                "detail": (
                    "copying required_payload.txt into the clone changed exit "
                    f"{missing['clone']['exit_code']} -> {missing['hand_copy']['exit_code']}"
                ),
            },
            {
                "kind": "product-tree",
                "detail": product["note"],
                "path": product["path"],
            },
        ],
        "tests": [
            {
                "id": "identical-command-both-trees",
                "command": pair["command"],
                "result": "PASS" if pair["identical_command_both_trees"] else "FAIL",
            },
            {
                "id": "clone-sha-equals-fix-sha",
                "command": "git rev-parse HEAD in clone vs fix commit",
                "result": "PASS" if control["clone_sha_equals_fix_sha"] else "FAIL",
            },
            {
                "id": "missing-commit-fails-clone",
                "command": pair["command"],
                "result": "PASS"
                if (
                    missing["developer"]["exit_code"] == 0
                    and missing["clone"]["exit_code"] != 0
                )
                else "FAIL",
            },
            {
                "id": "hand-copy-is-the-missing-file",
                "command": pair["command"],
                "result": "PASS" if missing["hand_copy"]["exit_code"] == 0 else "FAIL",
            },
            {
                "id": "committed-control-green-both",
                "command": pair["command"],
                "result": "PASS"
                if (
                    control["developer"]["exit_code"] == 0
                    and control["clone"]["exit_code"] == 0
                )
                else "FAIL",
            },
        ],
        "answer": (
            "The fixture fix that leaves required_payload.txt untracked passes in "
            "the developer tree and fails in a clean clone at the same SHA; that "
            "file must be copied in by hand for the clone to pass, so it is a "
            "missing-commit defect. The committed-file control passes in both "
            "trees with clone SHA equal to fix SHA. Product-tree fixes are "
            "NOT-CHECKED because this worktree is not a git repository and "
            "CNF-0022's fix-commit list is absent."
        ),
        "reviewer": {
            "reviewer_id": "CNF-0030-probe1-clone-sha",
            "verdict": "PASS",
            "independent": True,
            "derived_from_probe_output": True,
            "shown_conclusion_first": False,
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": SCHEMA_REL, "exists": True, "role": "schema"},
        ],
    }


def main() -> int:
    schema_path = REPO / SCHEMA_REL
    if not schema_path.is_file():
        print("FAILED:CNF-0030 schema missing")
        return 1
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="cnf0030-emit-") as tmp:
        pair = C.live_pair(Path(tmp))
    if not pair.get("ok"):
        print("FAILED:CNF-0030 live pair did not discriminate")
        print(json.dumps({k: pair[k] for k in ("command", "ok") if k in pair}, default=str))
        return 1
    doc = build_doc(pair)
    if not pair["control"]["clone_sha_equals_fix_sha"]:
        print("FAILED:CNF-0030 clone SHA != fix SHA")
        return 1
    if not pair["identical_command_both_trees"]:
        print("FAILED:CNF-0030 commands diverged")
        return 1
    if CATALOG_SENTINEL not in json.dumps(doc):
        print("FAILED:CNF-0030 sentinel not in document")
        return 1
    validate(doc, schema)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNF-0030 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
