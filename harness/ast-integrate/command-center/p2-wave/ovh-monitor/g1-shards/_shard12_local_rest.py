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
OUT = HERE / "_shard12_local_rest.jsonl"
DONE = {
    "ADV-0072", "ADV-0098", "ADV-0121",
    "IMP-0026", "IMP-0047", "IMP-0073", "IMP-0177", "IMP-0315", "IMP-0338", "IMP-0361",
}
IDS = [
    ln.strip()
    for ln in (HERE / "shard-12.txt").read_text(encoding="utf-8").splitlines()
    if ln.strip() and ln.strip() not in DONE
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
                        timeout=45,
                        env=env,
                    )
                    text = ((p.stdout or "") + (p.stderr or "")).strip()
                    tail = text.splitlines()[-8:]
                    rc = p.returncode
                except subprocess.TimeoutExpired:
                    rc, tail = 124, ["TIMEOUT"]
                row = {"id": uid, "script": script.name, "rc": rc, "tail": tail}
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                last = tail[-1] if tail else ""
                mark = "OK" if rc == 0 else "FAIL"
                print(f"{mark}\t{uid}\t{script.name}\trc={rc}\t{last[:140]}", flush=True)


if __name__ == "__main__":
    main()
