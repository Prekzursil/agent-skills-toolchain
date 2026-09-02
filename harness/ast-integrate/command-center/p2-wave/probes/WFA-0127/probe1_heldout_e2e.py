#!/usr/bin/env python3
"""Probe 1: end-to-end scout + held-out known-answer (evidence A and B)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from constants import ARTIFACT_REL, REPO, SENTINEL, STAGE_IDS  # noqa: E402
from ir import build_ir  # noqa: E402
import scout  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0127-probe1 {msg}")
    return 1


def every_node_anchored(obj) -> bool:
    if isinstance(obj, dict):
        if obj.get("kind") in {"stage", "role", "gate", "policy", "retry", "resume"}:
            if not obj.get("source_anchor"):
                return False
        return all(every_node_anchored(v) for v in obj.values())
    if isinstance(obj, list):
        return all(every_node_anchored(v) for v in obj)
    return True


def main() -> int:
    artifact = REPO / ARTIFACT_REL
    if not artifact.is_file() or artifact.stat().st_size <= 0:
        return fail("artifact-missing")
    raw = artifact.read_text(encoding="utf-8")
    if SENTINEL not in raw:
        return fail("sentinel-absent")
    doc = json.loads(raw)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{doc.get('state')}")
    if doc.get("ir_kind") != "WorkflowIR":
        return fail("not-workflow-ir")
    if doc.get("not_a_runtime") is not True:
        return fail("ir-claims-runtime")
    if "execution_entrypoint" in doc:
        return fail("ir-has-entrypoint")
    ir_stages = list(doc.get("stage_ids") or [])
    if ir_stages != list(STAGE_IDS):
        return fail(f"stage-id-drift {ir_stages}")
    live_ir = build_ir()
    if live_ir.get("stage_ids") != ir_stages:
        return fail("artifact-ir-drift")
    if not every_node_anchored(doc):
        return fail("node-missing-source-anchor")

    e2e = scout.run(scout.load_goal("e2e"))
    if e2e.get("stages_executed") != list(STAGE_IDS):
        return fail(f"stages {e2e.get('stages_executed')}")
    ranked = e2e.get("ranked") or []
    if not ranked:
        return fail("e2e-empty-ranked")
    for hit in ranked:
        if hit.get("disposition") == "COMPOSE":
            anchors = hit.get("provenance_anchor") or []
            if not anchors or not hit.get("licence_class"):
                return fail(f"compose-missing-evidence {hit.get('id')}")
            continue
        if not hit.get("provenance_anchor"):
            return fail(f"missing-provenance {hit.get('id')}")
        if not hit.get("licence_class"):
            return fail(f"missing-licence {hit.get('id')}")
    print(
        f"e2e ranked={e2e.get('ranked_ids')} "
        f"unknown={[u.get('id') for u in e2e.get('unknown_needs_probe') or []]}"
    )

    held = scout.load_goal("heldout")
    known = str(held.get("known_answer_id") or "")
    if known and known in str(held.get("text") or ""):
        return fail("known-answer-leaked-into-goal-text")
    result = scout.run(held)
    ids = [str(x) for x in (result.get("ranked_ids") or [])]
    if known not in ids[:3]:
        return fail(f"held-out-miss known={known} ranked={ids}")
    top = next(r for r in result["ranked"] if r.get("id") == known)
    if top.get("disposition") != "ADOPT":
        return fail(f"held-out-not-adopt {top}")
    if top.get("licence_class") != "MIT":
        return fail(f"held-out-licence {top.get('licence_class')}")
    if "kanban-drain.md" not in str(top.get("provenance_anchor") or ""):
        return fail(f"held-out-anchor {top.get('provenance_anchor')}")

    unknown_ids = {str(u.get("id")) for u in result.get("unknown_needs_probe") or []}
    if "wf-ghost-unverified" not in unknown_ids:
        return fail(f"ghost-ranked-or-dropped unknown={unknown_ids} ranked={ids}")
    ghost = next(u for u in result["unknown_needs_probe"] if u.get("id") == "wf-ghost-unverified")
    if not ghost.get("exists_only_would_pass"):
        return fail("ghost-exists-only-control-dead")
    if ghost.get("content_ok"):
        return fail("ghost-content-false-green")
    if "wf-copyleft-drain" in ids:
        return fail("copyleft-passed-permissive-filter")
    if "wf-unknown-licence-drain" in ids:
        return fail("unknown-licence-ranked")
    papers = [
        s
        for s in result.get("searched_source_classes") or []
        if s.get("source_class") == "papers"
    ]
    if not papers or papers[0].get("present") is not True:
        return fail("papers-class-not-searched")
    if papers[0].get("n_candidates") != 0:
        return fail(f"papers-should-be-recorded-empty n={papers[0].get('n_candidates')}")
    wfa = [
        s
        for s in result.get("searched_source_classes") or []
        if s.get("source_class") == "wfa-0019-fixture"
    ]
    if not wfa or not wfa[0].get("present"):
        return fail("wfa-0019-surface-absent")

    print(
        f"heldout known={known} rank_index={ids.index(known)} "
        f"licence={top.get('licence_class')} src={top.get('provenance_anchor')}"
    )
    print("SUCCESS:WFA-0127-probe1 e2e ranked with provenance+licence; held-out known-answer in top")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
