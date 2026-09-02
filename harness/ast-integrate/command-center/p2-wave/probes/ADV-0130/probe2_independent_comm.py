#!/usr/bin/env python3
"""Probe 2: independent POSIX comm subtraction must reproduce the NOVEL set.

Does not import engine.subtract. Reads typed triples from the ledger, rebuilds
the declared set from the same sources, and subtracts with comm(1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import comm_subtract as C  # noqa: E402
import engine as E  # noqa: E402
import schema_local as S  # noqa: E402

OUT = REPO / "command-center/adversarial/ADV-0130-novelty-accounting.json"
UNIT = "ADV-0130"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe2 {msg}")
    return 1


def triples_from(rows: list) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        s = row.get("subject_id")
        r = row.get("relation")
        o = row.get("object_id")
        if s and r and o:
            out.add((str(s), str(r), str(o)))
    return out


def main() -> int:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        return fail("artifact missing")
    try:
        doc = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(f"unparseable:{type(exc).__name__}")

    body = S.payload(doc)
    artifact_novel = triples_from(list(body.get("novel") or []))
    filed_norm: set[tuple[str, str, str]] = set()
    for rec in body.get("filed") or []:
        if not isinstance(rec, dict):
            continue
        if rec.get("classification") == "UNNORMALISABLE":
            continue
        t = rec.get("triple")
        if isinstance(t, dict) and t.get("subject_id") and t.get("relation") and t.get("object_id"):
            filed_norm.add((str(t["subject_id"]), str(t["relation"]), str(t["object_id"])))

    if not filed_norm:
        return fail("no normalisable filed triples")

    declared, _sources = E.collect_declared(REPO)
    if not declared:
        return fail("declared set empty")

    work = HERE / "_comm_work"
    comm_set = C.comm_novel(filed_norm, declared, workdir=work)

    if comm_set != artifact_novel:
        only_comm = sorted(comm_set - artifact_novel)[:8]
        only_art = sorted(artifact_novel - comm_set)[:8]
        return fail(
            f"NOVEL mismatch comm={len(comm_set)} artifact={len(artifact_novel)} "
            f"only_comm={only_comm} only_artifact={only_art}"
        )

    if not body.get("independent_reimplementation", {}).get("identical_novel_set"):
        return fail("artifact identical_novel_set is not true")

    summary = {
        "probe": "probe2-independent-comm",
        "unit_id": UNIT,
        "tool": "/usr/bin/comm",
        "method": "comm -23 LC_ALL=C sorted unique TSV",
        "filed_normalisable": len(filed_norm),
        "declared": len(declared),
        "novel": len(comm_set),
        "identical_novel_set": True,
        "pass": True,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    print("SUCCESS:ADV-0130-probe2 independent comm reproduced NOVEL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
