"""Apply or revert a candidate patch; tree-hash equality on revert."""
from __future__ import annotations

import hashlib
import json
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


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def take_snapshot(root: Path) -> TreeSnapshot:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            files[rel] = _hash_bytes(path.read_bytes())
    blob = json.dumps(files, sort_keys=True).encode("utf-8")
    return TreeSnapshot(tree_hash=_hash_bytes(blob), files=files)


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


def apply_patch(root: Path, changes: dict[str, bytes]) -> None:
    for rel, data in changes.items():
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)


def check_revert(root: Path, snapshot: TreeSnapshot) -> None:
    live = take_snapshot(root)
    if live.tree_hash != snapshot.tree_hash:
        raise IncompleteRevertError("tree hash after revert does not match")


def _read_tree_bytes(root: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_file():
            out[path.relative_to(root).as_posix()] = path.read_bytes()
    return out


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
    keep = not _in_band(score)
    if keep:
        post = take_snapshot(root)
        _append_ledger(ledger, {"label": label, "decision": KEEP})
        return Decision(
            decision=KEEP,
            hashes_equal=pre.tree_hash == post.tree_hash,
            pre_tree_hash=pre.tree_hash,
            post_tree_hash=post.tree_hash,
        )
    touched_outside: list[str] = []
    allowed = set(changes)
    for rel, data in originals.items():
        dest = root / rel
        if dest.read_bytes() != data and rel not in allowed:
            touched_outside.append(rel)
        dest.write_bytes(data)
    for rel in changes:
        if rel not in originals:
            dest = root / rel
            if dest.exists():
                dest.unlink()
    post = take_snapshot(root)
    _append_ledger(ledger, {"label": label, "decision": DROP})
    return Decision(
        decision=DROP,
        hashes_equal=pre.tree_hash == post.tree_hash,
        pre_tree_hash=pre.tree_hash,
        post_tree_hash=post.tree_hash,
        touched_outside_modified=touched_outside,
    )


def _append_ledger(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


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
        dest = tree / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")


def retain(
    *,
    tree: Path,
    candidate_id: str,
    files: dict[str, str],
    ledger_path: Path,
    program_root: Path | None = None,
    produced_by: str | None = None,
) -> dict[str, Any]:
    tree = Path(tree)
    pre = take_snapshot(tree)
    before = measure_score_json(tree)
    originals = _read_tree_bytes(tree)
    for rel, text in files.items():
        dest = tree / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
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
        for rel, data in originals.items():
            (tree / rel).write_bytes(data)
        for rel in files:
            if rel not in originals:
                p = tree / rel
                if p.exists():
                    p.unlink()
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
        _append_ledger(Path(ledger_path), row)
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
    _append_ledger(Path(ledger_path), row)
    return row

