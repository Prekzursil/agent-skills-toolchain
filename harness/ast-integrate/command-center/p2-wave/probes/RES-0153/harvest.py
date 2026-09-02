#!/usr/bin/env python3
"""Load 30 pinned real UNVERIFIED/residual tags. Do not walk a mutating corpus."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TARGET = 30
PIN = HERE / "fixtures" / "pinned_tags.json"


def _observable(claim: str) -> bool:
    from generator import generate

    return generate(claim).get("status") != "NEEDS-HUMAN-FRAMING"


def harvest_thirty() -> list[dict]:
    doc = json.loads(PIN.read_text(encoding="utf-8"))
    tags = list(doc.get("tags") or [])
    if len(tags) != TARGET:
        raise RuntimeError(f"pin has {len(tags)} tags, need {TARGET}")
    out: list[dict] = []
    seen: set[str] = set()
    for i, item in enumerate(tags, 1):
        claim = str(item.get("claim") or "").strip()
        src = str(item.get("source_path") or "")
        if len(claim) < 12:
            raise RuntimeError(f"pin tag {i} claim too short")
        if not src:
            raise RuntimeError(f"pin tag {i} missing source_path")
        path = REPO / src
        if not path.is_file():
            raise RuntimeError(f"pinned source missing: {src}")
        if claim in seen:
            raise RuntimeError(f"duplicate pinned claim at {i}")
        seen.add(claim)
        row = {
            "id": f"UV-{i:02d}",
            "source_class": item.get("source_class"),
            "source_path": src,
            "source_locator": item.get("source_locator"),
            "source_id": item.get("source_id"),
            "claim": claim,
            "tag": item.get("tag") or "UNVERIFIED",
            "names_observable": _observable(claim),
        }
        authored = item.get("authored_settling_experiment")
        if isinstance(authored, str) and authored.strip():
            row["authored_settling_experiment"] = authored.strip()
        out.append(row)
    return out


def main() -> int:
    rows = harvest_thirty()
    n_obs = sum(1 for r in rows if r["names_observable"])
    print(
        json.dumps(
            {
                "n": len(rows),
                "observable": n_obs,
                "unobservable": len(rows) - n_obs,
                "classes": {
                    c: sum(1 for r in rows if r["source_class"] == c)
                    for c in sorted({r["source_class"] for r in rows})
                },
                "ids": [r["id"] for r in rows],
            },
            indent=1,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
