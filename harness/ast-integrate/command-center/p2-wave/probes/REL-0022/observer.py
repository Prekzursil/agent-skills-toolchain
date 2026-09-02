"""System-level observer: canary filesystem census plus optional strace -f."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

CAN_PERCEIVE = [
    "create/modify/delete of files under the canary HOME (sha256 census)",
    "file-related syscalls of the installer and descendants whose path lies under the canary HOME (strace -f), when ptrace is available",
    "child-process file writes that persist inside the canary HOME (census; strace attributes the pid when available)",
]

CANNOT_PERCEIVE = [
    "network sockets, DNS, and outbound HTTP",
    "host systemd/cron units (the installer writes a file-backed timer only)",
    "Windows registry and scheduled-task store",
    "in-memory-only mutations that never hit disk",
    "kernel modules and mounts outside the canary tree",
    "file ops by processes not in the observed tree and not leaving bytes under the canary HOME",
]

STRACE_BLIND = (
    "syscall-level child attribution is NOT-CHECKED because strace/ptrace "
    "was unavailable; filesystem census of the canary HOME still applies"
)

PATH_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
CHILD_REL = ".ast-plugin/cache/child-beacon.txt"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def census(root: Path) -> dict[str, dict]:
    root = Path(root).resolve()
    out: dict[str, dict] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        st = path.stat()
        out[rel] = {
            "sha256": sha256_file(path),
            "bytes": st.st_size,
            "mtime_ns": st.st_mtime_ns,
        }
    return out


def diff_census(before: dict, after: dict) -> dict[str, set[str]]:
    created = set(after) - set(before)
    deleted = set(before) - set(after)
    modified = {
        rel
        for rel in (set(before) & set(after))
        if before[rel]["sha256"] != after[rel]["sha256"]
    }
    return {"created": created, "deleted": deleted, "modified": modified}


def effect_keys(diff: dict[str, set[str]]) -> set[str]:
    keys: set[str] = set()
    for rel in diff["created"]:
        keys.add(f"fs:create:{rel}")
    for rel in diff["modified"]:
        keys.add(f"fs:modify:{rel}")
    for rel in diff["deleted"]:
        keys.add(f"fs:delete:{rel}")
    return keys


def _parse_strace(text: str, canary: Path) -> dict:
    canary_s = str(canary.resolve())
    pids: set[int] = set()
    under: list[dict] = []
    outside: list[str] = []
    for line in text.splitlines():
        mpid = re.match(r"^\s*(\d+)\s+", line)
        if not mpid:
            continue
        pid = int(mpid.group(1))
        pids.add(pid)
        for raw in PATH_RE.findall(line):
            try:
                path = raw.encode("utf-8").decode("unicode_escape")
            except Exception:
                path = raw
            if not path.startswith("/"):
                continue
            if path == canary_s or path.startswith(canary_s + "/"):
                under.append({"pid": pid, "path": path, "line": line[:240]})
            elif any(
                tok in line
                for tok in ("O_CREAT", "O_TRUNC", "unlink", "rename", "mkdir")
            ):
                if "/usr/" in path or "/lib/" in path or path.startswith("/proc"):
                    continue
                if path.startswith("/tmp/rel0022-") or path.startswith("/tmp/strace"):
                    continue
                outside.append(path)
    return {
        "pids": sorted(pids),
        "under_canary": under,
        "outside_mutating": sorted(set(outside))[:32],
    }


def observe_command(home: Path, argv: list[str], env: dict[str, str]) -> dict:
    """Run argv with HOME=canary. Census is authoritative. strace -f is extra."""
    home = Path(home).resolve()
    before = census(home)
    fd, log_name = tempfile.mkstemp(prefix="rel0022-strace-", suffix=".log")
    os.close(fd)
    strace_log = Path(log_name)
    strace_bin = shutil.which("strace")
    strace_ok = False
    strace_text = ""
    if strace_bin:
        cmd = [
            strace_bin,
            "-f",
            "-qq",
            "-s",
            "256",
            "-e",
            "trace=file",
            "-o",
            str(strace_log),
            "--",
            *argv,
        ]
    else:
        cmd = argv
    proc = subprocess.run(
        cmd,
        cwd=str(HERE),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if strace_bin and strace_log.is_file():
        strace_text = strace_log.read_text(encoding="utf-8", errors="replace")
        strace_ok = bool(strace_text.strip())
        if "Operation not permitted" in (proc.stderr or "") and not strace_text.strip():
            strace_ok = False
            proc = subprocess.run(
                argv,
                cwd=str(HERE),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
    try:
        strace_log.unlink(missing_ok=True)
    except OSError:
        pass
    after = census(home)
    diff = diff_census(before, after)
    parsed = (
        _parse_strace(strace_text, home)
        if strace_ok
        else {"pids": [], "under_canary": [], "outside_mutating": []}
    )
    child_in_census = CHILD_REL in diff["created"] or CHILD_REL in after
    child_pids: set[int] = set()
    if parsed["under_canary"]:
        beacon_abs = str((home / CHILD_REL).resolve())
        installer_guess = parsed["pids"][0] if parsed["pids"] else None
        for rec in parsed["under_canary"]:
            if rec["path"] == beacon_abs and rec["pid"] != installer_guess:
                child_pids.add(rec["pid"])
    return {
        "returncode": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
        "argv": argv,
        "diff": {k: sorted(v) for k, v in diff.items()},
        "effect_keys": sorted(effect_keys(diff)),
        "strace_available": bool(strace_bin),
        "strace_ok": strace_ok,
        "strace_pids": parsed["pids"],
        "strace_child_pids_for_beacon": sorted(child_pids),
        "strace_outside_mutating": parsed["outside_mutating"],
        "child_beacon_in_census": child_in_census,
        "before_count": len(before),
        "after_count": len(after),
    }


def detector_control(home: Path) -> dict:
    """Produce a known side effect and require the census to capture it."""
    rel = "detector-control.beacon"
    path = Path(home) / rel
    before = census(home)
    path.write_text("KNOWN-SIDE-EFFECT\n", encoding="utf-8")
    after = census(home)
    diff = diff_census(before, after)
    captured = rel in diff["created"]
    return {
        "produced": rel,
        "captured": captured,
        "pass": captured,
        "created": sorted(diff["created"]),
        "method": "canary-HOME sha256 census around a known write",
    }
