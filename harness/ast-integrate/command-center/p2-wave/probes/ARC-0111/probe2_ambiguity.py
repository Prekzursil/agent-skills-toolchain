#!/usr/bin/env python3
"""Probe 2: every ambiguous id lists both candidate resolutions and stays unresolved.

Never guess. An LLM guess on this mechanical comparison measured 86% accurate
on this estate with every error pointing at data loss.

Controls:
  * M-16 matches option-universe AND research-harness (and historical mechanism)
  * M-12 matches option-universe AND historical mechanism
  * I5 resolves to exactly one namespace (option-universe)
  * MECH-01 resolves to exactly one namespace (mechanism) — prefix is not family M
  * planted M-99 with no discriminating token is AMBIGUOUS, not guessed
  * a mutant that binds M-16 to a single namespace must be rejected
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import coverage as C  # noqa: E402

ART = REPO / "command-center/phase4/conformance/ARC-0111.json"
SENTINEL = "SUCCESS:ARC-0111"


def _fail(msg: str) -> int:
    print(f"FAILED:ARC-0111-probe2 {msg}")
    return 1


def _ns_set(row: dict) -> set[str]:
    return {str(c.get("namespace")) for c in (row.get("candidates") or [])}


def _require_ambiguous(row: dict, needed: set[str], label: str) -> str | None:
    if row.get("status") != "AMBIGUOUS":
        return f"{label} status={row.get('status')} wanted AMBIGUOUS"
    if row.get("namespace") is not None:
        return f"{label} guessed namespace={row.get('namespace')}"
    got = _ns_set(row)
    missing = needed - got
    if missing:
        return f"{label} missing candidates {sorted(missing)} got={sorted(got)}"
    if len(got) < 2:
        return f"{label} fewer than two candidates {sorted(got)}"
    return None


def main() -> int:
    fx = C.run_fixture(HERE)
    namespaces = C.load_namespaces(
        C._read_json(C.fixture_dir(HERE) / "option_universe.json")
    )
    by_id = {r["id"]: r for r in fx["resolutions"]}

    m16 = by_id.get("M-16")
    if not m16:
        return _fail("M-16 missing from fixture resolutions")
    err = _require_ambiguous(
        m16, {"option-universe", "research-harness"}, "M-16"
    )
    print(f"M-16 status={m16['status']} candidates={sorted(_ns_set(m16))}")
    if err:
        return _fail(err)

    m12 = by_id.get("M-12")
    if not m12:
        return _fail("M-12 missing from fixture resolutions")
    err = _require_ambiguous(m12, {"option-universe", "mechanism"}, "M-12")
    print(f"M-12 status={m12['status']} candidates={sorted(_ns_set(m12))}")
    if err:
        return _fail(err)

    i5 = by_id.get("I5")
    if not i5 or i5.get("status") != "RESOLVED" or i5.get("namespace") != "option-universe":
        return _fail(f"I5 unambiguous control failed {i5}")
    print(f"I5 status={i5['status']} namespace={i5['namespace']}")

    mech = by_id.get("MECH-01")
    if not mech or mech.get("status") != "RESOLVED" or mech.get("namespace") != "mechanism":
        return _fail(f"MECH-01 unambiguous control failed {mech}")
    print(f"MECH-01 status={mech['status']} namespace={mech['namespace']}")

    planted = C.resolve_token("M-99", namespaces)
    print(
        f"planted M-99 status={planted['status']} "
        f"candidates={sorted(_ns_set(planted))}"
    )
    err = _require_ambiguous(
        planted, {"option-universe", "mechanism"}, "planted M-99"
    )
    if err:
        return _fail(err)

    m1 = C.resolve_token("M-1", namespaces)
    print(f"M-1 status={m1['status']} namespace={m1.get('namespace')}")
    if m1.get("status") != "RESOLVED" or m1.get("namespace") != "wave1-mission-grade":
        return _fail(f"M-1 should be wave1-mission-grade only {m1}")

    # Ambiguous selected ids must sit in unmapped, not mapped.
    unm = {r["id"] for r in fx["unmapped"]}
    mapped = {r["id"] for r in fx["mapped"]}
    for oid in ("M-16", "M-12"):
        if oid not in unm:
            return _fail(f"{oid} ambiguous but not in unmapped")
        if oid in mapped:
            return _fail(f"{oid} ambiguous but mapped (guessed binding)")

    amb_ids = {r["id"] for r in fx["ambiguous"]}
    if "M-16" not in amb_ids or "M-12" not in amb_ids:
        return _fail(f"ambiguous list incomplete {sorted(amb_ids)}")

    mutant = copy.deepcopy(m16)
    mutant["status"] = "RESOLVED"
    mutant["namespace"] = "option-universe"
    mutant["candidates"] = [
        c
        for c in mutant["candidates"]
        if c.get("namespace") == "option-universe"
    ]
    print(
        f"mutant M-16 status={mutant['status']} "
        f"namespace={mutant['namespace']} n_cand={len(mutant['candidates'])}"
    )
    if _require_ambiguous(mutant, {"option-universe", "research-harness"}, "mutant") is None:
        return _fail("mutant single-namespace M-16 was accepted as AMBIGUOUS")

    if not ART.is_file():
        return _fail("conformance artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return _fail("sentinel absent")
    doc = json.loads(text)
    art_amb = (doc.get("fixture_coverage") or {}).get("ambiguous") or []
    art_ids = {r.get("id") for r in art_amb if isinstance(r, dict)}
    if "M-16" not in art_ids or "M-12" not in art_ids:
        return _fail(f"artifact ambiguous list incomplete {sorted(art_ids)}")
    for row in art_amb:
        if row.get("id") in {"M-16", "M-12"} and row.get("namespace") is not None:
            return _fail(f"artifact guessed namespace for {row.get('id')}")
        if row.get("id") in {"M-16", "M-12"} and len(row.get("candidates") or []) < 2:
            return _fail(f"artifact {row.get('id')} missing both candidates")
    policy = doc.get("namespace_policy") or {}
    if policy.get("guessing") is not False:
        return _fail("namespace_policy.guessing must be false")
    print("SUCCESS:ARC-0111-probe2 ambiguity both-candidates unresolved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
