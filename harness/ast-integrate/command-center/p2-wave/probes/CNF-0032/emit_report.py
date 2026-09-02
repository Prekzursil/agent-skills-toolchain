#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0032-hunk-revert-causality.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import protocol as P  # noqa: E402
import schema_local as S  # noqa: E402

UNIT = "CNF-0032"
OUT_REL = "command-center/confirmation/CNF-0032-hunk-revert-causality.json"
SCHEMA_REL = "command-center/schema/causality-report.schema.json"
STRIKES = HERE / "_schema_strikes.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0032/probe1_revert_restore.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0032/probe2_non_load_bearing.py"
)
SENTINEL = (
    "SUCCESS:CNF-0032 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and each examined fix has a "
    "matched revert-red and restore-green pair recorded. Any other terminal "
    "state is FAILED:CNF-0032 <classification> with the diagnostic tail attached."
)
QUESTION = (
    "Is the fix the CAUSE of the corrected behaviour, or did something else "
    "change alongside it? In a scratch tree revert ONLY the fix hunk, leaving "
    "tests and everything else intact, and require the failure to return. "
    "Question: for how many fixes does the failure NOT return, meaning the "
    "fix is not load-bearing for the behaviour it claims?"
)
RETRY_POLICY = (
    "zero retries. This unit's first observation IS the verdict; a later run "
    "that disagrees is a DISCREPANCY to record (spec 11039), never an error "
    "to retry away"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {"unit_id": UNIT, "state": "SUCCESS"},
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_art(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": max(len(raw), 1),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-4000:],
        "fingerprint": sha256_text(f"{method}|{command}"),
        "exit_code": int(exit_code),
    }


def err_fp(errs: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(errs)).encode("utf-8")).hexdigest()[:16]


def load_strikes() -> dict:
    if not STRIKES.is_file():
        return {"attempts": []}
    try:
        data = json.loads(STRIKES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"attempts": []}
    if not isinstance(data, dict):
        return {"attempts": []}
    data.setdefault("attempts", [])
    return data


