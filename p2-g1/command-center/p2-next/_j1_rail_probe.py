"""Re-probe the cross-vendor Codex rail end-to-end, with a known-broken control.

The lane's owner-facing page says the rail is DOWN on the strength of ONE transport
(a single `mcp__codex__codex` call). This probe exercises the transport that
rules/common/cross-vendor-dispatch.md SECTION 3 actually prescribes -- `codex exec`
with the prompt off stdin and `--ignore-user-config` -- and applies the SECTION 2
AND-gate rather than an exit code alone:

    exit 0  AND  -o file exists  AND  non-empty  AND  carries the nonce we demanded.

DETECTOR CONTROL (the part that makes a PASS informative): the same call is repeated
with CODEX_HOME pointed at an EMPTY scratch directory, so no credential is reachable.
If that control also "succeeds", the probe is not measuring auth at all and its green
means nothing. No credential is read for value, written, rotated or printed; the
control only redirects one subprocess's HOME at an empty temp dir.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent
TIMEOUT_SEC = 300


def resolve_codex() -> str:
    """`codex` on PATH is a .ps1/.cmd shim that CreateProcess cannot launch.

    Round 1 of this probe passed the bare name and got
    `[WinError 2] The system cannot find the file specified` for BOTH the live
    call and the control -- which would have read as "the rail is down" if the
    control had not refused to discriminate. Resolve the .cmd explicitly, the
    same defect class as `which` in Git Bash missing a .cmd shim.
    """
    import shutil

    for cand in ("codex.cmd", "codex.exe", "codex"):
        found = shutil.which(cand)
        if found and not found.lower().endswith(".ps1"):
            return found
    raise SystemExit("FAILED:j1-rail-probe cannot resolve a launchable codex binary")


def run_codex(prompt: str, out_path: pathlib.Path, codex_home: str | None) -> dict:
    """One `codex exec` invocation. Returns the full AND-gate evidence, never raises."""
    env = dict(os.environ)
    if codex_home is not None:
        env["CODEX_HOME"] = codex_home
    cmd = [
        resolve_codex(),
        "exec",
        "--ignore-user-config",
        "--sandbox",
        "read-only",
        "-o",
        str(out_path),
        "-",
    ]
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SEC,
            env=env,
            shell=False,
        )
        rc: int | None = proc.returncode
        stderr, stdout = proc.stderr, proc.stdout
    except subprocess.TimeoutExpired:
        rc, stderr, stdout = None, f"TIMEOUT after {TIMEOUT_SEC}s", ""
    except FileNotFoundError as exc:
        rc, stderr, stdout = None, f"codex not found: {exc}", ""
    elapsed = round(time.time() - started, 1)

    exists = out_path.exists()
    body = out_path.read_text(encoding="utf-8", errors="replace") if exists else ""
    return {
        "exit_code": rc,
        "elapsed_sec": elapsed,
        "out_exists": exists,
        "out_bytes": len(body.encode("utf-8")),
        "out_body": body.strip()[:200],
        "stderr_tail": (stderr or "").strip()[-400:],
        "stdout_tail": (stdout or "").strip()[-200:],
    }


def and_gate(ev: dict, nonce: str) -> bool:
    """cross-vendor-dispatch SECTION 2: exit 0 AND file AND non-empty AND validates."""
    return (
        ev["exit_code"] == 0
        and ev["out_exists"]
        and ev["out_bytes"] > 0
        and nonce in ev["out_body"]
    )


def main() -> int:
    nonce = f"RAILPROBE-{uuid.uuid4().hex[:12].upper()}"
    prompt = (
        "Reply with exactly this token and nothing else, no punctuation, "
        f"no explanation: {nonce}"
    )

    tmpdir = pathlib.Path(tempfile.mkdtemp(prefix="railprobe-"))
    results: dict[str, object] = {
        "probe": "codex exec --ignore-user-config --sandbox read-only -o <f> -",
        "resolved_binary": resolve_codex(),
        "nonce": nonce,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # --- LIVE: the real credential store, untouched ------------------------
    live_out = tmpdir / "live.txt"
    live = run_codex(prompt, live_out, codex_home=None)
    live["and_gate_pass"] = and_gate(live, nonce)
    results["live"] = live

    # --- CONTROL: an EMPTY CODEX_HOME, so no credential is reachable -------
    empty_home = tmpdir / "empty-codex-home"
    empty_home.mkdir()
    ctrl_out = tmpdir / "control.txt"
    ctrl = run_codex(prompt, ctrl_out, codex_home=str(empty_home))
    ctrl["and_gate_pass"] = and_gate(ctrl, nonce)
    results["control_empty_codex_home"] = ctrl

    # The control must NOT pass, or the probe cannot tell auth-up from auth-down.
    control_discriminates = live["and_gate_pass"] and not ctrl["and_gate_pass"]
    results["control_discriminates"] = control_discriminates

    if live["and_gate_pass"] and ctrl["and_gate_pass"]:
        verdict = (
            "DETECTOR-FAILURE: control passed too; this probe does not measure auth"
        )
    elif live["and_gate_pass"]:
        verdict = "RAIL-UP: codex exec authenticates and returns the demanded nonce"
    elif not live["and_gate_pass"] and not ctrl["and_gate_pass"]:
        verdict = "RAIL-DOWN-OR-INERT: live failed; control also failed (expected) "
    else:
        verdict = (
            "SELF-CONTRADICTING: live failed while an unauthenticated control passed"
        )
    results["verdict"] = verdict

    out = HERE / "J1-RAIL-PROBE.json"
    out.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")

    print(json.dumps(results, indent=2))
    print()
    print(f"VERDICT: {verdict}")
    print(f"control discriminates: {control_discriminates}")
    print(f"wrote {out}")

    if not control_discriminates:
        print("FAILED:j1-rail-probe the control did not discriminate")
        return 1
    print("SUCCESS:j1-rail-probe live passes the AND-gate, control fails")
    return 0


if __name__ == "__main__":
    sys.exit(main())
