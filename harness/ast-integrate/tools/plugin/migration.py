"""Versioned migration steps: apply, inverse, dry-run, resume, target cap."""
from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_REL = "tools/plugin/schema/migration-step.schema.json"
JOURNAL_SCHEMA = "imp-0047-migration-journal/v1"
VERSION_FILE = "layout-version"
DEFAULT_CONFIG = {
    "layout": "copied-skills",
    "token_file": "root.json",
}


class MigrationError(Exception):
    pass


def dump_json(doc: Any) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _posix(path: str | Path) -> str:
    return str(path).replace("\\", "/")


def sha256_file_census(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            out[rel] = hashlib.sha256(raw).hexdigest()
    return out


def blake2_tree_digest(root: Path) -> str:
    h = hashlib.blake2b()
    for rel, digest in sorted(sha256_file_census(root).items()):
        path = root / rel
        size = path.stat().st_size if path.is_file() else 0
        body = path.read_bytes() if path.is_file() else b""
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(str(size).encode("ascii"))
        h.update(b"\0")
        h.update(body)
    return h.hexdigest()


def censuses(root: Path) -> dict[str, Any]:
    files = sha256_file_census(root)
    return {
        "file_census": files,
        "file_count": len(files),
        "blake2": blake2_tree_digest(root),
    }


def censuses_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return a.get("file_census") == b.get("file_census") and a.get("blake2") == b.get("blake2")


def validate_step_spec(spec: dict[str, Any]) -> None:
    if not isinstance(spec, dict):
        raise MigrationError("step spec is not an object")
    if not str(spec.get("id") or "").strip():
        raise MigrationError("step id missing")
    if not str(spec.get("description") or "").strip():
        raise MigrationError("step description missing")
    inverse = spec.get("inverse")
    if not isinstance(inverse, str) or not inverse.strip():
        raise MigrationError(f"step {spec.get('id')} has empty inverse")


def demo_step_specs() -> list[dict[str, Any]]:
    return [
        {
            "id": "s1-relocate-key",
            "description": "Relocate token_file to key_location and bump layout-version to 1.",
            "inverse": "restore-token-file-from-key-location",
            "from_version": "0",
            "to_version": "1",
        },
        {
            "id": "s2-move-skill",
            "description": "Move skills/legacy/SKILL.md to skills/core/SKILL.md.",
            "inverse": "restore-legacy-skill-path",
            "from_version": "1",
            "to_version": "2",
        },
        {
            "id": "s3-dispatch-hooks",
            "description": "Replace hooks/old.json with hooks/dispatch.json.",
            "inverse": "restore-hooks-old",
            "from_version": "2",
            "to_version": "3",
        },
    ]


def wrong_inverse_spec() -> dict[str, Any]:
    return {
        "id": "s-wrong-inverse",
        "description": "Writes a marker whose inverse does not restore the prior tree.",
        "inverse": "write-a-different-marker",
        "from_version": "0",
        "to_version": "1",
        "wrong_inverse": True,
    }


def build_demo_tree(root: Path) -> Path:
    root = Path(root)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / "config.json").write_text(dump_json(dict(DEFAULT_CONFIG)), encoding="utf-8")
    (root / VERSION_FILE).write_text("0\n", encoding="utf-8")
    (root / "root.json").write_text('{"token":"demo"}\n', encoding="utf-8")
    (root / "hooks").mkdir()
    (root / "hooks" / "old.json").write_text('{"hook":"old"}\n', encoding="utf-8")
    (root / "skills" / "legacy").mkdir(parents=True)
    (root / "skills" / "legacy" / "SKILL.md").write_text("legacy-skill\n", encoding="utf-8")
    return root


def _read_version(root: Path) -> str:
    path = root / VERSION_FILE
    if not path.is_file():
        return "0"
    return path.read_text(encoding="utf-8").strip() or "0"


def _write_version(root: Path, version: str) -> None:
    (root / VERSION_FILE).write_text(f"{version}\n", encoding="utf-8")


def _load_config(root: Path) -> dict[str, Any]:
    raw = (root / "config.json").read_bytes()
    return json.loads(raw.decode("utf-8"))


def _write_config(root: Path, doc: dict[str, Any], crlf: bool = False) -> None:
    text = dump_json(doc)
    data = text.encode("utf-8")
    if crlf:
        data = data.replace(b"\n", b"\r\n")
    (root / "config.json").write_bytes(data)


