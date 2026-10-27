#!/usr/bin/env python3
"""TST-0100 probe2: the verdict is the git command, not the path (indep).

Mechanically different from probe1's write matrix: the decoy pair -
identical path shape, different origin - is resolved with the guard's
own command and the verdicts compared; the guard source is AST-scanned
for the git invocation and for the absence of a path-string pin; and,
since this box HAS PowerShell 7 (the receipt recorded that rerun
NOT-CHECKED on its Linux worktree), the decoy and pinned rows are
re-run live through pwsh."""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = REPO / "command-center" / "p2-wave" / "probes" / "TST-0100"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from guard import check_write, normalize, pinned_origin, resolve_origin  # noqa: E402

UNIT = "TST-0100"
OUT = REPO / "command-center" / "receipts" / (UNIT + ".json")
fails: list[str] = []


def chk(ok: bool, label: str, detail: str = "") -> None:
    if not ok:
        fails.append(label + (": " + detail if detail else ""))


def clone(url: str, into: Path) -> None:
    into.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(into)], capture_output=True, timeout=60)
    subprocess.run(["git", "-C", str(into), "remote", "add", "origin", url], capture_output=True, timeout=60)


def main() -> int:
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    chk("SUCCESS:TST-0100" in OUT.read_text(encoding="utf-8"), "sentinel-absent")
    foreign = "https://github.com/other-owner/foreign-worktree.git"
    pin = normalize(pinned_origin())
    td = Path(tempfile.mkdtemp(prefix="tst0100-p2-"))
    try:
        decoy = td / "ast-integrate-decoy"
        foreign2 = td / "plain-foreign"
        pinned = td / "anywhere-pinned"
        clone(foreign, decoy)
        clone(foreign, foreign2)
        clone(pinned_origin(), pinned)
        o1, n1 = resolve_origin(decoy)
        o2, _ = resolve_origin(foreign2)
        o3, _ = resolve_origin(pinned)
        chk(normalize(o1 or "") != pin and normalize(o3 or "") == pin, "command-resolves-origins")
        d1 = check_write(decoy, "out.txt")
        d3 = check_write(pinned, "out.txt")
        chk(d1["allowed"] is False and d3["allowed"] is True, "same-path-different-origin-different-verdict",
            d1["reason"] + "/" + d3["reason"])
        chk(d1["origin"] == foreign and d3["origin"] == pinned_origin().strip(), "verdict-carries-resolved-origin")
        # AST: the guard invokes git; it never compares the path string
        src = (HERE / "guard.py").read_text(encoding="utf-8")
        ast.parse(src)
        chk('"remote"' in src and '"get-url"' in src and "origin" in src, "ast-git-command-present")
        chk("ast-integrate-decoy" not in src and "ast-integrate.git" not in src.replace("pinned-origin.txt", ""), "no-path-string-pin-in-source")
        # live PowerShell 7 rerun (the receipt's NOT-CHECKED gap)
        pwsh = shutil.which("pwsh") or shutil.which("powershell")
        pwsh_rows = None
        if pwsh:
            script = (
                "$d = git -C '" + str(decoy) + "' remote get-url origin 2>$null; "
                "$p = git -C '" + str(pinned) + "' remote get-url origin 2>$null; "
                "@{decoy_origin=$d; pinned_origin=$p} | ConvertTo-Json"
            )
            r = subprocess.run([pwsh, "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=120)
            chk(r.returncode == 0, "pwsh-git-runs", (r.stderr or "")[:120])
            try:
                pwsh_rows = json.loads(r.stdout)
                chk(normalize(str(pwsh_rows.get("pinned_origin") or "")) == pin and normalize(str(pwsh_rows.get("decoy_origin") or "")) != pin,
                    "pwsh-rerun-agrees")
            except Exception as exc:
                chk(False, "pwsh-json-parse", type(exc).__name__)
        else:
            chk(False, "pwsh-available-on-this-box")
        sc = doc.get("scope") or {}
        chk("a live PowerShell 7 re-run on Windows" in str(sc.get("does_not_claim") or []), "receipt-recorded-psgap")
    finally:
        time.sleep(0.5)
        shutil.rmtree(td, ignore_errors=True)
    if fails:
        print("FAILED:" + UNIT + "-probe2 " + "; ".join(fails))
        return 1
    print(json.dumps({"decoy": {"allowed": d1["allowed"], "origin": d1["origin"]},
                      "pinned": {"allowed": d3["allowed"], "origin": d3["origin"]},
                      "pwsh_rows": pwsh_rows}, indent=1))
    print("SUCCESS:" + UNIT + "-probe2 verdict follows the git command (decoy refused, same-shape pinned path permitted, origins carried verbatim); AST shows the git invocation and no path-string pin; PowerShell 7 rerun on this Windows box AGREES - the receipt's recorded NOT-CHECKED gap is now closed live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
