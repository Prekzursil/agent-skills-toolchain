"""Reject tests whose only observable is a file path.

Catalog evidence_requirement: each proposed test names a process-visible
effect, a loader log line, or a tool-inventory entry. A test whose only
observable is a file path is rejected in the plan itself.
"""
from __future__ import annotations

from typing import Any

ALLOWED_KINDS = frozenset(
    {"process-visible-effect", "loader-log-line", "tool-inventory-entry"}
)
FORBIDDEN_KINDS = frozenset(
    {"file-existence", "path-exists", "is_file", "file-path", "glob"}
)


def observable_ok(obs: Any) -> tuple[bool, str]:
    if not isinstance(obs, dict):
        return False, "observable-missing"
    kind = str(obs.get("kind") or "")
    if kind in FORBIDDEN_KINDS:
        return False, f"forbidden-kind:{kind}"
    if kind not in ALLOWED_KINDS:
        return False, f"kind-not-runtime:{kind}"
    if obs.get("distinct_from_file_existence") is not True:
        return False, "not-distinct-from-file-existence"
    reads = str(obs.get("reads") or "").strip()
    if len(reads) < 8:
        return False, "reads-too-short"
    lowered = reads.lower()
    if "exist" in lowered and "inventor" not in lowered and "canary" not in lowered and "log" not in lowered:
        return False, "reads-looks-like-existence"
    return True, kind


def both_states_ok(row: dict[str, Any]) -> tuple[bool, str]:
    bs = row.get("both_states")
    if not isinstance(bs, dict):
        return False, "both-states-missing"
    if bs.get("fired_on_unloaded") is not True:
        return False, "must-fire-on-unloaded"
    if bs.get("silent_on_loaded") is not True:
        return False, "must-be-silent-on-loaded"
    return True, "both-states"


def check_tests(doc: dict[str, Any]) -> tuple[bool, str]:
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        return False, "tests-missing-or-short"
    for i, row in enumerate(tests):
        if not isinstance(row, dict):
            return False, f"tests[{i}]-not-object"
        ok, why = observable_ok(row.get("observable"))
        if not ok:
            return False, f"tests[{i}].{row.get('id')}:{why}"
        ok, why = both_states_ok(row)
        if not ok:
            return False, f"tests[{i}].{row.get('id')}:{why}"
    rejected = doc.get("rejected_tests")
    if not isinstance(rejected, list) or len(rejected) < 1:
        return False, "rejected-tests-missing"
    found_path_only = False
    for r in rejected:
        if not isinstance(r, dict):
            continue
        reason = str(r.get("reason") or "")
        kind = str((r.get("observable") or {}).get("kind") or r.get("kind") or "")
        if kind in FORBIDDEN_KINDS or "file" in reason.lower() or "path" in reason.lower():
            found_path_only = True
    if not found_path_only:
        return False, "rejected-tests-must-include-file-path-only"
    anti = doc.get("anti_tautology")
    if not isinstance(anti, dict):
        return False, "anti-tautology-missing"
    if anti.get("all_declaration_files_syntactically_valid") is not True:
        return False, "anti-tautology-declarations-not-valid"
    if anti.get("test_fails_while_declarations_valid") is not True:
        return False, "anti-tautology-did-not-fail"
    return True, f"tests={len(tests)} rejected={len(rejected)}"


def file_existence_mutant(doc: dict[str, Any]) -> dict[str, Any]:
    """Replace the first test's observable with a file-existence check."""
    import copy

    mutant = copy.deepcopy(doc)
    tests = mutant.get("tests") or []
    if tests:
        tests[0]["observable"] = {
            "kind": "file-existence",
            "reads": "Path(repo/capabilities/skills/skill.council.skill.json).is_file()",
            "distinct_from_file_existence": False,
        }
    return mutant
