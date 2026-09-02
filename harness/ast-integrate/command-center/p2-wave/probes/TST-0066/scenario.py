"""Alias matrix: trailing-dot and 8.3 against every guard under test."""
from __future__ import annotations

from winpath import FIXTURE_VOLUME, same_identity

# Denied file (catalog: blob recorded as hook.py. checks out as hook.py;
# deny keyed on the checked-out name must still catch the dotted alias).
DENIED_SECRET = r"C:\Program Files\app\secret.txt"
DENIED_SECRET_DOT = r"C:\Program Files\app\secret.txt."
DENIED_SECRET_SPACE = r"C:\Program Files\app\secret.txt "
DENIED_SECRET_83 = r"C:\PROGRA~1\app\SECRET~1.TXT"

ALLOWED_HOOKS = r"C:\Program Files\app\hooks"
ALLOWED_HOOK = r"C:\Program Files\app\hooks\hook.py"
ALLOWED_HOOK_DOT = r"C:\Program Files\app\hooks\hook.py."
ALLOWED_HOOK_83 = r"C:\PROGRA~1\app\HOOKS~1\HOOK~1.PY"

# Outside the hooks allowlist, still under Program Files\app.
OUTSIDE_HOOKS_VIA_DOT = r"C:\Program Files\app\hooks.\..\secret.txt"
OUTSIDE_HOOKS_VIA_83 = r"C:\PROGRA~1\app\hooks\..\secret.txt"

REPO_ROOT = r"C:\work\ast-integrate"
OUTSIDE_VIA_DOT = r"C:\work\ast-integrate.\..\escape.txt"
OUTSIDE_VIA_83 = r"C:\work\AST-IN~1\..\escape.txt"
INSIDE_VIA_83 = r"C:\work\AST-IN~1\command-center\WORK-U~1.JSO"
INSIDE_LONG = r"C:\work\ast-integrate\command-center\WORK-UNIT-CATALOG.json"
INSIDE_DOT = r"C:\work\ast-integrate\command-center\WORK-UNIT-CATALOG.json."

# Live estate deny/exclude list member (reconcile_delivery.DECLARING_DOCS).
ESTATE_DENIED_REL = "command-center/WORK-UNIT-CATALOG.json"
ESTATE_DENIED_DOT = "command-center/WORK-UNIT-CATALOG.json."
ESTATE_DENIED_83 = "COMMAN~1/WORK-U~1.JSO"


def alias_pairs() -> list[dict]:
    """Every (long identity, trailing-dot alias, 8.3 alias) the probes fire."""
    return [
        {
            "id": "denied-secret",
            "kind": "deny-target",
            "canonical": DENIED_SECRET,
            "trailing_dot": DENIED_SECRET_DOT,
            "trailing_space": DENIED_SECRET_SPACE,
            "short_name": DENIED_SECRET_83,
        },
        {
            "id": "allowed-hook",
            "kind": "allow-target",
            "canonical": ALLOWED_HOOK,
            "trailing_dot": ALLOWED_HOOK_DOT,
            "short_name": ALLOWED_HOOK_83,
        },
        {
            "id": "repo-catalog",
            "kind": "containment-inside",
            "canonical": INSIDE_LONG,
            "trailing_dot": INSIDE_DOT,
            "short_name": INSIDE_VIA_83,
        },
    ]


def prove_identities() -> list[dict]:
    rows = []
    checks = [
        ("denied-dot", DENIED_SECRET, DENIED_SECRET_DOT, True),
        ("denied-space", DENIED_SECRET, DENIED_SECRET_SPACE, True),
        ("denied-83", DENIED_SECRET, DENIED_SECRET_83, True),
        ("hook-dot", ALLOWED_HOOK, ALLOWED_HOOK_DOT, True),
        ("hook-83", ALLOWED_HOOK, ALLOWED_HOOK_83, True),
        ("inside-83", INSIDE_LONG, INSIDE_VIA_83, True),
        ("outside-dot-escapes", REPO_ROOT, OUTSIDE_VIA_DOT, False),
        ("outside-83-escapes", REPO_ROOT, OUTSIDE_VIA_83, False),
        ("outside-hooks-dot", ALLOWED_HOOKS, OUTSIDE_HOOKS_VIA_DOT, False),
        ("distinct-secret-vs-hook", DENIED_SECRET, ALLOWED_HOOK, False),
    ]
    for cid, a, b, want in checks:
        got = same_identity(a, b, FIXTURE_VOLUME)
        rows.append(
            {
                "id": cid,
                "a": a,
                "b": b,
                "same": got,
                "expected": want,
                "ok": got is want,
            }
        )
    return rows
