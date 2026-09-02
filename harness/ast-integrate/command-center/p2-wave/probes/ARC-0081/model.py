#!/usr/bin/env python3
"""ARC-0081 reference permission model: the single evaluation choke point.

Callers grant or deny capability only by going through `evaluate_request`.
Set-shape errors, including credential-read wildcards, are rejected by
`validate_permission_set` at declaration time — before any request is evaluated.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

CLASSES = ("tool", "path", "egress", "subprocess", "credential")
EFFECTS = ("grant", "deny")
ACTIONS = {
    "tool": ("invoke",),
    "path": ("read", "write", "delete", "exec"),
    "egress": ("connect",),
    "subprocess": ("spawn",),
    "credential": ("read",),
}
DEFAULT_ACTION = {
    "tool": "invoke",
    "path": "read",
    "egress": "connect",
    "subprocess": "spawn",
    "credential": "read",
}
WILDCARD_CHARS = frozenset("*?")

# Catalog tool names used as realistic selectors on this estate.
CATALOG_TOOLS = ("Read", "Grep", "Glob", "Bash", "Write", "Edit")


class InvalidPermissionSet(ValueError):
    """Declared set failed validation; must not be evaluated."""

    def __init__(self, errors: list[dict[str, str]]):
        self.errors = errors
        super().__init__(errors[0]["message"] if errors else "invalid permission set")


def contains_wildcard(selector: str) -> bool:
    return any(ch in selector for ch in WILDCARD_CHARS)


def default_action(class_: str) -> str:
    return DEFAULT_ACTION[class_]


def _as_str(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _norm_path(selector: str) -> str:
    s = selector.replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    if len(s) > 1 and s.endswith("/"):
        s = s[:-1]
    return s


def _glob_to_regex(pattern: str, *, path: bool) -> re.Pattern[str]:
    """Translate a restricted glob. `*` is one segment on paths; `**` crosses slashes."""
    out: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        if path and pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        ch = pattern[i]
        if ch == "*":
            out.append("[^/]*" if path else ".*")
        elif ch == "?":
            out.append("[^/]" if path else ".")
        else:
            out.append(re.escape(ch))
        i += 1
    out.append("$")
    return re.compile("".join(out))


def selector_matches(pattern: str, value: str, class_: str) -> bool:
    if pattern == value:
        return True
    if class_ == "path":
        pat = _norm_path(pattern)
        val = _norm_path(value)
        if pat == val:
            return True
        return _glob_to_regex(pat, path=True).fullmatch(val) is not None
    return _glob_to_regex(pattern, path=False).fullmatch(value) is not None


def action_matches(statement: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    class_ = request["class"]
    stmt_action = statement.get("action")
    req_action = request.get("action") or default_action(class_)
    if stmt_action in (None, ""):
        stmt_action = default_action(class_)
    if stmt_action == "*":
        return class_ != "credential"
    return stmt_action == req_action


def _err(rule: str, path: str, message: str) -> dict[str, str]:
    return {"rule": rule, "path": path, "message": message}


def validate_permission_set(pset: Any) -> list[dict[str, str]]:
    """Declaration-time checks. Credential-read wildcards fail here, not at evaluate."""
    errors: list[dict[str, str]] = []
    if not isinstance(pset, dict):
        return [_err("shape", "$", "permission set must be an object")]
    subject = pset.get("subject")
    if not isinstance(subject, str) or not subject.strip():
        errors.append(_err("shape", "$.subject", "subject must be a non-empty string"))
    perms = pset.get("permissions")
    if not isinstance(perms, list):
        errors.append(_err("shape", "$.permissions", "permissions must be an array"))
        return errors
    for i, stmt in enumerate(perms):
        loc = f"$.permissions[{i}]"
        if not isinstance(stmt, dict):
            errors.append(_err("shape", loc, "statement must be an object"))
            continue
        extra = set(stmt) - {"effect", "class", "action", "selector"}
        if extra:
            errors.append(
                _err("shape", loc, f"unknown fields {sorted(extra)}")
            )
        effect = stmt.get("effect")
        class_ = stmt.get("class")
        selector = stmt.get("selector")
        action = stmt.get("action")
        if effect not in EFFECTS:
            errors.append(_err("vocabulary", f"{loc}.effect", "effect must be grant or deny"))
        if class_ not in CLASSES:
            errors.append(
                _err(
                    "vocabulary",
                    f"{loc}.class",
                    "class must be tool|path|egress|subprocess|credential",
                )
            )
            continue
        if not isinstance(selector, str) or selector == "":
            errors.append(_err("shape", f"{loc}.selector", "selector must be a non-empty string"))
            continue
        if action not in (None, "") and action != "*":
            allowed = ACTIONS[class_]
            if action not in allowed:
                errors.append(
                    _err(
                        "vocabulary",
                        f"{loc}.action",
                        f"action {action!r} not valid for class {class_}",
                    )
                )
        if class_ == "path" and ".." in selector.replace("\\", "/").split("/"):
            errors.append(_err("path-traversal", f"{loc}.selector", "path selector must not contain .."))
        # THE load-bearing validation-time rule (catalog tests_required[1]):
        if effect == "grant" and class_ == "credential":
            if contains_wildcard(selector) or action == "*":
                errors.append(
                    _err(
                        "wildcard-credential-escalation",
                        loc,
                        "a grant of class credential must name a concrete selector; "
                        "wildcards that would grant credential read are rejected at "
                        "validation time, not at evaluation time",
                    )
                )
        if effect == "grant" and class_ not in CLASSES:
            errors.append(_err("vocabulary", f"{loc}.class", "unknown class"))
    return errors


def _statement_matches(stmt: Mapping[str, Any], request: Mapping[str, Any]) -> bool:
    if stmt.get("class") != request.get("class"):
        return False
    if not action_matches(stmt, request):
        return False
    selector = stmt.get("selector")
    value = request.get("selector")
    if not isinstance(selector, str) or not isinstance(value, str):
        return False
    return selector_matches(selector, value, request["class"])


def _normalize_request(request: Mapping[str, Any]) -> dict[str, str] | dict[str, str]:
    class_ = _as_str(request.get("class"))
    selector = _as_str(request.get("selector"))
    if class_ is None or selector is None:
        return {"error": "request must have string class and selector"}
    if class_ not in CLASSES:
        return {"error": f"unknown class {class_}"}
    if contains_wildcard(selector):
        return {"error": "request selector must be concrete (no wildcards)"}
    if class_ == "path" and ".." in selector.replace("\\", "/").split("/"):
        return {"error": "path request must not contain .."}
    action = _as_str(request.get("action")) or default_action(class_)
    if action not in ACTIONS[class_]:
        return {"error": f"action {action!r} not valid for class {class_}"}
    if class_ == "path":
        selector = _norm_path(selector)
    return {"class": class_, "action": action, "selector": selector}


def evaluate_request(
    pset: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    require_validated: bool = True,
) -> dict[str, Any]:
    """SINGLE choke point. Every capability class is decided here.

    Precedence (deny-overrides, closed world):
      1. Reject wildcard/unknown requests (fail closed).
      2. Collect matching statements (class + action + selector glob).
      3. If any matching deny: DENY (deny overrides any matching grant).
      4. Else if any matching grant: GRANT.
      5. Else DENY (closed-world default).
    Cross-class: a match in one class never grants another class.
    """
    if require_validated:
        errors = validate_permission_set(pset)
        if errors:
            raise InvalidPermissionSet(errors)
    perm_list = list(pset.get("permissions") or [])
    norm = _normalize_request(request)
    if "error" in norm:
        return {
            "outcome": "DENY",
            "reason": "invalid-request",
            "detail": norm["error"],
            "matched_grants": [],
            "matched_denies": [],
        }
    grants: list[dict[str, Any]] = []
    denies: list[dict[str, Any]] = []
    for stmt in perm_list:
        if not isinstance(stmt, dict):
            continue
        if not _statement_matches(stmt, norm):
            continue
        item = {
            "effect": stmt.get("effect"),
            "class": stmt.get("class"),
            "action": stmt.get("action") or default_action(norm["class"]),
            "selector": stmt.get("selector"),
        }
        if stmt.get("effect") == "deny":
            denies.append(item)
        elif stmt.get("effect") == "grant":
            grants.append(item)
    if denies:
        return {
            "outcome": "DENY",
            "reason": "deny-overrides",
            "detail": "a matching deny beats any matching grant",
            "matched_grants": grants,
            "matched_denies": denies,
        }
    if grants:
        return {
            "outcome": "GRANT",
            "reason": "grant-match",
            "detail": "at least one matching grant and no matching deny",
            "matched_grants": grants,
            "matched_denies": [],
        }
    return {
        "outcome": "DENY",
        "reason": "closed-world-default",
        "detail": "no matching grant; default is deny",
        "matched_grants": [],
        "matched_denies": [],
    }


def grant_as_request(stmt: Mapping[str, Any]) -> dict[str, str] | None:
    """Turn an exact (non-wildcard) grant into a request. Wildcards return None."""
    if stmt.get("effect") != "grant":
        return None
    class_ = stmt.get("class")
    selector = stmt.get("selector")
    if class_ not in CLASSES or not isinstance(selector, str):
        return None
    if contains_wildcard(selector) or stmt.get("action") == "*":
        return None
    return {
        "class": class_,
        "action": stmt.get("action") or default_action(class_),
        "selector": selector,
    }


def least_privilege(declared: Mapping[str, Any], observed: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Machine-checkable least privilege: declared covers observed and nothing more.

    - undeclared: observed requests that this set would DENY (used capability
      not in the declaration).
    - unused: grant statements that match no observed request. Exact grants
      that survive this check are equal to observed use. Wildcard grants that
      matched at least one observed request pass unused-detection but still
      permit unobserved invocations — that tightness gap is residual, and
      credential wildcards cannot appear because validation rejects them.
    """
    unused: list[dict[str, Any]] = []
    undeclared: list[dict[str, Any]] = []
    observed_list = [dict(r) for r in observed]
    for stmt in declared.get("permissions") or []:
        if not isinstance(stmt, dict) or stmt.get("effect") != "grant":
            continue
        matched = False
        for obs in observed_list:
            norm = _normalize_request(obs)
            if "error" in norm:
                continue
            if _statement_matches(stmt, norm):
                matched = True
                break
        if not matched:
            unused.append(
                {
                    "class": stmt.get("class"),
                    "action": stmt.get("action") or default_action(stmt["class"]),
                    "selector": stmt.get("selector"),
                }
            )
    for obs in observed_list:
        decision = evaluate_request(declared, obs)
        if decision["outcome"] != "GRANT":
            undeclared.append({"request": dict(obs), "reason": decision["reason"]})
    return {
        "holds": not unused and not undeclared,
        "unused_grants": unused,
        "undeclared_use": undeclared,
        "observed_count": len(observed_list),
    }


