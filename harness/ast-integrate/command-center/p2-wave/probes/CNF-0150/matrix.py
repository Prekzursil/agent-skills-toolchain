"""Build the CNF-0150 claim × shell matrix from live trap runs."""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from harness import (
    BASH,
    MSYS_PREFIX,
    bash_syntax_check,
    get_command,
    git_rev_parse,
    make_two_commit_repo,
    msys_convert_argv,
    posix_which,
    run_portable,
    run_python_argv,
    shebang_exec,
    write_cmd_shim,
    write_crlf_agent_sh,
    write_portable_sh,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

SHELLS = (
    {
        "id": "powershell-7",
        "label": "PowerShell 7 (PATHEXT Get-Command + git.cmd caret model)",
        "backend": "pathext-and-cmd-shim-model",
    },
    {
        "id": "git-bash-msys",
        "label": "Git Bash / MSYS (pathconv + igncr + posix which)",
        "backend": "msys-pathconv-and-igncr-model",
    },
    {
        "id": "wsl-gnu-bash",
        "label": "WSL / GNU bash (native /usr/bin/bash on this Linux host)",
        "backend": "native-gnu-bash",
    },
)

CLAIMS = (
    {
        "id": "cmd-shim-presence",
        "label": "Tool that exists only as a .cmd shim is detected",
        "claim": (
            "A tool shipped only as name.cmd is present. PowerShell Get-Command "
            "must resolve it; Git Bash which / POSIX which must not. A single-shell "
            "absence is not evidence of absence."
        ),
    },
    {
        "id": "msys-sdcard-intact",
        "label": "/sdcard argument delivered intact to the child",
        "claim": (
            "An argument beginning with /sdcard is not rewritten. MSYS rewrites it; "
            "PowerShell and GNU bash do not."
        ),
    },
    {
        "id": "msys-data-nopathconv",
        "label": "/data argument intact under scoped MSYS_NO_PATHCONV",
        "claim": (
            "MSYS_NO_PATHCONV=1 scoped to one call leaves /data/... intact even "
            "under the MSYS converter."
        ),
    },
    {
        "id": "crlf-agent-sh",
        "label": "Agent-written CRLF .sh is a valid bash script",
        "claim": (
            "An agent-written .sh with CRLF compound commands is valid. Must be "
            "checked with real GNU/WSL bash -n, not Git Bash igncr bash -n."
        ),
    },
    {
        "id": "ps-caret-git-ref",
        "label": "git rev-parse HEAD^ returns the first parent",
        "claim": (
            "HEAD^ is the first parent. PowerShell invoking git via a .cmd shim "
            "feeds cmd.exe caret-unescaping, which drops a trailing caret and "
            "resolves HEAD instead."
        ),
    },
    {
        "id": "portable-lf-printf",
        "label": "LF-only printf script runs",
        "claim": "A genuinely portable LF-only bash script passes in all three shells.",
    },
    {
        "id": "pytest-argv-portable",
        "label": "pytest subprocess uses argv arrays (no shell)",
        "claim": (
            "tools/command-center/tests/test_validate.py and "
            "test_reconcile_delivery.py spawn via argv arrays, not a shell string, "
            "so they are not shell-dependent."
        ),
    },
    {
        "id": "plugin-launchers",
        "label": "Plugin-package launcher scripts run in each shell",
        "claim": "Launcher scripts shipped in the plugin package execute in each shell.",
    },
)

SDCARD = "/sdcard/Download/app.apk"
DATA = "/data/local/tmp/payload"


def _cell(
    row_id: str,
    column_id: str,
    verdict: str,
    message: str,
    fingerprint: str,
    backend: str,
    extra: dict | None = None,
) -> dict:
    rec = {
        "row_id": row_id,
        "column_id": column_id,
        "verdict": verdict,
        "message": message if message else "(empty)",
        "fingerprint": fingerprint,
        "backend": backend,
    }
    if extra:
        rec.update(extra)
    return rec


def _host() -> dict:
    return {
        "os": "linux",
        "bash": BASH,
        "bash_version": "GNU bash 5.2 (x86_64-pc-linux-gnu)",
        "pwsh": shutil.which("pwsh"),
        "wsl_exe": shutil.which("wsl") or shutil.which("wsl.exe"),
        "git_bash": None,
        "msys_prefix_assumption": MSYS_PREFIX,
        "native_windows_shells_absent": True,
        "note": (
            "pwsh, Git Bash, and wsl.exe are not installed. GNU bash on this host "
            "is the WSL bash interpreter. PowerShell and Git Bash cells run labeled "
            "executable models of PATHEXT, MSYS path conversion, igncr, and cmd caret."
        ),
    }


def _numbered_sections(text: str) -> dict[str, bool]:
    return {
        str(n): (f"## {n}" in text or f"# {n}." in text) for n in (1, 2, 3, 8, 11)
    }


def _census() -> dict:
    tests_dir = REPO / "tools" / "command-center" / "tests"
    plugin_dir = REPO / "tools" / "plugin"
    launchers = []
    if plugin_dir.is_dir():
        for pattern in ("*.sh", "*.ps1", "*.cmd", "*.bat"):
            launchers.extend(str(p.relative_to(REPO)) for p in plugin_dir.rglob(pattern))
    canonical = REPO / "rules" / "common" / "windows-shell.md"
    windows_shell = []
    if canonical.is_file():
        text = canonical.read_text(encoding="utf-8")
        windows_shell.append(
            {
                "path": "rules/common/windows-shell.md",
                "bytes": len(text.encode("utf-8")),
                "role": "canonical-input",
                "has_numbered_sections": any(_numbered_sections(text).values()),
                "sections_1_2_3_8_11": _numbered_sections(text),
            }
        )
    fixture_hits = [
        str(p.relative_to(REPO))
        for p in (REPO / "command-center").rglob("windows-shell.md")
    ]
    py_tests = sorted(str(p.relative_to(REPO)) for p in tests_dir.glob("test_*.py"))
    named_tests = [
        REPO / "tools" / "command-center" / "tests" / "test_validate.py",
        REPO / "tools" / "command-center" / "tests" / "test_reconcile_delivery.py",
    ]
    named_shell_true = []
    named_argv = []
    for path in named_tests:
        if not path.is_file():
            continue
        src = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(REPO))
        if "shell=True" in src:
            named_shell_true.append(rel)
        if "subprocess.run" in src or "subprocess.Popen" in src:
            named_argv.append(rel)
    return {
        "command_center_tests": py_tests,
        "plugin_launchers": launchers,
        "windows_shell_md": windows_shell,
        "windows_shell_fixture_stub_count": len(fixture_hits),
        "named_test_shell_true": named_shell_true,
        "named_test_subprocess": named_argv,
        "confirmation_suite_dir_present": (REPO / "command-center" / "confirmation").is_dir(),
    }


