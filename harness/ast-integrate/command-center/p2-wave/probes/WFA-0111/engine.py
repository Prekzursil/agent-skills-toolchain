"""WFA-0111 fusion-operator selection policy.

Two mechanically independent paths:

A. Certification oracle — catalog semantics of WFA-0100..0107. For each
   source pair it returns the operator that would actually certify (or
   NOT-FUSIBLE). It is not a fitted policy and is not used at apply-time.

B. Fitted policy — majority vote over recorded feature bins on the TRAIN
   split only. Held-out pairs are never seen during fit. Revisable: the
   votes, backoff, and pair rows are recorded so the same procedure can
   be re-run on new labelled pairs.

Upstream operator artifacts (WFA-0100..0107) are absent on this worktree.
The oracle therefore executes the operators' documented LEGAL/CERTIFY
predicates, not live fusion binaries. That limitation is recorded, not
papered over.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "WFA-0111"
SENTINEL = "SUCCESS:WFA-0111"
OUT_REL = "command-center/wfa/WFA-0111-fusion-operator-selection-policy.json"
SCHEMA_REL = (
    "command-center/p2-wave/probes/WFA-0111/audit-report.schema.json"
)
PAIRS_REL = "command-center/p2-wave/probes/WFA-0111/fixtures/pairs.json"
CATALOG_SCHEMA = (
    "command-center/wfa/schema/wfa-schema-pack.json#/$defs/AuditReport"
)

OPERATORS: tuple[str, ...] = (
    "stage-splice",
    "common-core",
    "union",
    "best-of-breed",
    "conditional-hybrid",
    "ensemble",
    "progressive",
)
NOT_FUSIBLE = "NOT-FUSIBLE"
CHOICES: tuple[str, ...] = OPERATORS + (NOT_FUSIBLE,)

FEATURES: tuple[str, ...] = (
    "overlap_ratio",
    "conflict_presence",
    "benchmark_separation",
    "cost_asymmetry",
)

UPSTREAM_PATHS = {
    "WFA-0100": "command-center/wfa/WFA-0100-fusion-stage-splice.json",
    "WFA-0101": "command-center/wfa/WFA-0101-fusion-common-core.json",
    "WFA-0102": "command-center/wfa/WFA-0102-fusion-union.json",
    "WFA-0103": "command-center/wfa/WFA-0103-fusion-best-of-breed.json",
    "WFA-0104": "command-center/wfa/WFA-0104-fusion-conditional-hybrid.json",
    "WFA-0105": "command-center/wfa/WFA-0105-fusion-ensemble.json",
    "WFA-0106": "command-center/wfa/WFA-0106-fusion-progressive.json",
    "WFA-0107": "command-center/wfa/WFA-0107-fusion-precondition-checker.json",
}

OVERLAPS = (0.08, 0.22, 0.38, 0.50, 0.62, 0.78, 0.92)
SEPS = (0.08, 0.28, 0.48, 0.72, 0.88)
COSTS = (0.08, 0.28, 0.48, 0.72, 0.88)
CONFLICTS = (False, True)
LICENCE_BLOCK_INDICES = (3, 17, 41, 73, 101, 140, 181, 220, 251, 288, 310, 339)


def _r2(x: float) -> float:
    return round(float(x), 2)


def bin_continuous(x: float) -> str:
    if x < 0.33:
        return "low"
    if x < 0.66:
        return "mid"
    return "high"


def feature_bin(pair: dict[str, Any]) -> str:
    lic = "blocked" if pair.get("licence_incompatible") else "ok"
    conf = "conflict" if pair["conflict_presence"] else "clean"
    return "|".join(
        (
            bin_continuous(pair["overlap_ratio"]),
            conf,
            bin_continuous(pair["benchmark_separation"]),
            bin_continuous(pair["cost_asymmetry"]),
            lic,
        )
    )


def _parts(key: str) -> tuple[str, str, str, str, str]:
    p = key.split("|")
    if len(p) != 5:
        raise ValueError(f"bad feature bin {key!r}")
    return p[0], p[1], p[2], p[3], p[4]


def legal_reason(pair: dict[str, Any], operator: str) -> tuple[bool, str]:
    """WFA-0107 precondition plus operator-specific hard refusals."""
    if pair.get("licence_incompatible"):
        return False, "licence-incompatible"
    if operator == "union" and pair["conflict_presence"]:
        return False, "mechanism-conflict"
    if operator == "stage-splice" and pair["overlap_ratio"] < 0.20:
        return False, "type-unsatisfied-at-insertion"
    if operator == "common-core" and pair["overlap_ratio"] < 0.35:
        return False, "degenerate-empty-intersection"
    return True, "LEGAL"


def operator_score(pair: dict[str, Any], operator: str) -> float:
    """Independent certification margin. Positive => this operator certifies.

    Each operator owns a region of the four-property space, taken from the
    catalog roles (WFA-0100..0106), not from the fitted bin policy.
    """
    o = float(pair["overlap_ratio"])
    s = float(pair["benchmark_separation"])
    k = float(pair["cost_asymmetry"])
    c = bool(pair["conflict_presence"])
    if operator == "progressive":
        return (k - 0.58) * 1.4
    if operator == "best-of-breed":
        return (s - 0.55) * 1.4 - 0.45 * k
    if operator == "common-core":
        return (o - 0.64) * 1.6 - 0.25 * s - 0.25 * k
    if operator == "conditional-hybrid":
        return (0.30 - o) * 1.8 - 0.10 * s + (0.12 if c else 0.0)
    if operator == "union":
        if c:
            return -1.0
        return 0.42 - o - 0.22 * s - 0.22 * k
    if operator == "stage-splice":
        return 0.52 - 1.55 * abs(o - 0.50) - 0.55 * k - 0.70 * s
    if operator == "ensemble":
        return (
            0.58
            - 1.25 * abs(k - 0.18)
            - 1.15 * abs(s - 0.45)
            - 0.70 * abs(o - 0.48)
        )
    raise KeyError(operator)


def certify_pair(pair: dict[str, Any]) -> dict[str, Any]:
    """Oracle: which operators certify, and which one actually would."""
    legal: dict[str, str] = {}
    illegal: dict[str, str] = {}
    scores: dict[str, float] = {}
    certified_set: list[str] = []
    for op in OPERATORS:
        ok, reason = legal_reason(pair, op)
        if not ok:
            illegal[op] = reason
            scores[op] = -1.0
            continue
        legal[op] = reason
        sc = operator_score(pair, op)
        scores[op] = round(sc, 6)
        if sc >= 0.0:
            certified_set.append(op)
    if not certified_set:
        gold = NOT_FUSIBLE
        margin = None
    else:
        gold = max(
            certified_set,
            key=lambda op: (scores[op], -OPERATORS.index(op)),
        )
        margin = scores[gold]
    return {
        "legal": legal,
        "illegal": illegal,
        "scores": scores,
        "certified_set": certified_set,
        "certified": gold,
        "margin": margin,
    }


def _split_for(key: str, modulus: int, held_residue: int) -> str:
    """Feature-hash split so held-out is not locked to one grid axis."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return "held_out" if int(digest[:8], 16) % modulus == held_residue else "train"


