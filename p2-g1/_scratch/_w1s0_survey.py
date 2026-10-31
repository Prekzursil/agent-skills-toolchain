"""Survey the 12 wave-1 shard-0 artifacts: reviewer, manifest, section shapes."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")
MY = [
    "ADV-0006", "ADV-0019", "ADV-0027", "ADV-0028", "ADV-0029", "ADV-0033",
    "ADV-0037", "ADV-0038", "ADV-0060", "ADV-0096", "ADV-0124", "ADV-0127",
]


def main() -> int:
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    by = {u["id"]: u for u in cat["work_units"]}
    glob_rows = json.loads(
        (REPO / "command-center/UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8")
    )
    rows = glob_rows.get("artifacts") if isinstance(glob_rows, dict) else glob_rows
    glob_ids = {a.get("unit_id") for a in rows if isinstance(a, dict)}

    for uid in MY:
        u = by[uid]
        doc = json.loads((REPO / u["output_path"]).read_text(encoding="utf-8"))
        rv = doc.get("reviewer") or {}
        mr = doc.get("manifest_registration") or {}
        ev = doc.get("evidence") or []
        ev0 = ev[0] if ev else {}
        print(f"{uid}: state={doc.get('state')} sent={str(doc.get('sentinel'))[:24]!r}")
        print(
            f"  reviewer={rv.get('verdict')}/ind={rv.get('independent')}/vendor={rv.get('vendor')} "
            f"mr={mr.get('registered')}->{str(mr.get('manifest_path'))[-52:]}"
        )
        print(
            f"  n_evidence={len(ev)} ev0_keys={sorted(ev0.keys()) if isinstance(ev0, dict) else '?'} "
            f"in_global_manifest={uid in glob_ids}"
        )
        print(
            f"  tests={len(doc.get('tests') or [])} nc={len(doc.get('negative_controls') or [])} "
            f"dc={len(doc.get('downstream_consumers') or [])} defects={len(doc.get('defects') or [])} "
            f"ru={len(doc.get('residual_unknowns') or [])} "
            f"sv={doc.get('schema_version')} ts={bool(doc.get('timestamps'))} retry={bool(doc.get('retry'))}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
