#!/usr/bin/env python3
"""TST-0197 probe 2: independent os.listdir count over the SAME planted tree.

Two independent signals: the scandir-walker count (probe 1's API) and this
os.listdir recursion must agree on the reserved-name tree. Also proves the
extended-length \?\ form of each reserved entry opens live on Windows.
"""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from enumerator import dir_listing_count, enumerate_tree  # noqa: E402
from fixture import plant_tree  # noqa: E402


def main() -> int:
    root = HERE / "fixtures" / "reserved-tree-2"
    if root.exists():
        shutil.rmtree(root)
    plant_tree(root)

    walker = enumerate_tree(root)
    listing = dir_listing_count(root)
    extended = [f for f in walker["reserved_files"] if f["extended_length_form"]]

    extended_open_ok = True
    extended_open_detail = []
    for f in walker["reserved_files"]:
        form = f.get("extended_length_form")
        if not form:
            continue
        try:
            with open(form, "rb") as fh:
                data = fh.read()
            extended_open_ok = extended_open_ok and len(data) > 0
            extended_open_detail.append({"name": f["name"], "opened_bytes": len(data)})
        except OSError as exc:
            extended_open_ok = False
            extended_open_detail.append({"name": f["name"], "error": str(exc)})

    counts_agree = walker["file_count"] == listing["count"]
    names_match = sorted(f["name"] for f in walker["files"]) == listing["names"]

    checks = {
        "independent_counts_agree": counts_agree,
        "names_agree": names_match,
        "reserved_in_both_signals": sorted(f["name"] for f in walker["reserved_files"])
        == sorted(n for n in listing["names"] if n.upper().split(".")[0] in {"NUL", "CON", "AUX", "PRN", "COM1", "LPT1"}),
        "extended_forms_recorded": bool(extended),
        "extended_open_live": extended_open_ok,
    }
    out = {
        "probe": "probe2_dir_listing",
        "unit": "TST-0197",
        "scandir_count": walker["file_count"],
        "listdir_count": listing["count"],
        "extended_open_detail": extended_open_detail,
        "checks": checks,
        "ok": all(checks.values()),
    }
    (HERE / "probe2_dir_listing.raw.txt").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(out, sort_keys=True))
    shutil.rmtree(root, ignore_errors=True)
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
