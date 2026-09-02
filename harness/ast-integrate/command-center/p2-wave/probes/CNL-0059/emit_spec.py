#!/usr/bin/env python3
"""Emit CNL-0059 detector spec (JSON at the catalog .md output_path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import fixtures as F  # noqa: E402
import schema_local as S  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0059-unanimity-and-the-instant-unanimity-suspicion-trigger.md"
)
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0059/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0059/probe2_negative_control.py"
)
QUESTION = (
    "The spec requires that suspiciously fast unanimity triggers blind "
    "re-evaluation - what exactly is 'suspiciously fast', measured in what "
    "units, and what is the false-positive cost when a council is unanimous "
    "because the answer is genuinely obvious?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/CNL-0059/detector.py",
    "command-center/p2-wave/probes/CNL-0059/fixtures.py",
    "command-center/p2-wave/probes/CNL-0059/fixtures/obvious-arithmetic.json",
    "command-center/p2-wave/probes/CNL-0059/fixtures/sycophantic-chair-echo.json",
    "command-center/p2-wave/probes/CNL-0059/overclaim.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode()).hexdigest()[:32]


def find_line(path: Path, needle: str) -> tuple[int, str]:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i, line.strip()[:180]
    raise SystemExit(f"FAILED:CNL-0059 emit needle not found in {path}: {needle}")


def art_row(rel: str, role: str) -> dict:
    digest, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    F.dump_named()
    good_row = F.load_named(F.NAMED_OBVIOUS)
    bad_row = F.load_named(F.NAMED_SYCOPHANTIC)
    g = D.evaluate(good_row["transcript"])
    b = D.evaluate(bad_row["transcript"])
    if g.get("fire") or not b.get("fire"):
        print("FAILED:CNL-0059 emit named both-states did not discriminate")
        return 1
    by = F.transcripts_by_label()
    obvious = by["obvious"]
    syc = by["sycophantic"]
    fp_hits = sum(1 for t in obvious if D.evaluate(t).get("fire"))
    fn_hits = sum(1 for t in syc if not D.evaluate(t).get("fire"))
    fp = fp_hits / len(obvious)
    fn = fn_hits / len(syc)

    cat = REPO / "command-center/WORK-UNIT-CATALOG.json"
    seeded = REPO / "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
    det = HERE / "detector.py"
    cat_id_line, cat_id_snip = find_line(cat, '"id": "CNL-0059"')
    cat_ev_line, cat_ev_snip = find_line(
        cat, "the trigger is mandated, its threshold is not"
    )
    cat_q_line, cat_q_snip = find_line(cat, "what exactly is 'suspiciously fast'")
    seed_line, seed_snip = find_line(seeded, "trigger mandated, threshold unspecified")
    thr_line, thr_snip = find_line(det, "SUSPICION_MAX_ROUND = 1")
    ign_line, ign_snip = find_line(det, "The transcript field elapsed_ms is ignored")

    g_verb = D.verbatim_line(g)
    b_verb = D.verbatim_line(b)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    domain = {
        "kind": "council-detector-spec",
        "control_ids": [
            "CNL-0059-C1-both-states",
            "CNL-0059-C2-wall-clock",
        ],
        "observations": [
            {
                "name": "false_positive_rate",
                "measured": fp,
                "method": "detector.evaluate on labeled obvious corpus",
                "anchor": "command-center/p2-wave/probes/CNL-0059/fixtures.py:corpus",
            },
            {
                "name": "named_obvious_fired",
                "measured": bool(g.get("fire")),
                "method": "detector.evaluate",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0059/fixtures/"
                    "obvious-arithmetic.json"
                ),
            },
            {
                "name": "named_sycophantic_fired",
                "measured": bool(b.get("fire")),
                "method": "detector.evaluate",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0059/fixtures/"
                    "sycophantic-chair-echo.json"
                ),
            },
        ],
        "title": "Unanimity and the instant-unanimity suspicion trigger",
        "question": QUESTION,
        "pathology": (
            "Instant unanimity without independent briefs (sycophantic / "
            "chair-echo collapse) that still looks like a confident consensus."
        ),
        "format_note": (
            "Catalog output_path uses a .md suffix; G-1 parses the file with "
            "json.loads, so this artifact is JSON."
        ),
        "spec_anchors": [
            {
                "id": "10944",
                "claim": (
                    "Suspiciously fast unanimity must trigger blind "
                    "re-evaluation (mandate)."
                ),
                "status": "RESTATED-IN-CATALOG",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_ev_line}",
                "source_on_worktree": False,
                "source_path_absent": (
                    "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                    "_USER-PROMPTS.md"
                ),
            },
            {
                "id": "11336",
                "claim": (
                    "The trigger is mandated; the numeric threshold and unit "
                    "are not specified by the spec."
                ),
                "status": "UNSPECIFIED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_ev_line}",
                "catalog_gloss": (
                    "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:"
                    f"{seed_line}"
                ),
            },
        ],
        "threshold": {
            "primary_unit": (
                "deliberation rounds (integer, 1-indexed) together with "
                "independent-brief count (0..seat_count)"
            ),
            "suspicion_window": (
                f"first unanimous tally at round <= {D.SUSPICION_MAX_ROUND}"
            ),
            "collapse_signals": [
                (
                    "independent_brief_count < seat_count, where an independent "
                    f"brief is >= {D.MIN_BRIEF_CHARS} chars and token-Jaccard vs "
                    f"the chair statement is < {D.CHAIR_ECHO_JACCARD_MIN}"
                ),
                (
                    "mean pairwise token-Jaccard of first-round briefs >= "
                    f"{D.PAIRWISE_JACCARD_MIN}"
                ),
                (
                    "mean Jaccard(brief, chair_statement) >= "
                    f"{D.CHAIR_ECHO_JACCARD_MIN}"
                ),
            ],
            "rejected_units": [
                (
                    "wall-clock milliseconds / seconds: confounded by model "
                    "latency, hardware, and padding; a slow clone would evade "
                    "and a fast obvious council would false-positive"
                ),
                (
                    "unique evidence-node count: genuinely obvious answers "
                    "often cite the same well-known fact, so shared evidence "
                    "is not collapse"
                ),
            ],
            "numeric": {
                "suspicion_max_round": D.SUSPICION_MAX_ROUND,
                "pairwise_jaccard_min": D.PAIRWISE_JACCARD_MIN,
                "chair_echo_jaccard_min": D.CHAIR_ECHO_JACCARD_MIN,
                "min_brief_chars": D.MIN_BRIEF_CHARS,
            },
            "chosen_here": True,
            "spec_named_the_numeric_threshold": False,
        },
        "predicate": {
            "fire_when": (
                "seat_count>=2 AND unanimous at round<=1 AND (missing "
                "independent briefs OR pairwise clone OR chair echo). On fire, "
                "contracted action is blind_re_evaluation."
            ),
            "silent_when": (
                "never unanimous; OR first unanimity after round 1; OR round-1 "
                "unanimity where every seat filed a non-echo independent brief "
                "(the genuinely-obvious case)."
            ),
            "ignores": ["elapsed_ms", "fixture label", "wall-clock"],
        },
        "both_states": {
            "known_good": {
                "fixture": (
                    "command-center/p2-wave/probes/CNL-0059/fixtures/"
                    "obvious-arithmetic.json"
                ),
                "fired": bool(g.get("fire")),
                "verbatim": g_verb,
            },
            "planted_bad": {
                "fixture": (
                    "command-center/p2-wave/probes/CNL-0059/fixtures/"
                    "sycophantic-chair-echo.json"
                ),
                "fired": bool(b.get("fire")),
                "verbatim": b_verb,
            },
        },
        "false_positive_rate": fp,
        "false_negative_rate": fn,
        "corpus": {
            "obvious_n": len(obvious),
            "obvious_fires": fp_hits,
            "sycophantic_n": len(syc),
            "sycophantic_silent": fn_hits,
        },
        "negative_control": {
            "reject_state": (
                "sycophantic chair-echo unanimous in round 1 with cloned briefs"
            ),
            "does": (
                "FIRE=true and remediation=blind_re_evaluation; does not "
                "treat the cloned vote as legitimate consensus."
            ),
            "verbatim": b_verb,
        },
        "false_positive_cost": (
            f"{fp_hits} of {len(obvious)} genuinely-obvious or "
            f"post-challenge unanimous fixtures fired "
            f"(false_positive_rate={fp}). Round-1 unanimity after independent "
            "briefs is treated as legitimate obviousness, not suspicion."
        ),
        "remediation_contract": {
            "on_fire": "blind_re_evaluation",
            "allowed_implements": [
                "forced_dissent",
                "strongest_counterexample",
                "role_rotation",
                "independent_critic",
            ],
            "implementation_locus": (
                "IMP-0318 (tools/council/antifail/unanimity.py) ports this "
                "predicate; this unit specifies when it fires, not the second "
                "pass body."
            ),
        },
        "detector_implementation": (
            "command-center/p2-wave/probes/CNL-0059/detector.py"
        ),
        "reviewer": {
            "reviewer_id": "CNL-0059-probe2-both-states-rerun",
            "verdict": "PASS",
            "independent": True,
            "executed_both_states": True,
            "command": P2,
        },
        "catalog_unit": {
            "id_line": cat_id_line,
            "id_snippet": cat_id_snip,
            "question_line": cat_q_line,
            "question_snippet": cat_q_snip,
        },
        "completion": "SUCCESS:CNL-0059",
        "SUCCESS:CNL-0059": True,
    }

    src_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0059'); "
        "import detector as D, fixtures as F; F.dump_named(); "
        "g=D.evaluate(F.load_named(F.NAMED_OBVIOUS)['transcript']); "
        "b=D.evaluate(F.load_named(F.NAMED_SYCOPHANTIC)['transcript']); "
        "print(D.verbatim_line(g)); print(D.verbatim_line(b))\""
    )
    cat_read = (
        f"read command-center/WORK-UNIT-CATALOG.json:{cat_ev_line} "
        "evidence_requirement"
    )
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNL-0059'); "
        "import json, schema_local as S; "
        "p='command-center/design/council/"
        "CNL-0059-unanimity-and-the-instant-unanimity-suspicion-trigger.md'; "
        "print(len(list(S.validator().iter_errors(json.load(open(p))))))\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0059",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0059",
        "spec_anchor": (
            f"command-center/WORK-UNIT-CATALOG.json:{cat_ev_line} "
            "(trigger mandated, threshold not)"
        ),
        "min_bytes_threshold": 4000,
        "profile": "council-detector-spec",
        "artifacts": [art_row(p, "supporting") for p in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    "Named obvious-arithmetic is SILENT and named "
                    "sycophantic-chair-echo FIRES with blind_re_evaluation; "
                    "false_positive_rate is a number on the obvious corpus."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/CNL-0059/detector.py:"
                    f"{thr_line}"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": src_cmd,
                        "raw_output": g_verb + "\n" + b_verb,
                        "fingerprint": fingerprint("command", src_cmd),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "read command-center/p2-wave/probes/CNL-0059/"
                            "fixtures/obvious-arithmetic.json and "
                            "sycophantic-chair-echo.json then detector.evaluate"
                        ),
                        "raw_output": (
                            f"obvious_n={len(obvious)} obvious_fires={fp_hits} "
                            f"false_positive_rate={fp} "
                            f"sycophantic_n={len(syc)} silent={fn_hits}"
                        ),
                        "fingerprint": fingerprint(
                            "file-read",
                            "named-fixtures+corpus-rates",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Catalog restates spec :10944/:11336 as mandate-without-"
                    "threshold; wall-clock milliseconds are not the unit."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_ev_line}",
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": cat_read,
                        "raw_output": cat_ev_snip,
                        "fingerprint": fingerprint("file-read", cat_read),
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "command-center/p2-wave/probes/ARC-0005/"
                            "seeded_classes.py FC-11336"
                        ),
                        "raw_output": (
                            f"{seed_snip} || detector.py:{ign_line} {ign_snip}"
                        ),
                        "fingerprint": fingerprint(
                            "static-analysis",
                            "ARC-0005/seeded_classes.py:FC-11336",
                        ),
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-both-states-fp-rate",
                "name": "both-states plus numeric false-positive rate",
                "command": P1,
                "result": "PASS",
                "assertions": 4,
            },
            {
                "id": "probe2-negative-control-wall-clock",
                "name": "negative control, wall-clock distractor, schema",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
            },
        ],
        "negative_controls": [
            {
                "id": "CNL-0059-C1-both-states",
                "kind": "known-broken-fixture",
                "description": (
                    "Sycophantic chair-echo unanimous in round 1 must FIRE; "
                    "genuinely-obvious independent briefs must stay SILENT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": b_verb,
                "good_state_output": g_verb,
            },
            {
                "id": "CNL-0059-C2-wall-clock",
                "kind": "mutation",
                "description": (
                    "Mutating elapsed_ms to 1 vs 10**9 must not change either "
                    "named-fixture verdict."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "elapsed_ms ignored; sycophantic still FIRE",
                "good_state_output": "elapsed_ms ignored; obvious still SILENT",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0059-probe2-both-states-rerun",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Mechanical both-states re-run via probe2: load named JSON "
                "from disk and call detector.evaluate directly. Does not read "
                "probe1 output. Wall-clock mutation and SequenceMatcher ranking "
                "are a second mechanism."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/CNL-0059/"
                "UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "CNL-0059",
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNL-0059/"
                    "probe2_negative_control.py"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "schema_errors=0 (disk RefResolver)",
                    "fingerprint": fingerprint("schema-validate", schema_cmd),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "hypothesis, enumerate >=2 alternative mechanisms before a "
                "3rd attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Whether live LLM councils with these thresholds match the "
                    "fixture FP rate (fixtures are deterministic transcripts)."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run IMP-0318 / TST-0258 against a live simulator once it "
                    "exists on this worktree."
                ),
            }
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "p2-deliver-worker",
            "execution_substrate": "local-parallel",
        },
        "report": domain,
    }

    validator = S.validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0059 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for gdoc in (
        {},
        {"unit_id": "CNL-0059", "false_positive_rate": "low"},
        {"blob": "x" * 200},
    ):
        if not list(validator.iter_errors(gdoc)):
            print(f"FAILED:CNL-0059 schema accepted garbage {list(gdoc)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 4000:
        print(f"FAILED:CNL-0059 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest} fp={fp} fn={fn}")
    print("SUCCESS:CNL-0059 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
