"""Which twin pairs could be reconciled WITHOUT losing content, and in which direction.

Corrects a scoping error in _r3_direction2.py's labels. A `replace` opcode is
NOT a harmless in-place edit: a 171-line block replaced by a 100-line block is
one `replace`, and syncing either way destroys the other side's bytes just as
surely as an `insert` would. So the sync-safety question is not "which verdict"
but "which opcodes are present":

  only `delete`  -> mirror is a strict subset; mirror <- root loses nothing
  only `insert`  -> root is a strict subset; root <- mirror loses nothing
  any `replace`  -> both sides hold bytes in the same slot; a human must read it
  both delete+insert -> two-way; a human must read it

Run:  python command-center/slop-report/_r3_synctable.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

SRC = Path(__file__).with_name("_r3_direction2.out.json")
OUT = Path(__file__).with_suffix(".out.json")


def safety(opcodes: dict) -> str:
    kinds = {k for k, v in opcodes.items() if v}
    if kinds == {"delete"}:
        return "safe-mirror<-root"
    if kinds == {"insert"}:
        return "safe-root<-mirror"
    if not kinds:
        return "identical"
    return "needs-human-read"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [{**r, "sync_safety": safety(r["opcodes"])} for r in data["rows"]]

    controls = {
        "c1_delete_only_is_safe": safety({"delete": 2}) == "safe-mirror<-root",
        "c2_replace_is_never_safe": safety({"delete": 2, "replace": 1})
        == "needs-human-read",
        "c3_insert_only_is_other_direction": safety({"insert": 1})
        == "safe-root<-mirror",
        "c4_empty_is_identical": safety({}) == "identical",
    }

    tally = Counter(r["sync_safety"] for r in rows)
    payload = {
        "rev": data["rev"],
        "tally": dict(tally),
        "controls": controls,
        "all_controls_pass": all(controls.values()),
        "rows": sorted(rows, key=lambda r: (r["sync_safety"], r["root"])),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    for r in payload["rows"]:
        ops = ",".join(f"{k}:{v}" for k, v in sorted(r["opcodes"].items()))
        print(f"{r['sync_safety']:>17}  {ops:<28}  {r['root']}")
    print(f"\ntally={dict(tally)}")
    for k, v in controls.items():
        print(f"  control {k}: {v}")
    if not payload["all_controls_pass"]:
        print("FAILED:r3-synctable a control did not pass")
        return 1
    print(f"SUCCESS:r3-synctable -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
