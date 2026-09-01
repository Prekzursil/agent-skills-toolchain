#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

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


DIGEST_SIDECAR_NAME = "recall-digest.json"
DIGEST_MAX_NOTES = 16
DIGEST_SUMMARY_CHARS = 200
_DIGEST_EXCLUDED_PARTS = {
    ".git",
    ".hf",
    ".models",
    "compaction-checkpoints",
    "node_modules",
}
_NOTES_ARRAY_RE = re.compile(r'"notes"\s*:\s*\[')
_HEADER_BUILT_AT_RE = re.compile(r'"built_at"\s*:\s*"([^"]+)"')
_HEADER_SCHEMA_RE = re.compile(r'"schema_version"\s*:\s*(\d+)')


def _digest_path_excluded(value: str) -> bool:
    if not value:
        return False
    return any(part in _DIGEST_EXCLUDED_PARTS for part in value.replace("\\", "/").split("/"))


def _slim_note(note: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(note, dict):
        return None
    path = str(note.get("path") or "")
    permalink = str(note.get("permalink") or "")
    if _digest_path_excluded(path) or _digest_path_excluded(permalink):
        return None
    try:
        mtime = float(note.get("mtime") or 0.0)
    except (TypeError, ValueError):
        mtime = 0.0
    try:
        importance = float(note.get("importance") or 0.0)
    except (TypeError, ValueError):
        importance = 0.0
    return {
        "title": redact_text(str(note.get("title") or "Untitled"), redact_paths=True, max_chars=180),
        "path": redact_text(path, redact_paths=True, max_chars=300),
        "permalink": redact_text(permalink, redact_paths=True, max_chars=240),
        "mtime": mtime,
        "importance": _clamp01(importance),
        "summary": redact_text(
            str(note.get("summary") or ""),
            redact_paths=True,
            max_chars=DIGEST_SUMMARY_CHARS,
        ),
    }


def _select_digest_notes(
    notes: Iterable[dict[str, Any]], limit: int = DIGEST_MAX_NOTES
) -> list[dict[str, Any]]:
    def gen() -> Iterable[dict[str, Any]]:
        for raw in notes:
            item = _slim_note(raw)
            if item is not None:
                yield item

    return heapq.nlargest(limit, gen(), key=lambda n: (n["importance"], n["mtime"]))


def _peek_index_header(path: Path) -> tuple[int | None, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            head = handle.read(4096)
    except OSError:
        return None, ""
    schema = None
    match = _HEADER_SCHEMA_RE.search(head)
    if match:
        try:
            schema = int(match.group(1))
        except ValueError:
            schema = None
    built = ""
    match = _HEADER_BUILT_AT_RE.search(head)
    if match:
        built = match.group(1)
    return schema, built


def iter_index_notes(path: Path | str) -> Iterable[dict[str, Any]]:
    """Yield each notes[] object without retaining keyword arrays.

    Streams the file in chunks. Peak extra RAM is one note object (keywords
    dropped immediately). Fail-open: corrupt or oversized objects end iteration.
    """
    decoder = json.JSONDecoder()
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        buf = ""
        in_array = False
        while True:
            chunk = handle.read(65536)
            if chunk:
                buf += chunk
            elif not buf:
                return
            if not in_array:
                match = _NOTES_ARRAY_RE.search(buf)
                if not match:
                    if not chunk:
                        return
                    buf = buf[-128:]
                    continue
                buf = buf[match.end() :]
                in_array = True
            progressed = False
            while True:
                buf = buf.lstrip()
                if buf.startswith("]"):
                    return
                if buf.startswith(","):
                    buf = buf[1:]
                    progressed = True
                    continue
                if not buf.startswith("{"):
                    break
                try:
                    obj, end = decoder.raw_decode(buf)
                except json.JSONDecodeError:
                    break
                buf = buf[end:]
                progressed = True
                if isinstance(obj, dict):
                    obj.pop("keywords", None)
                    yield obj
            if not chunk and not progressed:
                return
            if len(buf) > 12_000_000:
                return


def _write_digest(
    digest_path: Path,
    *,
    schema_version: int,
    built_at: str,
    notes: list[dict[str, Any]],
) -> None:
    atomic_write_json(
        digest_path,
        {
            "schema_version": schema_version,
            "built_at": built_at,
            "notes": notes,
        },
    )


def build_digest_from_index(
    index_path: Path | str, digest_path: Path | str | None = None
) -> int:
    """Build the slim SessionStart sidecar from an existing full index.

    Never walks the vault. Missing/unreadable index → empty digest (fail-open).
    """
    source = Path(index_path)
    target = Path(digest_path) if digest_path else source.with_name(DIGEST_SIDECAR_NAME)
    schema_version = SCHEMA_VERSION
    built_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    selected: list[dict[str, Any]] = []
    try:
        if source.is_file():
            header_schema, header_built = _peek_index_header(source)
            if header_schema is not None:
                schema_version = header_schema
            if header_built:
                built_at = header_built
            selected = _select_digest_notes(iter_index_notes(source))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        selected = []
    _write_digest(
        target, schema_version=schema_version, built_at=built_at, notes=selected
    )
    return len(selected)


def build_index(vault: Path | str, target: Path | str) -> int:
    vault_path = Path(vault).resolve()
    target_path = Path(target)
    notes: list[dict[str, Any]] = []
    fingerprint = hashlib.sha256()
    now = time.time()
    if not vault_path.exists():
        raise FileNotFoundError(vault_path)

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
    try:
        _write_digest(
            target_path.with_name(DIGEST_SIDECAR_NAME),
            schema_version=SCHEMA_VERSION,
            built_at=str(document["built_at"]),
            notes=_select_digest_notes(notes),
        )
    except OSError:
        pass
    return len(notes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build the bounded lexical Basic Memory index"
    )
    parser.add_argument("--vault", default="D:/basic-memory")
    parser.add_argument(
        "--target", default=str(default_state_root() / "recall-index.json")
    )
    parser.add_argument(
        "--from-index",
        default="",
        help="Build slim recall-digest.json from an existing index (no vault scan)",
    )
    parser.add_argument(
        "--digest-target",
        default="",
        help="Override digest output path (used with --from-index)",
    )
    args = parser.parse_args(argv)
    try:
        if args.from_index:
            digest_target = args.digest_target or str(
                Path(args.from_index).with_name(DIGEST_SIDECAR_NAME)
            )
            count = build_digest_from_index(args.from_index, digest_target)
            print(f"SUCCESS:recall-digest notes={count}")
            return 0
        count = build_index(args.vault, args.target)
    except Exception as exc:
        print(f"FAILED:recall-index {type(exc).__name__}")
        return 1
    print(f"SUCCESS:recall-index notes={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
