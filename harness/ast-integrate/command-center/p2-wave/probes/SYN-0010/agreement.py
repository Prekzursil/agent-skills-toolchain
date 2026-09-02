"""Chance-corrected agreement for SYN-0010 (Fleiss' kappa).

Headline statistic: Fleiss' kappa over a joint label per universe item.
Categories: OUT, P0, P1, P2, P3 — set membership and severity in one rating.

Null model (sampling frame): a fixed panel of N synthesizers independently
assigns each closed-universe mechanism id a label with probabilities equal to
the observed category marginals. Chance agreement is the sum of squared
marginals (Fleiss 1971). This is not a random-rater population model.

Thresholds below were declared before any control draw.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]

CATEGORIES = ("OUT", "P0", "P1", "P2", "P3")
SEVERITY_SCORE = {"OUT": 0, "P3": 1, "P2": 2, "P1": 3, "P0": 4}

# Declared 2026-08-24 before the seeded random-control draw.
IDENTICAL_MIN = 1.0 - 1e-12
RANDOM_ABS_MAX = 0.20
CONTROL_UNIVERSE_SIZE = 50
CONTROL_N_RATERS = 3
SEED = 20260824
BOOTSTRAP_ITERS = 2000
BOOTSTRAP_LEVEL = 0.95

SYN8 = REPO / "command-center/synthesis/SYN-0008.candidate-syntheses.json"
SYN9 = REPO / "command-center/synthesis/SYN-0009.raw-source-control.json"
CLAIM_REGISTRY = REPO / "command-center/CLAIM-REGISTRY.json"

NULL_MODEL = (
    "Null model: a fixed panel of N synthesizers independently assigns each "
    "closed-universe mechanism id a joint label in {OUT, P0, P1, P2, P3} with "
    "probabilities equal to the observed category marginals; chance agreement "
    "P_e is the sum of squared marginals (Fleiss 1971). This matches a complete "
    "item universe rated by a named panel, not a sample of raters from a larger "
    "population."
)

REFUSED_PHRASE = "the agents converged"

CATALOG_SENTINEL = (
    "SUCCESS:SYN-0010 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both synthetic controls "
    "land at their expected extremes. Any other terminal state is "
    "FAILED:SYN-0010 <classification> with the diagnostic tail attached."
)


def roundf(x: float, nd: int = 12) -> float:
    return float(f"{x:.{nd}f}")


def fleiss_kappa(
    rows: list[list[str]], categories: tuple[str, ...] = CATEGORIES
) -> dict[str, Any]:
    """Fleiss' kappa from per-item rating tuples (one string per rater)."""
    if not rows:
        raise ValueError("empty rating matrix")
    n = len(rows[0])
    if n < 2:
        raise ValueError("need >=2 raters")
    if any(len(r) != n for r in rows):
        raise ValueError("ragged rating matrix")
    n_items = len(rows)
    cat_index = {c: i for i, c in enumerate(categories)}
    counts = []
    for row in rows:
        vec = [0] * len(categories)
        for lab in row:
            if lab not in cat_index:
                raise ValueError(f"unknown category {lab!r}")
            vec[cat_index[lab]] += 1
        counts.append(vec)

    denom = n * (n - 1)
    p_i = [sum(v * (v - 1) for v in vec) / denom for vec in counts]
    p_bar = sum(p_i) / n_items

    total = n_items * n
    p_j = [sum(vec[j] for vec in counts) / total for j in range(len(categories))]
    p_e = sum(p * p for p in p_j)

    if p_bar == 1.0:
        kappa = 1.0
    elif p_e >= 1.0 - 1e-15:
        kappa = 0.0
    else:
        kappa = (p_bar - p_e) / (1.0 - p_e)

    return {
        "name": "fleiss_kappa",
        "value": roundf(kappa),
        "p_bar": roundf(p_bar),
        "p_e": roundf(p_e),
        "n_items": n_items,
        "n_raters": n,
        "categories": list(categories),
        "category_marginals": {
            categories[j]: roundf(p_j[j]) for j in range(len(categories))
        },
    }


