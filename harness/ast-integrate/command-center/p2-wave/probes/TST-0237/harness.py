#!/usr/bin/env python3
"""Instrumented per-turn harness wall-clock for TST-0237.

Catalog question: how many milliseconds each harness component
(hook dispatch, capability router, rule injection, ledger write) adds to a
turn, and is the total under the declared ceiling.

SCOPE: wall-clock only. Context-token cost of routing is TST-0240 and is
not computed or reported here.

Production turn-pipeline modules (hook dispatcher, packaged capability
router, rule injector, B07 ledger) are discovered if present. Fixture
installs always run through this module so both-states ablation and the
5% attribution check stay live even when those paths are absent.

Each component does real work (match/score/assemble/append). Timings use
time.perf_counter. No time.sleep padding.
"""
from __future__ import annotations

import hashlib
import json
import os
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "TST-0237"
OUT_REL = "command-center/receipts/TST-0237.json"
SCHEMA_REL = "command-center/schema/receipt.schema.json#/$defs/benchmark_result"
SCHEMA_FILE = "command-center/schema/receipt.schema.json"
SUT_REL = "command-center/p2-wave/probes/TST-0237/harness.py"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0237/probe1_instrumented_sum.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0237/probe2_ab_attribution.py"
)

# Wall-clock p50 ceiling for the four in-process components on one turn.
# BASELINE-SNAPSHOT.json is present but does not declare a per-component
# turn-overhead budget. 100 ms sits under the Phase 10 HUD debounce (300 ms)
# and under a single jq spawn (~200 ms); a spawn-bound four-stage
# implementation would miss it.
DECLARED_CEILING_MS = 100.0
RECONCILE_TOLERANCE = 0.05
N_TURNS = 31
WARMUP = 3

COMPONENTS = (
    "hook_dispatch",
    "capability_router",
    "rule_injection",
    "ledger_write",
)

PRODUCTION_CANDIDATES = [
    "tools/agentspec/agentspec/turn.py",
    "tools/agentspec/agentspec/hooks.py",
    "tools/agentspec/agentspec/router.py",
    "tools/harness/turn.py",
    "tools/plugin/hooks.py",
    "tools/router/route.py",
    "hooks/_dispatch/dispatch.py",
    "hooks/_dispatch/manifest.json",
    "command-center/BASELINE-SNAPSHOT.json",
    "rules/common/bash-hud-and-terminal-emit.md",
    "_USER-PROMPTS.md",
]

