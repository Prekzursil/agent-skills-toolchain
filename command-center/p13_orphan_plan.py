"""P13 corroboration: is the 2,007-unit catalog an ORPHANED plan?

Signal 1 (already run, p13_execution_gap.py): per-path existence -> 1/2007 present.
Signal 2 (HERE, mechanically different): SET INTERSECTION between
  (a) the catalog's declared output_path universe, and
  (b) the artifacts the program actually delivered (ARTIFACT-MANIFEST.json + the
      real on-disk tracked file list),
computed as set algebra rather than per-path stat().

If the intersection is ~empty while (b) is large, the two namespaces are disjoint:
real work was delivered, but NOT at the paths the catalog contracted for -- so the
catalog cannot answer "what was dropped", which is itself the blind spot.

Also checks the 103-item register's receipt contract: items marked DONE-VERIFIED
whose declared receipt output_path does not exist.

Read-only apart from one JSON report.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
CC = REPO / "command-center"
OUT = CC / "P13-ORPHAN-PLAN.json"


def norm(p: str) -> str:
    return (p or "").replace("\\", "/").strip().lstrip("./")


def tracked_files() -> set[str]:
    r = subprocess.run(
        ["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True
    )
    return {norm(x) for x in r.stdout.splitlines() if x.strip()}


def ondisk_cc_files() -> set[str]:
    """Every real file under command-center (tracked or not)."""
    out = set()
    for p in CC.rglob("*"):
        if p.is_file():
            out.add(norm(str(p.relative_to(REPO))))
    return out


def main() -> int:
    cat = json.loads((CC / "WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    wus = cat["work_units"]
    items = cat["items"]

    declared = {norm(w.get("output_path", "")) for w in wus}
    declared.discard("")

    manifest_paths: set[str] = set()
    man = json.loads((CC / "ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))

    def harvest(o) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if (
                    isinstance(v, str)
                    and ("/" in v)
                    and v.endswith(
                        (".json", ".md", ".py", ".yaml", ".yml", ".txt", ".mjs", ".js")
                    )
                ):
                    manifest_paths.add(norm(v))
                else:
                    harvest(v)
        elif isinstance(o, list):
            for v in o:
                harvest(v)
        elif isinstance(o, str):
            if "/" in o and o.endswith(
                (".json", ".md", ".py", ".yaml", ".yml", ".txt")
            ):
                manifest_paths.add(norm(o))

    harvest(man)

    tracked = tracked_files()
    disk_cc = ondisk_cc_files()

    inter_manifest = declared & manifest_paths
    inter_tracked = declared & tracked
    inter_disk = declared & disk_cc

    # --- 103-item register receipt contract ---
    item_rows = []
    for it in items:
        op = norm(it.get("output_path", ""))
        exists = (
            (REPO / op).is_file() and (REPO / op).stat().st_size > 0 if op else False
        )
        item_rows.append(
            {
                "id": it.get("id"),
                "disposition": it.get("disposition"),
                "status": it.get("status"),
                "output_path": op,
                "receipt_exists": exists,
            }
        )
    done_verified = [r for r in item_rows if r["disposition"] == "DONE-VERIFIED"]
    dv_no_receipt = [r for r in done_verified if not r["receipt_exists"]]
    any_receipt = [r for r in item_rows if r["receipt_exists"]]

    report = {
        "artifact": "P13-ORPHAN-PLAN",
        "unit": "depth/p13-blindspot",
        "status": "MEASURED",
        "signal_2_probe": "set intersection of declared output_path universe vs delivered file universes",
        "universes": {
            "declared_output_paths_distinct": len(declared),
            "artifact_manifest_paths": len(manifest_paths),
            "git_tracked_files": len(tracked),
            "ondisk_command_center_files": len(disk_cc),
        },
        "intersections": {
            "declared_AND_artifact_manifest": sorted(inter_manifest),
            "declared_AND_artifact_manifest_n": len(inter_manifest),
            "declared_AND_git_tracked": sorted(inter_tracked),
            "declared_AND_git_tracked_n": len(inter_tracked),
            "declared_AND_ondisk_cc": sorted(inter_disk),
            "declared_AND_ondisk_cc_n": len(inter_disk),
        },
        "register_receipt_contract": {
            "items_total": len(item_rows),
            "declared_receipt_paths_existing": len(any_receipt),
            "done_verified_n": len(done_verified),
            "done_verified_without_receipt_n": len(dv_no_receipt),
            "done_verified_without_receipt_ids": [r["id"] for r in dv_no_receipt],
            "receipts_dir_exists": (CC / "receipts").is_dir(),
        },
        "status_census_items": {},
    }
    import collections

    report["status_census_items"] = dict(
        collections.Counter(str(r["status"]) for r in item_rows).most_common()
    )
    report["disposition_x_status"] = dict(
        collections.Counter(
            f"{r['disposition']} | {r['status']}" for r in item_rows
        ).most_common()
    )

    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("=== UNIVERSES ===")
    for k, v in report["universes"].items():
        print(f"  {k}: {v}")
    print()
    print("=== INTERSECTIONS with the 2,007-unit declared output_path universe ===")
    print(f"  vs ARTIFACT-MANIFEST paths : {len(inter_manifest)}")
    print(
        f"  vs git-tracked files       : {len(inter_tracked)}  {sorted(inter_tracked)[:5]}"
    )
    print(
        f"  vs on-disk command-center   : {len(inter_disk)}  {sorted(inter_disk)[:5]}"
    )
    print()
    print("=== 103-ITEM REGISTER RECEIPT CONTRACT ===")
    rr = report["register_receipt_contract"]
    print(f"  receipts dir exists            : {rr['receipts_dir_exists']}")
    print(
        f"  items with existing receipt    : {rr['declared_receipt_paths_existing']}/103"
    )
    print(f"  DONE-VERIFIED                  : {rr['done_verified_n']}")
    print(f"  DONE-VERIFIED w/o receipt      : {rr['done_verified_without_receipt_n']}")
    print(
        f"  ids                            : {rr['done_verified_without_receipt_ids']}"
    )
    print()
    print("=== items status census ===")
    for k, v in report["status_census_items"].items():
        print(f"  {v:4d}  {k}")
    print()
    print("=== disposition | status ===")
    for k, v in report["disposition_x_status"].items():
        print(f"  {v:4d}  {k}")
    print()
    print(f"SUCCESS:p13-orphan-plan wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
