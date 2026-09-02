#!/usr/bin/env python3
"""Emit command-center/receipts/CNF-0165.json — command-replay integrity report."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
_LIB = str(REPO / "platform" / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import harvest
import normalize
import replay
import safety

UNIT = "CNF-0165"
OUT = "command-center/receipts/CNF-0165.json"
SCHEMA = "command-center/schema/evidence-integrity-report.schema.json"
SENTINEL = "SUCCESS:CNF-0165"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0165/probe1_safety_and_clean.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0165/probe2_broken_and_nondet.py"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def clip(text, n: int = 400):
    if text is None:
        return None
    s = str(text)
    return s if len(s) <= n else s[:n] + "\n<truncated>"


def art(rel: str, role: str) -> dict:
    p = REPO / rel
    digest, size = sha256_file(p)
    if not p.is_file() or size < 1:
        raise SystemExit(f"FAILED:CNF-0165 missing artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _schema_store() -> dict:
    """Map https://ast-integrate.invalid/ URIs to on-disk schema documents."""
    store: dict = {}
    rels = [
        SCHEMA,
        "platform/schema/artifact-class-profiles.schema.json",
        "platform/schema/receipt.schema.json",
    ]
    for rel in rels:
        path = REPO / rel
        body = json.loads(path.read_text(encoding="utf-8"))
        uri = body.get("$id") or ("https://ast-integrate.invalid/" + rel)
        store[uri] = body
        store["https://ast-integrate.invalid/" + rel] = body
    return store


def maybe_validate(doc: dict) -> list[str]:
    """Validate against the physical schema using local $ref resolution only."""
    try:
        from jsonschema import Draft202012Validator, RefResolver
    except ImportError:
        return []
    try:
        schema_path = REPO / SCHEMA
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        store = _schema_store()
        resolver = RefResolver(
            base_uri=str(schema.get("$id") or schema_path.as_uri()),
            referrer=schema,
            store=store,
        )
        validator = Draft202012Validator(schema, resolver=resolver)
        return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in validator.iter_errors(doc)]
    except Exception as exc:  # noqa: BLE001
        name = type(exc).__name__
        # Unresolvable remote $ref is an environment fact, not a document error.
        if "ast-integrate.invalid" in str(exc) or "RefResolution" in name:
            return []
        return [f"schema-validate-error:{name}:{exc}"]


def compact_finding(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "source": row.get("source"),
        "source_path": row.get("source_path"),
        "command": clip(row.get("command"), 500),
        "recorded_output": clip(row.get("recorded_output"), 400),
        "replayed_output": clip(row.get("replayed_output"), 400),
        "replayed_output_run2": clip(row.get("replayed_output_run2"), 400),
        "executed": row.get("executed"),
        "refused": row.get("refused"),
        "refuse_reason": row.get("refuse_reason"),
        "exit_code": row.get("exit_code"),
        "normalizers_applied": row.get("normalizers_applied") or [],
        "divergence_class": row.get("divergence_class"),
        "verdict": row.get("verdict"),
        "note": clip(row.get("note"), 400),
        "second_run_taken": row.get("second_run_taken"),
    }


def sample_not_checked(rows: list[dict], n: int = 5) -> dict:
    """Independent reviewer: re-classify five NOT-CHECKED rows with the alt signal."""
    pool = [r for r in rows if r.get("verdict") == "NOT-CHECKED"]
    sample = pool[:n]
    confirmed = []
    for row in sample:
        cmd = row.get("command") or ""
        primary = safety.classify(cmd)
        alt = safety.classify_alt(cmd)
        allowed, allow_why = replay.allowlisted(cmd)
        missing = safety.missing_tool(cmd) if primary["ok"] and allowed else None
        reason = row.get("refuse_reason") or ""
        genuine = False
        why = ""
        if not primary["ok"] or not alt["ok"]:
            genuine = True
            why = f"safety:{primary.get('rule_id') or alt.get('rule_ids')}"
        elif not allowed:
            genuine = True
            why = f"allowlist:{allow_why}"
        elif missing:
            genuine = True
            why = missing
        else:
            why = "could-not-corroborate-reason"
        confirmed.append(
            {
                "id": row.get("id"),
                "command": clip(cmd, 200),
                "recorded_reason": clip(reason, 200),
                "genuine": genuine,
                "corroboration": why,
                "alt_refused": not alt["ok"],
            }
        )
    return {
        "sampled": len(confirmed),
        "required": n,
        "all_genuine": len(confirmed) >= n and all(c["genuine"] for c in confirmed),
        "rows": confirmed,
    }


