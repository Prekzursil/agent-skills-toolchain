#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from harness.ledger import default_state_root
    from harness.redaction import redact_text
    from harness.storage import atomic_write_json

    try:
        from harness.injection_grammar import DIRECTIVE_CATEGORIES, looks_poisoned
    except ImportError:  # pragma: no cover - foundation module absent (fail-open)
        DIRECTIVE_CATEGORIES = ()  # type: ignore[assignment]

        def looks_poisoned(text: object, *, categories: Any = None) -> bool:  # type: ignore[misc]
            return False
else:
    from .ledger import default_state_root
    from .redaction import redact_text
    from .storage import atomic_write_json

    try:
        from .injection_grammar import DIRECTIVE_CATEGORIES, looks_poisoned
    except ImportError:  # pragma: no cover - foundation module absent (fail-open)
        DIRECTIVE_CATEGORIES = ()  # type: ignore[assignment]

        def looks_poisoned(text: object, *, categories: Any = None) -> bool:  # type: ignore[misc]
            return False


# Bumped for the SI-5 note schema (gem B1): each note now carries mtime,
# importance, superseded_by, is_failure_head and poisoned. Additive only -
# every field the previous consumers relied on is unchanged, and the RecallModule
# degrades gracefully on an old (v1) index that lacks the new fields.
SCHEMA_VERSION = 2

_EXCLUDED_DIRS = {".git", ".hf", ".models", "compaction-checkpoints", "node_modules"}
_WORD = re.compile(r"[a-z0-9][a-z0-9._-]{2,}", re.I)
_STOPWORDS = {
    "about",
    "after",
    "also",
    "and",
    "are",
    "before",
    "from",
    "have",
    "into",
    "that",
    "the",
    "this",
    "with",
    "your",
    "http",
    "https",
    "www",
}

# Tags / types that mark a note as a FAILURE / contradiction head (boosted first
# by the RecallModule - conflicting memory beats confirming memory).
_FAILURE_TAGS = {"failure", "compaction-checkpoint", "compaction_checkpoint"}
# Frontmatter signals that push the default `importance` up or down when a note
# has no explicit `importance:` value.
_HIGH_IMPORTANCE_TAGS = {
    "current",
    "keystone",
    "important",
    "critical",
    "decision",
    "milestone",
    "star",
    "starred",
    "pinned",
    "canonical",
    "high",
}
_LOW_IMPORTANCE_TAGS = {
    "deprecated",
    "superseded",
    "obsolete",
    "archive",
    "archived",
    "stale",
    "retired",
    "low",
}
_IMPORTANCE_WORDS = {
    "critical": 1.0,
    "high": 0.9,
    "important": 0.8,
    "medium": 0.5,
    "med": 0.5,
    "normal": 0.5,
    "low": 0.2,
    "minor": 0.2,
    "trivial": 0.1,
}


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body = text[end + 4 :].lstrip("\r\n")
    try:
        import yaml

        parsed = yaml.safe_load(raw)
        return (parsed if isinstance(parsed, dict) else {}), body
    except Exception:
        return {}, body


def _summary(body: str) -> str:
    pieces: list[str] = []
    for line in body.splitlines():
        clean = line.strip()
        if not clean or clean.startswith(("#", "<!--", "```")):
            if pieces:
                break
            continue
        pieces.append(clean)
        if sum(len(item) for item in pieces) >= 320:
            break
    return redact_text(" ".join(pieces), redact_paths=True, max_chars=360)


def _keywords(*values: str) -> list[str]:
    words: set[str] = set()
    for value in values:
        for token in _WORD.findall(value.lower()):
            if token not in _STOPWORDS:
                words.add(token)
    return sorted(words)[:80]


