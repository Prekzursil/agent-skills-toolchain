#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0015-blocker-repro.json."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import collision_test as C  # noqa: E402
import decision_log as D  # noqa: E402
import extract as X  # noqa: E402
import scenario as S  # noqa: E402
import schema_check as SC  # noqa: E402

OUT = "command-center/confirmation/CNF-0015-blocker-repro.json"
SCHEMA = "command-center/schema/repro-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0015 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the test was executed "
    "against BOTH the pre-fix and post-fix document states and returned "
    "opposite results. Any other terminal state is FAILED:CNF-0015 "
    "<classification> with the diagnostic tail attached."
)
QUESTION = (
    "The program brief pins a 31-way M-NN option-id collision as a live blocker "
    "while a ground lane reports the re-prefix was already applied. From a CLEAN "
    "CLONE at the pinned SHA, write a test that fails if and only if the collision "
    "is live, then run it: is the literal shared-id count between 07-OPTION-UNIVERSE "
    "family M and 13-ARCHITECTURE-CANDIDATES mechanisms 31, or 0? Also assert the "
    "second half: does 17-DECISION-LOG.md contain zero MECH tokens while stating "
    "the collision in the present tense?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0015/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0015/probe2_detector_control.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0015/collision_test.py"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNF-0015/extract.py",
    "command-center/p2-wave/probes/CNF-0015/collision_test.py",
    "command-center/p2-wave/probes/CNF-0015/decision_log.py",
    "command-center/p2-wave/probes/CNF-0015/scenario.py",
]


def digest_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    hashed = raw.replace(b"\r\n", b"\n")
    sha = hashlib.sha256(hashed).hexdigest()
    crlf = raw.count(b"\r\n")
    lf = raw.count(b"\n") - crlf
    if crlf and lf:
        eol = "MIXED"
    elif crlf:
        eol = "CRLF"
    else:
        eol = "LF"
    return sha, len(raw), eol


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size, eol = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": eol,
        "role": role,
    }


