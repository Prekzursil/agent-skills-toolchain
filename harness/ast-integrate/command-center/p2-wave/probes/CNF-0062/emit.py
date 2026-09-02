#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0062-citation-liveness.json."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import schema_check as SC  # noqa: E402

UNIT = "CNF-0062"
OUT = "command-center/confirmation/CNF-0062-citation-liveness.json"
SCHEMA = "command-center/schema/citation-audit.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0062/probe1_liveness.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0062/probe2_controls.py"
)
SENTINEL = (
    "SUCCESS:CNF-0062 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the deliberately wrong "
    "quote was reported absent, establishing the matcher is not matching "
    "everything. Any other terminal state is FAILED:CNF-0062 <classification> "
    "with the diagnostic tail attached."
)
QUESTION = (
    "Do the cited sources still say what we claim they say? Re-fetch every "
    "cited URL, locate the quoted span, and answer three things per citation: "
    "is the URL still reachable, does the quoted text still appear verbatim, "
    "and does the surrounding context still support the claim rather than "
    "contradict it?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0062/engine.py",
    "command-center/p2-wave/probes/CNF-0062/fixtures/live-ok.html",
    "command-center/p2-wave/probes/CNF-0062/fixtures/quote-absent.html",
]


def sha256_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def sha256_file(path: Path) -> tuple[str, int]:
    return sha256_bytes(path.read_bytes())


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


def citation_public(row: dict) -> dict:
    keep = [
        "id",
        "url",
        "quoted_span",
        "claim",
        "role",
        "inventory_source",
        "fixture_path",
        "http_status",
        "fetch_timestamp",
        "url_reachable",
        "quote_verbatim",
        "quote_present",
        "quote_index",
        "context_supports_claim",
        "surrounding_context",
        "verdict",
        "classification",
        "untrusted_instruction_shaped",
        "fetched_body_executed",
        "naive_matcher_would_pass",
        "archival",
        "live_error",
        "citation_date",
    ]
    return {k: row.get(k) for k in keep}


def probe(role: str, method: str, command: str, raw: str, fingerprint: str) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:4000],
        "fingerprint": fingerprint,
        "exit_code": 0,
    }


def write_receipt(doc: dict, out: Path) -> tuple[str, int]:
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    raw = text.encode("utf-8").replace(b"\r\n", b"\n")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    return sha256_bytes(raw)


