#!/usr/bin/env python3
"""PreToolUse guardrail: deny Read/Edit/Grep/Bash access to credential files.

Enforces the no-raw-credentials rule STRUCTURALLY (not by trusting the model):
a confused/jailbroken agent still cannot pull a literal secret into context.
The declarative permissions.deny in settings.json already blocks the Read tool
on .env/*.pem/*credentials*; this ALSO closes the Bash/Grep gap (e.g. `cat .env`,
`Get-Content .env`, `grep KEY credentials`).

Fail-open (AGENTS.md 6): any internal error exits 0 so the harness never wedges.
Emits the docs' preferred JSON deny (hookSpecificOutput.permissionDecision).
"""

import json
import sys
import re
import fnmatch
import os

SENSITIVE_GLOBS = [
    ".env",
    ".env.*",
    "*.env",
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.pkcs12",
    "credentials",
    "credentials.*",
    "*credentials*",
    ".credentials.json",
    "id_rsa",
    "id_rsa.*",
    "id_ed25519",
    "id_ed25519.*",
    "secrets.*",
    "*.secret",
    ".netrc",
    ".pgpass",
]
# read-ish verbs that would surface file contents into a tool result
READ_VERBS = (
    r"(?:cat|type|bat|less|more|head|tail|nl|strings|xxd|od|base64|"
    r"grep|rg|sls|select-string|get-content|\bgc\b|printf)"
)
# bare secret-name fragments to look for near a read verb
SECRET_FRAGMENTS = [
    ".env",
    "credential",
    "id_rsa",
    "id_ed25519",
    ".pem",
    ".key",
    ".netrc",
    ".pgpass",
    ".p12",
    ".pfx",
]
# PUBLIC placeholder templates. By universal convention these are COMMITTED to
# version control and hold no real secret (`.env` is gitignored, `.env.example`
# is not), so the `.env.*` glob must not swallow them: it made the guard deny the
# first step of `commands/update-docs.md:29` ("Read `.env.example` (or
# `.env.template`, `.env.sample`)"). Matched as EXACT basenames, never as a glob,
# so `.env.example.bak` / `.env.examples` stay sensitive.
PUBLIC_TEMPLATE_SUFFIXES = ("example", "template", "sample")
PUBLIC_TEMPLATE_BASENAMES = frozenset(
    ".env." + suffix for suffix in PUBLIC_TEMPLATE_SUFFIXES
)


def is_sensitive(path):
    if not path:
        return False
    p = str(path).strip().strip('"').strip("'")
    base = os.path.basename(p).lower()
    if base in PUBLIC_TEMPLATE_BASENAMES:
        return False
    low = p.replace("\\", "/").lower()
    for g in SENSITIVE_GLOBS:
        gl = g.lower()
        if fnmatch.fnmatch(base, gl) or fnmatch.fnmatch(low, "*/" + gl):
            return True
    return False


def _fragment_pattern(fragment):
    """Regex source for one SECRET_FRAGMENTS entry.

    `.env` is the only special case: an occurrence that is exactly a public
    template (`.env.example`, `.env.template`, `.env.sample`) must NOT match, so
    `cat .env.example` stays allowed while `cat .env`, `cat .env.local` and
    `cat .env.examples` keep matching. The trailing `(?![\\w.-])` keeps this
    exemption in lockstep with the exact-basename rule in is_sensitive().
    """
    if fragment != ".env":
        return re.escape(fragment)
    suffixes = "|".join(PUBLIC_TEMPLATE_SUFFIXES)
    return r"\.env(?!\.(?:" + suffixes + r")(?![\w.-]))"


def bash_touches_secret(cmd):
    if not cmd:
        return False
    low = str(cmd).lower()
    frag = "|".join(_fragment_pattern(f) for f in SECRET_FRAGMENTS)
    # a read verb on the same segment as a secret fragment
    if re.search(READ_VERBS + r"[^\n|;&<>]*(?:" + frag + r")", low):
        return True
    return False


def deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


REASON = (
    "Blocked by the no-raw-credentials guardrail: credential files must not be "
    "read into the model context. Wire the secret via ${ENV} indirection in "
    '.mcp.json (headers: "Authorization": "Bearer ${PHYLO_TOKEN}"), a '
    "headersHelper script, or the local token broker — the literal must be "
    "resolved by a non-model process, never surfaced to the agent."
)


def _guard_enabled():
    """Owner directive 2026-07-11: this credential-file-READ block is OPT-IN and
    OFF by default. It created setbacks in interactive sessions (inspecting one's
    OWN ~/.ssh keys / .env / config, and workflows that merely NAME a credential
    file). Set HARNESS_CREDENTIAL_GUARD=1 (or true/yes/on) to re-enable. Mirrors the
    gate in ~/.agents/harness/modules.py SecretGuardModule so both credential
    mechanisms share ONE toggle. The secret-LITERAL input block and the
    irreversible-op (disk-wipe / history-rewrite) gate are separate and unaffected."""
    return os.environ.get("HARNESS_CREDENTIAL_GUARD", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def main():
    data = json.load(sys.stdin)
    if not _guard_enabled():
        sys.exit(
            0
        )  # credential-file block DISABLED BY DEFAULT (owner directive 2026-07-11)
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    if tool in ("Read", "Edit", "NotebookEdit", "MultiEdit"):
        if is_sensitive(ti.get("file_path") or ti.get("notebook_path", "")):
            deny(REASON)
    elif tool == "Grep":
        if is_sensitive(ti.get("path", "")):
            deny(REASON)
    elif tool in ("Bash", "PowerShell"):
        if bash_touches_secret(ti.get("command", "")):
            deny(REASON)
    sys.exit(0)  # no decision -> normal permission flow


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)  # fail-open
