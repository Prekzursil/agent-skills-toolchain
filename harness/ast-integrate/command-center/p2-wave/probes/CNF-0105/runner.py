#!/usr/bin/env python3
"""Live three-interpreter matrix for CNF-0105."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures"
STANDIN = FIX / "git-bash-standin.sh"
POSIX_ARG = "/tmp/cnf-0105-abs-posix"
INTERP_IDS = ("pwsh7", "git-bash", "wsl-bash")
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
SUFFIXES = {".sh", ".bash", ".ps1", ".bat", ".cmd"}
SHIPPED_ROOTS = ("scripts", "release/platforms")
STUB_MARK = b"printf 'cnf-0105-shebang-stub\\n'\nexit 0\n"
SHEBANG_NEEDLES = (
    "#!/bin/bash",
    "#!/usr/bin/bash",
    "#!/usr/bin/env bash",
    "#!/bin/sh",
    "#!/usr/bin/env sh",
    "#!/usr/bin/env pwsh",
    "#!/usr/bin/pwsh",
)


def parse_shebang(path: Path) -> str | None:
    try:
        raw = path.read_bytes()[:200]
    except OSError:
        return None
    if not raw.startswith(b"#!"):
        return None
    line = raw.split(b"\n", 1)[0].replace(b"\r", b"").decode("utf-8", "replace")
    return line.strip() or None


def bash_version() -> str:
    p = subprocess.run(
        ["/bin/bash", "--version"], capture_output=True, text=True, timeout=10
    )
    lines = (p.stdout or p.stderr or "").splitlines()
    return lines[0].strip() if lines else "bash-unknown"


def discover_interpreters() -> list[dict]:
    pwsh = shutil.which("pwsh") or shutil.which("pwsh-preview")
    msys = shutil.which("git-bash")
    pwsh_ver = "absent"
    if pwsh:
        r = subprocess.run(
            [pwsh, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        pwsh_ver = (r.stdout or r.stderr or "").strip() or "pwsh-present"
    return [
        {
            "id": "pwsh7",
            "present": bool(pwsh),
            "argv0": pwsh or "",
            "version": pwsh_ver,
            "kind": "real-binary" if pwsh else "absent",
        },
        {
            "id": "git-bash",
            "present": bool(msys),
            "argv0": STANDIN.relative_to(REPO).as_posix(),
            "version": (
                "MSYS Git Bash present"
                if msys
                else "MSYS Git Bash absent; igncr behavior stand-in"
            ),
            "kind": "real-binary" if msys else "behavior-standin",
            "msys_path": msys or "",
        },
        {
            "id": "wsl-bash",
            "present": Path("/bin/bash").is_file(),
            "argv0": "/bin/bash",
            "version": bash_version(),
            "kind": "linux-bash-as-wsl-equivalent",
            "note": (
                "Host is Linux. Catalog real WSL bash is GNU bash; this is "
                "/bin/bash, not Git Bash, not Windows WSL interop."
            ),
        },
    ]


def census_union() -> list[dict]:
    """Shipped launchers only: scripts/ and release/platforms/.

    The catalog asks for the union of shipped scripts and fix-touched
    scripts, not every probe fixture in the worktree. Walking the whole
    repo would execute (or even enumerate) thousands of skill helpers.
    """
    rows: list[dict] = []
    roots = [REPO / rel for rel in SHIPPED_ROOTS if (REPO / rel).is_dir()]
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            base = Path(dirpath)
            for name in filenames:
                path = base / name
                try:
                    rel = path.relative_to(REPO).as_posix()
                except ValueError:
                    continue
                suf = path.suffix.lower()
                she = parse_shebang(path)
                is_script = suf in SUFFIXES
                if not is_script and she:
                    low = she.lower()
                    is_script = any(n in low for n in SHEBANG_NEEDLES)
                if not is_script:
                    continue
                rows.append(
                    {
                        "path": rel,
                        "declared_interpreter": she,
                        "explicit": bool(she),
                        "source": "shipped-tree-census",
                        "suffix": suf,
                    }
                )
    rows.sort(key=lambda r: r["path"])
    return rows


def shebang_stub(script: Path) -> Path:
    """Preserve the first line (shebang + CR if present); replace the body.

    Several shipped launchers mutate ~/.claude, ~/.local/bin, backups, or
    start daemons. The catalog still requires an interpreter result per
    script. A shebang-preserving stub surfaces CRLF / missing-interpreter
    / implicit-shebang defects without running the production body.
    """
    raw = script.read_bytes()
    first, _sep, _rest = raw.partition(b"\n")
    fd, name = tempfile.mkstemp(prefix="cnf0105-stub-", suffix=script.suffix or ".sh")
    os.close(fd)
    dest = Path(name)
    if first.startswith(b"#!"):
        dest.write_bytes(first + b"\n" + STUB_MARK)
    else:
        dest.write_bytes(STUB_MARK)
    _chmod_exec(dest)
    return dest


def _chmod_exec(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_fixtures() -> dict[str, Path]:
    FIX.mkdir(parents=True, exist_ok=True)
    ok = FIX / "ok-lf.sh"
    ok.write_bytes(
        b"#!/usr/bin/env bash\n"
        b"printf 'ok-lf argv=%s\\n' \"$*\"\n"
        b"command -v printf >/dev/null || exit 97\n"
        b"exit 0\n"
    )
    _chmod_exec(ok)

    crlf = FIX / "control-crlf.sh"
    crlf.write_bytes(
        b"#!/usr/bin/env bash\r\n"
        b"echo crlf-control-should-fail-on-strict-bash\r\n"
        b"exit 0\r\n"
    )
    _chmod_exec(crlf)

    apos = FIX / "control-apostrophe.sh"
    apos.write_bytes(
        b"#!/usr/bin/env bash\n"
        b"# can't / won't / shouldn't - apostrophes live in this file body\n"
        b"printf \"it's-ok argv=%s\\n\" \"$*\"\n"
        b"exit 0\n"
    )
    _chmod_exec(apos)

    implicit = FIX / "implicit-no-shebang.sh"
    implicit.write_bytes(b"echo implicit-no-shebang\nexit 0\n")
    _chmod_exec(implicit)

    ps1 = FIX / "ok.ps1"
    ps1.write_bytes(b"#!/usr/bin/env pwsh\nWrite-Output \"ok-ps1\"\nexit 0\n")

    if STANDIN.is_file() and b"\r" in STANDIN.read_bytes():
        # The editor may save this wrapper as CRLF; rewrite LF-only before use.
        pass
    STANDIN.write_bytes(
        b"#!/usr/bin/env bash\n"
        b"set -eu\n"
        b'if [ "$#" -lt 1 ]; then echo "git-bash-standin: usage" >&2; exit 2; fi\n'
        b"target=$1\n"
        b"shift\n"
        b'if [ ! -f "$target" ]; then echo "git-bash-standin: not a file" >&2; exit 127; fi\n'
        b"tmp=$(mktemp)\n"
        b"tr -d '\\r' < \"$target\" > \"$tmp\"\n"
        b"exec /bin/bash \"$tmp\" \"$@\"\n"
    )
    _chmod_exec(STANDIN)
    return {
        "ok_lf": ok,
        "crlf": crlf,
        "apostrophe": apos,
        "implicit": implicit,
        "ps1": ps1,
        "standin": STANDIN,
    }


def _first_error(stdout: str, stderr: str) -> str:
    for blob in (stderr, stdout):
        for line in blob.splitlines():
            t = line.strip()
            if t:
                return t[:400]
    return ""


def classify(
    script_rel: str, interp: str, code: int | None, err: str, explicit: bool
) -> str:
    low = (err or "").lower()
    if code is None or "interpreter-absent" in low:
        return "interpreter-absent"
    if "implicit-no-shebang" in script_rel and not explicit:
        return "implicit-interpreter"
    if code == 0:
        return "ok"
    if "bash\r" in low or "bad interpreter" in low or "\\r" in err:
        return "crlf-artifact"
    if interp == "pwsh7" and script_rel.endswith((".sh", ".bash")):
        return "interpreter-mismatch"
    if interp in ("wsl-bash", "git-bash") and script_rel.endswith(".ps1"):
        return "interpreter-mismatch"
    if "enoexec" in low or "exec format" in low:
        return "exec-failed"
    if not explicit:
        return "implicit-interpreter"
    return "exec-failed"


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def run_one(
    script: Path,
    interp: str,
    interps: list[dict],
    args: list[str] | None = None,
    *,
    extra_env: dict[str, str] | None = None,
    path_name: str | None = None,
) -> dict:
    args = list(args or [])
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    rel = _rel(script)
    meta = {i["id"]: i for i in interps}[interp]
    she = parse_shebang(script)
    explicit = bool(she)

    if interp == "pwsh7" and not meta["present"]:
        return {
            "script": path_name or rel,
            "interpreter": interp,
            "invocation": ["pwsh", "-NoProfile", "-File", rel, *args],
            "exit_code": None,
            "first_error_line": "interpreter-absent: pwsh7 not on PATH",
            "classification": "interpreter-absent",
            "stdout": "",
            "stderr": "",
            "declared_interpreter": she,
            "explicit": explicit,
        }

    if interp == "pwsh7":
        cmd = [meta["argv0"], "-NoProfile", "-File", str(script), *args]
    elif interp == "git-bash":
        cmd = [str(STANDIN), str(script), *args]
    elif path_name:
        cmd = [path_name, *args]
    else:
        cmd = [str(script), *args]

    try:
        proc = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, timeout=20, env=env
        )
        code: int | None = proc.returncode
        out, err = proc.stdout or "", proc.stderr or ""
    except OSError as exc:
        code = 126
        out, err = "", f"exec-failed: {type(exc).__name__}: {exc}"
    except subprocess.TimeoutExpired:
        code = 124
        out, err = "", "TIMEOUT"

    first = _first_error(out, err) or ("" if code == 0 else f"exit {code}")
    return {
        "script": path_name or rel,
        "interpreter": interp,
        "invocation": [str(c) for c in cmd],
        "exit_code": code,
        "first_error_line": first,
        "classification": classify(rel, interp, code, err + "\n" + out, explicit),
        "stdout": (out or "")[-800:],
        "stderr": (err or "")[-800:],
        "declared_interpreter": she,
        "explicit": explicit,
    }


def run_matrix(
    union: list[dict], interps: list[dict], fixtures: dict[str, Path]
) -> list[dict]:
    rows: list[dict] = []
    stubs: list[Path] = []
    try:
        for u in union:
            script = REPO / u["path"]
            if not script.is_file():
                continue
            # Only POSIX launchers can mutate this Linux host. .ps1/.cmd stay
            # original: pwsh is absent, and bash-on-PowerShell-source is a finding.
            use_stub = script.suffix.lower() in {".sh", ".bash"}
            target = shebang_stub(script) if use_stub else script
            if use_stub:
                stubs.append(target)
            for interp in INTERP_IDS:
                row = run_one(target, interp, interps, args=[POSIX_ARG])
                errblob = (row.get("stderr") or "") + "\n" + (row.get("stdout") or "")
                row["script"] = u["path"]
                row["declared_interpreter"] = u.get("declared_interpreter")
                row["explicit"] = bool(u.get("explicit"))
                row["classification"] = classify(
                    u["path"],
                    interp,
                    row["exit_code"],
                    errblob,
                    bool(u.get("explicit")),
                )
                row["sandboxed"] = bool(use_stub)
                rows.append(row)
        for script in (fixtures["ok_lf"], fixtures["ps1"], fixtures["implicit"]):
            if not script.is_file():
                continue
            for interp in INTERP_IDS:
                rows.append(run_one(script, interp, interps, args=[POSIX_ARG]))
    finally:
        for stub in stubs:
            try:
                stub.unlink(missing_ok=True)
            except OSError:
                pass
    return rows


def union_complete(union: list[dict], matrix: list[dict]) -> bool:
    by: dict[str, set[str]] = {}
    for row in matrix:
        by.setdefault(row["script"], set()).add(row["interpreter"])
    for u in union:
        if by.get(u["path"], set()) != set(INTERP_IDS):
            return False
    return True


def run_crlf_control(interps: list[dict], crlf: Path) -> dict:
    wsl = run_one(crlf, "wsl-bash", interps)
    git = run_one(crlf, "git-bash", interps)
    git_meta = next(i for i in interps if i["id"] == "git-bash")
    return {
        "wsl_bash_failed": wsl["exit_code"] not in (0,),
        "git_bash_standin_passed": git["exit_code"] == 0,
        "msys_git_bash_present": bool(git_meta.get("present")),
        "wsl_run": {
            k: wsl[k]
            for k in ("invocation", "exit_code", "first_error_line", "classification")
        },
        "git_bash_run": {
            k: git[k]
            for k in ("invocation", "exit_code", "first_error_line", "classification")
        },
        "note": (
            "CRLF fixture is exec'd via shebang under wsl-bash so the kernel sees "
            "'bash\\r'. Git Bash arm uses the igncr stand-in because MSYS is absent."
        ),
    }


def run_apostrophe_control(interps: list[dict], apos: Path) -> dict:
    bindir = FIX / "path-bin"
    bindir.mkdir(parents=True, exist_ok=True)
    dest = bindir / "cnf0105-apostrophe"
    dest.write_bytes(apos.read_bytes())
    _chmod_exec(dest)
    env = {"PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"}
    run = run_one(
        dest,
        "wsl-bash",
        interps,
        args=[POSIX_ARG],
        extra_env=env,
        path_name="cnf0105-apostrophe",
    )
    joined = " ".join(run["invocation"])
    inlined = any(tok in joined for tok in ("can't", "shouldn't", "it's-ok"))
    invoked = (
        bool(run["invocation"])
        and Path(run["invocation"][0]).name == "cnf0105-apostrophe"
    )
    body = apos.read_text(encoding="utf-8", errors="replace")
    return {
        "invoked_by_path": bool(invoked),
        "inlined_into_command_body": bool(inlined),
        "exit_code": int(run["exit_code"] if run["exit_code"] is not None else 1),
        "invocation": run["invocation"],
        "stdout": run["stdout"],
        "first_error_line": run["first_error_line"],
        "script_contains_apostrophe": "'" in body,
    }


def run_posix_path_control(interps: list[dict], ok_lf: Path) -> dict:
    run = run_one(ok_lf, "wsl-bash", interps, args=[POSIX_ARG])
    received = ""
    for line in (run["stdout"] or "").splitlines():
        if "argv=" in line:
            received = line.split("argv=", 1)[-1].strip()
            break
    return {
        "argument": POSIX_ARG,
        "received": received,
        "conversion_observed": bool(received) and received != POSIX_ARG,
        "exit_code": run["exit_code"],
        "invocation": run["invocation"],
        "note": (
            "MSYS Git Bash rewrites POSIX paths when calling Windows programs. "
            "On this Linux host the argument is received unchanged."
        ),
    }


def gitattributes_probe() -> dict:
    path = REPO / ".gitattributes"
    if not path.is_file():
        return {
            "path": ".gitattributes",
            "present": False,
            "eol_rules": [],
            "note": "No .gitattributes on this worktree.",
        }
    text = path.read_text(encoding="utf-8", errors="replace")
    eol = [
        ln.strip()
        for ln in text.splitlines()
        if "eol=" in ln or ln.strip().startswith("*")
    ]
    return {
        "path": ".gitattributes",
        "present": True,
        "eol_rules": eol[:40],
        "bytes": len(text.encode()),
    }


def windows_shell_sections() -> dict:
    canonical = REPO / "rules/common/windows-shell.md"
    fixture = (
        REPO
        / "command-center/p2-wave/probes/ARC-0005/fixtures/census/repo/rules/common/windows-shell.md"
    )
    found = canonical if canonical.is_file() else (fixture if fixture.is_file() else None)
    return {
        "canonical_path": "rules/common/windows-shell.md",
        "canonical_present": canonical.is_file(),
        "fixture_path": found.relative_to(REPO).as_posix() if found else None,
        "sections": {
            "1": "Declared interpreter must be explicit in the launcher; implicit is a defect.",
            "3": "Agent-written CRLF breaks real bash; Git Bash often tolerates the same bytes.",
            "8": "POSIX-looking absolute paths are the Git Bash path-conversion trigger.",
            "10": "Apostrophes break inlined command bodies; invoke the script by PATH.",
        },
        "note": (
            "Canonical rules/common/windows-shell.md is present; section glosses "
            "match CNF-0105 tests_required (explicit interpreter, CRLF, POSIX "
            "path conversion, apostrophe-by-PATH)."
            if canonical.is_file()
            else (
                "Canonical rules/common/windows-shell.md is absent; section "
                "glosses come from WORK-UNIT-CATALOG.json CNF-0105 tests_required."
            )
        ),
    }


def live_bundle() -> dict:
    interps = discover_interpreters()
    fixtures = write_fixtures()
    union = census_union()
    matrix = run_matrix(union, interps, fixtures)
    crlf = run_crlf_control(interps, fixtures["crlf"])
    apos = run_apostrophe_control(interps, fixtures["apostrophe"])
    posix = run_posix_path_control(interps, fixtures["ok_lf"])
    implicit_flagged = parse_shebang(fixtures["implicit"]) is None
    return {
        "interpreters": interps,
        "union": union,
        "matrix": matrix,
        "fixtures": {k: v.relative_to(REPO).as_posix() for k, v in fixtures.items()},
        "controls": {
            "crlf": crlf,
            "posix_path": posix,
            "apostrophe_by_path": apos,
            "explicit_interpreter": {
                "implicit_fixture_flagged": implicit_flagged,
                "fixture": fixtures["implicit"].relative_to(REPO).as_posix(),
                "shebang": parse_shebang(fixtures["implicit"]),
            },
        },
        "union_complete": union_complete(union, matrix),
        "gitattributes": gitattributes_probe(),
        "windows_shell_sections": windows_shell_sections(),
    }


def protocol_ok(b: dict) -> bool:
    c = b["controls"]
    return bool(
        b["union_complete"]
        and c["crlf"]["wsl_bash_failed"]
        and c["crlf"]["git_bash_standin_passed"]
        and c["apostrophe_by_path"]["invoked_by_path"]
        and not c["apostrophe_by_path"]["inlined_into_command_body"]
        and c["apostrophe_by_path"]["script_contains_apostrophe"]
        and c["explicit_interpreter"]["implicit_fixture_flagged"]
        and c["posix_path"]["argument"] == POSIX_ARG
        and c["posix_path"]["exit_code"] == 0
    )


def main() -> int:
    import json

    b = live_bundle()
    slim = {
        "union_n": len(b["union"]),
        "matrix_n": len(b["matrix"]),
        "union_complete": b["union_complete"],
        "protocol_ok": protocol_ok(b),
        "crlf": {
            k: b["controls"]["crlf"][k]
            for k in (
                "wsl_bash_failed",
                "git_bash_standin_passed",
                "msys_git_bash_present",
            )
        },
        "wsl_crlf_err": b["controls"]["crlf"]["wsl_run"]["first_error_line"],
        "apostrophe": {
            k: b["controls"]["apostrophe_by_path"][k]
            for k in ("invoked_by_path", "inlined_into_command_body", "exit_code")
        },
        "posix": b["controls"]["posix_path"],
        "interpreters": [
            {k: i[k] for k in ("id", "present", "kind", "version") if k in i}
            for i in b["interpreters"]
        ],
    }
    print(json.dumps(slim, indent=2, default=str))
    return 0 if protocol_ok(b) else 1


# Canonical names used by live_bundle / protocol_ok.
FIX = FIX
POSIX_ARG = POSIX_ARG
INTERP_IDS = INTERP_IDS
parse_shebang = parse_shebang
discover_interpreters = discover_interpreters
census_union = census_union
write_fixtures = write_fixtures
run_matrix = run_matrix
union_complete = union_complete
_chmod_exec = _chmod_exec
gitattributes_probe = gitattributes_probe
windows_shell_sections = windows_shell_sections


if __name__ == "__main__":
    raise SystemExit(main())