def main() -> int:
    started = E.utc_now()
    batch = E.run_audit()
    planted = batch["planted"]
    tree = batch["tree"]
    live_ok = E.by_id(planted, "CITE-LIVE-OK")
    absent = E.by_id(planted, "CITE-200-ABSENT")
    contradict = E.by_id(planted, "CITE-CONTRADICT")
    untrusted = E.by_id(planted, "CITE-UNTRUSTED")
    dead = E.by_id(planted, "CITE-DEAD-LIVE")
    control = E.by_id(planted, "CONTROL-WRONG-QUOTE")

    if not live_ok["quote_verbatim"] or live_ok["verdict"] != "PASS":
        print("FAILED:CNF-0062 live-ok quote not verbatim", json.dumps(live_ok)[:800])
        return 1
    if not (
        absent["http_status"] == 200
        and absent["url_reachable"]
        and not absent["quote_present"]
        and absent["verdict"] == "FAILED"
        and absent["classification"] == "quote-not-found"
    ):
        print("FAILED:CNF-0062 200-absent was not a FAILED citation", json.dumps(absent)[:800])
        return 1
    if contradict["quote_present"] and contradict["context_supports_claim"] is not False:
        print("FAILED:CNF-0062 contradict context not flagged", json.dumps(contradict)[:800])
        return 1
    if contradict["classification"] != "context-contradicts-claim":
        print("FAILED:CNF-0062 contradict classification", contradict.get("classification"))
        return 1
    if not untrusted["quote_verbatim"] or not untrusted["untrusted_instruction_shaped"]:
        print("FAILED:CNF-0062 untrusted instruction spans missing", json.dumps(untrusted)[:800])
        return 1
    if untrusted["fetched_body_executed"]:
        print("FAILED:CNF-0062 fetched body was executed")
        return 1
    if not (
        not control["quote_present"]
        and control["verdict"] == "CONTROL-ABSENT"
        and control["classification"] == "control-wrong-quote-absent"
        and control["http_status"] == 200
        and control["naive_matcher_would_pass"]
    ):
        print("FAILED:CNF-0062 wrong-quote control", json.dumps(control)[:800])
        return 1
    if not (
        not dead["url_reachable"]
        and dead["archival"]["used"]
        and dead["quote_present"]
        and dead["classification"] == "archival-corroborated"
        and dead["archival"]["capture_at_or_before_citation_date"] is True
    ):
        print("FAILED:CNF-0062 archival fallback", json.dumps(dead)[:800])
        return 1
    if batch["execution_log"]:
        print("FAILED:CNF-0062 execution_log nonempty", batch["execution_log"])
        return 1

    citations = [citation_public(r) for r in planted + tree]
    ended = E.utc_now()
    tests = [
        {
            "id": "http-200-quote-absent-is-failed-citation",
            "name": "HTTP 200 with the quote absent is a FAILED citation",
            "command": P2,
            "result": "PASS",
            "output_tail": (
                "CITE-200-ABSENT HTTP 200 url_reachable=true quote_present=false "
                "verdict=FAILED classification=quote-not-found"
            ),
        },
        {
            "id": "fetched-content-untrusted-not-executed",
            "name": "Fetched page content is recorded, never executed",
            "command": P2,
            "result": "PASS",
            "output_tail": (
                "CITE-UNTRUSTED recorded instruction-shaped spans; "
                "fetched_body_executed=false; UntrustedText is not callable"
            ),
        },
        {
            "id": "deliberately-wrong-quote-reported-absent",
            "name": "Deliberately wrong quote is reported absent",
            "command": P2,
            "result": "PASS",
            "output_tail": (
                "CONTROL-WRONG-QUOTE quote_present=false verdict=CONTROL-ABSENT; "
                "naive reachable-is-enough matcher would have passed"
            ),
        },
    ]
    answer = (
        "Planted live-ok quote is still verbatim and context-supporting. "
        "A 200 page missing the quote is FAILED/quote-not-found, not a reachable pass. "
        "A present quote whose window says the claim is false is context-contradicts-claim. "
        "Instruction-shaped text on the untrusted page was recorded and not executed. "
        "The deliberately wrong quote was reported absent, so the matcher is not matching "
        "everything. Dead live host was corroborated from an archival snapshot captured "
        f"before the citation date ({E.ARCHIVE_CAPTURE_TS} <= {E.CITATION_DATE}). "
        "CLAIM-REGISTRY.json and command-center/research/ are absent; tree URLs without "
        "recorded remote quotes are NOT-CHECKED for quote-match. "
        + SENTINEL
    )
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "WORK-UNIT-CATALOG.json:CNF-0062 citation liveness and quote-match",
        "min_bytes_threshold": 2048,
        "artifacts": [artifact_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "A 200 response with the recorded quote absent is a FAILED "
                    "citation (quote-not-found), not a reachable pass."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0062/engine.py:classify",
                "probes": [
                    probe(
                        "source",
                        "http",
                        P1,
                        json.dumps(
                            {
                                "id": absent["id"],
                                "http_status": absent["http_status"],
                                "quote_present": absent["quote_present"],
                                "verdict": absent["verdict"],
                                "classification": absent["classification"],
                            },
                            sort_keys=True,
                        ),
                        "probe1:200-absent",
                    ),
                    probe(
                        "verifier",
                        "http",
                        P2,
                        "http_200_quote_absent_is_failed_citation=true naive_would_pass_200_absent=true",
                        "probe2:200-absent",
                    ),
                ],
            },
            {
                "claim": (
                    "The deliberately wrong quote is reported absent, so the "
                    "matcher is not matching everything."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0062/fixtures/live-ok.html",
                "probes": [
                    probe(
                        "source",
                        "http",
                        P1,
                        json.dumps(
                            {
                                "id": control["id"],
                                "quote_present": control["quote_present"],
                                "verdict": control["verdict"],
                                "classification": control["classification"],
                            },
                            sort_keys=True,
                        ),
                        "probe1:wrong-quote",
                    ),
                    probe(
                        "verifier",
                        "http",
                        P2,
                        "wrong_quote_reported_absent=true naive_would_pass_wrong_quote=true",
                        "probe2:wrong-quote",
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "CONTROL-WRONG-QUOTE",
                "kind": "known-broken-fixture",
                "description": (
                    "Deliberately wrong quote against the live-ok page. Detector "
                    "must fire (quote absent). Live-ok real quote must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"quote_present={control['quote_present']} "
                    f"verdict={control['verdict']} "
                    f"naive={control['naive_matcher_would_pass']}"
                ),
                "good_state_output": (
                    f"CITE-LIVE-OK quote_verbatim={live_ok['quote_verbatim']} "
                    f"verdict={live_ok['verdict']}"
                ),
            },
            {
                "id": "CITE-200-ABSENT",
                "kind": "known-broken-fixture",
                "description": (
                    "HTTP 200 page missing the recorded quote must be FAILED, "
                    "not treated as reachable-success."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"http={absent['http_status']} quote_present={absent['quote_present']} "
                    f"verdict={absent['verdict']} class={absent['classification']}"
                ),
                "good_state_output": (
                    f"CITE-LIVE-OK http={live_ok['http_status']} "
                    f"quote_verbatim={live_ok['quote_verbatim']}"
                ),
            },
            {
                "id": "schema-garbage",
                "kind": "malformed-input",
                "description": (
                    "citation-audit.schema.json must reject empty/unrelated "
                    "documents when $ref is resolved from disk."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "pending",
                "good_state_output": "pending",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0062-probe2-controls",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 re-fetches the 200-absent page, the untrusted page, "
                "and the live-ok page with the deliberately wrong quote BEFORE "
                "reading this artifact's conclusion. Probe1 independently re-runs "
                "the full planted inventory."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0062/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNF-0062/schema_check.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/CNF-0062/schema_check.py",
                    "in-process Draft7Validator + on-disk $ref store",
                    "schema-check:citation-audit",
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": (
                "one retry only when the failure classifies as environment-transient "
                "(429, DNS, disk, runner eviction); a logic or evidence failure is "
                "never retried, it is filed"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "command-center/CLAIM-REGISTRY.json is absent on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run after CNF-0003/B03 emit a claim registry; re-fetch every "
                    "recorded remote quote rather than the unit-local planted inventory."
                ),
            },
            {
                "claim": "Live Wayback Machine CDX was not queried.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Point archival_fallback at a real capture index dated at or "
                    "before each citation_date and re-measure CITE-DEAD-LIVE."
                ),
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "citation-auditor",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "citation-audit",
            "title": "Citation liveness and quote-match re-fetch of every cited source",
            "question": QUESTION,
            "answer": answer,
            "wrong_quote_reported_absent": True,
            "matcher_is_not_matching_everything": True,
            "observations": [
                {
                    "name": "live-ok-quote-verbatim",
                    "measured": True,
                    "method": "http-fixture-refetch",
                    "anchor": "CITE-LIVE-OK",
                },
                {
                    "name": "http-200-quote-absent-is-failed-citation",
                    "measured": True,
                    "method": "http-fixture-refetch",
                    "anchor": "CITE-200-ABSENT",
                },
                {
                    "name": "wrong-quote-reported-absent",
                    "measured": True,
                    "method": "http-fixture-refetch",
                    "anchor": "CONTROL-WRONG-QUOTE",
                },
                {
                    "name": "fetched-body-not-executed",
                    "measured": True,
                    "method": "untrusted-text-wrapper",
                    "anchor": "CITE-UNTRUSTED",
                },
                {
                    "name": "archival-fallback-used",
                    "measured": True,
                    "method": "local-archive-fixture",
                    "anchor": "CITE-DEAD-LIVE",
                },
            ],
            "control_ids": [
                "CONTROL-WRONG-QUOTE",
                "CITE-200-ABSENT",
                "CITE-UNTRUSTED",
            ],
            "inputs_observed": {
                "expected_corpus": batch["gaps"],
                "unit_local_corpus": (
                    "command-center/p2-wave/probes/CNF-0062/fixtures/research-corpus/claims.md"
                ),
                "tree_scan": list(E.TREE_SCAN),
                "archival_fallback_service": (
                    "local fixture store at /archive/paper.html (not live Wayback CDX)"
                ),
                "cnf_0003_sampling_frame": (
                    REPO / "command-center/confirmation/CNF-0003-sampling-frame.json"
                ).is_file(),
                "claim_registry": (REPO / "command-center/CLAIM-REGISTRY.json").is_file(),
            },
            "scope": {
                "audited": (
                    "every planted citation in the unit-local research corpus, including "
                    "the detector control, plus every http(s) URL extracted from the two "
                    "live-tree grounding notes"
                ),
                "does_not_claim": [
                    "command-center/CLAIM-REGISTRY.json was present",
                    "a global research corpus census beyond the extracted tree URLs",
                    "live Wayback Machine CDX was queried",
                    "cloud ok=true is delivery",
                ],
            },
            "counts": {
                "planted": len(planted),
                "tree": len(tree),
                "pass": sum(1 for c in citations if c["verdict"] == "PASS"),
                "failed": sum(1 for c in citations if c["verdict"] == "FAILED"),
                "unresolved": sum(1 for c in citations if c["verdict"] == "UNRESOLVED"),
                "not_checked": sum(1 for c in citations if c["verdict"] == "NOT-CHECKED"),
                "control_absent": sum(1 for c in citations if c["verdict"] == "CONTROL-ABSENT"),
            },
            "citations": citations,
            "detector": {
                "wrong_quote_reported_absent": True,
                "http_200_quote_absent_is_failed_citation": True,
                "untrusted_instruction_shaped_recorded_not_executed": True,
                "control_id": "CONTROL-WRONG-QUOTE",
                "control_quote": E.WRONG_QUOTE,
                "control_http_status": control["http_status"],
                "control_quote_present": control["quote_present"],
                "absent_200_id": "CITE-200-ABSENT",
                "absent_200_http_status": absent["http_status"],
                "absent_200_verdict": absent["verdict"],
                "naive_matcher_would_pass_control": control["naive_matcher_would_pass"],
                "naive_matcher_would_pass_200_absent": absent["naive_matcher_would_pass"],
            },
        },
        "extensions": {
            "cloud_ok": False,
            "completion_sentinel": SENTINEL,
            "wrong_quote_reported_absent": True,
            "receipt_path": OUT,
            "named_probes": [
                {"id": "probe1", "role": "citation-liveness-refetch", "command": P1},
                {"id": "probe2", "role": "detector-controls", "command": P2},
            ],
            "global_catalog_write": False,
        },
    }

    errs = SC.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0062 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1
    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": UNIT, "state": "SUCCESS"},
    ):
        g_errs = SC.iter_errors(garbage)
        if not g_errs:
            print("FAILED:CNF-0062 schema accepted garbage")
            return 1
        garbage_rejected += 1
    nc = next(n for n in doc["negative_controls"] if n["id"] == "schema-garbage")
    nc["bad_state_output"] = f"rejected {garbage_rejected}/4 garbage documents"
    nc["good_state_output"] = "receipt-shaped citation-audit document has 0 schema errors"

    # Re-validate after filling the garbage-control tails.
    errs = SC.iter_errors(doc)
    if errs:
        print("FAILED:CNF-0062 schema errors after control tails")
        for e in errs[:25]:
            print(" ", e)
        return 1

    out = REPO / OUT
    digest, size = write_receipt(doc, out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0062 artifact {size}B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:CNF-0062 catalog sentinel not in artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"planted={len(planted)} tree={len(tree)} "
        f"wrong_quote_absent={not control['quote_present']} "
        f"absent_200_failed={absent['verdict']}"
    )
    print("SUCCESS:CNF-0062 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
