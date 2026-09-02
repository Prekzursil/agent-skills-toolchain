#!/usr/bin/env python3
"""Probe 1: detector-control then both-states for the gloss-field lint.

A known gloss-reading consumer MUST fail the lint before any clean-consumer
silence is trusted. Switching the same consumer to state_v/size_v MUST pass.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FOUNDRY = REPO / "command-center" / "foundry"
sys.path.insert(0, str(FOUNDRY))
sys.path.insert(0, str(HERE))

import lint_field_contract as lint  # noqa: E402

ART = REPO / "command-center/foundry/WFA-0157-machine-consumer-field-contract-gate-on-state-v-size.json"
GLOSS = HERE / "fixtures" / "gloss_reader.py"
VREAD = HERE / "fixtures" / "v_reader.py"

BAD = '''def admit(blueprint):
    return blueprint["state"] == "FOUND"


def by_size(records, size):
    return [r for r in records if r.get("size") == size]
'''

GOOD = '''def admit(blueprint):
    return blueprint["state_v"] == "FOUND"


def by_size(records, size_v):
    return [r for r in records if r.get("size_v") == size_v]
'''


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0157-probe1 {msg}")
    return 1


def main() -> int:
    gloss = lint.lint_file(GLOSS)
    print("detector_control_first=True")
    print(f"gloss_reader_findings={len(gloss)}")
    for f in gloss:
        print(f"  {f.path}:{f.line} field={f.field} kind={f.kind} {f.snippet}")
    if not gloss:
        return fail("detector-control: known gloss reader was silent")
    if not any(f.field == "state" for f in gloss):
        return fail("detector-control: did not flag state gloss")
    print("detector_control_found_known_gloss_read=True")

    vread = lint.lint_file(VREAD)
    print(f"v_reader_findings={len(vread)}")
    if vread:
        return fail("v_reader (state_v/size_v) was not clean")

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "switch_consumer.py"
        p.write_text(BAD, encoding="utf-8")
        bad_hits = lint.lint_file(p)
        p.write_text(GOOD, encoding="utf-8")
        good_hits = lint.lint_file(p)
    print(f"switch_gloss_findings={len(bad_hits)} switch_v_findings={len(good_hits)}")
    if not bad_hits:
        return fail("switched-same-file gloss state did not fail lint")
    if good_hits:
        return fail("switched-same-file state_v still failed lint")
    print("both_states_same_file=True")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    bs = doc.get("both_states") or {}
    if bs.get("gloss_reader_fails_lint") is not True:
        return fail("artifact did not record gloss-reader fail")
    if bs.get("v_reader_passes_lint") is not True:
        return fail("artifact did not record v-reader pass")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:WFA-0157" not in text:
        return fail("sentinel-absent")
    print("SUCCESS:WFA-0157-probe1 both-states gloss-lint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
