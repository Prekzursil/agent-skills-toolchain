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
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
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


def run_cs(cs: Path, pwsh: str, verb: str, timeout: int) -> tuple[dict | None, str]:
    """-> (parsed, error). Never raises; a dead probe is a reportable state, not a crash."""
    cmd = [pwsh, "-NoProfile", "-File", str(cs), verb, "-Json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "cs {} timed out after {}s (VM wedged?)".format(verb, timeout)
    except OSError as exc:
        return None, "cannot run cs {}: {}".format(verb, exc)
    out = (proc.stdout or "").strip()
    if not out:
        return None, "cs {} produced no output (exit {})".format(verb, proc.returncode)
    try:
        return json.loads(out.splitlines()[-1]), ""
    except (ValueError, IndexError):
        return None, "cs {} output was not JSON: {}".format(verb, out[:160])


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
        lines.append("  [X] {}".format(err))
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Claude Science health monitor (read-only)."
    )
    ap.add_argument("--once", action="store_true", help="render one snapshot and exit")
    ap.add_argument("--json", action="store_true", help="emit the raw combined JSON")
    ap.add_argument(
        "--interval", type=int, default=60, help="seconds between refreshes"
    )
    ap.add_argument(
        "--timeout", type=int, default=120, help="per-probe timeout, seconds"
    )
    args = ap.parse_args(argv)

    cs = find_cs()
    pwsh = find_pwsh()
    if cs is None or pwsh is None:
        missing = "cs.ps1" if cs is None else "pwsh/powershell"
        # FAIL CLOSED: not being able to look is not the same as everything being fine.
        print("FAILED:csmon cannot locate {} - nothing was measured".format(missing))
        return 1

    while True:
        errors: list[str] = []
        status, err = run_cs(cs, pwsh, "status", args.timeout)
        if err:
            errors.append(err)
        doctor, err = run_cs(cs, pwsh, "doctor", args.timeout)
        if err:
            errors.append(err)

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
            time.sleep(max(5, args.interval))
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
