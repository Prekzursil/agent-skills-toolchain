#!/usr/bin/env python3
"""Batch envelope-lifts + a few shard-12 artifact repairs. Not a measurement."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
import importlib.util

spec = importlib.util.spec_from_file_location("s12_sha", HERE / "_s12_sha.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
REPO = mod.REPO


def load(rel: str) -> dict:
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


def save(rel: str, doc: dict) -> None:
    (REPO / rel).write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def lift(doc: dict, keys: tuple[str, ...]) -> list[str]:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    done = []
    for k in keys:
        if k in report:
            top = doc.get(k)
            if top in (None, [], {}, "") or k not in doc:
                doc[k] = report[k]
                done.append(k)
    return done


def main() -> int:
    edits = []

    # CNF-0068: vote-count flag + edges live under report
    rel = "command-center/confirmation/CNF-0068-contradiction-adjudication.json"
    doc = load(rel)
    done = lift(
        doc,
        (
            "never_adjudicated_by_agent_count",
            "edges",
            "kind",
            "summary",
        ),
    )
    save(rel, doc)
    mod.refresh_manifest("CNF-0068", [rel])
    edits.append(("CNF-0068", rel, done))

    # CNF-0117: denials live under report
    rel = "command-center/confirmation/CNF-0117-loud-degradation.json"
    doc = load(rel)
    done = lift(
        doc,
        (
            "denials",
            "control",
            "credential_safety",
            "all_denials_loud_or_degraded",
            "inventory",
        ),
    )
    save(rel, doc)
    mod.refresh_manifest("CNF-0117", [rel])
    edits.append(("CNF-0117", rel, done))

    print(json.dumps(edits, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