def kappa_from_matrix(matrix: dict[str, Any]) -> dict[str, Any]:
    """Recompute Fleiss' kappa from a published per-item matrix alone."""
    cats = tuple(matrix["categories"])
    rows = [list(item["ratings"]) for item in matrix["items"]]
    return fleiss_kappa(rows, cats)


def bootstrap_interval(
    rows: list[list[str]],
    seed: int,
    iters: int = BOOTSTRAP_ITERS,
    level: float = BOOTSTRAP_LEVEL,
    categories: tuple[str, ...] = CATEGORIES,
) -> dict[str, Any]:
    rng = random.Random(seed)
    n = len(rows)
    stats: list[float] = []
    for _ in range(iters):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        stats.append(fleiss_kappa(sample, categories)["value"])
    stats.sort()
    alpha = 1.0 - level
    lo_i = int(math.floor(alpha / 2 * iters))
    hi_i = int(math.ceil((1 - alpha / 2) * iters)) - 1
    lo_i = max(0, min(iters - 1, lo_i))
    hi_i = max(0, min(iters - 1, hi_i))
    return {
        "low": roundf(stats[lo_i]),
        "high": roundf(stats[hi_i]),
        "method": f"item-bootstrap-{iters}",
        "level": level,
        "seed": seed,
    }


def mean_pairwise_spearman(rows: list[list[str]]) -> float:
    """Mean pairwise Pearson of ordinal severity scores.

    Independent raters have expected correlation 0, so this is already
    chance-centered for the ordinal ranking channel.
    """
    n_raters = len(rows[0])
    series = []
    for r in range(n_raters):
        series.append([SEVERITY_SCORE[row[r]] for row in rows])

    def pearson(x: list[int], y: list[int]) -> float:
        n = len(x)
        mx = sum(x) / n
        my = sum(y) / n
        num = sum((a - mx) * (b - my) for a, b in zip(x, y))
        dx = math.sqrt(sum((a - mx) ** 2 for a in x))
        dy = math.sqrt(sum((b - my) ** 2 for b in y))
        if dx == 0.0 and dy == 0.0:
            return 1.0
        if dx == 0.0 or dy == 0.0:
            return 0.0
        return num / (dx * dy)

    pairs = [
        pearson(series[i], series[j])
        for i in range(n_raters)
        for j in range(i + 1, n_raters)
    ]
    return roundf(sum(pairs) / len(pairs))


def binary_set_kappa(rows: list[list[str]]) -> dict[str, Any]:
    collapsed = [["IN" if lab != "OUT" else "OUT" for lab in row] for row in rows]
    return fleiss_kappa(collapsed, ("OUT", "IN"))


def matrix_from_rows(
    item_ids: list[str],
    rater_ids: list[str],
    rows: list[list[str]],
    categories: tuple[str, ...] = CATEGORIES,
) -> dict[str, Any]:
    items = []
    for iid, ratings in zip(item_ids, rows):
        items.append(
            {
                "id": iid,
                "ratings": list(ratings),
                "unanimous": len(set(ratings)) == 1,
            }
        )
    return {
        "categories": list(categories),
        "rater_ids": list(rater_ids),
        "items": items,
    }