def generate_pairs() -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    n = 0
    for o in OVERLAPS:
        for conf in CONFLICTS:
            for s in SEPS:
                for k in COSTS:
                    row: dict[str, Any] = {
                        "id": f"pair-{n:04d}",
                        "overlap_ratio": _r2(o),
                        "conflict_presence": conf,
                        "benchmark_separation": _r2(s),
                        "cost_asymmetry": _r2(k),
                        "licence_incompatible": False,
                        "index": n,
                        "split": _split_for(f"{o}|{int(conf)}|{s}|{k}", 5, 0),
                    }
                    cert = certify_pair(row)
                    row["certified"] = cert["certified"]
                    row["certified_set"] = list(cert["certified_set"])
                    pairs.append(row)
                    n += 1
    for j, idx in enumerate(LICENCE_BLOCK_INDICES):
        if idx >= n:
            continue
        src = pairs[idx]
        clone: dict[str, Any] = {
            "id": f"pair-lic-{j:02d}",
            "overlap_ratio": src["overlap_ratio"],
            "conflict_presence": src["conflict_presence"],
            "benchmark_separation": src["benchmark_separation"],
            "cost_asymmetry": src["cost_asymmetry"],
            "licence_incompatible": True,
            "index": len(pairs),
            "cloned_from": src["id"],
            # Guarantee held-out licence blocks so NOT-FUSIBLE is evaluated,
            # not only trained. Hash split parked all 12 clones in train.
            "split": "held_out" if j >= 9 else "train",
        }
        cert = certify_pair(clone)
        clone["certified"] = cert["certified"]
        clone["certified_set"] = list(cert["certified_set"])
        pairs.append(clone)
    return pairs


