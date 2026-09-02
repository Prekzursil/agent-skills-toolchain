#!/usr/bin/env python3
"""Probe 2: structural census (WFA-0141-style) is blind to a semantic mutant.

Independent of probe 1's both-states table: re-translate, mutate the same
gate, show plane/stage/gate counts still match, and show the execution
oracle still fails. Also resolve artifact evidence anchors and refuse
garbage under the translation-oracle schema.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import both_states as B  # noqa: E402
import schema_check as SC  # noqa: E402
from oracle import judge, mutate_one_gate  # noqa: E402
from structural import structural_census  # noqa: E402
from translate import translate  # noqa: E402

ART = REPO / (
    "command-center/foundry/"
    "WFA-0155-translation-fidelity-oracle-for-the-translate-route.json"
)


def main() -> int:
    foreign = B.load_source()
    native = translate(foreign)
    mutant = mutate_one_gate(native, stage="review", field="score", new_op="lt")
    struct = structural_census(foreign, mutant)
    print(json.dumps({"structural_mutant": struct}, sort_keys=True))
    if not struct.get("would_pass_wfa0141_style"):
        print("FAILED:WFA-0155-probe2 mutant should still look structurally faithful")
        return 1
    if struct.get("control_plane_count") != 1:
        print("FAILED:WFA-0155-probe2 mutant introduced a second plane")
        return 1
    pass_case = B.load_cases()[0]
    row = judge(foreign, mutant, pass_case)
    print(
        f"oracle_mutant_pass={row['pass']} mismatches={row['mismatches']}"
    )
    if row["pass"]:
        print("FAILED:WFA-0155-probe2 oracle accepted semantically inverted gate")
        return 1
    if not ART.is_file():
        print("FAILED:WFA-0155-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    dist = B.doc_distinction(doc)
    if dist.get("structural_census_passes_mutant") is not True:
        print("FAILED:WFA-0155-probe2 artifact missed structural pass on mutant")
        return 1
    if dist.get("oracle_fails_mutant") is not True:
        print("FAILED:WFA-0155-probe2 artifact missed oracle fail on mutant")
        return 1
    if B.doc_kind(doc) != "translation-oracle":
        print("FAILED:WFA-0155-probe2 kind")
        return 1
    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        print("FAILED:WFA-0155-probe2 evidence < 2")
        return 1
    kinds = {e.get("kind") for e in evidence}
    methods = {
        p.get("method")
        for e in evidence
        for p in (e.get("probes") or [])
        if isinstance(p, dict)
    }
    independent = ("file-line" in kinds and "rerunnable-command" in kinds) or (
        "file-read" in methods and ("test-run" in methods or "command" in methods)
    )
    if not independent:
        print("FAILED:WFA-0155-probe2 evidence kinds not independent")
        return 1
    file_line_hits = 0
    for i, row_e in enumerate(evidence):
        anchor = str(row_e.get("anchor") or "")
        snippet = str(row_e.get("snippet") or "")
        if not snippet:
            for p in row_e.get("probes") or []:
                if isinstance(p, dict) and p.get("method") == "file-read":
                    snippet = str(p.get("raw_output") or "")
                    break
        if row_e.get("kind") == "rerunnable-command" or " " in anchor:
            print(f"anchor[{i}] command {anchor}")
            continue
        rel, _, rest = anchor.partition(":")
        try:
            line = int(rest.split(":", 1)[0])
        except ValueError:
            print(f"anchor[{i}] command {anchor}")
            continue
        ok, why = A.resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print(f"FAILED:WFA-0155-probe2 {why}")
            return 1
        file_line_hits += 1
    if file_line_hits < 1:
        print("FAILED:WFA-0155-probe2 no file-line evidence resolved")
        return 1
    schema_errs = SC.errors(doc)
    if schema_errs:
        print("FAILED:WFA-0155-probe2 artifact fails schema")
        for e in schema_errs[:8]:
            print(" ", e)
        return 1
    if not SC.rejects_garbage():
        print("FAILED:WFA-0155-probe2 schema accepted garbage")
        return 1
    print("schema_rejects_garbage=True")
    print("SUCCESS:WFA-0155-probe2 structural-blind oracle-catches-mutant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
