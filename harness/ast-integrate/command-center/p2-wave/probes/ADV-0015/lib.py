#!/usr/bin/env python3
"""ADV-0015: routing-table / cost-estimator staleness vs published vendor surface.

Probe 1 diffs program tables against today's published ids, windows and prices.
Probe 2 calls the live CNL-0004 cost router with a retired id and classifies
fail-loudly vs silent-substitute vs stale-price estimate vs silent-drop.

Silent substitution is a defect even when the substituted model still works.
Degrade-loudly is the contract.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0015"
OUT_REL = "command-center/adversarial/ADV-0015-model-routing-table-staleness.json"
SCHEMA_REL = "command-center/schema/stale-premise-reprobe.schema.json"
CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"
FIXTURE_REL = (
    "command-center/p2-wave/probes/ADV-0015/fixtures/vendor_surface.json"
)
CNL_COMPOSER_REL = "command-center/p2-wave/probes/CNL-0004/composer.py"
SEED_REL = "tools/command-center/seed.py"
P1_REL = "command-center/p2-wave/probes/ADV-0015/probe1_vendor_surface_diff.py"
P2_REL = "command-center/p2-wave/probes/ADV-0015/probe2_retired_id_runtime.py"
P1_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P1_REL}"
P2_CMD = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {P2_REL}"
LEGAL = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)
PROBE1_NAME = (
    "Probe 1: fetch the current vendor surface and diff every id, window "
    "and price against the table."
)
PROBE2_NAME = (
    "Probe 2 (mechanically different): runtime behaviour test - call the "
    "router with a deliberately retired id and record whether it fails "
    "loudly, silently substitutes, or estimates a cost from a stale price."
)
RETIRED_ID = "text-davinci-003"
DEFECT_BEHAVIOURS = frozenset(
    {"silent-substitute", "silent-drop", "stale-price-estimate"}
)
FETCH_URLS = (
    "https://docs.anthropic.com/en/docs/about-claude/models/overview",
    "https://developers.openai.com/api/docs/models",
)
ID_RE = re.compile(
    r"\b(?:claude-[a-z0-9][a-z0-9.-]*|gpt-[0-9][a-z0-9][a-z0-9.-]*)\b",
    re.I,
)


def load_catalog_unit() -> dict[str, Any]:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT_ID:
            return u
    raise RuntimeError("ADV-0015 missing from catalog")


def catalog_sentinel() -> str:
    return str(load_catalog_unit()["completion_sentinel"])


def load_fixture() -> dict[str, Any]:
    return json.loads((REPO / FIXTURE_REL).read_text(encoding="utf-8"))


def _try_fetch(url: str, timeout: float = 8.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url, headers={"User-Agent": "ADV-0015-stale-premise-reprobe/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(400_000)
            status = int(getattr(resp, "status", 200) or 200)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "url": url,
            "ok": False,
            "status": None,
            "error": type(exc).__name__,
            "ids": [],
        }
    text = raw.decode("utf-8", errors="replace")
    ids = sorted({m.group(0).lower() for m in ID_RE.finditer(text)})
    return {
        "url": url,
        "ok": True,
        "status": status,
        "error": None,
        "ids": ids,
        "bytes": len(raw),
    }


def published_surface() -> dict[str, Any]:
    fx = load_fixture()
    current: set[str] = set()
    by_id: dict[str, dict[str, Any]] = {}
    for vendor in ("anthropic", "openai"):
        block = fx.get(vendor) or {}
        for mid in block.get("current_ids") or []:
            current.add(str(mid).lower())
        for mid, meta in (block.get("by_id") or {}).items():
            by_id[str(mid).lower()] = dict(meta)
            current.add(str(mid).lower())
    fetches = [_try_fetch(u) for u in FETCH_URLS]
    live_ids: set[str] = set()
    retired = {str(x).lower() for x in (fx.get("retired_ids") or [])}
    for f in fetches:
        live_ids.update(str(i).lower() for i in (f.get("ids") or []))
        if f.get("ok"):
            current.update(
                str(i).lower()
                for i in (f.get("ids") or [])
                if str(i).lower() not in retired
            )
    return {
        "fixture_captured_at": fx.get("captured_at"),
        "sources": list(fx.get("sources") or []),
        "current_ids": sorted(current),
        "by_id": by_id,
        "retired_ids": sorted(retired),
        "live_fetches": [
            {
                "url": f["url"],
                "ok": f["ok"],
                "status": f.get("status"),
                "error": f.get("error"),
                "n_ids": len(f.get("ids") or []),
            }
            for f in fetches
        ],
        "live_fetch_any_ok": any(bool(f.get("ok")) for f in fetches),
        "live_ids_sample": sorted(live_ids)[:40],
    }


def extract_catalog_assignments() -> list[dict[str, Any]]:
    data = json.loads((REPO / CATALOG_REL).read_text(encoding="utf-8"))
    counts: Counter[tuple[str, str]] = Counter()
    for u in data.get("work_units") or []:
        if not isinstance(u, dict):
            continue
        asg = u.get("assigned_model_vendor_role")
        if not isinstance(asg, dict):
            continue
        model = str(asg.get("model") or "").strip()
        vendor = str(asg.get("vendor") or "").strip()
        if not model:
            continue
        counts[(vendor.lower(), model.lower())] += 1
    rows = []
    for (vendor, model), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        rows.append(
            {
                "table": "WORK-UNIT-CATALOG.assigned_model_vendor_role",
                "vendor": vendor,
                "model": model,
                "window_tokens": None,
                "price_usd": None,
                "n_units": n,
            }
        )
    return rows


def extract_seed_default() -> dict[str, Any] | None:
    path = REPO / SEED_REL
    if not path.is_file():
        return None
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    value = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign):
            tgt = node.target
            if isinstance(tgt, ast.Name) and tgt.id == "DEFAULTS":
                value = node.value
                break
        elif isinstance(node, ast.Assign):
            if any(
                isinstance(t, ast.Name) and t.id == "DEFAULTS" for t in node.targets
            ):
                value = node.value
                break
    if value is None or not isinstance(value, ast.Dict):
        return None
    defaults = ast.literal_eval(value)
    asg = defaults.get("assignment") or {}
    model = str(asg.get("model") or "").strip()
    if not model:
        return None
    return {
        "table": "tools/command-center/seed.py:DEFAULTS.assignment",
        "vendor": str(asg.get("vendor") or "").lower(),
        "model": model.lower(),
        "window_tokens": None,
        "price_usd": None,
        "n_units": 1,
    }


def load_cnl_composer() -> Any:
    path = REPO / CNL_COMPOSER_REL
    spec = importlib.util.spec_from_file_location("adv0015_cnl0004_composer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load CNL-0004 composer")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_cnl_cost_table() -> list[dict[str, Any]]:
    mod = load_cnl_composer()
    rows: list[dict[str, Any]] = []
    for src, dst in (mod.DOWNGRADE or {}).items():
        rows.append(
            {
                "table": "CNL-0004.DOWNGRADE",
                "vendor": "unknown",
                "model": str(src).lower(),
                "window_tokens": None,
                "price_usd": float(dst[1]),
                "downgrade_to": str(dst[0]).lower(),
                "n_units": 1,
            }
        )
    auto = mod.auto_compose({"id": "adv-0015-inventory"})
    for seat in auto.get("roster") or []:
        rows.append(
            {
                "table": "CNL-0004.auto_compose",
                "vendor": str(seat.get("vendor") or "").lower(),
                "model": str(seat.get("model") or "").lower(),
                "window_tokens": None,
                "price_usd": float(seat.get("cost_usd") or 0),
                "seat_id": seat.get("seat_id"),
                "n_units": 1,
            }
        )
    return rows


def program_tables() -> list[dict[str, Any]]:
    rows = extract_catalog_assignments()
    seed = extract_seed_default()
    if seed:
        rows.append(seed)
    rows.extend(extract_cnl_cost_table())
    return rows


def diff_row(row: dict[str, Any], surface: dict[str, Any]) -> dict[str, Any]:
    mid = str(row.get("model") or "").lower()
    meta = (surface.get("by_id") or {}).get(mid) or {}
    current = set(surface.get("current_ids") or [])
    on = mid in current
    retired = mid in set(surface.get("retired_ids") or [])
    window_row = row.get("window_tokens")
    window_pub = meta.get("window_tokens")
    price_row = row.get("price_usd")
    mismatches: list[str] = []
    if not on:
        mismatches.append("id-absent-from-published-surface")
    if retired:
        mismatches.append("id-listed-as-retired")
    if window_row is None:
        mismatches.append("window-unrecorded-in-program-table")
    elif window_pub is not None and int(window_row) != int(window_pub):
        mismatches.append("window-mismatch")
    if price_row is not None and on and meta:
        mismatches.append("price-not-vendor-per-mtok")
    return {
        "model": mid,
        "vendor": row.get("vendor"),
        "table": row.get("table"),
        "on_published_surface": on,
        "retired": retired,
        "window_tokens_program": window_row,
        "window_tokens_published": window_pub,
        "price_usd_program": price_row,
        "mismatches": mismatches,
        "kind": "match" if not mismatches else "stale",
    }


def classify_runtime(obs: dict[str, Any]) -> str:
    if obs.get("loud"):
        return "fail-loudly"
    model_in = str(obs.get("model_in") or "")
    model_out = obs.get("model_out")
    if (
        model_out is not None
        and str(model_out) != model_in
        and not obs.get("dropped")
        and not obs.get("blocked")
    ):
        return "silent-substitute"
    if obs.get("dropped") or obs.get("blocked"):
        return "silent-drop"
    if obs.get("kept") and obs.get("unknown") and obs.get("cost_usd") is not None:
        return "stale-price-estimate"
    return "other"


def is_defect(behaviour: str) -> bool:
    return behaviour in DEFECT_BEHAVIOURS


def planted_runtime_controls() -> dict[str, Any]:
    loud = {
        "model_in": RETIRED_ID,
        "model_out": None,
        "loud": True,
        "dropped": False,
        "blocked": False,
        "kept": False,
        "unknown": True,
        "cost_usd": None,
        "substitute_would_work": False,
        "note": "planted fail-loudly router",
    }
    silent = {
        "model_in": RETIRED_ID,
        "model_out": "gpt-5.6-sol",
        "loud": False,
        "dropped": False,
        "blocked": False,
        "kept": True,
        "unknown": True,
        "cost_usd": 4.0,
        "substitute_would_work": True,
        "note": "planted silent substitute to a working current model",
    }
    b_loud = classify_runtime(loud)
    b_silent = classify_runtime(silent)
    loud_ok = b_loud == "fail-loudly" and not is_defect(b_loud)
    silent_ok = (
        b_silent == "silent-substitute"
        and is_defect(b_silent)
        and silent["substitute_would_work"] is True
    )
    return {
        "loud": {**loud, "behaviour": b_loud, "defect": is_defect(b_loud)},
        "silent": {**silent, "behaviour": b_silent, "defect": is_defect(b_silent)},
        "loud_ok": loud_ok,
        "silent_ok": silent_ok,
    }


def call_cnl_router(model_id: str, cost_usd: float, cap: float) -> dict[str, Any]:
    mod = load_cnl_composer()
    seat = mod._seat(
        "seat.retired",
        "model",
        "implementer",
        model_id,
        "openai",
        ["repo-local"],
        cost_usd,
    )
    known = set(mod.DOWNGRADE) | {
        str(s.get("model"))
        for s in (mod.auto_compose({"id": "x"}).get("roster") or [])
    }
    unknown = model_id not in known
    try:
        fitted, mutations = mod._fit_budget([seat], cap, set())
    except Exception as exc:  # noqa: BLE001 - classify loud vs silent
        obs = {
            "model_in": model_id,
            "model_out": None,
            "loud": True,
            "dropped": False,
            "blocked": False,
            "kept": False,
            "unknown": unknown,
            "cost_usd": None,
            "mutations": [],
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
            "cap": cap,
        }
        obs["behaviour"] = classify_runtime(obs)
        obs["defect"] = is_defect(obs["behaviour"])
        return obs
    if fitted is None:
        obs = {
            "model_in": model_id,
            "model_out": None,
            "loud": False,
            "dropped": True,
            "blocked": True,
            "kept": False,
            "unknown": unknown,
            "cost_usd": None,
            "mutations": list(mutations),
            "cap": cap,
        }
        obs["behaviour"] = classify_runtime(obs)
        obs["defect"] = is_defect(obs["behaviour"])
        return obs
    remaining = fitted[0] if fitted else None
    dropped = remaining is None
    model_out = None if remaining is None else remaining.get("model")
    kept_cost = None if remaining is None else remaining.get("cost_usd")
    obs = {
        "model_in": model_id,
        "model_out": model_out,
        "loud": False,
        "dropped": dropped,
        "blocked": False,
        "kept": remaining is not None,
        "unknown": unknown,
        "cost_usd": kept_cost,
        "mutations": list(mutations),
        "cap": cap,
        "n_seats_out": len(fitted),
    }
    obs["behaviour"] = classify_runtime(obs)
    obs["defect"] = is_defect(obs["behaviour"])
    return obs


def planted_surface_controls(surface: dict[str, Any]) -> dict[str, Any]:
    good = {
        "table": "planted-matching-control",
        "vendor": "anthropic",
        "model": "claude-opus-5",
        "window_tokens": 1000000,
        "price_usd": None,
    }
    bad = {
        "table": "planted-stale-control",
        "vendor": "openai",
        "model": RETIRED_ID,
        "window_tokens": 4097,
        "price_usd": 0.02,
    }
    g = diff_row(good, surface)
    b = diff_row(bad, surface)
    return {
        "matching": g,
        "stale": b,
        "matching_ok": g["kind"] == "match" and g["on_published_surface"],
        "stale_ok": b["kind"] == "stale" and not b["on_published_surface"],
    }


def _verdict(controls_ok: bool, finding_confirmed: bool) -> str:
    if not controls_ok:
        return "NOT-CHECKED"
    return "CONFIRMED" if finding_confirmed else "REFUTED"


def measure() -> dict[str, Any]:
    surface = published_surface()
    tables = program_tables()
    diffs = [diff_row(r, surface) for r in tables]
    n_stale = sum(1 for d in diffs if d["kind"] == "stale")
    n_match = sum(1 for d in diffs if d["kind"] == "match")
    surf_ctrl = planted_surface_controls(surface)
    rt_ctrl = planted_runtime_controls()
    over = call_cnl_router(RETIRED_ID, cost_usd=18.0, cap=5.0)
    under = call_cnl_router(RETIRED_ID, cost_usd=3.0, cap=10.0)
    known = call_cnl_router("opus", cost_usd=18.0, cap=10.0)
    controls_ok = (
        surf_ctrl["matching_ok"]
        and surf_ctrl["stale_ok"]
        and rt_ctrl["loud_ok"]
        and rt_ctrl["silent_ok"]
    )
    catalog_stale = any(
        d["kind"] == "stale" and "CATALOG" in str(d.get("table")) for d in diffs
    )
    cnl_stale = any(
        "CNL-0004" in str(d.get("table")) and d["kind"] == "stale" for d in diffs
    )
    seed_stale = any(
        "seed.py" in str(d.get("table")) and d["kind"] == "stale" for d in diffs
    )
    targets = [
        {
            "id": "CTRL-SURFACE-MATCHING-ROW",
            "verdict": _verdict(controls_ok, False)
            if surf_ctrl["matching_ok"]
            else "NOT-CHECKED",
            "claim": (
                "Planted claude-opus-5 with published 1M window is not flagged "
                "stale (detector can go green)."
            ),
            "detail": surf_ctrl["matching"],
        },
        {
            "id": "CTRL-SURFACE-STALE-ROW",
            "verdict": _verdict(controls_ok, True)
            if surf_ctrl["stale_ok"]
            else "NOT-CHECKED",
            "claim": (
                f"Planted retired id {RETIRED_ID} is flagged stale "
                "(detector can go red)."
            ),
            "detail": surf_ctrl["stale"],
        },
        {
            "id": "CATALOG-ASSIGNED-MODEL-IDS",
            "verdict": _verdict(controls_ok, catalog_stale),
            "claim": (
                "Catalog assigned_model_vendor_role model ids are stale versus "
                "today's published vendor surface (alias or missing window/price)."
            ),
            "n_stale": n_stale,
            "n_match": n_match,
        },
        {
            "id": "CNL-0004-COST-TABLE-IDS",
            "verdict": _verdict(controls_ok, cnl_stale),
            "claim": (
                "CNL-0004 DOWNGRADE / auto_compose model ids and prices are "
                "stale versus today's published vendor surface."
            ),
        },
        {
            "id": "SEED-DEFAULT-ASSIGNMENT",
            "verdict": _verdict(controls_ok, seed_stale),
            "claim": (
                "tools/command-center/seed.py DEFAULTS.assignment.model is stale "
                "versus today's published vendor surface."
            ),
        },
        {
            "id": "CTRL-LOUD-FAIL-NOT-DEFECT",
            "verdict": _verdict(controls_ok, False)
            if rt_ctrl["loud_ok"]
            else "NOT-CHECKED",
            "claim": (
                "A fail-loudly retired-id response is not classified as a defect."
            ),
            "detail": rt_ctrl["loud"],
        },
        {
            "id": "CTRL-SILENT-SUB-IS-DEFECT",
            "verdict": _verdict(controls_ok, True)
            if rt_ctrl["silent_ok"]
            else "NOT-CHECKED",
            "claim": (
                "Silent substitution of a retired id is a defect even when the "
                "substituted model works; degrade-loudly is the contract."
            ),
            "detail": rt_ctrl["silent"],
        },
        {
            "id": "RUNTIME-RETIRED-ID-OVER-BUDGET",
            "verdict": _verdict(controls_ok, bool(over.get("defect"))),
            "claim": (
                f"CNL-0004 _fit_budget({RETIRED_ID!r}, over budget) fails "
                "loudly rather than silent-drop / silent-sub / stale price."
            ),
            "detail": over,
        },
        {
            "id": "RUNTIME-RETIRED-ID-UNDER-BUDGET",
            "verdict": _verdict(controls_ok, bool(under.get("defect"))),
            "claim": (
                f"CNL-0004 _fit_budget({RETIRED_ID!r}, under budget) fails "
                "loudly rather than keeping a cost for an unknown id."
            ),
            "detail": under,
        },
        {
            "id": "RUNTIME-KNOWN-ALIAS-NOT-RETIRED-CASE",
            "verdict": _verdict(controls_ok, False),
            "claim": (
                "Known alias 'opus' is in DOWNGRADE; a budget downgrade to "
                "haiku is not the retired-id case and is recorded separately."
            ),
            "detail": known,
        },
    ]
    # Matching-row control: finding_confirmed=False means REFUTED (the
    # "this row is stale" claim is refuted). Stale-row control: CONFIRMED.
    if controls_ok:
        targets[0]["verdict"] = "REFUTED"
        targets[5]["verdict"] = "REFUTED"
        targets[1]["verdict"] = "CONFIRMED"
        targets[6]["verdict"] = "CONFIRMED"

    verdicts = [t["verdict"] for t in targets]
    if not controls_ok:
        overall = "NOT-CHECKED"
    elif "CONFIRMED" in verdicts and "REFUTED" in verdicts:
        overall = "PARTIAL"
    elif "CONFIRMED" in verdicts:
        overall = "CONFIRMED"
    elif "REFUTED" in verdicts:
        overall = "REFUTED"
    else:
        overall = "NOT-CHECKED"

    tests = [
        {
            "id": "T-SURFACE-MATCHING-CONTROL",
            "result": "PASS" if surf_ctrl["matching_ok"] else "FAIL",
        },
        {
            "id": "T-SURFACE-STALE-CONTROL",
            "result": "PASS" if surf_ctrl["stale_ok"] else "FAIL",
        },
        {
            "id": "T-LOUD-FAIL-NOT-DEFECT",
            "result": "PASS" if rt_ctrl["loud_ok"] else "FAIL",
        },
        {
            "id": "T-SILENT-SUB-IS-DEFECT",
            "result": "PASS" if rt_ctrl["silent_ok"] else "FAIL",
            "note": (
                "silent substitution classified as defect even when substitute works"
            ),
        },
        {
            "id": "T-PROBE1-DIFF-RAN",
            "result": "PASS" if diffs else "FAIL",
        },
        {
            "id": "T-PROBE2-RETIRED-CALL-RAN",
            "result": "PASS" if over.get("behaviour") else "FAIL",
        },
    ]
    negative_controls = [
        {
            "id": "NC-SURFACE-BOTH-STATES",
            "fired_on_bad_state": bool(surf_ctrl["stale_ok"]),
            "silent_on_good_state": bool(surf_ctrl["matching_ok"]),
            "good_state": "claude-opus-5 planted matching row",
            "bad_state": f"{RETIRED_ID} planted stale row",
        },
        {
            "id": "NC-RUNTIME-BOTH-STATES",
            "fired_on_bad_state": bool(rt_ctrl["silent_ok"]),
            "silent_on_good_state": bool(rt_ctrl["loud_ok"]),
            "good_state": "fail-loudly retired-id router",
            "bad_state": "silent-substitute retired-id router (substitute works)",
        },
    ]
    return {
        "controls_ok": controls_ok,
        "overall_verdict": overall,
        "state": "SUCCESS",
        "surface": {
            "fixture_captured_at": surface.get("fixture_captured_at"),
            "n_current_ids": len(surface.get("current_ids") or []),
            "live_fetch_any_ok": surface.get("live_fetch_any_ok"),
            "live_fetches": surface.get("live_fetches"),
            "retired_ids": surface.get("retired_ids"),
            "sources": surface.get("sources"),
        },
        "n_table_rows": len(tables),
        "n_stale": n_stale,
        "n_match": n_match,
        "stale_models": sorted({d["model"] for d in diffs if d["kind"] == "stale"}),
        "matching_models": sorted(
            {d["model"] for d in diffs if d["kind"] == "match"}
        ),
        "diffs": diffs,
        "surface_controls": surf_ctrl,
        "runtime_controls": rt_ctrl,
        "runtime_over": over,
        "runtime_under": under,
        "runtime_known_alias": known,
        "targets": targets,
        "tests": tests,
        "negative_controls": negative_controls,
        "unique_catalog_models": sorted(
            {r["model"] for r in tables if "CATALOG" in str(r.get("table"))}
        ),
    }


def _payload(tag: str, body: dict[str, Any]) -> str:
    return json.dumps({"probe": tag, **body}, sort_keys=True, default=str) + "\n"


def probe1_report(m: dict[str, Any] | None = None) -> str:
    m = m if m is not None else measure()
    body = {
        "name": PROBE1_NAME,
        "n_table_rows": m["n_table_rows"],
        "n_stale": m["n_stale"],
        "n_match": m["n_match"],
        "stale_models": m["stale_models"],
        "matching_models": m["matching_models"],
        "surface": {
            "fixture_captured_at": m["surface"].get("fixture_captured_at"),
            "live_fetch_any_ok": m["surface"].get("live_fetch_any_ok"),
            "live_ok": [
                {"url": f.get("url"), "ok": bool(f.get("ok"))}
                for f in (m["surface"].get("live_fetches") or [])
            ],
            "retired_ids": m["surface"].get("retired_ids"),
            "sources": m["surface"].get("sources"),
        },
        "surface_controls": {
            "matching_ok": m["surface_controls"]["matching_ok"],
            "stale_ok": m["surface_controls"]["stale_ok"],
            "matching_kind": m["surface_controls"]["matching"]["kind"],
            "stale_kind": m["surface_controls"]["stale"]["kind"],
        },
        "unique_catalog_models": m["unique_catalog_models"],
    }
    return (
        PROBE1_NAME
        + "\n"
        + _payload("probe1", body)
        + (
            f"surface_matching_ok={m['surface_controls']['matching_ok']} "
            f"surface_stale_ok={m['surface_controls']['stale_ok']} "
            f"n_stale={m['n_stale']} n_match={m['n_match']}\n"
        )
    )


def probe2_report(m: dict[str, Any] | None = None) -> str:
    m = m if m is not None else measure()
    body = {
        "name": PROBE2_NAME,
        "retired_id": RETIRED_ID,
        "runtime_controls": {
            "loud_ok": m["runtime_controls"]["loud_ok"],
            "silent_ok": m["runtime_controls"]["silent_ok"],
            "loud_behaviour": m["runtime_controls"]["loud"]["behaviour"],
            "silent_behaviour": m["runtime_controls"]["silent"]["behaviour"],
            "silent_substitute_would_work": m["runtime_controls"]["silent"][
                "substitute_would_work"
            ],
        },
        "over_budget": m["runtime_over"],
        "under_budget": m["runtime_under"],
        "known_alias": m["runtime_known_alias"],
    }
    return (
        PROBE2_NAME
        + "\n"
        + _payload("probe2", body)
        + (
            f"loud_ok={m['runtime_controls']['loud_ok']} "
            f"silent_ok={m['runtime_controls']['silent_ok']} "
            f"over_behaviour={m['runtime_over'].get('behaviour')} "
            f"over_defect={m['runtime_over'].get('defect')} "
            f"under_behaviour={m['runtime_under'].get('behaviour')} "
            f"under_defect={m['runtime_under'].get('defect')}\n"
        )
    )


def schema_errors(doc: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema-not-installed"]
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    return [
        f"{list(e.path)}: {e.message}"
        for e in jsonschema.Draft7Validator(schema).iter_errors(doc)
    ]
