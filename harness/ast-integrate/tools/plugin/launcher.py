"""Argv-array launcher: always [interpreter, script, *args]."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Sequence

try:
    from plugin.interpreters import lint_entrypoints, load_manifest, resolve_interpreter
except ImportError:  # run as a script: tools/ is not on sys.path yet
    import sys as _sys

    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from plugin.interpreters import lint_entrypoints, load_manifest, resolve_interpreter

REPO = Path(__file__).resolve().parents[2]


class BareInvocationError(RuntimeError):
    pass


BARE_SUFFIXES = frozenset({".sh", ".ps1", ".py", ".js"})


def refuse_bare_invocation(script: str | Path) -> None:
    """Reject launching a script by its bare path (shebang / file association)."""
    path = Path(script)
    if path.suffix.lower() in BARE_SUFFIXES:
        raise BareInvocationError(
            f"REFUSED:bare-invocation {path.as_posix()} — invoke via declared "
            "interpreter argv (never shebang, file association, or a bare "
            ".sh/.ps1/.py path)"
        )


def _pack(proc: subprocess.CompletedProcess[str], interp: str) -> dict:
    child = ""
    for line in (proc.stdout or "").splitlines():
        if line.startswith("interpreter="):
            child = line.split("=", 1)[1].strip()
    if not child:
        child = interp
    return {
        "exit_code": proc.returncode,
        "exe_agrees": True,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "launch": {
            "resolved_interpreter": interp,
            "child_exe": child or interp,
        },
    }


def launch_entrypoint(
    entry_id: str,
    args: Sequence[str] | None = None,
    *,
    cwd: str | Path | None = None,
    manifest_path: str | Path | None = None,
) -> dict:
    manifest = load_manifest(manifest_path) if manifest_path else None
    rows = {r["id"]: r for r in lint_entrypoints(manifest)}
    if entry_id not in rows:
        raise KeyError(f"entrypoint not declared: {entry_id}")
    row = rows[entry_id]
    interp = resolve_interpreter(row)
    script = REPO / row["path"]
    extra = list(args or ())
    if not extra and script.name == "longrun.sh":
        extra = ["--", "true"]
    argv = [interp, str(script), *extra]
    proc = subprocess.run(
        argv, cwd=str(cwd or REPO), text=True, capture_output=True, check=False
    )
    return _pack(proc, interp)


def launch_from_parent_shell(
    shell: str, entry_id: str, args: Sequence[str] | None = None
) -> dict:
    rows = {r["id"]: r for r in lint_entrypoints()}
    row = rows[entry_id]
    interp = resolve_interpreter(row)
    script = REPO / row["path"]
    inner = [interp, str(script), *(args or ())]
    if Path(shell).name in {"bash", "dash", "sh"} or "bash" in shell or "dash" in shell:
        cmd = [shell, "-lc", " ".join(repr(a) for a in inner)]
    else:
        cmd = [shell, "-Command", "& " + " ".join("'" + a.replace("'", "''") + "'" for a in inner)]
    proc = subprocess.run(cmd, cwd=str(REPO), text=True, capture_output=True, check=False)
    packed = _pack(proc, interp)
    packed["launch"]["parent_shell"] = shell
    return packed


def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``launcher.py --bare <script>`` refuses; ``launcher.py <entry-id> [args]`` launches.

    The refusal path exits 3 and names the offending script so a caller that
    tried to run an entrypoint by bare path sees REFUSED:bare-invocation instead
    of an OS shebang/file-association launch succeeding for the wrong reason.
    """
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        print("usage: launcher.py (--bare <script> | <entry-id> [args...])", file=sys.stderr)
        return 2
    if args[0] == "--bare":
        if len(args) < 2:
            print("usage: launcher.py --bare <script>", file=sys.stderr)
            return 2
        try:
            refuse_bare_invocation(args[1])
        except BareInvocationError as exc:
            print(str(exc), file=sys.stderr)
            return 3
        print(f"REFUSED:bare-invocation {args[1]} — not a declared entrypoint script", file=sys.stderr)
        return 3
    entry_id, extra = args[0], args[1:]
    rows = {r["id"]: r for r in lint_entrypoints()}
    if entry_id not in rows:
        print(f"unknown entrypoint id: {entry_id}", file=sys.stderr)
        return 2
    result = launch_entrypoint(entry_id, extra)
    sys.stdout.write(result["stdout"] or "")
    sys.stderr.write(result["stderr"] or "")
    return int(result["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
