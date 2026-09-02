"""Uninstall owned plugin paths while retaining user data (IMP-0027).

Two entry points share this module:

* ``uninstall(home, projection, purge_user_data=False)`` removes the paths a
  projection declares as plugin-owned and never touches ``user-data`` unless
  asked (IMP-0027).
* ``uninstall_plugin(profile, claim)`` performs a claimed-path uninstall on a
  disposable host profile: only paths under ``plugins/<plugin_name>/`` may be
  claimed, every path must stay inside the profile, and shared host JSON
  documents (hooks/mcp/settings) are edited surgically so unrelated
  components survive (ADV-0120 / ADV-0021).

``naive_empty_shared_json`` is the deliberately destructive negative control
that empties the shared documents wholesale; it exists so the collateral
damage probes can show that a file-inventory check alone does not catch it.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

DISPOSABLE_MARKER = ".disposable-profile.json"
PLUGINS_DIR = "plugins"
SHARED_JSON_DOCS = ("host/hooks.json", "host/mcp.json", "host/settings.json")


class UninstallError(Exception):
    pass


def uninstall(home: Path, projection: Any, purge_user_data: bool = False) -> dict[str, Any]:
    home = Path(home)
    rels = []
    if hasattr(projection, "owned_relpaths"):
        rels = list(projection.owned_relpaths())
    elif isinstance(projection, dict):
        rels = list(projection.get("owned") or [])
    removed = []
    for rel in rels:
        path = home / rel
        if path.is_file():
            path.unlink()
            removed.append(str(rel))
        elif path.is_dir():
            shutil.rmtree(path)
            removed.append(str(rel))
    if purge_user_data:
        user_root = home / "user-data"
        if user_root.exists():
            shutil.rmtree(user_root)
    # prune empty owned directories
    for rel in sorted(rels, key=lambda r: r.count("/"), reverse=True):
        parent = (home / rel).parent
        if parent != home and parent.is_dir() and not any(parent.iterdir()):
            try:
                parent.rmdir()
            except OSError:
                pass
    return {"removed": removed, "purge_user_data": bool(purge_user_data)}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UninstallError(f"shared document unreadable: {path.name}: {exc}") from exc


def _dump_json(path: Path, doc: Any) -> None:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require_disposable_profile(profile: Path) -> dict[str, Any]:
    """Return the disposable marker document or raise UninstallError.

    A profile without ``.disposable-profile.json`` declaring ``disposable: true``
    is treated as a live user profile and the uninstall is refused.
    """
    marker = Path(profile) / DISPOSABLE_MARKER
    if not marker.is_file():
        raise UninstallError(
            f"refusing uninstall: {DISPOSABLE_MARKER} missing; profile may be live"
        )
    try:
        doc = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UninstallError(f"refusing uninstall: unreadable disposable marker: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("disposable") is not True:
        raise UninstallError("refusing uninstall: disposable marker does not declare disposable=true")
    return doc


def resolve_claimed_path(profile: Path, plugin_name: str, rel: str) -> Path:
    """Validate one claimed relative path and return its absolute location.

    The path must be relative, must resolve inside ``profile`` and must lie
    under ``plugins/<plugin_name>/``; anything else raises UninstallError.
    """
    profile = Path(profile).resolve()
    rel_text = str(rel).replace("\\", "/")
    candidate = Path(rel_text)
    if candidate.is_absolute() or not rel_text or rel_text.startswith("/"):
        raise UninstallError(f"claimed path escapes profile: {rel!r} is absolute")
    target = (profile / candidate).resolve()
    try:
        inside = target.relative_to(profile)
    except ValueError as exc:
        raise UninstallError(f"claimed path escapes profile: {rel!r}") from exc
    parts = inside.parts
    if ".." in candidate.parts:
        raise UninstallError(f"claimed path escapes profile: {rel!r} uses '..'")
    if len(parts) < 3 or parts[0] != PLUGINS_DIR or parts[1] != plugin_name:
        raise UninstallError(
            f"claimed path {rel!r} lies outside plugins/{plugin_name}/; refusing"
        )
    return target


def _walk_path(doc: Any, path: list[str], file_rel: str) -> Any:
    node = doc
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise UninstallError(f"claimed_json path {path!r} absent in {file_rel}")
        node = node[key]
    return node


def apply_json_claim(profile: Path, entry: dict[str, Any]) -> dict[str, Any]:
    """Remove exactly the claimed member from one shared JSON document.

    ``array_path`` + ``match_key``/``match_value`` removes matching rows from an
    array; ``object_path`` + ``key`` pops one key from an object. Every other
    member of the document is rewritten unchanged.
    """
    file_rel = str(entry.get("file") or "")
    if not file_rel or file_rel.startswith("/") or ".." in Path(file_rel).parts:
        raise UninstallError(f"claimed_json file escapes profile: {file_rel!r}")
    path = Path(profile) / file_rel
    if not path.is_file():
        return {"file": file_rel, "removed": 0, "missing": True}
    doc = _load_json(path)
    removed = 0
    if "array_path" in entry:
        arr = _walk_path(doc, [str(k) for k in entry["array_path"]], file_rel)
        if not isinstance(arr, list):
            raise UninstallError(f"claimed_json array_path is not an array in {file_rel}")
        match_key = str(entry.get("match_key") or "id")
        match_value = entry.get("match_value")
        kept = [row for row in arr if not (isinstance(row, dict) and row.get(match_key) == match_value)]
        removed = len(arr) - len(kept)
        arr[:] = kept
    elif "object_path" in entry:
        obj = _walk_path(doc, [str(k) for k in entry["object_path"]], file_rel)
        if not isinstance(obj, dict):
            raise UninstallError(f"claimed_json object_path is not an object in {file_rel}")
        key = str(entry.get("key") or "")
        if key in obj:
            del obj[key]
            removed = 1
    else:
        raise UninstallError(f"claimed_json entry for {file_rel} has neither array_path nor object_path")
    _dump_json(path, doc)
    return {"file": file_rel, "removed": removed, "missing": False}


def _claim_uninstall(profile: Path, claim: dict[str, Any]) -> dict[str, Any]:
    profile = Path(profile)
    plugin_name = str(claim.get("plugin_name") or "")
    if not plugin_name or "/" in plugin_name or plugin_name in (".", ".."):
        raise UninstallError(f"invalid plugin_name {plugin_name!r}")
    marker = require_disposable_profile(profile)
    claimed = [str(p) for p in (claim.get("claimed_paths") or [])]
    # validate everything before touching anything: a single bad claim aborts the run
    targets = [resolve_claimed_path(profile, plugin_name, rel) for rel in claimed]
    json_claims = [dict(e) for e in (claim.get("claimed_json") or [])]
    for entry in json_claims:
        file_rel = str(entry.get("file") or "")
        if not file_rel or file_rel.startswith("/") or ".." in Path(file_rel).parts:
            raise UninstallError(f"claimed_json file escapes profile: {file_rel!r}")

    removed: list[str] = []
    absent: list[str] = []
    for rel, target in zip(claimed, targets):
        if target.is_file() or target.is_symlink():
            target.unlink()
            removed.append(rel)
        elif target.is_dir():
            shutil.rmtree(target)
            removed.append(rel)
        else:
            absent.append(rel)

    json_edits = [apply_json_claim(profile, entry) for entry in json_claims]

    pruned: list[str] = []
    plugin_root = (profile / PLUGINS_DIR / plugin_name).resolve()
    if plugin_root.is_dir():
        for sub in sorted(plugin_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
                pruned.append(str(sub.relative_to(profile.resolve())))
        if not any(plugin_root.iterdir()):
            plugin_root.rmdir()
            pruned.append(f"{PLUGINS_DIR}/{plugin_name}")
    claim_file = profile / f".uninstall-claim-{plugin_name}.json"
    consumed_claim = False
    if claim_file.is_file():
        claim_file.unlink()
        consumed_claim = True
    return {
        "ok": True,
        "mode": "claimed-path",
        "plugin_name": plugin_name,
        "disposable_unit": marker.get("unit_id"),
        "removed_paths": removed,
        "absent_paths": absent,
        "pruned_dirs": pruned,
        "json_edits": json_edits,
        "shared_docs_rewritten": sorted({e["file"] for e in json_edits if not e["missing"]}),
        "consumed_claim_file": consumed_claim,
    }


def uninstall_plugin(profile: Path, claim: Any, purge_user_data: bool = False) -> dict[str, Any]:
    """Uninstall a plugin from ``profile``.

    With a claim dict (``plugin_name`` + ``claimed_paths`` [+ ``claimed_json``])
    this performs the confined claimed-path uninstall and refuses on a missing
    disposable marker, a path escaping the profile, or a path outside
    ``plugins/<plugin_name>/``. Any other ``claim`` is treated as an IMP-0027
    projection and forwarded to :func:`uninstall`.
    """
    if isinstance(claim, dict) and ("claimed_paths" in claim or "plugin_name" in claim):
        return _claim_uninstall(Path(profile), claim)
    return uninstall(Path(profile), claim, purge_user_data=purge_user_data)


def naive_empty_shared_json(profile: Path) -> dict[str, Any]:
    """Negative control: empty every shared host JSON document to ``{}``.

    Leaves every file under ``plugins/`` untouched (so a file inventory stays
    intact) while destroying the hook, MCP and settings registrations of every
    plugin, which is exactly the collateral damage a claimed-path uninstall
    must not cause. Still refuses to run on a non-disposable profile.
    """
    profile = Path(profile)
    require_disposable_profile(profile)
    emptied: list[str] = []
    missing: list[str] = []
    for rel in SHARED_JSON_DOCS:
        path = profile / rel
        if not path.is_file():
            missing.append(rel)
            continue
        _dump_json(path, {})
        emptied.append(rel)
    return {
        "ok": True,
        "mode": "naive-empty",
        "emptied": emptied,
        "missing": missing,
        "plugin_files_touched": [],
    }