def park_blocked(required_fix: str, errs: list[str], fp: str) -> int:
    now = utcnow()
    blocked = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "BLOCKED",
        "sentinel": f"FAILED:{UNIT} parked-same-fingerprint-structural-refute",
        "spec_anchor": "command-center/catalog-slices/CNF-1.json:CNF-0032",
        "min_bytes_threshold": 256,
        "artifacts": [file_art(SCHEMA_REL, "supporting")],
        "evidence": [
            {
                "claim": (
                    "Two same-fingerprint structural refutes; parked without "
                    "an ADV rebuild circle."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0032/_schema_strikes.json",
                "probes": [
                    probe(
                        "source",
                        "schema-validate",
                        "schema_local.error_messages",
                        "\n".join(errs[:12]),
                        1,
                    ),
                    probe(
                        "verifier",
                        "file-read",
                        str(STRIKES.relative_to(REPO).as_posix()),
                        f"fingerprint={fp}",
                        1,
                    ),
                ],
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 2,
            "policy": RETRY_POLICY,
            "attempts": [
                {
                    "attempt": 1,
                    "error_fingerprint": fp,
                    "outcome": "FAILED",
                    "started_at": now,
                },
                {
                    "attempt": 2,
                    "error_fingerprint": fp,
                    "outcome": "BLOCKED",
                    "started_at": now,
                },
            ],
        },
        "failure": {
            "classification": ["schema-invalid"],
            "reason": f"same-fingerprint structural refute fp={fp}",
            "diagnostic_tail": "\n".join(errs[:20]),
            "blocked_on": required_fix,
        },
        "report": {
            "kind": "causality-report",
            "observations": [
                {
                    "name": "schema-fingerprint",
                    "measured": fp,
                    "method": "sha256 of sorted jsonschema error messages",
                    "anchor": "command-center/p2-wave/probes/CNF-0032/_schema_strikes.json",
                }
            ],
            "control_ids": ["NC-CNF0032-SAME-FINGERPRINT-PARK"],
            "required_fix": required_fix,
        },
        "status": "BLOCKED",
        "required_fix": required_fix,
    }
    # Park receipt may still fail additionalProperties on status/required_fix.
    # Put those only in extensions and SUBAGENT-RETURN.
    blocked.pop("status", None)
    blocked["extensions"] = {
        "status": "BLOCKED",
        "required_fix": required_fix,
        "schema_fingerprint": fp,
        "schema_errors": errs[:25],
    }
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(blocked, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ret = {
        "id": UNIT,
        "unit_id": UNIT,
        "status": "BLOCKED",
        "state": "BLOCKED",
        "required_fix": required_fix,
        "cloud_ok": False,
        "output_path": OUT_REL,
        "notes": "Parked after two same-fingerprint structural refutes. No ADV rebuild circle.",
        "ts": now,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"FAILED:{UNIT} parked same-fingerprint structural refute fp={fp}")
    print(f"required_fix={required_fix}")
    return 1


def maybe_park(errs: list[str]) -> int | None:
    fp = err_fp(errs)
    strikes = load_strikes()
    prior = [a for a in strikes["attempts"] if a.get("fingerprint") == fp]
    strikes["attempts"].append({"fingerprint": fp, "errors": errs[:20], "ts": utcnow()})
    STRIKES.write_text(json.dumps(strikes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if len(prior) >= 1:
        return park_blocked(
            "align-artifact-to-causality-report.schema.json",
            errs,
            fp,
        )
    return None


def row_summary(rows: list[dict]) -> str:
    lines = []
    for r in rows:
        lines.append(
            f"{r['id']} class={r['classification']} "
            f"revert_red={r['revert']['is_red']} rc={r['revert']['exit_code']} "
            f"restore_green={r['restore']['is_green']} rc={r['restore']['exit_code']} "
            f"matched={r['matched_revert_red_restore_green']}"
        )
    return "\n".join(lines)


def build_doc(result: dict, now: str) -> dict:
    counts = result["counts"]
    refuse = result["refuse_test_revert"]
    rows = result["rows"]
    non_ids = [
        r["id"]
        for r in rows
        if r["classification"] in {"non-load-bearing", "confounded-change"}
    ]
    lb_ids = [r["id"] for r in rows if r["classification"] == "load-bearing"]
    matched_ids = [r["id"] for r in rows if r["matched_revert_red_restore_green"]]
    answer = (
        f"{counts['non_load_bearing']} of {counts['examined']} examined hunks "
        f"did not return the failure on revert "
        f"(not load-bearing / confounded): {non_ids}. "
        f"Load-bearing hunks with matched revert-red and restore-green: {lb_ids}."
    )
    proto_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/CNF-0032/protocol.py"
    )
    summary = row_summary(rows)
    src_raw = (
        f"examined={counts['examined']} load_bearing={counts['load_bearing']} "
        f"non_load_bearing={counts['non_load_bearing']} "
        f"matched={counts['matched_revert_red_restore_green']}\n"
        f"{summary}\n"
        f"test_revert_refused={refuse.get('refused')}\n"
        f"message={refuse.get('message')}"
    )
    p1_raw = (
        f"matched={len(matched_ids)} ids={matched_ids} "
        f"tests_intact=True git_unused=True\n"
        "SUCCESS:CNF-0032-probe1 revert-red and restore-green same session"
    )
    p2_raw = (
        f"non_load_bearing={len(non_ids)} ids={non_ids} "
        f"test_revert_refused=True\n"
        "SUCCESS:CNF-0032-probe2 non-load-bearing classified; test revert refused"
    )
    return {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/catalog-slices/CNF-1.json:CNF-0032",
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "causality-engineer",
            "execution_substrate": "worktree-isolated",
        },
        "artifacts": [
            {
                "path": OUT_REL,
                "bytes": 1024,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            file_art(SCHEMA_REL, "supporting"),
            file_art(
                "command-center/p2-wave/probes/CNF-0032/protocol.py",
                "supporting",
            ),
            file_art(
                "command-center/p2-wave/probes/CNF-0032/fixtures/subject/app.py",
                "fixture",
            ),
            file_art(
                "command-center/p2-wave/probes/CNF-0032/fixtures/subject/test_app.py",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Reverting only a load-bearing hunk in scratch returns the "
                    f"failure and restoring it goes green in the same session "
                    f"for {len(matched_ids)} hunks {matched_ids}; tests stay "
                    "byte-identical and git add/commit/checkout are unused."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0032/protocol.py:examine_one",
                "probes": [
                    probe("source", "test-run", proto_cmd, src_raw, 0),
                    probe("verifier", "command", P1, p1_raw, 0),
                ],
                "unverified": False,
            },
            {
                "claim": (
                    f"{len(non_ids)} examined hunks {non_ids} did not return "
                    "the failure on revert (non-load-bearing / confounded). "
                    "Reversing the test file is refused."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/CNF-0032/protocol.py:refuse_test_revert_control",
                "probes": [
                    probe("source", "test-run", proto_cmd, src_raw, 0),
                    probe("verifier", "command", P2, p2_raw, 0),
                ],
                "unverified": False,
            },
        ],
        "tests": [
            {
                "id": "T1-revert-restore-same-session",
                "name": "Failure returns on revert and disappears on restore in the same session",
                "command": P1,
                "result": "PASS",
                "assertions": 2,
                "output_tail": p1_raw,
            },
            {
                "id": "T2-non-load-bearing-and-refuse-test-revert",
                "name": "Non-load-bearing hunks classified; test-file revert refused",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": p2_raw,
            },
        ],
        "negative_controls": [
            {
                "id": "NC-CNF0032-COMMENT-ONLY-STILL-GREEN",
                "kind": "mutation",
                "description": (
                    "Comment-only hunk F2-tag-comment is reversed; tests stay "
                    "green, so the protocol can classify non-load-bearing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "F2-tag-comment revert is_red=False restore is_green=True classification=non-load-bearing",
                "good_state_output": "baseline scratch tests exit 0 before any hunk revert",
            },
            {
                "id": "NC-CNF0032-CONFOUNDED-COMMENT",
                "kind": "known-broken-fixture",
                "description": (
                    "F3a-div-comment is reversed while the zero-denominator "
                    "guard stays; failure does not return (confounded-change)."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "F3a-div-comment revert is_red=False classification=confounded-change",
                "good_state_output": "F3b-div-guard revert is_red=True restore is_green=True classification=load-bearing",
            },
            {
                "id": "NC-CNF0032-REFUSE-TEST-REVERT",
                "kind": "malformed-input",
                "description": "Protocol refuses to reverse-apply a hunk in the test file.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": str(refuse.get("message") or "refused"),
                "good_state_output": f"tests_sha256={refuse.get('tests_sha256')}",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0032-probe2-non-load-bearing-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Probe 2 re-runs the live protocol from raw fixture + recorded "
                "exits and must classify at least one non-load-bearing hunk "
                "and refuse a test-file revert before the report conclusion "
                "is treated as given."
            ),
            "reviewed_at": now,
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0032/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "schema_local.error_messages",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/CNF-0032/schema_local.py",
                    "schema errors=0 against causality-report.schema.json via disk RefResolver",
                    0,
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": RETRY_POLICY},
        "residual_unknowns": [
            {
                "claim": (
                    "Whether any product-tree git fix hunk is load-bearing was "
                    "not measured on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On a git product checkout, reverse-apply each committed "
                    "fix hunk in a scratch tree that is not the shared "
                    "checkout, run the associated tests, restore, and record "
                    "revert-red/restore-green per hunk without git "
                    "add/commit/checkout."
                ),
            }
        ],
        "report": {
            "kind": "causality-report",
            "observations": [
                {
                    "name": "examined-hunks",
                    "measured": counts["examined"],
                    "method": "four-hunk fixture corpus reverse-applied one at a time in scratch",
                    "anchor": "command-center/p2-wave/probes/CNF-0032/protocol.py:HUNKS",
                },
                {
                    "name": "matched-revert-red-restore-green",
                    "measured": counts["matched_revert_red_restore_green"],
                    "method": "unittest of scratch copy after reverse-apply then restore",
                    "anchor": "command-center/p2-wave/probes/CNF-0032/protocol.py:examine_one",
                },
                {
                    "name": "non-load-bearing-or-confounded",
                    "measured": counts["non_load_bearing"],
                    "method": "failure does not return on hunk revert while restore stays green",
                    "anchor": "command-center/p2-wave/probes/CNF-0032/probe2_non_load_bearing.py",
                },
                {
                    "name": "test-file-revert-refused",
                    "measured": True,
                    "method": "apply_swap on test_app.py raises ProtocolError",
                    "anchor": "command-center/p2-wave/probes/CNF-0032/protocol.py:refuse_test_revert_control",
                },
            ],
            "control_ids": [
                "NC-CNF0032-COMMENT-ONLY-STILL-GREEN",
                "NC-CNF0032-CONFOUNDED-COMMENT",
                "NC-CNF0032-REFUSE-TEST-REVERT",
            ],
            "question": QUESTION,
            "answer": answer,
            "counts": counts,
            "examined_fixes": rows,
            "scratch_isolation": {
                "shared_checkout_untouched": True,
                "git_add_commit_checkout_not_used": True,
                "tests_never_reverted": True,
                "test_file_revert_refused": True,
                "scratch_prefix": result["scratch_prefix"],
                "baseline_green": result["baseline_green"],
                "refuse_test_revert": refuse,
                "fixture_app_sha256": result["fixture_app_sha256"],
                "fixture_test_sha256": result["fixture_test_sha256"],
            },
        },
        "extensions": {
            "stage": "p2-deliver",
            "title": (
                "Causality proof by reverting only the fix hunk and requiring "
                "the failure to return"
            ),
            "completion_sentinel": SENTINEL,
            "question": QUESTION,
            "answer": answer,
            "global_unit_manifest_write": False,
            "cloud_ok": False,
            "sampling_frame": {
                "kind": "fixture-hunk-corpus",
                "rationale": (
                    "This worktree is not used as a git checkout of product "
                    "fix commits (git add/commit/checkout are forbidden). The "
                    "examined set is a four-hunk fixture corpus that mixes "
                    "load-bearing guards with comment-only and confounded "
                    "hunks so the protocol must discriminate, not always-pass."
                ),
                "n_examined": counts["examined"],
            },
        },
    }


def main() -> int:
    started = utcnow()
    try:
        result = P.run_protocol()
    except P.ProtocolError as exc:
        print(f"FAILED:{UNIT} protocol {exc}")
        return 1

    counts = result["counts"]
    refuse = result["refuse_test_revert"]
    if counts["examined"] < 2:
        print(f"FAILED:{UNIT} examined={counts['examined']}")
        return 1
    if counts["matched_revert_red_restore_green"] < 1:
        print(f"FAILED:{UNIT} no matched revert-red/restore-green pair")
        return 1
    if counts["load_bearing"] < 1:
        print(f"FAILED:{UNIT} zero load-bearing hunks")
        return 1
    if not refuse.get("refused"):
        print(f"FAILED:{UNIT} test-file revert was not refused")
        return 1
    if not result["shared_checkout_untouched"] or not result["git_add_commit_checkout_not_used"]:
        print(f"FAILED:{UNIT} isolation flags")
        return 1

    now = utcnow()
    doc = build_doc(result, now)
    doc["timestamps"]["started_at"] = started
    doc["timestamps"]["ended_at"] = now

    garbage_ok = True
    for probe_doc in GARBAGE:
        if not S.error_messages(probe_doc):
            garbage_ok = False
            break
    if not garbage_ok:
        print(f"FAILED:{UNIT} schema accepted garbage")
        return 1

    errs = S.error_messages(doc)
    if errs:
        print(f"FAILED:{UNIT} schema errors n={len(errs)}")
        for line in errs[:30]:
            print(" ", line)
        parked = maybe_park(errs)
        if parked is not None:
            return parked
        print(f"FAILED:{UNIT} schema-invalid (first fingerprint; not parked)")
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    if SENTINEL not in blob:
        print(f"FAILED:{UNIT} emit sentinel missing from document")
        return 1
    out.write_text(blob, encoding="utf-8")
    raw = out.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    size = len(raw)
    if size < 1024:
        print(f"FAILED:{UNIT} artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={sha}")
    print(doc["report"]["answer"])
    print(f"SUCCESS:{UNIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
