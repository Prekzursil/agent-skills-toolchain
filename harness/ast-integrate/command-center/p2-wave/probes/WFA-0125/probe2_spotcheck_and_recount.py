#!/usr/bin/env python3
"""Probe 2: independent recount + keyword-trap downgrade + NEITHER routing.

Does not call extract.extract_requirements. Re-parses the catalog with its
own regexes, recounts artifact cells, and runs the structured spot-check
on a planted keyword-only mention.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import extract as X  # noqa: E402  # spot_check / keyword_trap_record only

ART = REPO / X.OUT_REL
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

FAMILY_COUNT_RE = re.compile(
    r"(research/evidence|engineering/reliability|security/governance|"
    r"product/design|data/science|collective-intelligence/meta)\s+(\d+)",
    re.I,
)
DASH_LIST_RE = re.compile(
    r"Target:\s*(?:implement|register)\s+(\d+)\s+(?:library\s+)?"
    r"blueprints?\s+-\s+([a-z0-9]+(?:-[a-z0-9]+)*)"
    r"((?:\s*,\s*[a-z0-9]+(?:-[a-z0-9]+)*)*)",
    re.I,
)
BARE_REGISTER_RE = re.compile(
    r"Target:\s*register\s+([a-z0-9]+(?:-[a-z0-9]+)*"
    r"(?:\s*,\s*[a-z0-9]+(?:-[a-z0-9]+)*)+)\s+as library entries",
    re.I,
)
IMP_IDS = tuple(f"IMP-{n:04d}" for n in range(234, 257))
MAP = {
    "research/evidence": "research and evidence",
    "engineering/reliability": "engineering and reliability",
    "security/governance": "security and governance",
    "product/design": "product and strategy",
    "data/science": "data and science",
    "collective-intelligence/meta": "collective intelligence",
}


def split_ids(head: str, tail: str = "") -> list[str]:
    blob = head + (tail or "")
    return [p.strip().lower() for p in blob.split(",") if p.strip()]


def parse_ids(question: str) -> list[str]:
    m = DASH_LIST_RE.search(question or "")
    if m:
        ids = split_ids(m.group(2), m.group(3) or "")
        declared = int(m.group(1))
        if declared != len(ids):
            raise ValueError(f"declared {declared} parsed {len(ids)}: {ids}")
        return ids
    m = BARE_REGISTER_RE.search(question or "")
    if m:
        return split_ids(m.group(1))
    raise ValueError("no blueprint id list")


def main() -> int:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {
        u["id"]: u
        for u in (catalog.get("work_units") or [])
        if isinstance(u, dict) and isinstance(u.get("id"), str)
    }
    imp0178_q = str((by_id.get("IMP-0178") or {}).get("question_or_target") or "")
    fam_raw = {k.lower(): int(n) for k, n in FAMILY_COUNT_RE.findall(imp0178_q)}
    fam_sum = sum(fam_raw.values())
    print(f"RECOUNT family_raw={fam_raw} sum={fam_sum}")

    ids: list[str] = []
    for uid in IMP_IDS:
        rec = by_id.get(uid)
        if not isinstance(rec, dict):
            print(f"FAILED:WFA-0125-probe2 missing {uid}")
            return 1
        try:
            got = parse_ids(str(rec.get("question_or_target") or ""))
        except ValueError as exc:
            print(f"FAILED:WFA-0125-probe2 {uid} {exc}")
            return 1
        ids.extend(got)
    print(f"RECOUNT parsed_n={len(ids)} unique={len(set(ids))}")
    if len(ids) != fam_sum or len(set(ids)) != len(ids):
        print("FAILED:WFA-0125-probe2 recount != IMP-0178 sum or not unique")
        return 1

    if not ART.is_file():
        print("FAILED:WFA-0125-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    cells = [c for c in (doc.get("cells") or []) if isinstance(c, dict)]
    print(f"RECOUNT artifact_cells={len(cells)}")
    if len(cells) != fam_sum:
        print(f"FAILED:WFA-0125-probe2 cells {len(cells)} != {fam_sum}")
        return 1
    art_ids = [str(c.get("requirement_id") or "") for c in cells]
    if art_ids != ids:
        missing = sorted(set(ids) - set(art_ids))
        extra = sorted(set(art_ids) - set(ids))
        print(f"FAILED:WFA-0125-probe2 id set mismatch missing={missing[:8]} extra={extra[:8]}")
        return 1

    goals = [g for g in (doc.get("generation_lane_goals") or []) if isinstance(g, dict)]
    neither = [
        c
        for c in cells
        if str(c.get("status") or "") in {"NEITHER", "UNCOVERED"}
    ]
    print(f"RECOUNT neither_or_uncovered={len(neither)} goals={len(goals)}")
    if len(goals) != len(neither) or not goals:
        print("FAILED:WFA-0125-probe2 NEITHER cells not fully routed")
        return 1
    goal_ids = {str(g.get("requirement_id") or "") for g in goals}
    cell_ids = {str(c.get("requirement_id") or "") for c in neither}
    if goal_ids != cell_ids:
        print("FAILED:WFA-0125-probe2 generation goal ids != NEITHER cells")
        return 1
    uncited = [
        g
        for g in goals
        if "10902-10907" not in str(g.get("spec_cite") or "")
        or str(g.get("kind") or "") != "typed-generation-goal"
        or str(g.get("lane") or "") != "generation"
    ]
    if uncited:
        print(f"FAILED:WFA-0125-probe2 uncited or untyped goals n={len(uncited)}")
        return 1

    trap = X.keyword_trap_record("deep-research")
    check = X.spot_check("deep-research", trap)
    print(
        f"KEYWORD-TRAP pass={check['pass']} reason={check['reason']} "
        f"mention={check['keyword_mention']}"
    )
    if check["pass"] or check["reason"] != "keyword-only-mention":
        print("FAILED:WFA-0125-probe2 keyword trap was not downgraded")
        return 1
    structured_ok = {
        "id": "deep-research",
        "covers": ["deep-research"],
        "does": "unrelated prose",
    }
    ok = X.spot_check("deep-research", structured_ok)
    print(f"STRUCTURED-HIT pass={ok['pass']} reason={ok['reason']}")
    if not ok["pass"]:
        print("FAILED:WFA-0125-probe2 structured cover rejected")
        return 1

    art_trap = doc.get("keyword_trap") or {}
    if not art_trap.get("downgraded"):
        print("FAILED:WFA-0125-probe2 artifact keyword_trap.downgraded is false")
        return 1

    print(
        "NEGATIVE CONTROL verbatim: on a candidate whose does-text mentions "
        "deep-research but whose id is wf-unrelated-taxonomy-note, "
        f"spot_check.pass={check['pass']} reason={check['reason']}; "
        "on a record with structured id=deep-research, "
        f"spot_check.pass={ok['pass']}."
    )
    print("SUCCESS:WFA-0125-probe2 independent-recount keyword-trap routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
