"""Independent reviewer: re-run both-states and recount; do not trust author prose."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FOUNDRY = REPO / "command-center" / "foundry"
sys.path.insert(0, str(FOUNDRY))
sys.path.insert(0, str(HERE))

import lint_field_contract as lint  # noqa: E402
from recount import assert_catalog  # noqa: E402

GLOSS = HERE / "fixtures" / "gloss_reader.py"
VREAD = HERE / "fixtures" / "v_reader.py"
CONSUMERS = FOUNDRY / "consumers"


def review() -> dict:
    gloss = lint.lint_file(GLOSS)
    vread = lint.lint_file(VREAD)
    foundry = lint.lint_paths(lint.iter_py(CONSUMERS))
    recount = assert_catalog()
    gloss_fails = any(f.field == "state" for f in gloss)
    size_also = any(f.field == "size" for f in gloss)
    v_clean = len(vread) == 0
    foundry_clean = len(foundry) == 0
    ok = (
        gloss_fails
        and size_also
        and v_clean
        and foundry_clean
        and recount["matches_catalog_claim"]
        and recount["signals_agree"]
    )
    return {
        "reviewer_id": "WFA-0157-both-states-recount-rerun",
        "independent": True,
        "executed_both_states": True,
        "verdict": "PASS" if ok else "FAIL",
        "gloss_reader_findings": len(gloss),
        "gloss_reader_fails_on_state": gloss_fails,
        "gloss_reader_fails_on_size": size_also,
        "v_reader_findings": len(vread),
        "foundry_consumer_findings": len(foundry),
        "recount_n": recount["signal_a"]["n"],
        "recount_non_literal": recount["signal_a"]["non_literal"],
        "signals_agree": recount["signals_agree"],
        "scope_not_agreement": True,
    }
