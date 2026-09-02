#!/usr/bin/env python3
"""Planted-canary secret sweep: gitleaks + Shannon entropy, prefix-only hits.

Canary bodies are generated at runtime, never written into this module, never
serialized, and always unlinked before the function returns.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import shutil
import string
import subprocess
import tarfile
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORPUS = REPO / "command-center"
UNIT = "ADV-0023"
CANARY_NAME_PREFIX = "ADV0023CANARY-"
GITLEAKS_VERSION = "8.30.1"
GITLEAKS_SHA256 = "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
GITLEAKS_URL = (
    "https://github.com/gitleaks/gitleaks/releases/download/"
    f"v{GITLEAKS_VERSION}/gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
)
GITLEAKS_CACHE = Path("/tmp/adv0023-gitleaks-bin/gitleaks")
ABSENT_PREFIX = "ADV0023ABSENT_"
ENTROPY_MIN_LEN = 16
ENTROPY_MIN_BITS = 3.5
TOKEN_SPLIT = re.compile(r"[A-Za-z0-9+/=_\-.]{16,}")
ASSIGN = re.compile(
    r"(?i)(?:password|passwd|secret|token|api[_-]?key|authorization|"
    r"aws_secret|private_key)\s*[=:]\s*[\"']?([A-Za-z0-9/+=_\-.]{16,})"
)
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".bin"}
SKIP_SUFFIX = {
    ".pyc",
    ".pyo",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".zip",
    ".gz",
    ".tgz",
    ".tar",
    ".bin",
    ".woff",
    ".so",
    ".o",
    ".a",
}
PREFIX_BY_RULE = {
    "aws-access-token": "AKIA",
    "github-pat": "ghp_",
    "slack-bot-token": "xoxb-",
    "private-key": "-----BEGIN",
    "jwt": "eyJ",
    "generic-api-key": "key=",
    "gcp-api-key": "AIza",
    "curl-auth-header": "Authorization",
    "linkedin-client-id": "linkedin",
    "hubspot-api-key": "hubspot",
}
PLANTS = (
    {
        "id": "canary-aws-artifact",
        "surface": "artifacts",
        "rel": "command-center/adversarial/ADV0023CANARY-artifact.env",
        "expected_rule": "aws-access-token",
        "prefix": "AKIA",
        "kind": "aws",
    },
    {
        "id": "canary-github-event-log",
        "surface": "event-logs",
        "rel": "command-center/p2-wave/ADV0023CANARY-event.jsonl",
        "expected_rule": "github-pat",
        "prefix": "ghp_",
        "kind": "github",
    },
    {
        "id": "canary-slack-transcript",
        "surface": "transcripts",
        "rel": "command-center/p2-wave/probes/WFA-0020/fixtures/transcripts/ADV0023CANARY-transcript.jsonl",
        "expected_rule": "slack-bot-token",
        "prefix": "xoxb-",
        "kind": "slack",
    },
    {
        "id": "canary-pem-cache",
        "surface": "caches",
        "rel": "command-center/p2-wave/ADV0023CANARY-cache.dat",
        "expected_rule": "private-key",
        "prefix": "-----BEGIN",
        "kind": "pem",
    },
    {
        "id": "canary-generic-fixture",
        "surface": "test-fixtures",
        "rel": "command-center/p2-wave/probes/TST-0243/captures/ADV0023CANARY-fixture.txt",
        "expected_rule": "generic-api-key",
        "prefix": "key=",
        "kind": "generic",
    },
    {
        "id": "canary-jwt-rollback",
        "surface": "rollback-backups",
        "rel": "command-center/p2-wave/probes/CNF-0072/fixtures/prefix-backup/ADV0023CANARY-rollback.bak",
        "expected_rule": "jwt",
        "prefix": "eyJ",
        "kind": "jwt",
    },
)
MENTION_REL = "command-center/p2-wave/ADV0023CANARY-mention-control.md"
MENTION_BODY = (
    "This control mentions AWS_ACCESS_KEY_ID, GITHUB_TOKEN and SLACK_BOT_TOKEN "
    "as variable names. No credential value is assigned.\n"
    "password=changeme\n"
)


def shannon(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    counts = Counter(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def rel_of(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        text = path.as_posix()
        marker = "/command-center/"
        idx = text.find(marker)
        if idx >= 0:
            return "command-center/" + text[idx + len(marker) :]
        return text


def prefix_for_rule(rule: str) -> str:
    return PREFIX_BY_RULE.get(rule, f"rule:{rule}"[:24])


def _rand(alphabet: str, n: int) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _b64url(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _make_secret(kind: str) -> tuple[str, str]:
    """Return (file_text, body_for_leak_check). Body is never serialized."""
    if kind == "aws":
        # gitleaks aws-access-token: AKIA + [A-Z2-7]{16} (not 0/1/8/9)
        body = "AKIA" + _rand("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567", 16)
        return f"aws_access_key_id={body}\n", body
    if kind == "github":
        body = "ghp_" + _rand(string.ascii_letters + string.digits, 36)
        return f"token={body}\n", body
    if kind == "slack":
        body = (
            "xoxb-"
            + _rand(string.digits, 12)
            + "-"
            + _rand(string.digits, 12)
            + "-"
            + _rand(string.ascii_letters + string.digits, 24)
        )
        return f"SLACK_BOT_TOKEN={body}\n", body
    if kind == "pem":
        inner = secrets.token_urlsafe(80)
        # Split literals so this source file is not itself a private-key hit.
        begin = "-----BEGIN " + "OPENSSH PRIVATE " + "KEY-----"
        end = "-----END " + "OPENSSH PRIVATE " + "KEY-----"
        text = begin + "\n" + inner + "\n" + end + "\n"
        return text, inner
    if kind == "generic":
        body = secrets.token_urlsafe(40)
        return f"AWS_SECRET_ACCESS_KEY={body}\n", body
    if kind == "jwt":
        hdr = _b64url(b'{"alg":"HS256","typ":"JWT"}')
        pay = _b64url(b'{"sub":"adv0023","iat":1}')
        sig = secrets.token_urlsafe(32)
        body = f"{hdr}.{pay}.{sig}"
        return body + "\n", body
    raise ValueError(kind)


def leftover_canary_paths() -> list[str]:
    found: list[str] = []
    if not CORPUS.is_dir():
        return found
    for p in CORPUS.rglob(CANARY_NAME_PREFIX + "*"):
        if p.is_file():
            found.append(rel_of(p))
    return sorted(found)


def purge_canaries() -> list[str]:
    removed: list[str] = []
    for rel in leftover_canary_paths():
        path = REPO / rel
        try:
            path.unlink()
            removed.append(rel)
        except OSError:
            continue
    return removed


def ensure_gitleaks() -> Path:
    cached = GITLEAKS_CACHE
    if cached.is_file() and os.access(cached, os.X_OK):
        return cached
    which = shutil.which("gitleaks")
    if which:
        return Path(which)
    cached.parent.mkdir(parents=True, exist_ok=True)
    tgz = cached.parent / f"gitleaks_{GITLEAKS_VERSION}_linux_x64.tar.gz"
    urllib.request.urlretrieve(GITLEAKS_URL, tgz)  # noqa: S310 - pinned checksum
    digest = hashlib.sha256(tgz.read_bytes()).hexdigest()
    if digest != GITLEAKS_SHA256:
        tgz.unlink(missing_ok=True)
        raise RuntimeError(f"gitleaks checksum mismatch got={digest}")
    with tarfile.open(tgz, "r:gz") as tf:
        member = tf.getmember("gitleaks")
        tf.extract(member, path=cached.parent, filter="data")
    cached.chmod(0o755)
    if not cached.is_file():
        raise RuntimeError("gitleaks extract missing binary")
    return cached


def run_gitleaks(source: Path, timeout: int = 140) -> tuple[int, list[dict], str]:
    binary = ensure_gitleaks()
    with tempfile.TemporaryDirectory(prefix="adv0023-gl-") as td:
        report = Path(td) / "gitleaks.json"
        cmd = [
            str(binary),
            "detect",
            "--source",
            str(source),
            "--no-git",
            "--no-banner",
            "--redact",
            "--report-format",
            "json",
            "--report-path",
            str(report),
            "--exit-code",
            "0",
            "--timeout",
            str(timeout),
            "--max-target-megabytes",
            "12",
            "--log-level",
            "warn",
        ]
        p = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout + 15,
            check=False,
        )
        raw_tail = ((p.stderr or "") + "\n" + (p.stdout or "")).strip()[-2000:]
        hits: list[dict] = []
        if report.is_file() and report.stat().st_size > 0:
            payload = json.loads(report.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                hits = payload
        return p.returncode, hits, raw_tail


def _decode(raw: bytes) -> str | None:
    if not raw or b"\x00" in raw[:1024]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("latin-1")
        except UnicodeDecodeError:
            return None


def _prefix_from_token(token: str) -> str:
    for pfx in (
        "AKIA",
        "ghp_",
        "gho_",
        "github_pat_",
        "xoxb-",
        "xoxp-",
        "xoxa-",
        "-----BEGIN",
        "eyJ",
        "AIza",
        "sk_live_",
        "sk_test_",
    ):
        if token.startswith(pfx):
            return pfx
    return "<entropy>"


def scan_entropy_file(path: Path) -> list[dict]:
    try:
        if path.stat().st_size > 6_000_000:
            return []
        raw = path.read_bytes()
    except OSError:
        return []
    text = _decode(raw)
    if text is None:
        return []
    rel = rel_of(path)
    hits: list[dict] = []
    seen: set[tuple[int, str]] = set()
    lines = text.splitlines()
    planted = CANARY_NAME_PREFIX in path.name

    def add(line_no: int, token: str) -> None:
        if len(token) < ENTROPY_MIN_LEN:
            return
        ent = round(shannon(token), 6)
        if ent < ENTROPY_MIN_BITS:
            return
        key = (line_no, _prefix_from_token(token))
        if key in seen:
            return
        seen.add(key)
        hits.append(
            {
                "scanner": "entropy",
                "path": rel,
                "line": line_no,
                "prefix": _prefix_from_token(token),
                "entropy": ent,
                "rule": "high-entropy-token",
            }
        )

    if planted:
        for i, line in enumerate(lines, 1):
            for tok in TOKEN_SPLIT.findall(line):
                add(i, tok)
        return hits
    for i, line in enumerate(lines, 1):
        for m in ASSIGN.finditer(line):
            add(i, m.group(1))
    return hits


def scan_entropy_corpus() -> list[dict]:
    hits: list[dict] = []
    for dirpath, dirnames, filenames in os.walk(CORPUS):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in SKIP_SUFFIX:
                continue
            hits.extend(scan_entropy_file(path))
    return hits


def surface_of(rel: str) -> str:
    text = rel.replace("\\", "/").lower()
    if "/adversarial/" in text or "/receipts/" in text or "/confirmation/" in text:
        return "artifacts"
    if "transcript" in text:
        return "transcripts"
    if "rollback" in text or "backup" in text or "snapshot" in text:
        return "rollback-backups"
    if "/fixtures/" in text or "fixture" in text:
        return "test-fixtures"
    if "cache" in text or text.endswith(".tmp") or text.endswith(".dat"):
        return "caches"
    if text.endswith(".jsonl") or text.endswith(".log") or "/event" in text:
        return "event-logs"
    if "/audit/" in text:
        return "artifacts"
    return "other-corpus"


def _normalize_gitleaks(hits: list[dict]) -> list[dict]:
    out: list[dict] = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        path = rel_of(Path(str(h.get("File") or "")))
        rule = str(h.get("RuleID") or "unknown")
        try:
            ent = float(h.get("Entropy") or 0.0)
        except (TypeError, ValueError):
            ent = 0.0
        out.append(
            {
                "scanner": "gitleaks",
                "path": path,
                "line": int(h.get("StartLine") or 0),
                "prefix": prefix_for_rule(rule),
                "entropy": round(ent, 6),
                "rule": rule,
            }
        )
    return out


def _assert_no_bodies(blob: str, bodies: list[str]) -> None:
    for body in bodies:
        if body and body in blob:
            raise RuntimeError("secret body leaked into sweep result")


def run_sweep() -> dict:
    """Plant, scan command-center, unplant, return prefix-only results."""
    stale = purge_canaries()
    bodies: list[str] = []
    planted: list[dict] = []
    mention_path = REPO / MENTION_REL
    try:
        for spec in PLANTS:
            path = REPO / spec["rel"]
            path.parent.mkdir(parents=True, exist_ok=True)
            text, body = _make_secret(spec["kind"])
            bodies.append(body)
            path.write_text(text, encoding="utf-8")
            line = 1
            planted.append(
                {
                    "id": spec["id"],
                    "surface": spec["surface"],
                    "path": spec["rel"],
                    "line": line,
                    "prefix": spec["prefix"],
                    "expected_rule": spec["expected_rule"],
                    "bytes": path.stat().st_size,
                }
            )
        mention_path.parent.mkdir(parents=True, exist_ok=True)
        mention_path.write_text(MENTION_BODY, encoding="utf-8")

        gl_rc, gl_raw, gl_tail = run_gitleaks(CORPUS)
        gl_hits = _normalize_gitleaks(gl_raw)
        ent_hits = scan_entropy_corpus()

        by_path_gl: dict[str, list[dict]] = {}
        for hit in gl_hits:
            by_path_gl.setdefault(hit["path"], []).append(hit)
        by_path_ent: dict[str, list[dict]] = {}
        for hit in ent_hits:
            by_path_ent.setdefault(hit["path"], []).append(hit)

        recall_rows = []
        for row in planted:
            gl_for = by_path_gl.get(row["path"]) or []
            ent_for = by_path_ent.get(row["path"]) or []
            gl_rule = any(h.get("rule") == row["expected_rule"] for h in gl_for)
            gl_any = bool(gl_for)
            ent_any = bool(ent_for)
            recall_rows.append(
                {
                    "id": row["id"],
                    "surface": row["surface"],
                    "path": row["path"],
                    "line": row["line"],
                    "prefix": row["prefix"],
                    "expected_rule": row["expected_rule"],
                    "gitleaks_found": gl_rule or gl_any,
                    "gitleaks_expected_rule": gl_rule,
                    "entropy_found": ent_any,
                    "gitleaks_entropy": (gl_for[0]["entropy"] if gl_for else None),
                    "entropy_value": (ent_for[0]["entropy"] if ent_for else None),
                }
            )

        n = len(recall_rows)
        gl_found = sum(1 for r in recall_rows if r["gitleaks_found"])
        ent_found = sum(1 for r in recall_rows if r["entropy_found"])
        combined = sum(1 for r in recall_rows if r["gitleaks_found"] or r["entropy_found"])
        mention_hits = [h for h in gl_hits if h["path"] == MENTION_REL]
        canary_paths = {r["path"] for r in planted} | {MENTION_REL}
        corpus_gl = [h for h in gl_hits if h["path"] not in canary_paths]
        corpus_ent = [h for h in ent_hits if h["path"] not in canary_paths]
        absent_hits = [
            h
            for h in (gl_hits + ent_hits)
            if str(h.get("prefix") or "").startswith(ABSENT_PREFIX)
            or ABSENT_PREFIX in str(h.get("path") or "")
        ]
        surfaces = {
            "artifacts",
            "event-logs",
            "transcripts",
            "caches",
            "test-fixtures",
            "rollback-backups",
            "other-corpus",
        }
        surface_hits = {s: 0 for s in surfaces}
        for hit in corpus_gl:
            surface_hits[surface_of(hit["path"])] = surface_hits.get(surface_of(hit["path"]), 0) + 1

        result = {
            "unit_id": UNIT,
            "gitleaks": {
                "binary": str(ensure_gitleaks()),
                "version": GITLEAKS_VERSION,
                "exit_code": gl_rc,
                "hit_count": len(gl_hits),
                "corpus_hit_count": len(corpus_gl),
                "log_tail": gl_tail[-800:],
            },
            "entropy": {
                "hit_count": len(ent_hits),
                "corpus_hit_count": len(corpus_ent),
                "min_bits": ENTROPY_MIN_BITS,
                "min_len": ENTROPY_MIN_LEN,
            },
            "canaries": recall_rows,
            "recall": {
                "planted": n,
                "gitleaks_found": gl_found,
                "entropy_found": ent_found,
                "combined_found": combined,
                "gitleaks_rate": (gl_found / n) if n else 0.0,
                "entropy_rate": (ent_found / n) if n else 0.0,
                "combined_rate": (combined / n) if n else 0.0,
            },
            "mention_control": {
                "path": MENTION_REL,
                "gitleaks_hits": len(mention_hits),
                "silent": len(mention_hits) == 0,
            },
            "absent_prefix": {
                "prefix": ABSENT_PREFIX,
                "hits": len(absent_hits),
                "silent": len(absent_hits) == 0,
            },
            "corpus_gitleaks_hits": corpus_gl,
            "corpus_entropy_hits": corpus_ent[:120],
            "surface_gitleaks_counts": surface_hits,
            "stale_purged_before": stale,
        }
        blob = json.dumps(result, sort_keys=True)
        _assert_no_bodies(blob, bodies)
        return result
    finally:
        for spec in PLANTS:
            (REPO / spec["rel"]).unlink(missing_ok=True)
        mention_path.unlink(missing_ok=True)
        leftover = leftover_canary_paths()
        if leftover:
            purge_canaries()
            leftover = leftover_canary_paths()
        # attach removal proof on the result if we built it
        # (finally cannot easily mutate result if exception before assign)
        try:
            result  # noqa: F821
        except NameError:
            pass
        else:
            result["removal"] = {
                "verified": leftover == [],
                "leftover": leftover,
            }
            blob = json.dumps(result, sort_keys=True)
            _assert_no_bodies(blob, bodies)


def first_json(text: str) -> dict | None:
    start = text.find("{")
    if start < 0:
        return None
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None
