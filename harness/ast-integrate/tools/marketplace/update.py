"""Preview-then-apply plugin update with permission widening consent (IMP-0087)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from plugin.permission_diff import independent_set_containment


class PreviewFidelityError(RuntimeError):
    pass


class UpdateAborted(RuntimeError):
    def __init__(self, reason: str = "update aborted") -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class Preview:
    version_delta: dict[str, str]
    changelog: dict[str, Any]
    permission_diff: dict[str, Any]
    independent_containment_verdict: str
    file_changes: dict[str, list[dict[str, str]]]
    expected_files: dict[str, int]
    expected_permissions: list[str]


def write_package_tree(dest: Path, pkg: Any) -> None:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for rel, data in (pkg.files or {}).items():
        out = dest / str(rel)
        out.parent.mkdir(parents=True, exist_ok=True)
        raw = data if isinstance(data, (bytes, bytearray)) else str(data).encode("utf-8")
        out.write_bytes(raw)


def census_tree(root: Path) -> dict[str, int]:
    root = Path(root)
    out: dict[str, int] = {}
    if not root.exists():
        return out
    for path in root.rglob("*"):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            out[rel] = path.stat().st_size
    return out


def effective_permissions_from_disk(dest: Path) -> list[str]:
    manifest = Path(dest) / "plugin.json"
    if not manifest.is_file():
        return []
    import json

    doc = json.loads(manifest.read_text(encoding="utf-8"))
    return [str(p) for p in (doc.get("permissions") or [])]


def preview_update(installed: Any, candidate: Any) -> Preview:
    from_v = str(installed.version)
    to_v = str(candidate.version)
    releases = list(candidate.releases or [])
    expected_versions: list[str] = []
    if from_v in releases and to_v in releases:
        i = releases.index(from_v)
        j = releases.index(to_v)
        expected_versions = releases[i + 1 : j + 1]
    else:
        expected_versions = [to_v]
    changelog = dict(candidate.changelog or {})
    entries = []
    gaps = []
    for ver in expected_versions:
        notes = changelog.get(ver)
        gap = notes is None
        if gap:
            gaps.append(ver)
        entries.append({"version": ver, "gap": gap, "notes": notes or []})
    inst_files = set((installed.files or {}).keys())
    cand_files = set((candidate.files or {}).keys())
    added = sorted(cand_files - inst_files)
    removed = sorted(inst_files - cand_files)
    changed = sorted(
        rel
        for rel in (inst_files & cand_files)
        if (installed.files or {}).get(rel) != (candidate.files or {}).get(rel)
    )
    containment = independent_set_containment(installed.permissions, candidate.permissions)
    expected_files = {rel: len(candidate.files[rel]) for rel in cand_files}
    added_perms = sorted(set(candidate.permissions) - set(installed.permissions))
    return Preview(
        version_delta={"from": from_v, "to": to_v},
        changelog={
            "gaps": gaps,
            "expected_versions": expected_versions,
            "entries": entries,
        },
        permission_diff={
            "verdict": containment,
            "from": list(installed.permissions),
            "to": list(candidate.permissions),
            "added": added_perms,
        },
        independent_containment_verdict=containment,
        file_changes={
            "added": [{"path": p} for p in added],
            "removed": [{"path": p} for p in removed],
            "modified": [{"path": p} for p in changed],
        },
        expected_files=expected_files,
        expected_permissions=list(candidate.permissions),
    )


def underreported_preview(preview: Preview, extra_path: str) -> Preview:
    clone = Preview(
        version_delta=dict(preview.version_delta),
        changelog=dict(preview.changelog),
        permission_diff=dict(preview.permission_diff),
        independent_containment_verdict=preview.independent_containment_verdict,
        file_changes={k: list(v) for k, v in preview.file_changes.items()},
        expected_files=dict(preview.expected_files),
        expected_permissions=list(preview.expected_permissions),
    )
    clone.file_changes["added"] = [r for r in clone.file_changes["added"] if r["path"] != extra_path]
    clone.expected_files.pop(extra_path, None)
    return clone


def apply_update(
    dest: Path,
    installed: Any,
    candidate: Any,
    *,
    consent_store: Any = None,
    preview: Preview | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    prev = preview or preview_update(installed, candidate)
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    if prev.permission_diff.get("verdict") == "widen":
        added = set(candidate.permissions) - set(installed.permissions)
        allowed = False
        if consent_store is not None and hasattr(consent_store, "allows"):
            allowed = bool(
                consent_store.allows(
                    candidate.name, installed.version, candidate.version, added
                )
            )
        elif consent_store is not None and getattr(consent_store, "_items", None):
            allowed = True
        if not allowed:
            raise UpdateAborted("permission-widening-requires-consent")
    write_package_tree(dest, candidate)
    return {"ok": True, "applied": True, "dest": str(dest), "version": candidate.version}


def assert_preview_matches_actual(preview: Preview, dest: Path) -> bool:
    live_files = census_tree(dest)
    live_perms = effective_permissions_from_disk(dest)
    if live_files != preview.expected_files:
        raise PreviewFidelityError("file census != preview.expected_files")
    if list(live_perms) != list(preview.expected_permissions):
        raise PreviewFidelityError("permissions != preview.expected_permissions")
    return True
