#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "command-center/p2-wave/probes/ADV-0041/scratch/stage-real-plugin/tools/plugin"
DST = REPO / "tools/plugin"
TRASH = REPO / "command-center/p2-wave/ovh-monitor/g1-shards/_trash"


def main() -> None:
    for name in ("layout_fingerprints.py", "layout_fixtures.py"):
        text = (SRC / name).read_text(encoding="utf-8")
        text = text.replace("import strict_json as sj  # noqa: E402", "import json as sj")
        lines = []
        skip_lib = False
        for ln in text.splitlines():
            if "_LIB = Path(__file__).resolve().parent.parent / \"lib\"" in ln:
                skip_lib = True
                continue
            if skip_lib:
                if ln.startswith("import json as sj") or ln.startswith("import strict_json"):
                    skip_lib = False
                    continue
                if "sys.path.insert" in ln or ln.startswith("if str(_LIB)"):
                    continue
                skip_lib = False
            lines.append(ln)
        if name == "layout_fixtures.py" and "import json as sj" not in "\n".join(lines):
            # ensure json alias exists after pathlib import
            out = []
            inserted = False
            for ln in lines:
                out.append(ln)
                if (not inserted) and ln.startswith("from pathlib import Path"):
                    out.append("import json as sj")
                    inserted = True
            lines = out
        (DST / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print("wrote", name, (DST / name).stat().st_size)

    TRASH.mkdir(parents=True, exist_ok=True)
    design = REPO / "command-center/phase3/A8/DESIGN.json"
    if design.is_file():
        shutil.copy2(design, TRASH / "ARC-0055-A8-DESIGN.json")
        design.unlink()
        print("moved DESIGN.json")
    else:
        print("DESIGN.json absent")


if __name__ == "__main__":
    main()
