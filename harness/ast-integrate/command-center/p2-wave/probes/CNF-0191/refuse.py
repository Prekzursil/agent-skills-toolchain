"""Destructive / credential / paid-resource refusal list.

Applied BEFORE any subprocess. A command matching this list is NOT-CHECKED,
never assumed correct because it looks plausible. The list itself is the
reviewed filter named by CNF-0191 tests_required.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Reviewed refusal list. Each row: id, pattern, reason class.
# Reviewer (probe2) re-reads this table and asserts it is consulted first.
REVIEWED_REFUSAL_LIST: list[tuple[str, str, str]] = [
    ("destructive-rm-rf", r"\brm\s+-[a-zA-Z]*[rf][a-zA-Z]*[rf]\b", "destructive"),
    ("destructive-git-push", r"\bgit\b(?:\s+\S+)*\s+push\b", "destructive"),
    ("destructive-git-reset", r"\bgit\b(?:\s+\S+)*\s+reset\s+--hard\b", "destructive"),
    ("destructive-git-checkout", r"\bgit\b(?:\s+\S+)*\s+checkout\b", "destructive"),
    ("destructive-git-rebase", r"\bgit\b(?:\s+\S+)*\s+rebase\b", "destructive"),
    ("destructive-git-stash", r"\bgit\b(?:\s+\S+)*\s+stash\b", "destructive"),
    ("git-clone", r"\bgit\b(?:\s+\S+)*\s+clone\b", "network-install"),
    ("git-crypt", r"\bgit-crypt\b", "credentials"),
    ("pipe-to-shell", r"\|\s*(ba)?sh\b", "destructive"),
    ("curl-pipe", r"\b(curl|wget)\b", "network-install"),
    ("fork-bomb", r":\(\)\s*\{\s*:\|:&\s*\};:", "destructive"),
    ("disk-wipe", r"\b(mkfs|dd\s+if=)\b", "destructive"),
    ("power", r"\b(shutdown|reboot|poweroff|halt)\b", "destructive"),
    ("sql-destroy", r"\b(DROP\s+TABLE|DELETE\s+FROM)\b", "destructive"),
    ("publish", r"\b(npm\s+publish|twine\s+upload)\b", "destructive"),
    ("npm-install", r"\bnpm\s+i(nstall)?\b", "network-install"),
    ("pip-install", r"\bpip\d*\s+install\b", "network-install"),
    ("uvx-network", r"\buvx\b", "network-install"),
    ("venv-create", r"\bpython3?\s+-m\s+venv\b", "destructive"),
    ("claude-config", r"\bclaude\s+(plugin|mcp)\b", "credentials"),
    ("mutating-close", r"close\.py\b(?!.*\s--list(?:\s|$))", "destructive"),
    ("mutating-render", r"render\.py\b(?!.*--check)", "destructive"),
    ("mutating-seed", r"\bseed\.py\b", "destructive"),
    ("copy-home", r"\bCopy-Item\b", "destructive"),
    ("slash-command", r"^/[a-zA-Z][a-zA-Z0-9_-]*(\s|$)", "not-executable"),
    ("chmod-root", r"\bchmod\s+-R\s+777\s+/", "destructive"),
    (
        "credentials",
        r"(AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|sk-[A-Za-z0-9]{8,})",
        "credentials",
    ),
    (
        "owner-login",
        r"\b(docker\s+login|aws\s+|gcloud\s+|az\s+|gh\s+auth)\b",
        "credentials",
    ),
    (
        "paid-resource",
        r"\b(terraform\s+apply|scw\s+instance\s+server\s+create)\b",
        "paid-resource",
    ),
]

_COMPILED = [
    (rid, re.compile(pat, re.I | re.S), klass)
    for rid, pat, klass in REVIEWED_REFUSAL_LIST
]


@dataclass(frozen=True)
class Refusal:
    rule_id: str
    klass: str
    reason: str


def classify(command: str) -> Refusal | None:
    text = command or ""
    for rid, rx, klass in _COMPILED:
        if rx.search(text):
            return Refusal(
                rule_id=rid,
                klass=klass,
                reason=f"NOT-CHECKED:{klass}:{rid} (refusal applied before subprocess)",
            )
    return None


def redact(command: str) -> str:
    """Never print secret material. Evidence keeps the shape, not the value."""
    out = command
    out = re.sub(
        r"(AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY)\s*=\s*\S+",
        r"\1=<redacted>",
        out,
        flags=re.I,
    )
    out = re.sub(r"sk-[A-Za-z0-9]{8,}", "sk-<redacted>", out)
    return out