def _tag_set(metadata: dict[str, Any]) -> set[str]:
    """Lowercase token set from frontmatter `tags` (a list, or a comma/space string)."""
    raw = metadata.get("tags")
    if isinstance(raw, str):
        parts: list[str] = re.split(r"[,\s]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        parts = [str(item) for item in raw]
    else:
        parts = []
    tokens: set[str] = set()
    for part in parts:
        token = str(part).strip().lower().lstrip("#")
        if token:
            tokens.add(token)
    return tokens


def _explicit_importance(raw: Any) -> float | None:
    """Parse a frontmatter `importance` value, or None to fall back to the default."""
    if raw is None or isinstance(raw, bool):
        # `importance: true` is not a 0..1 number - fall back to the heuristic.
        return None
    if isinstance(raw, (int, float)):
        return _clamp01(float(raw))
    if isinstance(raw, str):
        stripped = raw.strip().lower()
        if not stripped:
            return None
        try:
            return _clamp01(float(stripped))
        except ValueError:
            return _IMPORTANCE_WORDS.get(stripped)
    return None


def _default_importance(tags: set[str], mtime: float, now: float) -> float:
    """Derive importance (0..1) from tags + recency when no explicit value is set.

    A mild prior only - the RecallModule applies the real exponential recency
    decay over `mtime`; this recency nudge just seeds notes with no other signal."""
    score = 0.5
    if tags & _HIGH_IMPORTANCE_TAGS:
        score += 0.2
    if tags & _LOW_IMPORTANCE_TAGS:
        score -= 0.25
    if mtime > 0:
        age_days = max(0.0, (now - mtime) / 86400.0)
        if age_days <= 7:
            score += 0.15
        elif age_days <= 30:
            score += 0.05
        elif age_days > 365:
            score -= 0.10
    return _clamp01(score)


def _importance(
    metadata: dict[str, Any], tags: set[str], mtime: float, now: float
) -> float:
    explicit = _explicit_importance(metadata.get("importance"))
    if explicit is not None:
        return round(explicit, 4)
    return round(_default_importance(tags, mtime, now), 4)


def _is_failure_head(
    metadata: dict[str, Any], tags: set[str], superseded_by: str
) -> bool:
    """True for a failure/checkpoint note OR the current head of a --supersedes chain.

    A note is a chain head when it supersedes an older note (frontmatter
    `supersedes`, or the temporal-validity `valid_as_of` marker per the vault
    convention) and is not itself superseded."""
    if tags & _FAILURE_TAGS:
        return True
    note_type = str(metadata.get("type") or "").lower()
    if (
        "failure" in note_type
        or "compaction-checkpoint" in note_type
        or "compaction_checkpoint" in note_type
    ):
        return True
    supersedes = metadata.get("supersedes")
    has_supersedes = (
        bool(supersedes)
        if not isinstance(supersedes, (str, bytes))
        else bool(str(supersedes).strip())
    )
    valid_as_of = bool(str(metadata.get("valid_as_of") or "").strip())
    if (has_supersedes or valid_as_of) and not superseded_by:
        return True
    return False


def build_index(vault: Path | str, target: Path | str) -> int:
    vault_path = Path(vault).resolve()
    target_path = Path(target)
    notes: list[dict[str, Any]] = []
    fingerprint = hashlib.sha256()
    now = time.time()
    if not vault_path.exists():
        raise FileNotFoundError(vault_path)
    # An index target inside the scanned vault ALIASES a source note: the writer
    # below replaces that pathname outright, so the note's Markdown bytes are lost
    # while the caller still gets a success return (and the CLI still prints
    # SUCCESS). Reject it before anything is read or written. `parent.resolve() /
    # name` is compared because that is the exact directory entry os.replace acts
    # on - a symlinked FINAL component is replaced in place, not followed.
    write_target = target_path.expanduser()
    write_target = write_target.parent.resolve() / write_target.name
    if write_target.is_relative_to(vault_path):
        raise ValueError(f"refusing to write the index inside the vault: {target}")

    for path in sorted(vault_path.rglob("*.md")):
        try:
            relative = path.relative_to(vault_path)
        except ValueError:
            continue
        if any(part in _EXCLUDED_DIRS for part in relative.parts[:-1]):
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")[:16384]
            stat = path.stat()
        except OSError:
            continue
        metadata, body = _frontmatter(raw)
        safe_body = redact_text(body, redact_paths=True, max_chars=16384)
        title = str(metadata.get("title") or path.stem).strip()
        permalink = str(
            metadata.get("permalink") or relative.with_suffix("").as_posix()
        ).strip()
        safe_path = redact_text(relative.as_posix(), redact_paths=True, max_chars=300)
        safe_title = redact_text(title, redact_paths=True, max_chars=180)
        safe_permalink = redact_text(permalink, redact_paths=True, max_chars=240)
        summary = _summary(safe_body)

        # SI-5 note-schema fields (gem B1). `mtime` (epoch float) was stat'd then
        # discarded before; keep it so the RecallModule can apply recency decay.
        mtime = float(stat.st_mtime)
        tags = _tag_set(metadata)
        superseded_raw = metadata.get("superseded_by")
        superseded_by = (
            redact_text(str(superseded_raw).strip(), redact_paths=True, max_chars=240)
            if superseded_raw
            else ""
        )
        importance = _importance(metadata, tags, mtime, now)
        is_failure_head = _is_failure_head(metadata, tags, superseded_by)
        # Poisoned pre-scan reuses the shared D2 injection grammar, scoped to the
        # DIRECTIVE categories: a poisoned MEMORY steers the agent when recalled,
        # whereas a documented shell one-liner in the owner's own note is benign.
        poisoned = looks_poisoned(body, categories=DIRECTIVE_CATEGORIES)

        notes.append(
            {
                "path": safe_path,
                "title": safe_title,
                "summary": summary,
                "permalink": safe_permalink,
                "keywords": _keywords(
                    safe_path, safe_title, safe_permalink, summary, safe_body[:2000]
                ),
                "mtime": mtime,
                "importance": importance,
                "superseded_by": superseded_by,
                "is_failure_head": is_failure_head,
                "poisoned": poisoned,
            }
        )
        fingerprint.update(relative.as_posix().encode("utf-8", "replace"))
        fingerprint.update(str(stat.st_mtime_ns).encode("ascii"))

    document = {
        "schema_version": SCHEMA_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "vault_hash": fingerprint.hexdigest(),
        "notes": notes,
    }
    atomic_write_json(target_path, document)
    return len(notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the bounded lexical Basic Memory index"
    )
    parser.add_argument("--vault", default="D:/basic-memory")
    parser.add_argument(
        "--target", default=str(default_state_root() / "recall-index.json")
    )
    args = parser.parse_args(argv)
    try:
        count = build_index(args.vault, args.target)
    except Exception as exc:
        print(f"FAILED:recall-index {type(exc).__name__}")
        return 1
    print(f"SUCCESS:recall-index notes={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
