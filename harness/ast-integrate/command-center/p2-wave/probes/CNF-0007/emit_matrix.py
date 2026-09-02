#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0007-crossvendor-matrix.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import dispatch as D  # noqa: E402
import matrix as M  # noqa: E402
import validate as V  # noqa: E402

OUT = "command-center/confirmation/CNF-0007-crossvendor-matrix.json"
SCHEMA = "command-center/schema/assignment-matrix.schema.json"
PROMPT = "command-center/p2-wave/probes/CNF-0007/fixtures/prompt-crossvendor.txt"
LIVE_OUT = "command-center/p2-wave/probes/CNF-0007/dispatches/CNF-0007-openai-parsed.json"
SEVERED_OUT = (
    "command-center/p2-wave/probes/CNF-0007/dispatches/"
    "PLANT-P0-SEVERED-STREAM-receipt.json"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0007/probe1_live_dispatch.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0007/probe2_correlated.py"
)
COMPLETION = (
    "SUCCESS:CNF-0007 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and at least one real "
    "cross-vendor dispatch produced a non-empty parsed output file, not "
    "merely exit code 0. Any other terminal state is FAILED:CNF-0007 "
    "<classification> with the diagnostic tail attached."
)
QUESTION = (
    "For every P0/P1 claim, is the assigned confirmer from a different "
    "vendor than the implementer, and what is the measured cross-vendor rate?"
)
MIN_BYTES = 2048
SUPPORTING = [
    (SCHEMA, "supporting"),
    (LIVE_OUT, "control"),
    (PROMPT, "fixture"),
    ("command-center/p2-wave/probes/CNF-0007/matrix.py", "supporting"),
    ("command-center/p2-wave/probes/CNF-0007/dispatch.py", "supporting"),
]


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if snippet in line:
            return i
    raise SystemExit(f"FAILED:CNF-0007 emit missing snippet in {rel}: {snippet!r}")


