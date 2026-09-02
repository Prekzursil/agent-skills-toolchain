"""Apply or revert a candidate patch; tree-hash equality on revert.

The retain/revert gate has ONE safety story, told twice so a probe can cross-check it:

* a :class:`TreeSnapshot` is the content census of a tree (path -> sha256 of LF-normalised
  bytes) plus one ``tree_hash`` over the census. Equal hashes after a revert mean the tree is
  byte-identical to the pre-candidate tree; a revert that misses a file, leaves a created
  file behind or touches an unrelated file cannot produce an equal hash.
* :func:`apply_patch` records the PRE-IMAGE of every path it writes (``None`` = did not
  exist) and the directories it created, so :func:`revert_patch` restores exactly that set
  and reports what it touched. :func:`check_revert` then refuses a revert that touched a
  path outside the patch (:class:`SafetyError`) or left the tree hash different
  (:class:`IncompleteRevertError`).

Decisions are appended to a JSONL ledger that is append-only: :func:`reject_rewrite` refuses
any rewrite that would discard recorded rows. A candidate is KEPT only on a MEASURED
improvement -- a score whose noise band is merely ``assumed`` can never count
(:func:`measured_improvement`).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

KEEP = "KEEP"
DROP = "DROP"


def measured_improvement(score: dict[str, Any]) -> bool:
    return not _in_band(score)


class AppendOnlyError(RuntimeError):
    pass


class IncompleteRevertError(RuntimeError):
    pass


class SafetyError(RuntimeError):
    pass


@dataclass
class TreeSnapshot:
    tree_hash: str
    files: dict[str, str]


@dataclass
class Decision:
    decision: str
    hashes_equal: bool
    pre_tree_hash: str
    post_tree_hash: str
    touched_outside_modified: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    touched_files: list[str] = field(default_factory=list)


@dataclass
class AppliedPatch:
    """What :func:`apply_patch` did: the pre-image of every written path (``None`` when the
    path did not exist), the directories it had to create (shallowest first) and the sorted
    set of paths it wrote."""

    preimages: dict[str, bytes | None]
    created_dirs: list[str]
    modified_files: list[str]


@dataclass
class RevertReport:
    """What :func:`revert_patch` did. ``touched`` is every path the revert wrote or removed --
    the set :func:`check_revert` compares against the patch's ``modified_files``."""

    touched: list[str]
    restored: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    removed_dirs: list[str] = field(default_factory=list)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _inside(root: Path, rel: str) -> Path:
    """Resolve ``rel`` under ``root``; a path that escapes the tree is a :class:`SafetyError`."""
    root = Path(root)
    dest = (root / rel).resolve()
    try:
        dest.relative_to(root.resolve())
    except ValueError:
        raise SafetyError(f"path escapes the tree: {rel!r}") from None
    return root / rel


def take_snapshot(root: Path) -> TreeSnapshot:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = _hash_bytes(path.read_bytes())
    blob = json.dumps(files, sort_keys=True).encode("utf-8")
    return TreeSnapshot(tree_hash=_hash_bytes(blob), files=files)


def snap_diff(pre: TreeSnapshot, post: TreeSnapshot) -> dict[str, Any]:
    """Path-level census diff: ``added`` / ``removed`` / ``changed`` (sorted) and ``equal``."""
    added = sorted(set(post.files) - set(pre.files))
    removed = sorted(set(pre.files) - set(post.files))
    changed = sorted(
        rel for rel in pre.files.keys() & post.files.keys() if pre.files[rel] != post.files[rel]
    )
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "equal": not (added or removed or changed) and pre.tree_hash == post.tree_hash,
    }


def _in_band(score: dict[str, Any]) -> bool:
    if str(score.get("noise_band_source") or "") == "assumed":
        return True
    delta = float(score.get("delta") or 0.0)
    band = score.get("noise_band") or {}
    low = float(band.get("low") or 0.0)
    high = float(band.get("high") or 0.0)
    if score.get("higher_is_better"):
        return not (delta > high)
    return not (delta < low)


def apply_patch(root: Path, changes: dict[str, bytes]) -> AppliedPatch:
    """Write ``changes`` into ``root``, recording pre-images and created directories."""
    root = Path(root)
    preimages: dict[str, bytes | None] = {}
    created_dirs: list[str] = []
    for rel in sorted(changes):
        dest = _inside(root, rel)
        preimages[rel] = dest.read_bytes() if dest.is_file() else None
        missing: list[str] = []
        parent = dest.parent
        while parent != root and not parent.exists():
            missing.append(parent.relative_to(root).as_posix())
            parent = parent.parent
        dest.parent.mkdir(parents=True, exist_ok=True)
        for made in reversed(missing):
            if made not in created_dirs:
                created_dirs.append(made)
        dest.write_bytes(changes[rel])
    return AppliedPatch(preimages=preimages, created_dirs=created_dirs, modified_files=sorted(changes))


