#!/usr/bin/env python3
"""Probe 2: alias collapse, independent content proof, floor carry.

A command that only invokes a skill collapses to that skill id with an
ALIAS edge. Independent proof (alias_proof.py) must agree. collapsed_count
is the OWN-PROCEDURE count carried for WFA-0123.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import adapter as A  # noqa: E402
import alias_proof as P  # noqa: E402
import corpus as C  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0048-adapter-slash-command.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0048-probe2 {msg}")
    return 1


def main() -> int:
    C.materialize()
    rows = A.classify_dir(C.IFAMILY, repo=REPO, detect_alias=True)
    if len(rows) != 31:
        return fail(f"I-family n={len(rows)} expected 31")

    aliases = [r for r in rows if r.verdict == A.ALIAS]
    owns = [r for r in rows if r.verdict == A.OWN_PROCEDURE]
    print(f"raw=31 alias={len(aliases)} own={len(owns)} collapsed={len(owns)}")

    if not aliases:
        return fail("expected at least one ALIAS in the I-family")
    if len(aliases) + len(owns) != 31:
        return fail("verdict partition != 31")

    for cls in aliases:
        path = C.IFAMILY / f"{cls.command_id}.md"
        proof = P.prove_alias(path, expected_skill=cls.skill_id)
        print(
            f"alias {cls.command_id} -> {cls.skill_id} "
            f"added_stages={proof['added_stage_count']} ok={proof['alias_ok']}"
        )
        if not proof["alias_ok"]:
            return fail(f"independent proof rejected {cls.command_id}: {proof}")
        if proof["added_stage_count"] != 0:
            return fail(f"{cls.command_id} added stages under independent proof")
        ir = A.to_ir(cls)
        if ir.get("alias_of") != cls.skill_id:
            return fail(f"{cls.command_id} IR alias_of mismatch")
        if ir["stages"]:
            return fail(f"{cls.command_id} IR retained stages after collapse")

    # Dedicated thin invoke: cmd-docs
    docs = next(r for r in rows if r.command_id == "cmd-docs")
    if docs.verdict != A.ALIAS or docs.skill_id != "skill:docs":
        return fail(f"cmd-docs {docs.verdict} {docs.skill_id}")

    # Use-versus-mention: numbered list in description must not become stages.
    aside = next(r for r in rows if r.command_id == "cmd-aside")
    print(
        f"cmd-aside verdict={aside.verdict} skill_id={aside.skill_id} "
        f"stages={len(aside.stages)}"
    )
    if aside.verdict != A.ALIAS:
        return fail("cmd-aside description list was mistaken for stages")

    for cls in owns:
        ir = A.to_ir(cls)
        if not ir["stages"]:
            return fail(f"{cls.command_id} OWN-PROCEDURE has no stages")
        for st in ir["stages"]:
            if "path" not in st["source_anchor"] or "line" not in st["source_anchor"]:
                return fail(f"{st['id']} missing source_anchor")
        if ir.get("runtime_entrypoint"):
            return fail(f"{cls.command_id} IR has runtime_entrypoint")

    collapsed = len(owns)
    if not ART.is_file():
        return fail("artifact missing; emit_report.py must run first")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"artifact self-declared {doc.get('state')}")
    if "SUCCESS:WFA-0048" not in ART.read_text(encoding="utf-8"):
        return fail("sentinel absent")
    fc = doc.get("floor_carry") or {}
    if fc.get("raw_count") != 31:
        return fail(f"floor raw_count={fc.get('raw_count')}")
    if fc.get("collapsed_count") != collapsed:
        return fail(
            f"floor collapsed_count={fc.get('collapsed_count')} live={collapsed}"
        )
    if fc.get("alias_count") != len(aliases):
        return fail("floor alias_count mismatch")
    if fc.get("consumer_unit") != "WFA-0123":
        return fail("floor_carry missing WFA-0123 consumer")
    edges = doc.get("alias_edges") or []
    if len(edges) != len(aliases):
        return fail(f"alias_edges {len(edges)} != {len(aliases)}")
    if any(e.get("kind") != "ALIAS" for e in edges):
        return fail("alias edge kind missing")

    print(
        json.dumps(
            {
                "raw": 31,
                "alias": len(aliases),
                "own": len(owns),
                "collapsed": collapsed,
                "consumer": "WFA-0123",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:WFA-0048-probe2 alias-collapse floor-carry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
