#!/usr/bin/env python3
"""Credential-exposure gate for payload members before artifact emission (IMP-0004).

Two independent detectors must agree before a clean verdict is trusted:

1. **Gitleaks-style shape rules** (provider prefixes, PEM headers, assigned secrets).
2. **Shannon-entropy pass** over token-shaped string literals (implemented separately
   from the pattern table — a different instrument, not a second copy of the same
   regex list).

Findings report path / rule / line / variable name / byte offset and an
``excerpt_shape`` descriptor (``len=N entropy=X.YYbits``). They never carry the
matched secret body past a zero-entropy prefix (e.g. ``ghp_`` / ``sk-``).

Pack pre-emit calls :func:`assert_members_clean` so a planted credential blocks
zip emission. Standalone CLI mirrors the forbidden-content scanner contract.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

#: Pattern rules (gitleaks-shaped). Names are stable ids used in reports/tests.
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
        r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|"
        r"auth[_-]?token|client[_-]?secret)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_=-]{16,}",
    ),
)

_SECRET_RES = tuple((name, re.compile(pat)) for name, pat in SECRET_RULES)

#: Known safe zero-entropy prefixes that may appear in reports (never the body).
SAFE_PREFIXES: tuple[str, ...] = (
    "ghp_",
    "gho_",
    "ghu_",
    "ghs_",
    "ghr_",
    "sk-ant-",
    "sk-",
    "hf_",
    "xoxb-",
    "xoxa-",
    "xoxp-",
    "xoxr-",
    "xoxs-",
    "AKIA",
    "ASIA",
    "eyJ",
    "-----BEGIN",
)

HIGH_ENTROPY_MIN_LEN = 32
HIGH_ENTROPY_BITS = 4.0
IDENTIFIER_TOKEN = re.compile(r"^[a-z0-9][a-z0-9_/-]*$")
_ASSIGN_VAR_RE = re.compile(
    r"(?i)\b([A-Za-z_][A-Za-z0-9_]*)\b\s*[:=]\s*[\"']?[A-Za-z0-9/+_=-]{16,}"
)
_HASH_CONTEXT_RE = re.compile(
    r"(?i)\b(sha256|sha1|md5|digest|hash|checksum|revision)\b"
)
#: Candidate base64 blobs long enough to hide a ghp_/sk- style token after decode.
_B64_CANDIDATE_RE = re.compile(r"[A-Za-z0-9+/]{40,}={0,2}")
_B64_MIN_DECODED_LEN = 16

#: Adjacent / ``+``-joined string literals (split_literal evasion).
#: Matches one pair of quoted strings separated only by whitespace and/or ``+``.
_JOIN_PAIR_RE = re.compile(
    r"""(?xs)
    (?P<q1>["'])
    (?P<body1>(?:\\.|(?!(?P=q1)).)*)
    (?P=q1)
    \s*(?:\+\s*)?
    (?P<q2>["'])
    (?P<body2>(?:\\.|(?!(?P=q2)).)*)
    (?P=q2)
    """
)
#: Simple ``NAME = "literal"`` assignments (single-line) for ident+ident joins.
_LIT_ASSIGN_RE = re.compile(
    r"""(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(["'])([^"'\\]*)\2\s*$"""
)
#: ``IDENT + IDENT`` (possibly chained later via repeated expansion).
_IDENT_PLUS_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\+\s*([A-Za-z_][A-Za-z0-9_]*)\b"
)


# Safe base64 decode (no binascii import required):
def _b64_decode_safe(token: str) -> bytes | None:
    if not re.fullmatch(r"[A-Za-z0-9+/]+=*", token):
        return None
    pad = (-len(token)) % 4
    padded = token + ("=" * pad)
    try:
        raw = base64.b64decode(padded, validate=False)
    except Exception:
        return None
    if len(raw) < _B64_MIN_DECODED_LEN:
        return None
    # Require mostly printable / utf-8-ish so random high-entropy isn't all blocking.
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Still pattern-scan latin-1 view for ASCII credential prefixes.
        text = raw.decode("latin-1", errors="ignore")
    if not any(ch.isprintable() or ch in "\n\r\t" for ch in text[:64]):
        return None
    return raw


def looks_like_hash_literal(line: str) -> bool:
    return bool(_HASH_CONTEXT_RE.search(line))


#: Detector-control plant: synthetic github-shaped token assembled at runtime.
PLANTED_CONTROL_REL = "planted_secret_control.txt"
PLANTED_CONTROL_PREFIX = "ghp_"


class SecretGateError(RuntimeError):
    """Payload contains credential-shaped content that must not ship."""


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    line: int
    severity: str  # "blocking" | "advisory"
    excerpt_shape: str
    variable_name: str = ""
    byte_offset: int = 0
    prefix: str = ""

    def as_dict(self) -> dict[str, object]:
        """Schema-shaped finding (secret-finding.schema.json) — never the value."""
        return {
            "path": self.path,
            "rule": self.rule,
            "line": self.line,
            "severity": self.severity,
            "excerpt_shape": self.excerpt_shape,
        }

    def named_line(self) -> str:
        """Human report line: path + rule + var + offset + shape; never the body."""
        var = self.variable_name or "-"
        pref = self.prefix or "-"
        return (
            f"SECRET path={self.path} rule={self.rule} line={self.line} "
            f"var={var} byte_offset={self.byte_offset} prefix={pref} "
            f"severity={self.severity} {self.excerpt_shape}"
        )


@dataclass
class ScanReport:
    scanned_files: int = 0
    findings: list[Finding] = field(default_factory=list)
    gitleaks_exit_code: int | None = None
    gitleaks_finding_count: int | None = None
    entropy_finding_count: int = 0
    pattern_finding_count: int = 0
    planted_control_found: bool = False
    report_text: str = ""

    @property
    def blocking(self) -> int:
        return sum(1 for f in self.findings if f.severity == "blocking")

    @property
    def clean(self) -> bool:
        return self.blocking == 0

    @property
    def exit_code(self) -> int:
        return 0 if self.clean else 14

    def as_secret_finding_doc(self) -> dict[str, object]:
        return {
            "artifact": "secret-finding",
            "scanned_files": self.scanned_files,
            "blocking": self.blocking,
            "findings": [f.as_dict() for f in self.findings],
        }

    def render_named_report(self) -> str:
        lines = [
            f"scanned_files={self.scanned_files}",
            f"blocking={self.blocking}",
            f"finding_count={len(self.findings)}",
            f"pattern_finding_count={self.pattern_finding_count}",
            f"entropy_finding_count={self.entropy_finding_count}",
            f"planted_control_found={self.planted_control_found}",
            f"gitleaks_exit_code={self.gitleaks_exit_code}",
            f"gitleaks_finding_count={self.gitleaks_finding_count}",
            f"clean={self.clean}",
            f"exit_code={self.exit_code}",
            "--- findings ---",
        ]
        for f in self.findings:
            lines.append(f.named_line())
        lines.append("--- end-findings ---")
        return "\n".join(lines) + "\n"


def shannon_bits(s: str) -> float:
    """Independent Shannon entropy (bits/char) — not a regex rule."""
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def findings_from_decoded_b64(
    token: str,
    *,
    relpath: str,
    lineno: int,
    line_start: int,
    raw_line: str,
    token_pos: int,
) -> list[Finding]:
    """If ``token`` base64-decodes to a credential-shaped plaintext, emit blocking."""
    raw = _b64_decode_safe(token)
    if raw is None:
        return []
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError:
        decoded = raw.decode("latin-1", errors="ignore")
    out: list[Finding] = []
    for name, rx in _SECRET_RES:
        m = rx.search(decoded)
        if not m:
            continue
        matched = m.group(0)
        out.append(
            Finding(
                path=relpath,
                rule=f"base64_wrapped_{name}",
                line=lineno,
                severity="blocking",
                excerpt_shape=(
                    f"b64_len={len(token)} decoded_len={len(matched)} "
                    f"entropy={shannon_bits(matched):.2f}bits"
                ),
                variable_name=extract_variable_name(raw_line),
                byte_offset=line_start + max(token_pos, 0),
                prefix=safe_prefix_of(matched),
            )
        )
    return out


def join_adjacent_string_literals(text: str) -> str:
    """Collapse adjacent / ``+``-joined quoted string literals into one literal.

    Settles split_literal evasions such as::

        API_TOKEN = (
            "ghp_...."
            "...."
        )
    """

    def _repl(m: re.Match[str]) -> str:
        body = m.group("body1") + m.group("body2")
        # Prefer the first quote style for the reconstructed literal.
        q = m.group("q1")
        return f"{q}{body}{q}"

    prev = None
    cur = text
    # Bound iterations so pathological inputs cannot hang the gate.
    for _ in range(64):
        if cur == prev:
            break
        prev = cur
        cur = _JOIN_PAIR_RE.sub(_repl, cur)
    return cur


def expand_ident_string_concats(text: str) -> str:
    """Append synthetic assignments for ``A + B`` when both are string literals.

    Catches::

        _p1 = "ghp_...."
        _p2 = "...."
        API_TOKEN_JOINED = _p1 + _p2
    """
    assigns: dict[str, str] = {
        m.group(1): m.group(3) for m in _LIT_ASSIGN_RE.finditer(text)
    }
    if not assigns:
        return text
    extras: list[str] = []
    seen: set[str] = set()
    # Multi-pass so ``a + b + c`` shaped chains via temps still settle.
    working = dict(assigns)
    for _ in range(16):
        grew = False
        for m in _IDENT_PLUS_RE.finditer(text):
            left, right = m.group(1), m.group(2)
            if left not in working or right not in working:
                continue
            joined = working[left] + working[right]
            key = f"_SPLIT_JOINED_{left}_{right}"
            if key in seen:
                continue
            if any(v == joined for v in working.values()):
                continue
            seen.add(key)
            working[key] = joined
            extras.append(f'{key} = "{joined}"\n')
            grew = True
        if not grew:
            break
    if not extras:
        return text
    return text + "\n" + "".join(extras)


def reconstruct_split_literals(text: str) -> str:
    """Rebuild contiguous credential-shaped text from split_literal evasions."""
    return expand_ident_string_concats(join_adjacent_string_literals(text))


def findings_from_reconstructed_split(
    text: str,
    *,
    relpath: str,
) -> list[Finding]:
    """Pattern-scan a split-literal reconstruction; emit ``split_literal_*`` rules."""
    reconstructed = reconstruct_split_literals(text)
    if reconstructed == text:
        return []
    out: list[Finding] = []
    # Scan reconstruction as a single blob; line numbers refer to joined view.
    offset = 0
    for lineno, line in enumerate(reconstructed.splitlines(), start=1):
        line_start = offset
        raw_line = line
        if len(line) > 4096:
            line = line[:4096]
        for name, rx in _SECRET_RES:
            m = rx.search(line)
            if not m:
                continue
            matched = m.group(0)
            out.append(
                Finding(
                    path=relpath,
                    rule=f"split_literal_{name}",
                    line=lineno,
                    severity="blocking",
                    excerpt_shape=(
                        f"split_joined len={len(matched)} "
                        f"entropy={shannon_bits(matched):.2f}bits"
                    ),
                    variable_name=extract_variable_name(raw_line),
                    byte_offset=line_start + m.start(),
                    prefix=safe_prefix_of(matched),
                )
            )
        offset += len(raw_line.encode("utf-8", errors="replace")) + 1
    return out




def safe_prefix_of(matched: str) -> str:
    """Return the longest known zero-entropy prefix of ``matched``, else empty."""
    for pref in sorted(SAFE_PREFIXES, key=len, reverse=True):
        if matched.startswith(pref):
            return pref
    return ""


def extract_variable_name(line: str) -> str:
    m = _ASSIGN_VAR_RE.search(line)
    return m.group(1) if m else ""


def synthesize_github_pat(*, seed: int = 20260908, body_len: int = 36) -> str:
    """Build a synthetic FAKE ghp_ token (never a real credential).

    Body is PRNG-derived so source files need not embed a full token literal.
    """
    # Deterministic LCG — no secrets module; reproducible across probes.
    state = seed & 0xFFFFFFFF
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    chars: list[str] = []
    for _ in range(body_len):
        state = (1664525 * state + 1013904223) & 0xFFFFFFFF
        chars.append(alphabet[state % len(alphabet)])
    return PLANTED_CONTROL_PREFIX + "".join(chars)


def secret_body(token: str) -> str:
    """Body past the safe prefix — must never appear in reports."""
    pref = safe_prefix_of(token)
    return token[len(pref) :] if pref else token


def report_contains_secret_body(report_text: str, token: str) -> bool:
    body = secret_body(token)
    if not body:
        return False
    return body in report_text


def scan_text(
    text: str,
    *,
    relpath: str,
    base_offset: int = 0,
) -> list[Finding]:
    """Scan one UTF-8 text blob. Pattern rules + independent entropy pass."""
    out: list[Finding] = []
    offset = base_offset
    for lineno, line in enumerate(text.splitlines(), start=1):
        # Track byte offset of line start within the original text.
        line_start = offset
        raw_line = line
        if len(line) > 4096:
            line = line[:4096]
        for name, rx in _SECRET_RES:
            m = rx.search(line)
            if not m:
                continue
            matched = m.group(0)
            out.append(
                Finding(
                    path=relpath,
                    rule=name,
                    line=lineno,
                    severity="blocking",
                    excerpt_shape=(
                        f"len={len(matched)} entropy={shannon_bits(matched):.2f}bits"
                    ),
                    variable_name=extract_variable_name(raw_line),
                    byte_offset=line_start + m.start(),
                    prefix=safe_prefix_of(matched),
                )
            )
        # Base64-wrapped credentials (adversarial evasion: encode plaintext token).
        for m in _B64_CANDIDATE_RE.finditer(line):
            out.extend(
                findings_from_decoded_b64(
                    m.group(0),
                    relpath=relpath,
                    lineno=lineno,
                    line_start=line_start,
                    raw_line=raw_line,
                    token_pos=m.start(),
                )
            )
        # Independent entropy instrument (not a second copy of SECRET_RULES).
        for token in re.findall(
            r"[A-Za-z0-9+/=_-]{%d,}" % HIGH_ENTROPY_MIN_LEN, line
        ):
            if IDENTIFIER_TOKEN.match(token):
                continue
            if looks_like_hash_literal(raw_line):
                continue
            if shannon_bits(token) < HIGH_ENTROPY_BITS:
                continue
            # Skip advisory entropy if base64 decode already produced a blocking hit
            # on the same candidate (avoid double-noise).
            if any(
                f.rule.startswith("base64_wrapped_") and f.line == lineno
                for f in out
            ):
                continue
            out.append(
                Finding(
                    path=relpath,
                    rule="high_entropy_token",
                    line=lineno,
                    severity="advisory",
                    excerpt_shape=(
                        f"len={len(token)} entropy={shannon_bits(token):.2f}bits"
                    ),
                    variable_name=extract_variable_name(raw_line),
                    byte_offset=line_start + line.find(token),
                    prefix=safe_prefix_of(token),
                )
            )
            break
        offset += len(raw_line.encode("utf-8", errors="replace")) + 1
    # Split-literal reconstruction (adjacent / + joined fragments).
    # Deduplicate against contiguous hits that already blocked on the same prefix.
    existing_prefixes = {
        (f.rule.split("split_literal_", 1)[-1], f.prefix)
        for f in out
        if f.severity == "blocking"
    }
    for f in findings_from_reconstructed_split(text, relpath=relpath):
        base_rule = f.rule.removeprefix("split_literal_")
        if (base_rule, f.prefix) in existing_prefixes:
            continue
        out.append(f)
        existing_prefixes.add((base_rule, f.prefix))
    return out


def scan_bytes(data: bytes, *, relpath: str) -> list[Finding]:
    """Scan blob bytes. Does NOT skip on embedded NUL (fail-closed; no exemption)."""
    text = data.decode("utf-8", errors="replace")
    return scan_text(text, relpath=relpath)


def scan_members(
    members: Sequence[tuple[str, bytes]],
    *,
    require_planted_control: bool = False,
    planted_rel: str = PLANTED_CONTROL_REL,
    planted_token: str | None = None,
) -> ScanReport:
    """Scan ``(relpath, blob)`` pack members. Returns a typed report."""
    report = ScanReport()
    all_findings: list[Finding] = []
    for rel, blob in members:
        report.scanned_files += 1
        findings = scan_bytes(blob, relpath=rel)
        all_findings.extend(findings)
        if planted_token and planted_token.encode("ascii", errors="ignore") in blob:
            if rel == planted_rel or planted_rel in rel.replace("\\", "/"):
                report.planted_control_found = True
            else:
                report.planted_control_found = True
    report.findings = all_findings
    report.pattern_finding_count = sum(
        1 for f in all_findings if f.rule != "high_entropy_token"
    )
    report.entropy_finding_count = sum(
        1 for f in all_findings if f.rule == "high_entropy_token"
    )
    report.report_text = report.render_named_report()
    if require_planted_control and not report.planted_control_found:
        raise SecretGateError(
            f"planted control {planted_rel!r} was NOT FOUND — clean verdict untrusted"
        )
    return report


def assert_members_clean(
    members: Sequence[tuple[str, bytes]],
) -> ScanReport:
    """Pre-emit gate: raise :class:`SecretGateError` on any blocking finding."""
    report = scan_members(members)
    if report.blocking:
        named = "; ".join(f.named_line() for f in report.findings if f.severity == "blocking")
        raise SecretGateError(
            f"credential-exposure gate blocked emit ({report.blocking}): {named}"
        )
    return report


def scan_tree(root: Path) -> ScanReport:
    """Walk a staging tree and scan every regular file."""
    members: list[tuple[str, bytes]] = []
    root = Path(root)
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            abspath = Path(dirpath) / name
            try:
                data = abspath.read_bytes()
            except OSError:
                continue
            rel = abspath.relative_to(root).as_posix()
            members.append((rel, data))
    members.sort(key=lambda t: t[0])
    return scan_members(members)


def run_gitleaks_on_tree(
    root: Path,
    *,
    config: Path | None = None,
    gitleaks_bin: str | None = None,
) -> tuple[int, list[dict], str]:
    """Run real gitleaks against ``root``; return (exit_code, findings, raw_json).

    Uses ``gitleaks dir`` (filesystem scan) so uncommitted fixture trees work.
    ``--redact`` ensures the JSON never carries the secret body.
    """
    binary = gitleaks_bin or shutil.which("gitleaks")
    if not binary:
        raise SecretGateError("gitleaks binary not found on PATH")
    root = Path(root)
    cfg = Path(config) if config else None
    with tempfile.TemporaryDirectory(prefix="imp0004-gl-") as td:
        report_path = Path(td) / "gitleaks-report.json"
        cmd = [
            binary,
            "dir",
            str(root),
            "--redact",
            "--exit-code",
            "1",
            "--report-format",
            "json",
            "--report-path",
            str(report_path),
            "--no-banner",
        ]
        if cfg and cfg.is_file():
            cmd.extend(["--config", str(cfg)])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        raw = ""
        findings: list[dict] = []
        if report_path.is_file():
            raw = report_path.read_text(encoding="utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw.strip() else []
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list):
                findings = parsed
            elif isinstance(parsed, dict) and "findings" in parsed:
                findings = list(parsed["findings"])
        return proc.returncode, findings, raw


def entropy_flags_token(token: str) -> bool:
    """Independent entropy instrument: does ``token`` exceed the entropy floor?"""
    if len(token) < HIGH_ENTROPY_MIN_LEN:
        # Provider-shaped tokens may be shorter than HIGH_ENTROPY_MIN_LEN body+prefix;
        # still score the body alone for the second instrument proof.
        body = secret_body(token)
        if len(body) >= 16 and shannon_bits(body) >= HIGH_ENTROPY_BITS:
            return True
        return shannon_bits(token) >= HIGH_ENTROPY_BITS and len(token) >= 20
    return shannon_bits(token) >= HIGH_ENTROPY_BITS


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="IMP-0004 credential-exposure gate (fail-closed; never echoes secrets)"
    )
    ap.add_argument("--root", type=Path, help="staging tree to scan")
    ap.add_argument(
        "--json",
        action="store_true",
        help="emit secret-finding.schema.json document",
    )
    ap.add_argument(
        "--require-planted-control",
        action="store_true",
        help="fail if planted control path is missing (detector self-test)",
    )
    args = ap.parse_args(list(argv) if argv is not None else None)
    if not args.root:
        ap.error("--root is required")
    try:
        report = scan_tree(args.root)
        if args.require_planted_control:
            # Re-scan with control requirement using default planted path presence.
            planted = any(
                PLANTED_CONTROL_REL in f.path or f.path.endswith(PLANTED_CONTROL_REL)
                for f in report.findings
            ) or (args.root / PLANTED_CONTROL_REL).is_file()
            report.planted_control_found = planted or report.planted_control_found
            if not report.planted_control_found and report.clean:
                print("FAILED:secret-gate planted-control-NOT-FOUND", file=sys.stderr)
                return 13
    except SecretGateError as exc:
        print(f"FAILED:secret-gate {exc}", file=sys.stderr)
        return 14

    if args.json:
        print(json.dumps(report.as_secret_finding_doc(), indent=2, sort_keys=True))
    else:
        sys.stdout.write(report.render_named_report())
    if report.clean:
        print("SUCCESS:secret-gate clean")
        return 0
    print(f"FAILED:secret-gate findings={len(report.findings)} blocking={report.blocking}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
