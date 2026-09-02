#!/usr/bin/env python3
"""Probe 1: detector control — extractor reproduces the known 31-way M-NN set.

Does not import probe 2. Re-runs the extractor on disk fixtures. Fails if the
known option∩mech set is hardcoded rather than extracted (option-only corpus
must not report the 31-way intersection).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import collision as C  # noqa: E402
import scenario as S  # noqa: E402

ART = REPO / "command-center/receipts/TST-0095.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0095/probe1_extractor_control.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0095-probe1 {msg}")
    return 1


def main() -> int:
    S.ensure_fixtures()
    live = S.test_extractor_reproduces_the_known_collision_set()
    if not live["ok"]:
        print(json.dumps(live, sort_keys=True, default=str)[:4000])
        return fail("extractor did not reproduce the known 31-way collision set")
    if live["count"] != 31 or live["got"] != S.KNOWN_COLLISION_SET:
        return fail(f"collision set count={live['count']} got={live['got'][:8]}")
    if live["single_namespace_false_positive"]:
        return fail("option-only corpus invented a cross-namespace intersection")
    if live["empty_corpus_false_positive"]:
        return fail("empty corpus invented collisions")
    if live.get("cc0023_agrees") is False:
        return fail("CC-0023 collision_numbers disagree with reconstructed 31-way")

    rows = S.extract_dir(S.KNOWN_DIR)
    mapping = C.id_map(rows)
    m16 = {d["namespace"] for d in mapping.get("M-16", [])}
    if not {S.OPTION_NS, S.MECH_NS, S.WAVE3_NS}.issubset(m16):
        return fail(f"M-16 namespaces {sorted(m16)} missing third/fourth holders")

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if "SUCCESS:TST-0095" not in json.dumps(doc):
            return fail("artifact sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail(f"self-declared:{st}")
        claimed = list(doc.get("known_collision_set") or [])
        if claimed != S.KNOWN_COLLISION_SET:
            return fail("artifact known_collision_set != live extractor")
        if doc.get("extractor_proven_on_known_case") is not True:
            return fail("artifact extractor_proven_on_known_case is not true")
        src = doc.get("source_probe") or {}
        ver = doc.get("verifier_probe") or {}
        if src and ver:
            if json.dumps(src, sort_keys=True) == json.dumps(ver, sort_keys=True):
                return fail("source_probe identical to verifier_probe")
            if src.get("command") == P1 and src.get("command") == ver.get("command"):
                return fail("source and verifier share probe1 command")

    out = {
        "probe": "probe1-extractor-control",
        "unit_id": "TST-0095",
        "known_collision_count": 31,
        "known_collision_set": live["got"],
        "third_fourth_namespaces": live["third_fourth_namespaces"],
        "cc0023_agrees": live["cc0023_agrees"],
        "single_namespace_false_positive": [],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"extractor known-31way count={live['count']} "
        f"M-1 namespaces={live['third_fourth_namespaces'].get('M-1')} "
        f"M-16 namespaces={live['third_fourth_namespaces'].get('M-16')}"
    )
    print("SUCCESS:TST-0095-probe1 extractor reproduces the known collision set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
