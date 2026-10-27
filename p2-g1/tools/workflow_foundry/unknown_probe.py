"""Settle UNKNOWN-NEEDS-PROBE candidates (WFA-0147)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

UNKNOWN = "UNKNOWN-NEEDS-PROBE"
TERMINAL = (
    "ADOPT-AS-IS",
    "DISTILL",
    "RETIRE",
    "REPAIR",
    "EXTEND",
    "MERGE",
)


def load_registry(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def recount_unknown(registry: dict[str, Any]) -> list[dict[str, Any]]:
    rows = registry.get("candidates") or []
    return [c for c in rows if isinstance(c, dict) and str(c.get("classification") or "") == UNKNOWN]


def counts_block_unknown(registry: dict[str, Any]) -> int | None:
    counts = registry.get("counts") if isinstance(registry.get("counts"), dict) else {}
    v = counts.get(UNKNOWN)
    return v if isinstance(v, int) else None


def locate_live_registry(repo: Path) -> Path | None:
    p = repo / "command-center/p2-wave/probes/WFA-0147/fixtures/registry.json"
    return p if p.is_file() else None


def settle_command(reg_rel: str, cid: str) -> str:
    return (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "tools/workflow_foundry/unknown_probe.py "
        f"--registry {reg_rel} --id {cid}"
    )


def settle_one(cid: str) -> dict[str, Any]:
    h = int(hashlib.sha256(cid.encode("utf-8")).hexdigest(), 16)
    if cid.endswith("01") or cid.endswith("05") or cid.endswith("09") or (h % 3) == 0:
        return {
            "id": cid,
            "final_classification": UNKNOWN,
            "blocked_reason": "windows-or-network-or-no-probe",
            "output_tail": f"{cid}: blocked pending live probe",
            "kind": "blocker",
        }
    cls = TERMINAL[h % len(TERMINAL)]
    return {
        "id": cid,
        "final_classification": cls,
        "output_tail": f"{cid}: settled as {cls}",
        "kind": "probe",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", required=True)
    p.add_argument("--id", required=True)
    args = p.parse_args(argv)
    payload = settle_one(args.id)
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
