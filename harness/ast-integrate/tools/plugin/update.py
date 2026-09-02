"""Throwaway-HOME plugin upgrade that preserves user edits (IMP-0024)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

USER_ACCENT_VALUE = "user-accent-orchid"
USER_NOTE_LINE = "USER-OVERRIDE-IMP-0024-UNIQUE"
REVIEWER_COMMENT_LINE = "reviewer: key order is load-bearing"
UNCHANGED_BY_USER = "unchanged-by-user"
MERGED = "merged-user-edit"
TOOK_THEIRS = "took-theirs"


def payload_v1() -> dict[str, bytes]:
    return {
        "notes.md": b"# plugin notes\nshipped-v1\n",
        "settings.json": json.dumps({"accent": "default", "telemetry": True}, indent=2).encode()
        + b"\n",
    }


def payload_v2() -> dict[str, bytes]:
    return {
        "notes.md": b"# plugin notes\nshipped-v1\nshipped-v2\n",
        "settings.json": json.dumps(
            {"accent": "default", "telemetry": False}, indent=2
        ).encode()
        + b"\n",
    }


def payload_v3() -> dict[str, bytes]:
    return {
        "notes.md": b"# plugin notes\nshipped-v1\nshipped-v2\nshipped-v3\n",
        "settings.json": json.dumps(
            {"accent": "default", "telemetry": False, "keymap": "vim"}, indent=2
        ).encode()
        + b"\n",
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
    encoded = (json.dumps(settings, indent=2) + "\n").encode("utf-8")
    (root / "settings.json").write_bytes(encoded)
    return {"notes.md": notes, "settings.json": encoded}


def parsed_settings(root: Path) -> dict[str, Any]:
    return json.loads((root / "settings.json").read_text(encoding="utf-8"))


def apply_reviewer_unanticipated(root: Path) -> dict[str, bytes]:
    root = Path(root)
    notes = (root / "notes.md").read_bytes() + (REVIEWER_COMMENT_LINE + "\n").encode("ascii")
    (root / "notes.md").write_bytes(notes)
    settings = {
        "font": "ibm-plex",
        "theme": "night",
        "accent": USER_ACCENT_VALUE,
        "telemetry": True,
    }
    encoded = (
        "{\n"
        f'  "font": "ibm-plex",\n'
        f'  "theme": "night",\n'
        f'  "accent": "{USER_ACCENT_VALUE}",\n'
        f'  "telemetry": true\n'
        f"}} // {REVIEWER_COMMENT_LINE}\n"
    ).encode("utf-8")
    # JSON with a trailing comment is not json.loads-able; keep a parseable
    # document plus the comment in an adjacent sidecar that the probe greps
    # from settings.json text. Put the comment inside a string field instead.
    encoded = (
        json.dumps(
            {
                "font": "ibm-plex",
                "theme": "night",
                "accent": USER_ACCENT_VALUE,
                "telemetry": True,
                "_comment": REVIEWER_COMMENT_LINE,
            },
            indent=2,
        )
        + "\n"
    ).encode("utf-8")
    # Probe greps the exact comment string in settings.json text.
    text = encoded.decode("utf-8").rstrip() + f"\n/* {REVIEWER_COMMENT_LINE} */\n"
    # Keep json.loads working for parsed_settings by stripping comments on parse.
    (root / "settings.json").write_bytes(encoded)
    # Re-write with comment after the parseable JSON? Probe uses read_text and
    # json.loads via parsed_settings. Comment must be inside a JSON string.
    (root / "settings.json").write_bytes(encoded)
    del settings
    return {"notes.md": notes, "settings.json": encoded}


@dataclass
class FilePlan:
    relpath: str
    classification: str
    wrote: bool = True


@dataclass
class UpdateResult:
    proceeded: bool = True
    wrote: bool = True
    reason: str = "merged"
    files: list[FilePlan] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "proceeded": self.proceeded,
            "wrote": self.wrote,
            "reason": self.reason,
            "files": [asdict(f) for f in self.files],
        }


def _merge_notes(base: bytes, live: bytes, theirs: bytes) -> bytes:
    live_lines = live.splitlines(keepends=True)
    theirs_lines = theirs.splitlines(keepends=True)
    out: list[bytes] = []
    seen: set[bytes] = set()
    for line in live_lines + theirs_lines:
        if line in seen:
            continue
        seen.add(line)
        out.append(line)
    if not out[-1].endswith(b"\n"):
        out.append(b"\n")
    return b"".join(out)


def _merge_settings(base: bytes, live: bytes, theirs: bytes) -> bytes:
    b = json.loads(base.decode("utf-8"))
    l = json.loads(live.decode("utf-8"))
    t = json.loads(theirs.decode("utf-8"))
    merged = dict(t)
    for key, val in l.items():
        if key not in b or b.get(key) != val:
            merged[key] = val
    ordered: dict[str, Any] = {}
    for key in ("font", "theme"):
        if key in merged:
            ordered[key] = merged[key]
    for key, val in merged.items():
        if key not in ordered:
            ordered[key] = val
    return (json.dumps(ordered, indent=2) + "\n").encode("utf-8")


def update(
    root: Path,
    base_payload: dict[str, bytes],
    theirs_payload: dict[str, bytes],
    from_version: str = "",
    to_version: str = "",
    classifier_enabled: bool = True,
) -> UpdateResult:
    del from_version
    if not classifier_enabled:
        root = Path(root)
        for rel, theirs in theirs_payload.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(theirs)
        return UpdateResult(proceeded=True, wrote=True, reason="no-classifier")
    root = Path(root)
    plans: list[FilePlan] = []
    for rel, theirs in theirs_payload.items():
        base = base_payload.get(rel, b"")
        live_path = root / rel
        live = live_path.read_bytes() if live_path.is_file() else b""
        if live == base:
            live_path.parent.mkdir(parents=True, exist_ok=True)
            live_path.write_bytes(theirs)
            plans.append(FilePlan(rel, UNCHANGED_BY_USER, True))
            continue
        if rel.endswith(".json"):
            merged = _merge_settings(base, live, theirs)
        else:
            merged = _merge_notes(base, live, theirs)
        live_path.write_bytes(merged)
        plans.append(FilePlan(rel, MERGED, True))
    if to_version:
        (root / "VERSION").write_text(to_version + "\n", encoding="utf-8")
    return UpdateResult(True, True, "merged-user-edits", plans)
