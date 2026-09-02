"""Throwaway-HOME plugin upgrade that preserves user edits (IMP-0024).

Every target file of an upgrade from shipped vN (*base*) to shipped vN+1
(*theirs*) is classified against the live copy (*ours*):

* ``unchanged-by-user`` – live bytes equal shipped vN -> replaced by vN+1;
* ``merged-user-edit``  – the user changed it -> three-way merged (JSON is
  merged key-by-key preserving the user's key order, everything else is
  diff3 via ``three_way_merge.merge_lines`` with disjoint end-of-file
  insertions from both sides kept as a union);
* ``conflicted``        – both sides changed the same key / the same base
  lines differently -> the whole update stops and writes NOTHING.

Classification is a planning phase; bytes are written only when no target
is conflicted, so a conflict in one file never leaves a half-applied tree.
Live paths that are not part of the payload are never touched or deleted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:  # imported as ``plugin.update``
    from .three_way_merge import merge_lines
except ImportError:  # imported as top-level ``update`` (tools/plugin on sys.path)
    from three_way_merge import merge_lines

USER_ACCENT_VALUE = "user-accent-orchid"
USER_NOTE_LINE = "USER-OVERRIDE-IMP-0024-UNIQUE"
USER_THEME_VALUE = "user-theme-midnight"
USER_THEME_NOTE_LINE = "USER-THEME-IMP-0024-CONFLICT"
SHIPPED_THEME_VALUE = "shipped-theme-solar"
REVIEWER_COMMENT_LINE = "reviewer: key order is load-bearing"
UNCHANGED_BY_USER = "unchanged-by-user"
MERGED = "merged-user-edit"
CONFLICTED = "conflicted"
TOOK_THEIRS = "took-theirs"
REASON_MERGED = "merged-user-edits"
REASON_CONFLICT = "conflict"
REASON_NO_CLASSIFIER = "no-classifier"


def _json_bytes(doc: dict[str, Any]) -> bytes:
    return (json.dumps(doc, indent=2) + "\n").encode("utf-8")


def payload_v1() -> dict[str, bytes]:
    return {
        "notes.md": b"# plugin notes\nshipped-v1\n",
        "settings.json": _json_bytes({"accent": "default", "telemetry": True}),
    }


def payload_v2() -> dict[str, bytes]:
    return {
        "notes.md": b"# plugin notes\nshipped-v1\nshipped-v2\n",
        "settings.json": _json_bytes({"accent": "default", "telemetry": False}),
    }


def payload_v3() -> dict[str, bytes]:
    return {
        "notes.md": b"# plugin notes\nshipped-v1\nshipped-v2\nshipped-v3\n",
        "settings.json": _json_bytes(
            {"accent": "default", "telemetry": False, "keymap": "vim"}
        ),
    }


def payload_conflict_theirs() -> dict[str, bytes]:
    """Shipped vN+1 that introduces ``theme`` — the key the user also added.

    Pair with :func:`apply_user_theme_conflict` on a v1 tree: both sides add
    ``settings.json:theme`` with different values, which is a genuine
    conflict (neither side equals the base, and they disagree).
    """
    return {
        "notes.md": b"# plugin notes\nshipped-v1\nshipped-v2\n",
        "settings.json": _json_bytes(
            {"accent": "default", "telemetry": False, "theme": SHIPPED_THEME_VALUE}
        ),
    }


def seed_live_tree(root: Path, payload: dict[str, bytes], version: str = "1.0.0") -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "VERSION").write_text(version + "\n", encoding="utf-8")
    for rel, body in payload.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)


def apply_user_override(root: Path) -> dict[str, bytes]:
    root = Path(root)
    notes = (root / "notes.md").read_bytes() + (USER_NOTE_LINE + "\n").encode("ascii")
    (root / "notes.md").write_bytes(notes)
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    settings["accent"] = USER_ACCENT_VALUE
    encoded = _json_bytes(settings)
    (root / "settings.json").write_bytes(encoded)
    return {"notes.md": notes, "settings.json": encoded}


def apply_user_theme_conflict(root: Path) -> dict[str, bytes]:
    """User adds ``theme`` (and a notes line) — collides with :func:`payload_conflict_theirs`."""
    root = Path(root)
    notes = (root / "notes.md").read_bytes() + (USER_THEME_NOTE_LINE + "\n").encode("ascii")
    (root / "notes.md").write_bytes(notes)
    settings = json.loads((root / "settings.json").read_text(encoding="utf-8"))
    settings["theme"] = USER_THEME_VALUE
    encoded = _json_bytes(settings)
    (root / "settings.json").write_bytes(encoded)
    return {"notes.md": notes, "settings.json": encoded}


def parsed_settings(root: Path) -> dict[str, Any]:
    return json.loads((root / "settings.json").read_text(encoding="utf-8"))


def apply_reviewer_unanticipated(root: Path) -> dict[str, bytes]:
    """Reviewer edit: keys reordered (font, theme first) plus a comment on both files.

    The comment must survive as text in settings.json while the document stays
    ``json.loads``-able, so it travels inside a ``_comment`` string field.
    """
    root = Path(root)
    notes = (root / "notes.md").read_bytes() + (REVIEWER_COMMENT_LINE + "\n").encode("ascii")
    (root / "notes.md").write_bytes(notes)
    encoded = _json_bytes(
        {
            "font": "ibm-plex",
            "theme": "night",
            "accent": USER_ACCENT_VALUE,
            "telemetry": True,
            "_comment": REVIEWER_COMMENT_LINE,
        }
    )
    (root / "settings.json").write_bytes(encoded)
    return {"notes.md": notes, "settings.json": encoded}


def tree_sha(root: Path) -> str:
    """Deterministic sha256 over every file under *root* (posix relpath + bytes)."""
    root = Path(root)
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(rel + b"\0" + str(len(data)).encode("ascii") + b"\0" + data)
    return digest.hexdigest()


@dataclass
class FilePlan:
    relpath: str
    classification: str
    wrote: bool = True
    conflicts: list[str] = field(default_factory=list)


@dataclass
class UpdateResult:
    proceeded: bool = True
    wrote: bool = True
    reason: str = "merged"
    files: list[FilePlan] = field(default_factory=list)
    conflicted: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "proceeded": self.proceeded,
            "wrote": self.wrote,
            "reason": self.reason,
            "files": [asdict(f) for f in self.files],
            "conflicted": list(self.conflicted),
        }


def _merge_notes(base: bytes, live: bytes, theirs: bytes) -> bytes:
    """Union of live and theirs lines (live order first, duplicates dropped)."""
    del base
    live_lines = live.splitlines(keepends=True)
    theirs_lines = theirs.splitlines(keepends=True)
    out: list[bytes] = []
    seen: set[bytes] = set()
    for line in live_lines + theirs_lines:
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    if out and not out[-1].endswith(b"\n"):
        out.append(b"\n")
    return b"".join(out)


def _decode(data: bytes) -> str:
    return data.decode("utf-8").replace("\r\n", "\n")


def three_way_lines(base: bytes, live: bytes, theirs: bytes) -> tuple[bytes, list[str]]:
    """diff3 classification for line files -> (merged bytes, conflict regions).

    ``three_way_merge.merge_lines`` (IMP-0031) decides what conflicts. A
    region whose *base* side is empty means both sides inserted new lines at
    the same point (typically both appended at EOF); those are disjoint
    additions, resolved as the union of live then theirs lines. A region with
    base lines means both sides rewrote the same shipped lines differently:
    that is a real conflict and is reported instead of guessed.
    """
    result = merge_lines(_decode(base), _decode(live), _decode(theirs))
    real = [c.region for c in result.conflicts if c.base]
    if real:
        return b"", real
    if result.conflicts:
        return _merge_notes(base, live, theirs), []
    return (result.text or "").encode("utf-8"), []


_MISSING = object()


def three_way_settings(base: bytes, live: bytes, theirs: bytes) -> tuple[bytes, list[str]]:
    """Key-level three-way merge of JSON objects -> (merged bytes, conflicting keys).

    Per key: agreement wins; a side equal to base yields to the other side
    (including deletions); two different changes are a conflict. Key order is
    the user's (live) order, then keys only theirs added — the user's ordering
    is treated as load-bearing.
    """
    b = json.loads(base.decode("utf-8")) if base.strip() else {}
    o = json.loads(live.decode("utf-8")) if live.strip() else {}
    t = json.loads(theirs.decode("utf-8")) if theirs.strip() else {}
    if not (isinstance(b, dict) and isinstance(o, dict) and isinstance(t, dict)):
        if o == t or t == b:
            return _json_bytes(o) if isinstance(o, dict) else (json.dumps(o) + "\n").encode(), []
        if o == b:
            return theirs, []
        return b"", ["$"]
    order = list(o.keys()) + [k for k in t.keys() if k not in o] + [
        k for k in b.keys() if k not in o and k not in t
    ]
    merged: dict[str, Any] = {}
    conflicts: list[str] = []
    for key in order:
        bv, ov, tv = b.get(key, _MISSING), o.get(key, _MISSING), t.get(key, _MISSING)
        if ov is _MISSING and tv is _MISSING:
            continue
        if ov == tv:
            merged[key] = ov
        elif ov == bv:
            if tv is not _MISSING:
                merged[key] = tv
        elif tv == bv:
            if ov is not _MISSING:
                merged[key] = ov
        else:
            conflicts.append(key)
    if conflicts:
        return b"", conflicts
    return _json_bytes(merged), []


def _merge_settings(base: bytes, live: bytes, theirs: bytes) -> bytes:
    """Merged settings bytes; a conflicting key keeps the user's value (legacy helper)."""
    merged, conflicts = three_way_settings(base, live, theirs)
    if not conflicts:
        return merged
    o = json.loads(live.decode("utf-8")) if live.strip() else {}
    t = json.loads(theirs.decode("utf-8")) if theirs.strip() else {}
    doc = {**t, **o} if isinstance(o, dict) and isinstance(t, dict) else o
    return _json_bytes(doc) if isinstance(doc, dict) else (json.dumps(doc) + "\n").encode()


