"""Codex readiness as a BEHAVIORAL gate (ultra accepted AND a bogus effort rejected). Version is
OBSERVED and recorded, never gated on an exact match: the node installs codex latest and we do not
control that version, so an exact-version gate would falsely STOP the fan-out. If a future codex
drops ultra, the behavioral both-states probe catches it."""

from __future__ import annotations
import re


def _ver(out: str) -> str:
    m = re.search(r"\d+\.\d+\.\d+", out or "")
    return m.group(0) if m else "unknown"


def assert_codex_ready(run_cmd) -> tuple[bool, str, str]:
    rc, out, _ = run_cmd(["codex", "--version"])
    version = _ver(out)
    if rc != 0:
        return False, version, "codex --version failed"
    rc_u, _, err_u = run_cmd(
        ["codex", "exec", "-c", 'model_reasoning_effort="ultra"', "--", "noop"]
    )
    if rc_u != 0:
        return False, version, f"ultra rejected (rc={rc_u}): {err_u.strip()[:120]}"
    rc_b, _, _ = run_cmd(
        ["codex", "exec", "-c", 'model_reasoning_effort="wombat"', "--", "noop"]
    )
    if rc_b == 0:
        return (
            False,
            version,
            "both-states failure: a bogus effort was ALSO accepted; probe is blind",
        )
    return True, version, f"ready (codex {version}, ultra accepted, bogus rejected)"


def check_node_preflight(text: str) -> tuple[bool, str, str]:
    """Parse a node preflight unit's self-report: lines `codex_version:`, `ultra_rc:`, `bogus_rc:`.
    Gate is behavioral (ultra_rc==0 AND bogus_rc!=0). Version recorded, not gated."""

    def find(k):
        m = re.search(rf"^{k}:\s*(.+)$", text or "", re.M)
        return m.group(1).strip() if m else None

    version, ultra, bogus = (
        find("codex_version") or "unknown",
        find("ultra_rc"),
        find("bogus_rc"),
    )
    if ultra != "0":
        return False, version, f"node ultra_rc={ultra} (expected 0)"
    if bogus is None or bogus == "0":
        return False, version, f"node bogus_rc={bogus} (expected nonzero; probe blind)"
    return True, version, f"node ready (codex {version}, ultra ok, bogus rejected)"