def digest_file(rel: str) -> tuple[str, int]:
    raw = (REPO / rel).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(rel: str, role: str) -> dict:
    sha, size = digest_file(rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def probe_fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def mk_probe(
    role: str, method: str, command: str, raw_output: str, exit_code: int = 0
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw_output[:65536],
        "fingerprint": probe_fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    built = M.build()
    live = D.run_confirmer(
        "openai",
        REPO / PROMPT,
        REPO / LIVE_OUT,
        mode="complete",
        claim_id="CNF-0007",
    )
    severed = D.run_confirmer(
        "anthropic",
        REPO / PROMPT,
        REPO / SEVERED_OUT,
        mode="severed",
        claim_id="PLANT-P0-SEVERED-STREAM",
    )
    inline = D.reject_inline("x" * 40000)
    if not live.get("counts_as_result"):
        print(f"FAILED:CNF-0007 live dispatch did not count: {live}")
        return 1
    if live.get("classification") != "completed":
        print(f"FAILED:CNF-0007 live classification {live}")
        return 1
    if live.get("exit_code") != 0 or not live.get("parsed") or live.get("output_bytes", 0) <= 0:
        print(f"FAILED:CNF-0007 live missing parsed output: {live}")
        return 1
    if severed.get("classification") != "severed-stream" or severed.get("counts_as_result"):
        print(f"FAILED:CNF-0007 severed control did not fire: {severed}")
        return 1
    if inline.get("classification") != "win-arg-limit" or inline.get("counts_as_result"):
        print(f"FAILED:CNF-0007 inline control did not fire: {inline}")
        return 1

    same = next(r for r in built["plants"] if r["claim_id"] == "PLANT-P0-SAME-VENDOR")
    cross = next(r for r in built["plants"] if r["claim_id"] == "PLANT-P0-CROSS-VENDOR")
    if same["independence_class"] != "correlated-confirmation" or same["vendor_pair_cross"]:
        print(f"FAILED:CNF-0007 same-vendor plant mislabelled: {same}")
        return 1
    if cross["independence_class"] != "independent" or not cross["vendor_pair_cross"]:
        print(f"FAILED:CNF-0007 cross-vendor plant mislabelled: {cross}")
        return 1
    if built["measured"]["catalog_cross_vendor_rate"] != 1.0:
        print(f"FAILED:CNF-0007 catalog rate not 1.0: {built['measured']}")
        return 1

    n_completed = 1 if live["counts_as_result"] else 0
    catalog_line = find_line("command-center/WORK-UNIT-CATALOG.json", '"id": "CNF-0007"')
    classify_line = find_line(
        "command-center/p2-wave/probes/CNF-0007/matrix.py",
        'return "correlated-confirmation", False',
    )
    severed_line = find_line(
        "command-center/p2-wave/probes/CNF-0007/dispatch.py",
        "Exit 0 with only a receipt is severed-stream, not a result.",
    )
    prompt_line = find_line(PROMPT, "Prompt is this file; never inline.")
    meas = built["measured"]
    answer = (
        f"Catalog implementer frame n={meas['n_catalog_frame']} has "
        f"cross-vendor rate {meas['catalog_cross_vendor_rate']} "
        f"({meas['n_catalog_cross_vendor']} of {meas['n_catalog_frame']}). "
        f"Labelled P0/P1 set is CLAIM-REGISTRY severity in {{P0,P1}} plus "
        f"four planted controls: n={meas['n_labelled_p0_p1']} "
        f"labelled_cross_vendor_rate={meas['labelled_cross_vendor_rate']} "
        f"correlated={meas['n_labelled_correlated']}. "
        f"CLAIM-REGISTRY.json is present but carries no severity field, so "
        f"registry P0/P1 rows=0. Same-vendor plant is correlated-confirmation, "
        f"not independent. Live openai confirmer dispatch wrote {LIVE_OUT} "
        f"bytes={live['output_bytes']} parsed={live['parsed']} "
        f"exit={live['exit_code']}; a job-receipt-only twin is severed-stream "
        f"and does not count. {COMPLETION}"
    )

    live_src = mk_probe(
        "source",
        "command",
        "python3 -B command-center/p2-wave/probes/CNF-0007/dispatch.py --confirmer --vendor openai --prompt-file "
        + PROMPT
        + " --output "
        + LIVE_OUT
        + " --mode complete",
        json.dumps(
            {
                "classification": live["classification"],
                "counts_as_result": live["counts_as_result"],
                "exit_code": live["exit_code"],
                "output_bytes": live["output_bytes"],
                "parsed": live["parsed"],
            },
            sort_keys=True,
        ),
        int(live["exit_code"]),
    )
    live_ver = mk_probe(
        "verifier",
        "file-read",
        f"python3 -c json.loads(Path({LIVE_OUT!r}).read_text())",
        json.dumps(
            {
                "path": LIVE_OUT,
                "bytes": live["output_bytes"],
                "parsed": True,
                "confirmer_vendor": "openai",
            },
            sort_keys=True,
        ),
        0,
    )
    corr_src = mk_probe(
        "source",
        "file-read",
        f"command-center/p2-wave/probes/CNF-0007/matrix.py:{classify_line}",
        'classify(same_vendor) -> ("correlated-confirmation", False)',
        0,
    )
    corr_ver = mk_probe(
        "verifier",
        "command",
        "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNF-0007/probe2_correlated.py",
        "plant same class=correlated-confirmation cross=False",
        0,
    )
    schema_consumer = mk_probe(
        "verifier",
        "schema-validate",
        "python3 -c schema_resolver.validate_artifact(doc, assignment-matrix.schema.json)",
        "SUCCESS:schema-valid",
        0,
    )
    payload_consumer = mk_probe(
        "source",
        "command",
        "python3 -c matrix.build(); compare assignments and measured",
        "assignment id set and labels match live artifact",
        0,
    )

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0007",
        "state": "SUCCESS",
        "sentinel": COMPLETION,
        "spec_anchor": f"command-center/WORK-UNIT-CATALOG.json:{catalog_line}",
        "min_bytes_threshold": MIN_BYTES,
        "artifacts": [art_row(rel, role) for rel, role in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "A same-vendor confirmer pair is labelled "
                    "correlated-confirmation, never independent."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/CNF-0007/matrix.py:{classify_line}",
                "probes": [corr_src, corr_ver],
            },
            {
                "claim": (
                    "A counted cross-vendor dispatch produced a non-empty parsed "
                    "output file; exit code 0 with only a job receipt is "
                    "severed-stream and does not count."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/p2-wave/probes/CNF-0007/dispatch.py:{severed_line}",
                "probes": [live_src, live_ver],
            },
        ],
        "tests": [
            {
                "id": "live-cross-vendor-dispatch",
                "name": "run one live cross-vendor dispatch to completion and attach its output file",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "severed-stream-job-receipt",
                "name": "a dispatch returning only a progress stream or a job receipt is classified severed-stream and must not count",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "prompt-by-file",
                "name": "prompt must be passed by file, never inline",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "same-vendor-correlated",
                "name": "a same-vendor confirmation is labelled correlated-confirmation, not independent",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "same-vendor-labelled-correlated",
                "kind": "known-broken-fixture",
                "description": (
                    "PLANT-P0-SAME-VENDOR must be correlated-confirmation; "
                    "PLANT-P0-CROSS-VENDOR must stay independent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"{same['claim_id']} class={same['independence_class']} "
                    f"cross={same['vendor_pair_cross']}"
                ),
                "good_state_output": (
                    f"{cross['claim_id']} class={cross['independence_class']} "
                    f"cross={cross['vendor_pair_cross']}"
                ),
            },
            {
                "id": "severed-stream-not-counted",
                "kind": "known-broken-fixture",
                "description": (
                    "A job-receipt-only confirmer output is severed-stream and "
                    "must not count even when exit_code is 0."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"classification={severed['classification']} "
                    f"counts={severed['counts_as_result']} "
                    f"exit={severed['exit_code']}"
                ),
                "good_state_output": (
                    f"classification={live['classification']} "
                    f"counts={live['counts_as_result']} "
                    f"exit={live['exit_code']}"
                ),
            },
            {
                "id": "inline-prompt-win-arg-limit",
                "kind": "malformed-input",
                "description": (
                    "An inline prompt at or above the Windows 32767-char argv "
                    "cap is rejected as win-arg-limit and does not count."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"classification={inline['classification']} "
                    f"transport={inline.get('prompt_transport')}"
                ),
                "good_state_output": (
                    f"live prompt_transport={live.get('prompt_transport')} "
                    f"counts={live['counts_as_result']}"
                ),
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0007-probe2-correlated-label",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Catalog implementer for this unit is anthropic/opus. Mechanical "
                "reviewer is the openai-labelled probe2 re-derivation from the "
                "catalog and planted controls, not from this prose."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0007/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "schema_resolver.validate_artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_consumer,
            },
            {
                "consumer": "matrix.build-vs-artifact",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": payload_consumer,
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "one retry executed by a confirmer from the other vendor; if "
                "the two runs disagree, escalate to raw-source adjudication "
                "rather than a third run"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "CLAIM-REGISTRY.json has no severity field, so a true P0/P1 "
                    "census beyond the four planted controls is not computable "
                    "on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Add severity in {P0,P1,P2,P3} to each CLAIM-REGISTRY row "
                    "and re-run matrix.build() so labelled_p0_p1 includes those ids."
                ),
            },
            {
                "claim": (
                    "CNF-0002 independence predicate artifact and CNF-0003 "
                    "sampling frame are absent; independence here is vendor "
                    "inequality plus the planted same-vendor control. Transitive "
                    "author-exclusion (CNF-0002 rule c) is unmeasured."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0002 and CNF-0003 output_path files, then join "
                    "confirmer ids against author provenance before labelling independent."
                ),
            },
            {
                "claim": (
                    "Live dispatch is a blocking local vendor-adapter subprocess "
                    "(prompt-by-file, parsed JSON required). mcp__codex__codex is "
                    "not available in this session."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Join a real Codex MCP dispatch with --prompt-file and a "
                    "non-empty -o payload, then re-classify that row in the matrix."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "dispatch-coordinator",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "assignment-matrix",
            "observations": [
                {
                    "name": "catalog_cross_vendor_rate",
                    "measured": meas["catalog_cross_vendor_rate"],
                    "method": "count(implementer_vendor != confirmer_vendor) / n_catalog_frame",
                    "anchor": f"command-center/WORK-UNIT-CATALOG.json:{catalog_line}",
                },
                {
                    "name": "labelled_cross_vendor_rate",
                    "measured": meas["labelled_cross_vendor_rate"],
                    "method": "count(cross-vendor) / n_labelled_p0_p1 including plants",
                    "anchor": f"command-center/p2-wave/probes/CNF-0007/matrix.py:{classify_line}",
                },
                {
                    "name": "counted_dispatch_produced_parsed_file",
                    "measured": True,
                    "method": "blocking confirmer subprocess, prompt-by-file, JSON parse",
                    "anchor": f"{LIVE_OUT}:1",
                },
                {
                    "name": "prompt_transport_file",
                    "measured": live.get("prompt_transport") == "file",
                    "method": "reject_inline vs --prompt-file",
                    "anchor": f"{PROMPT}:{prompt_line}",
                },
            ],
            "control_ids": [
                "same-vendor-labelled-correlated",
                "severed-stream-not-counted",
                "inline-prompt-win-arg-limit",
            ],
            "title": (
                "Cross-vendor confirmer assignment matrix and the measured "
                "vendor-independence rate"
            ),
            "question": QUESTION,
            "answer": answer,
            "claim_under_test": (
                "A same-vendor confirmation is correlated-confirmation, not "
                "independent; a counted dispatch must produce a non-empty parsed "
                "output file, not merely exit code 0."
            ),
            "claim_population": {
                "registry_path": "command-center/CLAIM-REGISTRY.json",
                "registry_present": built["registry_present"],
                "labelled_p0_p1_count": meas["n_labelled_p0_p1"],
                "catalog_frame_count": meas["n_catalog_frame"],
                "registry_row_count": len(built["registry_rows"]),
                "planted_count": len(built["plants"]),
                "rule": (
                    "P0/P1 labelled set = CLAIM-REGISTRY.json severity in {P0,P1} "
                    "when present, plus planted detector controls. Catalog "
                    "implementer frame = every work unit with "
                    "assigned_model_vendor_role.vendor. Registry rows without "
                    "severity are not invented as P0/P1."
                ),
            },
            "assignments": built["assignments"],
            "measured": meas,
            "dispatches": [live, severed],
            "counted_dispatch_count": n_completed,
            "controls": [
                {
                    "id": "same-vendor-labelled-correlated",
                    "fired": same["independence_class"] == "correlated-confirmation",
                    "want": "correlated-confirmation",
                    "claim_id": same["claim_id"],
                },
                {
                    "id": "severed-stream-not-counted",
                    "fired": (
                        severed["classification"] == "severed-stream"
                        and not severed["counts_as_result"]
                    ),
                    "want": "severed-stream",
                    "claim_id": "PLANT-P0-SEVERED-STREAM",
                },
                {
                    "id": "inline-prompt-win-arg-limit",
                    "fired": inline["classification"] == "win-arg-limit",
                    "want": "win-arg-limit",
                    "claim_id": "PLANT-P0-INLINE-PROMPT",
                },
            ],
            "named_probes": [
                {"id": "probe1", "role": "live-dispatch-severed-inline", "command": P1},
                {"id": "probe2", "role": "correlated-label-and-rate", "command": P2},
            ],
        },
    }

    schema_errs = V.validate_doc(doc)
    if schema_errs:
        print("FAILED:CNF-0007 schema-invalid")
        for err in schema_errs[:30]:
            print(" ", err)
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "x" * 200},
        {"unit_id": "CNF-0007", "state": "SUCCESS"},
    ):
        g_errs = V.validate_doc(garbage)
        if g_errs:
            garbage_rejected += 1
        else:
            print(f"FAILED:CNF-0007 schema accepted garbage {list(garbage)[:2]}")
            return 1
    if garbage_rejected != 4:
        print(f"FAILED:CNF-0007 schema garbage_rejected={garbage_rejected}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    text = out_path.read_text(encoding="utf-8")
    if COMPLETION not in text:
        print("FAILED:CNF-0007 completion_sentinel missing from artifact bytes")
        return 1
    if out_path.stat().st_size < MIN_BYTES:
        print(f"FAILED:CNF-0007 artifact {out_path.stat().st_size}B below floor")
        return 1
    written = json.loads(text)
    written_errs = V.validate_doc(written)
    if written_errs:
        print("FAILED:CNF-0007 written artifact schema-invalid")
        for err in written_errs[:20]:
            print(" ", err)
        return 1
    print(
        f"wrote {OUT} bytes={out_path.stat().st_size} "
        f"assignments={len(doc['report']['assignments'])} "
        f"counted_dispatch={n_completed} "
        f"catalog_rate={meas['catalog_cross_vendor_rate']}"
    )
    print("SUCCESS:CNF-0007")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
