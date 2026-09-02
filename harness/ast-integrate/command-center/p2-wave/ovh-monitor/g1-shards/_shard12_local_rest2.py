#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
WRAPPER = REPO / "command-center" / "p2-wave" / "seed-stage" / "g1_python.py"
OUT = HERE / "_shard12_local_rest2.jsonl"
IDS = [
    "CC-0008", "CNF-0025", "CNF-0098", "CNF-0154", "CNL-0020", "CNL-0068",
    "IMP-0001", "IMP-0091", "IMP-0120", "IMP-0146", "IMP-0209", "IMP-0238",
    "IMP-0265", "IMP-0291", "IMP-0393", "IMP-0430", "IMP-0460",
    "REL-0007", "RES-0022", "RES-0113", "RES-0160", "RES-0182", "SYN-0028",
    "TST-0023", "TST-0057", "TST-0106", "TST-0141", "TST-0163", "TST-0208",
    "TST-0235", "TST-0264", "TST-0297", "TST-0321",
    "WFA-0031", "WFA-0084", "WFA-0134",
]
env = os.environ.copy()
env["PYTHONDONTWRITEBYTECODE"] = "1"
env["AST_INTEGRATE_ROOT"] = str(REPO)
env["PYTHONPATH"] = os.pathsep.join(
    [
        str(REPO / "command-center" / "p2-wave" / "seed-stage"),
        str(REPO),
        str(REPO / "tools"),
        str(REPO / "tools" / "measure-guard"),
        str(REPO / "platform" / "lib"),
        str(REPO / "tools" / "agentspec"),
    ]
)


def cmds(uid: str) -> list[Path]:
    pdir = REPO / "command-center" / "p2-wave" / "probes" / uid
    out = []
    for globn in ("probe1*.py", "probe2*.py"):
        paths = sorted(pdir.glob(globn))
        named = [p for p in paths if p.name not in {"probe1.py", "probe2.py"}]
        pick = named[0] if named else (paths[0] if paths else None)
        if pick is not None:
            out.append(pick)
    return out


def main() -> None:
    if OUT.exists():
        OUT.unlink()
    with OUT.open("a", encoding="utf-8") as fh:
        for uid in IDS:
            for script in cmds(uid):
                try:
                    p = subprocess.run(
                        [sys.executable, "-B", str(WRAPPER), str(script)],
                        cwd=str(REPO),
                        capture_output=True,
                        text=True,
                        timeout=40,
                        env=env,
                    )
                    text = ((p.stdout or "") + (p.stderr or "")).strip()
                    tail = text.splitlines()[-6:]
                    rc = p.returncode
                except subprocess.TimeoutExpired:
                    rc, tail = 124, ["TIMEOUT"]
                fh.write(json.dumps({"id": uid, "script": script.name, "rc": rc, "tail": tail}) + "\n")
                fh.flush()
                last = tail[-1] if tail else ""
                print(f"{'OK' if rc==0 else 'FAIL'}\t{uid}\t{script.name}\trc={rc}\t{last[:120]}", flush=True)


if __name__ == "__main__":
    main()
