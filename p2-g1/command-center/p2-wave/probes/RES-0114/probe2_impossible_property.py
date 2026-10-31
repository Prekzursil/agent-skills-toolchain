#!/usr/bin/env python3
"""Probe 2: name one hermeticity property an agent run can never satisfy.

Mechanically different from probe 1: this probe does not classify destination
lists. It checks the both-states control on P-CLOSED-WORLD-BIT-IDENTITY and
the E3-without-baseline promotion gate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import fixtures as F  # noqa: E402
import predicate as P  # noqa: E402
from engine import validate_against_schema  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT_ID}-probe2 {msg}")
    return 1


def main() -> int:
    live = P.agent_run_can_satisfy(C.IMPOSSIBLE_PROPERTY_ID, F.PROFILE_LIVE_AGENT)
    closed = P.agent_run_can_satisfy(C.IMPOSSIBLE_PROPERTY_ID, F.PROFILE_CLOSED_BUILD)
    print(f"impossible live_agent satisfiable={live} closed_build satisfiable={closed}")
    if live:
        return fail("live model+web was marked as satisfying closed-world bit-identity")
    if not closed:
        return fail("closed software build was marked unsatisfiable (detector silent in both states)")

    egress_live = P.agent_run_can_satisfy(C.CATCHING_PROPERTY_ID, F.PROFILE_LIVE_AGENT)
    egress_closed = P.agent_run_can_satisfy(C.CATCHING_PROPERTY_ID, F.PROFILE_CLOSED_BUILD)
    print(f"undeclared-egress live={egress_live} closed={egress_closed}")
    if not (egress_live and egress_closed):
        return fail("P-UNDECLARED-EGRESS is adoptable; detector must allow both profiles")

    ok, reason = P.can_promote(F.E3_NO_BASELINE)
    print(f"planted-no-baseline promote={ok} reason={reason}")
    if ok:
        return fail("headline without baseline promoted")
    if "baseline" not in reason and "E3" not in reason:
        return fail(f"promotion refusal reason too vague: {reason}")

    ok4, reason4 = P.can_promote(F.OVERCLAIM_BIT_IDENTITY)
    print(f"overclaim-bit-identity promote={ok4} reason={reason4}")
    if ok4:
        return fail("E4 overclaim promoted")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    errs = validate_against_schema(doc)
    if errs:
        return fail(f"schema {errs[0]}")

    imp = doc.get("impossible_property") or {}
    print(
        "artifact impossible id={i} satisfiable_live={s}".format(
            i=imp.get("id"),
            s=imp.get("satisfiable_by_agent_run_with_live_model_and_web"),
        )
    )
    if imp.get("id") != C.IMPOSSIBLE_PROPERTY_ID:
        return fail("impossible property not named")
    if imp.get("satisfiable_by_agent_run_with_live_model_and_web") is not False:
        return fail("artifact claims live agent can satisfy Definition 1")
    if not (imp.get("reason") or "").strip():
        return fail("impossible property has no reason")

    named = [p.get("id") for p in (doc.get("property_list") or []) if isinstance(p, dict)]
    if C.IMPOSSIBLE_PROPERTY_ID not in named:
        return fail("impossible property missing from property_list")
    row = next(p for p in doc["property_list"] if p.get("id") == C.IMPOSSIBLE_PROPERTY_ID)
    if row.get("impossible_for_live_model_and_web") is not True:
        return fail("property_list row not marked impossible")
    if row.get("agent_run_adoptable") is not False:
        return fail("impossible property marked adoptable")

    promoted = set(doc.get("promoted_mechanisms") or [])
    if "M-PLANTED-NO-BASELINE" in promoted:
        return fail("E3-no-baseline row was promoted")
    if "M-FULL-AGENT-BIT-IDENTITY" in promoted:
        return fail("overclaim bit-identity was promoted")

    reviewer = doc.get("reviewer") or {}
    if reviewer.get("default") != "REFUTED":
        return fail("refuter did not default to REFUTED")
    if reviewer.get("independent") is not True:
        return fail("reviewer not independent")
    if reviewer.get("read_conclusion_first") is not False:
        return fail("reviewer read conclusion first")
    refuted = reviewer.get("refuted_claims") or []
    if "M-FULL-AGENT-BIT-IDENTITY" not in refuted:
        return fail("overclaim not in refuted_claims")
    survivors = reviewer.get("surviving_claims") or []
    if not survivors:
        return fail("no surviving claims")
    for s in survivors:
        if not str(s.get("strongest_caveat") or "").strip():
            return fail(f"survivor {s.get('id')} missing strongest caveat")

    answers = doc.get("answers") or {}
    if answers.get("impossible_property_named") != C.IMPOSSIBLE_PROPERTY_ID:
        return fail("answers did not name the impossible property")

    print(
        "SUCCESS:RES-0114-probe2 impossible property "
        f"{C.IMPOSSIBLE_PROPERTY_ID} named; both-states discriminate; "
        "E3-no-baseline not promoted"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
