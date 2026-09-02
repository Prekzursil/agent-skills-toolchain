"""Secret and PII scan over packaging-included files. Never prints values.

Reports class, path, line, byte offset, and a redacted snippet only.
"""
from __future__ import annotations

import re
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

from packaging import (  # noqa: E402
    SECRET_BASENAMES,
    SECRET_SUFFIXES,
    SKIP_SELF_ARTIFACT,
    include_census,
    prove_resolver,
)

# tools/plugin/secret_gate.py (IMP-0004) is absent on this Linux worktree
# (tools/plugin/ holds only schema/). Local detectors keep the same contract:
# class, path, line, and a redacted snippet — never a secret body.
ASSIGN_RE = re.compile(
    rb"(?i)(?:^|[\s,{\"'])"
    rb"([A-Za-z_][A-Za-z0-9_]{0,80}?(?:api[_-]?key|secret|token|password|passwd|"
    rb"credential|private[_-]?key|authorization|auth_token|access_key))"
    rb"\s*[:=]\s*[\"']?[A-Za-z0-9/+=_\-.]{16,}"
)
PEM_RE = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
)
_PREFIXES = (
    b"sk-ant-",
    b"sk-proj-",
    b"github_pat_",
    b"glpat-",
    b"ghp_",
    b"xoxb-",
    b"xoxp-",
    b"xoxa-",
    b"xoxs-",
    b"AKIA",
    b"sk-",
)


def _known_prefix(blob: bytes) -> str | None:
    for pref in _PREFIXES:
        if blob.startswith(pref):
            return pref.decode("ascii")
    return None


def is_secret_path(rel: str) -> bool:
    name = rel.replace("\\", "/").rsplit("/", 1)[-1].lower()
    if name in SECRET_BASENAMES or name.startswith(".env.") or "credential" in name:
        return True
    if name.endswith(SECRET_SUFFIXES):
        return True
    return False

HOME_WIN_S = re.compile(
    r"(?i)(?:C:[/\\]|/mnt/c/|/c/)Users[/\\]([^\s/\\\"']+)"
)
HOME_UNIX = re.compile(r"(?i)(?<![A-Za-z0-9_])/(?:home|Users)/([^\s/\\\"']+)")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
TOKEN_PREFIX = re.compile(
    rb"(?:AKIA[0-9A-Z]{8,}|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"
    rb"|sk-(?:proj-|ant-)?[A-Za-z0-9]{16,}|xox[bpsa]-[A-Za-z0-9-]{16,}"
    rb"|glpat-[A-Za-z0-9\-_]{16,})"
)

EXAMPLE_EMAIL_DOMAINS = frozenset(
    {"example.com", "example.org", "example.net", "invalid", "localhost", "test"}
)
MAX_HITS_PER_FILE = 40
MAX_FILE_BYTES = 8 * 1024 * 1024
TEXT_SUFFIXES = frozenset(
    {
        ".md",
        ".json",
        ".py",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".sh",
        ".ps1",
        ".js",
        ".ts",
        ".csv",
        ".xml",
        ".html",
        ".rst",
        ".ini",
        ".cfg",
        ".env",
        ".lock",
    }
)


def _is_text(path: Path, blob: bytes) -> bool:
    if b"\x00" in blob[:8192]:
        return False
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    try:
        blob[:4096].decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _redact_snippet(line: str) -> str:
    s = HOME_WIN_S.sub(r"C:/Users/<redacted>", line)
    s = HOME_UNIX.sub(lambda m: m.group(0).rsplit("/", 1)[0] + "/<redacted>", s)
    s = EMAIL_RE.sub("<redacted-email>", s)
    s = re.sub(r"AKIA[0-9A-Z]{8,}", "AKIA<redacted>", s)
    s = re.sub(r"ghp_[A-Za-z0-9]{8,}", "ghp_<redacted>", s)
    s = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "sk-<redacted>", s)
    s = re.sub(r"xox[bpsa]-[A-Za-z0-9-]{8,}", "xox-<redacted>", s)
    s = s.strip()
    if len(s) > 160:
        s = s[:157] + "..."
    return s


def _email_ok(addr: str) -> bool:
    domain = addr.rsplit("@", 1)[-1].lower()
    if domain in EXAMPLE_EMAIL_DOMAINS or domain.endswith(".example"):
        return False
    if "json-schema.org" in domain or domain.endswith(".local"):
        return False
    return True


