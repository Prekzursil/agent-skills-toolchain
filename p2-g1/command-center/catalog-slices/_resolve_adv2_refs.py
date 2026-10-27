#!/usr/bin/env python3
"""Retarget detector for ADV-2.json's sibling-slice references.

Motive (CONFIRMED, not hypothetical): while ADV-2 was being authored on 2026-08-09,
RES-2.json was renumbered mid-flight. Four ids that ADV-2 cited silently retargeted
to semantically unrelated units - the Tor/onion legal-gate unit was RES-0154 at one
read and RES-0138 minutes later, and RES-0154 then meant "refuter role design". A
dangling id is loud; a retarget is silent, so existence alone is NOT a check.

This resolver therefore checks TITLE, not existence, using the dependency_anchors
recorded in each unit, and it validates itself against a planted retarget before it
is allowed to report a clean run."""
from __future__ import annotations

import glob
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
ID = re.compile(r"\b((?:ARC|AUD|CC|CNL|CNF|IMP|REL|RES|TST|WFA)-\d{4})\b")


def build_index() -> dict[str, tuple[str, str]]:
    idx: dict[str, tuple[str, str]] = {}
    for f in sorted(glob.glob(str(HERE / "*.json"))):
        p = pathlib.Path(f)
        if p.name == "ADV-2.json":
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if isinstance(d, list):
            for o in d:
                if isinstance(o, dict) and "id" in o:
                    idx[o["id"]] = (p.name, o.get("title", ""))
    return idx


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def check(idx: dict[str, tuple[str, str]], units: list[dict]) -> list[str]:
    bad: list[str] = []
    for x in units:
        for dep, want in x.get("dependency_anchors", {}).items():
            if dep not in idx:
                bad.append(f"{x['id']} -> {dep}: ABSENT (anchor: {want[:60]})")
                continue
            got = idx[dep][1]
            if not norm(got).startswith(norm(want)[:60]):
                bad.append(f"{x['id']} -> {dep}: RETARGET\n"
                           f"      anchor: {want[:88]}\n"
                           f"      ondisk: {got[:88]}  ({idx[dep][0]})")
    return bad


index = build_index()
units = json.load(open(HERE / "ADV-2.json", encoding="utf-8"))

# --- DETECTOR CONTROL (both-states). The checker must FIRE on a known retarget
#     before its silence on the real data means anything.
anchored = {d for x in units for d in x.get("dependency_anchors", {})}
assert anchored, "no dependency_anchors present - nothing to check"
victim = sorted(anchored)[0]
poisoned = dict(index)
poisoned[victim] = (poisoned[victim][0], "A COMPLETELY DIFFERENT UNIT TITLE")
ctrl = check(poisoned, units)
assert any(victim in b and "RETARGET" in b for b in ctrl), \
    f"CONTROL FAILED: checker did not fire on a planted retarget of {victim}"
print(f"# detector control: planted retarget of {victim} -> FIRED ({len(ctrl)} hit(s))")

# --- real run
bad = check(index, units)
blob = (HERE / "ADV-2.json").read_text(encoding="utf-8")
cited = sorted(set(ID.findall(blob)))
missing_prose = [c for c in cited if c not in index]

print(f"# sibling units indexed: {len(index)}")
print(f"# distinct sibling ids cited anywhere in ADV-2: {len(cited)}")
print(f"# machine-read dependency ids carrying a title anchor: {len(anchored)}")
if missing_prose:
    print(f"# ids cited in prose that do not resolve at all: {missing_prose}")

if bad:
    print("\nFAILED:resolve-ADV-2-refs")
    for b in bad:
        print("  -", b)
    raise SystemExit(1)
print(f"SUCCESS:resolve-ADV-2-refs anchored={len(anchored)} retargets=0 "
      f"unresolved-prose={len(missing_prose)}")
