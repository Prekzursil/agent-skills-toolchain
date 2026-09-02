#!/usr/bin/env python3
"""Probe 2: re-invoke recorded spawn bounds live; recompute hook uniqueness."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import escalate as E  # noqa: E402
import hooks as K  # noqa: E402

UNIT = "RES-0162"
ART = REPO / "command-center/research/prior-art/RES-0162-cross-vendor-invocation-surface-leaks.json"
MUST_MEASURE = ("python3", "posix-true")


def fail(msg: str) -> int:
    print(f"FAILED:RES-0162-probe2 {msg}")
    return 1


def discover_map() -> dict[str, dict]:
    return {r["id"]: r for r in E.discover()}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if "SUCCESS:RES-0162" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    meas = doc.get("measurements") or {}
    stored = {r.get("id"): r for r in (meas.get("runtimes") or []) if isinstance(r, dict)}
    live_disc = discover_map()
    confirmed = []
    for rid in MUST_MEASURE:
        row = stored.get(rid) or {}
        if row.get("status") != "MEASURED":
            return fail(f"{rid} was not MEASURED")
        last_ok = int(row.get("last_ok_bytes") or 0)
        first_fail = row.get("first_fail_bytes")
        if not last_ok or not first_fail:
            return fail(f"{rid} missing bounds")
        spec = live_disc.get(rid)
        if spec is None:
            return fail(f"{rid} missing from discover()")
        got = E.confirm_bounds(spec, last_ok, int(first_fail))
        if not got.get("ok"):
            return fail(f"{rid} bound confirm failed {json.dumps(got, sort_keys=True)}")
        quoted = str(row.get("first_fail_error") or "")
        if "Errno 7" not in quoted and "Argument list too long" not in quoted:
            if got.get("first_fail_errno") != 7 and "Argument list too long" not in str(
                got.get("first_fail_error") or ""
            ):
                return fail(f"{rid} fail error not E2BIG: {quoted!r} live={got}")
        if rid == "python3":
            child_n = got.get("last_ok_child_n")
            if child_n != last_ok:
                return fail(f"python3 truncated or child_n drift child_n={child_n} last_ok={last_ok}")
        confirmed.append(rid)

    host = meas.get("host") or {}
    if str(host.get("windows_createprocess_32767") or "") != "NOT-CHECKED":
        return fail("Windows CreateProcess must be NOT-CHECKED on this Linux host")
    if str(host.get("sys_platform") or "") == "win32":
        return fail("unexpected win32 platform on this Linux worktree")

    ten_x = meas.get("file_transport_size")
    file_row = meas.get("file_transport") or {}
    if not ten_x or not file_row.get("spawned"):
        return fail("file transport did not spawn at recorded size")
    with tempfile.TemporaryDirectory(prefix="res0162-p2-") as tmp:
        live_file = E.file_transport(int(ten_x), Path(tmp), timeout=5.0)
    if not live_file.get("spawned"):
        return fail(f"file transport re-spawn failed {live_file}")
    if live_file.get("child_n") not in (int(ten_x), None):
        # python --read-file reports n; require exact
        if live_file.get("child_n") != int(ten_x):
            return fail(f"file transport child_n={live_file.get('child_n')} want {ten_x}")

    hook = K.compare()
    stored_hooks = meas.get("hooks") or {}
    if set(hook.get("claude_only") or []) != set(stored_hooks.get("claude_only") or []):
        return fail("claude_only drift")
    if hook.get("unique_lifecycle_runtime") != stored_hooks.get("unique_lifecycle_runtime"):
        return fail("unique_lifecycle_runtime drift")
    if not hook.get("pass"):
        return fail("hook uniqueness did not pass")
    if "WorktreeCreate" not in (hook.get("claude_only") or []):
        return fail("WorktreeCreate not unique to Claude vs Codex")
    if "TeammateIdle" not in (hook.get("claude_only") or []):
        return fail("TeammateIdle not unique to Claude vs Codex")

    for claim in doc.get("claims") or []:
        sigs = claim.get("signals") or []
        if len(sigs) < 2:
            return fail(f"claim {claim.get('id')} needs two signals")
        lin = claim.get("lineage") or {}
        if len(str(lin.get("sha256") or "")) != 64:
            return fail(f"claim {claim.get('id')} lineage sha256")

    out = {
        "probe": "probe2-escalating-payload",
        "unit_id": UNIT,
        "pass": True,
        "confirmed": confirmed,
        "python3_first_fail": (stored.get("python3") or {}).get("first_fail_bytes"),
        "posix_true_first_fail": (stored.get("posix-true") or {}).get("first_fail_bytes"),
        "python3_error": (stored.get("python3") or {}).get("first_fail_error"),
        "file_transport_size": ten_x,
        "unique_lifecycle_runtime": hook.get("unique_lifecycle_runtime"),
        "claude_only_n": len(hook.get("claude_only") or []),
        "windows_createprocess": "NOT-CHECKED",
    }
    print(json.dumps(out, indent=1, sort_keys=True))
    print(
        "SUCCESS:RES-0162-probe2 live bounds re-spawned; E2BIG quoted; "
        "Claude-only hook lifecycle"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
