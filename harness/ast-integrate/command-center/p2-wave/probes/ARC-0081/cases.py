#!/usr/bin/env python3
"""Decision-table INPUTS for ARC-0081. Outcomes are computed, never hand-authored."""
from __future__ import annotations

from model import pset, req, stmt

DECISION_CASES: list[dict] = [
    {
        "id": "exact-grant-tool",
        "family": "grant",
        "permissions": pset("u", stmt("grant", "tool", "Read")),
        "request": req("tool", "Read"),
        "notes": "Named tool grant matches an identical invoke request.",
    },
    {
        "id": "closed-world-unlisted-tool",
        "family": "closed-world",
        "permissions": pset("u", stmt("grant", "tool", "Read")),
        "request": req("tool", "Write"),
        "notes": "Unlisted tool is denied; default is closed-world.",
    },
    {
        "id": "deny-overrides-same-selector",
        "family": "precedence",
        "permissions": pset(
            "u",
            stmt("grant", "tool", "Bash"),
            stmt("deny", "tool", "Bash"),
        ),
        "request": req("tool", "Bash"),
        "notes": "When grant and deny both match, deny wins.",
    },
    {
        "id": "deny-overrides-broader-grant",
        "family": "precedence",
        "permissions": pset(
            "u",
            stmt("grant", "path", "/tmp/**"),
            stmt("deny", "path", "/tmp/secret"),
        ),
        "request": req("path", "/tmp/secret"),
        "notes": "A specific deny beats a broader grant that also matches.",
    },
    {
        "id": "tool-wildcard-grant",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "tool", "*")),
        "request": req("tool", "Grep"),
        "notes": "Tool wildcard expands to a named catalog tool.",
    },
    {
        "id": "tool-wildcard-does-not-cross-class",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "tool", "*")),
        "request": req("credential", "env:GITHUB_TOKEN"),
        "notes": "A tool wildcard never grants credential read.",
    },
    {
        "id": "path-double-star-descends",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "path", "/tmp/**")),
        "request": req("path", "/tmp/a/b.txt"),
        "notes": "** crosses path segments.",
    },
    {
        "id": "path-single-star-one-segment",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "path", "/tmp/*")),
        "request": req("path", "/tmp/a/b.txt"),
        "notes": "Single-segment * does not cross a slash.",
    },
    {
        "id": "egress-exact",
        "family": "grant",
        "permissions": pset("u", stmt("grant", "egress", "api.github.com:443")),
        "request": req("egress", "api.github.com:443"),
        "notes": "Named egress grant matches the same host:port.",
    },
    {
        "id": "egress-unlisted-host",
        "family": "closed-world",
        "permissions": pset("u", stmt("grant", "egress", "api.github.com:443")),
        "request": req("egress", "evil.example:443"),
        "notes": "Unlisted egress target is denied.",
    },
    {
        "id": "subprocess-exact",
        "family": "grant",
        "permissions": pset("u", stmt("grant", "subprocess", "/usr/bin/git")),
        "request": req("subprocess", "/usr/bin/git"),
        "notes": "Named subprocess grant matches the same executable.",
    },
    {
        "id": "subprocess-other-bin",
        "family": "closed-world",
        "permissions": pset("u", stmt("grant", "subprocess", "/usr/bin/git")),
        "request": req("subprocess", "/usr/bin/python3"),
        "notes": "A subprocess grant does not imply a different executable.",
    },
    {
        "id": "credential-named-grant",
        "family": "grant",
        "permissions": pset("u", stmt("grant", "credential", "env:GITHUB_TOKEN")),
        "request": req("credential", "env:GITHUB_TOKEN"),
        "notes": "Named credential grant (no wildcard) matches that id only.",
    },
    {
        "id": "credential-other-name",
        "family": "closed-world",
        "permissions": pset("u", stmt("grant", "credential", "env:GITHUB_TOKEN")),
        "request": req("credential", "env:AWS_SECRET_ACCESS_KEY"),
        "notes": "A named credential grant does not cover a different secret id.",
    },
    {
        "id": "unrelated-deny-does-not-block",
        "family": "precedence",
        "permissions": pset(
            "u",
            stmt("grant", "path", "/var/log/**"),
            stmt("deny", "path", "/tmp/**"),
        ),
        "request": req("path", "/var/log/app.log"),
        "notes": "A deny that does not match leaves a matching grant intact.",
    },
    {
        "id": "empty-set-closed",
        "family": "closed-world",
        "permissions": pset("u"),
        "request": req("tool", "Read"),
        "notes": "Empty declaration denies every request.",
    },
    {
        "id": "path-star-does-not-grant-credential",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "path", "**")),
        "request": req("credential", "env:GITHUB_TOKEN"),
        "notes": "A path wildcard never grants credential read.",
    },
    {
        "id": "tool-prefix-wildcard",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "tool", "mcp__*")),
        "request": req("tool", "mcp__cloud-hub__modal_sandbox_exec"),
        "notes": "Prefix wildcard expands inside the tool class only.",
    },
    {
        "id": "tool-prefix-wildcard-nonmatch",
        "family": "wildcard",
        "permissions": pset("u", stmt("grant", "tool", "mcp__*")),
        "request": req("tool", "Bash"),
        "notes": "Prefix wildcard does not match a name outside the prefix.",
    },
    {
        "id": "deny-wildcard-overrides-exact-grant",
        "family": "precedence",
        "permissions": pset(
            "u",
            stmt("grant", "tool", "Bash"),
            stmt("deny", "tool", "*"),
        ),
        "request": req("tool", "Bash"),
        "notes": "A matching deny wildcard still overrides an exact grant.",
    },
    {
        "id": "path-action-mismatch",
        "family": "closed-world",
        "permissions": pset("u", stmt("grant", "path", "/tmp/**", action="read")),
        "request": req("path", "/tmp/a", action="write"),
        "notes": "A read grant does not authorize write on the same path.",
    },
]


LEAST_PRIVILEGE_CASES: list[dict] = [
    {
        "id": "lp-exact-equality",
        "declared": pset(
            "comp.a",
            stmt("grant", "tool", "Read"),
            stmt("grant", "tool", "Grep"),
        ),
        "observed": [req("tool", "Read"), req("tool", "Grep")],
    },
    {
        "id": "lp-unused-grant",
        "declared": pset(
            "comp.b",
            stmt("grant", "tool", "Read"),
            stmt("grant", "tool", "Write"),
        ),
        "observed": [req("tool", "Read")],
    },
    {
        "id": "lp-undeclared-use",
        "declared": pset("comp.c", stmt("grant", "tool", "Read")),
        "observed": [req("tool", "Read"), req("tool", "Write")],
    },
]

ESCALATION_WITNESSES = [
    req("tool", "Write"),
    req("credential", "env:GITHUB_TOKEN"),
]
