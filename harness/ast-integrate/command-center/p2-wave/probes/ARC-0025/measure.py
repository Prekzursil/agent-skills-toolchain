#!/usr/bin/env python3
"""Live context + latency measurement for A4 lazy-activation cost."""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as INV  # noqa: E402
import tokenizer as TOK  # noqa: E402

PYTHON = sys.executable
MCP_ECHO = HERE / "mcp_stdio_echo.py"
REPEATS = 3
ERROR_BAND_PCT = 10.0
LATENCY_SPREAD_LIMIT_PCT = 30.0


def direction(a: int, b: int) -> str:
    if a > b:
        return "gt"
    if a < b:
        return "lt"
    return "eq"


def median(xs: list[float]) -> float:
    return float(statistics.median(xs))


def spread_pct(xs: list[float]) -> float:
    if not xs:
        return 0.0
    m = median(xs)
    if m == 0:
        return 0.0 if max(xs) == min(xs) else 100.0
    return abs(max(xs) - min(xs)) / m * 100.0


def read_norm(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def time_skill(path: Path) -> float:
    t0 = time.perf_counter()
    raw = read_norm(path)
    _ = TOK.count_bytes(raw)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


def time_workflow(path: Path) -> float:
    t0 = time.perf_counter()
    raw = read_norm(path)
    json.loads(raw.decode("utf-8"))
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


def time_mcp() -> float:
    t0 = time.perf_counter()
    p = subprocess.Popen(
        [PYTHON, "-B", str(MCP_ECHO)],
        cwd=str(REPO),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p.stdout is not None and p.stdin is not None
    ready = p.stdout.readline()
    if ready.strip() != "ready":
        p.kill()
        raise RuntimeError(f"mcp analogue did not ready: {ready!r}")
    p.stdin.write("initialize\n")
    p.stdin.flush()
    _ = p.stdout.readline()
    p.wait(timeout=5)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0


def latency_block(runs: list[float]) -> dict[str, Any]:
    return {
        "runs_ms": [round(x, 4) for x in runs],
        "median_ms": round(median(runs), 4),
        "spread_pct": round(spread_pct(runs), 3),
    }


def n_star(g0: float, activated: float, mean_body: float, mean_index: float) -> float:
    denom = mean_body - mean_index
    if denom <= 0:
        return float("inf")
    return (g0 + activated) / denom


def scale_cost(n: float, fixed: float, mean: float) -> float:
    return fixed + n * mean


def measure(include_latency: bool = True) -> dict[str, Any]:
    bag = INV.materialize()
    files = bag["files"]
    by_id = {f["id"]: f for f in files}

    for f in files:
        raw = read_norm(REPO / f["path"])
        f["tokens"] = TOK.count_bytes(raw)
        if f["bytes"] != len(raw):
            raise RuntimeError(f"byte drift {f['id']}")

    bodies = [f for f in files if f["role"] == "catalogue"]
    catalogue = bodies
    scaffolding = [f for f in files if f["role"] == "scaffolding"]
    resident = [f for f in files if f["role"] == "gateway_resident"]

    always_bytes = sum(f["bytes"] for f in bodies)
    always_tokens = sum(f["tokens"] for f in bodies)

    activated_ids = list(bag["activated_ids"])
    missing = [i for i in activated_ids if i not in by_id]
    if missing:
        raise RuntimeError(f"activated missing: {missing}")
    activated = [by_id[i] for i in activated_ids]
    act_bytes = sum(f["bytes"] for f in activated)
    act_tokens = sum(f["tokens"] for f in activated)

    g0_bytes = sum(f["bytes"] for f in resident)
    g0_tokens = sum(f["tokens"] for f in resident)
    index = by_id["a4.index"]
    n_cat = len(catalogue)
    mean_body_tok = sum(f["tokens"] for f in catalogue) / n_cat
    mean_body_b = sum(f["bytes"] for f in catalogue) / n_cat
    mean_index_tok = index["tokens"] / n_cat
    mean_index_b = index["bytes"] / n_cat
    scaf_tok = sum(f["tokens"] for f in scaffolding)
    scaf_b = sum(f["bytes"] for f in scaffolding)
    # Gateway resident INDEX scales with N; GATEWAY.json is fixed.
    gw_stub = by_id["a4.gateway"]
    g0_fixed_tok = gw_stub["tokens"]
    g0_fixed_b = gw_stub["bytes"]

    # C_always(N)=N*B ; C_gateway(N)=G_stub+N*I+A
    # N* = (G_stub + A) / (B - I). Scaffolding is reported, not in N*.
    ns_tok = n_star(g0_fixed_tok, act_tokens, mean_body_tok, mean_index_tok)
    ns_b = n_star(g0_fixed_b, act_bytes, mean_body_b, mean_index_b)
    ratio = (
        max(ns_tok, ns_b) / min(ns_tok, ns_b)
        if math.isfinite(ns_tok) and math.isfinite(ns_b) and min(ns_tok, ns_b) > 0
        else float("inf")
    )

    def first_pos(nstar: float) -> int:
        if not math.isfinite(nstar):
            return 10**9
        if nstar <= 0:
            return 1
        # smallest integer N with C_gateway(N) < C_always(N); if equal at int, next.
        n = max(1, math.ceil(nstar + 1e-12) if nstar == int(nstar) else math.ceil(nstar))
        return int(n)

    first_pos_tok = first_pos(ns_tok)
    # Config-first always-on at measured N includes scaffolding + catalogue bodies.
    # Gateway at measured N: resident (index+stub) + activated bodies.
    gw_at_n_tok = g0_tokens + act_tokens
    gw_at_n_b = g0_bytes + act_bytes

    bytes_dir = direction(always_bytes, act_bytes)
    tok_dir = direction(always_tokens, act_tokens)
    agree = bytes_dir == tok_dir and bytes_dir == "gt"

    lat: dict[str, Any] = {"repeats": REPEATS, "skipped": not include_latency}
    if include_latency:
        skill_path = REPO / by_id["skill.council"]["path"]
        wf_path = REPO / by_id["wf.catalog-class.discovery-only"]["path"]
        skill_runs = [time_skill(skill_path) for _ in range(REPEATS)]
        wf_runs = [time_workflow(wf_path) for _ in range(REPEATS)]
        mcp_runs = [time_mcp() for _ in range(REPEATS)]
        lat = {
            "repeats": REPEATS,
            "clock": "time.perf_counter",
            "machine": "linux-this-box",
            "skill": latency_block(skill_runs),
            "workflow": latency_block(wf_runs),
            "mcp_mount": latency_block(mcp_runs),
            "measurement_command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0025/probe1_two_signal.py"
            ),
            "note": (
                "Skill/workflow are in-process read+parse (OS cache may help). "
                "MCP is a new stdio process each repeat (true cold start analogue)."
            ),
        }

    inv_files = []
    for f in files:
        inv_files.append(
            {
                "id": f["id"],
                "kind": f["kind"],
                "path": f["path"],
                "bytes": f["bytes"],
                "tokens": f["tokens"],
                "role": f["role"],
                "sha256": f["sha256"],
            }
        )

    return {
        "tokenizer": TOK.pin_record(),
        "inventory": {
            "root": bag["root"],
            "file_count": len(files),
            "catalogue_n": n_cat,
            "scaffolding_n": len(scaffolding),
            "files": inv_files,
            "host_present": bag["host_present"],
            "registry_path": bag["registry_path"],
        },
        "always_on": {
            "bytes": always_bytes,
            "tokens": always_tokens,
            "file_ids": [f["id"] for f in bodies],
            "measurement_command": (
                "python3 -c \"from pathlib import Path; import sys; "
                "sys.path.insert(0,'command-center/p2-wave/probes/ARC-0025'); "
                "import measure; print(measure.measure(False)['always_on'])\""
            ),
        },
        "activated_set": {
            "bytes": act_bytes,
            "tokens": act_tokens,
            "members": [
                {"id": f["id"], "kind": f["kind"], "path": f["path"]}
                for f in activated
            ],
            "measurement_command": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0025/probe1_two_signal.py"
            ),
        },
        "gateway_at_measured_n": {
            "bytes": gw_at_n_b,
            "tokens": gw_at_n_tok,
            "resident_bytes": g0_bytes,
            "resident_tokens": g0_tokens,
        },
        "two_signal": {
            "always_on_bytes": always_bytes,
            "always_on_tokens": always_tokens,
            "activated_bytes": act_bytes,
            "activated_tokens": act_tokens,
            "bytes_direction": bytes_dir,
            "tokens_direction": tok_dir,
            "agree_in_direction": agree,
            "empty_inventory_tokens": 0,
            "empty_vs_activated_tokens_direction": direction(0, act_tokens),
        },
        "means": {
            "catalogue_n": n_cat,
            "mean_body_tokens": mean_body_tok,
            "mean_body_bytes": mean_body_b,
            "mean_index_row_tokens": mean_index_tok,
            "mean_index_row_bytes": mean_index_b,
            "scaffolding_tokens": scaf_tok,
            "scaffolding_bytes": scaf_b,
            "gateway_stub_tokens": g0_fixed_tok,
            "gateway_stub_bytes": g0_fixed_b,
        },
        "break_even": {
            "formula": (
                "C_always(N)=N*mean_catalogue_body; "
                "C_gateway(N)=gateway_stub + N*mean_index_row + activated_set(K=3). "
                "N* = (stub + activated) / (mean_body - mean_index). "
                "Gateway is NET NEGATIVE for N < N* (context tokens). "
                "Plugin/marketplace/docs/catalogs are scaffolding, measured separately, "
                "not folded into catalogue N."
            ),
            "n_star_tokens": ns_tok if math.isfinite(ns_tok) else None,
            "n_star_bytes": ns_b if math.isfinite(ns_b) else None,
            "net_negative_below": ns_tok if math.isfinite(ns_tok) else None,
            "first_net_positive_integer_n": first_pos_tok,
            "bytes_tokens_n_star_ratio": ratio if math.isfinite(ratio) else None,
            "measured_n": n_cat,
            "gateway_net_negative_at_measured_n": gw_at_n_tok > always_tokens,
        },
        "latency": lat,
        "error_band_pct": ERROR_BAND_PCT,
        "latency_spread_limit_pct": LATENCY_SPREAD_LIMIT_PCT,
        "agree": agree,
    }


def wc_c(path: Path) -> int:
    p = subprocess.run(
        ["wc", "-c", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return int(p.stdout.split()[0])


def remeasure_shell_bytes(files: list[dict[str, Any]]) -> dict[str, int]:
    """Mechanically different byte probe: shell wc -c."""
    out = {}
    for f in files:
        out[f["id"]] = wc_c(REPO / f["path"])
    return out


if __name__ == "__main__":
    doc = measure(include_latency=True)
    print(json.dumps({
        "always_on": doc["always_on"],
        "activated_set": {k: doc["activated_set"][k] for k in ("bytes", "tokens")},
        "two_signal": doc["two_signal"],
        "break_even": doc["break_even"],
        "latency": {
            "skill_median_ms": doc["latency"]["skill"]["median_ms"],
            "workflow_median_ms": doc["latency"]["workflow"]["median_ms"],
            "mcp_median_ms": doc["latency"]["mcp_mount"]["median_ms"],
        },
    }, indent=2, sort_keys=True))
