"""Independent structural classifier for residual identifiability.

Does not read the sealed mapping until score() compares guesses. Fingerprints
are mechanism phrases that survive name/author redaction.
"""
from __future__ import annotations

from pathlib import Path

# (architecture_id, required distinctive phrases)
FINGERPRINTS: list[tuple[str, list[str]]] = [
    (
        "A1",
        [
            "no generated layer",
            "whole-object",
            "static-config",
            "is not loaded",
        ],
    ),
    (
        "A2",
        [
            "generator_version",
            "byte-identical",
            "registry_entry_sha256",
            "provenance",
        ],
    ),
    (
        "A3",
        [
            "lockfile-pinned",
            "cache-invalidation",
            "stale-cache-masks",
        ],
    ),
    (
        "A4",
        [
            "deactivation path",
            "resident-set",
            "refuses an activation",
        ],
    ),
    (
        "A5",
        [
            "append-only",
            "at-least-once",
            "duplicate-dispatch",
        ],
    ),
    (
        "A6",
        [
            "FAIL LOUDLY",
            "never silently downgraded",
            "vendor-only",
        ],
    ),
    (
        "A7",
        [
            "choke point",
            "least-privilege",
            "bypass path",
        ],
    ),
    (
        "A8",
        [
            "jobs-to-be-done",
            "error-message contract",
        ],
    ),
    (
        "A9",
        [
            "singular control plane",
            "borrowed mechanism",
            "capability-to-authority",
        ],
    ),
]


def read_entry_text(entry_dir: Path) -> str:
    parts: list[str] = []
    for path in sorted(entry_dir.rglob("*")):
        if path.is_file():
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                continue
    return "\n".join(parts)


def classify_text(text: str) -> str | None:
    lowered = text.casefold()
    scored: list[tuple[int, str]] = []
    for arch_id, phrases in FINGERPRINTS:
        hits = sum(1 for p in phrases if p.casefold() in lowered)
        if hits >= 2:
            scored.append((hits, arch_id))
    if not scored:
        return None
    scored.sort(key=lambda row: (-row[0], row[1]))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def classify_entry(entry_dir: Path) -> str | None:
    return classify_text(read_entry_text(entry_dir))


def score(entries_root: Path, mapping: dict[str, str], labels: list[str]) -> dict:
    rows = []
    hits = 0
    for label in labels:
        guess = classify_entry(entries_root / label)
        truth = mapping.get(label)
        hit = bool(guess) and guess == truth
        if hit:
            hits += 1
        rows.append({"label": label, "guess": guess, "hit": hit})
    attempts = len(labels)
    hit_rate = (hits / attempts) if attempts else 0.0
    return {
        "attempts": attempts,
        "hits": hits,
        "hit_rate": hit_rate,
        "blindness_score": hit_rate,
        "rows": rows,
    }
