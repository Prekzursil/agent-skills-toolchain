"""Two mechanically different secret scanners over git history and packed objects.

Scanner 1 is rule/prefix regex (gitleaks-style). Scanner 2 is Shannon entropy on
underscore-split token segments. Neither returns a credential body — only a
zero-entropy prefix, path, commit, and rule name.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from history_repo import git

# Recognisable non-secret prefix for the planted control.
CANARY_PREFIX = "CNF0108CANARY_"

# Rule prefixes are themselves low-entropy; bodies are never copied out.
PATTERN_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("planted-canary", re.compile(re.escape(CANARY_PREFIX) + r"[A-Za-z0-9_-]{8,}"), CANARY_PREFIX),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA"),
    ("github-pat", re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_"),
    ("slack-token", re.compile(r"xox[baprs]-"), "xox"),
    ("pem-private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "-----BEGIN"),
]

TOKEN_SPLIT = re.compile(r"[A-Za-z0-9+/=_-]{20,}")
ENTROPY_MIN_LEN = 16
ENTROPY_MIN_BITS = 3.5


def shannon(s: str) -> float:
    if not s:
        return 0.0
    n = len(s)
    counts = Counter(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def _decode(raw: bytes) -> str | None:
    if not raw or b"\x00" in raw[:1024]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _hit(
    scanner: str,
    rule: str,
    prefix: str,
    path: str,
    commit: str,
    blob: str,
    body_len: int,
) -> dict:
    return {
        "scanner": scanner,
        "rule": rule,
        "prefix": prefix,
        "path": path,
        "commit": commit,
        "blob": blob,
        "body_len": int(body_len),
    }


def scan_text_pattern(text: str, path: str, commit: str, blob: str) -> list[dict]:
    hits: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for rule, rx, prefix in PATTERN_RULES:
        for m in rx.finditer(text):
            key = (rule, path, commit)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                _hit(
                    "pattern",
                    rule,
                    prefix,
                    path,
                    commit,
                    blob,
                    max(0, len(m.group(0)) - len(prefix)),
                )
            )
    return hits


def scan_text_entropy(text: str, path: str, commit: str, blob: str) -> list[dict]:
    hits: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for tok in TOKEN_SPLIT.findall(text):
        parts = [p for p in tok.split("_") if p]
        if not parts:
            continue
        # Score the longest high-entropy segment so a known prefix cannot hide a body.
        best = max(parts, key=lambda p: (shannon(p), len(p)))
        if len(best) < ENTROPY_MIN_LEN or shannon(best) < ENTROPY_MIN_BITS:
            continue
        prefix = CANARY_PREFIX if CANARY_PREFIX in tok else "<entropy>"
        rule = "planted-canary-entropy" if CANARY_PREFIX in tok else "high-entropy-segment"
        key = (rule, path, commit)
        if key in seen:
            continue
        seen.add(key)
        hits.append(_hit("entropy", rule, prefix, path, commit, blob, len(best)))
    return hits


def iter_commit_blobs(repo: Path) -> list[tuple[str, str, str]]:
    """Return (commit, path, blob_sha) for every blob on every ref."""
    commits = git(repo, "rev-list", "--all").stdout.split()
    rows: list[tuple[str, str, str]] = []
    for commit in commits:
        tree = git(repo, "ls-tree", "-r", "--full-tree", commit).stdout.splitlines()
        for line in tree:
            # <mode> <type> <sha>\t<path>
            try:
                meta, path = line.split("\t", 1)
            except ValueError:
                continue
            parts = meta.split()
            if len(parts) < 3 or parts[1] != "blob":
                continue
            rows.append((commit, path, parts[2]))
    return rows


def git_bytes(repo: Path, sha: str) -> bytes:
    env = os.environ.copy()
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    p = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "blob", sha],
        capture_output=True,
        check=True,
    )
    return p.stdout


def packed_blob_shas(repo: Path) -> set[str]:
    pack_dir = Path(repo) / ".git" / "objects" / "pack"
    found: set[str] = set()
    for idx in pack_dir.glob("*.idx"):
        out = git(repo, "verify-pack", "-v", str(idx)).stdout.splitlines()
        for line in out:
            parts = line.split()
            if len(parts) >= 2 and len(parts[0]) == 40:
                found.add(parts[0])
    return found


def all_object_shas(repo: Path) -> set[str]:
    out = git(repo, "cat-file", "--batch-check", "--batch-all-objects").stdout.splitlines()
    shas: set[str] = set()
    for line in out:
        parts = line.split()
        if parts:
            shas.add(parts[0])
    return shas


def scan_working_tree(repo: Path) -> tuple[list[dict], list[dict]]:
    pattern: list[dict] = []
    entropy: list[dict] = []
    root = Path(repo)
    for dirpath, dirnames, filenames in os_walk_skip_git(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            text = _decode(raw)
            if text is None:
                continue
            pattern.extend(scan_text_pattern(text, rel, "WORKING-TREE", "working-tree"))
            entropy.extend(scan_text_entropy(text, rel, "WORKING-TREE", "working-tree"))
    return pattern, entropy


def os_walk_skip_git(root: Path):
    return os.walk(root)


def scan_history(repo: Path) -> dict:
    """Walk every commit blob and every packed object with both scanners."""
    repo = Path(repo)
    cache: dict[str, bytes] = {}
    pattern: list[dict] = []
    entropy: list[dict] = []
    rows = iter_commit_blobs(repo)
    for commit, path, blob in rows:
        if blob not in cache:
            cache[blob] = git_bytes(repo, blob)
        text = _decode(cache[blob])
        if text is None:
            continue
        pattern.extend(scan_text_pattern(text, path, commit, blob))
        entropy.extend(scan_text_entropy(text, path, commit, blob))

    packed = packed_blob_shas(repo)
    all_objs = all_object_shas(repo)
    packed_extra_pattern = 0
    packed_extra_entropy = 0
    seen_blobs = {b for _, _, b in rows}
    for sha in sorted(all_objs):
        if sha in seen_blobs:
            continue
        try:
            raw = git_bytes(repo, sha)
        except Exception:
            continue
        text = _decode(raw)
        if text is None:
            continue
        ph = scan_text_pattern(text, "(packed-object)", "(packed)", sha)
        eh = scan_text_entropy(text, "(packed-object)", "(packed)", sha)
        packed_extra_pattern += len(ph)
        packed_extra_entropy += len(eh)
        pattern.extend(ph)
        entropy.extend(eh)

    return {
        "pattern_hits": pattern,
        "entropy_hits": entropy,
        "commits_walked": len({c for c, _, _ in rows}),
        "blobs_walked": len(seen_blobs),
        "packed_object_shas": len(packed),
        "all_object_shas": len(all_objs),
        "packed_extra_pattern_hits": packed_extra_pattern,
        "packed_extra_entropy_hits": packed_extra_entropy,
    }


def canary_found(hits: list[dict], prefix: str = CANARY_PREFIX) -> bool:
    return any(h.get("prefix") == prefix for h in hits)


def redact_finding(hit: dict, classification: str, fid: str) -> dict:
    return {
        "id": fid,
        "classification": classification,
        "path": hit["path"],
        "commit": hit["commit"],
        "rule": hit["rule"],
        "prefix": hit["prefix"],
        "scanner": hit["scanner"],
        "blob": hit["blob"],
        "body_len": hit["body_len"],
        "rotation_recommendation": (
            "Synthetic planted canary — do not rotate any live credential. "
            "This unit never rotates, revokes, or unsets secrets."
            if hit["prefix"] == CANARY_PREFIX
            else (
                "Owner should rotate the credential at the named path/commit if it "
                "is confirmed live. This unit never rotates."
            )
        ),
        "blast_radius": (
            f"git blob {hit['blob'][:12]} on commit {hit['commit'][:12]} path {hit['path']}; "
            "any clone of this history contains the blob until rewritten."
        ),
    }
