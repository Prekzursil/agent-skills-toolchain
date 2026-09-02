#!/usr/bin/env python3
"""Smallest machine-checkable definitions for the eight CNL-0009 targets.

As-written spec text on this tree names the targets (and a few stopping
thresholds) but does not define identity, taxonomy, corpus, or admissibility.
These functions ARE those missing definitions, scoped to attacks a machine
can catch without a language model: duplicates, case/punct, token permutation,
out-of-taxonomy labels, empty categories, unfalsifiable objections, prose-only
counterexamples, and unresolvable evidence nodes.

Synonym rewrites and one-parameter forks that disagree across the two unique-idea
signals are residual (CNL-0051), not claimed solved here.
"""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

TARGETS = (
    "unique-idea",
    "category",
    "novelty",
    "diversity",
    "coverage",
    "objection",
    "counterexample",
    "evidence",
)

STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "for",
        "with",
        "on",
        "in",
        "by",
        "is",
        "be",
        "as",
        "at",
        "use",
        "using",
        "used",
    }
)
JACCARD_MERGE = 0.80
DIVERSITY_H_MIN = 0.90
DIVERSITY_J_MAX = 0.45
OBJECTION_KINDS = frozenset(
    {"counterexample", "missing-evidence", "contradiction"}
)

HERE = Path(__file__).resolve().parent