def revert_patch(
    root: Path,
    preimages: Mapping[str, bytes | None],
    created_dirs: Iterable[str] = (),
    *,
    skip: Iterable[str] = (),
    extra_touch: Iterable[str] = (),
) -> RevertReport:
    """Restore every recorded pre-image (``None`` -> delete) and drop now-empty created dirs.

    ``skip`` leaves the named paths un-restored and ``extra_touch`` rewrites the named paths
    in place (bytes unchanged) -- both are recorded, never hidden, so :func:`check_revert`
    can refuse the result. They exist to make an incomplete or over-reaching revert a
    reproducible negative control rather than a hypothetical.
    """
    root = Path(root)
    skip_set = set(skip)
    touched: list[str] = []
    restored: list[str] = []
    deleted: list[str] = []
    skipped: list[str] = []
    for rel, data in preimages.items():
        if rel in skip_set:
            skipped.append(rel)
            continue
        dest = _inside(root, rel)
        if data is None:
            if dest.exists():
                dest.unlink()
                deleted.append(rel)
                touched.append(rel)
            continue
        if dest.is_file() and dest.read_bytes() == data:
            continue  # already at its pre-image: writing it again would be an unrelated touch
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        restored.append(rel)
        touched.append(rel)
    removed_dirs: list[str] = []
    for made in sorted(created_dirs, key=lambda d: (-d.count("/"), d)):
        path = _inside(root, made)
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            removed_dirs.append(made)
    for rel in extra_touch:
        dest = _inside(root, rel)
        if dest.is_file():
            dest.write_bytes(dest.read_bytes())
        touched.append(rel)
    return RevertReport(
        touched=sorted(set(touched)),
        restored=sorted(restored),
        deleted=sorted(deleted),
        skipped=sorted(skipped),
        removed_dirs=removed_dirs,
    )


def check_revert(
    pre: TreeSnapshot | Path,
    post: TreeSnapshot,
    modified_files: Iterable[str] | None = None,
    touched: Iterable[str] | None = None,
) -> None:
    """Refuse a revert that touched outside the patch or left the tree hash different.

    Two call shapes: ``check_revert(pre_snapshot, post_snapshot, modified_files, touched)``
    checks the touched set first (:class:`SafetyError`), then hash equality
    (:class:`IncompleteRevertError`); the original ``check_revert(root, snapshot)`` compares
    the live tree against ``snapshot``.
    """
    if not isinstance(pre, TreeSnapshot):
        live = take_snapshot(Path(pre))
        pre, post = post, live
    if touched is not None:
        outside = sorted(set(touched) - set(modified_files or ()))
        if outside:
            raise SafetyError(f"revert touched files outside the patch: {outside}")
    if post.tree_hash != pre.tree_hash:
        diff = snap_diff(pre, post)
        raise IncompleteRevertError(
            "tree hash after revert does not match: "
            f"changed={diff['changed']} added={diff['added']} removed={diff['removed']}"
        )


