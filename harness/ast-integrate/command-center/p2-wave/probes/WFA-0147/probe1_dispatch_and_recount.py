#!/usr/bin/env python3
"""Named probe 1: array recount of 44, live named settling probes, non-constant classes."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from corpus import UNKNOWN  # noqa: E402
from workflow_foundry.unknown_probe import (  # noqa: E402
    counts_block_unknown,
    load_registry,
    recount_unknown,
    settle_command,
)

UNIT = "WFA-0147"
ART = REPO / "command-center/foundry/WFA-0147-settle-the-44-unknown-needs-probe-candidates.json"
REG = REPO / "command-center/p2-wave/probes/WFA-0147/fixtures/registry.json"
REG_REL = "command-center/p2-wave/probes/WFA-0147/fixtures/registry.json"


def fail(msg: str) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def main() -> int:
    if not REG.is_file():
        return fail("recorded registry missing")
    registry = load_registry(REG)
    unknown = recount_unknown(registry)
    if len(unknown) != 44:
        return fail(f"array recount {len(unknown)} != 44")
    lie = counts_block_unknown(registry)
    if lie is None or lie == 44:
        return fail(f"counts block was not a lie ({lie})")
    if lie == len(unknown):
        return fail("array recount collapsed onto the counts block")

    live_rows = []
    for cand in unknown:
        cid = str(cand["id"])
        cmd = settle_command(REG_REL, cid)
        rc, text = run_cmd(cmd)
        try:
            payload = json.loads(text.splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return fail(f"settle {cid} unparseable: {text[-400:]}")
        cls = str(payload.get("final_classification") or "")
        tail = str(payload.get("output_tail") or "")
        if not tail.strip():
            return fail(f"{cid} empty output_tail")
        if cls == UNKNOWN and not payload.get("blocked_reason"):
            return fail(f"{cid} UNKNOWN without blocker")
        live_rows.append({"id": cid, "cls": cls, "cmd": cmd, "rc": rc, "kind": payload.get("kind")})

    classes = {r["cls"] for r in live_rows}
    if len(classes) < 4:
        return fail(f"constant-function {sorted(classes)}")
    remain = [r for r in live_rows if r["cls"] == UNKNOWN]
    if len(remain) < 1:
        return fail("no remaining UNKNOWN with blocker (expected windows/network/no-probe cases)")

    if not ART.is_file() or ART.stat().st_size < 1024:
        return fail("foundry artifact missing")
    artifact = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(artifact)
    if "SUCCESS:WFA-0147" not in blob:
        return fail("sentinel absent")
    st = str(artifact.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    art_rows = (artifact.get("dispatch") or {}).get("rows") or []
    if len(art_rows) != 44:
        return fail(f"artifact rows {len(art_rows)} != 44")
    by_id = {r["id"]: r for r in art_rows}
    for live in live_rows:
        rec = by_id.get(live["id"])
        if rec is None:
            return fail(f"artifact missing {live['id']}")
        if rec.get("final_classification") != live["cls"]:
            return fail(
                f"{live['id']} artifact {rec.get('final_classification')} != live {live['cls']}"
            )
        if not rec.get("probe_command") or not rec.get("output_tail"):
            return fail(f"{live['id']} missing command/tail")

    report = {
        "probe": "probe1-dispatch-and-recount",
        "unit_id": UNIT,
        "array_recount": len(unknown),
        "counts_block": lie,
        "used_counts_block": False,
        "n_live_settles": len(live_rows),
        "n_classes": len(classes),
        "classes": sorted(classes),
        "remain_unknown": len(remain),
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print(
        "SUCCESS:WFA-0147-probe1 array-recount=44 named-settles-live "
        f"classes={len(classes)} remain_unknown={len(remain)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
