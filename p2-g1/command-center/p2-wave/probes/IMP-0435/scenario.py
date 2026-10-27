"""Emit green/red receipt fixtures for the IMP-0435 both-states CI evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def emit(root: Path) -> dict:
    """Write a valid IMP-0435-shaped receipt and an invalid catalog-id receipt."""
    sys.path.insert(0, str(REPO / "command-center"))
    import receipt_validate as rv  # noqa: PLC0415

    golden = rv.minimal_golden(REPO)
    golden["id"] = "IMP-0435"
    green_dir = root / "green"
    red_dir = root / "red"
    green_dir.mkdir(parents=True, exist_ok=True)
    red_dir.mkdir(parents=True, exist_ok=True)
    gp = green_dir / "IMP-0435.json"
    gp.write_text(json.dumps(golden, indent=2), encoding="utf-8")
    bogus = dict(golden)
    bogus["id"] = "ZZZ-9999"
    bogus["unit_id"] = "ZZZ-9999"
    bogus["sentinel"] = "SUCCESS:ZZZ-9999"
    bogus["completion_sentinel"] = "SUCCESS:ZZZ-9999"
    bogus["spec_anchor"] = "command-center/WORK-UNIT-CATALOG.json work_units[id=ZZZ-9999]"
    rp = red_dir / "bogus.json"
    rp.write_text(json.dumps(bogus, indent=2), encoding="utf-8")
    return {"green": str(gp), "red": str(rp),
            "green_admits": rv.admit(gp, rv.catalog_ids(REPO), rv._load_gate())[0],
            "red_admits": rv.admit(rp, rv.catalog_ids(REPO), rv._load_gate())[0]}


if __name__ == "__main__":
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        print(json.dumps(emit(Path(td)), indent=2))
