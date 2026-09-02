"""Local GitHub secret-scanning prefix engine.

This is NOT hosted GitHub Secret Scanning. Patterns follow token types listed
in the fetched GitHub docs snapshot (AWS, GitHub PAT, Slack, Stripe, Google
API key, npm, GitLab, Hugging Face, SendGrid, RSA private key).
"""
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS = HERE / "sources" / "github-supported-secret-scanning-patterns.md"

# Prefix/regex engines from documented token types. Independent of gitleaks.toml.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"\bAKIA[A-Z2-7]{16}\b")),
    ("github_personal_access_token", re.compile(r"\bghp_[0-9A-Za-z]{36}\b")),
    ("slack_api_token", re.compile(r"\bxoxb-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*")),
    ("stripe_api_key", re.compile(r"\b(?:sk|rk)_(?:test|live|prod)_[a-zA-Z0-9]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[\w-]{35}\b")),
    ("npm_access_token", re.compile(r"\bnpm_[0-9A-Za-z]{36}\b")),
    ("gitlab_access_token", re.compile(r"\bglpat-[\w-]{20}\b")),
    ("hf_user_access_token", re.compile(r"\bhf_[A-Za-z]{34}\b")),
    ("sendgrid_api_key", re.compile(r"\bSG\.[A-Za-z0-9=_\-.]{66}\b")),
    (
        "rsa_private_key",
        re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----"),
    ),
]


def docs_ok() -> bool:
    if not DOCS.is_file():
        return False
    text = DOCS.read_text(encoding="utf-8", errors="replace")
    return "Amazon AWS Access Key ID" in text and "GitHub Personal Access Token" in text


def scan_tree(root: Path) -> list[dict]:
    """Return hits as {relpath, rule_id} with no matched secret bytes."""
    root = Path(root)
    hits: list[dict] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in {".md", ".jsonl", ".txt", ".env", ".sh"}:
            continue
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for rule_id, pat in PATTERNS:
            if pat.search(text):
                hits.append({"relpath": rel, "rule_id": rule_id, "scanner": "github-docs-local"})
                break
    return hits
