"""Product blueprints 5-8: competitive-teardown, market-landscape,
scenario-planning, strategy-war-game.

Each run() is a pure function of its fixture. Numeric ranges on claims come
only from bands.attach() so they cannot drift from the lexicon.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from bands import attach, band_from_strength, quantize_probability
from lint import lint_document

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
PRE = HERE / "presets"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim(
    cid: str,
    text: str,
    *,
    register: str,
    evidence: str,
    band: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": cid,
        "text": text,
        "register": register,
        "evidence_tag": evidence,
    }
    if register == "forward-looking":
        if not band:
            raise ValueError(f"{cid} forward-looking claim missing band")
        row.update(attach(band))
    if extra:
        row.update(extra)
    return row


def _document(
    blueprint_id: str,
    claims: list[dict[str, Any]],
    prose: str,
    derived: dict[str, Any],
) -> dict[str, Any]:
    doc = {
        "blueprint_id": blueprint_id,
        "claims": claims,
        "prose": prose,
        "derived": derived,
    }
    report = lint_document(doc)
    doc["lint"] = report
    if not report["ok"]:
        raise ValueError(
            f"{blueprint_id} produced unlintable output: {report['findings']}"
        )
    return doc


def _prose(claims: list[dict[str, Any]]) -> str:
    bits = []
    for c in claims:
        if c["register"] != "forward-looking":
            continue
        text = str(c["text"]).rstrip(".")
        bits.append(
            f"{text} — {c['confidence_band']} ({c['p_low']}-{c['p_high']}%), "
            f"measured at {c['evidence_tag']}."
        )
    return " ".join(bits)


def _workflow(wf_id: str, stages: list[dict[str, Any]], max_stages: int) -> dict[str, Any]:
    return {
        "id": wf_id,
        "kind": "workflow_blueprint",
        "discovery_only": False,
        "stages": stages,
        "stopping": {"max_stages": max_stages, "on_error": "halt"},
    }


# ---------------------------------------------------------------------------
# competitive-teardown
# ---------------------------------------------------------------------------

def run_competitive_teardown(fixture: dict[str, Any]) -> dict[str, Any]:
    ours = fixture["ours"]
    horizon = int(fixture.get("horizon_quarters", 2))
    claims: list[dict[str, Any]] = []
    derived: list[dict[str, Any]] = []
    n = 0
    for comp in fixture["competitors"]:
        exclusive = sorted(set(comp["features"]) - set(ours["features"]))
        cadence_gap = int(comp["releases_per_year"]) - int(ours["releases_per_year"])
        price_delta = int(ours["price_usd_mo"]) - int(comp["price_usd_mo"])
        cuts = int(comp.get("price_cuts_last_8q") or 0)
        recency = comp.get("exclusive_shipped_quarters_ago")
        derived.append(
            {
                "name": comp["name"],
                "exclusive_features": exclusive,
                "cadence_gap": cadence_gap,
                "price_delta_usd": price_delta,
            }
        )
        slug = comp["name"].lower().replace(" ", "-")
        for feat in exclusive:
            n += 1
            strength = 0.55
            if cadence_gap > 0:
                strength += 0.15
            if isinstance(recency, int) and recency <= 2:
                strength += 0.15
            claims.append(
                _claim(
                    f"ct-keep-{n}",
                    (
                        f"{comp['name']} will still list exclusive feature "
                        f"{feat!r} within the next {horizon} quarters."
                    ),
                    register="forward-looking",
                    evidence=f"{slug}:features",
                    band=band_from_strength(min(0.99, strength)),
                    extra={"competitor": comp["name"], "feature": feat},
                )
            )
        if price_delta > 0 and cuts >= 2:
            n += 1
            claims.append(
                _claim(
                    f"ct-price-{n}",
                    (
                        f"{comp['name']} will still undercut {ours['name']} "
                        f"list price within the next {horizon} quarters."
                    ),
                    register="forward-looking",
                    evidence=f"{slug}:price-history",
                    band="likely",
                    extra={"price_delta_usd": price_delta, "cuts": cuts},
                )
            )
        elif price_delta < 0 and cuts == 0:
            n += 1
            claims.append(
                _claim(
                    f"ct-price-{n}",
                    (
                        f"{comp['name']} will not undercut {ours['name']} "
                        f"list price within the next {horizon} quarters."
                    ),
                    register="forward-looking",
                    evidence=f"{slug}:price-history",
                    band="likely",
                    extra={"price_delta_usd": price_delta, "cuts": cuts},
                )
            )
        n += 1
        claims.append(
            _claim(
                f"ct-hist-{n}",
                (
                    f"{comp['name']} listed {len(comp['features'])} features "
                    f"at ${comp['price_usd_mo']}/mo in the fixture snapshot."
                ),
                register="historical",
                evidence=f"{slug}:snapshot",
            )
        )
    if not any(c["register"] == "forward-looking" for c in claims):
        raise ValueError("competitive-teardown derived no forward-looking claims")
    return _document(
        "competitive-teardown",
        claims,
        _prose(claims),
        {"competitors": derived, "horizon_quarters": horizon},
    )


# ---------------------------------------------------------------------------
# market-landscape
# ---------------------------------------------------------------------------

def _projected_tam(seg: dict[str, Any], horizon_quarters: int) -> float:
    tam = float(seg["tam_usd_m"])
    cagr = float(seg["cagr"])
    years = horizon_quarters / 4.0
    return tam * ((1.0 + cagr) ** years)


def run_market_landscape(fixture: dict[str, Any]) -> dict[str, Any]:
    horizon = int(fixture.get("horizon_quarters", 4))
    rows = []
    for seg in fixture["segments"]:
        proj = _projected_tam(seg, horizon)
        rows.append({**seg, "projected_tam_usd_m": round(proj, 4)})
    rows.sort(key=lambda r: r["projected_tam_usd_m"], reverse=True)
    leader, second = rows[0], rows[1]
    gap_ratio = leader["projected_tam_usd_m"] / max(second["projected_tam_usd_m"], 1e-9)
    if gap_ratio >= 1.30:
        lead_band = "almost-certain"
    elif gap_ratio >= 1.10:
        lead_band = "likely"
    else:
        lead_band = "roughly-even"
    claims = [
        _claim(
            "ml-leader",
            (
                f"Segment {leader['id']!r} will remain the largest TAM "
                f"over the next {horizon} quarters."
            ),
            register="forward-looking",
            evidence=f"segments:{leader['id']}:tam-cagr",
            band=lead_band,
            extra={
                "gap_ratio": round(gap_ratio, 4),
                "leader_proj": leader["projected_tam_usd_m"],
                "second_proj": second["projected_tam_usd_m"],
            },
        )
    ]
    for seg in rows:
        hhi = int(seg["hhi"])
        if hhi >= 1800:
            hhi_band = "likely"
        elif hhi <= 1000:
            hhi_band = "unlikely"
        else:
            hhi_band = None
        if hhi_band:
            claims.append(
                _claim(
                    f"ml-hhi-{seg['id']}",
                    (
                        f"New-entrant share in {seg['id']!r} will stay below 10% "
                        f"over the next {horizon} quarters."
                    ),
                    register="forward-looking",
                    evidence=f"segments:{seg['id']}:hhi",
                    band=hhi_band,
                    extra={"hhi": hhi},
                )
            )
        claims.append(
            _claim(
                f"ml-hist-{seg['id']}",
                (
                    f"Segment {seg['id']} fixture TAM is ${seg['tam_usd_m']}M "
                    f"with CAGR {seg['cagr']} and HHI {seg['hhi']}."
                ),
                register="historical",
                evidence=f"segments:{seg['id']}:snapshot",
            )
        )
    return _document(
        "market-landscape",
        claims,
        _prose(claims),
        {"ranked": rows, "horizon_quarters": horizon, "gap_ratio": round(gap_ratio, 4)},
    )


# ---------------------------------------------------------------------------
# scenario-planning
# ---------------------------------------------------------------------------

def run_scenario_planning(fixture: dict[str, Any]) -> dict[str, Any]:
    drivers = fixture["drivers"]
    max_scenarios = int(fixture.get("max_scenarios") or 8)
    combos: list[list[tuple[str, dict[str, Any]]]] = [[]]
    for drv in drivers:
        nxt: list[list[tuple[str, dict[str, Any]]]] = []
        for prefix in combos:
            for st in drv["states"]:
                nxt.append(prefix + [(drv["id"], st)])
        combos = nxt
    if len(combos) > max_scenarios:
        combos = combos[:max_scenarios]
    claims: list[dict[str, Any]] = []
    scenarios: list[dict[str, Any]] = []
    for combo in combos:
        p = 1.0
        labels: dict[str, str] = {}
        for drv_id, st in combo:
            p *= float(st["p"])
            labels[drv_id] = st["id"]
        band = quantize_probability(p)
        sid = "sc-" + "-".join(st["id"] for _, st in combo)
        scenarios.append({"id": sid, "p": round(p, 6), "band": band, "states": labels})
        state_txt = ", ".join(f"{k}={v}" for k, v in labels.items())
        claims.append(
            _claim(
                sid,
                (
                    f"Scenario ({state_txt}) will be the operating environment "
                    f"over the planning horizon."
                ),
                register="forward-looking",
                evidence="drivers:" + ",".join(labels),
                band=band,
                extra={"p_joint": round(p, 6), "states": labels},
            )
        )
    for drv in drivers:
        total_p = round(sum(float(s["p"]) for s in drv["states"]), 6)
        claims.append(
            _claim(
                f"sc-hist-{drv['id']}",
                f"Driver {drv['id']} prior masses sum to {total_p}.",
                register="historical",
                evidence=f"drivers:{drv['id']}:priors",
            )
        )
    return _document(
        "scenario-planning",
        claims,
        _prose(claims),
        {"scenarios": scenarios, "combo_count": len(combos)},
    )


# ---------------------------------------------------------------------------
# strategy-war-game
# ---------------------------------------------------------------------------

def run_strategy_war_game(fixture: dict[str, Any]) -> dict[str, Any]:
    moves = list(fixture["our_moves"])
    replies = list(fixture["their_replies"])
    payoffs = fixture["payoffs"]
    freq = fixture["reply_frequencies"]
    ev: dict[str, float] = {}
    for mv in moves:
        total = 0.0
        for rp in replies:
            total += float(freq[rp]) * float(payoffs[mv][rp])
        ev[mv] = total
    ranked = sorted(ev.items(), key=lambda kv: kv[1], reverse=True)
    best, second = ranked[0], ranked[1]
    span = max(ev.values()) - min(ev.values())
    gap = best[1] - second[1]
    strength = 0.40 if span <= 0 else min(0.99, 0.40 + (gap / span) * 0.55)
    top_reply = max(freq.items(), key=lambda kv: kv[1])
    claims = [
        _claim(
            "wg-best",
            (
                f"Move {best[0]!r} will yield a higher expected payoff than "
                f"{second[0]!r} against the recorded reply mix."
            ),
            register="forward-looking",
            evidence="payoff-matrix:ev",
            band=band_from_strength(strength),
            extra={
                "best_ev": round(best[1], 4),
                "second_ev": round(second[1], 4),
                "gap": round(gap, 4),
                "span": round(span, 4),
                "strength": round(strength, 4),
            },
        ),
        _claim(
            "wg-reply",
            (
                f"Opponent reply {top_reply[0]!r} will remain the modal response "
                f"over the next round."
            ),
            register="forward-looking",
            evidence="reply-frequencies:modal",
            band=quantize_probability(float(top_reply[1])),
            extra={"modal_p": top_reply[1]},
        ),
    ]
    for mv, val in ranked:
        claims.append(
            _claim(
                f"wg-hist-{mv}",
                f"Recorded expected payoff for {mv} is {val:.4f}.",
                register="historical",
                evidence="payoff-matrix:snapshot",
            )
        )
    return _document(
        "strategy-war-game",
        claims,
        _prose(claims),
        {
            "expected_value": {k: round(v, 4) for k, v in ev.items()},
            "ranking": [m for m, _ in ranked],
        },
    )


def _example(name: str, runner: Callable[[dict[str, Any]], dict[str, Any]]):
    def _run() -> dict[str, Any]:
        return runner(_load(FIX / f"{name}.json"))

    return _run


def _smoke(name: str, runner: Callable[[dict[str, Any]], dict[str, Any]]):
    def _run() -> dict[str, Any]:
        doc = runner(_load(FIX / f"{name}.json"))
        fwd = [c for c in doc["claims"] if c["register"] == "forward-looking"]
        if len(fwd) < 1:
            raise AssertionError(f"{name} smoke: no forward-looking claims")
        if not doc["lint"]["ok"]:
            raise AssertionError(f"{name} smoke: lint failed {doc['lint']}")
        return {"ok": True, "forward_claims": len(fwd), "blueprint": name}

    return _run


def _bp(
    slug: str,
    wf_id: str,
    stages: list[dict[str, Any]],
    max_stages: int,
    runner: Callable[[dict[str, Any]], dict[str, Any]],
    caps: set[str],
    stopping_note: str,
) -> dict[str, Any]:
    wf = _workflow(wf_id, stages, max_stages)
    preset_path = PRE / f"{slug}.json"
    preset = _load(preset_path) if preset_path.is_file() else {"fixture": f"fixtures/{slug}.json"}
    return {
        "id": slug,
        "typed_workflow": wf,
        "runnable_example": _example(slug, runner),
        "preset": preset,
        "stopping_rules": {**wf["stopping"], "note": stopping_note},
        "smoke_test": _smoke(slug, runner),
        "capability_vector": frozenset(caps),
        "run": runner,
    }


def all_blueprints() -> list[dict[str, Any]]:
    return [
        _bp(
            "competitive-teardown",
            "wf.product.competitive-teardown",
            [
                {"id": "ingest", "kind": "read-fixture", "inputs": ["snapshot"], "outputs": ["matrix"]},
                {"id": "diff", "kind": "feature-price-diff", "inputs": ["matrix"], "outputs": ["gaps"]},
                {"id": "forecast", "kind": "banded-claim-emit", "inputs": ["gaps"], "outputs": ["claims.json"]},
                {"id": "lint", "kind": "output-lint", "inputs": ["claims.json"], "outputs": ["lint-report"]},
            ],
            4,
            run_competitive_teardown,
            {
                "competitor-feature-diff",
                "price-trajectory-forecast",
                "banded-claims",
                "evidence-tags",
            },
            "Halt if lint rejects any forward-looking claim; max 4 stages.",
        ),
        _bp(
            "market-landscape",
            "wf.product.market-landscape",
            [
                {"id": "ingest", "kind": "read-fixture", "inputs": ["segment-table"], "outputs": ["segments"]},
                {"id": "project", "kind": "tam-cagr-project", "inputs": ["segments"], "outputs": ["ranked-tam"]},
                {"id": "forecast", "kind": "banded-claim-emit", "inputs": ["ranked-tam"], "outputs": ["claims.json"]},
                {"id": "lint", "kind": "output-lint", "inputs": ["claims.json"], "outputs": ["lint-report"]},
            ],
            4,
            run_market_landscape,
            {"segment-tam-rank", "concentration-hhi", "banded-claims", "evidence-tags"},
            "Halt if lint rejects; projection uses fixture CAGR only.",
        ),
        _bp(
            "scenario-planning",
            "wf.product.scenario-planning",
            [
                {"id": "ingest", "kind": "read-fixture", "inputs": ["drivers"], "outputs": ["driver-states"]},
                {"id": "combinatorics", "kind": "cartesian-cap", "inputs": ["driver-states"], "outputs": ["scenarios"]},
                {"id": "quantize", "kind": "probability-to-band", "inputs": ["scenarios"], "outputs": ["claims.json"]},
                {"id": "lint", "kind": "output-lint", "inputs": ["claims.json"], "outputs": ["lint-report"]},
            ],
            4,
            run_scenario_planning,
            {
                "driver-cartesian",
                "probability-product",
                "band-quantize",
                "banded-claims",
                "evidence-tags",
            },
            "Cap cartesian expansion via max_scenarios; halt on lint reject.",
        ),
        _bp(
            "strategy-war-game",
            "wf.product.strategy-war-game",
            [
                {"id": "ingest", "kind": "read-fixture", "inputs": ["payoff-matrix"], "outputs": ["matrix"]},
                {"id": "expect", "kind": "expected-value", "inputs": ["matrix"], "outputs": ["move-ev"]},
                {"id": "forecast", "kind": "banded-claim-emit", "inputs": ["move-ev"], "outputs": ["claims.json"]},
                {"id": "lint", "kind": "output-lint", "inputs": ["claims.json"], "outputs": ["lint-report"]},
            ],
            4,
            run_strategy_war_game,
            {
                "payoff-matrix",
                "expected-value-move",
                "counter-move-forecast",
                "banded-claims",
                "evidence-tags",
            },
            "Halt if payoff cells missing; do not invent replies.",
        ),
    ]


def run_all() -> dict[str, dict[str, Any]]:
    return {bp["id"]: bp["runnable_example"]() for bp in all_blueprints()}
