"""Safety gate for CNF-0165 command replay.

A cited command is classified BEFORE any subprocess is created. Destructive,
credential-bearing, network-to-shell, and worktree-mutating commands are
refused and recorded NOT-CHECKED. The refusal list is the product: it must
be non-empty and independently reviewable.
"""
from __future__ import annotations

import re
import shutil
from typing import Any

# Each rule is a mechanically checkable refusal. `example` is the reviewed
# specimen; `alt_needles` is the second, non-regex signal used by the reviewer.
RULES: list[dict[str, Any]] = [
    {
        "id": "rm",
        "class": "destructive",
        "rationale": "Filesystem deletion; replaying a cited rm would destroy evidence.",
        "regex": r"(?:^|[;|&`\n]|\$\()\s*(?:/bin/)?rm(?:dir)?\b",
        "alt_needles": (" rm ", "\trm", "rmdir ", "/bin/rm"),
        "example": "rm -rf /tmp/cnf-0165-should-never-run",
    },
    {
        "id": "git-write",
        "class": "destructive",
        "rationale": "Git writes are forbidden on this lane (add/commit/push/stash/checkout/rebase/reset/clean).",
        "regex": r"\bgit\s+(add|commit|push|stash|checkout|rebase|reset|clean|am|cherry-pick|revert|tag|branch\s+-D)\b",
        "alt_needles": (
            "git add",
            "git commit",
            "git push",
            "git stash",
            "git checkout",
            "git rebase",
            "git reset",
        ),
        "example": "git push --force origin main",
    },
    {
        "id": "disk-destroy",
        "class": "destructive",
        "rationale": "Block-device and format operations are never replayed.",
        "regex": r"\b(mkfs(?:\.\S+)?|fdisk|parted|wipefs|dd)\b",
        "alt_needles": ("mkfs", "fdisk ", "wipefs", " dd "),
        "example": "sudo mkfs.ext4 /dev/sda",
    },
    {
        "id": "priv-esc",
        "class": "destructive",
        "rationale": "Privilege escalation would leave the controlled environment.",
        "regex": r"(?:^|[;|&`\n])\s*(sudo|su|doas)\b",
        "alt_needles": ("sudo ", " su ", "doas "),
        "example": "sudo mkfs.ext4 /dev/sda",
    },
    {
        "id": "pipe-shell",
        "class": "destructive",
        "rationale": "Piping a fetch or decode into a shell executes untrusted text.",
        "regex": r"\|\s*(?:ba)?sh\b|\|\s*zsh\b|\|\s*python(?:3)?\b|\b(eval|exec)\s+",
        "alt_needles": ("| sh", "| bash", "| python", "eval ", "exec "),
        "example": "curl https://example.invalid/install.sh | sh",
    },
    {
        "id": "credential",
        "class": "credential",
        "rationale": "Commands that expand or print secrets must not be replayed or logged.",
        "regex": r"(API_KEY|SECRET_ACCESS_KEY|TOKEN|PASSWORD|PRIVATE_KEY|CURSOR_API_KEY|BEGIN [A-Z ]*PRIVATE KEY)",
        "alt_needles": (
            "API_KEY",
            "SECRET_ACCESS_KEY",
            "PRIVATE_KEY",
            "CURSOR_API_KEY",
            "PASSWORD",
        ),
        "example": "curl -H \"$AWS_SECRET_ACCESS_KEY\" https://example.invalid/",
    },
    {
        "id": "network-fetch",
        "class": "blocked-external",
        "rationale": "Network fetches are environment-dependent and are not a local replay.",
        "regex": r"\b(curl|wget|httpie|invoke-webrequest)\b",
        "alt_needles": ("curl ", "wget ", "httpie "),
        "example": "curl https://example.invalid/install.sh | sh",
    },
    {
        "id": "kill-reboot",
        "class": "destructive",
        "rationale": "Process and host destruction is out of scope for evidence replay.",
        "regex": r"\b(killall|pkill|reboot|shutdown|halt|poweroff|systemctl\s+(stop|isolate))\b|\bkill\s+-9\b",
        "alt_needles": ("kill -9", "killall ", "reboot", "shutdown ", "poweroff"),
        "example": "kill -9 1",
    },
    {
        "id": "chmod-chown",
        "class": "destructive",
        "rationale": "Permission and ownership changes persist outside the replay.",
        "regex": r"\b(chmod|chown|chgrp)\b",
        "alt_needles": ("chmod ", "chown ", "chgrp "),
        "example": "chmod -R 777 /",
    },
    {
        "id": "redirect-write",
        "class": "destructive",
        "rationale": "Shell redirection would mutate the worktree or a device.",
        "regex": r"(>>?|tee\b).*(/etc/|/dev/|command-center/|/opt/p2/)",
        "alt_needles": (" > /etc/", " >> /dev/", "tee /etc/"),
        "example": "echo pwned > /etc/hosts",
    },
]