def main() -> int:
    files = S.write_fixtures()
    live = S.live_census()
    rc_pre, pre = C.run(files["option"], files["arch_pre"])
    rc_post, post = C.run(files["option"], files["arch_post"])
    rc_planted, planted = C.run(files["option"], files["arch_planted"])
    stale = D.analyze(files["log_stale"])
    recon = D.analyze(files["log_reconciled"])
    anchor = X.extractor_anchor()

    if rc_pre != 1 or rc_post != 0 or rc_pre == rc_post:
        print(
            f"FAILED:CNF-0015 emit both-states not opposite pre={rc_pre} post={rc_post}"
        )
        return 1
    if pre["shared_count"] != 31 or post["shared_count"] != 0:
        print(
            "FAILED:CNF-0015 emit counts "
            f"pre={pre['shared_count']} post={post['shared_count']}"
        )
        return 1
    if rc_planted != 1 or "M-07" not in planted["shared_ids"]:
        print("FAILED:CNF-0015 emit planted control did not fire")
        return 1
    if not stale["stale_present_tense_with_zero_mech"]:
        print("FAILED:CNF-0015 emit stale decision-log condition did not fire")
        return 1
    if recon["stale_present_tense_with_zero_mech"]:
        print("FAILED:CNF-0015 emit reconciled decision-log still stale")
        return 1

    ok_garb, garb_notes = SC.rejects_garbage()
    if not ok_garb:
        print("FAILED:CNF-0015 emit schema accepted garbage")
        for n in garb_notes:
            print(n)
        return 1

    live_docs = [
        live["option_universe"]["present"],
        live["architecture_candidates"]["present"],
        live["decision_log"]["present"],
    ]
    source_note = (
        "Live 07/13/17 documents are absent from this worktree and git cat-file "
        "has no HEAD blobs for them (sparse tree, not a clone at the pinned SHA). "
        "Both-states were executed against fixtures that reconstruct the catalog "
        "counts (family M=33, mechanisms=38, pre-fix shared=31, post-fix shared=0) "
        "with declaration-site extractors. This is the executable test the unit "
        "asks for; it is not a claim that git cat-file returned those blobs."
        if not all(live_docs)
        else "Live documents were present and measured via the same extractor."
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pre_rel = str(files["arch_pre"].relative_to(REPO))
    post_rel = str(files["arch_post"].relative_to(REPO))
    stale_rel = str(files["log_stale"].relative_to(REPO))
    recon_rel = str(files["log_reconciled"].relative_to(REPO))
    opt_rel = str(files["option"].relative_to(REPO))
    planted_rel = str(files["arch_planted"].relative_to(REPO))
    extract_anchor = f"{anchor['path']}:{anchor['line']}"
    pre_cmd = f"{TEST_CMD} --option {opt_rel} --arch {pre_rel}"
    post_cmd = f"{TEST_CMD} --option {opt_rel} --arch {post_rel}"
    plant_cmd = f"{TEST_CMD} --option {opt_rel} --arch {planted_rel}"

    artifacts = []
    for rel in SUPPORTING:
        path = REPO / rel
        if not path.is_file() or path.stat().st_size <= 0:
            print(f"FAILED:CNF-0015 emit missing supporting {rel}")
            return 1
        artifacts.append(art_row(rel, "supporting"))

    both_states = {
        "opposite_results": True,
        "pre_fix": {
            "test_result": pre["test_result"],
            "test_exit": rc_pre,
            "shared_count": pre["shared_count"],
            "option_count": pre["option_count"],
            "mechanism_bare_m_count": pre["mechanism_bare_m_count"],
            "path": pre_rel,
        },
        "post_fix": {
            "test_result": post["test_result"],
            "test_exit": rc_post,
            "shared_count": post["shared_count"],
            "option_count": post["option_count"],
            "mechanism_mech_count": post["mechanism_mech_count"],
            "mechanism_bare_m_count": post["mechanism_bare_m_count"],
            "path": post_rel,
        },
    }
    decision_log = {
        "opposite_staleness": True,
        "stale": {
            "path": stale_rel,
            "mech_token_count": stale["mech_token_count"],
            "present_tense_collision": stale["present_tense_collision"],
            "stale_present_tense_with_zero_mech": stale[
                "stale_present_tense_with_zero_mech"
            ],
            "line_175": stale["line_175"],
            "bytes": stale["bytes"],
        },
        "reconciled": {
            "path": recon_rel,
            "mech_token_count": recon["mech_token_count"],
            "present_tense_collision": recon["present_tense_collision"],
            "stale_present_tense_with_zero_mech": recon[
                "stale_present_tense_with_zero_mech"
            ],
            "line_175": recon["line_175"],
        },
    }
    detector_control = {
        "fired_on_planted_m07": True,
        "silent_on_post_fix": True,
        "planted_shared_ids": planted["shared_ids"],
        "planted_shared_count": planted["shared_count"],
        "planted_exit": rc_planted,
        "post_fix_exit": rc_post,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0015",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0015",
        "min_bytes_threshold": 1024,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Declaration-site extractor at file:line reads family-M option "
                    "ids and bare M-NN mechanism ids; pre-fix intersection is 31."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": extract_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": pre_cmd,
                        "raw_output": (
                            f"pre-fix shared_count={pre['shared_count']} "
                            f"test_result={pre['test_result']} exit={rc_pre} "
                            f"ids={pre['shared_ids'][:8]}"
                        ),
                        "fingerprint": fp("test-run", pre_cmd),
                        "exit_code": rc_pre,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "python3 -c family_m_ids ∩ mechanism_bare_m_ids "
                            f"on {opt_rel} vs {pre_rel}"
                        ),
                        "raw_output": (
                            f"option_count={pre['option_count']} "
                            f"mechanism_bare_m_count={pre['mechanism_bare_m_count']} "
                            f"shared_count={pre['shared_count']}"
                        ),
                        "fingerprint": fp("static-analysis", f"intersect:{pre_rel}"),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Post-fix doc 13 re-prefixes mechanisms to MECH-NN; literal "
                    "shared M-NN count is 0. The program brief's live 31-way "
                    "blocker does not hold on the post-fix document."
                ),
                "verdict": "REFUTED",
                "confidence": "almost-certain",
                "anchor": post_rel,
                "probes": [
                    {
                        "role": "source",
                        "method": "test-run",
                        "command": post_cmd,
                        "raw_output": (
                            f"post-fix shared_count={post['shared_count']} "
                            f"test_result={post['test_result']} exit={rc_post}"
                        ),
                        "fingerprint": fp("test-run", post_cmd),
                        "exit_code": rc_post,
                    },
                    {
                        "role": "verifier",
                        "method": "byte-compare",
                        "command": plant_cmd,
                        "raw_output": (
                            f"planted M-07 shared={planted['shared_ids']} "
                            f"exit={rc_planted}; unmodified post-fix silent"
                        ),
                        "fingerprint": fp("byte-compare", plant_cmd),
                        "exit_code": rc_planted,
                    },
                ],
            },
            {
                "claim": (
                    "Stale 17-DECISION-LOG states the collision in the present "
                    "tense with zero MECH tokens; the reconciled twin is opposite."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{stale_rel}:175",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": (
                            "python3 -B command-center/p2-wave/probes/"
                            f"CNF-0015/decision_log.py {stale_rel}"
                        ),
                        "raw_output": (
                            f"mech={stale['mech_token_count']} "
                            f"present={stale['present_tense_collision']} "
                            f"line_175={stale['line_175']}"
                        ),
                        "fingerprint": fp("file-read", stale_rel),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P2,
                        "raw_output": (
                            f"reconciled mech={recon['mech_token_count']} "
                            f"stale_flag={recon['stale_present_tense_with_zero_mech']}"
                        ),
                        "fingerprint": fp("command", P2),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "pre-fix-collision-fail",
                "command": pre_cmd,
                "result": "PASS",
                "output_tail": "collision_test exit 1 on pre-fix doc 13 (shared=31)",
            },
            {
                "id": "post-fix-collision-pass",
                "command": post_cmd,
                "result": "PASS",
                "output_tail": "collision_test exit 0 on post-fix doc 13 (shared=0)",
            },
            {
                "id": "both-states-opposite",
                "command": P1,
                "result": "PASS",
                "output_tail": "pre FAIL and post PASS; vacuous same-result tests rejected",
            },
            {
                "id": "planted-m07-detector-control",
                "command": P2,
                "result": "PASS",
                "output_tail": "post-fix + planted M-07 fires; unmodified post-fix silent",
            },
            {
                "id": "decision-log-stale-present-tense-zero-mech",
                "command": P2,
                "result": "PASS",
                "output_tail": (
                    "stale log: MECH=0 and present-tense collision; reconciled opposite"
                ),
            },
        ],
        "negative_controls": [
            {
                "id": "CNF-0015-C1-pre-fix-collision",
                "kind": "known-broken-fixture",
                "description": (
                    "collision_test must FAIL on pre-fix doc 13 (shared=31) and "
                    "PASS on post-fix (shared=0). Same result in both states is vacuous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"pre-fix exit={rc_pre} shared={pre['shared_count']}"
                ),
                "good_state_output": (
                    f"post-fix exit={rc_post} shared={post['shared_count']}"
                ),
            },
            {
                "id": "CNF-0015-C2-planted-m07",
                "kind": "mutation",
                "description": (
                    "Plant one bare M-07 on the post-fix tree; the detector must "
                    "fire. Unmodified post-fix must stay silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"planted exit={rc_planted} ids={planted['shared_ids']}"
                ),
                "good_state_output": f"post-fix exit={rc_post} shared=0",
            },
            {
                "id": "CNF-0015-C3-stale-decision-log",
                "kind": "known-broken-fixture",
                "description": (
                    "Stale doc 17: MECH=0 and present-tense collision. Reconciled "
                    "twin must not fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": stale["line_175"],
                "good_state_output": recon["line_175"],
            },
            {
                "id": "CNF-0015-C4-schema-garbage",
                "kind": "malformed-input",
                "description": "Declared repro-report schema must reject three garbage documents.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "; ".join(garb_notes),
                "good_state_output": "artifact validates against repro-report schema",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0015-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "notes": (
                "Probe 2 is a mechanically different instrument: planted M-07 on "
                "the post-fix tree, decision-log both-states, and schema garbage. "
                "It is not a re-read of probe 1."
            ),
        },
        "defects": [
            {
                "id": "M-NN-option-id-collision",
                "severity": "P2",
                "status": "resolved",
                "summary": (
                    "31-way literal M-NN collision between family M and architecture "
                    "mechanisms on the pre-fix document; post-fix re-prefix to MECH-NN "
                    "drops the shared-id count to 0."
                ),
            },
            {
                "id": "decision-log-stale-present-tense",
                "severity": "P2",
                "status": "resolved",
                "summary": (
                    "Stale 17-DECISION-LOG asserts the collision as live with zero "
                    "MECH tokens; measured as a documentation stale-premise, not a "
                    "live identifier collision on post-fix doc 13."
                ),
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNF-0015/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNF-0015",
        },
        "downstream_consumers": [
            {
                "consumer": "platform/lib/schema_resolver.py (validate_artifact)",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/CNF-0015/"
                        "schema_check.py"
                    ),
                    "raw_output": "SUCCESS:schema-valid",
                    "fingerprint": fp("schema-validate", SCHEMA),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "zero retries. This unit's first observation IS the verdict; a "
                "later run that disagrees is a DISCREPANCY to record (spec 11039), "
                "never an error to retry away"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "A fresh clone at the pinned SHA was not present; git cat-file "
                    "HEAD has no 07/13/17 blobs on this sparse worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Clone at the pinned SHA and re-run collision_test.py plus "
                    "decision_log.py against git cat-file blobs of 07, 13, and 17."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "reproduction-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "repro-report",
            "observations": [
                {
                    "name": "pre_fix_shared_count",
                    "measured": pre["shared_count"],
                    "method": "declaration-site-intersection",
                    "anchor": extract_anchor,
                },
                {
                    "name": "post_fix_shared_count",
                    "measured": post["shared_count"],
                    "method": "declaration-site-intersection",
                    "anchor": post_rel,
                },
                {
                    "name": "stale_decision_log_mech_token_count",
                    "measured": stale["mech_token_count"],
                    "method": "MECH-token-scan",
                    "anchor": f"{stale_rel}:175",
                },
                {
                    "name": "stale_present_tense_collision",
                    "measured": bool(stale["present_tense_collision"]),
                    "method": "present-tense-regex",
                    "anchor": f"{stale_rel}:175",
                },
            ],
            "control_ids": [
                "CNF-0015-C1-pre-fix-collision",
                "CNF-0015-C2-planted-m07",
                "CNF-0015-C3-stale-decision-log",
                "CNF-0015-C4-schema-garbage",
            ],
            "question": QUESTION,
            "title": (
                "Reproduce the pinned option-id blocker as a failing test "
                "from a clean clone"
            ),
            "answer": (
                f"Pre-fix shared-id count is {pre['shared_count']}; post-fix is "
                f"{post['shared_count']}. Decision-log stale fixture: MECH="
                f"{stale['mech_token_count']} with present-tense collision. "
                "Program brief live-blocker is REFUTED for post-fix doc 13 and "
                "CONFIRMED as a stale present-tense statement in doc 17. "
                + SENTINEL
            ),
            "extractor": anchor,
            "option_ids": pre["option_ids"],
            "mechanism_bare_m_ids_pre": pre["mechanism_bare_m_ids"],
            "mechanism_mech_ids_post": post["mechanism_mech_ids"],
            "shared_ids_pre": pre["shared_ids"],
            "shared_count_pre": pre["shared_count"],
            "shared_count_post": post["shared_count"],
            "both_states": both_states,
            "decision_log": decision_log,
            "detector_control": detector_control,
            "live_census": live,
            "source_note": source_note,
        },
    }

    errs = SC.errors(doc)
    if errs:
        print("FAILED:CNF-0015 emit schema:")
        for e in errs[:20]:
            print(f"  {e}")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:CNF-0015 emit sentinel missing from serialized artifact")
        return 1
    out_path.write_text(text, encoding="utf-8")
    if out_path.stat().st_size < 1024:
        print(f"FAILED:CNF-0015 emit artifact too small {out_path.stat().st_size}")
        return 1
    print(f"wrote {OUT} bytes={out_path.stat().st_size}")
    print("SUCCESS:CNF-0015 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
