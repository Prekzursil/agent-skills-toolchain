#!/usr/bin/env python3
"""IMP-0458 secret-scrub gate: detect and REPORT only.

Scans receipts, events and packaged artifacts before they are registered.
A finding names the variable, the scope and the evidence (byte offset,
byte length, zero-entropy prefix). The gate never rotates, revokes,
unsets or rewrites a credential. The caller decides whether to register.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import tarfile
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

DEFAULT_INCLUDE = (
    "command-center/receipts/**",
    "command-center/events/**",
    "release/**",
    "staging/**",
    "dist/**",
    "**/staging/**",
)
DEFAULT_EXCLUDE = (
    "**/.git/**",
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/.venv/**",
    "**/probes/IMP-0458/**",
)
MAX_FILE_BYTES = 8 * 1024 * 1024
ARCHIVE_SUFFIXES = {".zip", ".whl", ".egg", ".jar", ".tar", ".tgz", ".gz"}

# Low-entropy family prefixes. Reporting these is allowed; the random body is not.
TOKEN_RULES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    (
        "github-pat-classic",
        re.compile(r"ghp_[A-Za-z0-9]{36}"),
        "GITHUB_TOKEN",
        "ghp_",
    ),
    (
        "github-oauth",
        re.compile(r"gho_[A-Za-z0-9]{36}"),
        "GITHUB_OAUTH_TOKEN",
        "gho_",
    ),
    (
        "github-fine-grained",
        re.compile(r"github_pat_[A-Za-z0-9_]{22,}"),
        "GITHUB_TOKEN",
        "github_pat_",
    ),
    (
        "aws-access-key-id",
        re.compile(r"AKIA[0-9A-Z]{16}"),
        "AWS_ACCESS_KEY_ID",
        "AKIA",
    ),
    (
        "anthropic-api-key",
        re.compile(r"sk-ant-[A-Za-z0-9\-_]{24,}"),
        "ANTHROPIC_API_KEY",
        "sk-ant-",
    ),
    (
        "slack-bot-token",
        re.compile(r"xoxb-[0-9]{8,}-[0-9A-Za-z-]{16,}"),
        "SLACK_BOT_TOKEN",
        "xoxb-",
    ),
)

PEM_PRIVATE_RE = re.compile(
    rb"-----BEGIN (?P<kind>[A-Z0-9 ]*PRIVATE KEY)-----"
)

SECRET_ASSIGN_NAMES = (
    "AWS_SECRET_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "CURSOR_API_KEY",
    "API_KEY",
    "SECRET_KEY",
    "PRIVATE_KEY",
    "DATABASE_PASSWORD",
    "DB_PASSWORD",
    "NPM_TOKEN",
    "HF_TOKEN",
)
ASSIGN_RE = re.compile(
    r"(?P<var>"
    + "|".join(re.escape(n) for n in SECRET_ASSIGN_NAMES)
    + r""")\s*[=:]\s*(?P<q>['"]?)(?P<val>[^\s'"]{8,})(?P=q)?""",
    re.IGNORECASE,
)
PLACEHOLDER_RE = re.compile(
    r"""^(
        \$\{?[A-Z0-9_]+\}?
        |%[A-Z0-9_]+%
        |<.*>
        |\{\{.*\}\}
        |your[_-].*
        |xxx+
        |x{8,}
        |redacted
        |placeholder
        |changeme
        |example
        |dummy
        |sample
        |todo
        |none
        |null
        |true
        |false
        |process\.env\..*
    )$""",
    re.IGNORECASE | re.VERBOSE,
)
HASH_ONLY_RE = re.compile(r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{40}$|^[0-9a-fA-F]{64}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class Finding:
    variable: str
    scope: str
    byte_offset: int
    byte_length: int
    prefix: str
    rule: str
    evidence: str


@dataclass
class ScanReport:
    files_examined: int = 0
    bytes_examined: int = 0
    archives_opened: int = 0
    findings: list[Finding] = field(default_factory=list)
    opened_paths: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    mutated: bool = False
    mode: str = "report-only"

    def to_json(self) -> dict[str, Any]:
        d = asdict(self)
        d["finding_count"] = len(self.findings)
        return d


def synthetic_canary_value(nonce: bytes = b"IMP-0458") -> str:
    """Deterministic synthetic GitHub-shaped token. Not a live credential."""
    body = hashlib.sha256(nonce + b"/synthetic-canary-not-a-credential").hexdigest()[:36]
    return "ghp_" + body


def shannon(text: str) -> float:
    if not text:
        return 0.0
    n = len(text)
    counts = Counter(text)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _placeholder(value: str) -> bool:
    v = value.strip().strip("'\"")
    if not v or len(v) < 8:
        return True
    if PLACEHOLDER_RE.match(v):
        return True
    if HASH_ONLY_RE.match(v) or UUID_RE.match(v):
        return True
    if v.upper() in {n.upper() for n in SECRET_ASSIGN_NAMES}:
        return True
    return False


def _add(
    findings: list[Finding],
    *,
    variable: str,
    scope: str,
    offset: int,
    length: int,
    prefix: str,
    rule: str,
) -> None:
    key = (variable, scope, offset, rule)
    if any((f.variable, f.scope, f.byte_offset, f.rule) == key for f in findings):
        return
    findings.append(
        Finding(
            variable=variable,
            scope=scope,
            byte_offset=offset,
            byte_length=length,
            prefix=prefix,
            rule=rule,
            evidence=(
                f"variable={variable} scope={scope} offset={offset} "
                f"bytes={length} prefix={prefix} rule={rule}"
            ),
        )
    )


def scan_bytes(data: bytes, scope: str) -> list[Finding]:
    """Scan raw bytes. Never returns a secret body, only a zero-entropy prefix."""
    findings: list[Finding] = []
    for m in PEM_PRIVATE_RE.finditer(data):
        kind = m.group("kind").decode("ascii", errors="replace")
        _add(
            findings,
            variable="PRIVATE_KEY",
            scope=scope,
            offset=m.start(),
            length=len(m.group(0)),
            prefix="-----BEGIN",
            rule=f"pem-{kind.lower().replace(' ', '-')}",
        )
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
    for rule, cre, variable, prefix in TOKEN_RULES:
        for m in cre.finditer(text):
            _add(
                findings,
                variable=variable,
                scope=scope,
                offset=m.start(),
                length=len(m.group(0)),
                prefix=prefix,
                rule=rule,
            )
    for m in ASSIGN_RE.finditer(text):
        var = m.group("var").upper()
        val = m.group("val")
        if _placeholder(val):
            continue
        already = any(
            f.scope == scope
            and f.byte_offset <= m.start(0) < f.byte_offset + f.byte_length
            for f in findings
        )
        if already:
            continue
        if len(val) < 20 or shannon(val) < 3.5:
            continue
        _add(
            findings,
            variable=var,
            scope=scope,
            offset=m.start(),
            length=len(m.group(0)),
            prefix="",
            rule="secret-named-assignment",
        )
    return findings


def _is_excluded(rel: str, exclude: Iterable[str]) -> bool:
    posix = rel.replace("\\", "/")
    for pat in exclude:
        if fnmatch(posix, pat) or fnmatch(posix, pat.rstrip("/")):
            return True
        parts = posix.split("/")
        for i in range(len(parts)):
            if fnmatch("/".join(parts[: i + 1]), pat.rstrip("/**")):
                return True
    return False


def _is_included(rel: str, include: Iterable[str]) -> bool:
    posix = rel.replace("\\", "/")
    patterns = list(include)
    if not patterns:
        return True
    for pat in patterns:
        if pat in {"*", "**", "**/*", "**/**"}:
            return True
        if fnmatch(posix, pat) or fnmatch(posix.split("/")[-1], pat):
            return True
        if pat.endswith("/**") and (
            posix == pat[:-3].rstrip("/") or posix.startswith(pat[:-3] + "/")
        ):
            return True
    return False


def _archive_kind(path: Path) -> str | None:
    name = path.name.lower()
    if zipfile.is_zipfile(path):
        return "zip"
    if name.endswith(".tar") or name.endswith(".tar.gz") or name.endswith(".tgz"):
        if tarfile.is_tarfile(path):
            return "tar"
    return None


def _scan_archive(path: Path, scope: str, report: ScanReport) -> None:
    kind = _archive_kind(path)
    if kind is None:
        return
    report.archives_opened += 1
    try:
        if kind == "zip":
            with zipfile.ZipFile(path, "r") as zf:
                for info in zf.infolist():
                    if info.filename.endswith("/") or info.file_size > MAX_FILE_BYTES:
                        continue
                    payload = zf.read(info.filename)
                    report.bytes_examined += len(payload)
                    member = f"{scope}::{info.filename.replace(chr(92), '/')}"
                    report.findings.extend(scan_bytes(payload, member))
        else:
            with tarfile.open(path, "r:*") as tf:
                for member in tf.getmembers():
                    if not member.isfile() or member.size > MAX_FILE_BYTES:
                        continue
                    extracted = tf.extractfile(member)
                    if extracted is None:
                        continue
                    payload = extracted.read(MAX_FILE_BYTES + 1)
                    report.bytes_examined += len(payload)
                    inner = f"{scope}::{member.name.replace(chr(92), '/')}"
                    report.findings.extend(scan_bytes(payload, inner))
    except (OSError, zipfile.BadZipFile, tarfile.TarError) as exc:
        report.skipped.append(f"{scope}:archive-error:{type(exc).__name__}")


def scan_file(path: Path, scope: str | None = None) -> list[Finding]:
    rel = scope or str(path)
    if not path.is_file():
        return []
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        return []
    data = path.read_bytes()
    findings = scan_bytes(data, rel)
    if _archive_kind(path) is not None:
        tmp = ScanReport()
        _scan_archive(path, rel, tmp)
        findings.extend(tmp.findings)
    return findings


def scan_before_register(path: Path | str) -> ScanReport:
    """Pre-registration hook. Report only. Does not register or mutate."""
    p = Path(path)
    report = ScanReport(roots=[str(p)], mode="report-only", mutated=False)
    if not p.is_file():
        report.skipped.append(f"{p}:not-a-file")
        return report
    report.files_examined = 1
    report.opened_paths.append(str(p))
    try:
        size = p.stat().st_size
    except OSError as exc:
        report.skipped.append(f"{p}:{type(exc).__name__}")
        return report
    if size > MAX_FILE_BYTES:
        report.skipped.append(f"{p}:too-large")
        return report
    data = p.read_bytes()
    report.bytes_examined += len(data)
    scope = str(p)
    report.findings.extend(scan_bytes(data, scope))
    if _archive_kind(p) is not None:
        _scan_archive(p, scope, report)
    return report


def scan_tree(
    root: Path | str,
    *,
    include: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
    relative_to: Path | None = None,
) -> ScanReport:
    root_p = Path(root)
    report = ScanReport(roots=[str(root_p)], mode="report-only", mutated=False)
    if not root_p.exists():
        report.skipped.append(f"{root_p}:absent")
        return report
    inc = tuple(include) if include is not None else ("**/*",)
    exc = tuple(exclude) if exclude is not None else DEFAULT_EXCLUDE
    base = relative_to or root_p
    files: list[Path]
    if root_p.is_file():
        files = [root_p]
    else:
        files = sorted(p for p in root_p.rglob("*") if p.is_file())
    for path in files:
        try:
            rel = path.relative_to(base).as_posix()
        except ValueError:
            rel = path.as_posix()
        if _is_excluded(rel, exc):
            report.skipped.append(rel)
            continue
        if not _is_included(rel, inc) and include is not None:
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            report.skipped.append(f"{rel}:too-large")
            continue
        report.files_examined += 1
        report.opened_paths.append(rel)
        data = path.read_bytes()
        report.bytes_examined += len(data)
        report.findings.extend(scan_bytes(data, rel))
        if _archive_kind(path) is not None:
            _scan_archive(path, rel, report)
    return report


def scan_corpus(repo: Path | None = None) -> ScanReport:
    """Scan the catalog input trees: receipts, events, release staging."""
    base = repo or REPO
    merged = ScanReport(mode="report-only", mutated=False)
    roots = [
        base / "command-center" / "receipts",
        base / "command-center" / "events",
        base / "release",
        base / "staging",
        base / "dist",
        base / "command-center" / "release",
    ]
    for root in roots:
        try:
            merged.roots.append(root.relative_to(base).as_posix())
        except ValueError:
            merged.roots.append(str(root))
        part = scan_tree(root, include=("**/*",), exclude=DEFAULT_EXCLUDE, relative_to=base)
        merged.files_examined += part.files_examined
        merged.bytes_examined += part.bytes_examined
        merged.archives_opened += part.archives_opened
        merged.findings.extend(part.findings)
        merged.opened_paths.extend(part.opened_paths)
        merged.skipped.extend(part.skipped)
    return merged


WRITE_METHODS = frozenset(
    {
        "write_text",
        "write_bytes",
        "write",
        "unlink",
        "replace",
        "rename",
        "chmod",
        "putenv",
        "unsetenv",
        "unset",
        "rotate",
        "revoke",
        "delete_secret",
        "put_secret",
        "update_secret",
        "clear",
        "pop",
        "__setitem__",
        "__delitem__",
    }
)
ENV_MUTATORS = frozenset({"putenv", "unsetenv", "pop", "clear", "__setitem__", "__delitem__"})


def report_only_violations(source: str) -> list[str]:
    """Read the gate source. Any credential-mutating or write path is a violation.

    This is a source-read check, not a rotation test: it never attempts to
    rotate, revoke or unset anything.
    """
    tree = ast.parse(source)
    hits: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
                if (
                    name in ENV_MUTATORS
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "environ"
                ):
                    hits.append(f"L{node.lineno}:os.environ.{name}()")
            if name in WRITE_METHODS and name not in {"pop", "clear", "replace"}:
                # pop/clear/replace on non-environ objects are ignored above;
                # Path.write_* / unlink / unsetenv are always violations.
                if name in {
                    "write",
                    "write_text",
                    "write_bytes",
                    "unlink",
                    "rename",
                    "chmod",
                    "putenv",
                    "unsetenv",
                    "rotate",
                    "revoke",
                    "delete_secret",
                    "put_secret",
                    "update_secret",
                }:
                    hits.append(f"L{node.lineno}:{name}()")
            if isinstance(func, ast.Name) and func.id == "open":
                for arg in node.args[1:2]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if any(ch in arg.value for ch in "wxa+"):
                            hits.append(f"L{node.lineno}:open(mode={arg.value!r})")
                for kw in node.keywords:
                    if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                        val = str(kw.value.value)
                        if any(ch in val for ch in "wxa+"):
                            hits.append(f"L{node.lineno}:open(mode={val!r})")
        if isinstance(node, ast.Attribute) and node.attr == "environ":
            parent_is_load = True
            # Mention of os.environ as a read (snapshot) is allowed; assignment is not.
            # Detected via Call handling above.
            _ = parent_is_load
    return hits


def report_contains_secret_body(text: str, bodies: Iterable[str]) -> list[str]:
    """Return any full secret values that leaked into a report. Prefix-only is allowed."""
    leaked: list[str] = []
    for body in bodies:
        if body and body in text:
            leaked.append("full-value-present")
    return leaked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMP-0458 report-only secret-scrub gate")
    parser.add_argument("--root", type=str, default="", help="Tree or file to scan")
    parser.add_argument("--repo", action="store_true", help="Scan default corpus roots")
    parser.add_argument("--fail-on-findings", action="store_true")
    parser.add_argument("--json", action="store_true", default=True)
    args = parser.parse_args(argv)
    if args.repo or not args.root:
        report = scan_corpus(REPO)
    else:
        report = scan_tree(Path(args.root), include=("**/*",), exclude=DEFAULT_EXCLUDE)
    payload = report.to_json()
    print(json.dumps(payload, indent=1, sort_keys=True))
    if args.fail_on_findings and report.findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
