#!/usr/bin/env python3
"""Probe 2: both-states control, negative control, schema non-vacuity, anchors.

Independent of the author's prose: re-runs leak_check / completeness_check
from fixtures. A review that did not execute the control is rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import catchup as C  # noqa: E402
import schema_bind as SB  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0020-elastic-scaling-mid-council-recruitment-and-catch-up-brief.md"
)
SCHEMA = REPO / "command-center/schema/council-design-note.schema.json"


def resolve_anchor(repo: Path, spec: str, snippet: str) -> tuple[bool, str]:
    if ":" not in spec:
        return False, "no-colon"
    path, _, rest = spec.partition(":")
    try:
        line = int(rest)
    except ValueError:
        return False, "bad-line"
    fp = repo / path
    if not fp.is_file():
        return False, f"missing:{path}"
    lines = fp.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, "oob"
    got = lines[line - 1]
    if snippet not in got:
        return False, f"snippet-miss:{path}:{line}"
    return True, f"{path}:{line}"


def schema_errors(doc) -> list[str]:
    return SB.errors(doc)


def main() -> int:
    live = C.run_both_states()
    print(live["negative_control_verbatim"])
    print(
        "silent_on_good={g} fires_on_bad={b} fires_on_starved={s} "
        "fires_on_unacked={u} silent_on_mood={m} fires_on_stealth={t}".format(
            g=live["silent_on_good"],
            b=live["fires_on_bad"],
            s=live["fires_on_starved"],
            u=live["fires_on_unacked"],
            m=live["silent_on_mood"],
            t=live["fires_on_stealth"],
        )
    )
    if not live.get("ok"):
        print("FAILED:CNL-0020-probe2 both-states control did not discriminate")
        return 1
    if not (live["silent_on_good"] and live["fires_on_bad"]):
        print("FAILED:CNL-0020-probe2 leak_check did not both-states")
        return 1
    if not live["fires_on_starved"]:
        print("FAILED:CNL-0020-probe2 starved fixture silent")
        return 1

    if not ART.is_file() or not SCHEMA.is_file():
        print("FAILED:CNL-0020-probe2 artifact or schema missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0020-probe2 self-declared {doc.get('state')}")
        return 1
    rpt = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rec = (
        (doc.get("measurements") or rpt.get("measurements") or {}).get("both_states")
        or {}
    )
    for k in (
        "silent_on_good",
        "fires_on_bad",
        "fires_on_starved",
        "fires_on_unacked",
        "silent_on_mood",
        "fires_on_stealth",
    ):
        if rec.get(k) != live.get(k):
            print(f"FAILED:CNL-0020-probe2 artifact mismatch {k}")
            return 1
    if "ANCHOR_LEAK" not in str(rec.get("negative_control_verbatim") or ""):
        print("FAILED:CNL-0020-probe2 negative control not recorded verbatim")
        return 1

    errs = schema_errors(doc)
    print(f"schema_errors_on_artifact={len(errs)}")
    if errs:
        print("FAILED:CNL-0020-probe2 artifact fails declared schema")
        for e in errs[:6]:
            print(f"  {e}")
        return 1
    garbage = {"totally": "unrelated", "passing_tests": 999999}
    g_errs = schema_errors(garbage)
    print(f"schema_errors_on_garbage={len(g_errs)}")
    if len(g_errs) < 3:
        print("FAILED:CNL-0020-probe2 schema vacuous on garbage")
        return 1
    mutant = copy.deepcopy(doc)
    if isinstance(mutant.get("report"), dict) and "claims" in mutant["report"]:
        del mutant["report"]["claims"]
    elif "claims" in mutant:
        del mutant["claims"]
    m_errs = schema_errors(mutant)
    print(f"schema_errors_on_drop_claims={len(m_errs)}")
    drop_report = copy.deepcopy(doc)
    if "report" in drop_report:
        del drop_report["report"]
    r_errs = schema_errors(drop_report)
    print(f"schema_errors_on_drop_report={len(r_errs)}")
    if not r_errs:
        print("FAILED:CNL-0020-probe2 dropping report still valid")
        return 1

    claims = doc.get("claims") or rpt.get("claims") or []
    confirmed = 0
    refuted = 0
    for i, row in enumerate(claims):
        if not isinstance(row, dict):
            print(f"FAILED:CNL-0020-probe2 claims[{i}] not object")
            return 1
        v = row.get("verdict")
        if v == "CONFIRMED":
            confirmed += 1
            ok, why = resolve_anchor(REPO, str(row.get("anchor") or ""), str(row.get("snippet") or ""))
            print(f"anchor[{i}] ok={ok} {why}")
            if not ok:
                print("FAILED:CNL-0020-probe2 unresolved CONFIRMED anchor")
                return 1
        elif v == "REFUTED":
            refuted += 1
            if row.get("defect_locus") not in {"DESIGN", "SENTENCE"}:
                print("FAILED:CNL-0020-probe2 REFUTED missing defect_locus")
                return 1
    if confirmed < 2 or refuted < 1:
        print(f"FAILED:CNL-0020-probe2 claim mix confirmed={confirmed} refuted={refuted}")
        return 1

    reviewer = doc.get("reviewer") or {}
    rpt_reviewer = rpt.get("reviewer") if isinstance(rpt.get("reviewer"), dict) else {}
    if reviewer.get("independent") is not True:
        print("FAILED:CNL-0020-probe2 reviewer not independent")
        return 1
    executed = (
        rpt.get("executed_both_states_control") is True
        or rpt_reviewer.get("executed_both_states_control") is True
        or reviewer.get("executed_both_states_control") is True
        or "executed_both_states_control=true" in str(reviewer.get("notes") or "").lower()
    )
    if not executed:
        print("FAILED:CNL-0020-probe2 reviewer did not execute control")
        return 1

    print("SUCCESS:CNL-0020-probe2 both-states negative-control schema anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
