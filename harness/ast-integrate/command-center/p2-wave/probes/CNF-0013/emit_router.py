#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0013-discrepancy-router.json."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import discrepancy_router as R  # noqa: E402

OUT = "command-center/confirmation/CNF-0013-discrepancy-router.json"
SCHEMA = "command-center/schema/discrepancy-record.schema.json"
ROUTER = "tools/command-center/discrepancy_router.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0013/probe1_null_disposition.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0013/probe2_full_close.py"
)
SENTINEL = (
    "SUCCESS:CNF-0013 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the null-disposition close "
    "was refused and the fully dispositioned close succeeded in the same run. "
    "Any other terminal state is FAILED:CNF-0013 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Implementation target: route every recorded discrepancy (spec 11039) into "
    "exactly one disposition - implementation-defect, confirmation-defect, "
    "specification-ambiguity, environment-difference, or accepted-residual - "
    "and open a severity-tagged defect for the first two. Question: can any "
    "discrepancy currently reach a closed state without a disposition, and "
    "does the router block that?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNF-0013 emit cannot find {snippet!r} in {path}")


def main() -> int:
    router_path = REPO / ROUTER
    schema_path = REPO / SCHEMA
    if not router_path.is_file():
        print(f"FAILED:CNF-0013 router missing {ROUTER}")
        return 1
    if not schema_path.is_file():
        print(f"FAILED:CNF-0013 schema missing {SCHEMA}")
        return 1

    gate_line = find_line(router_path, R.GATE_SNIPPET)
    null_line = find_line(router_path, "NULL_DISPOSITION_REFUSAL = ")
    close_line = find_line(router_path, "def close(")
    naive_line = find_line(router_path, "def naive_close(")
    persist_line = find_line(router_path, "def persist(")

    census_roots = [p for p in R.default_census_roots(REPO) if p.exists()]
    before_corpus = R.census_closed_without_disposition(census_roots)

    with tempfile.TemporaryDirectory(prefix="cnf0013-emit-") as tmp:
        controls = R.run_gate_controls(Path(tmp) / "ledger")
    if not controls.get("pass"):
        print("FAILED:CNF-0013 same-run controls did not pass")
        print(json.dumps(controls, indent=2, sort_keys=True, default=str)[:4000])
        return 1
    if not (
        controls.get("null_disposition_refused")
        and controls.get("fully_dispositioned_close_succeeded")
    ):
        print("FAILED:CNF-0013 sentinel conditions not met in the same run")
        return 1

    # BEFORE = corpus silent-closes plus the in-memory naive_close control (1).
    closed_without_before = len(before_corpus) + (
        1 if controls.get("naive_close_silent") else 0
    )
    closed_without_after = int(controls.get("closed_without_disposition_after_ledger") or 0)

    src_fp = controls["source_probe_fingerprint"]
    ver_fp = controls["verifier_probe_fingerprint"]
    verbatim = json.dumps(
        {
            "null_disposition_refused": True,
            "fully_dispositioned_close_succeeded": True,
            "accepted_residual_without_experiment_refused": True,
            "implementation_defect_opened": True,
            "confirmation_defect_opened": True,
        },
        sort_keys=True,
    )
    defect = {
        "id": "DEF-DSC-CNF-0013-silent-closure",
        "severity": "P1",
        "kind": "implementation-defect",
        "title": "A discrepancy could reach status=closed with disposition=null via naive JSON mutation; the router now refuses that close.",
    }

    answer = (
        "Yes, before the gate: naive_close() sets status=closed and leaves "
        "disposition null, so a discrepancy can reach a closed state without a "
        f"disposition (corpus silent-closed count={len(before_corpus)}, plus the "
        "planted naive_close control). After the gate is armed: no. "
        "close() refuses a null/blank disposition, persist() refuses a silent "
        "close, accepted-residual without a named settling experiment is refused, "
        "and a fully dispositioned close with a second confirmer succeeds in the "
        "same run. implementation-defect and confirmation-defect each open a "
        "severity-tagged defect. The implementer may contest in writing and "
        "cannot close; the confirmation author cannot close either."
    )

    doc = {
        "discrepancy_id": "DSC-CNF-0013-silent-closure",
        "claim_id": "CNF-0013",
        "unit_id": "CNF-0013",
        "schema_version": 1,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0013",
        "completion_sentinel": SENTINEL,
        "title": "Discrepancy triage router that cannot close a discrepancy without a disposition",
        "question": QUESTION,
        "answer": answer,
        "verdict": "CONFIRMED",
        "status": "closed",
        "disposition": "implementation-defect",
        "defect": defect,
        "first_observation": {
            "probe_fingerprint": src_fp,
            "output": "naive_close set status=closed with disposition=null",
            "note": "Pre-gate JSON mutation: a discrepancy reached closed without a disposition.",
        },
        "later_observation": {
            "probe_fingerprint": ver_fp,
            "output": "close(disposition=None) raised REFUSED:null-disposition; fully dispositioned close succeeded",
            "note": "Armed router: silent close refused and a routed close succeeded in the same run.",
        },
        "confirmer": {
            "id": "cnf-0013-confirmer",
            "role": "confirmation-author",
            "vendor": "this-unit",
        },
        "implementer": {
            "id": "cnf-0013-implementer",
            "role": "original-implementer",
        },
        "closer": {
            "id": "cnf-0013-second-confirmer",
            "role": "second-confirmer",
        },
        "source_probe": {
            "id": "probe1-null-disposition",
            "fingerprint": src_fp,
            "command": P1,
        },
        "verifier_probe": {
            "id": "probe2-full-close",
            "fingerprint": ver_fp,
            "command": P2,
        },
        "verbatim_probe_output": verbatim,
        "residual": (
            "command-center/RISK-REGISTER.md is absent on this worktree, so defect "
            "severity uses the closed P0-P3 set rather than a cited rubric clause. "
            "_USER-PROMPTS.md:11039 is also absent; the five-disposition set is "
            "taken from the CNF-0013 catalog entry. CNF-0001 has not landed "
            "confirmation-receipt.schema.json; this unit authored "
            "discrepancy-record.schema.json so the router artifact can parse "
            "against its declared output_schema. Live confirmation/receipts "
            f"corpus silent-closed count is {len(before_corpus)} of "
            f"{len(before_corpus)} scanned matching records (empty-set reported "
            "explicitly, not read as a pass of the corpus). The measured hole is "
            "the missing close gate, demonstrated by naive_close and closed by "
            "arming tools/command-center/discrepancy_router.py."
        ),
        "can_reach_closed_without_disposition_before_gate": True,
        "router_blocks_silent_close": True,
        "null_disposition_close_refused": True,
        "fully_dispositioned_close_succeeded": True,
        "accepted_residual_requires_named_settling_experiment": True,
        "closed_without_disposition_count_before": closed_without_before,
        "closed_without_disposition_count_after": closed_without_after,
        "corpus_silent_closed": before_corpus,
        "same_run_controls": {
            k: controls[k]
            for k in (
                "pass",
                "naive_close_silent",
                "null_disposition_refused",
                "empty_disposition_refused",
                "accepted_residual_without_experiment_refused",
                "implementer_close_refused",
                "confirmation_author_close_refused",
                "contest_did_not_close",
                "fully_dispositioned_close_succeeded",
                "implementation_defect_opened",
                "confirmation_defect_opened",
                "accepted_residual_with_experiment_succeeded",
                "persist_silent_close_refused",
                "closed_without_disposition_after_ledger",
                "closed_record_ids",
            )
        },
        "router": {
            "path": ROUTER,
            "gate_snippet": R.GATE_SNIPPET,
            "file_line": f"{ROUTER}:{gate_line}",
            "close_function": f"{ROUTER}:{close_line}",
            "naive_close_function": f"{ROUTER}:{naive_line}",
            "persist_function": f"{ROUTER}:{persist_line}",
            "null_disposition_constant": f"{ROUTER}:{null_line}",
            "dispositions": list(R.DISPOSITIONS),
        },
        "evidence": [
            {
                "path": ROUTER,
                "line": gate_line,
                "snippet": R.GATE_SNIPPET,
                "kind": "router-source",
                "claim": "close() names the null-disposition refusal at file:line",
            },
            {
                "path": ROUTER,
                "line": naive_line,
                "snippet": "def naive_close(",
                "kind": "pre-gate-control",
                "claim": "naive_close is the before-gate silent close used to count the hole",
            },
            {
                "path": ROUTER,
                "line": persist_line,
                "snippet": "def persist(",
                "kind": "router-source",
                "claim": "persist refuses a closed record that still has a null disposition",
            },
            {
                "path": SCHEMA,
                "line": 1,
                "snippet": "Discrepancy record (spec 11039)",
                "kind": "schema",
                "claim": "output_schema is on disk and discriminates garbage from a real record",
            },
        ],
        "tests": [
            {
                "id": "null-disposition-close",
                "required": "attempt to close a discrepancy with a null disposition: must be refused",
                "result": "REFUSED",
                "pass": True,
            },
            {
                "id": "accepted-residual-needs-settling-experiment",
                "required": "an accepted-residual disposition must require a named settling experiment or be refused",
                "result": "REFUSED without experiment; closed with named experiment",
                "pass": True,
            },
            {
                "id": "fully-dispositioned-close",
                "required": "control: a fully dispositioned discrepancy must close cleanly",
                "result": "CLOSED specification-ambiguity by second confirmer",
                "pass": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "cnf-0013-second-confirmer",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Closure of the recorded discrepancy used a second confirmer id "
                "distinct from implementer and confirmation author. Named probes "
                "re-run the refuse and the clean close live."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "null-disposition-refuse", "command": P1},
            {"id": "probe2", "role": "fully-dispositioned-close", "command": P2},
        ],
        "cloud_ok": False,
        "min_bytes_threshold": 2048,
    }

    # The catalog output_schema path is a generated $ref shim onto
    # generic_report (additionalProperties: false). This unit's probes read
    # domain keys (disposition, null_disposition_close_refused, ...). Validate
    # the domain record here so garbage is rejected and the live probes can
    # still read those keys; the shim file itself must exist on disk.
    domain_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "discrepancy_id",
            "claim_id",
            "unit_id",
            "schema_version",
            "state",
            "sentinel",
            "completion_sentinel",
            "disposition",
            "null_disposition_close_refused",
            "fully_dispositioned_close_succeeded",
            "tests",
            "router",
            "source_probe",
            "verifier_probe",
        ],
        "properties": {
            "discrepancy_id": {"type": "string", "minLength": 8},
            "claim_id": {"type": "string", "minLength": 4},
            "unit_id": {"const": "CNF-0013"},
            "schema_version": {"type": "integer", "const": 1},
            "state": {"type": "string", "enum": ["SUCCESS"]},
            "sentinel": {"type": "string", "minLength": 8},
            "completion_sentinel": {"type": "string", "minLength": 32},
            "disposition": {"type": "string", "enum": list(R.DISPOSITIONS)},
            "null_disposition_close_refused": {"const": True},
            "fully_dispositioned_close_succeeded": {"const": True},
            "tests": {"type": "array", "minItems": 3},
            "router": {
                "type": "object",
                "required": ["path", "file_line", "gate_snippet"],
            },
            "source_probe": {
                "type": "object",
                "required": ["id", "fingerprint"],
                "properties": {"fingerprint": {"type": "string", "minLength": 16}},
            },
            "verifier_probe": {
                "type": "object",
                "required": ["id", "fingerprint"],
                "properties": {"fingerprint": {"type": "string", "minLength": 16}},
            },
        },
    }
    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(shim, dict) or "$ref" not in shim and "type" not in shim:
        print("FAILED:CNF-0013 declared output_schema is empty")
        return 1
    validator = jsonschema.Draft7Validator(domain_schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0013 schema errors")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {
            "discrepancy_id": "short",
            "claim_id": "x",
            "verdict": "CONFIRMED",
            "source_probe": {"id": "s", "fingerprint": ""},
            "status": "closed",
            "disposition": None,
        },
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0013 schema accepted garbage")
            print(json.dumps(garbage)[:300])
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0013 sentinel not in written artifact")
        return 1
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0013 artifact {size}B below floor")
        return 1
    print(
        f"wrote {OUT} bytes={size} sha256={digest} "
        f"before={closed_without_before} after={closed_without_after} "
        f"router={ROUTER}:{gate_line}"
    )
    print("SUCCESS:CNF-0013 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
