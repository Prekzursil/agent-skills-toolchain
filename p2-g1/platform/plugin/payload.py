"""Payload selection: deny-by-default allowlist, forbidden-content scan, secret gate, inventory.

This is the module that answers the spec's one explicit prohibition — *never ship `.git`,
unrelated caches, logs, transcripts, credentials, or gigabytes of unrelated content*. It answers
it structurally rather than by hoping:

* **Deny by default.** Nothing is included unless an allowlist rule names it. An exclude list
  alone is unsound: the first unlisted junk directory ships.
* **Forbidden classes are still checked after selection.** Two independent instruments must agree
  before a package is emitted — the allowlist (which decides) and the forbidden scanner (which
  refutes). A file that passes the allowlist but matches a forbidden class is a **build failure**,
  not a warning, because it means the allowlist is wrong.
* **The secret gate denies by default.** It flags on shape (key headers, assignment of a
  high-entropy token, known credential filenames) and never prints a matched value.
* **Budgets are hard.** A package that is accidentally 2 GB fails even if every command works.
"""

from __future__ import annotations

import fnmatch
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginError
from .fsops import content_hash, iter_files, normalised_size, relposix

#: Path classes that must never appear in a package, checked independently of the allowlist.
FORBIDDEN_CLASSES: dict[str, tuple[str, ...]] = {
    "vcs": (".git/*", ".git", "*/.git/*", ".gitmodules", ".hg/*", ".svn/*"),
    "cache": (
        "__pycache__/*",
        "*/__pycache__/*",
        "*.pyc",
        ".pytest_cache/*",
        "*/.pytest_cache/*",
        ".ruff_cache/*",
        "*/.ruff_cache/*",
        "node_modules/*",
        "*/node_modules/*",
        ".venv/*",
        "*/.venv/*",
        "*.egg-info/*",
    ),
    "log": ("*.log", "*/logs/*", "logs/*", "*.log.*"),
    "transcript": (
        "*.jsonl",
        "*/projects/*/*.jsonl",
        "*transcript*",
        "*/sessions/*",
        "*/.claude/history*",
    ),
    "credential": (
        ".env",
        ".env.*",
        "*/.env",
        "*.pem",
        "*.key",
        "*.pfx",
        "*.p12",
        "id_rsa*",
        "id_ed25519*",
        "*credentials*.json",
        "*.credentials*",
        "auth.json",
        "*token*.json",
        ".npmrc",
        ".netrc",
    ),
    "backup": ("*.bak", "*.bak-*", "*.orig", "*.baseline", "*Zone.Identifier"),
    "archive": ("*.zip", "*.tar", "*.tar.gz", "*.tgz", "*.7z", "*.vhdx", "*.iso"),
}

