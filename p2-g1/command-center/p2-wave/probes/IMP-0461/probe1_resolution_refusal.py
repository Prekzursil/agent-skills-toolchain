#!/usr/bin/env python3
"""IMP-0461 probe1: explicit interpreter resolution.

Builds the resolution table for "bash" from BOTH shell PATH domains (msys
Git bash vs the Windows system bash, which is the WSL launcher), shows the
two shells disagree on the same interpreter name, refuses bare invocation,
and proves the CRLF script is executed only under the tolerant interpreter
while the strict (WSL system) family gives a typed refusal."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EI_PY = REPO / "tools" / "launcher" / "explicit_interpreter.py"

spec = importlib.util.spec_from_file_location("imp0461_explicit_interpreter", EI_PY)
E = importlib.util.module_from_spec(spec)
sys.modules["imp0461_explicit_interpreter"] = E
spec.loader.exec_module(E)


def shell_domains():
    path_dirs = [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    msys_dirs, sys_dirs = [], []
    for d in path_dirs:
        dl = d.replace(chr(92), "/").lower()
        if "/git/" in dl or "msys" in dl:
            msys_dirs.append(d)
        elif "system32" in dl or "windowsapps" in dl:
            sys_dirs.append(d)
    return {"msys": msys_dirs, "wsl-system": sys_dirs}


def fail(msg):
    print("FAILED:IMP-0461-probe1 " + str(msg))
    return 1


def main() -> int:
    shells = shell_domains()
    if not shells["msys"] or not shells["wsl-system"]:
        return fail("both shell domains must exist on this box: %s" % json.dumps(shells))

    table = E.resolve_name("bash", shells)
    rows = table.as_dict()["rows"]
    msys_path = table.path_for_shell("msys")
    wsl_path = table.path_for_shell("wsl-system")
    if not table.both_consulted:
        return fail("resolver did not consult both shells: %s" % json.dumps(rows))
    if not table.shells_disagree:
        return fail("shells did not disagree on the same interpreter name: %s" % json.dumps(rows))
    if not msys_path or not wsl_path:
        return fail("a shell resolved to nothing: msys=%s wsl=%s" % (msys_path, wsl_path))
    if Path(msys_path).resolve() == Path(wsl_path).resolve():
        return fail("both shells resolved to the same file - disagreement vacuous")

    classification = {
        "msys": E.classify_bash(msys_path),
        "wsl-system": E.classify_bash(wsl_path),
    }
    if classification["msys"] != "msys" or classification["wsl-system"] != "wsl-system":
        return fail("classification wrong: %s" % json.dumps(classification))

    # Bare invocation must be refused before any argv is built.
    bare_refused = False
    try:
        E.argv_for("script.sh")
    except E.BareInvocationRefused:
        bare_refused = True
    if not bare_refused:
        return fail("bare script invocation was NOT refused")
    try:
        E.launch(Path("script.sh"))
        return fail("launch() without interpreter did not raise")
    except E.BareInvocationRefused:
        pass

    tmp = Path(tempfile.mkdtemp(prefix="imp0461-p1-"))
    lf = tmp / "lf.sh"
    lf.write_bytes(b"#!/bin/bash\necho IMP0461_LF_OK\n")
    crlf = tmp / "crlf.sh"
    crlf.write_bytes(b"#!/bin/bash\r\necho hi\r\n")

    # CRLF under the STRICT family (wsl system bash): typed refusal rc=2.
    strict = E.launch(crlf, interpreter=wsl_path, family="wsl-system")
    strict_rc = strict.returncode
    strict_err = strict.stderr or ""
    if strict_rc == 0:
        return fail("CRLF script executed successfully under the strict wsl-system family")
    if "CRLF" not in strict_err and "CRLF" not in (strict.stdout or ""):
        return fail("strict-family CRLF refusal not typed: rc=%s err=%r" % (strict_rc, strict_err[:80]))

    # Live control: the real Windows system bash demonstrably cannot take
    # this invocation (it mangles the Windows path - recorded, must not be
    # a silent success).
    live = subprocess.run([wsl_path, str(crlf)], capture_output=True, text=True, timeout=120)
    live_ok = live.returncode == 0 and "hi" in (live.stdout or "")

    # The TOLERANT interpreter (msys) runs the same CRLF script fine, and
    # the family-resolved argv targets exactly the msys binary.
    tolerant = subprocess.run([msys_path, str(crlf)], capture_output=True, text=True, timeout=120)
    if tolerant.returncode != 0 or "hi" not in (tolerant.stdout or ""):
        return fail("msys bash failed on CRLF script: rc=%s out=%r err=%r" % (
            tolerant.returncode, tolerant.stdout[:40], tolerant.stderr[:80]))
    argv_msys = E.argv_for(crlf, interpreter="bash", family="msys", shells=shells)
    if Path(argv_msys[0]).resolve() != Path(msys_path).resolve():
        return fail("family-resolved argv did not target the msys binary: %s" % argv_msys[0])
    lf_run = subprocess.run([msys_path, str(lf)], capture_output=True, text=True, timeout=120)
    if lf_run.returncode != 0 or "IMP0461_LF_OK" not in (lf_run.stdout or ""):
        return fail("msys bash failed on LF script")

    print(json.dumps({
        "probe": "probe1-resolution-refusal",
        "unit_id": "IMP-0461",
        "resolution_table": rows,
        "shells_disagree": table.shells_disagree,
        "both_consulted": table.both_consulted,
        "classification": classification,
        "bare_invocation_refused": bare_refused,
        "crlf_strict_family_rc": strict_rc,
        "crlf_strict_family_err": strict_err.strip()[:80],
        "crlf_live_system_bash_rc": live.returncode,
        "crlf_live_system_bash_ok": live_ok,
        "crlf_live_system_bash_err": (live.stderr or "").strip()[:90],
        "crlf_msys_rc": tolerant.returncode,
        "crlf_msys_ok": tolerant.returncode == 0,
        "lf_msys_rc": lf_run.returncode,
        "family_argv_targets_msys": True,
        "sentinel": "SENTINEL:IMP-0461:INTERPRETER-EXPLICIT",
    }, indent=2))
    print("SUCCESS:IMP-0461-probe1 both shells resolved and disagreeing; bare refused; CRLF refused under strict family, executed under msys")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