def is_escalation(old: Mapping[str, Any], new: Mapping[str, Any], witnesses: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Escalation iff some witness request is DENY under old and GRANT under new."""
    rows = []
    escalates = False
    for req in witnesses:
        a = evaluate_request(old, req)
        b = evaluate_request(new, req)
        widened = a["outcome"] == "DENY" and b["outcome"] == "GRANT"
        if widened:
            escalates = True
        rows.append(
            {
                "request": dict(req),
                "old": a["outcome"],
                "new": b["outcome"],
                "widened": widened,
            }
        )
    return {"escalates": escalates, "witnesses": rows}


def delegation_allowed(delegator: Mapping[str, Any], delegatee: Mapping[str, Any]) -> dict[str, Any]:
    """Delegation is a subset: every delegatee grant must be covered by the delegator.

    Credential grants may be delegated only as the same named selector (no
    wildcard parent — those cannot exist). Adding a grant the parent cannot
    itself obtain is refused.
    """
    errors: list[str] = []
    for stmt in delegatee.get("permissions") or []:
        if not isinstance(stmt, dict) or stmt.get("effect") != "grant":
            continue
        req = grant_as_request(stmt)
        if req is None:
            if stmt.get("class") == "credential":
                errors.append("credential grants cannot be delegated as wildcards")
                continue
            # Wildcard child: require an equal or `*`/`**` parent grant of the same class.
            parent_covers = any(
                p.get("effect") == "grant"
                and p.get("class") == stmt.get("class")
                and (
                    p.get("selector") == stmt.get("selector")
                    or p.get("selector") in ("*", "**")
                )
                for p in (delegator.get("permissions") or [])
                if isinstance(p, dict)
            )
            if not parent_covers:
                errors.append(
                    f"delegatee grant {stmt.get('class')}:{stmt.get('selector')} "
                    "is not covered by the delegator"
                )
            continue
        decision = evaluate_request(delegator, req)
        if decision["outcome"] != "GRANT":
            errors.append(
                f"delegatee grant {req['class']}:{req['selector']} is not held by the delegator"
            )
        if req["class"] == "credential":
            named = any(
                p.get("effect") == "grant"
                and p.get("class") == "credential"
                and p.get("selector") == req["selector"]
                and not contains_wildcard(str(p.get("selector", "")))
                for p in (delegator.get("permissions") or [])
                if isinstance(p, dict)
            )
            if not named:
                errors.append(
                    f"credential {req['selector']} may be delegated only as the same named grant"
                )
    return {"allowed": not errors, "errors": errors}


def pset(subject: str, *statements: Mapping[str, Any]) -> dict[str, Any]:
    return {"subject": subject, "permissions": [dict(s) for s in statements]}


def stmt(effect: str, class_: str, selector: str, action: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {"effect": effect, "class": class_, "selector": selector}
    if action is not None:
        row["action"] = action
    return row


def req(class_: str, selector: str, action: str | None = None) -> dict[str, str]:
    row = {"class": class_, "selector": selector}
    if action is not None:
        row["action"] = action
    return row