#: Credential-shaped content. Deny by default: an allowlist redactor leaked 8 real values in an
#: earlier phase of this program, so these rules describe SHAPES, not a list of known secrets.
SECRET_RULES: tuple[tuple[str, str], ...] = (
    ("private_key_header", r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    ("aws_access_key_id", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("github_token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("slack_token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("openai_key", r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    ("anthropic_key", r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ("hf_token", r"\bhf_[A-Za-z0-9]{30,}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    (
        "assigned_secret",
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_=-]{16,}",
    ),
)

_SECRET_RES = tuple((name, re.compile(pat)) for name, pat in SECRET_RULES)

#: THERE IS NO EXEMPTION LIST. An earlier revision carried a ``DOCUMENTED_PATTERN_FILES`` set that
#: downgraded findings in the scanner's own rule file to a `documented` severity. Measured: the set
#: named ``lib/payload.py`` while the shipped path is ``lib/astplugin/payload.py``, so it never
#: matched anything — an untested widening of a security gate, which is worse than no widening. It
#: is removed. If a shipped file ever trips the gate, the build fails loudly and the owner decides;
#: that is the correct behaviour for a publish gate.
HIGH_ENTROPY_MIN_LEN = 32
HIGH_ENTROPY_BITS = 4.0

#: An all-lowercase kebab/snake/slash token is an identifier (a schema filename, a URL path
#: segment), not a credential: real tokens carry mixed case, digits, or base64 punctuation
#: (`+`, `=`). MEASURED: the 14 advisory findings on this package were all of the form
#: `tools/plugin/schema/drift-classification` and `dev/ast-integrate/schema/compatibility`.
#: Suppressing ONLY this shape removes them without weakening the mixed-case/base64 path, which
#: `test_package.py` proves still fires.
IDENTIFIER_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_/-]*$")


def shannon_bits(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


@dataclass(frozen=True)
class AllowRule:
    """One deny-by-default include rule. ``glob`` is matched against the payload-relative path."""

    glob: str
    reason: str

    def matches(self, rel: str) -> bool:
        return fnmatch.fnmatch(rel, self.glob)


@dataclass
class SecretFinding:
    relpath: str
    rule: str
    line: int
    severity: str  # "blocking" (fails the build) | "advisory" (recorded only)
    excerpt_shape: str  # a SHAPE description, never the value

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.relpath,
            "rule": self.rule,
            "line": self.line,
            "severity": self.severity,
            "excerpt_shape": self.excerpt_shape,
        }


@dataclass
class PayloadEntry:
    relpath: str
    size: int
    sha256: str
    rule: str

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.relpath,
            "size": self.size,
            "sha256": self.sha256,
            "rule": self.rule,
        }


@dataclass
class Payload:
    root: Path
    entries: list[PayloadEntry] = field(default_factory=list)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    findings: list[SecretFinding] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(e.size for e in self.entries)

    @property
    def file_count(self) -> int:
        return len(self.entries)

    def inventory(self, *, name: str, version: str) -> dict[str, object]:
        """The payload-inventory artifact (tools/plugin/schema/payload-inventory.schema.json)."""
        return {
            "artifact": "payload-inventory",
            "plugin": name,
            "version": version,
            "total_bytes": self.total_bytes,
            "file_count": self.file_count,
            "entries": [e.as_dict() for e in self.entries],
            "forbidden_classes_checked": sorted(FORBIDDEN_CLASSES),
            "forbidden_matches": [],
        }


def allowlist_document(
    rules: list[AllowRule], *, budget_bytes: int, budget_files: int
) -> dict[str, object]:
    """The allowlist artifact (tools/plugin/schema/payload-allowlist.schema.json)."""
    return {
        "artifact": "payload-allowlist",
        "policy": "deny-by-default",
        "rules": [{"glob": r.glob, "reason": r.reason} for r in rules],
        "budget": {"max_bytes": budget_bytes, "max_files": budget_files},
        "forbidden_classes": {k: list(v) for k, v in sorted(FORBIDDEN_CLASSES.items())},
    }


def classify_forbidden(rel: str) -> str | None:
    """Return the forbidden class a path belongs to, or None. The independent refuting probe."""
    unified = rel.replace("\\", "/")
    for klass, globs in FORBIDDEN_CLASSES.items():
        for g in globs:
            if fnmatch.fnmatch(unified, g) or fnmatch.fnmatch(
                "/" + unified, "*/" + g.lstrip("*/")
            ):
                return klass
        # a path segment equal to a bare dir name (".git", "__pycache__") anywhere in the path
        for g in globs:
            bare = g.rstrip("/*").lstrip("*/")
            if bare and "*" not in bare and bare in unified.split("/"):
                return klass
    return None


def scan_secrets(path: Path, rel: str) -> list[SecretFinding]:
    """Shape-based secret scan. Records rule + line + a shape description; never the value."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PluginError(
            "E_IO", f"cannot read {path} for the secret gate: {exc}"
        ) from exc
    if b"\x00" in data[:8192]:
        return []
    text = data.decode("utf-8", errors="replace")
    out: list[SecretFinding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(line) > 4096:
            line = line[:4096]
        for name, rx in _SECRET_RES:
            m = rx.search(line)
            if not m:
                continue
            matched = m.group(0)
            out.append(
                SecretFinding(
                    relpath=rel,
                    rule=name,
                    line=lineno,
                    severity="blocking",
                    excerpt_shape=f"len={len(matched)} entropy={shannon_bits(matched):.2f}bits",
                )
            )
        for token in re.findall(r"[A-Za-z0-9+/=_-]{%d,}" % HIGH_ENTROPY_MIN_LEN, line):
            if IDENTIFIER_TOKEN.match(token):
                continue
            if shannon_bits(
                token
            ) >= HIGH_ENTROPY_BITS and not _looks_like_hash_literal(line):
                out.append(
                    SecretFinding(
                        relpath=rel,
                        rule="high_entropy_token",
                        line=lineno,
                        severity="advisory",
                        excerpt_shape=f"len={len(token)} entropy={shannon_bits(token):.2f}bits",
                    )
                )
                break
    return out


def _looks_like_hash_literal(line: str) -> bool:
    """sha256 digests and base64 test vectors are high-entropy but not credentials."""
    return bool(
        re.search(r"(?i)\b(sha256|sha1|md5|digest|hash|checksum|blob|revision)\b", line)
    )


def collect(
    root: Path,
    rules: list[AllowRule],
    *,
    budget_bytes: int,
    budget_files: int,
    enforce_secrets: bool = True,
) -> Payload:
    """Walk ``root``, select by allowlist, refute by forbidden class, gate on secrets, budget."""
    payload = Payload(root=root)
    for abspath in iter_files(root):
        rel = relposix(root, abspath)
        rule = next((r for r in rules if r.matches(rel)), None)
        if rule is None:
            payload.rejected.append((rel, "not matched by any allowlist rule"))
            continue
        klass = classify_forbidden(rel)
        if klass is not None:
            raise PluginError(
                "E_PAYLOAD",
                f"allowlist selected {rel!r} but it is forbidden content (class {klass!r}); "
                "the allowlist rule is wrong",
                context={"rule": rule.glob, "forbidden_class": klass},
            )
        # normalised_size, NOT st_size: the inventory must describe the bytes that SHIP, so a
        # CRLF checkout and an LF checkout of the same content produce the same inventory.
        payload.entries.append(
            PayloadEntry(
                rel, normalised_size(abspath), content_hash(abspath), rule.glob
            )
        )
        payload.findings.extend(scan_secrets(abspath, rel))

    payload.entries.sort(key=lambda e: e.relpath)

    blocking = [f for f in payload.findings if f.severity == "blocking"]
    if enforce_secrets and blocking:
        raise PluginError(
            "E_SECRET",
            f"{len(blocking)} credential-shaped finding(s) in the payload; nothing was packaged",
            context={
                "first": f"{blocking[0].relpath}:{blocking[0].line} rule={blocking[0].rule}",
                "rules_hit": ", ".join(sorted({f.rule for f in blocking})),
            },
        )
    if budget_files and payload.file_count > budget_files:
        raise PluginError(
            "E_BUDGET",
            f"payload has {payload.file_count} files, budget is {budget_files}",
            context={"over_by": payload.file_count - budget_files},
        )
    if budget_bytes and payload.total_bytes > budget_bytes:
        raise PluginError(
            "E_BUDGET",
            f"payload is {payload.total_bytes} bytes, budget is {budget_bytes}",
            context={"over_by": payload.total_bytes - budget_bytes},
        )
    return payload


def secret_findings_document(payload: Payload) -> dict[str, object]:
    """The secret-finding artifact (tools/plugin/schema/secret-finding.schema.json)."""
    return {
        "artifact": "secret-finding",
        "scanned_files": payload.file_count,
        "blocking": sum(1 for f in payload.findings if f.severity == "blocking"),
        "findings": [f.as_dict() for f in payload.findings],
    }


def inventory_diff(
    previous: dict[str, object], current: dict[str, object]
) -> dict[str, object]:
    """Release-to-release inventory diff (IMP-0005): what was added, removed, changed, and by how much."""
    prev = {e["path"]: e for e in previous.get("entries", [])}  # type: ignore[union-attr]
    cur = {e["path"]: e for e in current.get("entries", [])}  # type: ignore[union-attr]
    added = sorted(set(cur) - set(prev))
    removed = sorted(set(prev) - set(cur))
    changed = sorted(
        p for p in set(cur) & set(prev) if cur[p]["sha256"] != prev[p]["sha256"]
    )
    return {
        "artifact": "payload-inventory-diff",
        "added": added,
        "removed": removed,
        "changed": changed,
        "bytes_before": int(previous.get("total_bytes", 0)),  # type: ignore[arg-type]
        "bytes_after": int(current.get("total_bytes", 0)),  # type: ignore[arg-type]
        "files_before": int(previous.get("file_count", 0)),  # type: ignore[arg-type]
        "files_after": int(current.get("file_count", 0)),  # type: ignore[arg-type]
    }
