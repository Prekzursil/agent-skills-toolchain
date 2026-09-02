"""Write command-center/phase3/A5/CLAIM-UNDER-TEST.json.

ARC-0031 still owns DESIGN.json. This extract gives ARC-0037 dossier
anchors without rebuilding A5 (no ADV circle).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = "command-center/phase3/A5/CLAIM-UNDER-TEST.json"

DISPATCHERS = (
    "A5 publishes dispatchers for local, worktree, and cloud substrates"
)
FANOUT = "dynamic fan-out is in-contract for the local dispatcher"
NO_PREFLIGHT = (
    "A5 local operation has no proven commit-charge pre-flight ceiling"
)
COST = "A5 cost framing names arrival-rate 429 and compute, not commit charge"
WORKTREE = (
    "worktree-on-this-box still charges this box; only cloud-off-box is a "
    "different substrate"
)
SNIPPETS = (DISPATCHERS, FANOUT, NO_PREFLIGHT, COST, WORKTREE)


def claim_doc() -> dict:
    return {
        "adv_rebuild_circle": False,
        "architecture_class": "distributed-workflow-runtime",
        "architecture_id": "A5",
        "a5_design_json_present": False,
        "cost_framing": COST,
        "dynamic_fanout": FANOUT,
        "extract_id": "ARC-0037-claim-under-test",
        "local_dispatchers": DISPATCHERS,
        "no_preflight": NO_PREFLIGHT,
        "not_arc_0031_design": True,
        "role": (
            "ARC-0037 claim-under-test extract; ARC-0031 still owns DESIGN.json"
        ),
        "unit_id": "ARC-0037",
        "worktree_charge": WORKTREE,
    }


def write_claim(repo: Path | None = None) -> Path:
    root = repo or REPO
    path = root / OUT
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(claim_doc(), indent=1, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    lines = text.splitlines()
    for snippet in SNIPPETS:
        hits = [i for i, ln in enumerate(lines, 1) if snippet in ln]
        if len(hits) != 1:
            raise SystemExit(f"FAILED:ARC-0037 claim snippet {snippet!r} hits={hits}")
    return path


if __name__ == "__main__":
    p = write_claim()
    print(f"wrote {OUT} bytes={p.stat().st_size}")
