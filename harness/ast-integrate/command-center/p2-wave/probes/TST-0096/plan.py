"""Deterministic five-unit plan and oracle for TST-0096 crash-resume."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

PLAN: list[dict[str, Any]] = [
    {
        "id": "u1",
        "title": "alpha-unit",
        "artifact": "artifacts/u1.json",
        "payload": "alpha-body-" + ("A" * 48),
    },
    {
        "id": "u2",
        "title": "bravo-unit",
        "artifact": "artifacts/u2.json",
        "payload": "bravo-body-" + ("B" * 48),
    },
    {
        "id": "u3",
        "title": "charlie-unit",
        "artifact": "artifacts/u3.json",
        "payload": "charlie-body-" + ("C" * 48),
    },
    {
        "id": "u4",
        "title": "delta-unit",
        "artifact": "artifacts/u4.json",
        "payload": "delta-body-" + ("D" * 48),
    },
    {
        "id": "u5",
        "title": "echo-unit",
        "artifact": "artifacts/u5.json",
        "payload": "echo-body-" + ("E" * 48),
    },
]

# Four named kill points: two post-commit boundaries, two mid-unit crashes.
CHECKPOINTS: list[str] = ["after:u1", "mid:u2", "after:u3", "mid:u4"]


def by_id() -> dict[str, dict[str, Any]]:
    return {u["id"]: u for u in PLAN}


def known_checkpoints() -> set[str]:
    ids = [u["id"] for u in PLAN]
    return {f"mid:{i}" for i in ids} | {f"after:{i}" for i in ids}


def expected_complete_ids(kill_at: str) -> list[str]:
    kind, uid = kill_at.split(":", 1)
    ids = [u["id"] for u in PLAN]
    idx = ids.index(uid)
    if kind == "after":
        return ids[: idx + 1]
    if kind == "mid":
        return ids[:idx]
    raise ValueError(f"unknown checkpoint kind {kill_at!r}")


def expected_incomplete_ids(kill_at: str) -> list[str]:
    done = set(expected_complete_ids(kill_at))
    return [u["id"] for u in PLAN if u["id"] not in done]


def render_artifact(unit: dict[str, Any]) -> dict[str, Any]:
    uid = unit["id"]
    return {
        "unit_id": uid,
        "state": "SUCCESS",
        "sentinel": f"SUCCESS:{uid}",
        "title": unit["title"],
        "payload": unit["payload"],
    }


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes()
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def unit_oracle(
    root: Path, unit: dict[str, Any], recorded: dict[str, Any] | None = None
) -> dict[str, Any]:
    rel = unit["artifact"]
    path = Path(root) / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return {"pass": False, "reason": "absent", "path": rel}
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    sha = hashlib.sha256(raw).hexdigest()
    try:
        text = raw.decode("utf-8")
        doc = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"pass": False, "reason": "unparseable", "sha256": sha, "path": rel}
    if not isinstance(doc, dict):
        return {"pass": False, "reason": "not-object", "sha256": sha, "path": rel}
    sentinel = f"SUCCESS:{unit['id']}"
    if sentinel not in text:
        return {"pass": False, "reason": "sentinel-absent", "sha256": sha, "path": rel}
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return {
            "pass": False,
            "reason": f"self-declared:{st}",
            "sha256": sha,
            "path": rel,
        }
    if doc.get("unit_id") != unit["id"]:
        return {"pass": False, "reason": "unit-id-mismatch", "sha256": sha, "path": rel}
    if recorded and recorded.get("sha256") and recorded["sha256"] != sha:
        return {"pass": False, "reason": "sha-mismatch", "sha256": sha, "path": rel}
    return {"pass": True, "reason": "ok", "sha256": sha, "bytes": len(raw), "path": rel}


def artifact_set_hash(root: Path, plan: list[dict[str, Any]] | None = None) -> str:
    """Content hash of the artifact set. Paths are plan-relative, so the digest
    is identical across workspaces when payloads are identical.
    """
    units = plan if plan is not None else PLAN
    h = hashlib.sha256()
    for unit in units:
        rel = str(unit["artifact"]).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        path = Path(root) / rel
        if path.is_file():
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            h.update(hashlib.sha256(raw).digest())
        else:
            h.update(b"ABSENT")
        h.update(b"\n")
    return h.hexdigest()


def write_plan(root: Path) -> Path:
    path = Path(root) / "plan.json"
    atomic_write_text(path, json.dumps(PLAN, indent=2, sort_keys=True) + "\n")
    return path


def load_plan(root: Path) -> list[dict[str, Any]]:
    path = Path(root) / "plan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError(f"plan.json is not a non-empty list: {path}")
    return data
