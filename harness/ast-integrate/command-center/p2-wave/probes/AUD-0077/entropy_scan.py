"""Independent entropy-plus-pattern scanner. Does not call gitleaks."""
from __future__ import annotations

import re
from pathlib import Path

from helpers import (
    REPO,
    classify,
    fingerprint,
    is_self_artifact,
    is_text_file,
    iter_files,
    lhs_from_line,
    relpath,
    scope_for,
    shannon,
)

# Patterns authored here, not copied from gitleaks rule IDs.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("github-pat-shape", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("aws-access-key-id-shape", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("pem-private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt-shape", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("slack-token-shape", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("openai-sk-shape", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}")),
    ("anthropic-sk-shape", re.compile(r"\bsk-ant-[A-Za-z0-9-]{20,}")),
    ("google-api-key-shape", re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b")),
]

KEY_HINT = re.compile(
    r"(api[_-]?key|token|secret|passwd|password|credential|private[_-]?key|auth|bearer|access[_-]?key)",
    re.I,
)
ASSIGN_VALUE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_.-]{0,120})\s*[:=]\s*['\"]?(?P<rhs>[A-Za-z0-9/+=_.-]{24,})['\"]?"
)
MAX_HITS = 400


def _hit(rel: str, line: int, rule_id: str, var: str) -> dict:
    return {
        "path": rel,
        "line": line,
        "rule_id": rule_id,
        "detector": "entropy-pattern",
        "variable_name": var,
        "scope": scope_for(rel, var),
        "classification": classify(rel, var),
        "fingerprint": fingerprint(rel, line, rule_id, "entropy-pattern"),
    }


def scan_tree(root: Path | None = None) -> dict:
    root = (root or REPO).resolve()
    hits: list[dict] = []
    files_scanned = 0
    bytes_scanned = 0
    for path in iter_files(root):
        rel = relpath(path) if root == REPO.resolve() else path.name
        if root == REPO.resolve() and is_self_artifact(rel):
            continue
        if not is_text_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files_scanned += 1
        bytes_scanned += len(text.encode("utf-8", errors="replace"))
        lines = text.splitlines()
        seen_fp: set[str] = set()
        for i, line in enumerate(lines, start=1):
            var = lhs_from_line(line)
            for rule_id, pat in PATTERNS:
                if pat.search(line):
                    rec = _hit(rel if root == REPO.resolve() else relpath(path), i, rule_id, var)
                    if rec["fingerprint"] not in seen_fp:
                        hits.append(rec)
                        seen_fp.add(rec["fingerprint"])
                    break
            else:
                if KEY_HINT.search(var) or KEY_HINT.search(line[:80]):
                    m = ASSIGN_VALUE.search(line)
                    if m:
                        rhs = m.group("rhs")
                        ent = shannon(rhs)
                        # Drop rhs immediately; never store it.
                        del rhs
                        if ent >= 4.0 and len(m.group("lhs")) >= 3:
                            rec = _hit(
                                rel if root == REPO.resolve() else relpath(path),
                                i,
                                "assignment-high-entropy",
                                m.group("lhs"),
                            )
                            rec["shannon"] = round(ent, 3)
                            if rec["fingerprint"] not in seen_fp:
                                hits.append(rec)
                                seen_fp.add(rec["fingerprint"])
            if len(hits) >= MAX_HITS:
                break
        if len(hits) >= MAX_HITS:
            break
    hits.sort(key=lambda r: r["fingerprint"])
    counts: dict[str, int] = {}
    for h in hits:
        counts[h["rule_id"]] = counts.get(h["rule_id"], 0) + 1
    return {
        "tool": "entropy-pattern",
        "independent_of_gitleaks": True,
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "hit_count": len(hits),
        "capped": len(hits) >= MAX_HITS,
        "findings": hits,
        "fingerprints": [h["fingerprint"] for h in hits],
        "rule_counts": dict(sorted(counts.items())),
        "files_scanned": files_scanned,
        "bytes_scanned": bytes_scanned,
        "hit_count": len(hits),
        "rule_counts": dict(sorted(counts.items())),
        "independent_of_gitleaks": True,
    }

scan_tree = scan_tree
