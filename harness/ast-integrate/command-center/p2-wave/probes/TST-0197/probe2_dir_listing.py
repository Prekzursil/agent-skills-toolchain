#!/usr/bin/env python3
"""Probe 2: independent dir-listing count over the same reserved-name tree.

Signal (b): os.listdir recursion, not the enumerator’s os.scandir walker.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import campaign as C  # noqa: E402
import enumerator as E  # noqa: E402

ART = REPO / "command-center/receipts/TST-0197.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0197-probe2 {msg}")
    return 1


def find_listing(root: Path) -> list[str] | None:
    find_bin = shutil.which("find")
    if not find_bin:
        return None
    proc = subprocess.run(
        [find_bin, str(root), "-type", "f", "-printf", "%P\\n"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return sorted(line for line in proc.stdout.splitlines() if line)


def pwsh_present() -> str | None:
    return shutil.which("pwsh")


def main() -> int:
    result = C.run_campaign()
    enum_h = result["enumerator_hostile"]
    list_h = result["dirlist_hostile"]
    planted = result["planted_hostile"]
    checks = result["checks"]

    if not list_h["complete"]:
        return fail(f"dir listing incomplete errors={list_h.get('errors')}")
    if list_h["count"] != planted["planted_count"]:
        return fail(
            f"listdir count {list_h['count']} != planted {planted['planted_count']}"
        )
    if not checks["counts_match"]:
        return fail(
            f"enumerator count {enum_h.get('count')} != listdir {list_h.get('count')} "
            f"rels_enum={enum_h.get('rels')} rels_list={list_h.get('rels')}"
        )
    listed_reserved = sorted(
        p.upper()
        for p in list_h["rels"]
        if E.is_reserved_device_name(Path(p).name)
    )
    if listed_reserved != sorted(E.RESERVED_BASENAMES):
        return fail(f"listdir missed reserved names {listed_reserved}")

    find_rels = find_listing(Path(planted["root"]))
    find_ok = find_rels is not None and find_rels == sorted(list_h["rels"])
    if find_rels is not None and not find_ok:
        return fail(
            f"find listing diverged find={find_rels} listdir={list_h['rels']}"
        )

    pwsh = pwsh_present()

    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        blob = json.dumps(doc)
        if "SUCCESS:TST-0197" not in blob:
            return fail("receipt sentinel absent")
        pub = (doc.get("evidence") or {}).get("dir_listing") or {}
        if pub.get("count") != list_h["count"]:
            return fail(
                f"receipt dir_listing count {pub.get('count')} != live {list_h['count']}"
            )

    summary = {
        "probe": "probe2-dir-listing",
        "unit_id": "TST-0197",
        "pass": True,
        "listdir_count": list_h["count"],
        "enumerator_count": enum_h["count"],
        "counts_match": True,
        "reserved_in_listing": listed_reserved,
        "find_count": None if find_rels is None else len(find_rels),
        "find_agrees": find_ok if find_rels is not None else None,
        "pwsh_binary": pwsh,
        "api": list_h["api"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"listdir={list_h['count']} enumerator={enum_h['count']} "
        f"reserved={listed_reserved} find={summary['find_count']} pwsh={pwsh}"
    )
    print(
        "SUCCESS:TST-0197-probe2 independent os.listdir count matches "
        "enumerator; reserved names present"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