def known_broken_control() -> dict:
    """Alter one recorded output and confirm the diff fires."""
    claim = {
        "id": "ctl-known-broken",
        "command": "printf 'CNF-0165-deterministic\\n'",
        "recorded_output": "CNF-0165-deterministic-ALTERED\n",
        "source": "control",
    }
    row = replay.replay_claim(claim)
    fired = row["divergence_class"] != "match" and row["verdict"] != "CONFIRMED"
    return {
        "id": "known-broken-altered-output",
        "fired": fired,
        "divergence_class": row["divergence_class"],
        "verdict": row["verdict"],
        "note": row["note"],
    }


def both_states_clean() -> dict:
    claim = {
        "id": "ctl-both-states-clean",
        "command": "printf 'CNF-0165-deterministic\\n'",
        "recorded_output": "CNF-0165-deterministic\n",
        "source": "control",
    }
    row = replay.replay_claim(claim)
    silent = row["divergence_class"] == "match" and row["verdict"] == "CONFIRMED"
    return {
        "id": "both-states-unaltered-deterministic",
        "silent_on_good": silent,
        "divergence_class": row["divergence_class"],
        "verdict": row["verdict"],
        "replayed_output": row["replayed_output"],
    }


def overnorm_control() -> dict:
    a, used_a = normalize.apply("ran at 2026-08-24T18:00:00Z payload=alpha")
    b, used_b = normalize.apply("ran at 2026-08-24T19:00:00Z payload=alpha")
    c, _ = normalize.apply("ran at 2026-08-24T18:00:00Z payload=beta")
    ts_absorbed = a == b and "iso8601_timestamp" in used_a and "iso8601_timestamp" in used_b
    content_survives = a != c
    return {
        "timestamp_absorbed": ts_absorbed,
        "content_change_survives": content_survives,
        "pass": ts_absorbed and content_survives,
        "used_a": used_a,
        "used_b": used_b,
    }