PROMPT = (
    "Owner asks to route a deploy skill, inject the matching always-on rules, "
    "dispatch pre-turn hooks, and append one ledger record for the turn. "
    "Keywords: deploy skill workflow hook ledger inject capability."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def rel_err(a: float, b: float) -> float:
    denom = max(abs(b), 1e-12)
    return abs(a - b) / denom


def median(xs: Iterable[float]) -> float:
    data = list(xs)
    if not data:
        raise ValueError("median of empty")
    return float(statistics.median(data))


def discover_production() -> dict[str, dict]:
    rows = {}
    for rel in PRODUCTION_CANDIDATES:
        p = REPO / rel
        rows[rel] = {"present": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0}
    return rows


@dataclass
class Install:
    hooks: list[dict]
    capabilities: list[dict]
    rules: list[dict]
    ledger_path: Path
    prompt: str = PROMPT
    prev_hash: str = "0" * 64


def build_install(scratch: Path | None = None) -> Install:
    """Deterministic populated install. Sizes are the measurement fixture."""
    scratch = scratch or (HERE / "_scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    ledger = scratch / "turn-ledger.jsonl"
    if ledger.exists():
        ledger.unlink()

    vocab = [
        "deploy",
        "skill",
        "workflow",
        "hook",
        "ledger",
        "inject",
        "capability",
        "router",
        "rule",
        "turn",
    ]
    hooks = []
    for i in range(1800):
        ev = ("pre-turn", "post-turn", "on-tool")[i % 3]
        hooks.append(
            {
                "id": f"hook.{i:04d}",
                "event": ev,
                "pattern": vocab[i % len(vocab)],
                "sink": f"sink.{i % 40}",
            }
        )
    caps = []
    for i in range(2200):
        triggers = [vocab[i % len(vocab)], vocab[(i + 3) % len(vocab)], f"cap{i % 80}"]
        caps.append(
            {
                "id": f"cap.{i:04d}",
                "triggers": triggers,
                "body": f"capability-{i}-" + ("x" * 48),
            }
        )
    rules = []
    body_pad = "rule-body-line\n" * 12
    for i in range(420):
        tags = [vocab[i % len(vocab)], vocab[(i + 1) % len(vocab)]]
        rules.append(
            {
                "id": f"rule.{i:04d}",
                "tags": tags,
                "always_on": i % 7 == 0,
                "body": f"# rule {i}\n{body_pad}",
            }
        )
    return Install(hooks=hooks, capabilities=caps, rules=rules, ledger_path=ledger)


def _hook_dispatch(install: Install, event: str, payload: str) -> list[str]:
    fired: list[str] = []
    blob = payload.encode("utf-8")
    for hook in install.hooks:
        if hook["event"] != event:
            continue
        material = blob + hook["id"].encode("utf-8") + hook["pattern"].encode("utf-8")
        digest = hashlib.sha256(material).hexdigest()
        if hook["pattern"] in payload or int(digest[:2], 16) < 16:
            fired.append(f"{hook['id']}:{digest[:12]}")
    return fired


def _capability_router(install: Install, prompt: str, k: int = 8) -> list[dict]:
    hay = prompt.lower()
    scored: list[tuple[int, int, str, dict]] = []
    for cap in install.capabilities:
        hits = 0
        for trig in cap["triggers"]:
            if trig in hay:
                hits += 1
        tie = hashlib.sha256((cap["id"] + hay[:80]).encode("utf-8")).digest()[0]
        scored.append((hits, -tie, cap["id"], cap))
    scored.sort(reverse=True)
    out = []
    for hits, _tie, cid, cap in scored[:k]:
        out.append({"id": cid, "hits": hits, "body_bytes": len(cap["body"])})
    return out


def _rule_injection(install: Install, prompt: str, routed: list[dict]) -> dict:
    hay = prompt.lower()
    routed_ids = {r["id"] for r in routed}
    parts: list[str] = []
    kept: list[str] = []
    for rule in install.rules:
        tag_hit = any(t in hay for t in rule["tags"])
        if rule["always_on"] or tag_hit or any(rid[-4:] == rule["id"][-4:] for rid in routed_ids):
            parts.append(rule["body"])
            kept.append(rule["id"])
    block = "\n".join(parts)
    digest = hashlib.sha256(block.encode("utf-8")).hexdigest()
    return {"rule_count": len(kept), "block_bytes": len(block), "sha256": digest}


def _ledger_write(install: Install, record: dict) -> str:
    rec = dict(record)
    rec["prev"] = install.prev_hash
    line = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if b"\n" in line or b"\r" in line:
        raise ValueError("ledger record contains a raw newline")
    data = line + b"\n"
    digest = hashlib.sha256(data).hexdigest()
    install.ledger_path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
    if getattr(os, "O_BINARY", 0):
        flags |= os.O_BINARY
    fd = os.open(install.ledger_path, flags, 0o644)
    try:
        n = os.write(fd, data)
        if n != len(data):
            raise OSError(f"short ledger append: {n}/{len(data)}")
    finally:
        os.close(fd)
    install.prev_hash = digest
    return digest


COMPONENT_FN: dict[str, Callable[[Install, dict], object]] = {}


def _run_hook(install: Install, ctx: dict) -> object:
    return _hook_dispatch(install, "pre-turn", install.prompt)


def _run_router(install: Install, ctx: dict) -> object:
    routed = _capability_router(install, install.prompt)
    ctx["routed"] = routed
    return routed


def _run_rules(install: Install, ctx: dict) -> object:
    injected = _rule_injection(install, install.prompt, ctx.get("routed") or [])
    ctx["injected"] = injected
    return injected


def _run_ledger(install: Install, ctx: dict) -> object:
    record = {
        "unit_id": UNIT,
        "kind": "turn",
        "prompt_sha256": hashlib.sha256(install.prompt.encode("utf-8")).hexdigest(),
        "routed_ids": [r["id"] for r in (ctx.get("routed") or [])],
        "injection_sha256": (ctx.get("injected") or {}).get("sha256"),
        "injection_bytes": (ctx.get("injected") or {}).get("block_bytes", 0),
        "hook_count": len(ctx.get("hooks") or []),
    }
    return _ledger_write(install, record)


COMPONENT_FN = {
    "hook_dispatch": _run_hook,
    "capability_router": _run_router,
    "rule_injection": _run_rules,
    "ledger_write": _run_ledger,
}


@dataclass
class TurnResult:
    total_s: float
    parts_s: dict[str, float]
    ctx: dict = field(default_factory=dict)

    @property
    def total_ms(self) -> float:
        return self.total_s * 1000.0

    @property
    def parts_ms(self) -> dict[str, float]:
        return {k: v * 1000.0 for k, v in self.parts_s.items()}

    @property
    def instrumented_sum_s(self) -> float:
        return sum(self.parts_s.values())


def run_turn(
    install: Install,
    enabled: Iterable[str] | None = None,
    hide_from_instrument: Iterable[str] = (),
) -> TurnResult:
    """One turn. `enabled` defaults to all four components.

    hide_from_instrument: component still RUNS (and is in total) but its
    line item is recorded as 0. Used as the known-broken instrumentation.
    """
    on = set(COMPONENTS if enabled is None else enabled)
    hidden = set(hide_from_instrument)
    ctx: dict = {}
    parts = {name: 0.0 for name in COMPONENTS}
    t0 = time.perf_counter()
    for name in COMPONENTS:
        if name not in on:
            continue
        c0 = time.perf_counter()
        out = COMPONENT_FN[name](install, ctx)
        dt = time.perf_counter() - c0
        if name == "hook_dispatch":
            ctx["hooks"] = out
        if name not in hidden:
            parts[name] = dt
    total = time.perf_counter() - t0
    return TurnResult(total_s=total, parts_s=parts, ctx=ctx)


def _fresh_install() -> Install:
    return build_install(HERE / "_scratch")


def sample_turns(
    n: int,
    enabled: Iterable[str] | None = None,
    hide_from_instrument: Iterable[str] = (),
    warmup: int = WARMUP,
) -> list[TurnResult]:
    install = _fresh_install()
    for _ in range(warmup):
        run_turn(install, enabled=enabled, hide_from_instrument=hide_from_instrument)
    rows = []
    for _ in range(n):
        rows.append(run_turn(install, enabled=enabled, hide_from_instrument=hide_from_instrument))
    return rows


def sample_paired(
    n: int,
    enabled_a: Iterable[str] | None,
    enabled_b: Iterable[str] | None,
    hide_a: Iterable[str] = (),
    hide_b: Iterable[str] = (),
    warmup: int = WARMUP,
) -> tuple[list[TurnResult], list[TurnResult]]:
    """Interleave two enabled-sets so A/B is not a thermal-drift artifact."""
    install = _fresh_install()
    for _ in range(warmup):
        run_turn(install, enabled=enabled_a, hide_from_instrument=hide_a)
        run_turn(install, enabled=enabled_b, hide_from_instrument=hide_b)
    a_rows: list[TurnResult] = []
    b_rows: list[TurnResult] = []
    for _ in range(n):
        a_rows.append(run_turn(install, enabled=enabled_a, hide_from_instrument=hide_a))
        b_rows.append(run_turn(install, enabled=enabled_b, hide_from_instrument=hide_b))
    return a_rows, b_rows


def summarize(rows: list[TurnResult]) -> dict:
    totals = [r.total_ms for r in rows]
    parts = {name: median(r.parts_ms[name] for r in rows) for name in COMPONENTS}
    sum_ms = sum(parts.values())
    total_ms = median(totals)
    return {
        "n": len(rows),
        "total_median_ms": total_ms,
        "parts_median_ms": parts,
        "instrumented_sum_ms": sum_ms,
        "sum_vs_total_rel_err": rel_err(sum_ms, total_ms),
        "total_min_ms": min(totals),
        "total_max_ms": max(totals),
        "all_components_positive": all(v > 0.0 for v in parts.values()),
    }


def measure_instrumented(n: int = N_TURNS) -> dict:
    rows = sample_turns(n, enabled=COMPONENTS)
    s = summarize(rows)
    s["pass_reconcile_sum_vs_total"] = s["sum_vs_total_rel_err"] <= RECONCILE_TOLERANCE
    s["under_ceiling"] = s["total_median_ms"] < DECLARED_CEILING_MS
    s["ceiling_ms"] = DECLARED_CEILING_MS
    s["pass"] = bool(s["pass_reconcile_sum_vs_total"] and s["under_ceiling"] and s["all_components_positive"])
    return s


def measure_ab(n: int = N_TURNS) -> dict:
    on_rows, off_rows = sample_paired(n, COMPONENTS, ())
    on = summarize(on_rows)
    off = summarize(off_rows)
    delta = on["total_median_ms"] - off["total_median_ms"]
    recon = rel_err(on["instrumented_sum_ms"], delta)
    return {
        "n": n,
        "harness_on": on,
        "harness_off": off,
        "ab_delta_ms": delta,
        "sum_vs_ab_rel_err": recon,
        "pass_attribution": recon <= RECONCILE_TOLERANCE and delta > 0.0,
        "harness_off_faster": off["total_median_ms"] < on["total_median_ms"],
    }


def measure_both_states(n: int = N_TURNS, disable: str = "hook_dispatch") -> dict:
    if disable not in COMPONENTS:
        raise ValueError(disable)
    reduced = tuple(c for c in COMPONENTS if c != disable)
    on_rows, off_rows = sample_paired(n, COMPONENTS, reduced)
    on = summarize(on_rows)
    off = summarize(off_rows)
    line_on = on["parts_median_ms"][disable]
    line_off = off["parts_median_ms"][disable]
    paired_drops = [a.total_ms - b.total_ms for a, b in zip(on_rows, off_rows)]
    paired_median_drop = median(paired_drops)
    others_stable = True
    other_moves = {}
    for name in COMPONENTS:
        if name == disable:
            continue
        a = on["parts_median_ms"][name]
        b = off["parts_median_ms"][name]
        move = rel_err(a, b) if a else 0.0
        other_moves[name] = move
        if move > 0.50:
            others_stable = False
    line_moved = line_on > 0.0 and line_off <= line_on * 0.10
    total_moved = paired_median_drop > 0.0
    return {
        "disabled": disable,
        "n": n,
        "line_item_on_ms": line_on,
        "line_item_off_ms": line_off,
        "total_on_ms": on["total_median_ms"],
        "total_off_ms": off["total_median_ms"],
        "total_drop_ms": on["total_median_ms"] - off["total_median_ms"],
        "paired_median_drop_ms": paired_median_drop,
        "other_component_rel_moves": other_moves,
        "line_item_moved": line_moved,
        "total_moved": total_moved,
        "others_stable": others_stable,
        "pass": bool(line_moved and total_moved),
        "on": on,
        "off": off,
    }


def measure_missing_instrument(n: int = N_TURNS, hide: str | None = None) -> dict:
    """Known-broken: run all four, omit one from the instrumented dict."""
    on_rows = sample_turns(n, enabled=COMPONENTS)
    on = summarize(on_rows)
    hide_name = hide or max(on["parts_median_ms"], key=on["parts_median_ms"].get)
    hidden_rows, off_rows = sample_paired(
        n, COMPONENTS, (), hide_a=(hide_name,), hide_b=()
    )
    hidden = summarize(hidden_rows)
    off = summarize(off_rows)
    delta = hidden["total_median_ms"] - off["total_median_ms"]
    sum_vs_total = hidden["sum_vs_total_rel_err"]
    sum_vs_ab = rel_err(hidden["instrumented_sum_ms"], delta)
    fired = sum_vs_total > RECONCILE_TOLERANCE or sum_vs_ab > RECONCILE_TOLERANCE
    return {
        "hidden": hide_name,
        "n": n,
        "hidden_sum_ms": hidden["instrumented_sum_ms"],
        "hidden_total_ms": hidden["total_median_ms"],
        "ab_delta_ms": delta,
        "sum_vs_total_rel_err": sum_vs_total,
        "sum_vs_ab_rel_err": sum_vs_ab,
        "tolerance": RECONCILE_TOLERANCE,
        "detector_fired": fired,
        "pass_negative_control": fired,
        "honest_sum_vs_total_rel_err": on["sum_vs_total_rel_err"],
    }


def campaign(n: int = N_TURNS) -> dict:
    inst = measure_instrumented(n)
    ab = measure_ab(n)
    both = {name: measure_both_states(n, disable=name) for name in COMPONENTS}
    missing = measure_missing_instrument(n)
    both_pass = all(v["pass"] for v in both.values())
    passed = (
        inst["pass"]
        and ab["pass_attribution"]
        and ab["harness_off_faster"]
        and both_pass
        and missing["pass_negative_control"]
    )
    return {
        "instrumented": inst,
        "ab": ab,
        "both_states": both,
        "missing_instrument": missing,
        "pass": passed,
        "production": discover_production(),
        "ceiling_ms": DECLARED_CEILING_MS,
        "tolerance": RECONCILE_TOLERANCE,
        "n": n,
    }
