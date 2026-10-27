#!/usr/bin/env python3
"""TST-0209 probe 2: 200-shape property + static scan + mutant + JS parity
(rebuild, shard17-w4).

The dead prior builder's receipt names THIS probe as its reviewer
(TST-0209-probe2-property-and-static-scan, verdict PASS, independent=true)
but left no file on disk - the closure could not verify live. This rebuild
makes the instrument real. PASS needs:
  * property: all 200 synthetic secret shapes pushed through the exception
    channel come out with the infix absent and [REDACTED] present;
  * static scan: the production call-site module (tools/lib/observability.py)
    never imports or calls scrub/iter_shapes - scrubbing is sink-only;
  * mutant control: the call-site-only regime cannot protect a NEW site -
    an unopted site's raw output keeps the infix while the sink redacts it;
  * JS twin parity: tools/lib/security.mjs scrub redacts a live shape via a
    node stdin round-trip.
"""
from __future__ import annotations
import ast
import io
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LIB = REPO / "tools" / "lib"
sys.path.insert(0, str(LIB))

import observability  # noqa: E402
import sink_scrub  # noqa: E402
from secret_shapes import iter_shapes  # noqa: E402

UID = "TST-0209"


def fail(msg):
    print(f"FAILED:{UID}-probe2 {msg}")
    return 1


def static_scan_call_sites():
    """AST scan of the production call-site module.

    The sink-only pattern REQUIRES importing the sink route (_emit); what a
    call site must never do is import or call the SCRUBBER itself (scrub /
    the shape machinery) - that would be per-call-site redaction. Importing
    _emit from sink_scrub is therefore allowed and expected; any scrub or
    shape import/call is a hit."""
    src = (LIB / "observability.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = {"scrub", "iter_shapes", "secret_shapes"}
    hits = []
    routes_sink = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in banned:
                    hits.append(f"import {a.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            names = {a.name for a in node.names}
            if root in banned or "scrub" in names or "iter_shapes" in names:
                hits.append(f"from {node.module} import {sorted(names)}")
            if root == "sink_scrub" and "_emit" in names:
                routes_sink = True
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else "")
            if name == "scrub":
                hits.append("call scrub()")
    if not routes_sink:
        hits.append("call-site module does not route through the sink (_emit)")
    return hits


def main() -> int:
    shapes = iter_shapes()

    # 1. property: 200 shapes through the exception channel, sink captured
    failures = []
    buf, _ = sink_scrub.capture_sink()
    try:
        for s in shapes:
            try:
                raise RuntimeError(f"handled {s.secret} [{s.family}:{s.index}]")
            except RuntimeError as exc:
                out = observability.log_exception(exc)
            if s.infix in out or sink_scrub.REDACTED not in out:
                failures.append(s.infix)
        stream = buf.getvalue()
    finally:
        sink_scrub.reset_sink()
    sink_stream_clean = all(s.infix not in stream for s in shapes)
    property_pass = len(shapes) == 200 and not failures and sink_stream_clean

    # 2. static scan: sink-only defense at call sites
    hits = static_scan_call_sites()
    static_pass = not hits

    # 3. mutant control: call-site-only redaction leaves a NEW site exposed.
    #    The opted-in known site cleans its own output, but a new site that
    #    just writes (the realistic mistake under a call-site-only regime)
    #    keeps the infix - while the sink route would have redacted it.
    s_new = shapes[7]
    known = sink_scrub.scrub(f"known site {s_new.secret}")  # opted-in: clean
    new_site_raw = f"new site {s_new.secret}"               # unopted: leaks
    sink_route = observability._emit(f"new site {s_new.secret}")
    mutant_leaves_new_site_exposed = (
        s_new.infix not in known
        and s_new.infix in new_site_raw
        and s_new.infix not in sink_route)

    # 4. JS twin parity via node stdin round-trip
    secret = shapes[9].secret
    node_code = (
        "import { scrub } from './security.mjs';"
        "let d=''; process.stdin.on('data', c => d += c);"
        "process.stdin.on('end', () => process.stdout.write(scrub(d)));"
    )
    js_out = ""
    try:
        p = subprocess.run(["node", "--input-type=module", "-e", node_code],
                           input=secret, capture_output=True, text=True,
                           cwd=str(LIB), timeout=60)
        js_out = p.stdout
        js_parity = (p.returncode == 0 and shapes[9].infix not in js_out
                     and sink_scrub.REDACTED in js_out)
    except (OSError, subprocess.TimeoutExpired):
        js_parity = False

    checks = {
        "property_200_shapes_redacted": bool(property_pass),
        "static_scan_no_call_site_scrub": bool(static_pass),
        "sink_stream_captured_clean": bool(sink_stream_clean),
        "mutant_call_site_only_leaves_new_site_exposed": bool(mutant_leaves_new_site_exposed),
        "js_twin_parity": bool(js_parity),
    }
    out = {
        "probe": "probe2-property-and-static-scan",
        "unit_id": UID,
        "shape_count": len(shapes),
        "property_failure_count": len(failures),
        "property_failures_sample": failures[:5],
        "static_scan_hits": hits,
        "sink_stream_clean": bool(sink_stream_clean),
        "js_redacted_sample": js_out[:40],
        "checks": checks,
        "ok": all(checks.values()),
    }
    print(json.dumps(out, sort_keys=True))
    if not out["ok"]:
        return fail("property/static/mutant/parity check failed")
    print(f"SUCCESS:{UID}-probe2 200 shapes redacted; sink-only scan clean; mutant exposes new site; JS parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