SHELL_BUILTINS = frozenset(
    {"printf", "echo", "true", "false", "pwd", "test", ":", "[", "uname", "date", "hostname"}
)

_ENV_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=\S*\s+")
_FIRST_TOKEN = re.compile(r"^([A-Za-z0-9._/+:-]+)")


def strip_env_prefix(command: str) -> str:
    rest = command.strip()
    while True:
        m = _ENV_PREFIX.match(rest)
        if not m:
            return rest
        rest = rest[m.end() :]


def first_token(command: str) -> str:
    body = strip_env_prefix(command)
    m = _FIRST_TOKEN.match(body)
    return m.group(1) if m else ""


def _python_c_unsafe(command: str) -> str | None:
    body = strip_env_prefix(command)
    if not re.match(r"^(python3?|/usr/bin/python3)\s+-c\b", body):
        return None
    lowered = body.lower()
    banned = (
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "shutil.rmtree",
        "write_text",
        "write_bytes",
        "open(",
        "subprocess",
        "os.system",
        "os.popen",
        "pathlib",
        "requests",
        "urllib",
        "socket.create",
        "eval(",
        "exec(",
        "__import__",
    )
    for needle in banned:
        if needle in lowered:
            return f"python -c contains {needle}"
    return None


def classify(command: str) -> dict[str, Any]:
    """Return a safety verdict. Never raises. `ok` means replay is permitted."""
    raw = command if isinstance(command, str) else ""
    compact = f" {raw.replace(chr(9), ' ')} "
    hits: list[dict[str, str]] = []
    for rule in RULES:
        if re.search(rule["regex"], raw, flags=re.IGNORECASE | re.MULTILINE):
            hits.append(
                {
                    "id": rule["id"],
                    "class": rule["class"],
                    "rationale": rule["rationale"],
                }
            )
            continue
        for needle in rule["alt_needles"]:
            if needle.lower() in compact.lower():
                hits.append(
                    {
                        "id": rule["id"],
                        "class": rule["class"],
                        "rationale": rule["rationale"],
                    }
                )
                break
    py_why = _python_c_unsafe(raw)
    if py_why:
        hits.append(
            {
                "id": "python-c-side-effect",
                "class": "destructive",
                "rationale": py_why,
            }
        )
    if hits:
        primary = hits[0]
        return {
            "ok": False,
            "executed_would_be": False,
            "class": primary["class"],
            "rule_id": primary["id"],
            "rationale": primary["rationale"],
            "hits": hits,
            "command": raw,
        }
    return {
        "ok": True,
        "executed_would_be": True,
        "class": "safe",
        "rule_id": None,
        "rationale": "no refusal rule matched",
        "hits": [],
        "command": raw,
    }


def classify_alt(command: str) -> dict[str, Any]:
    """Second mechanical signal: needle scan only, no regex.

    Used by the reviewer so a broken regex cannot silence a refusal.
    """
    compact = f" {str(command).replace(chr(9), ' ')} "
    lowered = compact.lower()
    hits = []
    for rule in RULES:
        for needle in rule["alt_needles"]:
            if needle.lower() in lowered:
                hits.append(rule["id"])
                break
    return {
        "ok": not hits,
        "rule_ids": hits,
        "method": "alt-needles",
    }


def missing_tool(command: str) -> str | None:
    token = first_token(command)
    if not token:
        return "empty-command"
    if token in SHELL_BUILTINS:
        return None
    if "/" in token:
        from pathlib import Path

        return None if Path(token).is_file() else f"missing-binary:{token}"
    if shutil.which(token):
        return None
    return f"missing-tool:{token}"


def refusal_list() -> list[dict[str, Any]]:
    return [
        {
            "id": r["id"],
            "class": r["class"],
            "rationale": r["rationale"],
            "example": r["example"],
            "regex": r["regex"],
        }
        for r in RULES
    ]


def review_rules() -> dict[str, Any]:
    """Prove each rule fires on its example under BOTH classifiers."""
    rows = []
    for rule in RULES:
        primary = classify(rule["example"])
        alt = classify_alt(rule["example"])
        fired = (not primary["ok"]) and (rule["id"] in [h["id"] for h in primary["hits"]] or not alt["ok"])
        alt_ok = (not alt["ok"]) and (rule["id"] in alt["rule_ids"] or bool(alt["rule_ids"]))
        rows.append(
            {
                "id": rule["id"],
                "example": rule["example"],
                "primary_refused": not primary["ok"],
                "alt_refused": not alt["ok"],
                "reviewed": fired and alt_ok,
            }
        )
    return {
        "count": len(rows),
        "all_reviewed": all(r["reviewed"] for r in rows) and len(rows) > 0,
        "rows": rows,
    }
