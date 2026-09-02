#!/usr/bin/env python3
"""Probe 2: credential-read wildcards are rejected at VALIDATION time.

Both-states:
  BAD  grant credential *        -> validate_permission_set errors (rule present)
  GOOD grant credential env:NAME -> no errors, evaluate GRANTs that name
  GOOD grant tool *              -> no errors (does not grant credential)

A stripped validator that omits the credential-wildcard rule ACCEPTS the bad
set — proving the real rule is what rejects, not a generic shape error.
Schema if/then on the contract artifact must also reject the bad instance.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from model import (  # noqa: E402
    InvalidPermissionSet,
    evaluate_request,
    req,
    validate_permission_set,
)

ART = REPO / "command-center/phase4/contracts/ARC-0081.json"
SENTINEL = "SUCCESS:ARC-0081"
RULE = "wildcard-credential-escalation"

BAD = {
    "subject": "bad",
    "permissions": [{"effect": "grant", "class": "credential", "selector": "*"}],
}
BAD_PREFIX = {
    "subject": "bad-prefix",
    "permissions": [
        {"effect": "grant", "class": "credential", "selector": "env:*_TOKEN"}
    ],
}
GOOD_NAMED = {
    "subject": "good-named",
    "permissions": [
        {"effect": "grant", "class": "credential", "selector": "env:GITHUB_TOKEN"}
    ],
}
GOOD_TOOL_STAR = {
    "subject": "good-tool",
    "permissions": [{"effect": "grant", "class": "tool", "selector": "*"}],
}


def validate_without_credential_rule(pset: dict) -> list[dict]:
    """Mutant: same shape checks, no wildcard-credential-escalation rule."""
    import model as M

    saved = M.validate_permission_set

    def stripped(pset_inner):
        errors = []
        if not isinstance(pset_inner, dict):
            return [{"rule": "shape", "path": "$", "message": "object"}]
        perms = pset_inner.get("permissions")
        if not isinstance(perms, list):
            return [{"rule": "shape", "path": "$.permissions", "message": "array"}]
        for i, stmt in enumerate(perms):
            if not isinstance(stmt, dict):
                errors.append({"rule": "shape", "path": f"$.permissions[{i}]", "message": "object"})
                continue
            if stmt.get("effect") not in M.EFFECTS:
                errors.append({"rule": "vocabulary", "path": f"$.permissions[{i}].effect", "message": "effect"})
            if stmt.get("class") not in M.CLASSES:
                errors.append({"rule": "vocabulary", "path": f"$.permissions[{i}].class", "message": "class"})
            sel = stmt.get("selector")
            if not isinstance(sel, str) or not sel:
                errors.append({"rule": "shape", "path": f"$.permissions[{i}].selector", "message": "selector"})
        return errors

    try:
        return stripped(pset)
    finally:
        assert M.validate_permission_set is saved


def schema_rejects(doc: dict, instance: dict) -> bool:
    try:
        import jsonschema
    except ImportError:
        print("WARN: jsonschema missing; schema half of probe2 skipped")
        return True
    errs = list(jsonschema.Draft202012Validator(doc).iter_errors(instance))
    return bool(errs)


def main() -> int:
    if not ART.is_file():
        print("FAILED:ARC-0081-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:ARC-0081-probe2 sentinel absent")
        return 1
    doc = json.loads(text)

    bad_errs = validate_permission_set(BAD)
    prefix_errs = validate_permission_set(BAD_PREFIX)
    good_errs = validate_permission_set(GOOD_NAMED)
    tool_errs = validate_permission_set(GOOD_TOOL_STAR)
    mutant_errs = validate_without_credential_rule(copy.deepcopy(BAD))

    bad_hit = any(e.get("rule") == RULE for e in bad_errs)
    prefix_hit = any(e.get("rule") == RULE for e in prefix_errs)
    mutant_silent = not any(e.get("rule") == RULE for e in mutant_errs)

    print(f"bad_star rule={bad_hit} errors={len(bad_errs)}")
    print(f"bad_prefix rule={prefix_hit} errors={len(prefix_errs)}")
    print(f"good_named errors={len(good_errs)}")
    print(f"good_tool_star errors={len(tool_errs)}")
    print(f"mutant_without_rule silent_on_star={mutant_silent} errors={len(mutant_errs)}")

    # Evaluation must not GRANT the wildcard set (choke point re-validates).
    eval_raised = False
    try:
        decision = evaluate_request(BAD, req("credential", "env:GITHUB_TOKEN"))
        print(f"FAILED:ARC-0081-probe2 evaluate returned {decision.get('outcome')}")
        return 1
    except InvalidPermissionSet:
        eval_raised = True
    print(f"evaluate_on_bad raised InvalidPermissionSet={eval_raised}")

    named_decision = evaluate_request(GOOD_NAMED, req("credential", "env:GITHUB_TOKEN"))
    other_decision = evaluate_request(GOOD_NAMED, req("credential", "env:AWS_SECRET_ACCESS_KEY"))
    tool_cred = evaluate_request(GOOD_TOOL_STAR, req("credential", "env:GITHUB_TOKEN"))
    print(
        f"named GRANT={named_decision['outcome']} other={other_decision['outcome']} "
        f"tool_star_vs_credential={tool_cred['outcome']}"
    )

    schema_bad = schema_rejects(doc, BAD)
    schema_good = not schema_rejects(doc, GOOD_NAMED)
    schema_tool = not schema_rejects(doc, GOOD_TOOL_STAR)
    print(f"schema rejects_star={schema_bad} accepts_named={schema_good} accepts_tool_star={schema_tool}")

    ok = (
        bad_hit
        and prefix_hit
        and not good_errs
        and not tool_errs
        and mutant_silent
        and eval_raised
        and named_decision["outcome"] == "GRANT"
        and other_decision["outcome"] == "DENY"
        and tool_cred["outcome"] == "DENY"
        and schema_bad
        and schema_good
        and schema_tool
    )
    if not ok:
        print("FAILED:ARC-0081-probe2 wildcard-escalation control did not discriminate")
        return 1
    print("SUCCESS:ARC-0081-probe2 wildcard-escalation validation-time reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
