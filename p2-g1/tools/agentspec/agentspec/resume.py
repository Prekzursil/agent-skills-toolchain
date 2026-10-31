"""Resumable workflow runner (IMP-0145)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CHECKPOINT_NAME = "RESUME-CHECKPOINT.json"
SCHEMA = "agentspec.resume.checkpoint.v1"


class KillAtFraction(Exception):
    def __init__(self, dispatched: int, completed: list[str]) -> None:
        super().__init__(f"killed after {dispatched} units")
        self.dispatched = dispatched
        self.completed = list(completed)


@dataclass
class Workflow:
    workflow_id: str
    spec_version: str
    units: list[str]
    param_bindings: dict[str, Any] = field(default_factory=dict)


def workflow_from_ids(
    unit_ids: list[str],
    *,
    workflow_id: str,
    spec_version: str = "1",
    param_bindings: dict[str, Any] | None = None,
) -> Workflow:
    return Workflow(
        workflow_id=workflow_id,
        spec_version=spec_version,
        units=list(unit_ids),
        param_bindings=dict(param_bindings or {}),
    )


def persist_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha_file(path: Path) -> str:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


def artifact_index(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    art = Path(root) / "artifacts"
    if not art.is_dir():
        return out
    for p in sorted(art.rglob("*")):
        if p.is_file():
            rel = p.relative_to(root).as_posix()
            out[rel] = _sha_file(p)
    rec = Path(root) / "receipts"
    if rec.is_dir():
        for p in sorted(rec.glob("*.json")):
            rel = p.relative_to(root).as_posix()
            out[rel] = _sha_file(p)
    return out


def hash_set(index: dict[str, str]) -> set[tuple[str, str]]:
    return {(k, v) for k, v in index.items()}


def load_checkpoint(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _oracle_ok(receipt: Path) -> bool:
    if not receipt.is_file() or receipt.stat().st_size <= 0:
        return False
    try:
        doc = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    st = str(doc.get("state") or "").upper()
    if st in {"FAILED", "BLOCKED", "SEVERED", "TIMEOUT"}:
        return False
    text = receipt.read_text(encoding="utf-8")
    uid = str(doc.get("unit_id") or receipt.stem)
    return f"SUCCESS:{uid}" in text or doc.get("ok") is True


def _write_unit(root: Path, unit_id: str, wf: Workflow) -> None:
    rec_dir = root / "receipts"
    art_dir = root / "artifacts"
    rec_dir.mkdir(parents=True, exist_ok=True)
    art_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "unit_id": unit_id,
        "workflow_id": wf.workflow_id,
        "spec_version": wf.spec_version,
        "param_bindings": dict(wf.param_bindings),
        "state": "SUCCESS",
        "ok": True,
        "sentinel": f"SUCCESS:{unit_id}",
    }
    persist_json(rec_dir / f"{unit_id}.json", payload)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    (art_dir / f"{unit_id}.bin").write_bytes(blob)


class ResumableRunner:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _ckpt_path(self) -> Path:
        return self.root / CHECKPOINT_NAME

    def _write_checkpoint(
        self,
        wf: Workflow,
        run_id: str,
        completed: list[str],
        dispatch_log: list[str],
        killed: bool,
    ) -> dict[str, Any]:
        remaining = [u for u in wf.units if u not in completed]
        rec_hashes = {}
        rec_dir = self.root / "receipts"
        if rec_dir.is_dir():
            for uid in completed:
                p = rec_dir / f"{uid}.json"
                if p.is_file():
                    rec_hashes[uid] = _sha_file(p)
        ckpt = {
            "schema": SCHEMA,
            "run_id": run_id,
            "workflow_id": wf.workflow_id,
            "spec_version": wf.spec_version,
            "completed_unit_ids": list(completed),
            "receipt_hashes": rec_hashes,
            "open_nodes": [
                {"unit_id": u, "node_id": u, "reason": "not-yet-dispatched"}
                for u in remaining
            ],
            "param_bindings": dict(wf.param_bindings),
            "artifact_index": artifact_index(self.root),
            "dispatch_count_total": len(dispatch_log),
            "last_invocation_log": list(dispatch_log),
            "killed": killed,
        }
        persist_json(self._ckpt_path(), ckpt)
        return ckpt

    def run(
        self,
        wf: Workflow,
        run_id: str = "run",
        stop_after_units: int | None = None,
    ) -> dict[str, Any]:
        completed: list[str] = []
        ckpt_path = self._ckpt_path()
        if ckpt_path.is_file():
            prev = load_checkpoint(ckpt_path)
            completed = [
                u
                for u in (prev.get("completed_unit_ids") or [])
                if _oracle_ok(self.root / "receipts" / f"{u}.json")
            ]
        dispatch_log: list[str] = []
        for uid in wf.units:
            if uid in completed and _oracle_ok(self.root / "receipts" / f"{uid}.json"):
                continue
            _write_unit(self.root, uid, wf)
            completed.append(uid)
            # keep unique completed order
            seen = []
            for x in completed:
                if x not in seen:
                    seen.append(x)
            completed = seen
            dispatch_log.append(uid)
            if stop_after_units is not None and len(dispatch_log) >= int(stop_after_units):
                self._write_checkpoint(wf, run_id, completed, dispatch_log, killed=True)
                raise KillAtFraction(len(dispatch_log), completed)
        self._write_checkpoint(wf, run_id, completed, dispatch_log, killed=False)
        return {
            "ok": True,
            "run_id": run_id,
            "dispatch_count": len(dispatch_log),
            "dispatch_log": dispatch_log,
            "completed_unit_ids": list(completed),
        }