def classify(rel: str, base: bytes, live: bytes, theirs: bytes) -> tuple[FilePlan, bytes]:
    """Classify one target; returns the plan and the bytes that would be written."""
    if live == base:
        return FilePlan(rel, UNCHANGED_BY_USER, True), theirs
    if rel.lower().endswith((".json", ".jsonc", ".json5")):
        try:
            merged, conflicts = three_way_settings(base, live, theirs)
        except (UnicodeDecodeError, json.JSONDecodeError):
            merged, conflicts = three_way_lines(base, live, theirs)
    else:
        try:
            merged, conflicts = three_way_lines(base, live, theirs)
        except UnicodeDecodeError:
            merged, conflicts = b"", ["binary"]
    if conflicts:
        return FilePlan(rel, CONFLICTED, False, conflicts), b""
    return FilePlan(rel, MERGED, True), merged


def update(
    root: Path,
    base_payload: dict[str, bytes],
    theirs_payload: dict[str, bytes],
    from_version: str = "",
    to_version: str = "",
    classifier_enabled: bool = True,
) -> UpdateResult:
    """Upgrade *root* from *base_payload* to *theirs_payload*.

    With ``classifier_enabled=False`` (the negative control) every target is
    overwritten with theirs. Otherwise every target is classified first and
    nothing — not even VERSION — is written when any target is conflicted.
    """
    del from_version
    root = Path(root)
    if not classifier_enabled:
        plans: list[FilePlan] = []
        for rel, theirs in theirs_payload.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(theirs)
            plans.append(FilePlan(rel, TOOK_THEIRS, True))
        if to_version:
            (root / "VERSION").write_text(to_version + "\n", encoding="utf-8")
        return UpdateResult(True, True, REASON_NO_CLASSIFIER, plans)

    plans = []
    writes: dict[str, bytes] = {}
    conflicted: list[str] = []
    for rel, theirs in theirs_payload.items():
        base = base_payload.get(rel, b"")
        live_path = root / rel
        live = live_path.read_bytes() if live_path.is_file() else b""
        plan, data = classify(rel, base, live, theirs)
        plans.append(plan)
        if plan.classification == CONFLICTED:
            conflicted.append(rel)
        else:
            writes[rel] = data
    if conflicted:
        return UpdateResult(False, False, REASON_CONFLICT, plans, conflicted)
    for rel, data in writes.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    if to_version:
        (root / "VERSION").write_text(to_version + "\n", encoding="utf-8")
    return UpdateResult(True, True, REASON_MERGED, plans)


__all__ = [
    "CONFLICTED",
    "FilePlan",
    "MERGED",
    "REVIEWER_COMMENT_LINE",
    "SHIPPED_THEME_VALUE",
    "TOOK_THEIRS",
    "UNCHANGED_BY_USER",
    "USER_ACCENT_VALUE",
    "USER_NOTE_LINE",
    "USER_THEME_NOTE_LINE",
    "USER_THEME_VALUE",
    "UpdateResult",
    "apply_reviewer_unanticipated",
    "apply_user_override",
    "apply_user_theme_conflict",
    "classify",
    "parsed_settings",
    "payload_conflict_theirs",
    "payload_v1",
    "payload_v2",
    "payload_v3",
    "seed_live_tree",
    "three_way_lines",
    "three_way_settings",
    "tree_sha",
    "update",
]
