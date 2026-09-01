"""csmon -- the Claude Science health pane for the `mon` launcher.

Registered in .agents/skills/monitor-launcher/monitors.toml as:

    [csmon]
    dir = "claude-science-local"
    entry = "cs_monitor.py"

No `trigger_tool`, mirroring [crcp]: this is a MANUAL health monitor (`mon csmon`), not a
workflow poller, so nothing should auto-open it.

READ-ONLY by construction. It shells to `cs doctor -Json` / `cs status -Json` and renders; it
never starts, stops, recovers or reconfigures the daemon. `cs doctor` is itself read-only.

It renders NOT-CHECKED as its own column rather than folding it into PASS or WARN -- a monitor
that shows a green board over rows nobody could measure is the same fail-open defect the doctor
was rewritten to remove.

`--once` has an 8 second total deadline by default. Use a longer `--deadline` when a complete
doctor report matters more than caller latency. Probes run concurrently; any probe that misses
the deadline is named as NOT-CHECKED and makes the snapshot exit non-zero.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

GLYPH = {
    "PASS": "[+]",
    "FAIL": "[X]",
    "WARN": "[!]",
    "NOT-CHECKED": "[?]",
    "INFO": "[i]",
}


def find_cs() -> Path | None:
    """Deployed copy first, repo checkout second. None if neither exists."""
    # Hermetic render tests can select a dispatcher without touching the live service.
    override = os.environ.get("CSMON_CS")
    if override:
        candidate = Path(override).expanduser()
        return candidate if candidate.is_file() else None
    candidates = [
        Path.home() / ".local" / "bin" / "cs.ps1",
        Path.home()
        / "source"
        / "agent-skills-toolchain"
        / "scripts"
        / "claude-science"
        / "cs.ps1",
        Path.home()
        / "source"
        / "ast-integrate"
        / "scripts"
        / "claude-science"
        / "cs.ps1",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def find_pwsh() -> str | None:
    for exe in ("pwsh", "powershell"):
        found = shutil.which(exe)
        if found:
            return found
    return None


def run_cs(cs: Path, pwsh: str, verb: str, timeout: float) -> tuple[dict | None, str]:
    """-> (parsed, error). Never raises; a dead probe is a reportable state, not a crash."""
    cmd = [pwsh, "-NoProfile", "-File", str(cs), verb, "-Json"]
    # Files cannot be held open as anonymous pipe handles by pwsh/wsl grandchildren. Driving
    # Popen directly also avoids subprocess.run's unbounded communicate() after TimeoutExpired.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stdout_file:
        try:
            proc = subprocess.Popen(cmd, stdout=stdout_file, stderr=subprocess.STDOUT)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Killing only pwsh leaves wsl.exe descendants alive. Kill the whole Windows
                # process tree, then bound even the final wait: timeout handling must terminate.
                if os.name == "nt":
                    subprocess.Popen(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    ).wait(timeout=2)
                else:
                    proc.kill()
                try:
                    proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                return None, "cs {} timed out after {:.1f}s (VM wedged?)".format(
                    verb, timeout
                )
        except (OSError, subprocess.SubprocessError) as exc:
            return None, "cannot run cs {}: {}".format(verb, exc)
        stdout_file.seek(0)
        out = stdout_file.read().strip()
    if not out:
        return None, "cs {} produced no output (exit {})".format(verb, proc.returncode)
    try:
        return json.loads(out.splitlines()[-1]), ""
    except (ValueError, IndexError):
        return None, "cs {} output was not JSON: {}".format(verb, out[:160])


def collect_probes(
    cs: Path, pwsh: str, timeout: float, deadline: float
) -> tuple[dict | None, dict | None, list[str]]:
    """Run both probes concurrently and return no later than the total deadline."""
    results: dict[str, tuple[dict | None, str]] = {}
    lock = threading.Lock()

    def probe(verb: str) -> None:
        result = run_cs(cs, pwsh, verb, min(timeout, deadline))
        with lock:
            results[verb] = result

    threads = {
        verb: threading.Thread(target=probe, args=(verb,), daemon=True)
        for verb in ("status", "doctor")
    }
    started = time.monotonic()
    for thread in threads.values():
        thread.start()
    for thread in threads.values():
        thread.join(max(0.0, deadline - (time.monotonic() - started)))

    errors: list[str] = []
    for verb in ("status", "doctor"):
        if verb not in results:
            errors.append("NOT-CHECKED / deadline exceeded: cs {}".format(verb))
        elif results[verb][1]:
            errors.append("NOT-CHECKED / {}".format(results[verb][1]))
    return (
        results.get("status", (None, ""))[0],
        results.get("doctor", (None, ""))[0],
        errors,
    )


def render(
    status: dict | None, doctor: dict | None, errors: list[str], cs: Path
) -> str:
    lines = [
        "",
        "  Claude Science - csmon  ({})".format(time.strftime("%Y-%m-%dT%H:%M:%S")),
        # Naming the dispatcher is not decoration. find_cs() prefers the DEPLOYED copy, so a
        # stale ~/.local/bin/cs.ps1 silently produces degraded output (missing JSON, missing
        # fields) that looks like a monitor bug. Printing the path makes that one glance.
        "  via      : {}".format(cs),
        "",
    ]
    if status:
        state = "DOWN"
        if status.get("running"):
            state = "SLOW *** WEDGED ***" if status.get("wedged") else "HEALTHY"
        lines.append(
            "  state    : {}  (http {}, {}ms)".format(
                state, status.get("http_status"), status.get("latency_ms")
            )
        )
        lines.append(
            "  url      : {}  pid={} port={}".format(
                status.get("url"), status.get("pid"), status.get("port")
            )
        )
        lines.append(
            "  host     : wsl_up={} wsl_disk={}GB host_ram={}GB".format(
                status.get("wsl_up"),
                status.get("free_wsl_disk_gb"),
                status.get("host_free_ram_gb"),
            )
        )
        lines.append(
            "  watchdog : alive={} procs={} beat={}s last_recover={}".format(
                status.get("watchdog_alive"),
                status.get("watchdog_procs"),
                status.get("watchdog_beat_s"),
                status.get("last_recover") or "n/a",
            )
        )
        lines.append("")

    if doctor:
        for row in doctor.get("rows", []):
            lines.append(
                "  {} {:<28} {:<12} {}".format(
                    GLYPH.get(row.get("Status"), "[ ]"),
                    row.get("Check", "?"),
                    row.get("Status", "?"),
                    row.get("Detail", ""),
                )
            )
        lines.append("")
        lines.append(
            "  summary: {} FAIL, {} WARN, {} NOT-CHECKED, {} PASS".format(
                doctor.get("fail"),
                doctor.get("warn"),
                doctor.get("not_checked"),
                doctor.get("pass"),
            )
        )
        if doctor.get("not_checked"):
            lines.append(
                "  NOT-CHECKED rows were NOT measured - this board is not all-green."
            )

    for err in errors:
        lines.append("  [?] {}".format(err))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Claude Science health monitor (read-only)."
    )
    ap.add_argument("--once", action="store_true", help="render one snapshot and exit")
    ap.add_argument("--json", action="store_true", help="emit the raw combined JSON")
    ap.add_argument(
        "--interval", type=float, default=60, help="seconds between refreshes"
    )
    ap.add_argument(
        "--timeout", type=float, default=8, help="per-probe timeout, seconds"
    )
    ap.add_argument(
        "--deadline",
        type=float,
        default=8,
        help="total --once deadline in seconds; increase for a complete doctor report",
    )
    args = ap.parse_args(argv)

    if args.timeout <= 0 or args.deadline <= 0 or args.interval <= 0:
        ap.error("--timeout, --deadline and --interval must be positive")

    cs = find_cs()
    pwsh = find_pwsh()
    if cs is None or pwsh is None:
        missing = "cs.ps1" if cs is None else "pwsh/powershell"
        # FAIL CLOSED: not being able to look is not the same as everything being fine.
        print("FAILED:csmon cannot locate {} - nothing was measured".format(missing))
        return 1

    while True:
        # A continuous refresh also has a total bound no larger than its interval.
        total_deadline = (
            args.deadline if args.once else min(args.deadline, args.interval)
        )
        status, doctor, errors = collect_probes(
            cs, pwsh, min(args.timeout, total_deadline), total_deadline
        )

        if args.json:
            print(
                json.dumps(
                    {
                        "via": str(cs),
                        "status": status,
                        "doctor": doctor,
                        "errors": errors,
                    }
                )
            )
        else:
            if not args.once and os.name == "nt":
                os.system("")  # noqa: S605,S607 - enable ANSI/redraw on legacy consoles  # nosemgrep: quality.opengrep.python-os-system -- argument is a compile-time EMPTY literal, so there is no injectable surface; this is the documented Windows trick to enable VT/ANSI processing on a legacy console, not a command invocation
            print(render(status, doctor, errors, cs), flush=True)

        if args.once:
            unmeasured = bool(errors) or bool(doctor and doctor.get("not_checked"))
            failing = bool(doctor and doctor.get("fail"))
            return 1 if (unmeasured or failing) else 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
