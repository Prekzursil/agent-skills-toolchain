"""Resumable scout/forge engine with write-as-you-go partial artifacts (IMP-0215)."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

SCHEMA_REL = "tools/workflow_foundry/partial-artifact.schema.json"
STAGES = {
    "forge": [{"id": f"forge-{i:02d}"} for i in range(10)],
    "scout": [{"id": f"scout-{i:02d}"} for i in range(10)],
}


class InterruptedRun(Exception):
    def __init__(self, *, proven: list[str], progress_pct: float) -> None:
        super().__init__(f"interrupted at {progress_pct}%")
        self.proven = list(proven)
        self.progress_pct = float(progress_pct)


def atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    tmp.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def load_artifact(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_partial(doc: dict[str, Any]) -> None:
    required = ("state", "progress_pct", "claims", "checkpoint")
    missing = [k for k in required if k not in doc]
    if missing:
        raise ValueError(f"partial missing {missing}")
    claims = doc["claims"]
    if not isinstance(claims, list) or not claims:
        raise ValueError("claims empty")
    for claim in claims:
        if "id" not in claim or "verdict" not in claim:
            raise ValueError("claim missing id/verdict")
        if claim["verdict"] == "UNKNOWN":
            payload = claim.get("payload") or {}
            if payload.get("status") != "UNKNOWN":
                raise ValueError(f"{claim['id']} UNKNOWN missing status")
            if "not yet measured" not in str(payload.get("reason") or ""):
                raise ValueError(f"{claim['id']} UNKNOWN reason")


def count_ledger_dispatches(path: Path, session: str | None = None) -> tuple[int, list[str]]:
    ids: list[str] = []
    if not Path(path).is_file():
        return 0, []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("event") != "dispatch":
            continue
        if session is not None and rec.get("session") != session:
            continue
        ids.append(str(rec.get("claim_id")))
    return len(ids), ids


def _digest(engine: str, claim_id: str, goal: str) -> str:
    raw = f"{engine}:{claim_id}:{goal}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class ResumableEngine:
    def __init__(self, work: Path, engine: str, goal: str = "") -> None:
        self.work = Path(work)
        self.engine = engine
        self.goal = goal
        self.work.mkdir(parents=True, exist_ok=True)
        self.artifact_path = self.work / "partial.json"
        self.ledger_path = self.work / "ledger.jsonl"
        self._memory_only = False

    def _append_ledger(self, rec: dict[str, Any]) -> None:
        with self.ledger_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")

    def _write(self, doc: dict[str, Any]) -> None:
        if self._memory_only:
            self._memory_doc = doc
            return
        atomic_write_json(self.artifact_path, doc)

    def _blank_claims(self) -> list[dict[str, Any]]:
        rows = []
        for stage in STAGES[self.engine]:
            cid = stage["id"]
            rows.append(
                {
                    "id": cid,
                    "verdict": "UNKNOWN",
                    "payload": {
                        "status": "UNKNOWN",
                        "reason": "not yet measured",
                    },
                    "receipt_hash": None,
                }
            )
        return rows

    def _snapshot(self, claims: list[dict[str, Any]], *, complete: bool) -> dict[str, Any]:
        proven = [c["id"] for c in claims if c.get("verdict") == "PROVEN"]
        unknown = [c["id"] for c in claims if c.get("verdict") == "UNKNOWN"]
        hashes = {
            c["id"]: c["receipt_hash"]
            for c in claims
            if c.get("verdict") == "PROVEN" and c.get("receipt_hash")
        }
        n = len(claims) or 1
        pct = round(100.0 * len(proven) / n, 4)
        return {
            "state": "COMPLETE" if complete else "PARTIAL",
            "engine": self.engine,
            "goal": self.goal,
            "progress_pct": 100.0 if complete else pct,
            "claims": claims,
            "checkpoint": {
                "completed_claim_ids": proven,
                "open_nodes": unknown,
                "receipt_hashes": hashes,
            },
        }

    def run(
        self,
        session: str,
        *,
        kill_at_pct: float | None = None,
        resume: bool = False,
        ignore_checkpoint: bool = False,
    ) -> dict[str, Any]:
        stages = [s["id"] for s in STAGES[self.engine]]
        if resume and self.artifact_path.is_file() and not ignore_checkpoint:
            doc = load_artifact(self.artifact_path)
            claims = list(doc.get("claims") or self._blank_claims())
        else:
            claims = self._blank_claims()
        by_id = {c["id"]: c for c in claims}
        proven_ok: set[str] = set()
        if resume and not ignore_checkpoint:
            for claim in claims:
                if claim.get("verdict") == "PROVEN" and claim.get("receipt_hash"):
                    expected = _digest(self.engine, claim["id"], self.goal)
                    if claim["receipt_hash"] == expected:
                        proven_ok.add(claim["id"])
                        self._append_ledger(
                            {
                                "event": "skip_proven",
                                "session": session,
                                "claim_id": claim["id"],
                            }
                        )
        for cid in stages:
            if cid in proven_ok:
                continue
            self._append_ledger(
                {"event": "dispatch", "session": session, "claim_id": cid}
            )
            digest = _digest(self.engine, cid, self.goal)
            by_id[cid] = {
                "id": cid,
                "verdict": "PROVEN",
                "payload": {
                    "status": "PROVEN",
                    "measured": True,
                    "result_digest": digest,
                },
                "receipt_hash": digest,
            }
            claims = [by_id[s] for s in stages]
            proven = [c["id"] for c in claims if c["verdict"] == "PROVEN"]
            pct = 100.0 * len(proven) / len(stages)
            self._write(self._snapshot(claims, complete=False))
            if kill_at_pct is not None and abs(pct - float(kill_at_pct)) < 0.011:
                raise InterruptedRun(proven=proven, progress_pct=pct)
        claims = [by_id[s] for s in stages]
        final = self._snapshot(claims, complete=True)
        self._write(final)
        return final


class MemoryOnlyEngine(ResumableEngine):
    def __init__(self, work: Path, engine: str, goal: str = "") -> None:
        super().__init__(work, engine, goal=goal)
        self._memory_only = True
        self._memory_doc: dict[str, Any] | None = None
        # Memory-only must not leave an artifact on kill.
        if self.artifact_path.exists():
            self.artifact_path.unlink()