def dump_pairs(path: Path | None = None) -> list[dict[str, Any]]:
    pairs = generate_pairs()
    dest = path or (REPO / PAIRS_REL)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "unit_id": UNIT,
        "role": "revisable-fit-inputs",
        "features": list(FEATURES) + ["licence_incompatible"],
        "operators": list(OPERATORS),
        "not_fusible_token": NOT_FUSIBLE,
        "split_rule": (
            "sha256(feature-tuple)[:8] % 5 == 0 => held_out; "
            "licence clones j>=9 => held_out (3 of 12)"
        ),
        "pairs": pairs,
    }
    dest.write_text(
        json.dumps(body, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return pairs


def load_pairs(path: Path | None = None) -> list[dict[str, Any]]:
    src = path or (REPO / PAIRS_REL)
    doc = json.loads(src.read_text(encoding="utf-8"))
    pairs = list(doc["pairs"])
    live = generate_pairs()
    if [p["id"] for p in pairs] != [p["id"] for p in live]:
        raise RuntimeError("pairs.json id list drifted from engine.generate_pairs")
    for a, b in zip(pairs, live):
        if a["certified"] != b["certified"]:
            raise RuntimeError(f"pairs.json gold drift on {a['id']}")
        if a["split"] != b["split"]:
            raise RuntimeError(f"pairs.json split drift on {a['id']}")
    return pairs


def _majority(votes: dict[str, int]) -> str:
    if not votes:
        return NOT_FUSIBLE
    best_n = max(votes.values())
    tied = [c for c, n in votes.items() if n == best_n]
    for c in CHOICES:
        if c in tied:
            return c
    return tied[0]


def fit_policy(train: list[dict[str, Any]]) -> dict[str, Any]:
    tables: dict[str, dict[str, int]] = {}
    global_votes: dict[str, int] = {}
    for row in train:
        key = feature_bin(row)
        tables.setdefault(key, {})
        lab = row["certified"]
        tables[key][lab] = tables[key].get(lab, 0) + 1
        global_votes[lab] = global_votes.get(lab, 0) + 1
    rules = []
    lookup: dict[str, str] = {}
    for key in sorted(tables):
        choice = _majority(tables[key])
        lookup[key] = choice
        rules.append(
            {
                "bin": key,
                "choice": choice,
                "votes": dict(sorted(tables[key].items())),
                "n": sum(tables[key].values()),
            }
        )
    return {
        "kind": "majority-vote-feature-bins",
        "features": list(FEATURES) + ["licence_incompatible"],
        "bin_edges": {"low": [0.0, 0.33], "mid": [0.33, 0.66], "high": [0.66, 1.0]},
        "tie_break": "catalog-operator-order-then-NOT-FUSIBLE",
        "backoff": [
            "exact-five-tuple",
            "drop-cost_asymmetry",
            "drop-benchmark_separation",
            "drop-overlap_ratio",
            "global-majority",
        ],
        "n_train": len(train),
        "n_bins_occupied": len(rules),
        "global_majority": _majority(global_votes),
        "global_votes": dict(sorted(global_votes.items())),
        "rules": rules,
        "lookup": lookup,
        "revisable": True,
        "fit_inputs_path": PAIRS_REL,
    }


def _votes_where(
    lookup: dict[str, str], pred: Callable[[tuple[str, str, str, str, str]], bool]
) -> dict[str, int]:
    votes: dict[str, int] = {}
    for key, choice in lookup.items():
        if pred(_parts(key)):
            votes[choice] = votes.get(choice, 0) + 1
    return votes


def apply_policy(policy: dict[str, Any], pair: dict[str, Any]) -> dict[str, Any]:
    exact = feature_bin(pair)
    # WFA-0107: licence incompatibility blocks every operator before fit lookup.
    if pair.get("licence_incompatible"):
        return {
            "policy_choice": NOT_FUSIBLE,
            "bin": exact,
            "matched_bin": "licence-precondition",
        }
    lookup: dict[str, str] = policy["lookup"]
    if exact in lookup:
        return {
            "policy_choice": lookup[exact],
            "bin": exact,
            "matched_bin": exact,
        }
    o, c, s, _k, lic = _parts(exact)
    stages: list[tuple[str, Callable[[tuple[str, str, str, str, str]], bool]]] = [
        (
            f"{o}|{c}|{s}|*|{lic}",
            lambda p, o=o, c=c, s=s, lic=lic: (
                p[0] == o and p[1] == c and p[2] == s and p[4] == lic
            ),
        ),
        (
            f"{o}|{c}|*|*|{lic}",
            lambda p, o=o, c=c, lic=lic: p[0] == o and p[1] == c and p[4] == lic,
        ),
        (
            f"*|{c}|*|*|{lic}",
            lambda p, c=c, lic=lic: p[1] == c and p[4] == lic,
        ),
        (
            f"*|*|*|*|{lic}",
            lambda p, lic=lic: p[4] == lic,
        ),
    ]
    for label, pred in stages:
        votes = _votes_where(lookup, pred)
        if votes:
            return {
                "policy_choice": _majority(votes),
                "bin": exact,
                "matched_bin": label,
            }
    return {
        "policy_choice": policy["global_majority"],
        "bin": exact,
        "matched_bin": "*",
    }


def invert_choice(choice: str) -> str:
    if choice == NOT_FUSIBLE:
        return OPERATORS[0]
    return OPERATORS[(OPERATORS.index(choice) + 3) % len(OPERATORS)]


def exact_random_rate(golds: list[str], n_ops: int = len(OPERATORS)) -> float:
    """Uniform random over the seven operators (catalog 'random-operator')."""
    if not golds:
        return 0.0
    hits = sum((1.0 / n_ops) if g in OPERATORS else 0.0 for g in golds)
    return hits / len(golds)


def monte_carlo_random_rate(
    golds: list[str], seed: int = 2111, draws: int = 4000
) -> float:
    """Independent RNG path from exact_random_rate (probe 2 / evidence B)."""
    state = seed & 0xFFFFFFFF
    hits = 0
    n = len(golds)
    if n == 0:
        return 0.0
    for _ in range(draws):
        match = 0
        for g in golds:
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            pick = OPERATORS[state % len(OPERATORS)]
            if pick == g:
                match += 1
        hits += match
    return hits / (draws * n)


def evaluate(
    policy: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    out_rows = []
    matches = 0
    set_hits = 0
    not_fusible_n = 0
    not_fusible_correct = 0
    for row in rows:
        applied = apply_policy(policy, row)
        choice = applied["policy_choice"]
        gold = row["certified"]
        certified_set = list(row["certified_set"])
        match = choice == gold
        in_set = (choice in certified_set) or (
            gold == NOT_FUSIBLE and choice == NOT_FUSIBLE
        )
        if match:
            matches += 1
        if in_set:
            set_hits += 1
        if gold == NOT_FUSIBLE:
            not_fusible_n += 1
            if choice == NOT_FUSIBLE:
                not_fusible_correct += 1
        out_rows.append(
            {
                "id": row["id"],
                "overlap_ratio": row["overlap_ratio"],
                "conflict_presence": row["conflict_presence"],
                "benchmark_separation": row["benchmark_separation"],
                "cost_asymmetry": row["cost_asymmetry"],
                "licence_incompatible": bool(row.get("licence_incompatible")),
                "certified": gold,
                "certified_set": certified_set,
                "policy_choice": choice,
                "match": match,
                "in_certified_set": in_set,
                "bin": applied["bin"],
                "matched_bin": applied["matched_bin"],
            }
        )
    n = len(rows)
    golds = [r["certified"] for r in rows]
    exact = matches / n if n else 0.0
    rand_exact = exact_random_rate(golds)
    rand_mc = monte_carlo_random_rate(golds)
    invert_matches = sum(
        1 for rec in out_rows if invert_choice(rec["policy_choice"]) == rec["certified"]
    )
    invert_rate = invert_matches / n if n else 0.0
    return {
        "n": n,
        "exact_matches": matches,
        "exact_match_rate": round(exact, 6),
        "in_certified_set_hits": set_hits,
        "in_certified_set_rate": round(set_hits / n if n else 0.0, 6),
        "not_fusible_n": not_fusible_n,
        "not_fusible_correct": not_fusible_correct,
        "random_expected_rate": round(rand_exact, 6),
        "random_monte_carlo_rate": round(rand_mc, 6),
        "invert_policy_rate": round(invert_rate, 6),
        "policy_beats_random": exact > rand_exact,
        "margin_over_random": round(exact - rand_exact, 6),
        "invert_does_not_beat_random": invert_rate <= rand_exact,
        "golds": golds,
        "rows": out_rows,
    }


def gold_histogram(pairs: list[dict[str, Any]]) -> dict[str, int]:
    hist = {c: 0 for c in CHOICES}
    for p in pairs:
        hist[p["certified"]] = hist.get(p["certified"], 0) + 1
    return hist


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def upstream_status() -> dict[str, Any]:
    rows = []
    present = 0
    for uid, rel in UPSTREAM_PATHS.items():
        p = REPO / rel
        exists = p.is_file() and p.stat().st_size > 0
        if exists:
            present += 1
        rows.append({"unit_id": uid, "path": rel, "present": exists})
    return {
        "expected": len(UPSTREAM_PATHS),
        "present": present,
        "oracle_mode": (
            "live-operator-artifacts"
            if present == len(UPSTREAM_PATHS)
            else "catalog-semantics-simulator"
        ),
        "rows": rows,
    }


def schema_rejects_garbage(schema: dict[str, Any]) -> bool:
    try:
        import jsonschema
    except ImportError:
        return False
    garbage = [
        {},
        {"passing_tests": 999, "state": "SUCCESS"},
        {"unit_id": "WFA-0111", "state": "SUCCESS", "sentinel": "nope"},
    ]
    Validator = jsonschema.Draft7Validator
    for g in garbage:
        if Validator(schema).is_valid(g):
            return False
    return True


def schema_accepts(schema: dict[str, Any], doc: dict[str, Any]) -> bool:
    import jsonschema

    jsonschema.Draft7Validator(schema).validate(doc)
    return True
