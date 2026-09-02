#!/usr/bin/env python3
"""Probe 1: ranking-factor list is split documented-versus-inferred; proportion matches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C  # noqa: E402

ALLOWED = {"documented", "inferred"}


def main() -> int:
    art_path = C.REPO / C.OUT_REL
    if not art_path.is_file():
        print("FAILED:RES-0060-probe1 artifact missing")
        return 1
    text = art_path.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:RES-0060-probe1 self-declared {doc.get('state')}")
        return 1
    if C.SENTINEL not in text:
        print("FAILED:RES-0060-probe1 sentinel absent")
        return 1
    if not doc.get("ranking_factor_list_split_documented_versus_inferred"):
        print("FAILED:RES-0060-probe1 split flag false")
        return 1
    factors = doc.get("ranking_factors") or []
    if len(factors) < 8:
        print(f"FAILED:RES-0060-probe1 too few factors n={len(factors)}")
        return 1
    documented: list[str] = []
    inferred: list[str] = []
    seen: set[str] = set()
    for row in factors:
        if not isinstance(row, dict):
            print("FAILED:RES-0060-probe1 factor not object")
            return 1
        fid = str(row.get("id") or "")
        klass = str(row.get("evidence_class") or "")
        if not fid or fid in seen:
            print(f"FAILED:RES-0060-probe1 bad/duplicate id {fid!r}")
            return 1
        seen.add(fid)
        if klass not in ALLOWED:
            print(f"FAILED:RES-0060-probe1 unlabeled {fid} class={klass!r}")
            return 1
        if not row.get("factor") or not row.get("marketplace"):
            print(f"FAILED:RES-0060-probe1 incomplete row {fid}")
            return 1
        (documented if klass == "documented" else inferred).append(fid)
    if not documented or not inferred:
        print("FAILED:RES-0060-probe1 split is not both-sided")
        return 1
    total = len(documented) + len(inferred)
    proportion = len(inferred) / total
    prop = doc.get("undocumented_proportion") or {}
    if prop.get("documented_count") != len(documented):
        print("FAILED:RES-0060-probe1 documented_count mismatch")
        return 1
    if prop.get("inferred_count") != len(inferred):
        print("FAILED:RES-0060-probe1 inferred_count mismatch")
        return 1
    if prop.get("total") != total:
        print("FAILED:RES-0060-probe1 total mismatch")
        return 1
    got = float(prop.get("proportion"))
    if abs(got - proportion) > 1e-9:
        print(f"FAILED:RES-0060-probe1 proportion {got} != {proportion}")
        return 1
    statement = str(prop.get("statement") or "")
    if str(len(inferred)) not in statement or str(total) not in statement:
        print("FAILED:RES-0060-probe1 proportion not stated in prose")
        return 1
    answers = doc.get("answers") or {}
    listed_doc = (answers.get("signals_that_drive_discovery") or {}).get("documented") or []
    listed_inf = (answers.get("signals_that_drive_discovery") or {}).get("inferred") or []
    if set(listed_doc) != set(documented) or set(listed_inf) != set(inferred):
        print("FAILED:RES-0060-probe1 answers split != ranking_factors")
        return 1
    print(
        f"split documented={len(documented)} inferred={len(inferred)} "
        f"total={total} undocumented_proportion={proportion:.4f}"
    )
    print("SUCCESS:RES-0060-probe1 documented-versus-inferred split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
