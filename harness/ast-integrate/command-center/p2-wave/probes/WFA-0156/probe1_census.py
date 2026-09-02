#!/usr/bin/env python3
"""Probe 1: recompile all 108 blueprints; counts and quotes must match the artifact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import corpus as C  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0156-typed-stopping-rule-algebra-with-executable-evaluati.json"
)


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0156-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:WFA-0156-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:WFA-0156" not in text:
        print("FAILED:WFA-0156-probe1 sentinel absent")
        return 1
    if doc.get("kind") != "stop-rule-algebra" or doc.get("unit_id") != "WFA-0156":
        print("FAILED:WFA-0156-probe1 kind/unit_id")
        return 1

    loaded = C.load_corpus(REPO)
    rows = loaded["blueprints"]
    live = C.census(rows)
    recorded = doc.get("counts") or {}
    print(
        f"live EVALUABLE={live['EVALUABLE']} PROSE-ONLY={live['PROSE-ONLY']} "
        f"ABSENT={live['ABSENT']} COMPILE-REJECT={live['COMPILE-REJECT']} "
        f"n={live['blueprints']}"
    )
    if live["blueprints"] != 108:
        print(f"FAILED:WFA-0156-probe1 count={live['blueprints']}")
        return 1
    for key in ("EVALUABLE", "PROSE-ONLY", "ABSENT", "COMPILE-REJECT", "blueprints"):
        if int(recorded.get(key, -1)) != live[key]:
            print(f"FAILED:WFA-0156-probe1 counts drift {key} art={recorded.get(key)} live={live[key]}")
            return 1

    art_rows = {r["id"]: r for r in (doc.get("blueprints") or []) if isinstance(r, dict)}
    if len(art_rows) != 108:
        print(f"FAILED:WFA-0156-probe1 artifact rows={len(art_rows)}")
        return 1
    for row in rows:
        rec = art_rows.get(row["id"])
        if rec is None:
            print(f"FAILED:WFA-0156-probe1 missing {row['id']}")
            return 1
        if rec.get("compile_result") != row["compile_result"]:
            print(f"FAILED:WFA-0156-probe1 result drift {row['id']}")
            return 1
        if rec.get("raw_stop_text") != row["raw_stop_text"]:
            print(f"FAILED:WFA-0156-probe1 raw drift {row['id']}")
            return 1
        if row["compile_result"] in {"PROSE-ONLY", "COMPILE-REJECT"}:
            quoted = rec.get("quoted_raw_stop_text")
            if not quoted:
                print(f"FAILED:WFA-0156-probe1 missing quote {row['id']}")
                return 1
            if quoted != row["raw_stop_text"]:
                print(f"FAILED:WFA-0156-probe1 quote mismatch {row['id']}")
                return 1
        print(
            f"bp={row['id']} result={row['compile_result']} "
            f"degen={row['degenerate_immediate_stop']} "
            f"reject={row['reject_reason']}"
        )

    if bool(doc.get("library", {}).get("present")) != bool(loaded["library_present"]):
        print("FAILED:WFA-0156-probe1 library.present drift")
        return 1
    if doc.get("library", {}).get("original_library_stop_texts_forged") is not False:
        print("FAILED:WFA-0156-probe1 forged-flag")
        return 1

    out = {
        "probe": "probe1-census",
        "unit_id": "WFA-0156",
        "counts": live,
        "library_present": loaded["library_present"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:WFA-0156-probe1 census "
        f"EVALUABLE={live['EVALUABLE']} PROSE-ONLY={live['PROSE-ONLY']} "
        f"ABSENT={live['ABSENT']} COMPILE-REJECT={live['COMPILE-REJECT']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
