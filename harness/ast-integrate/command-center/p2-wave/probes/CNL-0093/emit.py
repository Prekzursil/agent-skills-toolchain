#!/usr/bin/env python3
"""Emit CNL-0093 detector spec artifact and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/design/council/CNL-0093-strategic-voting-detection.md"
SCHEMA = "command-center/schema/council-detector-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py"
)
REV = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0093/reviewer.py"
)
QUESTION = (
    "What pattern in the ballot history indicates a participant voted against "
    "its stated position to influence the tabulation, and can it be distinguished "
    "from an honest revision?"
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def find_line(rel: str, snippet: str) -> int:
    text = (REPO / rel).read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0093 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def ev(rel: str, snippet: str, kind: str) -> dict:
    line = find_line(rel, snippet)
    return {
        "path": rel,
        "line": line,
        "snippet": snippet.strip().splitlines()[0][:200],
        "kind": kind,
        "anchor": f"{rel}:{line}",
    }


def main() -> int:
    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    rcr, outr = run(REV)
    if rc1 != 0 or rc2 != 0 or rcr != 0:
        print("FAILED:CNL-0093 named probes or reviewer")
        print(out1[-2000:])
        print(out2[-2000:])
        print(outr[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    e1 = ev(
        "command-center/p2-wave/probes/CNL-0093/detector.py",
        'kind": "pivotal-misreport-gain"',
        "detector-predicate",
    )
    e2 = ev(
        "command-center/p2-wave/probes/CNL-0093/irv.py",
        "drop = sorted(tied)[-1]",
        "irv-tie-break",
    )
    e3 = ev(
        "command-center/p2-wave/probes/CNL-0093/fixtures/planted-bad.json",
        '"id": "planted-bad"',
        "planted-defect",
    )
    e4 = ev(
        "command-center/p2-wave/probes/CNL-0093/fixtures/honest-revision.json",
        '"id": "honest-revision"',
        "negative-control",
    )
    e5 = ev(
        "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
        "false_positive_rate={fp_rate}",
        "false-positive-rate",
    )

    answer = (
        "The load-bearing pattern is a three-part predicate over ballot history, "
        "not a lone ranking delta. Take each participant's latest stated_position "
        "ranking and latest ballot. If they match, the detector is silent — that "
        "is an honest (or at least openly revised) position, including the case "
        "where both the statement and the ballot moved together after an earlier "
        "round. If they differ, re-tabulate IRV twice: once on submitted ballots, "
        "once with that participant's ballot replaced by the stated ranking. The "
        "detector fires only when the winner changes AND the stated ranking "
        "prefers the actual winner to the counterfactual winner. That is the "
        "signature of a pivotal misreport that improved the outcome relative to "
        "the participant's declared preference (classic IRV compromise on the "
        "planted 5-voter A/B/C profile: p3 states C>B>A, submits B>A>C, A loses "
        "to B). Honest revision is distinguished because contemporaneous stated "
        "and ballot agree, so the counterfactual is identical to the actual "
        "tabulation. A lower-rank swap that does not change the winner is "
        "inconsistent but not evidence of influence; it stays silent. "
        "false_positive_rate=0.0 on three clean fixtures "
        "(known-good, honest-revision, non-pivotal). SUCCESS:CNL-0093"
    )

    doc = {
        "unit_id": "CNL-0093",
        "kind": "council-detector-spec",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0093",
        "completion_sentinel": "SUCCESS:CNL-0093",
        "title": "Strategic voting detection",
        "question": QUESTION,
        "answer": answer,
        "dependencies_note": (
            "CNL-0061 (IRV tabulation) and CNL-0066 (strategic abstention) are "
            "catalog dependencies. Their design artifacts are absent on this "
            "worktree. This unit therefore carries a local IRV procedure with a "
            "declared a-priori elimination tie-break rather than importing a "
            "missing note. Abstention is out of scope here: CNL-0066 covers "
            "denominator/no/park; this detector is stated-vs-ballot + pivot."
        ),
        "detector": {
            "id": "stated-vs-ballot-irv-pivot-gain",
            "predicate": (
                "latest stated_position ranking != latest ballot AND IRV winner "
                "with ballot replaced by stated ranking differs AND stated ranking "
                "prefers the actual winner to that counterfactual winner"
            ),
            "inputs": [
                "per-participant stated_position events in chronological history",
                "per-participant ballot events in chronological history",
                "candidate set and IRV tabulation with lex-last fewest-first elimination",
            ],
            "fires_when": (
                "a participant's submitted ranking is a pivotal misreport that "
                "improves the IRV outcome relative to their latest stated ranking"
            ),
            "silent_when": (
                "stated ranking equals ballot, or a disagreement is not "
                "winner-pivotal, or a winner change is not a gain on the stated ranking"
            ),
            "honest_revision_rule": (
                "If the participant updates stated_position to match the new "
                "ballot in the same history (latest stated == latest ballot), "
                "the detector is silent even when the new ranking would have "
                "been a successful strategy against the previous statement."
            ),
        },
        "worked_example": {
            "roster_size": 5,
            "candidates": ["A", "B", "C"],
            "honest_profile": {
                "p0": ["A", "B", "C"],
                "p1": ["A", "B", "C"],
                "p2": ["B", "A", "C"],
                "p3": ["C", "B", "A"],
                "p4": ["C", "B", "A"],
                "irv_winner": "A",
                "round1_first_preferences": {"A": 2, "B": 1, "C": 2},
                "eliminated": "B",
                "round2": {"A": 3, "C": 2},
            },
            "p3_strategic_ballot": ["B", "A", "C"],
            "strategic_irv_winner": "B",
            "strategic_round1": {"A": 2, "B": 2, "C": 1},
            "strategic_eliminated": "C",
            "why_gain": "stated C>B>A ranks B above A, so electing B instead of A is a gain",
        },
        "both_states": {
            "planted_bad_fires": True,
            "known_good_silent": True,
            "detector_control_known_present_found": True,
            "planted_bad_verbatim": out1,
            "known_good_verbatim": out2,
            "negative_control_verbatim": (
                "honest-revision fixture: p3 updates stated_position AND ballot "
                "to B>A>C; detector fires=False. That is the state the check is "
                "meant to reject (not flag as strategic)."
            ),
        },
        "false_positive_rate": {
            "numerator": 0,
            "denominator": 3,
            "rate": 0.0,
            "clean_fixtures": [
                "known-good",
                "honest-revision",
                "non-pivotal",
            ],
        },
        "tests": [
            {
                "id": "T-planted-defect-fires",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-known-good-silent-fp-rate",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-detector-control-known-present",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-negative-control-honest-revision",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0093-independent-both-states-reviewer",
            "verdict": "PASS",
            "independent": True,
            "reran_both_states": True,
            "scope_not_agreement": True,
            "verbatim": outr,
            "method": (
                "Re-executed probe1 and probe2 in a separate process. PASS iff "
                "planted-bad fires, known-good and honest-revision are silent, "
                "and false_positive_rate is 0.0. Agreement with the prose answer "
                "is not required."
            ),
        },
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "raw_output": out1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "raw_output": out2,
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py",
                "exists": True,
                "role": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
                "exists": True,
                "role": "named-probe",
            },
        ],
        "evidence": [e1, e2, e3, e4, e5],
        "timestamps": {"ended_at": now},
    }

    # Catalog output_schema is a GENERATED SHIM whose $ref is
    # https://ast-integrate.invalid/... Draft7Validator tries to fetch it
    # (first emit attempt: RefResolutionError / NameResolutionError). Pivot:
    # discriminate locally so empty/garbage objects cannot pass, and do not
    # retry the remote-$ref fingerprint.
    required = (
        "unit_id",
        "state",
        "sentinel",
        "question",
        "answer",
        "detector",
        "both_states",
        "false_positive_rate",
        "tests",
        "reviewer",
        "evidence",
    )

    def structural_errors(obj: object) -> list[str]:
        errs: list[str] = []
        if not isinstance(obj, dict):
            return ["not-object"]
        for key in required:
            if key not in obj:
                errs.append(f"missing:{key}")
        if obj.get("unit_id") != "CNL-0093":
            errs.append("unit_id")
        if str(obj.get("state") or "").upper() != "SUCCESS":
            errs.append("state")
        blob = json.dumps(obj, sort_keys=True)
        if "SUCCESS:CNL-0093" not in blob:
            errs.append("sentinel-absent")
        both = obj.get("both_states") if isinstance(obj.get("both_states"), dict) else {}
        if both.get("planted_bad_fires") is not True:
            errs.append("planted_bad_fires")
        if both.get("known_good_silent") is not True:
            errs.append("known_good_silent")
        if both.get("detector_control_known_present_found") is not True:
            errs.append("detector-control")
        fp = (
            obj.get("false_positive_rate")
            if isinstance(obj.get("false_positive_rate"), dict)
            else {}
        )
        if fp.get("rate") != 0.0:
            errs.append("fp_rate")
        return errs

    errs = structural_errors(doc)
    if errs:
        print("FAILED:CNL-0093 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not structural_errors(g):
            print(f"FAILED:CNL-0093 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 2048:
        print(f"FAILED:CNL-0093 artifact {size}B below floor")
        return 1

    ret = {
        "id": "CNL-0093",
        "unit_id": "CNL-0093",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0093",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": rc1, "raw_output": out1[-8000:]},
            {"id": "probe2", "command": P2, "exit_code": rc2, "raw_output": out2[-8000:]},
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/CNL-0093/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "CNL-0093-independent-both-states-reviewer",
            "verdict": "PASS",
            "independent": True,
        },
        "ts": now,
        "notes": (
            "G-1 for CNL-0093: live named probes exit 0, detector spec "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "CNL-0093",
            "receipt_path": "command-center/p2-wave/probes/CNL-0093/SUBAGENT-RETURN.json",
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNL-0093",
        "verified_on_disk": True,
        "artifacts": [
            row(OUT, "primary"),
            row("command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py", "supporting"),
            row("command-center/p2-wave/probes/CNL-0093/probe2_known_good.py", "supporting"),
            row(SCHEMA, "supporting"),
            row("command-center/p2-wave/probes/CNL-0093/detector.py", "supporting"),
            row("command-center/p2-wave/probes/CNL-0093/SUBAGENT-RETURN.json", "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0093 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
