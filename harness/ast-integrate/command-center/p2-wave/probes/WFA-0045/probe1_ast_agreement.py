#!/usr/bin/env python3
"""Probe 1: independent AST walk vs adapter semantic counts on all 10 files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from adapter import adapt_file  # noqa: E402
from corpus import load_corpus  # noqa: E402
from syntax_count import count_file  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0045-adapter-saved-workflow.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0045-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    text = json.dumps(doc)
    if "SUCCESS:WFA-0045" not in text:
        print("FAILED:WFA-0045-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0045-probe1 self-declared", doc.get("state"))
        return 1

    files, origin = load_corpus()
    if len(files) != 10:
        print("FAILED:WFA-0045-probe1 corpus size", len(files))
        return 1
    names = {p.name for p in files}
    if not {"plan-gate.mjs", "design-gate.mjs"} <= names:
        print("FAILED:WFA-0045-probe1 missing gate files", sorted(names))
        return 1

    per = []
    for path in files:
        syntax = count_file(path)
        adapted = adapt_file(path)
        semantic = adapted.get("counts") or {}
        agree = syntax == semantic and bool(adapted.get("ok"))
        per.append(
            {
                "file": path.name,
                "syntax": syntax,
                "semantic": semantic,
                "agree": agree,
                "ok": bool(adapted.get("ok")),
            }
        )
        if not agree:
            print("FAILED:WFA-0045-probe1 count mismatch", path.name, syntax, semantic)
            return 1

    recorded = {row["file"]: row for row in (doc.get("files") or []) if isinstance(row, dict)}
    for item in per:
        rec = recorded.get(item["file"]) or {}
        if rec.get("syntax_counts") != item["syntax"]:
            print("FAILED:WFA-0045-probe1 artifact syntax drift", item["file"])
            return 1
        if rec.get("semantic_counts") != item["semantic"]:
            print("FAILED:WFA-0045-probe1 artifact semantic drift", item["file"])
            return 1

    if not (doc.get("count_agreement") or {}).get("all_files_agree"):
        print("FAILED:WFA-0045-probe1 artifact count_agreement false")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-ast-agreement",
        "unit_id": "WFA-0045",
        "corpus_origin": origin,
        "files": len(files),
        "per_file": per,
        "computed_not_asserted": True,
        "method_b": "syntax_count.walk CallExpression",
        "method_a": "adapter semantic extraction",
    }
    print(json.dumps(payload, sort_keys=True))
    print(f"agree=10/10 origin={origin}")
    print("SUCCESS:WFA-0045-probe1 ast-agreement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