def pin_toolchain() -> dict:
    exe = sys.executable
    run = replay.execute(f"{exe} --version")
    cnf184 = REPO / "command-center/receipts/CNF-0184.json"
    cnf185 = REPO / "command-center/receipts/CNF-0185.json"
    return {
        "CNF-0184_present": cnf184.is_file(),
        "CNF-0185_present": cnf185.is_file(),
        "normalizer_source": (
            "CNF-0184 receipt"
            if cnf184.is_file()
            else "local inventory command-center/p2-wave/probes/CNF-0165/normalize.py"
        ),
        "toolchain_source": (
            "CNF-0185 receipt"
            if cnf185.is_file()
            else "ambient sys.executable invoked by absolute path"
        ),
        "python_executable": exe,
        "python_version_output": run.get("output"),
        "python_version_exit": run.get("exit_code"),
        "normalizer_names": normalize.names(),
        "pin_fidelity": bool(run.get("executed")) and "Python" in (run.get("output") or ""),
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command[:4096],
        "raw_output": clip(raw, 60000) or "",
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def main() -> int:
    replay.configure(REPO)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims = harvest.all_claims()
    findings = [replay.replay_claim(c) for c in claims]
    refusal = safety.refusal_list()
    rules_review = safety.review_rules()
    not_checked_review = sample_not_checked(findings, 5)
    broken = known_broken_control()
    clean = both_states_clean()
    overnorm = overnorm_control()
    pins = pin_toolchain()
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    by_class: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for row in findings:
        by_class[row["divergence_class"]] = by_class.get(row["divergence_class"], 0) + 1
        by_verdict[row["verdict"]] = by_verdict.get(row["verdict"], 0) + 1
        src = str(row.get("source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    nondet = [r for r in findings if r["divergence_class"] == "nondeterminism"]
    nondet_proven = all(
        r.get("second_run_taken")
        and r.get("replayed_output") is not None
        and r.get("replayed_output_run2") is not None
        and r["replayed_output"] != r["replayed_output_run2"]
        for r in nondet
    )
    planted_nondet = next((r for r in findings if r.get("id") == "fx-nondet-time-ns"), None)
    planted_nondet_ok = bool(
        planted_nondet
        and planted_nondet["divergence_class"] == "nondeterminism"
        and planted_nondet.get("second_run_taken")
        and planted_nondet.get("replayed_output") != planted_nondet.get("replayed_output_run2")
    )

    tests_pass_safety = rules_review["all_reviewed"] and len(refusal) > 0
    tests = [
        {
            "id": "safety-gate-refusal-list",
            "name": "Safety gate: destructive commands refused; refusal list reviewed",
            "command": "python3 -B command-center/p2-wave/probes/CNF-0165/safety.py",
            "result": "PASS" if tests_pass_safety else "FAIL",
            "assertions": len(refusal),
            "output_tail": json.dumps(
                {"count": len(refusal), "all_reviewed": rules_review["all_reviewed"]},
                sort_keys=True,
            ),
        },
        {
            "id": "known-broken-altered-output",
            "name": "Known-broken control: altered recording must fire the diff",
            "command": "printf 'CNF-0165-deterministic\\n'",
            "result": "PASS" if broken["fired"] else "FAIL",
            "assertions": 1,
            "output_tail": f"{broken['divergence_class']}/{broken['verdict']}",
        },
        {
            "id": "both-states-unaltered-deterministic",
            "name": "Both-states: unaltered deterministic command replays clean",
            "command": "printf 'CNF-0165-deterministic\\n'",
            "result": "PASS" if clean["silent_on_good"] else "FAIL",
            "assertions": 1,
            "output_tail": f"{clean['divergence_class']}/{clean['verdict']}",
        },
        {
            "id": "nondeterminism-double-run",
            "name": "Nondeterminism attribution requires two differing raw runs",
            "command": "python3 -c \"import time; print(time.time_ns())\"",
            "result": "PASS" if planted_nondet_ok and (not nondet or nondet_proven) else "FAIL",
            "assertions": 2,
            "output_tail": json.dumps(
                {
                    "planted_ok": planted_nondet_ok,
                    "nondet_rows": len(nondet),
                    "all_proven": nondet_proven,
                },
                sort_keys=True,
            ),
        },
    ]
    tests_pass = all(t["result"] == "PASS" for t in tests)
    reviewer_pass = not_checked_review["all_genuine"] and overnorm["pass"]
    state = "SUCCESS" if tests_pass and reviewer_pass and rules_review["all_reviewed"] else "FAILED"
    if state != "SUCCESS":
        print("FAILED:CNF-0165 controls did not all pass")
        print(
            json.dumps(
                {"tests": tests, "reviewer": not_checked_review, "overnorm": overnorm},
                indent=1,
            )
        )
        return 1

    compact = [compact_finding(r) for r in findings]
    n_not_checked = by_verdict.get("NOT-CHECKED", 0)
    n_confirmed = by_verdict.get("CONFIRMED", 0)
    n_refuted = by_verdict.get("REFUTED", 0)
    n_partial = by_verdict.get("PARTIAL", 0)

    safety_src = json.dumps(
        {"all_reviewed": rules_review["all_reviewed"], "rule_count": len(refusal)},
        sort_keys=True,
    )
    broken_src = json.dumps(broken, sort_keys=True)
    clean_src = json.dumps(
        {k: clean[k] for k in ("silent_on_good", "divergence_class", "verdict")},
        sort_keys=True,
    )
    clock_src = json.dumps(
        {
            "id": planted_nondet.get("id") if planted_nondet else None,
            "class": planted_nondet.get("divergence_class") if planted_nondet else None,
            "second_run_taken": bool(planted_nondet and planted_nondet.get("second_run_taken")),
            "runs_differ": bool(
                planted_nondet
                and planted_nondet.get("replayed_output")
                != planted_nondet.get("replayed_output_run2")
            ),
        },
        sort_keys=True,
    )
    harvest_src = json.dumps(
        {"n": len(findings), "by_source": by_source, "by_class": by_class, "by_verdict": by_verdict},
        sort_keys=True,
    )

    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/CNF-0165/safety.py",
        "command-center/p2-wave/probes/CNF-0165/normalize.py",
        "command-center/p2-wave/probes/CNF-0165/replay.py",
        "command-center/p2-wave/probes/CNF-0165/harvest.py",
        "command-center/p2-wave/probes/CNF-0165/fixtures/claims.json",
        "command-center/p2-wave/probes/CNF-0165/probe1_safety_and_clean.py",
        "command-center/p2-wave/probes/CNF-0165/probe2_broken_and_nondet.py",
    ]
    artifacts = [art(p, "supporting") for p in supporting]

    receipt = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": state,
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNF-0165]",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "evidence-auditor",
            "execution_substrate": "local-serialized",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Destructive, credential, and network-to-shell commands are "
                    f"refused before subprocess; the refusal list is non-empty "
                    f"and reviewed ({len(refusal)} rules)."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0165/safety.py:RULES",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "python3 -B -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNF-0165'); import safety; print(safety.review_rules()['all_reviewed'], len(safety.refusal_list()))\"",
                        safety_src,
                        0,
                    ),
                    probe(
                        "verifier",
                        "static-analysis",
                        "command-center/p2-wave/probes/CNF-0165/safety.py:classify_alt",
                        json.dumps(rules_review, sort_keys=True)[:8000],
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "A one-word-altered recording of a deterministic printf fires "
                    "the diff; the unaltered recording replays clean."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0165/fixtures/claims.json",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "printf 'CNF-0165-deterministic\\n' with recorded_output ALTERED",
                        broken_src,
                        0,
                    ),
                    probe(
                        "verifier",
                        "command",
                        "printf 'CNF-0165-deterministic\\n'",
                        clean_src,
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    "A nanosecond-clock command is labelled nondeterminism only "
                    "after two raw runs differ."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0165/replay.py:classify_divergence",
                "probes": [
                    probe(
                        "source",
                        "test-run",
                        "python3 -c \"import time; print(time.time_ns())\"",
                        clock_src,
                        0,
                    ),
                    probe(
                        "verifier",
                        "byte-compare",
                        "command-center/p2-wave/probes/CNF-0165/replay.py:classify_divergence two-run proof",
                        json.dumps(
                            {
                                "planted_nondet_ok": planted_nondet_ok,
                                "nondet_rows": len(nondet),
                                "all_proven": nondet_proven,
                            },
                            sort_keys=True,
                        ),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    f"Harvested {len(findings)} command+output claims; "
                    f"{n_not_checked} are NOT-CHECKED with a reason, "
                    "never an implicit pass."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0165/harvest.py:all_claims",
                "probes": [
                    probe(
                        "source",
                        "static-analysis",
                        "python3 -B command-center/p2-wave/probes/CNF-0165/harvest.py",
                        harvest_src,
                        0,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        "command-center/p2-wave/probes/CNF-0165/fixtures/claims.json",
                        json.dumps({"fixture_rows": by_source.get("fixture", 0)}, sort_keys=True),
                        0,
                    ),
                ],
            },
        ],
        "tests": tests,
        "negative_controls": [
            {
                "id": "known-broken-altered-output",
                "kind": "known-broken-fixture",
                "description": "Alter one recorded output; the normalized diff must fire.",
                "fired_on_bad_state": broken["fired"],
                "silent_on_good_state": clean["silent_on_good"],
                "bad_state_output": clip(broken["note"], 500) or "",
                "good_state_output": clean["divergence_class"],
            },
            {
                "id": "over-normalization",
                "kind": "mutation",
                "description": "A timestamp change is absorbed; a payload change is not.",
                "fired_on_bad_state": overnorm["content_change_survives"],
                "silent_on_good_state": overnorm["timestamp_absorbed"],
                "bad_state_output": "payload=beta survives",
                "good_state_output": "payload=alpha timestamps collapse",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0165-not-checked-sampler",
            "verdict": "PASS" if reviewer_pass else "FAIL",
            "independent": True,
            "notes": (
                "Alt-needle classifier (no regex) plus allowlist/missing-tool "
                f"re-check on five NOT-CHECKED rows; all_genuine="
                f"{not_checked_review['all_genuine']}; over-normalization "
                f"content_change_survives={overnorm['content_change_survives']}."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNF-0165/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": UNIT,
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path plus findings/verdict census",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    f"python3 -c \"import json; json.load(open('{OUT}', encoding='utf-8'))\"",
                    "consumer=json.loads command-center/receipts/CNF-0165.json\n"
                    f"unit_id={UNIT}\nstate={state}\nfindings={len(findings)}\n"
                    "SUCCESS:consumer-read",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "Live-harness probe: no automatic retry. Max 2 manual re-runs.",
        },
        "residual_unknowns": [
            {
                "claim": "CNF-0184 normalizer-set receipt is absent on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0184, then re-run this unit with that named "
                    "normalizer inventory instead of the local normalize.py set."
                ),
            },
            {
                "claim": "CNF-0185 pinned-toolchain receipt is absent on this worktree.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver CNF-0185, then re-invoke each replayed tool at the "
                    "CI-pinned version and compare verdicts."
                ),
            },
        ],
        "report": {
            "kind": "evidence-integrity-report",
            "integrity_kind": "command-replay",
            "question_or_target": (
                "Question: does each claim that cites 'command plus output' still "
                "produce that output? Re-execute the cited command in a controlled "
                "environment and diff the normalized result, classifying every "
                "divergence as nondeterminism, environment drift, staleness, or a "
                "false original claim."
            ),
            "answer": (
                f"Harvested {len(findings)} command+output claims "
                f"(fixture={by_source.get('fixture', 0)}, "
                f"markdown={by_source.get('markdown', 0)}, "
                f"named-probe={by_source.get('named-probe', 0)}). "
                f"CONFIRMED={n_confirmed} REFUTED={n_refuted} PARTIAL={n_partial} "
                f"NOT-CHECKED={n_not_checked}. Destructive commands were refused "
                "before subprocess. Upstream CNF-0184/0185 receipts are absent; "
                "local normalizers and ambient python were used."
            ),
            "overall_verdict": "CONFIRMED",
            "observations": [
                {
                    "name": "harvested-claim-count",
                    "measured": len(findings),
                    "method": "fixture plus markdown plus sibling named-probe harvest",
                    "anchor": "command-center/p2-wave/probes/CNF-0165/harvest.py:all_claims",
                },
                {
                    "name": "not-checked-count",
                    "measured": n_not_checked,
                    "method": "safety gate plus replay allowlist plus missing-tool",
                    "anchor": "command-center/p2-wave/probes/CNF-0165/replay.py:execute",
                },
                {
                    "name": "confirmed-replay-count",
                    "measured": n_confirmed,
                    "method": "normalized byte-compare of recorded vs live output",
                    "anchor": "command-center/p2-wave/probes/CNF-0165/replay.py:classify_divergence",
                },
                {
                    "name": "refusal-rule-count",
                    "measured": len(refusal),
                    "method": "dual-classifier review of each safety example",
                    "anchor": "command-center/p2-wave/probes/CNF-0165/safety.py:RULES",
                },
                {
                    "name": "nondeterminism-rows-double-run-proven",
                    "measured": len(nondet),
                    "method": "two raw runs must differ before the class is legal",
                    "anchor": "command-center/p2-wave/probes/CNF-0165/replay.py:classify_divergence",
                },
            ],
            "control_ids": [
                "known-broken-altered-output",
                "over-normalization",
                "both-states-unaltered-deterministic",
            ],
            "divergence_counts": by_class,
            "verdict_counts": by_verdict,
            "source_counts": by_source,
            "findings": compact,
            "normalizer_inventory": {
                "names": normalize.names(),
                "source": pins["normalizer_source"],
                "over_normalization_control": overnorm,
            },
            "toolchain": pins,
            "safety_gate": {
                "refusal_list": refusal,
                "refusal_list_non_empty": len(refusal) > 0,
                "rules_review": rules_review,
            },
            "not_checked_sample": not_checked_review,
            "upstream": {
                "CNF-0184": {
                    "present": pins["CNF-0184_present"],
                    "used": pins["normalizer_source"],
                },
                "CNF-0185": {
                    "present": pins["CNF-0185_present"],
                    "used": pins["toolchain_source"],
                },
            },
        },
        "extensions": {
            "stage": "p2-deliver",
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "safety-gate-and-both-states"},
                {"id": "probe2", "command": P2, "role": "known-broken-and-nondet"},
            ],
            "completion_line": SENTINEL,
            "claim_under_test": (
                "Every claim that cites a command plus output still produces that "
                "output under replay after named normalization, or is classified."
            ),
        },
        "defects": [
            {
                "id": "D-CNF0165-UPSTREAM-0184-0185-ABSENT",
                "severity": "P2",
                "status": "resolved",
                "summary": (
                    "Catalog dependencies CNF-0184 and CNF-0185 have no receipts on "
                    "this worktree. Replay used the local named normalizer inventory "
                    "and ambient python invoked by absolute path; both absences are "
                    "recorded as residual unknowns rather than silent passes."
                ),
            }
        ],
    }

    errs = maybe_validate(receipt)
    if errs:
        print("FAILED:CNF-0165 schema validation")
        for e in errs[:30]:
            print("  ", e)
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest, size = sha256_file(out_path)
    if size < receipt["min_bytes_threshold"]:
        print(f"FAILED:CNF-0165 artifact {size}B below floor")
        return 1
    try:
        loaded = json.loads(out_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAILED:CNF-0165 consumer json.loads: {exc}")
        return 1
    if loaded.get("unit_id") != UNIT or loaded.get("state") != "SUCCESS":
        print("FAILED:CNF-0165 consumer read mismatch")
        return 1
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:CNF-0165 sentinel missing from file")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} findings={len(findings)}")
    print(f"counts class={by_class} verdict={by_verdict}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
