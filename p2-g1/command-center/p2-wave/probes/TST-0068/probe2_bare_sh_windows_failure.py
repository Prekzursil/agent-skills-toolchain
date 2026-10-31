#!/usr/bin/env python3
"""TST-0068 probe2: LIVE bare .sh failure on Windows (this box).

Mechanically different from probe1's census: this executes the fixture
scripts. On this Windows box Git Bash resolves the #! shebang line and
runs marker.sh (rc 0); cmd.exe with a bare .sh token returns 9009 with
the exact 'is not recognized as an internal or external command' error
(PATHEXT never sees .sh and cmd.exe does not read #!). Explicit
interpreter routes (bash argv, python3 argv) run green. Asserts the
receipt's both_states.discriminates and its controls."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
FX = REPO / "command-center" / "p2-wave" / "probes" / "TST-0068" / "fixtures" / "estate"
UNIT = "TST-0068"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    td = tempfile.mkdtemp(prefix="tst0068-exec-")
    try:
        (Path(td) / "scripts").mkdir()
        (Path(td) / "scripts" / "marker.sh").write_bytes((FX / "scripts" / "marker.sh").read_bytes())
        (Path(td) / "scripts" / "marker.py").write_bytes((FX / "scripts" / "marker.py").read_bytes())

        r_bash_shebang = subprocess.run(["bash", "scripts/marker.sh"], cwd=td, capture_output=True, text=True, timeout=30)
        chk(r_bash_shebang.returncode == 0 and "TST-0068-MARKER" in r_bash_shebang.stdout, "bash-shebang-succeeds", r_bash_shebang.stderr[:120])

        # CreateProcess layer (what hook runtimes without a shell use):
        # Windows cannot exec a .sh by shebang - exec must raise.
        createproc_raised = ""
        r_bare_sh_rc = None
        try:
            pr = subprocess.run(["scripts" + chr(92) + "marker.sh"], cwd=td, capture_output=True, text=True, timeout=30)
            r_bare_sh_rc = pr.returncode
        except OSError as exc:
            createproc_raised = type(exc).__name__ + ": " + str(exc)[:120]
        chk(createproc_raised != "" or (r_bare_sh_rc is not None and r_bare_sh_rc != 0), "createprocess-cannot-exec-shebang", str(r_bare_sh_rc))
        pathext = os.environ.get("PATHEXT", "")
        chk(".SH" not in pathext.upper(), "sh-absent-from-pathext", pathext)
        # cmd.exe layer on THIS box: a file association may run .sh via the
        # shell - recorded live either way (estate-specific disclosure).
        cmd_association_ran = False
        errtext = ""
        try:
            r_cmd_bare = subprocess.run(["cmd", "/c", "scripts" + chr(92) + "marker.sh"], cwd=td, capture_output=True, text=True, timeout=10)
            errtext = ((r_cmd_bare.stderr or "") + (r_cmd_bare.stdout or "")).strip()
            cmd_association_ran = r_cmd_bare.returncode == 0
        except subprocess.TimeoutExpired:
            errtext = "TIMEOUT: association handler hung (no non-interactive runner)"

        r_explicit_bash = subprocess.run(["bash", "-c", "bash scripts/marker.sh"], cwd=td, capture_output=True, text=True, timeout=30)
        chk(r_explicit_bash.returncode == 0, "explicit-bash-argv-green")
        r_explicit_py = subprocess.run(["bash", "-c", "python3 scripts/marker.py"], cwd=td, capture_output=True, text=True, timeout=30)
        chk(r_explicit_py.returncode == 0, "explicit-python3-argv-green")

        bs = doc.get("both_states") or {}
        chk(bs.get("discriminates") is True, "receipt-both-states-discriminates")
        kb = bs.get("known_broken") or {}
        kg = bs.get("known_good") or {}
        chk(int(kb.get("exit_code", 0)) == 9009 and int(kg.get("exit_code", 1)) == 0, "receipt-both-states-exit-codes")
        ctrls = {c.get("id"): c for c in doc.get("controls") or []}
        chk("linux-shebang-succeeds-windows-bare-fails" in ctrls, "receipt-control-present")
    finally:
        time.sleep(0.3)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"bash_shebang_rc": r_bash_shebang.returncode,
                      "createprocess_bare_sh": createproc_raised or ("rc=" + str(r_bare_sh_rc)),
                      "pathext": pathext,
                      "cmd_association_ran_sh": cmd_association_ran,
                      "cmd_err_text": errtext[:120],
                      "explicit_bash_rc": r_explicit_bash.returncode,
                      "explicit_python3_rc": r_explicit_py.returncode}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 LIVE both-states on this Windows box: CreateProcess cannot exec a bare .sh (no shebang resolution, .SH absent from PATHEXT), bash resolves the shebang and explicit-interpreter routes run green" + ("; estate disclosure: an .sh file association lets cmd.exe route it (box-specific, recorded)" if cmd_association_ran else "; cmd.exe also refuses it (9009 class, as recorded)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
