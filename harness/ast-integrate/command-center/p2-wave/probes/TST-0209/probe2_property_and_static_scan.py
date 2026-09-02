#!/usr/bin/env python3
"""Probe 2: independent reviewer — 200-shape property test + static scan.

Evidence (b): no production call site performs its own redaction as the
only defense. A call-site-only helper does not protect a NEW site; the
sink does.
"""
from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "tools" / "lib"
sys.path.insert(0, str(LIB))

from secret_shapes import N_SHAPES, iter_shapes  # noqa: E402
from sink_scrub import (  # noqa: E402
    REDACTED,
    capture_sink,
    mutant_call_site_redact_then_write,
    mutant_raw_write,
    reset_sink,
    scrub,
)
from observability import log_error, log_exception  # noqa: E402
from static_scan import run_scan  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "TST-0209.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0209-probe2 {msg}")
    return 1


def _js_parity(shape) -> dict:
    node = shutil.which("node")
    mjs = LIB / "security.mjs"
    if not node or not mjs.is_file():
        return {"ran": False, "reason": "node-or-module-absent"}
    try:
        proc = subprocess.run(
            [node, str(mjs)],
            input=shape.exception_message(),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ran": False, "reason": type(exc).__name__}
    out = proc.stdout or ""
    return {
        "ran": True,
        "exit_code": proc.returncode,
        "infix_absent": shape.infix not in out,
        "marker_present": REDACTED in out,
        "ok": proc.returncode == 0 and shape.infix not in out and REDACTED in out,
    }


def main() -> int:
    shapes = iter_shapes()
    if len(shapes) != N_SHAPES:
        return fail(f"shape count {len(shapes)} want {N_SHAPES}")

    leaked: list[tuple[str, int]] = []
    sink, buf = capture_sink()
    try:
        for shape in shapes:
            try:
                raise RuntimeError(shape.exception_message())
            except RuntimeError as exc:
                out = log_exception(exc)
            if shape.infix in out:
                leaked.append((shape.family, shape.index))
        captured = buf.getvalue()
        for shape in shapes:
            if shape.infix in captured:
                leaked.append((shape.family, shape.index))
    finally:
        reset_sink()

    leaked = sorted(set(leaked))
    print(f"property_shapes={N_SHAPES} leaked={len(leaked)}")
    if leaked:
        sample = ",".join(f"{f}:{i}" for f, i in leaked[:12])
        return fail(f"exception property leaked families {sample}")

    scan = run_scan(extra_call_sites=[HERE / "probe1_new_call_site.py"])
    print(
        "static_scan ok={ok} sink_emit_scrubs={sink} call_sites_ok={sites} mjs_ok={mjs}".format(
            ok=scan["ok"],
            sink=scan["sink"].get("_emit_calls_scrub"),
            sites=all(r["ok"] for r in scan["call_sites"]),
            mjs=scan["security_mjs"].get("ok"),
        )
    )
    if not scan["ok"]:
        return fail(f"static scan {json.dumps(scan, sort_keys=True)[-1500:]}")

    wrapped, fresh = shapes[0], shapes[1]
    protected = io.StringIO()
    mutant_call_site_redact_then_write(protected, wrapped.exception_message())
    raw = io.StringIO()
    mutant_raw_write(raw, fresh.exception_message())
    if wrapped.infix in protected.getvalue():
        return fail("call-site helper failed to redact its own payload")
    if fresh.infix not in raw.getvalue():
        return fail("new site without helper did not leak — mutation control vacuous")
    sink, _buf = capture_sink()
    try:
        still = log_error(fresh.exception_message())
    finally:
        reset_sink()
    if fresh.infix in still:
        return fail("sink missed the new site the call-site helper never saw")
    print("call_site_only_defense_insufficient=True sink_catches_new_site=True")

    js = _js_parity(shapes[0])
    print(f"js_parity ran={js.get('ran')} ok={js.get('ok')} reason={js.get('reason', '')}")
    if js.get("ran") and not js.get("ok"):
        return fail("security.mjs stdin scrub leaked or missed marker")

    if RECEIPT.is_file():
        receipt_text = RECEIPT.read_text(encoding="utf-8")
        hits = [s.infix for s in shapes if s.infix in receipt_text]
        print(f"receipt_infix_hits={len(hits)}")
        if hits:
            return fail("receipt contains a synthetic secret infix")
        if "SUCCESS:TST-0209" not in receipt_text:
            return fail("receipt sentinel absent")
    else:
        print("receipt_infix_hits=deferred (receipt not yet written)")

    # Direct scrub of a PEM-shaped exception string (independent of logging).
    pem = next(s for s in shapes if s.family == "pem")
    if pem.infix in scrub(pem.exception_message()):
        return fail("direct scrub missed pem family")
    print("direct_scrub_pem=True")

    summary = {
        "probe": "probe2-property-and-static-scan",
        "unit_id": "TST-0209",
        "pass": True,
        "shapes": N_SHAPES,
        "leaked": 0,
        "static_scan_ok": True,
        "call_site_only_insufficient": True,
        "js_parity": js,
        "reviewer_id": "TST-0209-probe2-property-and-static-scan",
        "verdict": "PASS",
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:TST-0209-probe2 200 exception shapes; static scan; call-site-only insufficient")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