def _read_tree_bytes(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = path.read_bytes()
    return out


def _restore_originals(root: Path, originals: Mapping[str, bytes], written: Iterable[str]) -> list[str]:
    """Put every original byte string back and delete files the candidate created.

    Only files whose bytes actually differ are written, so the revert touches nothing it does
    not have to. Returns the sorted relative paths it wrote or removed.
    """
    touched: list[str] = []
    for rel, data in originals.items():
        dest = root / rel
        if not dest.is_file() or dest.read_bytes() != data:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            touched.append(rel)
    for rel in written:
        if rel not in originals:
            dest = root / rel
            if dest.exists():
                dest.unlink()
                touched.append(rel)
    return sorted(set(touched))


def decide(
    root: Path,
    changes: dict[str, bytes],
    score: dict[str, Any],
    ledger: Path,
    label: str,
) -> Decision:
    originals = _read_tree_bytes(root)
    pre = take_snapshot(root)
    apply_patch(root, changes)
    modified = sorted(changes)
    keep = not _in_band(score)
    if keep:
        post = take_snapshot(root)
        _append_ledger(ledger, {"label": label, "decision": KEEP})
        return Decision(
            decision=KEEP,
            hashes_equal=pre.tree_hash == post.tree_hash,
            pre_tree_hash=pre.tree_hash,
            post_tree_hash=post.tree_hash,
            modified_files=modified,
            touched_files=modified,
        )
    touched_outside: list[str] = []
    allowed = set(changes)
    for rel, data in originals.items():
        dest = root / rel
        if dest.is_file() and dest.read_bytes() != data and rel not in allowed:
            touched_outside.append(rel)
    touched = _restore_originals(root, originals, changes)
    post = take_snapshot(root)
    _append_ledger(ledger, {"label": label, "decision": DROP})
    return Decision(
        decision=DROP,
        hashes_equal=pre.tree_hash == post.tree_hash,
        pre_tree_hash=pre.tree_hash,
        post_tree_hash=post.tree_hash,
        touched_outside_modified=sorted(touched_outside),
        modified_files=modified,
        touched_files=touched,
    )


def _append_ledger(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def reject_rewrite(ledger: Path, replacement: bytes | str | None = None) -> None:
    """Refuse to rewrite an append-only ledger.

    A ledger with recorded rows may only GROW: when ``replacement`` is given it is accepted
    only if it starts with the current bytes (a pure append); with no replacement the call
    asks "may this ledger be rewritten at all?" and the answer for a non-empty ledger is
    :class:`AppendOnlyError`. A missing or empty ledger has nothing to protect.
    """
    path = Path(ledger)
    if not path.is_file():
        return
    current = path.read_bytes()
    if not current.strip():
        return
    if replacement is not None:
        proposed = replacement.encode("utf-8") if isinstance(replacement, str) else bytes(replacement)
        if proposed.startswith(current):
            return
    rows = sum(1 for line in current.splitlines() if line.strip())
    raise AppendOnlyError(
        f"{path.name}: rewriting an append-only ledger would discard {rows} recorded decision(s)"
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def tree_hash(root: Path) -> str:
    return take_snapshot(Path(root)).tree_hash


def measure_score_json(root: Path) -> float:
    path = Path(root) / "score.json"
    if not path.is_file():
        return 0.0
    doc = json.loads(path.read_text(encoding="utf-8"))
    return float(doc.get("value") or doc.get("score") or 0.0)


def read_ledger(path: Path) -> list[dict[str, Any]]:
    return load_jsonl(Path(path))


def apply_files(tree: Path, files: dict[str, str]) -> None:
    tree = Path(tree)
    for rel, text in files.items():
        dest = _inside(tree, rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def snapshot_paths(root: Path, paths: Iterable[str]) -> dict[str, bytes | None]:
    """Capture the pre-image of each named path (``None`` when it does not exist yet)."""
    root = Path(root)
    out: dict[str, bytes | None] = {}
    for rel in paths:
        dest = _inside(root, rel)
        out[rel] = dest.read_bytes() if dest.is_file() else None
    return out


def restore_snapshot(root: Path, snapshot: Mapping[str, bytes | None]) -> list[str]:
    """Write captured pre-images back (``None`` -> delete); return the paths touched.

    Restores ONLY the paths in ``snapshot``: handing it a subset of what was applied leaves
    the rest in place, which is exactly the residue :func:`check_revert` exists to catch.
    """
    root = Path(root)
    touched: list[str] = []
    for rel, data in snapshot.items():
        dest = _inside(root, rel)
        if data is None:
            if dest.exists():
                dest.unlink()
                touched.append(rel)
            continue
        if dest.is_file() and dest.read_bytes() == data:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        touched.append(rel)
    return sorted(set(touched))


def _default_ledger(tree: Path) -> Path:
    """The ledger a caller that names none gets: a sibling of the tree, never inside it (a
    file inside the tree would move the tree hash the gate is about to compare)."""
    return tree.parent / f"{tree.name}.retention-ledger.jsonl"


def retain(
    *,
    tree: Path,
    candidate_id: str,
    files: dict[str, str],
    ledger_path: Path | None = None,
    program_root: Path | None = None,
    produced_by: str | None = None,
) -> dict[str, Any]:
    tree = Path(tree)
    ledger = Path(ledger_path) if ledger_path is not None else _default_ledger(tree)
    pre = take_snapshot(tree)
    before = measure_score_json(tree)
    originals = _read_tree_bytes(tree)
    apply_files(tree, files)
    after = measure_score_json(tree)
    reason = "measured-improvement"
    decision = KEEP
    if after < before:
        decision = "REVERT"
        reason = "harmful"
    elif after == before:
        decision = "REVERT"
        reason = "neutral"
        if produced_by == "agent":
            reason = "neutral"
    if decision != KEEP:
        _restore_originals(tree, originals, files)
        post = take_snapshot(tree)
        hashes_equal = post.tree_hash == pre.tree_hash
        row = {
            "candidate_id": candidate_id,
            "decision": "REVERT",
            "reason": reason,
            "before_score": before,
            "after_score": after,
            "pre_tree_hash": pre.tree_hash,
            "post_decision_tree_hash": post.tree_hash,
            "hashes_equal": hashes_equal,
        }
        _append_ledger(ledger, row)
        return row
    post = take_snapshot(tree)
    row = {
        "candidate_id": candidate_id,
        "decision": KEEP,
        "reason": "measured-improvement",
        "before_score": before,
        "after_score": after,
        "pre_tree_hash": pre.tree_hash,
        "post_decision_tree_hash": post.tree_hash,
        "hashes_equal": pre.tree_hash == post.tree_hash,
    }
    _append_ledger(ledger, row)
    return row
