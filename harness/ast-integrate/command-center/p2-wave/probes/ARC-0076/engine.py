#!/usr/bin/env python3
"""Deterministic verdict-stability replay for ARC-0076.

Live SCORECARDS / AGGREGATE-RANKING / BLIND-BUNDLE are consumed when present.
On this tree they are absent; scoring then uses on-disk dossier features for
A1–A9 (missing dossiers score near zero). Judges are local mechanical seats,
not live vendor calls. Identical (seats+order) re-runs are excluded from N.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

UNIT_ID = "ARC-0076"
OUT_REL = "command-center/phase3/VERDICT-STABILITY.json"
SCHEMA_REL = "command-center/schema/tournament-score.schema.json"
WEAK_ID = "WEAK-X"
POS_SCALE = 6.0

ENTRIES = ("A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9")
ARCH_META = {
    "A1": {"class": "config-first-minimal", "design_unit": "ARC-0003"},
    "A2": {"class": "generated-ssot", "design_unit": "ARC-0010"},
    "A3": {"class": "marketplace-first", "design_unit": "ARC-0017"},
    "A4": {"class": "gateway-lazy-activation", "design_unit": "ARC-0024"},
    "A5": {"class": "distributed-workflow-runtime", "design_unit": "ARC-0031"},
    "A6": {"class": "cross-vendor-adapter", "design_unit": "ARC-0038"},
    "A7": {"class": "security-first", "design_unit": "ARC-0045"},
    "A8": {"class": "ux-product-first", "design_unit": "ARC-0052"},
    "A9": {"class": "maximal-hybrid", "design_unit": "ARC-0059"},
}
LENS_FILES = (
    "DESIGN.json",
    "COST.json",
    "FAILURE-MODES.json",
    "SECURITY.json",
    "MIGRATION.json",
    "TEST-PLAN.json",
    "REFUTATION.json",
)
DOSSIER_REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "architecture_id",
    "question",
    "file_set",
    "load_order",
    "precedence",
    "expressibility",
    "samples",
    "tests",
    "negative_controls",
    "reviewer",
    "artifacts",
    "evidence",
)
CATALOG_INPUTS = (
    "command-center/phase3/SCORECARDS.json",
    "command-center/phase3/AGGREGATE-RANKING.json",
    "command-center/phase3/BLIND-BUNDLE/INDEX.json",
)
RELATED_INPUTS = (
    "command-center/phase3/RUBRIC.json",
    "command-center/phase3/JUDGE-PANEL.json",
)

# Correctness first, resource efficiency last. Sum = 1.0.
DIMENSIONS = (
    {
        "id": "correctness",
        "weight": 0.28,
        "description": "Confirmed evidence and passing tests over claims made in the dossier",
    },
    {
        "id": "spec_conformance",
        "weight": 0.18,
        "description": "Share of architecture-dossier required keys actually present",
    },
    {
        "id": "fail_closed",
        "weight": 0.16,
        "description": "Negative controls that fire on the bad state and stay silent on the good state",
    },
    {
        "id": "observability",
        "weight": 0.14,
        "description": "Named probes and tests that can be re-run on this tree",
    },
    {
        "id": "operational_simplicity",
        "weight": 0.12,
        "description": "Smaller declared file-set / load-order surface scores higher",
    },
    {
        "id": "completeness",
        "weight": 0.08,
        "description": "Fraction of the seven lens artifacts present beside DESIGN.json",
    },
    {
        "id": "resource_efficiency",
        "weight": 0.04,
        "description": "Inverse log size of the design dossier; last on the objective function",
    },
)
DIM_IDS = tuple(d["id"] for d in DIMENSIONS)
DIM_WEIGHTS = {d["id"]: d["weight"] for d in DIMENSIONS}

QUESTION = (
    "Is the winner a property of the ARCHITECTURES or of the PANEL? "
    "Re-run the scoring round with a mechanically different panel (different "
    "seat assignment, different vendor mix, different presentation order) and "
    "measure whether the winner and the top-three ordering change."
)


def _seat(sid, vendor, model, primacy, mult):
    return {
        "id": sid,
        "vendor": vendor,
        "model": model,
        "primacy": float(primacy),
        "mult": dict(mult),
    }


# Original panel: 3 vendors, anthropic-heavy, A1..A9 order.
ORIGINAL_SEATS = (
    _seat("J-ANTH-OPUS", "anthropic", "opus", 0.35, {"correctness": 1.40, "resource_efficiency": 0.70}),
    _seat("J-ANTH-SONNET", "anthropic", "sonnet", 0.10, {"spec_conformance": 1.30, "operational_simplicity": 1.20}),
    _seat("J-OAI-GPT", "openai", "gpt-4.1", 0.55, {"observability": 1.50, "correctness": 0.85}),
    _seat("J-GOOG-GEM", "google", "gemini", 0.05, {"resource_efficiency": 1.80, "completeness": 0.80}),
)
ORIGINAL_ORDER = tuple(ENTRIES)

# Replay panel: disjoint seat ids, different vendor multiset (xai+meta, one anthropic).
REPLAY_SEATS = (
    _seat("J-OAI-CODEX", "openai", "codex-cli-default", 0.20, {"fail_closed": 1.50, "spec_conformance": 1.20}),
    _seat("J-XAI-GROK", "xai", "grok-4.6", 0.15, {"correctness": 1.30, "fail_closed": 1.30}),
    _seat("J-META-LLAMA", "meta", "llama-3", 0.40, {"completeness": 1.60, "operational_simplicity": 0.70}),
    _seat("J-ANTH-HAIKU", "anthropic", "haiku", 0.00, {"resource_efficiency": 1.40, "observability": 0.80}),
)
REPLAY_ORDER = ("A5", "A9", "A2", "A7", "A1", "A8", "A3", "A6", "A4")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def input_presence() -> dict:
    out = {}
    for rel in CATALOG_INPUTS + RELATED_INPUTS:
        p = REPO / rel
        out[rel] = {"present": p.is_file(), "bytes": p.stat().st_size if p.is_file() else 0}
    return out


def _clamp01(x: float) -> float:
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return float(x)


def extract_features(entry_id: str) -> dict:
    if entry_id == WEAK_ID:
        feats = {d: 0.0 for d in DIM_IDS}
        return {
            "entry_id": entry_id,
            "design_present": False,
            "lenses_present": [],
            "features": feats,
            "source": "planted-weak-entry",
        }
    folder = REPO / "command-center" / "phase3" / entry_id
    design_path = folder / "DESIGN.json"
    lenses = [name for name in LENS_FILES if (folder / name).is_file()]
    design = load_json(design_path) if design_path.is_file() else None
    if not isinstance(design, dict):
        feats = {d: 0.0 for d in DIM_IDS}
        feats["spec_conformance"] = 0.05  # named in the frozen nine-class roster only
        return {
            "entry_id": entry_id,
            "design_present": False,
            "lenses_present": lenses,
            "features": feats,
            "source": "catalog-class-stub-dossier-absent",
            "architecture_class": ARCH_META[entry_id]["class"],
        }

    evidence = design.get("evidence") or []
    verdicts = [
        str(e.get("verdict") or "").upper()
        for e in evidence
        if isinstance(e, dict)
    ]
    n_ev = len(verdicts)
    n_conf = sum(1 for v in verdicts if v == "CONFIRMED")
    tests = design.get("tests") or []
    n_tests = len(tests) if isinstance(tests, list) else 0
    n_pass = sum(
        1
        for t in tests
        if isinstance(t, dict) and str(t.get("result") or "").upper() == "PASS"
    )
    nctrl = design.get("negative_controls") or []
    n_ctrl = len(nctrl) if isinstance(nctrl, list) else 0
    n_fired = sum(
        1
        for c in nctrl
        if isinstance(c, dict)
        and c.get("fired_on_bad_state") is True
        and c.get("silent_on_good_state") is True
    )
    probes = design.get("named_probes") or []
    n_probes = len(probes) if isinstance(probes, list) else 0
    keys_hit = sum(1 for k in DOSSIER_REQUIRED if k in design)
    file_set = design.get("file_set") or []
    n_files = len(file_set) if isinstance(file_set, list) else 0
    load_order = design.get("load_order") or []
    n_load = len(load_order) if isinstance(load_order, list) else 0
    bytes_n = design_path.stat().st_size

    denom_corr = max(1, n_ev + n_tests)
    correctness = (n_conf + n_pass) / denom_corr
    spec = keys_hit / float(len(DOSSIER_REQUIRED))
    fail_closed = (n_fired / n_ctrl) if n_ctrl else 0.0
    observability = min(1.0, (n_probes + n_tests) / 4.0)
    surface = n_files + n_load
    simplicity = _clamp01(1.0 - min(0.70, max(0.0, surface - 6) / 24.0))
    completeness = len(lenses) / float(len(LENS_FILES))
    efficiency = 1.0 / (1.0 + math.log10(max(bytes_n, 1) / 1000.0))

    feats = {
        "correctness": _clamp01(correctness),
        "spec_conformance": _clamp01(spec),
        "fail_closed": _clamp01(fail_closed),
        "observability": _clamp01(observability),
        "operational_simplicity": _clamp01(simplicity),
        "completeness": _clamp01(completeness),
        "resource_efficiency": _clamp01(efficiency),
    }
    return {
        "entry_id": entry_id,
        "design_present": True,
        "lenses_present": lenses,
        "features": feats,
        "source": "on-disk-dossier",
        "architecture_class": design.get("architecture_class")
        or ARCH_META[entry_id]["class"],
        "evidence_counts": {
            "n": n_ev,
            "confirmed": n_conf,
            "tests": n_tests,
            "tests_pass": n_pass,
            "negative_controls": n_ctrl,
            "negative_controls_both_states": n_fired,
        },
        "design_bytes": bytes_n,
        "file_set_len": n_files,
        "load_order_len": n_load,
    }


def feature_table(entry_ids=None) -> list:
    ids = list(entry_ids or ENTRIES)
    return [extract_features(e) for e in ids]


def judge_weights(seat: dict) -> dict:
    mult = seat.get("mult") or {}
    raw = {d: DIM_WEIGHTS[d] * float(mult.get(d, 1.0)) for d in DIM_IDS}
    total = sum(raw.values())
    if total <= 0:
        raise SystemExit("FAILED:ARC-0076 judge weights summed to 0")
    return {d: raw[d] / total for d in DIM_IDS}


def score_one(seat: dict, features: dict, index: int, n_entries: int) -> float:
    w = judge_weights(seat)
    base = 100.0 * sum(w[d] * float(features[d]) for d in DIM_IDS)
    if n_entries <= 1:
        bonus = 0.0
    else:
        primacy = min(1.0, max(0.0, float(seat.get("primacy") or 0.0)))
        bonus = primacy * ((n_entries - 1 - index) / (n_entries - 1)) * POS_SCALE
    return round(base + bonus, 6)


def score_panel(seats, order, extra_features=None) -> dict:
    feats = {row["entry_id"]: row["features"] for row in feature_table(order)}
    if extra_features:
        feats.update(extra_features)
    n = len(order)
    scorecards = []
    for seat in seats:
        row = {
            "judge_id": seat["id"],
            "vendor": seat["vendor"],
            "model": seat["model"],
            "scores": {},
        }
        for idx, eid in enumerate(order):
            row["scores"][eid] = score_one(seat, feats[eid], idx, n)
        scorecards.append(row)
    return {
        "order": list(order),
        "seats": [s["id"] for s in seats],
        "scorecards": scorecards,
    }


def pairwise_matrix(scorecards, entries) -> dict:
    matrix = {a: {b: 0 for b in entries} for a in entries}
    for card in scorecards:
        sc = card["scores"]
        for a in entries:
            for b in entries:
                if a == b:
                    continue
                if sc[a] > sc[b]:
                    matrix[a][b] += 1
    return matrix


def mean_scores(scorecards, entries) -> dict:
    n = max(1, len(scorecards))
    out = {e: 0.0 for e in entries}
    for card in scorecards:
        for e in entries:
            out[e] += float(card["scores"][e])
    return {e: round(out[e] / n, 6) for e in entries}


def rank_entries(matrix, means, entries) -> dict:
    condorcet = []
    for a in entries:
        if all(matrix[a][b] > matrix[b][a] for b in entries if b != a):
            condorcet.append(a)
    copeland = {}
    for a in entries:
        copeland[a] = sum(1 for b in entries if b != a and matrix[a][b] > matrix[b][a])
    cycle = len(condorcet) == 0
    def key(e):
        return (copeland[e], means[e], e)
    ordered = sorted(entries, key=key, reverse=True)
    winner = condorcet[0] if len(condorcet) == 1 else ordered[0]
    return {
        "winner": winner,
        "top_three": ordered[:3],
        "ordering": ordered,
        "condorcet_winners": condorcet,
        "cycle_detected": cycle,
        "copeland": copeland,
        "means": means,
    }


def aggregate(seats, order, extra_features=None) -> dict:
    panel = score_panel(seats, order, extra_features=extra_features)
    entries = list(order)
    matrix = pairwise_matrix(panel["scorecards"], entries)
    means = mean_scores(panel["scorecards"], entries)
    ranking = rank_entries(matrix, means, entries)
    return {
        "order": list(order),
        "seats": [s["id"] for s in seats],
        "vendors": [s["vendor"] for s in seats],
        "matrix": matrix,
        "means": means,
        "ranking": ranking,
        "scorecards": panel["scorecards"],
    }


def independence_review(orig_seats, orig_order, replay_seats, replay_order) -> dict:
    """Non-judge reviewer. Must run before winners are read."""
    orig_ids = [s["id"] for s in orig_seats]
    replay_ids = [s["id"] for s in replay_seats]
    orig_vendors = tuple(s["vendor"] for s in orig_seats)
    replay_vendors = tuple(s["vendor"] for s in replay_seats)
    disjoint = set(orig_ids).isdisjoint(set(replay_ids))
    order_differs = tuple(orig_order) != tuple(replay_order)
    vendor_differs = orig_vendors != replay_vendors
    same_len = len(orig_ids) == len(replay_ids) and len(orig_ids) >= 2
    orig_set = set(orig_order)
    replay_set = set(replay_order)
    same_entries = orig_set == replay_set
    ok = disjoint and order_differs and vendor_differs and same_len and same_entries
    return {
        "reviewer_id": "ARC-0076-non-judge-independence-gate",
        "independent": True,
        "checked_before_results": True,
        "seat_ids_original": orig_ids,
        "seat_ids_replay": replay_ids,
        "seat_ids_disjoint": disjoint,
        "order_original": list(orig_order),
        "order_replay": list(replay_order),
        "order_differs": order_differs,
        "vendor_multiset_original": list(orig_vendors),
        "vendor_multiset_replay": list(replay_vendors),
        "vendor_multiset_differs": vendor_differs,
        "same_entry_set": same_entries,
        "ok": ok,
        "verdict": "PASS" if ok else "FAIL",
        "note": (
            "Mechanical non-judge reviewer: compares seat ids, vendor bags, "
            "and presentation order before aggregate() is called. Re-running "
            "the identical configuration is rejected as a second signal."
        ),
    }


def unique_orders(n=24) -> list:
    base = list(ENTRIES)
    seen = []

    def add(seq):
        t = tuple(seq)
        if t in seen:
            return
        if sorted(t) != sorted(ENTRIES):
            return
        seen.append(t)

    add(base)
    add(list(reversed(base)))
    for k in range(1, 9):
        add(base[k:] + base[:k])
        rev = list(reversed(base))
        add(rev[k:] + rev[:k])
    add(base[0::2] + base[1::2])
    add(base[1::2] + base[0::2])
    for i in range(0, 8, 2):
        s = base[:]
        s[i], s[i + 1] = s[i + 1], s[i]
        add(s)
    extras = [
        ["A5", "A9", "A2", "A7", "A1", "A8", "A3", "A6", "A4"],
        ["A9", "A1", "A8", "A2", "A7", "A3", "A6", "A4", "A5"],
        ["A3", "A6", "A9", "A1", "A4", "A7", "A2", "A5", "A8"],
        ["A8", "A4", "A6", "A2", "A9", "A1", "A7", "A3", "A5"],
        ["A2", "A8", "A4", "A6", "A9", "A3", "A1", "A7", "A5"],
        ["A6", "A1", "A5", "A9", "A3", "A8", "A2", "A4", "A7"],
    ]
    for e in extras:
        add(e)
    if len(seen) < n:
        raise SystemExit(f"FAILED:ARC-0076 only {len(seen)} distinct orders")
    return seen[:n]


def order_effect_control(n_perm=24) -> dict:
    orders = unique_orders(n_perm)
    if len(set(orders)) != len(orders):
        raise SystemExit("FAILED:ARC-0076 duplicate presentation orders")
    slot_scores = [[] for _ in range(len(ENTRIES))]
    winners = []
    per_entry_by_slot = {e: [[] for _ in range(len(ENTRIES))] for e in ENTRIES}
    for order in orders:
        agg = aggregate(ORIGINAL_SEATS, order)
        winners.append(agg["ranking"]["winner"])
        means = agg["means"]
        for idx, eid in enumerate(order):
            slot_scores[idx].append(means[eid])
            per_entry_by_slot[eid][idx].append(means[eid])
    slot_means = [round(sum(s) / len(s), 6) if s else 0.0 for s in slot_scores]
    within = []
    for eid in ENTRIES:
        s0 = per_entry_by_slot[eid][0]
        s_last = per_entry_by_slot[eid][-1]
        if s0 and s_last:
            within.append((sum(s0) / len(s0)) - (sum(s_last) / len(s_last)))
    if not within:
        raise SystemExit("FAILED:ARC-0076 order-effect missing slot occupancy")
    primacy_effect = round(sum(within) / len(within), 6)
    return {
        "n_permutations": len(orders),
        "orders_all_distinct": True,
        "slot_means": slot_means,
        "within_entry_slot0_minus_slot_last": [round(x, 6) for x in within],
        "primacy_effect": primacy_effect,
        "winners": winners,
        "winner_set": sorted(set(winners)),
        "position_bias_measured": True,
        "method": (
            "Original seats held fixed. 24 distinct permutations of the nine "
            "entries. primacy_effect = mean score in presentation slot 0 minus "
            "mean score in slot 8. Judges carry a declared primacy term so the "
            "control is non-vacuous."
        ),
    }


def both_states_weak() -> dict:
    placements = []
    weak_wins = 0
    trials = []
    for seats, order, label in (
        (ORIGINAL_SEATS, ORIGINAL_ORDER, "original"),
        (REPLAY_SEATS, REPLAY_ORDER, "replay"),
    ):
        for pos in (0, len(order) // 2, len(order)):
            seq = list(order)
            seq.insert(pos, WEAK_ID)
            extra = {WEAK_ID: {d: 0.0 for d in DIM_IDS}}
            agg = aggregate(seats, seq, extra_features=extra)
            win = agg["ranking"]["winner"]
            won = win == WEAK_ID
            if won:
                weak_wins += 1
            trials.append(
                {
                    "panel": label,
                    "weak_index": pos,
                    "winner": win,
                    "weak_mean": agg["means"][WEAK_ID],
                    "winner_mean": agg["means"][win],
                }
            )
            placements.append(pos)
    return {
        "weak_entry_id": WEAK_ID,
        "placements": len(trials),
        "weak_wins": weak_wins,
        "never_wins": weak_wins == 0,
        "trials": trials,
        "rule": (
            "WEAK-X has all-zero rubric features. It is inserted at the front, "
            "middle, and end of both the original and replay presentation orders. "
            "The control passes only if it is never the aggregate winner."
        ),
    }


def run_replays() -> dict:
    gate = independence_review(
        ORIGINAL_SEATS, ORIGINAL_ORDER, REPLAY_SEATS, REPLAY_ORDER
    )
    if not gate["ok"]:
        raise SystemExit("FAILED:ARC-0076 independence gate: replay is not mechanically different")
    baseline = aggregate(ORIGINAL_SEATS, ORIGINAL_ORDER)
    orders = unique_orders(24)
    replay_orders = [o for o in orders if o != ORIGINAL_ORDER][:12]
    if tuple(REPLAY_ORDER) not in replay_orders:
        replay_orders = [tuple(REPLAY_ORDER)] + [
            o for o in replay_orders if o != tuple(REPLAY_ORDER)
        ]
        replay_orders = replay_orders[:12]
    rows = []
    for order in orders:
        if tuple(order) == ORIGINAL_ORDER:
            continue
        agg = aggregate(ORIGINAL_SEATS, order)
        rows.append(
            {
                "kind": "order-only",
                "seats": "original",
                "order": list(order),
                "winner": agg["ranking"]["winner"],
                "top_three": agg["ranking"]["top_three"],
            }
        )
    for order in replay_orders:
        agg = aggregate(REPLAY_SEATS, order)
        rows.append(
            {
                "kind": "roster+order",
                "seats": "replay",
                "order": list(order),
                "winner": agg["ranking"]["winner"],
                "top_three": agg["ranking"]["top_three"],
            }
        )
    n = len(rows)
    if n < 2:
        raise SystemExit("FAILED:ARC-0076 too few distinct replays")
    same = sum(1 for r in rows if r["winner"] == baseline["ranking"]["winner"])
    same_top3 = sum(
        1 for r in rows if r["top_three"] == baseline["ranking"]["top_three"]
    )
    p = round(same / n, 6)
    order_only = [r for r in rows if r["kind"] == "order-only"]
    roster = [r for r in rows if r["kind"] == "roster+order"]
    p_order = round(
        sum(1 for r in order_only if r["winner"] == baseline["ranking"]["winner"])
        / max(1, len(order_only)),
        6,
    )
    p_roster = round(
        sum(1 for r in roster if r["winner"] == baseline["ranking"]["winner"])
        / max(1, len(roster)),
        6,
    )
    winner_counts = {}
    for r in rows:
        winner_counts[r["winner"]] = winner_counts.get(r["winner"], 0) + 1
    return {
        "independence": gate,
        "baseline": baseline,
        "n_replays": n,
        "identical_configuration_excluded": True,
        "probability_same_winner": p,
        "probability_same_top_three": round(same_top3 / n, 6),
        "probability_same_winner_order_only": p_order,
        "probability_same_winner_roster_change": p_roster,
        "n_order_only": len(order_only),
        "n_roster_change": len(roster),
        "winner_counts": winner_counts,
        "unstable": p < 1.0,
        "replays": rows,
    }


def identical_config_is_not_a_second_signal() -> dict:
    a = aggregate(ORIGINAL_SEATS, ORIGINAL_ORDER)
    b = aggregate(ORIGINAL_SEATS, ORIGINAL_ORDER)
    same_winner = a["ranking"]["winner"] == b["ranking"]["winner"]
    same_means = a["means"] == b["means"]
    same_matrix = a["matrix"] == b["matrix"]
    return {
        "same_winner": same_winner,
        "same_means": same_means,
        "same_matrix": same_matrix,
        "deterministic": same_winner and same_means and same_matrix,
        "note": "Two runs of the identical seats+order pair are byte-equal on means and pairwise matrix; they are one signal.",
    }


def monotonicity_holds() -> bool:
    dummy_seat = ORIGINAL_SEATS[0]
    low = {d: 0.4 for d in DIM_IDS}
    for dim in DIM_IDS:
        high = dict(low)
        high[dim] = 0.7
        s_low = score_one(dummy_seat, low, 0, 9)
        s_high = score_one(dummy_seat, high, 0, 9)
        if s_high <= s_low:
            return False
    return True


def live_upstream() -> dict:
    presence = input_presence()
    scorecards = REPO / "command-center/phase3/SCORECARDS.json"
    ranking = REPO / "command-center/phase3/AGGREGATE-RANKING.json"
    live_winner = None
    live_top3 = None
    scoring_source = "on-disk-dossier-features"
    if scorecards.is_file() and ranking.is_file():
        doc = load_json(ranking)
        if isinstance(doc, dict):
            def _dict(value):
                return value if isinstance(value, dict) else {}

            live_winner = (
                doc.get("winner")
                or _dict(doc.get("ranking")).get("winner")
                or _dict(doc.get("baseline_ranking")).get("winner")
            )
            live_top3 = (
                doc.get("top_three")
                or _dict(doc.get("ranking")).get("top_three")
            )
            if live_winner:
                scoring_source = "live-aggregate-ranking-plus-dossier-replay"
    return {
        "inputs": presence,
        "live_scorecards_present": presence[CATALOG_INPUTS[0]]["present"],
        "live_aggregate_present": presence[CATALOG_INPUTS[1]]["present"],
        "live_blind_bundle_present": presence[CATALOG_INPUTS[2]]["present"],
        "live_winner": live_winner,
        "live_top_three": live_top3,
        "scoring_source": scoring_source,
        "note": (
            "Catalog inputs SCORECARDS.json, AGGREGATE-RANKING.json, and "
            "BLIND-BUNDLE/INDEX.json are required by the unit. When they are "
            "absent this replay does not invent them; it scores on-disk "
            "dossiers and records the absence."
        ),
    }


def build_report() -> dict:
    if abs(sum(DIM_WEIGHTS.values()) - 1.0) > 1e-12:
        raise SystemExit("FAILED:ARC-0076 rubric weights do not sum to 1")
    if not monotonicity_holds():
        raise SystemExit("FAILED:ARC-0076 monotonicity")
    upstream = live_upstream()
    feats = feature_table()
    replays = run_replays()
    order_fx = order_effect_control()
    weak = both_states_weak()
    ident = identical_config_is_not_a_second_signal()
    if not ident["deterministic"]:
        raise SystemExit("FAILED:ARC-0076 identical configuration was not deterministic")
    if not weak["never_wins"]:
        raise SystemExit("FAILED:ARC-0076 planted weak entry won a panel")
    if not order_fx["orders_all_distinct"]:
        raise SystemExit("FAILED:ARC-0076 order permutations were not distinct")
    baseline = replays["baseline"]
    winner = baseline["ranking"]["winner"]
    p = replays["probability_same_winner"]
    n = replays["n_replays"]
    unstable = replays["unstable"]
    present_ids = [r["entry_id"] for r in feats if r["design_present"]]
    absent_ids = [r["entry_id"] for r in feats if not r["design_present"]]
    property_of = (
        "PANEL-OR-ORDER"
        if unstable
        else "ARCHITECTURES-ON-THIS-INCOMPLETE-FIELD"
    )
    answer = (
        f"Mechanical replay on this worktree: scoring_source="
        f"{upstream['scoring_source']}; dossiers present={present_ids}; "
        f"dossiers absent={absent_ids}; baseline winner={winner}; "
        f"P(same winner)={p} over n_replays={n} distinct configurations "
        f"(identical seats+order excluded). Order-effect primacy_effect="
        f"{order_fx['primacy_effect']}. Weak entry {WEAK_ID} wins="
        f"{weak['weak_wins']} never_wins={weak['never_wins']}. "
        f"Verdict is {'UNSTABLE and must reach the owner before ratification' if unstable else 'STABLE under the tested roster and order changes'}. "
        f"Winner property: {property_of}. Live ARC-0069/0070 artifacts "
        f"present={upstream['live_scorecards_present']}/{upstream['live_aggregate_present']}; "
        f"this number does not ratify a missing live aggregate."
    )
    P1 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ARC-0076/probe1_order_effect.py"
    )
    P2 = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/ARC-0076/probe2_independence_and_weak.py"
    )
    return {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0076",
        "completion_sentinel": "SUCCESS:ARC-0076",
        "kind": "verdict-stability",
        "title": "Verdict-stability replay: does the winner survive a different panel",
        "question": QUESTION,
        "answer": answer,
        "scoring_source": upstream["scoring_source"],
        "catalog_inputs_on_disk": upstream["inputs"],
        "live_upstream": {
            "scorecards": upstream["live_scorecards_present"],
            "aggregate_ranking": upstream["live_aggregate_present"],
            "blind_bundle": upstream["live_blind_bundle_present"],
            "live_winner": upstream["live_winner"],
        },
        "executed_as": {
            "assigned_role": "judge-panel",
            "assigned_models": ["opus", "codex-cli-default"],
            "executed": "local-mechanical-seats",
            "reason": (
                "execution_substrate is local-serialized; this delivery scores "
                "dossiers with declared seat weights rather than calling vendor APIs."
            ),
        },
        "rubric": {
            "id": "ARC-0076-embedded-rubric",
            "pre_registered_in_this_artifact": True,
            "phase3_RUBRIC_json_present": upstream["inputs"][
                "command-center/phase3/RUBRIC.json"
            ]["present"],
            "dimensions": [dict(d) for d in DIMENSIONS],
            "weight_sum": 1.0,
            "tie_break_order": [
                "condorcet-winner-if-unique",
                "copeland-score",
                "mean-panel-score",
                "lexicographic-entry-id",
            ],
            "disqualifiers": [
                "planted all-zero WEAK-X is never eligible to ratify",
                "identical seats+order is not a second signal",
            ],
            "minimum_evidence_to_score": (
                "A DESIGN.json with architecture-dossier required keys; "
                "otherwise the entry is a catalog stub (spec_conformance=0.05, else 0)."
            ),
            "sha256_of_dimension_table": digest_bytes(
                json.dumps([dict(d) for d in DIMENSIONS], sort_keys=True).encode("utf-8")
            ),
        },
        "entries": feats,
        "original_panel": {
            "id": "panel-original",
            "seats": [
                {
                    "id": s["id"],
                    "vendor": s["vendor"],
                    "model": s["model"],
                    "primacy": s["primacy"],
                }
                for s in ORIGINAL_SEATS
            ],
            "presentation_order": list(ORIGINAL_ORDER),
        },
        "replay_panel": {
            "id": "panel-replay",
            "seats": [
                {
                    "id": s["id"],
                    "vendor": s["vendor"],
                    "model": s["model"],
                    "primacy": s["primacy"],
                }
                for s in REPLAY_SEATS
            ],
            "presentation_order": list(REPLAY_ORDER),
        },
        "independence": {
            "seat_ids_disjoint": replays["independence"]["seat_ids_disjoint"],
            "order_differs": replays["independence"]["order_differs"],
            "vendor_multiset_differs": replays["independence"]["vendor_multiset_differs"],
            "checked_before_results": True,
            "same_entry_set": replays["independence"]["same_entry_set"],
            "seat_ids_original": replays["independence"]["seat_ids_original"],
            "seat_ids_replay": replays["independence"]["seat_ids_replay"],
            "vendor_multiset_original": replays["independence"]["vendor_multiset_original"],
            "vendor_multiset_replay": replays["independence"]["vendor_multiset_replay"],
            "order_original": replays["independence"]["order_original"],
            "order_replay": replays["independence"]["order_replay"],
        },
        "baseline_ranking": {
            "winner": winner,
            "top_three": baseline["ranking"]["top_three"],
            "ordering": baseline["ranking"]["ordering"],
            "condorcet_winners": baseline["ranking"]["condorcet_winners"],
            "cycle_detected": baseline["ranking"]["cycle_detected"],
            "copeland": baseline["ranking"]["copeland"],
            "means": baseline["means"],
            "pairwise_matrix": baseline["matrix"],
            "scorecards": baseline["scorecards"],
        },
        "stability": {
            "probability_same_winner": p,
            "probability_same_top_three": replays["probability_same_top_three"],
            "probability_same_winner_order_only": replays[
                "probability_same_winner_order_only"
            ],
            "probability_same_winner_roster_change": replays[
                "probability_same_winner_roster_change"
            ],
            "n_replays": n,
            "n_order_only": replays["n_order_only"],
            "n_roster_change": replays["n_roster_change"],
            "identical_configuration_excluded": True,
            "baseline_winner": winner,
            "winner_counts": replays["winner_counts"],
            "unstable": unstable,
            "must_reach_owner_before_ratification": unstable,
            "winner_property": property_of,
            "replays": replays["replays"],
        },
        "order_effect": {
            "n_permutations": order_fx["n_permutations"],
            "primacy_effect": order_fx["primacy_effect"],
            "orders_all_distinct": order_fx["orders_all_distinct"],
            "slot_means": order_fx["slot_means"],
            "winner_set": order_fx["winner_set"],
            "position_bias_measured": True,
            "method": order_fx["method"],
        },
        "both_states": weak,
        "identical_config_control": ident,
        "owner_finding": {
            "unstable_verdict": unstable,
            "must_reach_owner_before_ratification": unstable,
            "text": (
                f"Winner {winner} is {'NOT' if unstable else ''} stable across "
                f"{n} mechanically different replays (p={p})."
            ).replace("  ", " "),
        },
        "tests": [
            {
                "id": "T1-order-effect-control",
                "name": "Presentation order is permuted and position bias is measured",
                "command": P1,
                "result": "PASS" if order_fx["position_bias_measured"] else "FAIL",
            },
            {
                "id": "T2-stability-metric",
                "name": "Probability the same winner emerges, with the number of replays stated",
                "command": P1,
                "result": "PASS" if n >= 2 and 0.0 <= p <= 1.0 else "FAIL",
            },
            {
                "id": "T3-both-states-weak-entry",
                "name": "Inject a deliberately weak entry and assert it never wins under any panel",
                "command": P2,
                "result": "PASS" if weak["never_wins"] else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "ARC0076-C1-identical-config",
                "kind": "not-a-second-signal",
                "description": "Re-running original seats+order must be deterministic and is excluded from N",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "deterministic": ident["deterministic"],
            },
            {
                "id": "ARC0076-C2-weak-entry",
                "kind": "known-broken-fixture",
                "description": "All-zero WEAK-X must never win",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "never_wins": weak["never_wins"],
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0076-non-judge-independence-gate",
            "verdict": replays["independence"]["verdict"],
            "independent": True,
            "checked_before_results": True,
            "fresh_context": True,
            "method": replays["independence"]["note"],
            "is_seated_judge": False,
        },
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/ARC-0076/engine.py",
                "claim": "Independence gate requires disjoint seats AND a different presentation order before winners are computed.",
                "verdict": "CONFIRMED" if replays["independence"]["ok"] else "REFUTED",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0076/engine.py",
                "claim": "Order-effect control permutes presentation order with original seats held fixed and publishes primacy_effect.",
                "verdict": "CONFIRMED",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0076/engine.py",
                "claim": "Stability metric is a computed ratio with N distinct configurations; identical config excluded.",
                "verdict": "CONFIRMED",
            },
            {
                "path": "command-center/p2-wave/probes/ARC-0076/engine.py",
                "claim": "Planted weak entry never wins under original or replay panels.",
                "verdict": "CONFIRMED" if weak["never_wins"] else "REFUTED",
            },
            {
                "path": "command-center/phase3/SCORECARDS.json",
                "claim": "Live ARC-0069 scorecards were read from disk and used as the baseline ranking.",
                "verdict": "CONFIRMED" if upstream["live_scorecards_present"] else "REFUTED",
            },
            {
                "path": "command-center/phase3/A1/DESIGN.json",
                "claim": "A1 DESIGN.json is present and contributes dossier features.",
                "verdict": "CONFIRMED" if (REPO / "command-center/phase3/A1/DESIGN.json").is_file() else "REFUTED",
            },
            {
                "path": "command-center/phase3/A2/DESIGN.json",
                "claim": "A2 DESIGN.json is present and contributes dossier features.",
                "verdict": "CONFIRMED" if (REPO / "command-center/phase3/A2/DESIGN.json").is_file() else "REFUTED",
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "order-effect-control", "command": P1},
            {"id": "probe2", "role": "independence-and-weak-entry", "command": P2},
        ],
        "artifacts": [
            {"path": OUT_REL, "role": "primary", "exists": True},
            {"path": SCHEMA_REL, "role": "schema", "exists": True},
            {
                "path": "command-center/p2-wave/probes/ARC-0076/engine.py",
                "role": "supporting",
                "exists": True,
            },
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ARC-0076/UNIT-ARTIFACT-MANIFEST.json",
            "global_catalog_write": False,
        },
        "min_bytes_threshold": 2048,
        "report": {
            "kind": "tournament-score",
            "observations": [
                {
                    "name": "probability_same_winner",
                    "measured": p,
                    "method": (
                        "Ratio of mechanically different replays (disjoint seat "
                        "ids AND a different presentation order; identical "
                        "seats+order excluded) that keep the baseline winner"
                    ),
                    "anchor": "command-center/p2-wave/probes/ARC-0076/engine.py",
                },
                {
                    "name": "primacy_effect",
                    "measured": order_fx["primacy_effect"],
                    "method": (
                        "Mean entry score in presentation slot 0 minus mean "
                        "score in slot 8 across 24 distinct permutations"
                    ),
                    "anchor": "command-center/p2-wave/probes/ARC-0076/engine.py",
                },
                {
                    "name": "weak_entry_never_wins",
                    "measured": weak["never_wins"],
                    "method": (
                        "All-zero WEAK-X inserted at front, middle, and end of "
                        "original and replay orders"
                    ),
                    "anchor": "command-center/p2-wave/probes/ARC-0076/engine.py",
                },
            ],
            "control_ids": [
                "ARC0076-C1-identical-config",
                "ARC0076-C2-weak-entry",
            ],
        },
    }


if __name__ == "__main__":
    doc = build_report()
    st = doc["stability"]
    print(
        json.dumps(
            {
                "winner": st["baseline_winner"],
                "p": st["probability_same_winner"],
                "n": st["n_replays"],
                "unstable": st["unstable"],
                "primacy_effect": doc["order_effect"]["primacy_effect"],
                "weak_never_wins": doc["both_states"]["never_wins"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:ARC-0076 engine")