def _apply_s1(root: Path) -> list[dict[str, Any]]:
    mutations: list[dict[str, Any]] = []
    cfg_path = root / "config.json"
    crlf = cfg_path.is_file() and b"\r\n" in cfg_path.read_bytes()
    doc = _load_config(root)
    token = doc.pop("token_file", None)
    if token is not None:
        doc["key_location"] = token
        mutations.append({"op": "rename-key", "path": "config.json", "byte_delta": 0})
    if doc.get("layout") not in {"copied-skills", "v1-relocated-key"}:
        doc["layout"] = "copied-skills"
        mutations.append({"op": "normalize-layout", "path": "config.json", "byte_delta": 0})
    _write_config(root, doc, crlf=crlf)
    src = root / "root.json"
    dest = root / "keys" / "root.json"
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        src.unlink()
        mutations.append({"op": "move", "path": "keys/root.json", "byte_delta": dest.stat().st_size})
    _write_version(root, "1")
    mutations.append({"op": "version", "path": VERSION_FILE, "byte_delta": 2})
    return mutations


def _inverse_s1(root: Path) -> None:
    cfg_path = root / "config.json"
    crlf = cfg_path.is_file() and b"\r\n" in cfg_path.read_bytes()
    doc = _load_config(root)
    loc = doc.pop("key_location", None)
    if loc is not None:
        doc["token_file"] = loc
    _write_config(root, doc, crlf=crlf)
    src = root / "keys" / "root.json"
    dest = root / "root.json"
    if src.is_file():
        dest.write_bytes(src.read_bytes())
        src.unlink()
    _write_version(root, "0")


def _apply_s2(root: Path) -> list[dict[str, Any]]:
    src = root / "skills" / "legacy" / "SKILL.md"
    dest = root / "skills" / "core" / "SKILL.md"
    mutations = []
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        src.unlink()
        mutations.append({"op": "move", "path": "skills/core/SKILL.md", "byte_delta": dest.stat().st_size})
    _write_version(root, "2")
    mutations.append({"op": "version", "path": VERSION_FILE, "byte_delta": 2})
    return mutations


def _inverse_s2(root: Path) -> None:
    src = root / "skills" / "core" / "SKILL.md"
    dest = root / "skills" / "legacy" / "SKILL.md"
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        src.unlink()
    _write_version(root, "1")


def _apply_s3(root: Path) -> list[dict[str, Any]]:
    mutations = []
    old = root / "hooks" / "old.json"
    new = root / "hooks" / "dispatch.json"
    if old.is_file():
        old.unlink()
        mutations.append({"op": "delete", "path": "hooks/old.json", "byte_delta": -1})
    new.parent.mkdir(parents=True, exist_ok=True)
    body = b'{"hook":"dispatch"}\n'
    new.write_bytes(body)
    mutations.append({"op": "write", "path": "hooks/dispatch.json", "byte_delta": len(body)})
    _write_version(root, "3")
    mutations.append({"op": "version", "path": VERSION_FILE, "byte_delta": 2})
    return mutations


def _inverse_s3(root: Path) -> None:
    new = root / "hooks" / "dispatch.json"
    old = root / "hooks" / "old.json"
    if new.is_file():
        new.unlink()
    old.parent.mkdir(parents=True, exist_ok=True)
    old.write_text('{"hook":"old"}\n', encoding="utf-8")
    _write_version(root, "2")


def _apply_wrong(root: Path) -> list[dict[str, Any]]:
    marker = root / "wrong-apply.txt"
    marker.write_text("applied\n", encoding="utf-8")
    _write_version(root, "1")
    return [{"op": "write", "path": "wrong-apply.txt", "byte_delta": 8}]


def _inverse_wrong(root: Path) -> None:
    (root / "wrong-inverse.txt").write_text("not-a-restore\n", encoding="utf-8")


_APPLY = {
    "s1-relocate-key": _apply_s1,
    "s2-move-skill": _apply_s2,
    "s3-dispatch-hooks": _apply_s3,
    "s-wrong-inverse": _apply_wrong,
}
_INVERSE = {
    "s1-relocate-key": _inverse_s1,
    "s2-move-skill": _inverse_s2,
    "s3-dispatch-hooks": _inverse_s3,
    "s-wrong-inverse": _inverse_wrong,
}


class Step:
    def __init__(self, spec: dict[str, Any]):
        validate_step_spec(spec)
        self.spec = spec
        self.id = str(spec["id"])
        self.from_version = str(spec.get("from_version") or "0")
        self.to_version = str(spec.get("to_version") or "1")
        self.apply_calls = 0
        self.inverse_calls = 0

    def apply(self, root: Path) -> list[dict[str, Any]]:
        self.apply_calls += 1
        fn = _APPLY.get(self.id)
        if fn is None:
            raise MigrationError(f"no apply for {self.id}")
        return fn(root)

    def invert(self, root: Path) -> None:
        self.inverse_calls += 1
        fn = _INVERSE.get(self.id)
        if fn is None:
            raise MigrationError(f"no inverse for {self.id}")
        fn(root)


