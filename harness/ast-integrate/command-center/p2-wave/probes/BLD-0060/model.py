#!/usr/bin/env python3
"""BLD-0060 instruments: catalog id scheme, reject-on-overlap merger, lexical Jaccard.

The near-duplicate detector is LEXICAL token-set Jaccard. Threshold is calibrated
once at n=100 and is never lowered to chase recall on full rewrites.
"""
from __future__ import annotations

import json
import platform
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

UNIT_ID = "BLD-0060"
ID_RE = re.compile(r"^([A-Z]{2,5})-(\d+)$")
TOKEN_RE = re.compile(r"[a-z0-9]+")
THRESHOLD = 0.70  # calibrated at n=100; retry_policy forbids lowering it
SCALES = (100, 20480)
N_PLANT = 5
SEED_SLIDE = 20  # every 20th sorted live unit -> 100-unit sample
SYNTH_POOL_SIZE = 2000
SYNTH_POOL_K = 25
SYNTH_NONCES = 3
SYNONYM = {
    "question": "query",
    "catalog": "register",
    "unit": "item",
    "detector": "scanner",
    "threshold": "cutoff",
    "merge": "fold",
    "duplicate": "copy",
    "lexical": "tokenwise",
    "council": "assembly",
    "verdict": "ruling",
    "evidence": "exhibit",
    "mechanism": "device",
    "sample": "subset",
    "precision": "purity",
    "recall": "coverage",
}


class MergeCollision(Exception):
    def __init__(self, unit_id: str, paths: list[str]) -> None:
        super().__init__(f"id-collision {unit_id} in {paths}")
        self.unit_id = unit_id
        self.paths = list(paths)


def hardware() -> dict[str, str]:
    return {
        "platform": f"{sys.platform} {platform.machine()} {platform.release()}",
        "python": sys.version.split()[0],
        "concurrency": "single-process inverted-index Jaccard; merger is CPU-only",
    }


def tokenize(text: str) -> frozenset[str]:
    return frozenset(t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 3)


def unit_text(unit: dict[str, Any]) -> str:
    inputs = unit.get("inputs")
    if isinstance(inputs, list):
        extra = " ".join(str(x) for x in inputs)
    else:
        extra = str(inputs or "")
    return " ".join(
        [
            str(unit.get("id") or ""),
            str(unit.get("title") or ""),
            str(unit.get("question_or_target") or unit.get("target") or ""),
            extra,
        ]
    )


