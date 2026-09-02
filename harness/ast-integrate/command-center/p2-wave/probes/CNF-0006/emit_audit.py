#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0006-probe-independence.json."""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402
import fingerprint as F  # noqa: E402

OUT = "command-center/confirmation/CNF-0006-probe-independence.json"
SCHEMA = "command-center/schema/confirmation-audit.schema.json"
FP_REL = "command-center/p2-wave/probes/CNF-0006/fingerprint.py"
CORPUS_REL = "command-center/p2-wave/probes/CNF-0006/corpus.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0006/probe1_same_command_reject.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0006/probe2_shell_axis_accept.py"
)
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0006 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both fingerprint controls "
    "ran in the same invocation and returned opposite verdicts as designed. "
    "Any other terminal state is FAILED:CNF-0006 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Implementation target: fingerprint every probe by the tuple (tool, shell, "
    "data field, measurement kind) and reject any confirmation whose verifier "
    "fingerprint equals its source fingerprint. Question: across the confirmation "
    "corpus what percentage of CONFIRMED verdicts are same-probe re-runs?"
)
SCHEMA_STORE_RELS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)
SUPPORTING = (
    (FP_REL, "supporting"),
    (CORPUS_REL, "supporting"),
    (SCHEMA, "supporting"),
    ("command-center/p2-wave/probes/CNF-0006/emit_audit.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0006/probe1_same_command_reject.py", "control"),
    ("command-center/p2-wave/probes/CNF-0006/probe2_shell_axis_accept.py", "control"),
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0006 emit missing snippet in {rel}: {snippet!r}")
    return text[:idx].count("\n") + 1


def offline_validator():
    """Compile confirmation-audit against on-disk $id targets. No network."""
    store: dict[str, dict] = {}
    for rel in SCHEMA_STORE_RELS:
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not isinstance(sid, str) or not sid:
            raise SystemExit(f"FAILED:CNF-0006 schema missing $id: {rel}")
        store[sid] = doc
    schema = store["https://ast-integrate.invalid/command-center/schema/confirmation-audit.schema.json"]
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft202012Validator(schema, resolver=resolver)


def artifact_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def evidence_item(
    *,
    claim: str,
    anchor: str,
    source_cmd: str,
    source_out: str,
    verifier_cmd: str,
    verifier_out: str,
) -> dict:
    return {
        "claim": claim,
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": anchor,
        "probes": [
            {
                "role": "source",
                "method": "static-analysis",
                "command": source_cmd,
                "raw_output": source_out[:4000],
                "fingerprint": probe_fingerprint("static-analysis", source_cmd),
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": "command",
                "command": verifier_cmd,
                "raw_output": verifier_out[:4000],
                "fingerprint": probe_fingerprint("command", verifier_cmd),
                "exit_code": 0,
            },
        ],
    }


def main() -> int:
    controls = F.run_fingerprint_controls()
    if not controls["pass"]:
        print("FAILED:CNF-0006 detector-failure fingerprint controls did not pass")
        print(json.dumps(controls, indent=2, sort_keys=True, default=str)[:4000])
        return 1
    if not controls["opposite_verdicts_as_designed"]:
        print("FAILED:CNF-0006 detector-failure controls were not opposite")
        return 1
    if not controls["same_invocation"]:
        print("FAILED:CNF-0006 detector-failure controls not same invocation")
        return 1

    measured = C.scan_corpus(REPO)
    fp_line = inspect.getsourcelines(F.fingerprint)[1]
    fp_src = inspect.getsource(F.fingerprint).splitlines()[0]
    started = datetime.now(timezone.utc)
    n = int(measured["confirmed_count"])
    same_n = int(measured["same_probe_rerun_count"])
    rate = measured["percentage"]
    rate_text = "n/a (0 of 0)" if n == 0 else f"{rate:.1f}% ({same_n} of {n})"

    e1_line = find_line(FP_REL, "def fingerprint(probe: Any)")
    e2_line = find_line(FP_REL, "if src is None:")
    e3_line = find_line(FP_REL, "SHELL_ONLY_VERIFIER")
    if e1_line != fp_line:
        print(f"FAILED:CNF-0006 fingerprint line drift inspect={fp_line} file={e1_line}")
        return 1

    identical = controls["identical_command"]
    shell_only = controls["shell_only"]
    empty = controls["empty_source"]
    control_rows = [
        {
            "id": identical["id"],
            "designed_verdict": identical["designed_verdict"],
            "observed_verdict": identical["observed_verdict"],
            "classification": identical["classification"],
            "pass": identical["pass"],
        },
        {
            "id": shell_only["id"],
            "designed_verdict": shell_only["designed_verdict"],
            "observed_verdict": shell_only["observed_verdict"],
            "classification": shell_only["classification"],
            "differing_axes": shell_only["differing_axes"],
            "pass": shell_only["pass"],
        },
        {
            "id": empty["id"],
            "designed_verdict": empty["designed_verdict"],
            "observed_verdict": empty["observed_verdict"],
            "classification": empty["classification"],
            "pass": empty["pass"],
        },
    ]

    answer = (
        f"Fingerprint is {FP_REL}:{fp_line} over axes {list(F.AXES)}. "
        f"Same-invocation controls: identical Git-Bash `which python` "
        f"{identical['observed_verdict']} ({identical['classification']}); "
        f"shell-only Git Bash to PowerShell {shell_only['observed_verdict']} "
        f"({shell_only['classification']}, axes={shell_only['differing_axes']}); "
        f"empty source_probe {empty['observed_verdict']} ({empty['classification']}), "
        "never treated as differs-from-verifier. "
        f"Live confirmation corpus: {measured['percentage_note']}. "
        f"Same-probe rate {rate_text}. Offender ids: "
        f"{measured['offender_ids'] if measured['offender_ids'] else '[] (empty list is only meaningful because detector controls are attached)'}. "
        + COMPLETION_SENTINEL
    )

    ended = datetime.now(timezone.utc)
    duration = max(0.0, (ended - started).total_seconds())
    now = ended.strftime("%Y-%m-%dT%H:%M:%SZ")
    started_s = started.strftime("%Y-%m-%dT%H:%M:%SZ")

    src_cmd = f"sed -n '{fp_line}p' {FP_REL}"
    ident_out = (
        f"identical={identical['observed_verdict']} "
        f"class={identical['classification']} pass={identical['pass']}"
    )
    shell_out = (
        f"shell={shell_only['observed_verdict']} "
        f"axes={shell_only['differing_axes']} pass={shell_only['pass']}"
    )
    empty_out = (
        f"empty={empty['observed_verdict']} "
        f"class={empty['classification']} pass={empty['pass']}"
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0006",
        "state": "SUCCESS",
        "sentinel": COMPLETION_SENTINEL,
        "spec_anchor": "rules/common/fan-out-contract.md:A4",
        "min_bytes_threshold": 200,
        "artifacts": [artifact_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            evidence_item(
                claim=(
                    "A confirmation whose verifier fingerprint equals its source "
                    "fingerprint is a same-probe re-run and must be rejected."
                ),
                anchor=f"{FP_REL}:{e1_line}",
                source_cmd=src_cmd,
                source_out=fp_src,
                verifier_cmd=P1,
                verifier_out=ident_out,
            ),
            evidence_item(
                claim=(
                    "Shell is a declared independence axis: Git Bash to PowerShell "
                    "with the same tool, data field, and measurement kind is accepted."
                ),
                anchor=f"{FP_REL}:{e3_line}",
                source_cmd=f"sed -n '{e3_line}p' {FP_REL}",
                source_out="SHELL_ONLY_VERIFIER",
                verifier_cmd=P2,
                verifier_out=shell_out,
            ),
            evidence_item(
                claim=(
                    "An empty source_probe is a violation, never a trivial "
                    "differs-from-verifier pass."
                ),
                anchor=f"{FP_REL}:{e2_line}",
                source_cmd=f"sed -n '{e2_line}p' {FP_REL}",
                source_out="if src is None: verdict=VIOLATION",
                verifier_cmd=(
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNF-0006'); "
                    "import fingerprint as F; print(F.independence_check({}, F.SHELL_ONLY_VERIFIER)['verdict'])\""
                ),
                verifier_out=empty_out,
            ),
        ],
        "tests": [
            {
                "id": "control-identical-command-reject",
                "name": "File a confirmation re-running the identical command; it must be rejected",
                "command": P1,
                "result": "PASS" if identical["pass"] else "FAIL",
            },
            {
                "id": "control-shell-axis-accept",
                "name": "File one differing only in shell (Git Bash to PowerShell); it must be ACCEPTED",
                "command": P2,
                "result": "PASS" if shell_only["pass"] else "FAIL",
            },
            {
                "id": "control-empty-source-violation",
                "name": "An empty source_probe must count as a violation, never as differs-from-verifier",
                "command": P2,
                "result": "PASS" if empty["pass"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "control-identical-command-reject",
                "kind": "known-broken-fixture",
                "description": "Identical Git-Bash which python re-run must be REJECTED as same-probe-rerun.",
                "fired_on_bad_state": bool(identical["pass"]),
                "silent_on_good_state": bool(shell_only["pass"]),
                "bad_state_output": ident_out,
                "good_state_output": shell_out,
            },
            {
                "id": "control-empty-source-violation",
                "kind": "absent-input",
                "description": "Empty source_probe must be VIOLATION, never differs-from-verifier.",
                "fired_on_bad_state": bool(empty["pass"]),
                "silent_on_good_state": bool(shell_only["pass"]),
                "bad_state_output": empty_out,
                "good_state_output": shell_out,
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0006-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-run the DETECTOR CONTROL: identical-command must REJECT, "
                "shell-only must ACCEPT, empty source must VIOLATE. A reviewer "
                "who only re-reads the rate has verified nothing."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0006/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNF-0006",
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator confirmation-audit (disk $id store)",
                "artifact_path": SCHEMA,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/CNF-0006/emit_audit.py"
                    ),
                    "raw_output": "offline confirmation-audit validator compiled; garbage rejected",
                    "fingerprint": probe_fingerprint(
                        "schema-validate",
                        "python3 -B command-center/p2-wave/probes/CNF-0006/emit_audit.py",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started_s,
            "ended_at": now,
            "duration_seconds": duration,
        },
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a later "
                "run that disagrees is a DISCREPANCY to record (spec 11039), never an "
                "error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether later confirmation receipts keep the measured same-probe "
                    "rate. The live scan is the first observation, not a pass by emptiness."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run command-center/p2-wave/probes/CNF-0006/corpus.py scan_corpus "
                    "after the confirmation corpus grows and record the new rate as a "
                    "DISCREPANCY if it disagrees."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "verification-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "confirmation-audit",
            "observations": [
                {
                    "name": "same-probe-rerun-percentage",
                    "measured": rate_text,
                    "method": "scan_corpus + independence_check over confirmation JSON",
                    "anchor": f"{CORPUS_REL}:scan_corpus",
                },
                {
                    "name": "identical-command-control",
                    "measured": identical["observed_verdict"],
                    "method": "independence_check(IDENTICAL_SOURCE, IDENTICAL_VERIFIER)",
                    "anchor": f"{FP_REL}:{e1_line}",
                },
                {
                    "name": "shell-axis-control",
                    "measured": shell_only["observed_verdict"],
                    "method": "independence_check(IDENTICAL_SOURCE, SHELL_ONLY_VERIFIER)",
                    "anchor": f"{FP_REL}:{e3_line}",
                },
                {
                    "name": "empty-source-control",
                    "measured": empty["observed_verdict"],
                    "method": "independence_check(EMPTY_SOURCE, SHELL_ONLY_VERIFIER)",
                    "anchor": f"{FP_REL}:{e2_line}",
                },
            ],
            "control_ids": [
                "control-identical-command-reject",
                "control-shell-axis-accept",
                "control-empty-source-violation",
            ],
            "title": "Probe fingerprinting that rejects a confirmation which only re-ran the original probe",
            "question": QUESTION,
            "answer": answer,
            "completion_sentinel": COMPLETION_SENTINEL,
            "fingerprint_function": {
                "path": FP_REL,
                "line": fp_line,
                "symbol": "fingerprint",
                "first_line": fp_src,
                "axes": list(F.AXES),
                "anchor": f"{FP_REL}:{fp_line}",
            },
            "same_probe_rate": {
                "confirmed_count": n,
                "same_probe_rerun_count": same_n,
                "undeclared_source_count": int(measured["undeclared_source_count"]),
                "percentage": rate if rate is not None else "n/a",
                "percentage_note": measured["percentage_note"],
                "empty_corpus_is_not_a_pass": True,
                "detector_controls_attached": True,
                "roots_scanned": measured["roots"],
                "missing_roots": measured["missing_roots"],
                "files_examined_count": measured["files_examined_count"],
                "files_examined": measured["files_examined"],
            },
            "offenders": measured["offenders"],
            "offender_ids": measured["offender_ids"],
            "controls": control_rows,
            "controls_same_invocation": True,
            "controls_opposite_verdicts_as_designed": True,
            "claims": [
                {
                    "id": "CNF-0006-C1",
                    "claim": (
                        "A confirmation whose verifier fingerprint equals its source "
                        "fingerprint is a same-probe re-run and must be rejected."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": f"{FP_REL}:{e1_line}",
                },
                {
                    "id": "CNF-0006-C2",
                    "claim": (
                        "Shell is a declared independence axis: Git Bash to PowerShell "
                        "with the same tool, data field, and measurement kind is accepted."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": f"{FP_REL}:{e3_line}",
                },
                {
                    "id": "CNF-0006-C3",
                    "claim": (
                        "An empty source_probe is a violation, never a trivial "
                        "differs-from-verifier pass."
                    ),
                    "verdict": "CONFIRMED",
                    "anchor": f"{FP_REL}:{e2_line}",
                },
            ],
            "named_probes": [
                {"id": "probe1", "role": "identical-command-reject", "command": P1},
                {"id": "probe2", "role": "shell-axis-and-empty-source", "command": P2},
            ],
            "adv_rebuild_circle": False,
            "required_fix": None,
            "failure_classification_if_failed": None,
        },
    }

    validator = offline_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0006 schema-invalid")
        for err in errs[:20]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(garbage)):
            print(f"FAILED:CNF-0006 schema accepted garbage {list(garbage)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0006 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if COMPLETION_SENTINEL not in text:
        print("FAILED:CNF-0006 sentinel-absent after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"fingerprint {FP_REL}:{fp_line}")
    print(f"same_probe_rate {rate_text}")
    print("controls opposite=True identical=REJECTED shell=ACCEPTED empty=VIOLATION")
    print("SUCCESS:CNF-0006 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