def scan_file(path: Path, repo_rel: str) -> list[dict]:
    hits: list[dict] = []
    if is_secret_path(repo_rel):
        hits.append(
            {
                "class": "credential-path",
                "rule_id": "path-secret-file",
                "path": repo_rel,
                "line": 1,
                "byte_offset": 0,
                "severity": "P1",
                "snippet": "<credential-shaped-filename>",
            }
        )
    try:
        data = path.read_bytes()[:MAX_FILE_BYTES]
    except OSError:
        return hits
    if not _is_text(path, data):
        return hits
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")

    for match in PEM_RE.finditer(data):
        line = data[: match.start()].count(b"\n") + 1
        hits.append(
            {
                "class": "private-key",
                "rule_id": "pem-private-key",
                "path": repo_rel,
                "line": line,
                "byte_offset": match.start(),
                "severity": "P0",
                "snippet": "-----BEGIN <redacted> PRIVATE KEY-----",
            }
        )
    for match in TOKEN_PREFIX.finditer(data):
        line = data[: match.start()].count(b"\n") + 1
        pref = _known_prefix(match.group(0)[:24]) or match.group(0)[:4].decode(
            "ascii", errors="ignore"
        )
        hits.append(
            {
                "class": "credential-token",
                "rule_id": "known-token-prefix",
                "path": repo_rel,
                "line": line,
                "byte_offset": match.start(),
                "severity": "P0",
                "snippet": f"{pref}<redacted>",
            }
        )
    for match in ASSIGN_RE.finditer(data):
        name = match.group(1).decode("ascii", errors="replace")
        line = data[: match.start()].count(b"\n") + 1
        hits.append(
            {
                "class": "credential-assignment",
                "rule_id": "assignment-secret",
                "path": repo_rel,
                "line": line,
                "byte_offset": match.start(),
                    "severity": "P2",
                    "snippet": f"{name}=<redacted>",
            }
        )

    for i, line in enumerate(text.splitlines(), 1):
        if HOME_WIN_S.search(line) or HOME_UNIX.search(line):
            hits.append(
                {
                    "class": "owner-home-path",
                    "rule_id": "absolute-home-path",
                    "path": repo_rel,
                    "line": i,
                    "byte_offset": 0,
                    "severity": "P1",
                    "snippet": "C:/Users/<redacted>/... or /home/<redacted>/...",
                }
            )
        for addr in EMAIL_RE.findall(line):
            if _email_ok(addr):
                hits.append(
                    {
                        "class": "email",
                        "rule_id": "email-address",
                        "path": repo_rel,
                        "line": i,
                        "byte_offset": 0,
                        "severity": "P2",
                        "snippet": "<redacted-email> (surrounding prose withheld)",
                    }
                )
        if len(hits) >= MAX_HITS_PER_FILE:
            break
    return hits[:MAX_HITS_PER_FILE]


def prove_scanner() -> dict:
    """Both-states: fire on a planted home path; stay silent on example.com email."""
    with tempfile.TemporaryDirectory(prefix="aud0078-scan-") as tmp:
        root = Path(tmp)
        bad = root / "keep" / "owner.txt"
        good = root / "keep" / "docs.txt"
        bad.parent.mkdir(parents=True)
        bad.write_text(
            "notes at C:/Users/SomeOwner/.claude/harness-restore\n",
            encoding="utf-8",
        )
        good.write_text("contact admin@example.com for docs\n", encoding="utf-8")
        bad_hits = scan_file(bad, "keep/owner.txt")
        good_hits = scan_file(good, "keep/docs.txt")
        fired = any(h["class"] == "owner-home-path" for h in bad_hits)
        silent = not any(h["class"] == "email" for h in good_hits)
        return {
            "ok": fired and silent,
            "fired_on_home_path": fired,
            "silent_on_example_email": silent,
            "bad_classes": [h["class"] for h in bad_hits],
            "good_classes": [h["class"] for h in good_hits],
        }


def scan_included() -> dict:
    control = prove_resolver()
    scanner_control = prove_scanner()
    census = include_census()
    files = census["files"]
    findings: list[dict] = []
    scanned = 0
    skipped_binary = 0
    for row in files:
        path: Path = row["path"]
        rel = row["repo_rel"]
        scanned += 1
        try:
            head = path.read_bytes()[:64]
        except OSError:
            continue
        if b"\x00" in head and path.suffix.lower() not in {".md", ".json", ".py"}:
            skipped_binary += 1
            continue
        findings.extend(scan_file(path, rel))
    by_class = Counter(f["class"] for f in findings)
    by_path = Counter(f["path"] for f in findings)
    return {
        "control": control,
        "scanner_control": scanner_control,
        "plugin_scanners_present": {
            "forbidden_scan": (REPO / "tools/plugin/forbidden_scan.py").is_file(),
            "secret_gate": (REPO / "tools/plugin/secret_gate.py").is_file(),
        },
        "include": {
            "file_count": census["file_count"],
            "byte_count": census["byte_count"],
            "by_tree": census["by_tree"],
            "bytes_by_tree": census["bytes_by_tree"],
            "corpus_present": census["corpus_present"],
            "corpus_roots": census["corpus_roots"],
            "self_artifact_skipped": SKIP_SELF_ARTIFACT,
        },
        "scanned_files": scanned,
        "skipped_binary": skipped_binary,
        "finding_count": len(findings),
        "by_class": dict(by_class),
        "hottest_paths": by_path.most_common(20),
        "findings": findings,
        "never_prints_values": True,
    }