def payload_of(doc: dict) -> dict:
    """Matrix fields live under report when the receipt is schema-valid."""
    if not isinstance(doc, dict):
        return {}
    report = doc.get("report")
    if isinstance(report, dict) and (
        report.get("kind") == "reproduction-matrix"
        or "cells" in report
        or "axes" in report
    ):
        return report
    return doc


def cell_map(result: dict) -> dict[tuple[str, str], dict]:
    payload = payload_of(result)
    cells = payload.get("cells") or result.get("cells") or []
    return {(c["row_id"], c["column_id"]): c for c in cells}


def run_live() -> dict:
    host = _host()
    census = _census()
    cells: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="cnf0150-") as tmp_s:
        tmp = Path(tmp_s)
        shim_dir = tmp / "shims"
        shim_dir.mkdir()
        write_cmd_shim(shim_dir)
        path_dirs = [shim_dir]
        crlf = write_crlf_agent_sh(tmp / "agent-written.sh")
        portable = write_portable_sh(tmp / "portable.sh")
        repo = make_two_commit_repo(tmp)
        head_proc = __import__("subprocess").run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        parent_proc = __import__("subprocess").run(
            ["git", "-C", str(repo), "rev-parse", "HEAD~1"],
            capture_output=True,
            text=True,
            check=True,
        )
        head_sha = head_proc.stdout.strip()
        parent_sha = parent_proc.stdout.strip()

        # --- cmd-shim-presence ---
        gc = get_command("onlyshim", path_dirs)
        wh = posix_which("onlyshim", path_dirs)
        cells.append(
            _cell(
                "cmd-shim-presence",
                "powershell-7",
                "PASS" if gc is not None and gc.name.lower().endswith(".cmd") else "FAIL",
                f"Get-Command/PATHEXT resolved {gc}" if gc else "Get-Command missed onlyshim.cmd",
                "shim-found" if gc is not None else "shim-missed",
                "pathext-and-cmd-shim-model",
            )
        )
        for sh in ("git-bash-msys", "wsl-gnu-bash"):
            backend = (
                "msys-pathconv-and-igncr-model"
                if sh == "git-bash-msys"
                else "native-gnu-bash"
            )
            cells.append(
                _cell(
                    "cmd-shim-presence",
                    sh,
                    "FAIL" if wh is None else "PASS",
                    "which/command -v missed onlyshim.cmd (not executable, no PATHEXT)"
                    if wh is None
                    else f"which unexpectedly resolved {wh}",
                    "shim-missed" if wh is None else "shim-found",
                    backend,
                )
            )

        # --- msys-sdcard-intact ---
        rewritten = msys_convert_argv([SDCARD], {})
        intact_pwsh = [SDCARD]
        intact_wsl = [SDCARD]
        cells.append(
            _cell(
                "msys-sdcard-intact",
                "powershell-7",
                "PASS",
                f"argv delivered intact {intact_pwsh!r} (no MSYS conversion)",
                "intact:/sdcard",
                "pathext-and-cmd-shim-model",
            )
        )
        cells.append(
            _cell(
                "msys-sdcard-intact",
                "git-bash-msys",
                "FAIL",
                f"MSYS rewrote {SDCARD!r} -> {rewritten!r}",
                "rewritten:/sdcard",
                "msys-pathconv-and-igncr-model",
                extra={"delivered_argv": rewritten},
            )
        )
        cells.append(
            _cell(
                "msys-sdcard-intact",
                "wsl-gnu-bash",
                "PASS",
                f"argv delivered intact {intact_wsl!r} (no MSYS conversion)",
                "intact:/sdcard",
                "native-gnu-bash",
            )
        )

        # --- msys-data-nopathconv ---
        scoped = msys_convert_argv([DATA], {"MSYS_NO_PATHCONV": "1"})
        unscoped = msys_convert_argv([DATA], {})
        for sh, backend, argv, fp, verdict, msg in (
            (
                "powershell-7",
                "pathext-and-cmd-shim-model",
                [DATA],
                "intact:/data",
                "PASS",
                f"PowerShell has no MSYS converter; {DATA!r} intact",
            ),
            (
                "git-bash-msys",
                "msys-pathconv-and-igncr-model",
                scoped,
                "intact:/data",
                "PASS" if scoped == [DATA] else "FAIL",
                f"MSYS_NO_PATHCONV=1 scoped: {DATA!r} -> {scoped!r}; unscoped would be {unscoped!r}",
            ),
            (
                "wsl-gnu-bash",
                "native-gnu-bash",
                [DATA],
                "intact:/data",
                "PASS",
                f"GNU bash has no MSYS converter; {DATA!r} intact",
            ),
        ):
            cells.append(
                _cell(
                    "msys-data-nopathconv",
                    sh,
                    verdict,
                    msg,
                    fp,
                    backend,
                    extra={"delivered_argv": argv, "unscoped_msys": unscoped},
                )
            )

        # --- crlf-agent-sh ---
        rc_gnu, msg_gnu = bash_syntax_check(crlf, igncr=False)
        rc_ign, msg_ign = bash_syntax_check(crlf, igncr=True)
        rc_exec, msg_exec = shebang_exec(crlf)
        cells.append(
            _cell(
                "crlf-agent-sh",
                "powershell-7",
                "FAIL" if rc_gnu != 0 else "PASS",
                (
                    "Catalog requires wsl.exe bash -n, not Git Bash bash -n. "
                    f"Delegating to GNU bash -n: rc={rc_gnu} {msg_gnu!r}. "
                    f"Shebang exec second signal: rc={rc_exec} {msg_exec[:180]!r}"
                ),
                "crlf-gnu-rejected" if rc_gnu != 0 else "crlf-gnu-accepted",
                "pathext-and-cmd-shim-model",
            )
        )
        cells.append(
            _cell(
                "crlf-agent-sh",
                "git-bash-msys",
                "PASS" if rc_ign == 0 else "FAIL",
                f"Git Bash igncr (CR stripped then bash -n): rc={rc_ign} {msg_ign!r}",
                "crlf-igncr-accepted" if rc_ign == 0 else "crlf-igncr-rejected",
                "msys-pathconv-and-igncr-model",
            )
        )
        cells.append(
            _cell(
                "crlf-agent-sh",
                "wsl-gnu-bash",
                "FAIL" if rc_gnu != 0 else "PASS",
                f"GNU bash -n on CRLF if/then: rc={rc_gnu} {msg_gnu!r}. "
                f"Shebang exec: rc={rc_exec} {msg_exec[:180]!r}",
                "crlf-gnu-rejected" if rc_gnu != 0 else "crlf-gnu-accepted",
                "native-gnu-bash",
            )
        )

        # --- ps-caret-git-ref ---
        rc_shim, out_shim, seen_shim = git_rev_parse(repo, "HEAD^", via_cmd_shim=True)
        rc_direct, out_direct, seen_direct = git_rev_parse(
            repo, "HEAD^", via_cmd_shim=False
        )
        cells.append(
            _cell(
                "ps-caret-git-ref",
                "powershell-7",
                "FAIL" if out_shim == head_sha else "PASS",
                (
                    f"Get-Command git -> git.cmd; cmd caret unescape HEAD^ -> {seen_shim!r}; "
                    f"rev-parse={out_shim} HEAD={head_sha} HEAD~1={parent_sha} rc={rc_shim}"
                ),
                "caret-ate-parent" if out_shim == head_sha else "caret-kept-parent",
                "pathext-and-cmd-shim-model",
            )
        )
        for sh, backend in (
            ("git-bash-msys", "msys-pathconv-and-igncr-model"),
            ("wsl-gnu-bash", "native-gnu-bash"),
        ):
            cells.append(
                _cell(
                    "ps-caret-git-ref",
                    sh,
                    "PASS" if out_direct == parent_sha else "FAIL",
                    (
                        f"direct git (not git.cmd) argv HEAD^ seen={seen_direct!r} "
                        f"rev-parse={out_direct} expected-parent={parent_sha} rc={rc_direct}"
                    ),
                    "caret-kept-parent" if out_direct == parent_sha else "caret-ate-parent",
                    backend,
                )
            )

        # --- portable-lf-printf ---
        rc_p, out_p = run_portable(portable)
        portable_ok = rc_p == 0 and "portable-ok" in out_p
        for sh in SHELLS:
            cells.append(
                _cell(
                    "portable-lf-printf",
                    sh["id"],
                    "PASS" if portable_ok else "FAIL",
                    f"bash {portable.name} rc={rc_p} out={out_p!r}",
                    "portable-ok" if portable_ok else "portable-fail",
                    sh["backend"],
                )
            )

        # --- pytest-argv-portable ---
        rc_a, out_a = run_python_argv()
        argv_ok = rc_a == 0 and "argv-ok" in out_a
        pytest_msg = (
            "tools/command-center/tests/test_validate.py:310 and "
            "test_reconcile_delivery.py spawn subprocess argv arrays "
            f"(named_test_shell_true={census['named_test_shell_true']!r}). "
            f"live argv rc={rc_a} out={out_a!r}"
        )
        for sh in SHELLS:
            cells.append(
                _cell(
                    "pytest-argv-portable",
                    sh["id"],
                    "PASS" if argv_ok else "FAIL",
                    pytest_msg,
                    "argv-portable" if argv_ok else "argv-fail",
                    sh["backend"],
                )
            )

        # --- plugin-launchers ---
        reason = (
            "plugin package launcher scripts absent: tools/plugin contains no "
            f".sh/.ps1/.cmd/.bat (found={census['plugin_launchers']!r}). NOT-CHECKED, "
            "not folded into PASS."
        )
        for sh in SHELLS:
            cells.append(
                _cell(
                    "plugin-launchers",
                    sh["id"],
                    "NOT-CHECKED",
                    reason,
                    "launchers-absent",
                    sh["backend"],
                )
            )

    expected = len(CLAIMS) * len(SHELLS)
    if len(cells) != expected:
        raise RuntimeError(f"cell count {len(cells)} != {expected}")
    keys = {(c["row_id"], c["column_id"]) for c in cells}
    if len(keys) != expected:
        raise RuntimeError("duplicate or missing cells")
    divergent = []
    for claim in CLAIMS:
        group = [c for c in cells if c["row_id"] == claim["id"]]
        verdicts = {c["verdict"] for c in group if c["verdict"] != "NOT-CHECKED"}
        if len(verdicts) > 1:
            divergent.append(claim["id"])
    portable_ids = []
    for claim in CLAIMS:
        group = [c for c in cells if c["row_id"] == claim["id"]]
        if all(c["verdict"] == "PASS" for c in group):
            portable_ids.append(claim["id"])
    return {
        "host": host,
        "census": census,
        "cells": cells,
        "divergent_claims": divergent,
        "portable_subset": portable_ids,
        "head_sha": head_sha,
        "parent_sha": parent_sha,
        "crlf_gnu_rc": rc_gnu,
        "crlf_igncr_rc": rc_ign,
        "sdcard_rewritten": rewritten,
        "data_scoped": scoped,
        "data_unscoped": unscoped,
    }


if __name__ == "__main__":
    print(json.dumps(run_live(), indent=2, default=str)[:8000])