def divergences_from_matrix(matrix: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for item in matrix.get("items") or []:
        ratings = list(item.get("ratings") or [])
        if ratings and len(set(ratings)) > 1:
            out.append(
                {
                    "item_id": item.get("id"),
                    "ratings": ratings,
                    "unanimous": False,
                }
            )
    return out


def control_universe(k: int = CONTROL_UNIVERSE_SIZE) -> list[str]:
    return [f"SYN-0010-CTRL-{i:02d}" for i in range(k)]


def identical_by_rater(k: int = CONTROL_UNIVERSE_SIZE) -> list[list[str]]:
    pattern = [CATEGORIES[i % len(CATEGORIES)] for i in range(k)]
    return [list(pattern) for _ in range(CONTROL_N_RATERS)]


def transpose_raters_to_items(by_rater: list[list[str]]) -> list[list[str]]:
    k = len(by_rater[0])
    return [[by_rater[r][i] for r in range(len(by_rater))] for i in range(k)]


def run_identical_control() -> dict[str, Any]:
    ids = control_universe()
    by_rater = identical_by_rater()
    rows = transpose_raters_to_items(by_rater)
    raters = [f"identical-{i}" for i in range(CONTROL_N_RATERS)]
    stat = fleiss_kappa(rows)
    interval = bootstrap_interval(rows, SEED)
    matrix = matrix_from_rows(ids, raters, rows)
    ok = stat["value"] >= IDENTICAL_MIN
    return {
        "n_candidates": CONTROL_N_RATERS,
        "coefficient": stat["value"],
        "p_bar": stat["p_bar"],
        "p_e": stat["p_e"],
        "interval": interval,
        "set_membership_kappa": binary_set_kappa(rows)["value"],
        "severity_spearman": mean_pairwise_spearman(rows),
        "expected": "maximum",
        "pass": ok,
        "universe_size": len(ids),
        "matrix": matrix,
        "null_model": NULL_MODEL,
    }


def run_random_control() -> dict[str, Any]:
    ids = control_universe()
    rng = random.Random(SEED)
    by_rater = [
        [CATEGORIES[rng.randrange(len(CATEGORIES))] for _ in range(len(ids))]
        for _ in range(CONTROL_N_RATERS)
    ]
    rows = transpose_raters_to_items(by_rater)
    raters = [f"random-{i}" for i in range(CONTROL_N_RATERS)]
    stat = fleiss_kappa(rows)
    interval = bootstrap_interval(rows, SEED + 1)
    matrix = matrix_from_rows(ids, raters, rows)
    ok = abs(stat["value"]) <= RANDOM_ABS_MAX
    return {
        "n_candidates": CONTROL_N_RATERS,
        "coefficient": stat["value"],
        "p_bar": stat["p_bar"],
        "p_e": stat["p_e"],
        "interval": interval,
        "set_membership_kappa": binary_set_kappa(rows)["value"],
        "severity_spearman": mean_pairwise_spearman(rows),
        "expected": "near_zero",
        "pass": ok,
        "universe_size": len(ids),
        "matrix": matrix,
        "seed": SEED,
        "null_model": NULL_MODEL,
    }


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _as_id_list(val: Any) -> list[str]:
    out: list[str] = []
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    if not isinstance(val, list):
        return out
    for item in val:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
        elif isinstance(item, dict):
            for k in ("id", "mechanism_id", "canonical_mechanism_id", "cause_id"):
                v = item.get(k)
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
                    break
    return out


def ids_from_registry(doc: Any) -> list[str]:
    if isinstance(doc, list):
        blobs = doc
    elif isinstance(doc, dict):
        blobs = []
        for key in ("claims", "records", "items", "mechanisms", "entries"):
            if isinstance(doc.get(key), list):
                blobs = doc[key]
                break
        if not blobs:
            blobs = [doc]
    else:
        return []
    ids: list[str] = []
    for rec in blobs:
        if not isinstance(rec, dict):
            continue
        hit = False
        for k in (
            "mechanism_id",
            "canonical_mechanism_id",
            "canonical_mechanism",
            "id",
        ):
            v = rec.get(k)
            if isinstance(v, str) and v.strip():
                ids.append(v.strip())
                hit = True
                break
        if not hit:
            ids.extend(_as_id_list(rec.get("mechanism_ids")))
    seen: set[str] = set()
    ordered: list[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            ordered.append(i)
    return ordered


def iter_candidates(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("candidates", "syntheses", "items", "records", "panel"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return [doc]


def rating_for_item(candidate: dict[str, Any], item_id: str) -> str:
    in_set = False
    severity = None

    for key in (
        "root_cause_ids",
        "root_causes",
        "mechanism_ids",
        "mechanisms",
        "causes",
        "cause_ids",
    ):
        if item_id in set(_as_id_list(candidate.get(key))):
            in_set = True
            break

    sev_map = candidate.get("severity_by_id") or candidate.get("severities") or {}
    if isinstance(sev_map, dict) and item_id in sev_map:
        in_set = True
        severity = sev_map.get(item_id)

    ranking = candidate.get("severity_ranking") or candidate.get("severity_rankings") or []
    if isinstance(ranking, list):
        for pos, entry in enumerate(ranking):
            eid = None
            sev = None
            if isinstance(entry, str) and entry == item_id:
                eid = entry
            elif isinstance(entry, dict):
                eid = entry.get("id") or entry.get("mechanism_id")
                sev = entry.get("severity")
            if eid == item_id:
                in_set = True
                if sev:
                    severity = sev
                elif severity is None:
                    n = max(1, len(ranking))
                    bucket = pos * 3 // n
                    severity = ("P0", "P1", "P2")[min(bucket, 2)]
                break

    if not in_set:
        return "OUT"
    if isinstance(severity, str):
        s = severity.strip().upper()
        if s in CATEGORIES:
            return s
        if s in {"CRITICAL", "HIGHEST"}:
            return "P0"
        if s in {"HIGH"}:
            return "P1"
        if s in {"MEDIUM", "MODERATE"}:
            return "P2"
        if s in {"LOW"}:
            return "P3"
    return "P1"


def candidate_label(candidate: dict[str, Any], index: int, source: str) -> str:
    for k in ("id", "candidate_id", "vendor", "model"):
        v = candidate.get(k)
        if isinstance(v, str) and v.strip():
            return f"{source}:{v.strip()}"
    return f"{source}:candidate-{index}"


def load_live_panel() -> dict[str, Any]:
    inputs = {
        "syn_0008": {
            "path": str(SYN8.relative_to(REPO)).replace("\\", "/"),
            "present": SYN8.is_file() and SYN8.stat().st_size > 0,
        },
        "syn_0009": {
            "path": str(SYN9.relative_to(REPO)).replace("\\", "/"),
            "present": SYN9.is_file() and SYN9.stat().st_size > 0,
        },
        "claim_registry": {
            "path": str(CLAIM_REGISTRY.relative_to(REPO)).replace("\\", "/"),
            "present": CLAIM_REGISTRY.is_file() and CLAIM_REGISTRY.stat().st_size > 0,
        },
    }
    missing = [k for k, v in inputs.items() if not v["present"]]
    if missing:
        return {
            "status": "NOT-CHECKED",
            "reason": (
                "Live coefficient is NOT-CHECKED: required independent-synthesis "
                f"inputs absent ({', '.join(missing)}). A number without those "
                "files would be an invented panel, not a measurement. Universe "
                "size and null model for the live panel are therefore unpublished."
            ),
            "inputs": inputs,
            "n_candidates": 0,
            "coefficient": None,
            "universe_size": 0,
        }

    syn8 = _read_json(SYN8)
    syn9 = _read_json(SYN9)
    registry = _read_json(CLAIM_REGISTRY)
    if syn8 is None or syn9 is None or registry is None:
        return {
            "status": "NOT-CHECKED",
            "reason": (
                "Live inputs present on disk but unparseable; coefficient NOT-CHECKED."
            ),
            "inputs": inputs,
            "n_candidates": 0,
            "coefficient": None,
            "universe_size": 0,
        }

    cands = iter_candidates(syn8)
    control = iter_candidates(syn9)
    panel = cands + control
    if len(panel) < 2:
        return {
            "status": "NOT-CHECKED",
            "reason": (
                "Fewer than two live synthesizers after joining SYN-0008 and "
                "SYN-0009; Fleiss' kappa is undefined. NOT-CHECKED."
            ),
            "inputs": inputs,
            "n_candidates": len(panel),
            "coefficient": None,
            "universe_size": 0,
        }

    universe = ids_from_registry(registry)
    source = "command-center/CLAIM-REGISTRY.json"
    if not universe:
        mentioned: list[str] = []
        for c in panel:
            for key in (
                "root_cause_ids",
                "root_causes",
                "mechanism_ids",
                "mechanisms",
                "causes",
            ):
                mentioned.extend(_as_id_list(c.get(key)))
        universe = sorted(set(mentioned))
        source = "union-of-live-candidates (CLAIM-REGISTRY had no mechanism ids)"
    if not universe:
        return {
            "status": "NOT-CHECKED",
            "reason": (
                "Item universe is empty; a coefficient without universe size "
                "is uninterpretable."
            ),
            "inputs": inputs,
            "n_candidates": len(panel),
            "coefficient": None,
            "universe_size": 0,
        }

    rater_ids = [
        candidate_label(c, i, "syn8" if i < len(cands) else "syn9")
        for i, c in enumerate(panel)
    ]
    rows = [[rating_for_item(c, iid) for c in panel] for iid in universe]
    stat = fleiss_kappa(rows)
    interval = bootstrap_interval(rows, SEED)
    matrix = matrix_from_rows(universe, rater_ids, rows)
    return {
        "status": "COMPUTED",
        "reason": None,
        "inputs": inputs,
        "n_candidates": len(panel),
        "coefficient": stat["value"],
        "p_bar": stat["p_bar"],
        "p_e": stat["p_e"],
        "interval": interval,
        "set_membership_kappa": binary_set_kappa(rows)["value"],
        "severity_spearman": mean_pairwise_spearman(rows),
        "universe_size": len(universe),
        "universe_ids": universe,
        "universe_source": source,
        "matrix": matrix,
        "null_model": NULL_MODEL,
    }


def build_report() -> dict[str, Any]:
    ident = run_identical_control()
    rand = run_random_control()
    live = load_live_panel()
    controls_ok = bool(ident["pass"] and rand["pass"])

    if live.get("status") == "COMPUTED":
        headline = {
            "name": "fleiss_kappa",
            "value": live["coefficient"],
            "status": "COMPUTED",
            "universe_size": live["universe_size"],
            "interval": live["interval"],
            "p_bar": live["p_bar"],
            "p_e": live["p_e"],
            "set_membership_kappa": live["set_membership_kappa"],
            "severity_spearman": live["severity_spearman"],
            "panel": "live SYN-0008+SYN-0009",
        }
        matrix = live["matrix"]
        universe = {
            "size": live["universe_size"],
            "source": live["universe_source"],
            "ids": live["universe_ids"],
        }
        divs = divergences_from_matrix(matrix)
    else:
        headline = {
            "name": "fleiss_kappa",
            "value": None,
            "status": "NOT-CHECKED",
            "universe_size": 0,
            "interval": {
                "low": None,
                "high": None,
                "method": "not-applicable-no-live-panel",
                "level": BOOTSTRAP_LEVEL,
            },
            "panel": "live SYN-0008+SYN-0009 absent",
            "reason": live.get("reason"),
        }
        matrix = {
            "categories": list(CATEGORIES),
            "rater_ids": [],
            "items": [],
            "note": (
                "Live matrix empty because independent-synthesis inputs are absent."
            ),
        }
        missing = [
            str((live.get("inputs") or {}).get(k, {}).get("path") or k)
            for k in ("syn_0008", "syn_0009", "claim_registry")
            if not (live.get("inputs") or {}).get(k, {}).get("present")
        ]
        universe = {
            "size": 0,
            "source": (
                "unpublished: live panel incomplete; missing "
                + (", ".join(missing) if missing else "unknown")
            ),
            "ids": [],
        }
        divs = []

    return {
        "identical": ident,
        "random": rand,
        "live": live,
        "controls_ok": controls_ok,
        "headline": headline,
        "matrix": matrix,
        "universe": universe,
        "divergences": divs,
    }


if __name__ == "__main__":
    ident = run_identical_control()
    rand = run_random_control()
    print(
        json.dumps(
            {
                "identical": ident["coefficient"],
                "identical_pass": ident["pass"],
                "random": rand["coefficient"],
                "random_pass": rand["pass"],
                "random_spearman": rand["severity_spearman"],
            },
            indent=2,
        )
    )