def nfkc(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def normalize(text: str) -> str:
    t = nfkc(text).casefold()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def stem(tok: str) -> str:
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def tokens(text: str) -> frozenset[str]:
    return frozenset(stem(t) for t in normalize(text).split() if t)


def content_tokens(text: str) -> tuple[str, ...]:
    return tuple(sorted(t for t in tokens(text) if t not in STOP and len(t) > 1))


def mechanism_slug(text: str) -> str:
    ct = content_tokens(text)
    return ":".join(ct) if ct else "empty"


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _parent(ideas: list[dict]) -> list[int]:
    return list(range(len(ideas)))


def _find(parent: list[int], i: int) -> int:
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def _union(parent: list[int], i: int, j: int) -> None:
    ri, rj = _find(parent, i), _find(parent, j)
    if ri != rj:
        parent[rj] = ri


def validate_idea(idea: dict, taxonomy: list[str] | None = None) -> dict:
    text = str(idea.get("text") or "")
    slug = mechanism_slug(text)
    claimed = str(idea.get("mechanism_id") or "").strip()
    id_ok = (not claimed) or claimed == slug
    cat = str(idea.get("category") or "").strip()
    cat_ok = True if taxonomy is None else cat in taxonomy
    valid = bool(text.strip()) and id_ok
    return {
        "text": text,
        "slug": slug,
        "claimed_mechanism_id": claimed or slug,
        "id_ok": id_ok,
        "category": cat,
        "cat_ok": cat_ok,
        "valid": valid,
        "tokens": tokens(text),
    }


def unique_idea_count(ideas: list[dict]) -> dict:
    rows = [validate_idea(i) for i in ideas]
    valid = [r for r in rows if r["valid"]]
    naive = len({str(i.get("text") or "") for i in ideas})
    slugs = {r["slug"] for r in valid}
    parent = _parent(valid)
    for i, a in enumerate(valid):
        for j in range(i + 1, len(valid)):
            if jaccard(a["tokens"], valid[j]["tokens"]) >= JACCARD_MERGE:
                _union(parent, i, j)
    clusters = { _find(parent, i) for i in range(len(valid)) }
    slug_n = len(slugs)
    jac_n = len(clusters)
    agree = slug_n == jac_n
    return {
        "naive_distinct_strings": naive,
        "valid_records": len(valid),
        "invalid_records": len(rows) - len(valid),
        "slug_count": slug_n,
        "jaccard_cluster_count": jac_n,
        "signals_agree": agree,
        "unique_count": slug_n if agree else None,
        "may_gate_stopping_rule": agree,
        "metric": slug_n if agree else 0,
    }


def category_attainment(ideas: list[dict], taxonomy: list[str], min_count: int = 1) -> dict:
    rows = [validate_idea(i, taxonomy) for i in ideas]
    valid = [r for r in rows if r["valid"] and r["cat_ok"]]
    counts = {c: 0 for c in taxonomy}
    for r in valid:
        counts[r["category"]] += 1
    naive_labels = sorted({str(i.get("category") or "") for i in ideas if i.get("category")})
    attained = [c for c, n in counts.items() if n >= min_count]
    empty = [c for c, n in counts.items() if n == 0]
    return {
        "taxonomy": list(taxonomy),
        "counts": counts,
        "attained": attained,
        "empty": empty,
        "naive_distinct_labels": naive_labels,
        "naive_label_count": len(naive_labels),
        "attained_count": len(attained),
        "metric": len(attained),
        "pass": len(empty) == 0 and len(attained) == len(taxonomy),
    }


def novelty_score(ideas: list[dict], prior_art_slugs: set[str]) -> dict:
    rows = [validate_idea(i) for i in ideas]
    valid = [r for r in rows if r["valid"]]
    naive = 0
    for idea, row in zip(ideas, rows):
        claimed = str(idea.get("mechanism_id") or row["slug"])
        if claimed not in prior_art_slugs:
            naive += 1
    novel = [r for r in valid if r["slug"] not in prior_art_slugs]
    known = [r for r in valid if r["slug"] in prior_art_slugs]
    return {
        "prior_art_size": len(prior_art_slugs),
        "naive_claimed_novel": naive,
        "operational_novel": len(novel),
        "operational_known": len(known),
        "invalid_records": len(rows) - len(valid),
        "metric": len(novel),
        "quality_separable": True,
    }


def diversity_score(ideas: list[dict], taxonomy: list[str]) -> dict:
    rows = [validate_idea(i, taxonomy) for i in ideas]
    valid = [r for r in rows if r["valid"] and r["cat_ok"]]
    unique_slugs: dict[str, dict] = {}
    for r in valid:
        unique_slugs.setdefault(r["slug"], r)
    uniq = list(unique_slugs.values())
    cat_counts = [sum(1 for r in uniq if r["category"] == c) for c in taxonomy]
    total = sum(cat_counts)
    if total == 0 or len(taxonomy) <= 1:
        h_norm = 0.0
    else:
        h = 0.0
        for n in cat_counts:
            if n:
                p = n / total
                h -= p * math.log(p)
        h_norm = h / math.log(len(taxonomy))
    pairs = []
    for i, a in enumerate(uniq):
        for b in uniq[i + 1 :]:
            pairs.append(jaccard(a["tokens"], b["tokens"]))
    mean_j = sum(pairs) / len(pairs) if pairs else 1.0
    naive = len({r["category"] for r in rows if r["category"]}) / max(len(taxonomy), 1)
    ok = h_norm >= DIVERSITY_H_MIN and mean_j <= DIVERSITY_J_MAX and len(uniq) >= 2
    return {
        "unique_mechanisms": len(uniq),
        "h_norm": round(h_norm, 6),
        "mean_pairwise_jaccard": round(mean_j, 6),
        "naive_label_fraction": round(naive, 6),
        "metric": round(min(h_norm, 1.0 - mean_j), 6),
        "pass": ok,
    }


def coverage_score(ideas: list[dict], taxonomy: list[str], min_count: int = 1) -> dict:
    att = category_attainment(ideas, taxonomy, min_count=min_count)
    n = len(taxonomy)
    ratio = (len(att["attained"]) / n) if n else 0.0
    naive_filled = len([i for i in ideas if i.get("text")])
    naive = 1.0 if naive_filled else 0.0
    return {
        **att,
        "coverage_ratio": ratio,
        "naive_aggregate_nonempty": naive,
        "metric": ratio,
        "pass": att["pass"],
        "fire_reason": (
            None
            if att["pass"]
            else f"empty_categories={att['empty']}"
        ),
    }


def objection_count(objections: list[dict], fixture_dir: Path | None = None) -> dict:
    admissible = []
    naive = len(objections)
    for ob in objections:
        kind = str(ob.get("kind") or "")
        target = str(ob.get("target_claim_id") or "").strip()
        payload = ob.get("payload") or {}
        sha = str(payload.get("sha256") or "").strip()
        rel = str(payload.get("path") or "").strip()
        path_ok = False
        sha_ok = False
        if fixture_dir is not None and rel:
            p = fixture_dir / rel
            if p.is_file():
                path_ok = True
                sha_ok = file_sha256(p) == sha
        elif sha and rel:
            # Allow in-memory fixtures: payload.bytes + sha256 agreement.
            raw = payload.get("bytes")
            if isinstance(raw, str):
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                path_ok = True
                sha_ok = digest == sha
        ok = (
            bool(target)
            and kind in OBJECTION_KINDS
            and bool(sha)
            and path_ok
            and sha_ok
        )
        if ok:
            admissible.append({"kind": kind, "target": target, "sha256": sha})
    return {
        "naive_count": naive,
        "admissible_count": len(admissible),
        "inadmissible_count": naive - len(admissible),
        "admissible": admissible,
        "metric": len(admissible),
    }


def counterexample_count(items: list[dict]) -> dict:
    real = []
    naive = len(items)
    unresolved = []
    for it in items:
        claim = str(it.get("claim_id") or "").strip()
        check = str(it.get("check_id") or "").strip()
        exp = it.get("expected_rc")
        obs = it.get("observed_rc")
        load_bearing = bool(it.get("load_bearing"))
        executable = (
            bool(claim)
            and bool(check)
            and isinstance(exp, int)
            and isinstance(obs, int)
            and exp != 0
        )
        if executable:
            rec = {
                "claim_id": claim,
                "check_id": check,
                "expected_rc": exp,
                "observed_rc": obs,
                "load_bearing": load_bearing,
            }
            real.append(rec)
            if load_bearing and obs != 0:
                unresolved.append(rec)
    return {
        "naive_count": naive,
        "executable_count": len(real),
        "unresolved_load_bearing": len(unresolved),
        "metric": len(real),
        "cleared": len(unresolved) == 0,
    }


def evidence_saturation(
    claims: list[dict],
    nodes: list[dict],
    fixture_dir: Path | None = None,
) -> dict:
    resolvable = []
    for node in nodes:
        rel = str(node.get("path") or "").strip()
        sha = str(node.get("sha256") or "").strip()
        raw = node.get("bytes")
        ok = False
        if fixture_dir is not None and rel:
            p = fixture_dir / rel
            if p.is_file() and sha and file_sha256(p) == sha:
                ok = True
        elif isinstance(raw, str) and sha:
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            ok = digest == sha
        if ok:
            resolvable.append(node)
    load_bearing = [c for c in claims if c.get("load_bearing")]
    covered = []
    missing = []
    res_ids = set()
    for n in resolvable:
        res_ids.update(n.get("claim_ids") or [])
    for c in load_bearing:
        cid = str(c.get("id") or "")
        if cid in res_ids:
            covered.append(cid)
        else:
            missing.append(cid)
    naive = len(nodes)
    sat = bool(load_bearing) and not missing
    return {
        "naive_node_count": naive,
        "resolvable_nodes": len(resolvable),
        "load_bearing_claims": len(load_bearing),
        "covered": covered,
        "missing": missing,
        "metric": len(resolvable),
        "saturation": sat,
        "pass": sat,
    }


def _payload(text: str) -> dict:
    raw = text
    return {
        "bytes": raw,
        "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
        "path": "memory://fixture",
    }


def taxonomy() -> list[str]:
    return ["mechanism", "protocol", "evidence", "failure-class"]


def prior_art() -> set[str]:
    return {mechanism_slug("hash map keyed cache")}


def good_run() -> dict[str, Any]:
    ideas = [
        {"text": "hash map keyed cache", "category": "mechanism"},
        {"text": "round robin speaking quota", "category": "protocol"},
        {"text": "content addressed receipt blob", "category": "evidence"},
        {"text": "planted empty category detector", "category": "failure-class"},
    ]
    pay = _payload("observed rc=1 on empty-category fixture")
    return {
        "ideas": ideas,
        "taxonomy": taxonomy(),
        "prior_art": sorted(prior_art()),
        "objections": [
            {
                "kind": "counterexample",
                "target_claim_id": "C-coverage",
                "payload": pay,
            }
        ],
        "counterexamples": [
            {
                "claim_id": "C-coverage",
                "check_id": "coverage.empty_category",
                "expected_rc": 1,
                "observed_rc": 0,
                "load_bearing": True,
            }
        ],
        "claims": [
            {"id": "C-coverage", "load_bearing": True},
            {"id": "C-unique", "load_bearing": True},
        ],
        "evidence_nodes": [
            {
                "id": "E1",
                "claim_ids": ["C-coverage", "C-unique"],
                **_payload("sha-backed coverage and unique-idea receipts"),
            }
        ],
    }


def bad_empty_category_run() -> dict[str, Any]:
    run = good_run()
    run = {
        **run,
        "ideas": [i for i in run["ideas"] if i["category"] != "failure-class"],
    }
    return run


def gaming_inputs() -> dict[str, Any]:
    """Adversary inputs: maximise a naive reading while failing intent."""
    base = "hash map keyed cache"
    paraphrases = [
        {"text": "Hash Map Keyed Cache"},
        {"text": "hash-map keyed cache!"},
        {"text": "cache keyed hash map"},
        {"text": "HASH MAP   keyed   cache"},
        {"text": "hash map keyed cache."},
        {"text": "keyed cache hash map"},
    ]
    fake_cat = [
        {"text": f"idea {i} about widgets", "category": "made-up-bucket"}
        for i in range(6)
    ]
    mint_ids = [
        {
            "text": "hash map keyed cache",
            "mechanism_id": f"brand-new-{i}",
            "category": "mechanism",
        }
        for i in range(4)
    ]
    label_cycle = []
    cats = taxonomy()
    for i, cat in enumerate(cats * 2):
        label_cycle.append(
            {
                "text": "hash map keyed cache",
                "category": cat,
                "mechanism_id": f"distinct-{i}",
            }
        )
    three_of_four = [
        {"text": "hash map keyed cache", "category": "mechanism"},
        {"text": "round robin speaking quota", "category": "protocol"},
        {"text": "content addressed receipt blob", "category": "evidence"},
        {"text": "another cache note", "category": "mechanism"},
        {"text": "yet another cache note", "category": "mechanism"},
    ]
    fake_obj = [
        {"kind": "vibes", "target_claim_id": "", "payload": {}}
        for _ in range(10)
    ]
    fake_cx = [
        {
            "claim_id": "",
            "check_id": "",
            "note": "this is a counterexample",
            "load_bearing": True,
        }
        for _ in range(8)
    ]
    fake_ev = [
        {
            "id": f"N{i}",
            "path": "",
            "sha256": "",
            "claim_ids": [f"N{(i + 1) % 12}"],
        }
        for i in range(12)
    ]
    return {
        "unique-idea": paraphrases,
        "category": fake_cat,
        "novelty": mint_ids,
        "diversity": label_cycle,
        "coverage": three_of_four,
        "objection": fake_obj,
        "counterexample": fake_cx,
        "evidence": fake_ev,
        "paraphrase_base": base,
    }


def evaluate_run(run: dict) -> dict:
    tax = list(run.get("taxonomy") or taxonomy())
    prior = set(run.get("prior_art") or [])
    ideas = list(run.get("ideas") or [])
    return {
        "unique-idea": unique_idea_count(ideas),
        "category": category_attainment(ideas, tax),
        "novelty": novelty_score(ideas, prior),
        "diversity": diversity_score(ideas, tax),
        "coverage": coverage_score(ideas, tax),
        "objection": objection_count(list(run.get("objections") or [])),
        "counterexample": counterexample_count(list(run.get("counterexamples") or [])),
        "evidence": evidence_saturation(
            list(run.get("claims") or []),
            list(run.get("evidence_nodes") or []),
        ),
    }


def evaluate_gaming() -> dict[str, Any]:
    g = gaming_inputs()
    tax = taxonomy()
    prior = prior_art()
    out: dict[str, Any] = {}
    ui = unique_idea_count(g["unique-idea"])
    out["unique-idea"] = {
        "intent": "100 distinct strings of one mechanism must not satisfy unique-idea",
        "naive_metric": ui["naive_distinct_strings"],
        "operational_metric": ui["metric"],
        "gamed_naive": ui["naive_distinct_strings"] > ui["metric"],
        "intent_held": ui["metric"] == 1 and ui["signals_agree"],
        "detail": ui,
    }
    cat = category_attainment(g["category"], tax)
    out["category"] = {
        "intent": "labels outside the declared taxonomy must not attain any bin",
        "naive_metric": cat["naive_label_count"],
        "operational_metric": cat["metric"],
        "gamed_naive": cat["naive_label_count"] > cat["metric"],
        "intent_held": cat["metric"] == 0 and not cat["pass"],
        "detail": cat,
    }
    nov = novelty_score(g["novelty"], prior)
    out["novelty"] = {
        "intent": "minted mechanism_id values that disagree with slug(text) are not novel",
        "naive_metric": nov["naive_claimed_novel"],
        "operational_metric": nov["metric"],
        "gamed_naive": nov["naive_claimed_novel"] > nov["metric"],
        "intent_held": nov["metric"] == 0,
        "detail": nov,
    }
    div = diversity_score(g["diversity"], tax)
    out["diversity"] = {
        "intent": "cycling category labels on one mechanism must not pass diversity",
        "naive_metric": div["naive_label_fraction"],
        "operational_metric": div["metric"],
        "gamed_naive": div["naive_label_fraction"] > div["metric"],
        "intent_held": not div["pass"],
        "detail": div,
    }
    cov = coverage_score(g["coverage"], tax)
    out["coverage"] = {
        "intent": "aggregate nonempty ideas must not PASS while a taxonomy bin is empty",
        "naive_metric": cov["naive_aggregate_nonempty"],
        "operational_metric": cov["metric"],
        "gamed_naive": cov["naive_aggregate_nonempty"] > cov["metric"],
        "intent_held": not cov["pass"] and "failure-class" in cov["empty"],
        "detail": cov,
    }
    obj = objection_count(g["objection"])
    out["objection"] = {
        "intent": "unfalsifiable 'I object' rows must not count",
        "naive_metric": obj["naive_count"],
        "operational_metric": obj["metric"],
        "gamed_naive": obj["naive_count"] > obj["metric"],
        "intent_held": obj["metric"] == 0,
        "detail": obj,
    }
    cx = counterexample_count(g["counterexample"])
    out["counterexample"] = {
        "intent": "prose-only counterexample notes must not count",
        "naive_metric": cx["naive_count"],
        "operational_metric": cx["metric"],
        "gamed_naive": cx["naive_count"] > cx["metric"],
        "intent_held": cx["metric"] == 0,
        "detail": cx,
    }
    ev = evidence_saturation(
        [{"id": "C-coverage", "load_bearing": True}],
        g["evidence"],
    )
    out["evidence"] = {
        "intent": "circular evidence nodes with no resolvable bytes must not saturate",
        "naive_metric": ev["naive_node_count"],
        "operational_metric": ev["metric"],
        "gamed_naive": ev["naive_node_count"] > ev["metric"],
        "intent_held": (not ev["pass"]) and ev["metric"] == 0,
        "detail": ev,
    }
    out["_all_attempts_recorded"] = list(TARGETS)
    out["_all_intent_held"] = all(out[t]["intent_held"] for t in TARGETS)
    out["_all_gamed_naive"] = all(out[t]["gamed_naive"] for t in TARGETS)
    return out


def both_states() -> dict[str, Any]:
    good = evaluate_run(good_run())
    bad = evaluate_run(bad_empty_category_run())
    silent_on_good = bool(good["coverage"]["pass"])
    fired_on_bad = (not bad["coverage"]["pass"]) and bool(
        bad["coverage"].get("fire_reason")
    )
    return {
        "check": "coverage_score empty-category detector",
        "silent_on_good": silent_on_good,
        "fired_on_bad": fired_on_bad,
        "good_reason": good["coverage"].get("fire_reason"),
        "bad_reason": bad["coverage"].get("fire_reason"),
        "good_coverage_ratio": good["coverage"]["coverage_ratio"],
        "bad_coverage_ratio": bad["coverage"]["coverage_ratio"],
        "good_unique": good["unique-idea"],
        "bad_empty": bad["coverage"]["empty"],
        "discriminates": silent_on_good and fired_on_bad,
        "negative_control": {
            "rejects": "a run that leaves a declared taxonomy category empty",
            "on_that_state": bad["coverage"].get("fire_reason"),
            "does_not_reject": "a run with every taxonomy category occupied by a valid idea",
            "good_state_output": f"pass={good['coverage']['pass']} reason={good['coverage'].get('fire_reason')}",
            "bad_state_output": f"pass={bad['coverage']['pass']} reason={bad['coverage'].get('fire_reason')}",
        },
    }


def operational_definitions() -> dict[str, dict]:
    return {
        "unique-idea": {
            "as_written_measurable": False,
            "reason": "Catalog quotes unique_ideas >= 100 but never defines when two idea records are the same idea.",
            "operational": (
                "Valid records only (mechanism_id omitted or equal to slug(text)). "
                "slug = sorted content tokens after NFKC/casefold/punct-strip/light-stem. "
                "Second signal: Jaccard >= 0.80 connected components on token sets. "
                "unique_count is defined iff the two counts agree; otherwise the stopping gate may not fire."
            ),
            "ungameable_against": "exact duplicates, case/punct/whitespace, token permutation, minted ids",
            "residual": "synonym rewrites and one-parameter forks where the two signals disagree (CNL-0051)",
        },
        "category": {
            "as_written_measurable": False,
            "reason": "No taxonomy T is declared in the cited spec files (absent) or in the CNL-0009 question.",
            "operational": (
                "Run config supplies a finite taxonomy of category ids. An idea attains a bin iff it is valid "
                "and idea.category is a member of T. Target is per-bin min_count, never an aggregate."
            ),
            "ungameable_against": "invented labels outside T",
            "residual": "who authors T is a protocol concern (CNL-0054)",
        },
        "novelty": {
            "as_written_measurable": False,
            "reason": "No prior-art corpus or comparison operator is written.",
            "operational": (
                "novelty count = number of valid slugs not in a declared prior-art slug set. "
                "Quality (test_passed) is a separate field and must not be inferred from novelty."
            ),
            "ungameable_against": "minted mechanism_id on already-known text",
            "residual": "near-paraphrase vs corpus without slug identity (CNL-0053)",
        },
        "diversity": {
            "as_written_measurable": False,
            "reason": "No formula, population, or threshold is written.",
            "operational": (
                "On unique slugs: H_norm = Shannon entropy of category histogram / log(|T|). "
                "Second signal: mean pairwise Jaccard. PASS iff H_norm >= 0.90 AND mean Jaccard <= 0.45 AND n>=2."
            ),
            "ungameable_against": "label cycling on one mechanism",
            "residual": "semantic spread beyond token Jaccard (CNL-0054)",
        },
        "coverage": {
            "as_written_measurable": False,
            "reason": "Spec never says whether coverage is per-category or aggregate (IMP-0301 names this exact hole).",
            "operational": (
                "coverage_ratio = |{c in T: count(c) >= min_count}| / |T|. PASS iff ratio == 1.0. "
                "An empty declared category forces FAIL."
            ),
            "ungameable_against": "aggregate-nonempty while a bin is empty",
            "residual": "none for the empty-bin game",
        },
        "objection": {
            "as_written_measurable": False,
            "reason": "no_new_objection_rounds is named later as a stopping conjunct; admissibility is undefined.",
            "operational": (
                "Admissible iff kind in {counterexample, missing-evidence, contradiction}, target_claim_id nonempty, "
                "and payload sha256 matches in-memory bytes or an on-disk fixture. Metric = admissible count."
            ),
            "ungameable_against": "empty 'I object' rows",
            "residual": "paraphrased restatement of the same payload (CNL-0079)",
        },
        "counterexample": {
            "as_written_measurable": False,
            "reason": "unresolved_load_bearing_counterexample is named later; no executable shape is written.",
            "operational": (
                "A counterexample is a record with claim_id, check_id, expected_rc != 0, and observed_rc int. "
                "Metric = executable count. Cleared iff no load-bearing row still has observed_rc != 0."
            ),
            "ungameable_against": "prose-only notes without a check and return code",
            "residual": "which checks are load-bearing (CNL-0068)",
        },
        "evidence": {
            "as_written_measurable": False,
            "reason": "evidence_saturation is named later as a boolean with no saturation predicate.",
            "operational": (
                "A node resolves iff sha256 matches payload bytes (or an on-disk file). "
                "Saturation iff every load-bearing claim id appears on at least one resolvable node."
            ),
            "ungameable_against": "circular nodes with no bytes/path",
            "residual": "freshness windows (not in this unit)",
        },
    }
