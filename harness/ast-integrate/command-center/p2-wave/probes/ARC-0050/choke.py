"""Single permission choke point for A7 security-first capability invocations.

Every capability request must name a tool VERB. Grants are compared to the
verb, not to payload text (the measured use-versus-mention failure class).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

INVOKE_RE = re.compile(r"""invoke\(\s*['"]([a-z][a-z0-9:-]*)['"]""")
CHOKE_SYMBOL = "evaluate_capability"
CHOKE_PATH = "command-center/p2-wave/probes/ARC-0050/choke.py"


def evaluate_capability(
    request: dict[str, Any],
    grants: Iterable[str],
    *,
    mode: str = "verb",
) -> dict[str, Any]:
    """mode=verb is the honest choke. mode=text matches payload TEXT (fail-open)."""
    grant_set = {str(g) for g in grants}
    verb = str(request.get("verb") or "")
    payload = str(request.get("payload") or "")
    if mode == "allow-all":
        return {
            "decision": "ALLOW",
            "reason": "guard-removed",
            "verb": verb,
            "mode": mode,
            "choke": CHOKE_SYMBOL,
        }
    if mode == "text":
        fired = any(g in payload for g in grant_set) or any(
            g in payload for g in ("process:exec", "fs:write", "fs:read")
        )
        # Text matcher: mention of a forbidden verb fires even when the request
        # verb is allowed. Actual undeclared verbs with no mention slip through.
        mentioned_undeclared = [
            g
            for g in ("process:exec", "fs:write")
            if g in payload and g not in grant_set
        ]
        if mentioned_undeclared:
            return {
                "decision": "DENY",
                "reason": "text-mention",
                "verb": verb,
                "mode": mode,
                "choke": CHOKE_SYMBOL,
            }
        return {
            "decision": "ALLOW",
            "reason": "text-silent",
            "verb": verb,
            "mode": mode,
            "choke": CHOKE_SYMBOL,
        }
    if not verb:
        return {
            "decision": "DENY",
            "reason": "missing-verb",
            "verb": verb,
            "mode": mode,
            "choke": CHOKE_SYMBOL,
        }
    if verb in grant_set:
        return {
            "decision": "ALLOW",
            "reason": "granted",
            "verb": verb,
            "mode": mode,
            "choke": CHOKE_SYMBOL,
        }
    return {
        "decision": "DENY",
        "reason": "undeclared-verb",
        "verb": verb,
        "mode": mode,
        "choke": CHOKE_SYMBOL,
    }


def invoked_verbs(hook_source: str) -> list[str]:
    return INVOKE_RE.findall(hook_source)


def inspect_plugin_bundle(
    members: dict[str, bytes],
    manifest_permissions: list[str],
    *,
    mode: str = "verb",
) -> dict[str, Any]:
    grants = list(manifest_permissions)
    undeclared: list[str] = []
    mentions_only: list[str] = []
    for rel, blob in sorted(members.items()):
        if not rel.endswith(".py"):
            text = blob.decode("utf-8", errors="replace")
            for verb in ("process:exec", "fs:write"):
                if verb in text and verb not in grants:
                    mentions_only.append(f"{rel}:{verb}")
            continue
        source = blob.decode("utf-8", errors="replace")
        for verb in invoked_verbs(source):
            req = {"verb": verb, "payload": source}
            decision = evaluate_capability(req, grants, mode=mode)
            if decision["decision"] == "DENY" and decision.get("reason") != "text-mention":
                undeclared.append(f"{rel}:{verb}")
            elif mode == "text" and decision["decision"] == "DENY":
                mentions_only.append(f"{rel}:{verb}")
            elif mode == "allow-all":
                continue
            elif verb not in grants:
                undeclared.append(f"{rel}:{verb}")
    rejected = bool(undeclared) if mode != "allow-all" else False
    if mode == "text":
        rejected = bool(mentions_only)
        undeclared = []
    return {
        "rejected": rejected,
        "undeclared_invokes": undeclared,
        "text_mentions": mentions_only,
        "mode": mode,
        "grants": grants,
        "choke": CHOKE_SYMBOL,
        "path": CHOKE_PATH,
    }


def permission_boundary_cases(mode: str = "verb") -> dict[str, Any]:
    grants = ["fs:read"]
    allowed = evaluate_capability(
        {"verb": "fs:read", "payload": "read candidates.json"}, grants, mode=mode
    )
    denied = evaluate_capability(
        {"verb": "process:exec", "payload": "id"}, grants, mode=mode
    )
    mention = evaluate_capability(
        {
            "verb": "fs:read",
            "payload": (
                "Documentation: a malicious plugin that calls process:exec must be rejected."
            ),
        },
        grants,
        mode=mode,
    )
    if mode == "verb":
        fired_on_bad = denied["decision"] == "DENY"
        silent_on_good = allowed["decision"] == "ALLOW" and mention["decision"] == "ALLOW"
    elif mode == "allow-all":
        fired_on_bad = denied["decision"] == "DENY"
        silent_on_good = allowed["decision"] == "ALLOW"
    else:
        # text mode: mention of process:exec in a legitimate fs:read payload fires (FP)
        fired_on_bad = denied["decision"] == "DENY"
        silent_on_good = mention["decision"] == "ALLOW"
    return {
        "allowed": allowed,
        "denied": denied,
        "mention": mention,
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "mode": mode,
    }
