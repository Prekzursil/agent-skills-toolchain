#!/usr/bin/env python3
"""Probe 2: evidence-gated overrule, both-states, negative control, artifact."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from fanin import fan_in  # noqa: E402
from reviewer import counterexample_blind_overrule  # noqa: E402
from scenarios import overrule_blind, overrule_cited, overrule_cross_child, overrule_wrong_digest  # noqa: E402

ART_REL = "command-center/design/council/CNL-0037-nested-subcouncils-and-council-of-councils-fan-in.md"
SCHEMA_REL = "command-center/schema/council-design-note.schema.json"
NOTE_SCHEMA_REL = "command-center/p2-wave/probes/CNL-0037/note.schema.json"
CATALOG_INPUTS = [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]
DEP_PATHS = {
    "CNL-0031": "command-center/design/council/CNL-0031-flat-committee-and-caucus-grouping-when-structure-helps-an.md",
    "CNL-0071": "command-center/design/council/CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md",
}


def resolve_anchor(repo: Path, rel: str, line: int, snippet: str) -> tuple[bool, str]:
    path = repo / rel
    if not path.is_file():
        return False, f"missing:{rel}"
    lines = path.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return False, f"line-oob:{rel}:{line}:n={len(lines)}"
    if snippet not in lines[line - 1]:
        return False, f"snippet-miss:{rel}:{line}"
    return True, f"{rel}:{line}"


def main() -> int:
    cited = fan_in(overrule_cited())
    blind = fan_in(overrule_blind())
    wrong = fan_in(overrule_wrong_digest())
    cross = fan_in(overrule_cross_child())
    print(json.dumps({
        "cited_accepted": cited["overrule"]["accepted"],
        "cited_outcome": cited["outcome"],
        "blind_accepted": blind["overrule"]["accepted"],
        "blind_reason": blind["overrule"]["reason"],
        "wrong_reason": wrong["overrule"]["reason"],
        "cross_reason": cross["overrule"]["reason"],
    }, sort_keys=True))
    if cited["overrule"]["accepted"] is not True or cited["outcome"] != "PASS":
        print("FAILED:CNL-0037-probe2 cited overrule was not accepted")
        return 1
    if "dissent-gamma-1" not in cited["forwarded_dissent_ids"]:
        print("FAILED:CNL-0037-probe2 overrule dropped child dissent")
        return 1
    if blind["overrule"]["accepted"] is True or blind["overrule"]["reason"] != "BLIND_OVERRULE":
        print("FAILED:CNL-0037-probe2 blind overrule was not rejected as BLIND_OVERRULE")
        return 1
    if wrong["overrule"]["reason"] != "DIGEST_MISMATCH":
        print(f"FAILED:CNL-0037-probe2 wrong digest reason={wrong['overrule']['reason']}")
        return 1
    if cross["overrule"]["reason"] != "CITE_NOT_FROM_TARGET_CHILD":
        print(f"FAILED:CNL-0037-probe2 cross-child reason={cross['overrule']['reason']}")
        return 1
    neg = (
        "negative-control target=overrule-blind "
        f"overrule.accepted={blind['overrule']['accepted']} "
        f"overrule.reason={blind['overrule']['reason']} "
        f"outcome={blind['outcome']} "
        f"parent_complete={blind['parent_complete']}"
    )
    print(neg)
    rev = counterexample_blind_overrule()
    print(json.dumps({
        "reviewer_ok": rev["ok"],
        "planted_bad_fires": rev["both_states"]["planted_bad_fires"],
        "known_good_silent_accept": rev["both_states"]["known_good_silent_accept"],
        "refuted_not_attempted": rev["refuted_not_attempted"],
    }, sort_keys=True))
    if not rev["ok"] or rev["refuted_not_attempted"] is True:
        print("FAILED:CNL-0037-probe2 reviewer counterexample did not hold")
        return 1
    art = REPO / ART_REL
    if not art.is_file():
        print("FAILED:CNL-0037-probe2 design note missing")
        return 1
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CNL-0037-probe2 unparseable:{exc}")
        return 1
    if not (REPO / SCHEMA_REL).is_file():
        print("FAILED:CNL-0037-probe2 catalog output_schema missing")
        return 1
    schema = json.loads((REPO / NOTE_SCHEMA_REL).read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0037-probe2 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0037" not in text:
        print("FAILED:CNL-0037-probe2 sentinel-absent")
        return 1
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("independent") is not True or reviewer.get("re_ran_both_states") is not True:
        print("FAILED:CNL-0037-probe2 reviewer flags missing")
        return 1
    deps = doc.get("dependency_status") or {}
    for uid, rel in DEP_PATHS.items():
        live = (REPO / rel).is_file()
        claimed = bool((deps.get(uid) or {}).get("artifact_present"))
        if claimed != live:
            print(f"FAILED:CNL-0037-probe2 dependency honesty {uid} claimed={claimed} live={live}")
            return 1
    inputs = doc.get("catalog_inputs_on_tree") or {}
    for path in CATALOG_INPUTS:
        if inputs.get(path) is True:
            print(f"FAILED:CNL-0037-probe2 overclaim: catalog input marked present {path}")
            return 1
    evidence = doc.get("evidence") or []
    if len(evidence) < 2:
        print("FAILED:CNL-0037-probe2 evidence < 2")
        return 1
    kinds = {str(row.get("kind") or "") for row in evidence}
    if len(kinds) < 2:
        print(f"FAILED:CNL-0037-probe2 evidence kinds not independent: {kinds}")
        return 1
    for i, row in enumerate(evidence):
        rel = str(row.get("path") or "")
        line = int(row.get("line") or 0)
        snippet = str(row.get("snippet") or "")
        if not rel or not line or not snippet:
            print(f"FAILED:CNL-0037-probe2 evidence[{i}] missing path/line/snippet")
            return 1
        ok, why = resolve_anchor(REPO, rel, line, snippet)
        print(f"anchor[{i}] ok={ok} {why}")
        if not ok:
            print("FAILED:CNL-0037-probe2 unresolved anchor")
            return 1
    mutant = copy.deepcopy(doc)
    mutant.pop("negative_controls", None)
    try:
        jsonschema.Draft7Validator(schema).validate(mutant)
        print("FAILED:CNL-0037-probe2 schema accepted missing negative_controls")
        return 1
    except jsonschema.ValidationError:
        print("schema_mutant_rejected=True")
    print("SUCCESS:CNL-0037-probe2 evidence-gated-overrule both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
