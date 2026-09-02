#!/usr/bin/env python3
"""ADV-0118 live dual-shell quoting corpus against the program's own constructions.

In-tree git/gh helpers pass argv arrays (safe). There is no shlex.quote in the
tree; shell-string interpolation therefore uses naive single quotes. This engine
executes both styles in GNU bash and live PowerShell 7, then reads the far-end
value (git %B, fake-gh JSON, launcher file, rev-parse SHA).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0118"
WIN_CMDLINE_CAP = 32767
LONG_N = 40000


def catalog_unit() -> dict:
    data = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT:
            return u
    raise RuntimeError("ADV-0118 missing from WORK-UNIT-CATALOG.json")


def long_payload() -> str:
    token = "ADV0118P06"
    mid = LONG_N - 2 * len(token) - 1
    text = token + ("A" * mid) + "Z" + token
    if len(text) != LONG_N:
        raise RuntimeError(f"long payload len={len(text)}")
    return text


def payload_list() -> list[dict[str, str]]:
    return [
        {
            "id": "P01-ASCII-CONTROL",
            "kind": "control-ascii",
            "text": "plain ASCII payload ADV0118",
        },
        {
            "id": "P02-APOSTROPHE-PROSE",
            "kind": "apostrophe",
            "text": "Owner's notes: don't ship until it's done.",
        },
        {
            "id": "P03-HERESTRING-TERM",
            "kind": "herestring-terminator",
            "text": "keep-me\n'@\ntrailer-must-survive",
        },
        {
            "id": "P04-HEAD-CARET-REF",
            "kind": "caret-ref",
            "text": "HEAD^{commit}",
        },
        {
            "id": "P05-SDCARD-PATH",
            "kind": "posix-path",
            "text": "/sdcard/Android/data/com.example/files/notes.txt",
        },
        {
            "id": "P06-LONG-40000",
            "kind": "windows-cmdline-cap",
            "text": long_payload(),
        },
    ]


def payload_meta(text: str) -> dict[str, Any]:
    raw = text.encode("utf-8")
    return {
        "chars": len(text),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "head": text[:24].replace("\n", "\\n"),
        "tail": text[-24:].replace("\n", "\\n"),
    }


def naive_single_quote(text: str) -> str:
    return "'" + text + "'"


def find_pwsh() -> Path | None:
    env = os.environ.get("ADV0118_PWSH")
    cands: list[Path] = []
    if env:
        cands.append(Path(env))
    cands.append(HERE / "_tooling" / "pwsh" / "pwsh")
    cands.append(Path("/tmp/adv0118-pwsh/pwsh"))
    which = shutil.which("pwsh")
    if which:
        cands.append(Path(which))
    for p in cands:
        try:
            if p.is_file() and os.access(p, os.X_OK):
                return p.resolve()
        except OSError:
            continue
    return None


def ensure_pwsh() -> Path:
    found = find_pwsh()
    if found is not None:
        return found
    tgz = Path("/tmp/powershell-7.4.6-linux-x64.tar.gz")
    dest = Path("/tmp/adv0118-pwsh")
    if tgz.is_file():
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xzf", str(tgz), "-C", str(dest)], check=True)
        pwsh = dest / "pwsh"
        pwsh.chmod(pwsh.stat().st_mode | stat.S_IXUSR)
        if os.access(pwsh, os.X_OK):
            return pwsh.resolve()
    raise RuntimeError("pwsh 7 not found; set ADV0118_PWSH")


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "ADV-0118",
            "GIT_AUTHOR_EMAIL": "adv-0118@invalid.local",
            "GIT_COMMITTER_NAME": "ADV-0118",
            "GIT_COMMITTER_EMAIL": "adv-0118@invalid.local",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env


def _decode(raw: bytes | None) -> str:
    return (raw or b"").decode("utf-8", "replace")


def run_git(repo: Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess:
    env = git_env()
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        env=env,
        check=check,
    )


_TEMPLATE_REPO: Path | None = None


def init_repo(repo: Path, *, work: Path | None = None) -> None:
    global _TEMPLATE_REPO
    if work is not None:
        tmpl = work / "_template-repo"
        if _TEMPLATE_REPO is None or not (tmpl / ".git").exists():
            _TEMPLATE_REPO = tmpl
            if not (tmpl / ".git").exists():
                init_repo(tmpl, work=None)
        if repo.resolve() != tmpl.resolve():
            if repo.exists():
                shutil.rmtree(repo)
            shutil.copytree(tmpl, repo)
            return
    repo.mkdir(parents=True, exist_ok=True)
    env = git_env()
    subprocess.run(
        ["git", "init", "-q", str(repo)],
        check=True,
        capture_output=True,
        env=env,
    )
    run_git(repo, ["config", "user.name", "ADV-0118"])
    run_git(repo, ["config", "user.email", "adv-0118@invalid.local"])
    run_git(repo, ["config", "commit.gpgsign", "false"])
    run_git(repo, ["commit", "--allow-empty", "-qm", "init"], check=True)
    run_git(repo, ["commit", "--allow-empty", "-qm", "second"], check=True)
    run_git(repo, ["tag", "t1"], check=True)


def normalize_msg(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def classify(intended: str, delivered: str | None, rc: int, stderr: str) -> str:
    err = (stderr or "").lower()
    parse = any(
        s in err
        for s in (
            "unexpected eof",
            "missing the terminator",
            "parsererror",
            "syntax error",
            "the string is missing the terminator",
            "unmatched",
        )
    )
    if parse:
        return "parse_error"
    if delivered is None:
        return "refused" if rc != 0 else "refused"
    got = normalize_msg(delivered)
    want = normalize_msg(intended)
    if got == want:
        return "roundtrip"
    if want.startswith(got) and 0 < len(got) < len(want):
        return "truncated"
    if rc != 0:
        return "refused"
    return "mangled"


def classify_ref(oracle: str | None, delivered: str | None, rc: int, stderr: str) -> str:
    err = (stderr or "").lower()
    parse = any(
        s in err
        for s in (
            "missing the terminator",
            "parsererror",
            "syntax error",
            "unexpected eof",
        )
    )
    if parse:
        return "parse_error"
    if oracle is None:
        return "refused" if rc != 0 else "mangled"
    if delivered and delivered == oracle:
        return "roundtrip"
    if rc != 0 or not delivered:
        return "refused"
    return "mangled"


def constructions() -> list[dict[str, str]]:
    launcher = str(HERE / "owned_launcher.py")
    return [
        {
            "id": "C01-GIT-COMMIT-MESSAGE",
            "kind": "git-commit-message",
            "quoting": "naive-single-quote-shell-string",
        },
        {
            "id": "C02-GH-PR-BODY",
            "kind": "gh-pr-body",
            "quoting": "naive-single-quote-shell-string",
        },
        {
            "id": "C03-GIT-CARET-REF",
            "kind": "git-caret-ref",
            "quoting": "unquoted-interpolation",
        },
        {
            "id": "C04-POSIX-SDCARD-PATH",
            "kind": "posix-path",
            "quoting": "naive-single-quote-shell-string",
            "launcher": launcher,
        },
        {
            "id": "C05-HERESTRING-PAYLOAD",
            "kind": "herestring",
            "quoting": "shell-here-document",
            "launcher": launcher,
        },
        {
            "id": "C06-OWNED-LONGRUN-LAUNCHER",
            "kind": "owned-launcher",
            "quoting": "naive-single-quote-shell-string",
            "launcher": launcher,
        },
        {
            "id": "C07-NATIVE-ARGV-BOUNDARY",
            "kind": "native-argv",
            "quoting": "argv-array-no-shell",
        },
    ]


def oracle_rev_parse(repo: Path, spec: str) -> str | None:
    p = run_git(repo, ["rev-parse", "--verify", spec])
    if p.returncode != 0:
        return None
    return _decode(p.stdout).strip() or None


def read_commit_body(repo: Path) -> str | None:
    p = run_git(repo, ["log", "-1", "--format=%B"])
    if p.returncode != 0:
        return None
    return _decode(p.stdout)


def _run(cmd: list[str], env: dict[str, str], cwd: Path, timeout: int = 45) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, timeout=timeout)


def _write_exec(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _exec_script(
    cell_dir: Path, shell_id: str, shell_bin: str, script: str, env: dict[str, str]
) -> tuple[int, str, str, bool]:
    try:
        if shell_id.startswith("pwsh"):
            ps1 = cell_dir / "run.ps1"
            ps1.write_text(script, encoding="utf-8")
            proc = _run(
                [shell_bin, "-NoProfile", "-NonInteractive", "-File", str(ps1)],
                env,
                cell_dir,
            )
        else:
            sh = cell_dir / "run.sh"
            sh.write_text("#!/usr/bin/env bash\nset +H\n" + script, encoding="utf-8")
            proc = _run([shell_bin, "--noprofile", "--norc", str(sh)], env, cell_dir)
        return proc.returncode, _decode(proc.stdout), _decode(proc.stderr), False
    except subprocess.TimeoutExpired:
        return 124, "", "TIMEOUT", True


def _finish(
    cell_id: str,
    shell_id: str,
    construction: dict[str, str],
    payload: dict[str, str],
    script: str,
    argv: list[str] | None,
    rc: int,
    stdout: str,
    stderr: str,
    timed_out: bool,
    cmdline_chars: int,
    delivered: str | None,
    outcome: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = payload["text"]
    meta = payload_meta(text)
    deliv_meta = payload_meta(delivered) if isinstance(delivered, str) else None
    row: dict[str, Any] = {
        "id": cell_id,
        "shell": shell_id,
        "construction_id": construction["id"],
        "construction_kind": construction["kind"],
        "quoting": construction["quoting"],
        "payload_id": payload["id"],
        "payload_kind": payload["kind"],
        "payload": meta,
        "intended_sha256": meta["sha256"],
        "intended_chars": meta["chars"],
        "delivered": deliv_meta,
        "delivered_equals_intended": bool(
            isinstance(delivered, str) and normalize_msg(delivered) == normalize_msg(text)
        ),
        "exit_code": rc,
        "timed_out": timed_out,
        "stderr_tail": (stderr or "")[-400:],
        "stdout_tail": (stdout or "")[-200:],
        "constructed_command_chars": cmdline_chars,
        "windows_cmdline_cap": WIN_CMDLINE_CAP,
        "exceeds_windows_createprocess_cap": cmdline_chars > WIN_CMDLINE_CAP,
        "native_argv": argv is not None,
        "outcome": outcome,
    }
    if extra:
        row.update(extra)
        if extra.get("oracle_sha") is not None:
            row["delivered_equals_intended"] = delivered == extra.get("oracle_sha")
    return row


def run_cell(
    *,
    work: Path,
    shell_id: str,
    shell_bin: str,
    payload: dict[str, str],
    construction: dict[str, str],
) -> dict[str, Any]:
    cid = construction["id"]
    pid = payload["id"]
    text = payload["text"]
    work = work.resolve()
    cell_id = f"{shell_id}__{cid}__{pid}"
    cell_dir = work / cell_id
    cell_dir.mkdir(parents=True, exist_ok=True)
    env = git_env()
    delivered: str | None = None
    script = ""
    argv: list[str] | None = None
    rc = -1
    stdout = ""
    stderr = ""
    timed_out = False
    cmdline_chars = 0
    extra: dict[str, Any] = {}

    try:
        kind = construction["kind"]
        if kind == "native-argv":
            repo = cell_dir / "repo"
            init_repo(repo, work=work)
            argv = [
                "git",
                "-C",
                str(repo),
                "commit",
                "--allow-empty",
                "-qm",
                text,
            ]
            cmdline_chars = sum(len(a) + 1 for a in argv)
            proc = _run(argv, env, cell_dir)
            rc, stdout, stderr = proc.returncode, _decode(proc.stdout), _decode(proc.stderr)
            delivered = read_commit_body(repo)
            outcome = classify(text, delivered, rc, stderr)

        elif kind == "git-commit-message":
            repo = cell_dir / "repo"
            init_repo(repo, work=work)
            q = naive_single_quote(text)
            script = f"git -C {naive_single_quote(str(repo))} commit --allow-empty -m {q}\n"
            cmdline_chars = len(script)
            rc, stdout, stderr, timed_out = _exec_script(
                cell_dir, shell_id, shell_bin, script, env
            )
            delivered = read_commit_body(repo)
            outcome = classify(text, delivered, rc, stderr)

        elif kind == "gh-pr-body":
            cap = cell_dir / "gh-capture.json"
            env = {**env, "ADV0118_CAPTURE": str(cap)}
            gh_bin = cell_dir / "bin"
            gh_bin.mkdir(exist_ok=True)
            wrapper = gh_bin / "gh"
            cap_py = (HERE / "capture_argv.py").as_posix()
            _write_exec(
                wrapper,
                "#!/usr/bin/env python3\n"
                "import runpy\n"
                f"runpy.run_path({cap_py!r}, run_name='__main__')\n",
            )
            env["PATH"] = str(gh_bin) + os.pathsep + env.get("PATH", "")
            q = naive_single_quote(text)
            script = f"gh pr create --title t --body {q}\n"
            cmdline_chars = len(script)
            rc, stdout, stderr, timed_out = _exec_script(
                cell_dir, shell_id, shell_bin, script, env
            )
            if cap.is_file():
                try:
                    doc = json.loads(cap.read_text(encoding="utf-8"))
                    delivered = doc.get("body")
                except json.JSONDecodeError:
                    delivered = None
            outcome = classify(text, delivered, rc, stderr)

        elif kind == "git-caret-ref":
            repo = cell_dir / "repo"
            init_repo(repo, work=work)
            script = (
                f"git -C {naive_single_quote(str(repo))} rev-parse --verify {text}\n"
            )
            cmdline_chars = len(script)
            rc, stdout, stderr, timed_out = _exec_script(
                cell_dir, shell_id, shell_bin, script, env
            )
            lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
            delivered = lines[-1] if lines else None
            oracle = oracle_rev_parse(repo, text)
            extra = {"oracle_sha": oracle, "intended_spec": text}
            outcome = classify_ref(oracle, delivered, rc, stderr)

        elif kind in ("posix-path", "owned-launcher"):
            dest = cell_dir / "delivered.bin"
            env = {**env, "ADV0118_DELIVERED": str(dest)}
            flag = "--path" if kind == "posix-path" else "--payload"
            q = naive_single_quote(text)
            script = f"{sys.executable} {construction['launcher']} {flag} {q}\n"
            cmdline_chars = len(script)
            rc, stdout, stderr, timed_out = _exec_script(
                cell_dir, shell_id, shell_bin, script, env
            )
            if dest.is_file():
                delivered = dest.read_bytes().decode("utf-8", "replace")
            outcome = classify(text, delivered, rc, stderr)

        elif kind == "herestring":
            dest = cell_dir / "delivered.bin"
            env = {**env, "ADV0118_DELIVERED": str(dest)}
            launch = f"{sys.executable} {construction['launcher']} --payload"
            if shell_id.startswith("pwsh"):
                script = f"{launch} @'\n{text}\n'@\n"
            else:
                script = (
                    f"{launch} \"$(cat <<'ADV0118_HS'\n{text}\nADV0118_HS\n)\"\n"
                )
            cmdline_chars = len(script)
            rc, stdout, stderr, timed_out = _exec_script(
                cell_dir, shell_id, shell_bin, script, env
            )
            if dest.is_file():
                delivered = dest.read_bytes().decode("utf-8", "replace")
            outcome = classify(text, delivered, rc, stderr)
        else:
            raise RuntimeError(f"unknown construction {cid}")
    except subprocess.TimeoutExpired:
        timed_out = True
        rc = 124
        stderr = "TIMEOUT"
        outcome = "refused"
    except Exception as exc:
        rc = 99
        stderr = f"{type(exc).__name__}: {exc}"
        outcome = "refused"

    return _finish(
        cell_id,
        shell_id,
        construction,
        payload,
        script,
        argv,
        rc,
        stdout,
        stderr,
        timed_out,
        cmdline_chars,
        delivered,
        outcome,
        extra=extra,
    )


def extra_trailing_caret(work: Path, shells: list[dict[str, str]]) -> list[dict[str, Any]]:
    payload = {
        "id": "P04B-HEAD-CARET-TRAILING",
        "kind": "caret-ref-trailing",
        "text": "HEAD^",
    }
    construction = {
        "id": "C03-GIT-CARET-REF-TRAILING",
        "kind": "git-caret-ref",
        "quoting": "unquoted-interpolation",
    }
    return [
        run_cell(
            work=work,
            shell_id=sh["id"],
            shell_bin=sh["binary"],
            payload=payload,
            construction=construction,
        )
        for sh in shells
    ]


def windows_clip_negative_control(work: Path, bash: str) -> dict[str, Any]:
    text = long_payload()
    cell_dir = work / "NC-WINDOWS-CLIP"
    cell_dir.mkdir(parents=True, exist_ok=True)
    dest = cell_dir / "delivered.bin"
    env = git_env()
    env["ADV0118_DELIVERED"] = str(dest)
    launch = f"{sys.executable} {(HERE / 'owned_launcher.py').as_posix()} --payload"
    full = f"{launch} {naive_single_quote(text)}\n"
    clipped = full[:WIN_CMDLINE_CAP]
    sh = cell_dir / "run.sh"
    sh.write_text("#!/usr/bin/env bash\nset +H\n" + clipped, encoding="utf-8")
    proc = _run([bash, "--noprofile", "--norc", str(sh)], env, cell_dir)
    delivered = dest.read_bytes().decode("utf-8", "replace") if dest.is_file() else None
    outcome = classify(text, delivered, proc.returncode, _decode(proc.stderr))
    return {
        "id": "NC-WINDOWS-CLIP-32767",
        "full_chars": len(full),
        "clipped_chars": len(clipped),
        "exit_code": proc.returncode,
        "outcome": outcome,
        "delivered_chars": None if delivered is None else len(delivered),
        "roundtrip": outcome == "roundtrip",
        "fired_on_bad_state": outcome != "roundtrip",
        "stderr_tail": _decode(proc.stderr)[-300:],
        "note": "Mutant clips the constructed command to the Windows CreateProcess cap.",
    }


def run_matrix(work: Path) -> dict[str, Any]:
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    bash = shutil.which("bash") or "/usr/bin/bash"
    pwsh = ensure_pwsh()
    ver = subprocess.run(
        [
            str(pwsh),
            "-NoProfile",
            "-Command",
            "Write-Output $PSVersionTable.PSVersion.ToString()",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    shells = [
        {
            "id": "gnu-bash",
            "binary": bash,
            "family": "git-bash-posix",
            "note": (
                "Git Bash is MSYS bash. Apostrophe/heredoc quoting matches GNU bash. "
                "MSYS /drive conversion is absent on this Linux host."
            ),
        },
        {
            "id": "pwsh7",
            "binary": str(pwsh),
            "family": "powershell-7",
            "version": (ver.stdout or "").strip(),
            "note": "Live portable PowerShell 7.",
        },
    ]
    cells: list[dict[str, Any]] = []
    for sh in shells:
        for c in constructions():
            for p in payload_list():
                cells.append(
                    run_cell(
                        work=work,
                        shell_id=sh["id"],
                        shell_bin=sh["binary"],
                        payload=p,
                        construction=c,
                    )
                )
    cells.extend(extra_trailing_caret(work, shells))
    clip = windows_clip_negative_control(work, bash)
    return {
        "unit_id": UNIT,
        "shells": shells,
        "n_cells": len(cells),
        "cells": cells,
        "windows_clip_control": clip,
        "win_cmdline_cap": WIN_CMDLINE_CAP,
        "in_tree_shlex_quote_uses": 0,
        "program_native_argv_example": "tools/command-center/git_blob.py:_run_git list-form",
        "program_shell_string_style": "naive-single-quote (no shlex.quote anywhere in-tree)",
    }


def summarize(matrix: dict[str, Any]) -> dict[str, Any]:
    cells: list[dict[str, Any]] = matrix["cells"]

    def pick(pred) -> list[dict[str, Any]]:
        return [c for c in cells if pred(c)]

    ctrl = pick(
        lambda c: c["payload_id"] == "P01-ASCII-CONTROL"
        and c["construction_id"]
        in ("C01-GIT-COMMIT-MESSAGE", "C07-NATIVE-ARGV-BOUNDARY")
    )
    ctrl_ok = bool(ctrl) and all(c["outcome"] == "roundtrip" for c in ctrl)

    apos_shell = pick(
        lambda c: c["payload_id"] == "P02-APOSTROPHE-PROSE"
        and c["construction_id"]
        in (
            "C01-GIT-COMMIT-MESSAGE",
            "C02-GH-PR-BODY",
            "C06-OWNED-LONGRUN-LAUNCHER",
        )
        and not c.get("native_argv")
    )
    apos_native = pick(
        lambda c: c["payload_id"] == "P02-APOSTROPHE-PROSE"
        and c["construction_id"] == "C07-NATIVE-ARGV-BOUNDARY"
    )
    hs_ps = pick(
        lambda c: c["payload_id"] == "P03-HERESTRING-TERM"
        and c["construction_id"] == "C05-HERESTRING-PAYLOAD"
        and c["shell"] == "pwsh7"
    )
    hs_bash = pick(
        lambda c: c["payload_id"] == "P03-HERESTRING-TERM"
        and c["construction_id"] == "C05-HERESTRING-PAYLOAD"
        and c["shell"] == "gnu-bash"
    )
    peel_ps = pick(
        lambda c: c["payload_id"] == "P04-HEAD-CARET-REF"
        and c["construction_id"] == "C03-GIT-CARET-REF"
        and c["shell"] == "pwsh7"
    )
    peel_bash = pick(
        lambda c: c["payload_id"] == "P04-HEAD-CARET-REF"
        and c["construction_id"] == "C03-GIT-CARET-REF"
        and c["shell"] == "gnu-bash"
    )
    trail_ps = pick(
        lambda c: c["payload_id"] == "P04B-HEAD-CARET-TRAILING" and c["shell"] == "pwsh7"
    )
    path_bash = pick(
        lambda c: c["payload_id"] == "P05-SDCARD-PATH"
        and c["construction_id"] == "C04-POSIX-SDCARD-PATH"
        and c["shell"] == "gnu-bash"
    )
    long_native = pick(
        lambda c: c["payload_id"] == "P06-LONG-40000"
        and c["construction_id"] == "C07-NATIVE-ARGV-BOUNDARY"
    )
    long_shell = pick(
        lambda c: c["payload_id"] == "P06-LONG-40000"
        and c["construction_id"] == "C01-GIT-COMMIT-MESSAGE"
    )
    clip = matrix["windows_clip_control"]

    def v_break(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "NOT-CHECKED"
        if any(r["outcome"] != "roundtrip" for r in rows):
            return "CONFIRMED"
        return "REFUTED"

    def v_safe(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "NOT-CHECKED"
        if all(r["outcome"] == "roundtrip" for r in rows):
            return "REFUTED"
        return "CONFIRMED"

    targets = [
        {
            "id": "naive-shell-apostrophe-own-scripts",
            "verdict": v_break(apos_shell),
            "note": "Naive '...' wrap (no shlex.quote in tree) around Owner's/don't prose.",
            "n": len(apos_shell),
            "n_break": sum(1 for c in apos_shell if c["outcome"] != "roundtrip"),
        },
        {
            "id": "native-argv-apostrophe",
            "verdict": v_safe(apos_native),
            "note": "List-form git commit -m. REFUTED means the construction did not break.",
            "n": len(apos_native),
        },
        {
            "id": "pwsh-herestring-self-terminator",
            "verdict": v_break(hs_ps),
            "note": "PowerShell @' '@ here-string whose payload contains a line '@.",
            "n": len(hs_ps),
        },
        {
            "id": "bash-heredoc-self-terminator-payload",
            "verdict": v_safe(hs_bash),
            "note": "POSIX <<'ADV0118_HS' with a payload that is a PS terminator, not the bash delimiter.",
            "n": len(hs_bash),
        },
        {
            "id": "unquoted-HEAD-peel-under-pwsh7",
            "verdict": v_break(peel_ps),
            "note": "Unquoted HEAD^{commit} under live pwsh 7: ^ is XOR / {commit} is a script block.",
            "n": len(peel_ps),
            "outcomes": [c["outcome"] for c in peel_ps],
        },
        {
            "id": "unquoted-HEAD-peel-under-bash",
            "verdict": v_safe(peel_bash),
            "note": "Same unquoted HEAD^{commit} under GNU bash.",
            "n": len(peel_bash),
        },
        {
            "id": "unquoted-trailing-HEAD-caret-under-pwsh7",
            "verdict": v_safe(trail_ps),
            "note": "Live pwsh 7.4.6 passes trailing HEAD^ through to git.",
            "n": len(trail_ps),
            "outcomes": [c["outcome"] for c in trail_ps],
        },
        {
            "id": "posix-sdcard-path-gnu-bash",
            "verdict": v_safe(path_bash),
            "note": "Live GNU bash does not MSYS-convert /sdcard/... paths.",
            "n": len(path_bash),
        },
        {
            "id": "posix-sdcard-path-msys-git-bash",
            "verdict": "NOT-CHECKED",
            "note": "MSYS Git Bash is not on this Linux worktree.",
        },
        {
            "id": "long-payload-linux-live-truncation",
            "verdict": (
                "CONFIRMED"
                if any(c["outcome"] == "truncated" for c in long_native + long_shell)
                else "REFUTED"
            ),
            "note": "Silent truncation of a 40000-char payload on this Linux host.",
            "native_outcomes": [c["outcome"] for c in long_native],
            "shell_outcomes": [c["outcome"] for c in long_shell],
        },
        {
            "id": "long-payload-windows-32767-no-preflight",
            "verdict": (
                "CONFIRMED"
                if any(c.get("exceeds_windows_createprocess_cap") for c in long_shell)
                else "REFUTED"
            ),
            "note": "Naive shell-string constructors emit a command longer than 32767 with no refusal preflight.",
        },
    ]

    tests = [
        {
            "id": "control-plain-ascii-roundtrip-both-shells",
            "result": "PASS" if ctrl_ok else "FAIL",
            "detail": "P01 through C01 naive quotes and C07 native argv in gnu-bash and pwsh7.",
            "n": len(ctrl),
        },
        {
            "id": "long-payload-refuse-vs-silent-truncation",
            "result": "PASS" if clip.get("fired_on_bad_state") else "FAIL",
            "detail": "Negative control clips the constructed command to 32767 and must not round-trip.",
            "clip_outcome": clip.get("outcome"),
        },
    ]
    missing = any(t["result"] != "PASS" for t in tests)
    if missing:
        for t in targets:
            t["verdict"] = "NOT-CHECKED"
            t["downgraded"] = "missing-control"

    confirmed = [t for t in targets if t["verdict"] == "CONFIRMED"]
    refuted = [t for t in targets if t["verdict"] == "REFUTED"]
    unchecked = [t for t in targets if t["verdict"] == "NOT-CHECKED"]
    if missing:
        overall = "NOT-CHECKED"
    elif confirmed and refuted:
        overall = "PARTIAL"
    elif confirmed:
        overall = "CONFIRMED"
    elif refuted and not unchecked:
        overall = "REFUTED"
    else:
        overall = "PARTIAL"
    return {
        "targets": targets,
        "tests": tests,
        "control_ascii_ok": ctrl_ok,
        "overall_verdict": overall,
        "counts": {
            "confirmed": len(confirmed),
            "refuted": len(refuted),
            "not_checked": len(unchecked),
            "cells": len(cells),
        },
    }


def compact_cells(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for c in cells:
        delivered = c.get("delivered") if isinstance(c.get("delivered"), dict) else {}
        out.append(
            {
                "id": c["id"],
                "shell": c["shell"],
                "construction_id": c["construction_id"],
                "payload_id": c["payload_id"],
                "outcome": c["outcome"],
                "exit_code": c["exit_code"],
                "delivered_equals_intended": c.get("delivered_equals_intended"),
                "constructed_command_chars": c["constructed_command_chars"],
                "exceeds_windows_createprocess_cap": c["exceeds_windows_createprocess_cap"],
                "intended_chars": c["intended_chars"],
                "intended_sha256": c["intended_sha256"],
                "delivered_sha256": delivered.get("sha256") if delivered else None,
                "delivered_chars": delivered.get("chars") if delivered else None,
                "stderr_tail": (c.get("stderr_tail") or "")[:240],
            }
        )
    return out
