#!/usr/bin/env python3
"""IMP-0215 probe 1: kill-at-30% leaves a truthful partial artifact.

Two independent signals:
  (1) a killed forge (and scout) run leaves a schema-valid file whose
      unproven claims are explicit UNKNOWN, not omitted or guessed
  (2) the memory-only negative control holds proofs until the end, so the
      same kill leaves no artifact — write-as-you-go is load-bearing
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from workflow_foundry.resumable import (  # noqa: E402
    InterruptedRun,
    MemoryOnlyEngine,
    ResumableEngine,
    STAGES,
    load_artifact,
    validate_partial,
)

GOAL = "IMP-0215-kill-at-30-goal"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0215-probe1 {msg}")
    return 1


def unknown_ids(doc: dict) -> list[str]:
    return [c["id"] for c in doc["claims"] if c.get("verdict") == "UNKNOWN"]


def proven_ids(doc: dict) -> list[str]:
    return [c["id"] for c in doc["claims"] if c.get("verdict") == "PROVEN"]


def kill_run(root: Path, engine: str) -> tuple[Path, dict, InterruptedRun]:
    work = root / engine
    runner = ResumableEngine(work, engine, goal=GOAL)
    try:
        runner.run(session="killed", kill_at_pct=30)
    except InterruptedRun as exc:
        if not runner.artifact_path.is_file():
            raise RuntimeError("write-as-you-go left no artifact") from exc
        doc = load_artifact(runner.artifact_path)
        return runner.artifact_path, doc, exc
    raise RuntimeError(f"{engine} was not interrupted at 30%")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0215-p1-") as tmp:
        tmp_path = Path(tmp)
        results = {}
        for engine in ("forge", "scout"):
            path, doc, exc = kill_run(tmp_path, engine)
            try:
                validate_partial(doc)
            except Exception as err:
                return fail(f"{engine} schema-invalid: {err}")
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("state") in {"SUCCESS", "COMPLETE"}:
                return fail(f"{engine} partial self-declared {raw.get('state')}")
            if raw.get("state") != "PARTIAL":
                return fail(f"{engine} state={raw.get('state')!r} want PARTIAL")
            if abs(float(raw.get("progress_pct") or 0) - 30.0) > 0.01:
                return fail(f"{engine} progress_pct={raw.get('progress_pct')} want 30")
            stages = [s["id"] for s in STAGES[engine]]
            got = [c["id"] for c in raw["claims"]]
            if got != stages:
                return fail(f"{engine} claim roster incomplete {got}")
            proven = proven_ids(raw)
            unknown = unknown_ids(raw)
            if len(proven) != 3 or len(unknown) != 7:
                return fail(
                    f"{engine} proven={len(proven)} unknown={len(unknown)} want 3/7"
                )
            for claim in raw["claims"]:
                if claim["id"] in unknown:
                    payload = claim.get("payload") or {}
                    if payload.get("status") != "UNKNOWN":
                        return fail(f"{engine} {claim['id']} missing UNKNOWN status")
                    if "not yet measured" not in str(payload.get("reason") or ""):
                        return fail(f"{engine} {claim['id']} reason not explicit")
                    if claim.get("receipt_hash"):
                        return fail(f"{engine} {claim['id']} UNKNOWN carries a hash")
                if claim["id"] in proven:
                    if claim.get("payload", {}).get("measured") is not True:
                        return fail(f"{engine} {claim['id']} proven unmeasured")
            ckpt = raw.get("checkpoint") or {}
            if ckpt.get("completed_claim_ids") != proven:
                return fail(f"{engine} checkpoint completed mismatch")
            if ckpt.get("open_nodes") != unknown:
                return fail(f"{engine} checkpoint open_nodes mismatch")
            if set(ckpt.get("receipt_hashes") or {}) != set(proven):
                return fail(f"{engine} checkpoint hashes != proven set")
            body = path.read_text(encoding="utf-8")
            if "UNKNOWN" not in body or "not yet measured" not in body:
                return fail(f"{engine} artifact text omitted UNKNOWN")
            results[engine] = {
                "progress_pct": raw["progress_pct"],
                "proven": proven,
                "unknown": unknown,
                "exc_proven": exc.proven,
                "path": str(path),
            }

        mem = MemoryOnlyEngine(tmp_path / "memory-forge", "forge", goal=GOAL)
        try:
            mem.run(session="memory-killed", kill_at_pct=30)
            return fail("memory-only engine was not interrupted")
        except InterruptedRun:
            pass
        if mem.artifact_path.exists():
            return fail(
                "memory-only negative control wrote an artifact on kill "
                f"path={mem.artifact_path}"
            )

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe1-kill-partial",
                "unit_id": "IMP-0215",
                "forge": results["forge"],
                "scout": results["scout"],
                "memory_only_artifact_absent": True,
            },
            sort_keys=True,
        )
    )
    print(
        "forge_pct=30 scout_pct=30 proven=3 unknown=7 memory_only_absent=True"
    )
    print("SUCCESS:IMP-0215-probe1 kill-at-30% truthful partial UNKNOWN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
