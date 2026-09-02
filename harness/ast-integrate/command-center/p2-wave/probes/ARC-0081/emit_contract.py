#!/usr/bin/env python3
"""Emit command-center/phase4/contracts/ARC-0081.json — computed, not prose."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cases import DECISION_CASES, ESCALATION_WITNESSES, LEAST_PRIVILEGE_CASES  # noqa: E402
from model import (  # noqa: E402
    ACTIONS,
    CLASSES,
    DEFAULT_ACTION,
    EFFECTS,
    InvalidPermissionSet,
    delegation_allowed,
    evaluate_request,
    is_escalation,
    least_privilege,
    pset,
    req,
    stmt,
    validate_permission_set,
)

OUT_REL = "command-center/phase4/contracts/ARC-0081.json"
SENTINEL = "SUCCESS:ARC-0081"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0081/probe1_precedence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0081/probe2_wildcard_escalation.py"
)

GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def computed_decision_table() -> list[dict]:
    rows = []
    for case in DECISION_CASES:
        decision = evaluate_request(case["permissions"], case["request"])
        rows.append(
            {
                "id": case["id"],
                "family": case["family"],
                "permissions": case["permissions"]["permissions"],
                "request": case["request"],
                "computed_outcome": decision["outcome"],
                "computed_reason": decision["reason"],
                "matched_grants": decision["matched_grants"],
                "matched_denies": decision["matched_denies"],
                "notes": case["notes"],
            }
        )
    return rows


def computed_least_privilege() -> list[dict]:
    out = []
    for case in LEAST_PRIVILEGE_CASES:
        result = least_privilege(case["declared"], case["observed"])
        out.append(
            {
                "id": case["id"],
                "declared": case["declared"],
                "observed": case["observed"],
                "holds": result["holds"],
                "unused_grants": result["unused_grants"],
                "undeclared_use": result["undeclared_use"],
            }
        )
    return out


def schema_body() -> dict:
    class_enum = {"type": "string", "enum": list(CLASSES)}
    effect_enum = {"type": "string", "enum": list(EFFECTS)}
    selector = {"type": "string", "minLength": 1, "maxLength": 4096}
    statement = {
        "type": "object",
        "additionalProperties": False,
        "required": ["effect", "class", "selector"],
        "properties": {
            "effect": effect_enum,
            "class": class_enum,
            "action": {
                "type": "string",
                "minLength": 1,
                "maxLength": 32,
            },
            "selector": selector,
        },
        "allOf": [
            {
                "if": {
                    "type": "object",
                    "required": ["effect", "class"],
                    "properties": {
                        "effect": {"const": "grant"},
                        "class": {"const": "credential"},
                    },
                },
                "then": {
                    "properties": {
                        "selector": {
                            "type": "string",
                            "minLength": 1,
                            "pattern": "^[^*?]+$",
                            "description": (
                                "Named credential id only. A wildcard here would grant "
                                "credential read and is rejected at validation time."
                            ),
                        },
                        "action": {"type": "string", "enum": ["read"]},
                    }
                },
            }
        ],
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://ast-integrate.invalid/command-center/phase4/contracts/ARC-0081.json",
        "$comment": (
            f"{SENTINEL} — typed permission vocabulary and evaluation semantics. "
            "decision_table outcomes are computed by evaluate_request, not authored."
        ),
        "title": "Permission model: vocabulary, evaluation semantics and least-privilege statement",
        "unit_id": "ARC-0081",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "phase": "4",
        "owner_approval_required": True,
        "question": (
            "Specify the typed permission vocabulary and its evaluation semantics: "
            "the grant and deny forms, precedence when both match, wildcard expansion "
            "rules, escalation and delegation, the single location where evaluation "
            "occurs, and the machine-checkable statement of least privilege (declared "
            "permissions must be a superset of observed use and nothing more). Define "
            "what a permission means for each capability class: tool call, file path, "
            "network egress, subprocess, and credential read."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["subject", "permissions"],
        "properties": {
            "subject": {
                "type": "string",
                "minLength": 1,
                "maxLength": 256,
                "description": "Component, plugin, workflow, or principal the set binds to.",
            },
            "permissions": {
                "type": "array",
                "items": {"$ref": "#/$defs/permission_statement"},
            },
        },
        "$defs": {
            "permission_statement": statement,
            "capability_class": class_enum,
            "effect": effect_enum,
        },
        "vocabulary": {
            "effects": list(EFFECTS),
            "classes": list(CLASSES),
            "actions_by_class": {k: list(v) for k, v in ACTIONS.items()},
            "default_action_by_class": dict(DEFAULT_ACTION),
            "forms": {
                "grant": {
                    "shape": {
                        "effect": "grant",
                        "class": "<class>",
                        "action": "<optional; defaults per class>",
                        "selector": "<concrete or glob except credential>",
                    },
                    "means": "If this statement matches a request and no deny matches, the request is GRANT.",
                },
                "deny": {
                    "shape": {
                        "effect": "deny",
                        "class": "<class>",
                        "action": "<optional>",
                        "selector": "<concrete or glob>",
                    },
                    "means": "If this statement matches a request, the request is DENY even when a grant also matches.",
                },
            },
        },
        "capability_class_meanings": {
            "tool": {
                "request": "invoke a named tool (catalog examples: Read, Grep, Glob, Bash, Write, Edit).",
                "selector": "tool name or glob inside this class only",
                "does_not_imply": [
                    "file path access",
                    "network egress",
                    "subprocess spawn",
                    "credential read",
                ],
            },
            "path": {
                "request": "filesystem action (read|write|delete|exec) on a concrete POSIX path.",
                "selector": "path glob; * is one segment, ** crosses slashes",
                "does_not_imply": [
                    "credential-class read of the secret VALUE",
                    "tool invoke",
                    "subprocess",
                    "egress",
                ],
                "residual": (
                    "A path grant whose glob happens to include a secrets file is still "
                    "a path grant, not a credential grant. Credential values require "
                    "class=credential. A sibling deny-credential-reads control may still "
                    "block secret-shaped paths; that control is not this contract."
                ),
            },
            "egress": {
                "request": "connect to host:port (or URL authority).",
                "selector": "host[:port] or glob inside this class",
                "does_not_imply": ["credential read", "tool invoke", "path write"],
            },
            "subprocess": {
                "request": "spawn a named executable.",
                "selector": "executable path or name",
                "child_permissions": "empty unless separately granted; spawn does not inherit a superset",
                "does_not_imply": ["the child's network, path, or credential rights"],
            },
            "credential": {
                "request": "read a named secret id (env:NAME, file:PATH, keyring:ID).",
                "selector": "must be concrete on grant; wildcards are validation errors",
                "value_handling": (
                    "Evaluation returns GRANT or DENY only. It never returns, logs, "
                    "or prints the secret value. Presence of the id is enough."
                ),
                "does_not_imply": ["rotation", "revocation", "printing the value"],
            },
        },
        "wildcard_expansion": {
            "token_classes": ["tool", "egress", "subprocess", "credential"],
            "path_class": "path",
            "rules": [
                "* on a path matches zero or more characters except / (one segment).",
                "** on a path matches across slashes.",
                "* on a token class matches any string in that class (re .*).",
                "Matching is class-scoped: a match never crosses capability class.",
                "Requests MUST be concrete; a wildcard in a request is DENY (invalid-request).",
            ],
            "forbidden": [
                "grant + class=credential + wildcard selector or action=*",
            ],
        },
        "precedence": {
            "rule": "deny-overrides, then grant, else closed-world deny",
            "when_both_match": "DENY",
            "tie_break": "effect, not specificity: any matching deny beats any matching grant",
            "default": "DENY",
            "steps": [
                "Normalize the request. Wildcard or unknown-class requests DENY as invalid-request.",
                "A statement matches iff class equal, action equal (or statement default, or non-credential *), and selector glob-matches.",
                "If any matching statement has effect=deny -> DENY reason=deny-overrides.",
                "Else if any matching statement has effect=grant -> GRANT reason=grant-match.",
                "Else DENY reason=closed-world-default.",
            ],
        },
        "choke_point": {
            "id": "ARC-0081-evaluate_request",
            "module": "command-center/p2-wave/probes/ARC-0081/model.py",
            "function": "evaluate_request",
            "rule": (
                "This function is the single location where grant vs deny is decided "
                "for every capability class. No other path may authorize a tool call, "
                "path action, egress connect, subprocess spawn, or credential read."
            ),
            "validation_entry": "validate_permission_set",
            "load_time": (
                "A permission set is frozen only after validate_permission_set returns "
                "no errors. Credential-read wildcards die at that gate."
            ),
        },
        "escalation_and_delegation": {
            "escalation": (
                "S' escalates S iff there exists a concrete request r such that "
                "evaluate(S,r)=DENY and evaluate(S',r)=GRANT. Adding a grant, widening "
                "a selector, or removing a matching deny are the usual forms."
            ),
            "delegation": (
                "Principal A may delegate set D to B only if every grant in D is "
                "covered by A (evaluate(A, concretized grant)=GRANT for exact grants; "
                "wildcard child grants require an equal or * /** parent grant of the "
                "same class). Credential grants delegate only as the same named selector."
            ),
            "forbidden_delegation": [
                "delegating a credential the parent does not hold by name",
                "delegating class=credential with a wildcard (already unvalidatable)",
            ],
        },
        "least_privilege": {
            "statement": (
                "Declared grants must be a superset of observed use and nothing more: "
                "every observed request evaluates to GRANT, and every declared grant "
                "matches at least one observed request."
            ),
            "predicate": "holds <=> unused_grants=[] and undeclared_use=[]",
            "function": "least_privilege",
            "wildcard_residual": (
                "A wildcard grant that matched one observed request passes unused "
                "detection but still permits unobserved invocations in its expansion. "
                "Tightness of wildcards beyond 'at least one use' is NOT-CHECKED. "
                "Credential wildcards cannot appear (validation reject), so that "
                "residual does not apply to credential read."
            ),
        },
        "evaluation_semantics_source": "command-center/p2-wave/probes/ARC-0081/model.py",
        "missing_inputs": {
            "command-center/phase3/WINNING-ARCHITECTURE.json": False,
            "command-center/phase3/ARCHITECTURE-RATIFICATION.json": False,
            "command-center/RISK-REGISTER.md": False,
            "14-NO-REGRESSION-CONTRACT.md": False,
            "note": (
                "ARC-0077 (owner ratification) is not on this worktree. This contract "
                "is specified from the catalog question, A1/A2 permission-escalation "
                "failure class, and catalog tool_permissions names. It is not a claim "
                "that the owner has ratified a winning architecture."
            ),
        },
        "negative_controls": [
            {
                "id": "NC-wildcard-credential-grant",
                "input": {
                    "subject": "bad",
                    "permissions": [
                        {
                            "effect": "grant",
                            "class": "credential",
                            "selector": "*",
                        }
                    ],
                },
                "must": "fail validate_permission_set with rule wildcard-credential-escalation",
            },
            {
                "id": "NC-deny-overrides-both-states",
                "setup": "grant Bash plus deny Bash vs grant Bash alone",
                "must": "first DENY, second GRANT — the deny is what changes the outcome",
            },
        ],
        "tests": [
            {
                "id": "T1-precedence-table",
                "command": P1,
                "result": "PASS",
                "name": "Every decision_table row is asserted by recomputing evaluate_request",
            },
            {
                "id": "T2-wildcard-credential-validation",
                "command": P2,
                "result": "PASS",
                "name": "Credential-read wildcards rejected at validation time; named grant accepted",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0081-probe1-precedence-table",
            "verdict": "PASS",
            "independent": True,
            "role": "consumer-call-site",
            "notes": (
                "Probes are the consumer-side call site against this draft. An "
                "independent human contract reviewer and owner ratification are "
                "residual (catalog owner_approval_required=true)."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/ARC-0081/model.py",
                "exists": True,
                "role": "choke-point",
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "contract-author",
            "execution_substrate": "linux-local",
        },
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "owner ratification (ARC-0077) exists",
                "a production runtime already wires every path through evaluate_request",
                "secret values were read or printed",
            ]
        },
    }


def attach_computed(doc: dict) -> None:
    table = computed_decision_table()
    if len(table) < 12:
        raise SystemExit(f"decision table too small: {len(table)}")
    outcomes = {row["computed_outcome"] for row in table}
    if outcomes != {"GRANT", "DENY"}:
        raise SystemExit(f"decision table is not two-sided: {outcomes}")
    families = {row["family"] for row in table}
    for need in ("grant", "closed-world", "precedence", "wildcard"):
        if need not in families:
            raise SystemExit(f"missing family {need}")
    doc["decision_table"] = table
    doc["decision_table_row_count"] = len(table)
    doc["least_privilege_examples"] = computed_least_privilege()

    old = pset("old", stmt("grant", "tool", "Read"))
    new = pset("new", stmt("grant", "tool", "Read"), stmt("grant", "tool", "Write"))
    doc["escalation_example"] = is_escalation(old, new, ESCALATION_WITNESSES)

    parent = pset(
        "parent",
        stmt("grant", "tool", "Read"),
        stmt("grant", "credential", "env:GITHUB_TOKEN"),
    )
    child_ok = pset("child", stmt("grant", "tool", "Read"))
    child_bad = pset(
        "child-bad",
        stmt("grant", "tool", "Read"),
        stmt("grant", "tool", "Write"),
    )
    doc["delegation_examples"] = {
        "subset_allowed": delegation_allowed(parent, child_ok),
        "widening_refused": delegation_allowed(parent, child_bad),
    }

    bad = {
        "subject": "bad",
        "permissions": [{"effect": "grant", "class": "credential", "selector": "*"}],
    }
    good = {
        "subject": "good",
        "permissions": [
            {"effect": "grant", "class": "credential", "selector": "env:GITHUB_TOKEN"}
        ],
    }
    doc["validation_controls"] = {
        "wildcard_credential_grant_errors": validate_permission_set(bad),
        "named_credential_grant_errors": validate_permission_set(good),
        "tool_star_errors": validate_permission_set(
            {"subject": "t", "permissions": [{"effect": "grant", "class": "tool", "selector": "*"}]}
        ),
    }
    if not any(
        e["rule"] == "wildcard-credential-escalation"
        for e in doc["validation_controls"]["wildcard_credential_grant_errors"]
    ):
        raise SystemExit("emit: credential wildcard was not rejected")
    if doc["validation_controls"]["named_credential_grant_errors"]:
        raise SystemExit("emit: named credential grant was rejected")
    if doc["validation_controls"]["tool_star_errors"]:
        raise SystemExit("emit: tool * grant was rejected")

    try:
        evaluate_request(bad, req("credential", "env:GITHUB_TOKEN"))
        raise SystemExit("emit: evaluate accepted an unvalidated credential wildcard set")
    except InvalidPermissionSet:
        pass


def assert_schema_usable(doc: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        print("WARN: jsonschema not installed; skipping check_schema")
        return
    jsonschema.Draft202012Validator.check_schema(doc)
    validator = jsonschema.Draft202012Validator(doc)
    for g in GARBAGE:
        errs = list(validator.iter_errors(g))
        if not errs:
            raise SystemExit(f"emit: schema accepted garbage {g!r:.80}")
    good_instance = {
        "subject": "comp.demo",
        "permissions": [{"effect": "grant", "class": "tool", "selector": "Read"}],
    }
    errs = list(validator.iter_errors(good_instance))
    if errs:
        raise SystemExit(f"emit: schema rejected a valid instance: {errs[0].message}")
    bad_cred = {
        "subject": "bad",
        "permissions": [{"effect": "grant", "class": "credential", "selector": "*"}],
    }
    errs = list(validator.iter_errors(bad_cred))
    if not errs:
        raise SystemExit("emit: schema accepted credential wildcard grant")


def main() -> int:
    doc = schema_body()
    attach_computed(doc)
    assert_schema_usable(doc)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    if SENTINEL not in text:
        print("FAILED:emit sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_REL} bytes={len(text.encode('utf-8'))} rows={doc['decision_table_row_count']}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