def unit_tokens(unit: dict[str, Any]) -> frozenset[str]:
    return tokenize(unit_text(unit))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    inter = len(a & b)
    uni = len(a) + len(b) - inter
    return inter / uni if uni else 0.0


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def live_work_units(catalog: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = catalog if catalog is not None else load_catalog()
    units = doc.get("work_units") or []
    return [u for u in units if isinstance(u, dict) and u.get("id")]


def measure_id_scheme(units: list[dict[str, Any]]) -> dict[str, Any]:
    widths: dict[int, int] = defaultdict(int)
    prefixes: dict[str, dict[str, int]] = {}
    bad: list[str] = []
    for unit in units:
        uid = str(unit.get("id") or "")
        match = ID_RE.match(uid)
        if not match:
            bad.append(uid)
            continue
        prefix, digits = match.group(1), match.group(2)
        width = len(digits)
        widths[width] += 1
        rec = prefixes.setdefault(
            prefix, {"count": 0, "width": width, "min": 10**9, "max": -1}
        )
        rec["count"] += 1
        rec["width"] = width
        rec["min"] = min(rec["min"], int(digits))
        rec["max"] = max(rec["max"], int(digits))
    width_set = set(widths)
    observed_width = next(iter(width_set)) if len(width_set) == 1 else None
    per_prefix_capacity = 10 ** (observed_width or 0) if observed_width else None
    n_prefixes = len(prefixes)
    allocated = (per_prefix_capacity or 0) * n_prefixes
    tenx = {
        prefix: {
            "live_count": rec["count"],
            "live_max": rec["max"],
            "tenx_count": rec["count"] * 10,
            "tenx_max_if_dense": rec["max"] * 10,
            "fits_observed_width": rec["max"] * 10 < (per_prefix_capacity or 0),
        }
        for prefix, rec in prefixes.items()
    }
    single_prefix_fits_20480 = bool(
        per_prefix_capacity and (20480 < per_prefix_capacity)
    )
    multi_prefix_fits_20480 = allocated >= 20480
    all_tenx_fit = all(row["fits_observed_width"] for row in tenx.values())
    return {
        "n_units": len(units),
        "malformed_ids": bad,
        "digit_widths": {str(k): v for k, v in sorted(widths.items())},
        "observed_zero_padding_width": observed_width,
        "id_pattern": r"^[A-Z]{2,5}-[0-9]{4}$" if observed_width == 4 else None,
        "n_prefixes": n_prefixes,
        "per_prefix_capacity": per_prefix_capacity,
        "allocated_capacity": allocated,
        "single_prefix_accommodates_20480": single_prefix_fits_20480,
        "multi_prefix_accommodates_20480": multi_prefix_fits_20480,
        "tenx_each_prefix_fits_without_format_change": all_tenx_fit,
        "accommodates_20480_without_format_change": bool(
            multi_prefix_fits_20480 and all_tenx_fit
        ),
        "format_change_required_if_one_prefix_holds_20480": not single_prefix_fits_20480,
        "prefixes": {
            prefix: {k: rec[k] for k in ("count", "width", "min", "max")}
            for prefix, rec in sorted(prefixes.items())
        },
        "tenx_per_prefix": tenx,
    }


def merge_slices(
    slices: Iterable[tuple[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Fold slices into one unit list. Collision REJECTS; never silently dedups.

    Output is order-independent: slices sorted by path, units sorted by id.
    """
    ordered = sorted(((str(path), list(units)) for path, units in slices), key=lambda x: x[0])
    owners: dict[str, str] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for path, units in ordered:
        for unit in units:
            uid = str(unit.get("id") or "").strip()
            if not uid:
                raise MergeCollision("<blank>", [path])
            if uid in owners:
                raise MergeCollision(uid, [owners[uid], path])
            owners[uid] = path
            by_id[uid] = unit
    return [by_id[uid] for uid in sorted(by_id)]


def merge_silently_dedup(
    slices: Iterable[tuple[str, list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    """Anti-pattern control: last-writer wins. The real merger must not do this."""
    by_id: dict[str, dict[str, Any]] = {}
    for _path, units in slices:
        for unit in units:
            uid = str(unit.get("id") or "").strip()
            if uid:
                by_id[uid] = unit
    return [by_id[uid] for uid in sorted(by_id)]


def live_slices(units: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        key = str(unit.get("_source_slice_file") or "UNKNOWN.json")
        grouped[key].append(unit)
    return sorted(grouped.items())


def _synth_pool_indices(i: int) -> list[int]:
    acc = (i * 1103515245 + 12345) & 0x7FFFFFFF
    chosen: list[int] = []
    used: set[int] = set()
    while len(chosen) < SYNTH_POOL_K:
        acc = (acc * 1664525 + 1013904223) & 0xFFFFFFFF
        idx = acc % SYNTH_POOL_SIZE
        if idx not in used:
            used.add(idx)
            chosen.append(idx)
    return sorted(chosen)


def _synth_pool_bits(i: int) -> int:
    bits = 0
    for idx in _synth_pool_indices(i):
        bits |= 1 << idx
    return bits


def max_jaccard_bitsets(
    bit_ints: list[int], sizes: list[int], threshold: float, ids: list[str] | None = None
) -> dict[str, Any]:
    n = len(bit_ints)
    pair_count = n * (n - 1) // 2
    mx = 0.0
    arg = None
    above = 0
    for i in range(n):
        a = bit_ints[i]
        la = sizes[i]
        for j in range(i + 1, n):
            inter = (a & bit_ints[j]).bit_count()
            if not inter:
                continue
            uni = la + sizes[j] - inter
            jac = inter / uni if uni else 0.0
            if jac >= threshold:
                above += 1
            if jac > mx:
                mx = jac
                left = ids[i] if ids else i
                right = ids[j] if ids else j
                arg = (left, right, round(jac, 10))
    return {
        "n": n,
        "pair_count": pair_count,
        "clean_max_jaccard": mx,
        "above_threshold": above,
        "arg": arg,
    }


def max_jaccard_and_above(
    token_sets: list[frozenset[str]], threshold: float
) -> dict[str, Any]:
    """Complete inverted-index max + above-threshold count (pairs with empty
    intersection cannot be the max and cannot pass a positive threshold)."""
    n = len(token_sets)
    pair_count = n * (n - 1) // 2
    if n < 2:
        return {
            "n": n,
            "pair_count": pair_count,
            "clean_max_jaccard": 0.0,
            "above_threshold": 0,
            "arg": None,
        }
    postings: dict[str, list[int]] = defaultdict(list)
    sizes = [len(s) for s in token_sets]
    for i, tokens in enumerate(token_sets):
        for tok in tokens:
            postings[tok].append(i)
    mx = 0.0
    arg = None
    above = 0
    for i, tokens in enumerate(token_sets):
        seen: set[int] = set()
        cands: list[int] = []
        for tok in tokens:
            for j in postings[tok]:
                if j > i and j not in seen:
                    seen.add(j)
                    cands.append(j)
        la = sizes[i]
        for j in cands:
            inter = len(tokens & token_sets[j])
            uni = la + sizes[j] - inter
            jac = inter / uni if uni else 0.0
            if jac >= threshold:
                above += 1
            if jac > mx:
                mx = jac
                arg = (i, j, round(jac, 10))
    return {
        "n": n,
        "pair_count": pair_count,
        "clean_max_jaccard": mx,
        "above_threshold": above,
        "arg": arg,
    }


def sample_n100(units: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(units, key=lambda u: str(u.get("id") or ""))
    picked = ordered[::SEED_SLIDE]
    if len(picked) < 100:
        picked = ordered[:100]
    return picked[:100]


def make_synth(i: int) -> dict[str, Any]:
    """Distinct synthetic unit: 25-subset of reserved pool + 3 unique nonces.

    Title/question carry ONLY reserved tokens so the synth vocab is disjoint
    from the live English catalog (proven, not assumed).
    """
    chosen = _synth_pool_indices(i)
    pool = [f"synw{idx:04d}" for idx in chosen]
    nonces = [f"zxq{k}{i:05d}" for k in range(SYNTH_NONCES)]
    return {
        "id": f"q{i:05d}",
        "title": " ".join(nonces),
        "question_or_target": " ".join(pool),
        "inputs": pool,
        "_synthetic": True,
    }


def scale_corpus(
    live: list[dict[str, Any]], n: int
) -> tuple[list[dict[str, Any]], str]:
    if n <= len(live):
        return sample_n100(live) if n == 100 else live[:n], "live-sample"
    out = list(live)
    need = n - len(live)
    out.extend(make_synth(i) for i in range(need))
    return out, "live-plus-reserved-synth"


def exact_rename(parent: dict[str, Any], k: int) -> dict[str, Any]:
    uid = str(parent.get("id") or "UNK-0000")
    return {
        "id": f"RENM-{k:04d}",
        "title": str(parent.get("title") or ""),
        "question_or_target": str(
            parent.get("question_or_target") or parent.get("target") or ""
        ),
        "inputs": list(parent.get("inputs") or [])
        if isinstance(parent.get("inputs"), list)
        else parent.get("inputs"),
        "_plant_class": "exact_rename",
        "_parent": uid,
    }


def paraphrase(parent: dict[str, Any], k: int) -> dict[str, Any]:
    text = unit_text(parent)
    tokens = [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 3]
    replaced = 0
    out: list[str] = []
    for tok in tokens:
        if replaced < max(4, len(tokens) // 10) and tok in SYNONYM:
            out.append(SYNONYM[tok])
            replaced += 1
        else:
            out.append(tok)
    # If the parent used none of the synonym keys, swap a trailing slice for
    # stable paraphrase tokens that still overlap heavily.
    if replaced < 4 and len(out) >= 8:
        tail = out[-4:]
        out = out[:-4] + [f"para{k}{i}" for i, _ in enumerate(tail)]
    return {
        "id": f"PARA-{k:04d}",
        "title": " ".join(out[:12]),
        "question_or_target": " ".join(out),
        "inputs": [],
        "_plant_class": "paraphrase",
        "_parent": str(parent.get("id") or ""),
    }


def full_rewrite(parent: dict[str, Any], k: int) -> dict[str, Any]:
    tokens = sorted(unit_tokens(parent))
    cipher = [f"rwx{k:02d}{i:05d}" for i, _tok in enumerate(tokens)]
    return {
        "id": f"RWRT-{k:04d}",
        "title": " ".join(cipher[:8]),
        "question_or_target": " ".join(cipher),
        "inputs": cipher[:6],
        "_plant_class": "full_rewrite",
        "_parent": str(parent.get("id") or ""),
    }


def one_parameter_fork(parent: dict[str, Any], k: int) -> dict[str, Any]:
    text = unit_text(parent)
    swapped, nsub = re.subn(r"\d+", lambda m: str(int(m.group(0)) + 1 + k), text, count=1)
    if nsub == 0:
        swapped = text + f" parameter-fork-{k+1}"
    return {
        "id": f"FORK-{k:04d}",
        "title": str(parent.get("title") or "") + f" fork-{k}",
        "question_or_target": swapped,
        "inputs": parent.get("inputs") if isinstance(parent.get("inputs"), list) else [],
        "_plant_class": "one_parameter_fork",
        "_parent": str(parent.get("id") or ""),
    }


def whitespace_variant(parent: dict[str, Any], k: int) -> dict[str, Any]:
    title = "  ".join(str(parent.get("title") or "").split())
    q = " \n ".join(
        str(parent.get("question_or_target") or parent.get("target") or "").split()
    )
    return {
        "id": f"WSPC-{k:04d}",
        "title": title,
        "question_or_target": q,
        "inputs": parent.get("inputs") if isinstance(parent.get("inputs"), list) else [],
        "_plant_class": "whitespace_variant",
        "_parent": str(parent.get("id") or ""),
    }


PLANT_BUILDERS = {
    "exact_rename": exact_rename,
    "paraphrase": paraphrase,
    "full_rewrite": full_rewrite,
}


def plant_mutants(
    base: list[dict[str, Any]], n_plant: int = N_PLANT
) -> list[dict[str, Any]]:
    parents = base[:n_plant]
    planted: list[dict[str, Any]] = []
    for k, parent in enumerate(parents):
        for _cls, builder in PLANT_BUILDERS.items():
            planted.append(builder(parent, k))
    return planted


def firing_table(
    base: list[dict[str, Any]], planted: list[dict[str, Any]], threshold: float
) -> dict[str, Any]:
    parent_tok = {str(u.get("id")): unit_tokens(u) for u in base}
    by_class: dict[str, list[float]] = defaultdict(list)
    fired_by_class: dict[str, int] = defaultdict(int)
    rows = []
    for mutant in planted:
        cls = str(mutant.get("_plant_class") or "unknown")
        parent_id = str(mutant.get("_parent") or "")
        score = jaccard(unit_tokens(mutant), parent_tok[parent_id])
        fired = score >= threshold
        by_class[cls].append(score)
        fired_by_class[cls] += int(fired)
        rows.append(
            {
                "id": mutant.get("id"),
                "class": cls,
                "parent": parent_id,
                "jaccard": round(score, 10),
                "fired": fired,
            }
        )
    rates = {}
    for cls, scores in by_class.items():
        rates[cls] = {
            "n": len(scores),
            "fired": fired_by_class[cls],
            "firing_rate": fired_by_class[cls] / len(scores) if scores else 0.0,
            "min_jaccard": min(scores),
            "max_jaccard": max(scores),
            "mean_jaccard": sum(scores) / len(scores),
        }
    in_scope = ["exact_rename", "paraphrase"]
    tp = sum(fired_by_class[c] for c in in_scope)
    in_scope_n = sum(len(by_class[c]) for c in in_scope)
    rewrite_n = len(by_class.get("full_rewrite") or [])
    rewrite_fired = fired_by_class.get("full_rewrite", 0)
    return {
        "rows": rows,
        "by_class": rates,
        "true_positives_in_scope": tp,
        "in_scope_n": in_scope_n,
        "rewrite_n": rewrite_n,
        "rewrite_fired": rewrite_fired,
    }


def precision_recall(
    clean: dict[str, Any], plants: dict[str, Any], extra_above: int = 0
) -> dict[str, Any]:
    """Precision against the planted-mutant set plus clean above-threshold pairs.

    extra_above counts above-threshold pairs that are neither clean-base nor
    in-scope plants (should stay 0). Rewrite fires are not in-scope TPs.
    """
    fp = int(clean["above_threshold"]) + extra_above + int(plants["rewrite_fired"])
    tp = int(plants["true_positives_in_scope"])
    in_scope_n = int(plants["in_scope_n"])
    all_dup_n = in_scope_n + int(plants["rewrite_n"])
    precision = tp / (tp + fp) if (tp + fp) else None
    recall_in_scope = tp / in_scope_n if in_scope_n else None
    recall_all_classes = tp / all_dup_n if all_dup_n else None
    return {
        "true_positives": tp,
        "false_positives": fp,
        "precision": precision,
        "recall_in_scope_rename_and_paraphrase": recall_in_scope,
        "recall_including_full_rewrite_as_positive": recall_all_classes,
        "rewrite_treated_as_false_positive_if_it_fires": True,
    }


def measure_scale(live: list[dict[str, Any]], n: int, threshold: float) -> dict[str, Any]:
    base, origin = scale_corpus(live, n)
    planted = plant_mutants(base, N_PLANT)
    live_part = [u for u in base if not u.get("_synthetic")]
    synth_part = [u for u in base if u.get("_synthetic")]
    live_clean = max_jaccard_and_above([unit_tokens(u) for u in live_part], threshold)
    live_arg = None
    if live_clean.get("arg"):
        i, j, score = live_clean["arg"]
        live_arg = (str(live_part[i].get("id")), str(live_part[j].get("id")), score)
    synth_clean = {
        "n": 0,
        "pair_count": 0,
        "clean_max_jaccard": 0.0,
        "above_threshold": 0,
        "arg": None,
    }
    if synth_part:
        n_synth = len(synth_part)
        # Nonces and ids are unique per synth, so token intersection == pool
        # intersection. Size is pool + nonces + id token.
        synth_size = SYNTH_POOL_K + SYNTH_NONCES + 1
        bits = [_synth_pool_bits(i) for i in range(n_synth)]
        sizes = [synth_size] * n_synth
        ids = [str(u.get("id")) for u in synth_part]
        synth_clean = max_jaccard_bitsets(bits, sizes, threshold, ids)
    if synth_clean["clean_max_jaccard"] > live_clean["clean_max_jaccard"]:
        mx = synth_clean["clean_max_jaccard"]
        arg_ids = synth_clean["arg"]
        max_source = "synth-synth"
    else:
        mx = live_clean["clean_max_jaccard"]
        arg_ids = live_arg
        max_source = "live-live"
    above = int(live_clean["above_threshold"]) + int(synth_clean["above_threshold"])
    pair_count = len(base) * (len(base) - 1) // 2
    clean = {
        "n": len(base),
        "pair_count": pair_count,
        "clean_max_jaccard": mx,
        "above_threshold": above,
        "arg": arg_ids,
    }
    plants = firing_table(base, planted, threshold)
    pr = precision_recall(clean, plants)
    return {
        "n": n,
        "origin": origin,
        "n_base": len(base),
        "n_live_in_base": len(live_part),
        "n_synth_in_base": len(synth_part),
        "n_with_plants": len(base) + len(planted),
        "pair_count": pair_count,
        "clean_max_jaccard": mx,
        "clean_max_pair": arg_ids,
        "clean_max_source": max_source,
        "clean_above_threshold": above,
        "live_clean_max_jaccard": live_clean["clean_max_jaccard"],
        "synth_clean_max_jaccard": synth_clean["clean_max_jaccard"],
        "threshold": threshold,
        "plants": plants,
        "precision_recall": pr,
        "clean_max_below_threshold": mx < threshold,
    }


def extra_mutant_shapes(
    live: list[dict[str, Any]], threshold: float
) -> list[dict[str, Any]]:
    parents = sample_n100(live)[:N_PLANT]
    out = []
    for shape, builder in (
        ("one_parameter_fork", one_parameter_fork),
        ("whitespace_variant", whitespace_variant),
    ):
        scores = []
        fired = 0
        for k, parent in enumerate(parents):
            mutant = builder(parent, k)
            score = jaccard(unit_tokens(mutant), unit_tokens(parent))
            scores.append(score)
            fired += int(score >= threshold)
        out.append(
            {
                "shape": shape,
                "n": len(scores),
                "fired": fired,
                "firing_rate": fired / len(scores) if scores else 0.0,
                "min_jaccard": min(scores) if scores else 0.0,
                "max_jaccard": max(scores) if scores else 0.0,
            }
        )
    return out


def vocab_disjoint_proof(
    live: list[dict[str, Any]], n_synth: int
) -> dict[str, Any]:
    real = set()
    for unit in live:
        real |= unit_tokens(unit)
    synth = set()
    for i in range(n_synth):
        synth |= unit_tokens(make_synth(i))
    inter = real & synth
    return {
        "real_vocab": len(real),
        "synth_vocab": len(synth),
        "intersection": sorted(inter)[:20],
        "intersection_size": len(inter),
        "disjoint": not inter,
    }


def run_merger_controls(live: list[dict[str, Any]]) -> dict[str, Any]:
    slices = live_slices(live)
    # Positive: live slice merge is unique-id (catalog already unique).
    merged = merge_slices(slices)
    live_ids = sorted(str(u["id"]) for u in live)
    merged_ids = [str(u["id"]) for u in merged]
    positive_ok = merged_ids == live_ids

    a = [("slice-a.json", live[:3]), ("slice-b-disjoint.json", live[3:6])]
    disjoint = merge_slices(a)
    swapped = merge_slices(list(reversed(a)))
    order_independent = [str(u["id"]) for u in disjoint] == [
        str(u["id"]) for u in swapped
    ]

    overlap_payload = [
        ("slice-a.json", live[:3]),
        ("slice-b-overlap.json", [live[0], live[4]]),
    ]
    collision = None
    try:
        merge_slices(overlap_payload)
        rejected = False
    except MergeCollision as exc:
        rejected = True
        collision = {"id": exc.unit_id, "paths": exc.paths}

    silent = merge_silently_dedup(overlap_payload)
    # Real merger rejected; silent path would have produced 4 ids (0,1,2,4).
    return {
        "live_slice_count": len(slices),
        "live_merge_id_count": len(merged),
        "live_merge_matches_catalog": positive_ok,
        "disjoint_accepted": len(disjoint) == 6,
        "order_independent": order_independent,
        "overlap_rejected": rejected,
        "collision": collision,
        "silent_dedup_would_accept": len(silent) == 4,
        "silent_dedup_is_not_the_merger": rejected and len(silent) == 4,
        "negative_control_overlap_fires": rejected,
        "negative_control_disjoint_silent": len(disjoint) == 6,
    }


def measure_all() -> dict[str, Any]:
    live = live_work_units()
    scheme = measure_id_scheme(live)
    merger = run_merger_controls(live)
    n_synth = 20480 - len(live)
    disjoint = vocab_disjoint_proof(live, n_synth)
    scales = {}
    for n in SCALES:
        scales[str(n)] = measure_scale(live, n, THRESHOLD)
    extra = extra_mutant_shapes(live, THRESHOLD)
    # Real-vs-synth pairs are Jaccard 0 when vocabs are disjoint, so they
    # cannot raise the 20480 clean max above the real-only max except via synth-synth.
    return {
        "threshold": THRESHOLD,
        "id_scheme": scheme,
        "merger": merger,
        "vocab_disjoint": disjoint,
        "scales": scales,
        "additional_mutant_shapes": extra,
        "silent_class": "full_rewrite",
        "detector_scope": (
            "LEXICAL token-set Jaccard over id+title+question_or_target+inputs. "
            "A full semantic rewrite lands in the same score band as a genuinely "
            "distinct entry; the detector is silent on that class."
        ),
        "hardware": hardware(),
        "n_live": len(live),
    }