def _load_journal(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {
            "schema": JOURNAL_SCHEMA,
            "status": "idle",
            "current_version": "0",
            "applied_step_ids": [],
        }
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "schema": JOURNAL_SCHEMA,
            "status": "idle",
            "current_version": "0",
            "applied_step_ids": [],
        }
    if not isinstance(doc, dict):
        return {
            "schema": JOURNAL_SCHEMA,
            "status": "idle",
            "current_version": "0",
            "applied_step_ids": [],
        }
    doc.setdefault("applied_step_ids", [])
    doc.setdefault("schema", JOURNAL_SCHEMA)
    return doc


def _write_journal(path: Path | None, doc: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class MigrationEngine:
    def __init__(self, steps: list[Step] | None = None):
        self.steps = list(steps) if steps is not None else [Step(s) for s in demo_step_specs()]
        self.by_id = {s.id: s for s in self.steps}

    def migrate(
        self,
        root: Path,
        target: str,
        *,
        journal: Path | None = None,
        dry_run: bool = False,
        resume: bool = True,
        kill_after: str | None = None,
    ) -> dict[str, Any]:
        root = Path(root)
        jdoc = _load_journal(journal)
        if jdoc.get("status") == "failed" and not dry_run:
            raise MigrationError("failed journal must be inverted before retry")
        already = list(jdoc.get("applied_step_ids") or []) if resume else []
        already_set = set(already)
        target_i = int(target)
        planned = [s for s in self.steps if int(s.to_version) <= target_i]
        to_run = [s for s in planned if s.id not in already_set]

        if dry_run:
            shadow = root.parent / (root.name + ".dry-shadow")
            if shadow.exists():
                shutil.rmtree(shadow)
            shutil.copytree(root, shadow)
            mutations: list[dict[str, Any]] = []
            applied_ids: list[str] = []
            for step in to_run:
                mutations.extend(step.apply(shadow))
                applied_ids.append(step.id)
            shutil.rmtree(shadow, ignore_errors=True)
            return {
                "status": "complete",
                "dry_run": True,
                "current_version": target,
                "applied_step_ids": already + applied_ids,
                "newly_applied_step_ids": applied_ids,
                "mutations": mutations or [{"op": "noop", "path": ".", "byte_delta": 0}],
                "rendering": "shadow-copy apply; live tree and caller journal untouched",
            }

        newly: list[str] = []
        mutations = []
        status = "complete"
        for step in to_run:
            mutations.extend(step.apply(root))
            newly.append(step.id)
            already.append(step.id)
            jdoc["applied_step_ids"] = list(already)
            jdoc["current_version"] = step.to_version
            jdoc["status"] = "in_progress"
            _write_journal(journal, jdoc)
            if kill_after is not None and step.id == kill_after:
                status = "in_progress"
                break
        if status == "complete":
            jdoc["status"] = "complete"
            jdoc["current_version"] = str(target)
            _write_journal(journal, jdoc)
        return {
            "status": status,
            "dry_run": False,
            "current_version": _read_version(root),
            "applied_step_ids": list(already),
            "newly_applied_step_ids": newly,
            "mutations": mutations,
            "rendering": "live apply",
        }

    def invert(self, root: Path, target: str, *, journal: Path | None = None) -> dict[str, Any]:
        root = Path(root)
        jdoc = _load_journal(journal)
        applied = list(jdoc.get("applied_step_ids") or [])
        if not applied:
            current = _read_version(root)
            applied = [s.id for s in self.steps if int(s.to_version) <= int(current)]
        inverted: list[str] = []
        target_i = int(target)
        for step_id in reversed(applied):
            step = self.by_id.get(step_id)
            if step is None:
                continue
            if int(step.from_version) < target_i:
                break
            step.invert(root)
            inverted.append(step_id)
        remaining = [sid for sid in applied if sid not in inverted]
        jdoc["applied_step_ids"] = remaining
        jdoc["status"] = "complete" if remaining else "idle"
        jdoc["current_version"] = _read_version(root)
        jdoc.pop("failed_step", None)
        _write_journal(journal, jdoc)
        return {
            "status": "complete",
            "current_version": _read_version(root),
            "inverted_step_ids": inverted,
        }


def demo_engine() -> MigrationEngine:
    return MigrationEngine()
