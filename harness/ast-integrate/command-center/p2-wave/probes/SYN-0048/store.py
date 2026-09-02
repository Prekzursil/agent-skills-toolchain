"""Durable program-memory notes: supersede, never delete; edges read back from disk."""
from __future__ import annotations

import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PERMALINK_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class DeleteForbidden(RuntimeError):
    """Catalog failure class deleted-instead-of-superseded."""


class StoreError(RuntimeError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_write(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


class NoteStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, permalink: str) -> Path:
        if not PERMALINK_RE.fullmatch(permalink):
            raise StoreError(f"illegal permalink {permalink!r}")
        return self.root / f"{permalink}.json"

    def write_new(self, note: dict) -> dict:
        permalink = str(note["permalink"])
        dest = self.path_for(permalink)
        if dest.exists():
            raise StoreError(f"note already exists: {permalink}")
        payload = {
            "body": note["body"],
            "created_at": note.get("created_at") or now_iso(),
            "kind": note.get("kind") or "program-memory",
            "permalink": permalink,
            "superseded_by": None,
            "title": note["title"],
            "valid_as_of": note.get("valid_as_of"),
        }
        atomic_write(dest, payload)
        return self.read(permalink)

    def read(self, permalink: str) -> dict:
        dest = self.path_for(permalink)
        if not dest.is_file():
            raise StoreError(f"RESOLVE failed: {permalink} does not exist")
        return json.loads(dest.read_text(encoding="utf-8"))

    def exists(self, permalink: str) -> bool:
        return self.path_for(permalink).is_file()

    def all_notes(self) -> list[dict]:
        notes = []
        for path in sorted(self.root.glob("*.json")):
            notes.append(json.loads(path.read_text(encoding="utf-8")))
        return notes

    def supersede(self, old_permalink: str, new_note: dict) -> dict:
        old = self.read(old_permalink)
        if old.get("superseded_by"):
            existing = old["superseded_by"]
            wanted = new_note.get("permalink")
            if wanted and wanted != existing:
                raise StoreError(
                    f"{old_permalink} already superseded by {existing}, not {wanted}"
                )
            return self.edge(old_permalink)
        new_note = dict(new_note)
        if not new_note.get("valid_as_of"):
            new_note["valid_as_of"] = now_iso()
        written = self.write_new(new_note)
        old["superseded_by"] = written["permalink"]
        atomic_write(self.path_for(old_permalink), old)
        return self.edge(old_permalink)

    def edge(self, old_permalink: str) -> dict:
        old_rb = self.read(old_permalink)
        new_id = old_rb.get("superseded_by")
        if not new_id:
            raise StoreError(f"{old_permalink} has no superseded_by after write")
        new_rb = self.read(new_id)
        if not new_rb.get("valid_as_of"):
            raise StoreError(f"successor {new_id} missing valid_as_of")
        if old_rb.get("superseded_by") != new_rb["permalink"]:
            raise StoreError("read-back superseded_by mismatch")
        return {
            "new_id": new_rb["permalink"],
            "new_valid_as_of": new_rb["valid_as_of"],
            "old_id": old_permalink,
            "old_superseded_by": old_rb["superseded_by"],
            "read_back": True,
            "store": self.root.as_posix(),
        }

    def delete(self, permalink: str) -> None:
        raise DeleteForbidden(
            f"notes are superseded, never deleted: {permalink}"
        )

    def audit_edges(self) -> list[dict]:
        graph: dict[str, str] = {}
        for note in self.all_notes():
            target = note.get("superseded_by")
            if target:
                graph[note["permalink"]] = target
        for start, target in graph.items():
            self.read(target)
        for start in graph:
            seen: set[str] = set()
            cur = start
            while cur in graph:
                if cur in seen:
                    raise StoreError(f"ACYCLIC failed: cycle at {cur}")
                seen.add(cur)
                cur = graph[cur]
        edges = []
        for old_id in sorted(graph):
            edges.append(self.edge(old_id))
        return edges


def run_self_check(tmp_root: Path | None = None) -> dict:
    """Isolated store battery used by emit and probe2."""
    cleanup = False
    if tmp_root is None:
        tmp_root = Path(tempfile.mkdtemp(prefix="syn0048-store-"))
        cleanup = True
    store = NoteStore(tmp_root)
    old = store.write_new(
        {
            "body": "stale: resume from STATUS.md; delete this note when obsolete",
            "permalink": "old-resume-source",
            "title": "Stale resume pointer",
        }
    )
    edge = store.supersede(
        old["permalink"],
        {
            "body": "current: resume from the handoff package",
            "permalink": "new-resume-source",
            "title": "Current resume pointer",
        },
    )
    if edge["read_back"] is not True:
        raise StoreError("read_back is not True")
    if store.read("old-resume-source")["superseded_by"] != "new-resume-source":
        raise StoreError("old note missing superseded_by on read-back")
    if not store.read("new-resume-source").get("valid_as_of"):
        raise StoreError("successor missing valid_as_of on read-back")
    try:
        store.delete("old-resume-source")
        raise StoreError("delete() did not refuse")
    except DeleteForbidden:
        pass
    if not store.path_for("old-resume-source").is_file():
        raise StoreError("delete attempt removed the note")
    if not store.path_for("new-resume-source").is_file():
        raise StoreError("successor vanished")

    broken = NoteStore(tmp_root / "broken")
    broken.write_new(
        {
            "body": "planted broken chain",
            "permalink": "broken-old",
            "title": "Broken",
        }
    )
    dangling = broken.read("broken-old")
    dangling["superseded_by"] = "does-not-exist"
    atomic_write(broken.path_for("broken-old"), dangling)
    resolve_fired = False
    try:
        broken.audit_edges()
    except StoreError as exc:
        resolve_fired = "RESOLVE" in str(exc) or "does not exist" in str(exc)
    if not resolve_fired:
        raise StoreError("planted broken chain did not fire RESOLVE")

    notes_present = sorted(p.name for p in store.root.glob("*.json"))
    if cleanup:
        # Leave tmp for the caller if they passed a root; otherwise best-effort.
        pass
    return {
        "delete_refused": True,
        "edge": edge,
        "notes_present": notes_present,
        "resolve_control_fired": True,
    }
