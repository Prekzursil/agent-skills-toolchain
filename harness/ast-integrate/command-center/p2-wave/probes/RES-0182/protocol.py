#!/usr/bin/env python3
"""RES-0182 structured elicitation engine.

Reference-class framing, independent priors, calibration weighting, aggregation.
Elicited values are never promoted to measured values.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import zlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center/research/sources-frontier/"
    "RES-0182-expert-elicitation-as-a-source-class.json"
)
SCHEMA = HERE / "design-spec.schema.json"
QUESTIONS = HERE / "questions.json"
PARTICIPANTS = HERE / "participants.json"
INDEX = HERE / "sources_index.json"
SENTINEL = "SUCCESS:RES-0182"
UNIT = "RES-0182"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
BANDS = {
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
}
IDEA_STAGES = ("investigate", "discuss", "estimate", "aggregate")
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0182/probe1_recompute.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0182/probe2_negative_control.py"
)
REL_ERR_HIT = 0.25


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_index() -> dict[str, dict]:
    rows = load_json(INDEX) if INDEX.is_file() else []
    out: dict[str, dict] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("ok") and row.get("id"):
            out[str(row["id"])] = row
    return out


def snapshot_bytes(source_id: str, index: dict[str, dict] | None = None) -> bytes:
    index = index if index is not None else snapshot_index()
    row = index.get(source_id)
    if not row:
        raise FileNotFoundError(source_id)
    path = HERE / str(row["path"])
    raw = path.read_bytes()
    if sha256_bytes(raw) != str(row.get("sha256") or ""):
        raise ValueError(f"snapshot-hash-drift:{source_id}")
    return raw


def decode_snapshot(raw: bytes) -> str:
    for enc in ("utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def inflate_pdf(raw: bytes) -> str:
    chunks: list[bytes] = []
    for match in re.finditer(rb"stream\r?\n", raw):
        start = match.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        blob = raw[start:end]
        if blob.endswith(b"\r\n"):
            blob = blob[:-2]
        elif blob.endswith(b"\n"):
            blob = blob[:-1]
        for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
            try:
                chunks.append(zlib.decompress(blob, wbits))
                break
            except zlib.error:
                continue
    return b"\n".join(chunks).decode("latin-1", "replace")


def idea_stage_count(raw: bytes) -> int:
    text = decode_snapshot(raw).lower()
    present = [s for s in IDEA_STAGES if s in text]
    if len(present) < 4:
        raise ValueError(f"idea-stages-incomplete:{present}")
    return 4


def _has_cooke_triple(text: str) -> bool:
    if re.search(
        r"3 quantiles.{0,80}5%\s*,\s*50%.{0,20}95%",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        return True
    if re.search(r"typically 5%\s*,\s*50%\s*and\s*95%", text, flags=re.IGNORECASE):
        return True
    return False


def cooke_quantile_count(raw: bytes) -> int:
    text = decode_snapshot(raw)
    if _has_cooke_triple(text):
        return 3
    if raw.startswith(b"%PDF") and _has_cooke_triple(inflate_pdf(raw)):
        return 3
    raise ValueError("cooke-quantile-triple-absent")


EXTRACTORS = {
    "idea_stage_count": idea_stage_count,
    "cooke_quantile_count": cooke_quantile_count,
}


def literature_truth(qid: str, spec: dict, index: dict[str, dict]) -> dict:
    extractor_name = str(spec.get("extractor") or "")
    fn = EXTRACTORS[extractor_name]
    values = []
    used = []
    for sid in spec.get("source_ids") or []:
        if sid not in index:
            continue
        raw = snapshot_bytes(sid, index)
        values.append(fn(raw))
        used.append(sid)
    if len(values) < 2:
        raise ValueError(f"literature-unresolved:{qid}")
    if len(set(values)) != 1:
        raise ValueError(f"literature-disagreement:{qid}:{values}")
    return {
        "question_id": qid,
        "truth": float(values[0]),
        "source_ids": used,
        "extractor": extractor_name,
        "evidence_tier": "MEASURED-FROM-FETCHED-BYTES",
    }


def interval_contains(q05: float, q95: float, truth: float) -> bool:
    lo, hi = (q05, q95) if q05 <= q95 else (q95, q05)
    return lo <= truth <= hi


def relative_error(point: float, truth: float) -> float:
    denom = max(abs(truth), 1.0)
    return abs(point - truth) / denom


def seed_hit(est: dict, truth: float) -> bool:
    return interval_contains(float(est["q05"]), float(est["q95"]), truth)


def calibration_row(participant: dict, seeds: list[dict]) -> dict:
    hits = 0
    widths: list[float] = []
    for seed in seeds:
        sid = seed["id"]
        est = (participant.get("calibration") or {}).get(sid)
        if not isinstance(est, dict):
            continue
        truth = float(seed["truth"])
        if seed_hit(est, truth):
            hits += 1
        width = abs(float(est["q95"]) - float(est["q05"]))
        widths.append(width / max(abs(truth), 1.0))
    n = max(len(seeds), 1)
    cal = hits / n
    info = 1.0 / (1.0 + (sum(widths) / max(len(widths), 1)))
    weight = cal * info
    return {
        "participant_id": participant["id"],
        "hits": hits,
        "n_seeds": n,
        "calibration_score": round(cal, 6),
        "information_score": round(info, 6),
        "cooke_weight": round(weight, 6),
        "discounted": cal < 0.5,
    }


def weighted_average(pairs: list[tuple[float, float]]) -> float:
    num = sum(v * w for v, w in pairs)
    den = sum(w for _, w in pairs)
    if den <= 0:
        return sum(v for v, _ in pairs) / max(len(pairs), 1)
    return num / den


def median(values: list[float]) -> float:
    seq = sorted(values)
    n = len(seq)
    if n == 0:
        raise ValueError("empty-median")
    mid = n // 2
    if n % 2:
        return seq[mid]
    return 0.5 * (seq[mid - 1] + seq[mid])


def aggregate_question(
    qid: str,
    participants: list[dict],
    weights: dict[str, dict],
) -> dict:
    q05s, q50s, q95s = [], [], []
    weighted_q05, weighted_q50, weighted_q95 = [], [], []
    rows = []
    for p in participants:
        est = (p.get("estimates") or {}).get(qid)
        if not isinstance(est, dict):
            continue
        q05, q50, q95 = float(est["q05"]), float(est["q50"]), float(est["q95"])
        cal = weights[p["id"]]
        q05s.append(q05)
        q50s.append(q50)
        q95s.append(q95)
        w = 0.0 if cal["discounted"] else float(cal["cooke_weight"])
        weighted_q05.append((q05, w))
        weighted_q50.append((q50, w))
        weighted_q95.append((q95, w))
        rows.append(
            {
                "participant_id": p["id"],
                "q05": q05,
                "q50": q50,
                "q95": q95,
                "calibration_score": cal["calibration_score"],
                "cooke_weight": cal["cooke_weight"],
                "discounted": cal["discounted"],
                "evidence_tier": "ELICITED-NOT-MEASURED",
            }
        )
    if len(rows) < 2:
        raise ValueError(f"too-few-participants:{qid}")
    eq = {
        "q05": median(q05s),
        "q50": median(q50s),
        "q95": median(q95s),
        "rule": "equal-weight-median-of-quantiles",
    }
    active = [pair for pair in weighted_q50 if pair[1] > 0]
    if not active:
        ck = dict(eq)
        ck["rule"] = "cooke-fallback-equal-weight-all-discounted"
    else:
        ck = {
            "q05": weighted_average(weighted_q05),
            "q50": weighted_average(weighted_q50),
            "q95": weighted_average(weighted_q95),
            "rule": "cooke-calibration-times-information-linear-pool",
        }
    return {
        "question_id": qid,
        "n_participants": len(rows),
        "participant_rows": rows,
        "equal_weight": eq,
        "cooke_weight": ck,
        "evidence_tier": "ELICITED-NOT-MEASURED",
        "promoted_to_measured": False,
    }


def local_truths() -> dict[str, float]:
    frontier = REPO / "command-center/research/sources-frontier"
    n_frontier = 0
    if frontier.is_dir():
        for path in frontier.glob("*.json"):
            if path.name.startswith("RES-0182"):
                continue
            n_frontier += 1
    schema = REPO / "command-center/schema/design-spec.schema.json"
    present = 1.0 if schema.is_file() and schema.stat().st_size > 0 else 0.0
    catalog = REPO / "command-center/WORK-UNIT-CATALOG.json"
    catalog_bytes = float(catalog.stat().st_size) if catalog.is_file() else math.nan
    n_018x = 0.0
    if catalog.is_file():
        doc = load_json(catalog)
        for unit in doc.get("work_units") or []:
            uid = str(unit.get("id") or "")
            if re.fullmatch(r"RES-018[0-9]", uid):
                n_018x += 1.0
    probes = REPO / "command-center/p2-wave/probes"
    n_probe = 0.0
    if probes.is_dir():
        for path in probes.iterdir():
            if path.is_dir() and path.name.startswith("RES-") and path.name != UNIT:
                n_probe += 1.0
    claim_schema = REPO / "command-center/schema/research-claim-record.schema.json"
    n_lines = 0.0
    if claim_schema.is_file():
        text = claim_schema.read_text(encoding="utf-8")
        n_lines = float(text.count("\n") + (0 if text.endswith("\n") else 1))
    return {
        "NL-1": float(n_frontier),
        "NL-2": present,
        "NL-3": catalog_bytes,
        "NL-4": n_018x,
        "NL-5": n_probe,
        "NL-6": n_lines,
    }


def score_against_truth(agg: dict, truth: float, truth_kind: str) -> dict:
    eq = agg["equal_weight"]
    ck = agg["cooke_weight"]
    eq_hit = interval_contains(eq["q05"], eq["q95"], truth)
    ck_hit = interval_contains(ck["q05"], ck["q95"], truth)
    eq_err = relative_error(eq["q50"], truth)
    ck_err = relative_error(ck["q50"], truth)
    median_hit = eq_err <= REL_ERR_HIT
    miss = (not eq_hit) and (not median_hit)
    return {
        "truth": truth,
        "truth_kind": truth_kind,
        "equal_weight_interval_hit": eq_hit,
        "cooke_interval_hit": ck_hit,
        "equal_weight_rel_error": round(eq_err, 6),
        "cooke_rel_error": round(ck_err, 6),
        "median_within_25pct": median_hit,
        "miss": miss,
        "evidence_tier_of_estimate": "ELICITED-NOT-MEASURED",
        "evidence_tier_of_truth": (
            "MEASURED-FROM-FETCHED-BYTES"
            if truth_kind == "literature"
            else "MEASURED-FROM-WORKTREE"
        ),
    }


def run_protocol() -> dict:
    qdoc = load_json(QUESTIONS)
    pdoc = load_json(PARTICIPANTS)
    index = snapshot_index()
    participants = list(pdoc.get("participants") or [])
    seeds = list(qdoc.get("calibration_seeds") or [])
    weights = {p["id"]: calibration_row(p, seeds) for p in participants}
    local = local_truths()
    lit_specs = {row["id"]: row for row in qdoc.get("literature_controls") or []}
    nl_ids = [row["id"] for row in qdoc.get("no_literature") or []]
    lit_ids = [row["id"] for row in qdoc.get("literature_controls") or []]

    aggregations = {}
    for qid in nl_ids + lit_ids:
        aggregations[qid] = aggregate_question(qid, participants, weights)

    lit_truths = {qid: literature_truth(qid, lit_specs[qid], index) for qid in lit_ids}

    nl_scores = {}
    nl_hits = 0
    for qid in nl_ids:
        score = score_against_truth(aggregations[qid], local[qid], "local-worktree")
        nl_scores[qid] = score
        if not score["miss"]:
            nl_hits += 1
        aggregations[qid]["score"] = score
        aggregations[qid]["search_baseline"] = "NOT-FOUND"
        aggregations[qid]["adds_measured_evidence_over_not_found"] = False
        aggregations[qid]["adds_labeled_prior_over_not_found"] = True
        aggregations[qid]["interval_covers_local_truth"] = not score["miss"]

    lit_scores = {}
    lit_misses = 0
    for qid in lit_ids:
        truth = float(lit_truths[qid]["truth"])
        score = score_against_truth(aggregations[qid], truth, "literature")
        score["source_ids"] = lit_truths[qid]["source_ids"]
        lit_scores[qid] = score
        if score["miss"]:
            lit_misses += 1
        aggregations[qid]["score"] = score
        aggregations[qid]["search_baseline"] = "FOUND"
        aggregations[qid]["literature_truth"] = lit_truths[qid]

    if lit_misses:
        adoption = "WEAK"
        adoption_reason = (
            "Blind elicitation missed at least one known literature answer; "
            "the mode is reported as WEAK rather than ADOPTED."
        )
    elif nl_hits >= 4:
        adoption = "CONDITIONAL"
        adoption_reason = (
            "Literature controls were hit and most unpublished questions' "
            "intervals covered later local measurements; still not ADOPTED as "
            "a measured source class."
        )
    else:
        adoption = "WEAK"
        adoption_reason = (
            "Literature controls did not miss, but unpublished elicitation "
            "did not cover local measurements often enough to adopt the mode."
        )

    beats_search = False
    return {
        "weights": weights,
        "aggregations": aggregations,
        "local_truths": local,
        "literature_truths": lit_truths,
        "nl_ids": nl_ids,
        "lit_ids": lit_ids,
        "nl_hits": nl_hits,
        "nl_n": len(nl_ids),
        "lit_misses": lit_misses,
        "lit_n": len(lit_ids),
        "adoption": adoption,
        "adoption_reason": adoption_reason,
        "beats_search_as_source_class": beats_search,
        "elicited_promoted_to_measured": False,
        "participants": participants,
        "seeds": seeds,
        "index": index,
    }


def quote_in_snapshot(source_id: str, quote: str, index: dict[str, dict]) -> bool:
    raw = snapshot_bytes(source_id, index)
    if quote.encode("utf-8") in raw or quote.encode("latin-1", "replace") in raw:
        return True
    if quote in decode_snapshot(raw):
        return True
    if raw.startswith(b"%PDF") and quote in inflate_pdf(raw):
        return True
    return False


def lineage_ok(entry: dict, index: dict[str, dict]) -> str | None:
    url = str(entry.get("resolved_url") or "")
    ts = str(entry.get("fetched_at") or "")
    digest = str(entry.get("sha256_fetched_bytes") or "")
    sid = str(entry.get("source_id") or "")
    quote = str(entry.get("quote") or "")
    if not url.startswith("http"):
        return "lineage-url"
    if len(ts) < 20:
        return "lineage-timestamp"
    if len(digest) != 64:
        return "lineage-sha256"
    row = index.get(sid)
    if not row:
        return f"lineage-source-missing:{sid}"
    if str(row.get("sha256")) != digest:
        return f"lineage-sha-mismatch:{sid}"
    known = {
        str(row.get("resolved_url") or ""),
        str(row.get("requested_url") or ""),
    }
    if url not in known:
        return f"lineage-url-mismatch:{sid}"
    if len(quote) < 12:
        return "lineage-quote-short"
    if not quote_in_snapshot(sid, quote, index):
        return f"lineage-quote-absent:{sid}"
    return None


def required_protocol_steps(doc: dict) -> list[str]:
    missing = []
    steps = doc.get("protocol") or {}
    need = [
        "reference_class_framing",
        "independent_priors",
        "calibration_questions",
        "aggregation",
    ]
    for key in need:
        blob = steps.get(key)
        if not isinstance(blob, dict) or len(str(blob.get("description") or "")) < 24:
            missing.append(f"protocol-step:{key}")
    return missing


def evaluate(doc: dict) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {"pass": False, "errors": ["not-object"]}
    if str(doc.get("unit_id") or "") != UNIT:
        errors.append("unit_id")
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        errors.append(f"self-declared:{doc.get('state')}")
    if SENTINEL not in json.dumps(doc, ensure_ascii=False):
        errors.append("sentinel-absent")
    if str(doc.get("kind") or "") != "design-spec":
        errors.append("kind")
    if str(doc.get("report_kind") or "") != "expert-elicitation-source-class":
        errors.append("report-kind")
    errors.extend(required_protocol_steps(doc))

    distinct = doc.get("distinct_from_council") or {}
    if distinct.get("is_council_decision_protocol") is not False:
        errors.append("council-not-separated")
    if str(distinct.get("mode") or "") != "research-input":
        errors.append("mode-not-research-input")

    guard = doc.get("promotion_guard") or {}
    if guard.get("elicited_promoted_to_measured") is not False:
        errors.append("elicited-promoted")
    if str(guard.get("rule") or "") != "elicited-values-never-promoted-to-measured":
        errors.append("promotion-rule")

    live = run_protocol()
    stated_adopt = str((doc.get("adoption") or {}).get("status") or "")
    if stated_adopt != live["adoption"]:
        errors.append(f"adoption-drift:{stated_adopt}!={live['adoption']}")
    if live["lit_misses"] and stated_adopt == "ADOPTED":
        errors.append("literature-miss-adopted")
    if live["lit_misses"] and stated_adopt not in {"WEAK", "REJECTED"}:
        errors.append("literature-miss-not-weak")

    nl = doc.get("questions_no_literature") or []
    lit = doc.get("questions_literature_control") or []
    if len(nl) < 6:
        errors.append("nl-lt-6")
    if len(lit) < 2:
        errors.append("lit-lt-2")
    for row in nl + lit:
        if not isinstance(row, dict):
            errors.append("question-not-object")
            continue
        qid = str(row.get("id") or "?")
        if str(row.get("evidence_tier") or "") == "MEASURED" and qid.startswith("NL"):
            errors.append(f"nl-promoted:{qid}")
        if row.get("promoted_to_measured") is True:
            errors.append(f"row-promoted:{qid}")
        if "calibration_score" not in json.dumps(row):
            # each elicited estimate must carry a calibration score via participant_rows
            pass
        agg = row.get("aggregation") or row
        rows = agg.get("participant_rows") or []
        if qid in set(live["nl_ids"] + live["lit_ids"]) and len(rows) < 4:
            errors.append(f"participant-rows:{qid}")
        for prow in rows:
            if "calibration_score" not in prow:
                errors.append(f"calibration-score-absent:{qid}")
            if prow.get("evidence_tier") not in {None, "ELICITED-NOT-MEASURED"}:
                if str(prow.get("evidence_tier") or "").startswith("MEASURED"):
                    errors.append(f"participant-promoted:{qid}")

    for qid, truth in live["local_truths"].items():
        stated = None
        for row in nl:
            if row.get("id") == qid:
                stated = row.get("local_truth")
        if stated is not None and float(stated) != float(truth):
            errors.append(f"local-truth-drift:{qid}")

    for qid, rec in live["literature_truths"].items():
        stated = None
        for row in lit:
            if row.get("id") == qid:
                stated = row.get("literature_truth")
        if stated is None:
            errors.append(f"lit-truth-absent:{qid}")
        elif float(stated) != float(rec["truth"]):
            errors.append(f"lit-truth-drift:{qid}")

    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 4:
        errors.append("claims-lt-4")
    index = snapshot_index()
    for claim in claims:
        cid = str(claim.get("claim_id") or "?")
        verdict = str(claim.get("verdict") or claim.get("verification_status") or "")
        if str(claim.get("sherman_kent_band") or "") not in BANDS:
            errors.append(f"band:{cid}")
        path = str(claim.get("independent_verification_path") or "")
        if len(path) < 16:
            errors.append(f"verify-path:{cid}")
        lin = [x for x in (claim.get("source_lineage") or []) if isinstance(x, dict)]
        if len(lin) < 2:
            errors.append(f"single-signal:{cid}")
        else:
            urls = {str(x.get("resolved_url")) for x in lin}
            sids = {str(x.get("source_id")) for x in lin}
            if len(urls) < 2 and len(sids) < 2:
                errors.append(f"signals-not-independent:{cid}")
            for entry in lin[:2]:
                problem = lineage_ok(entry, index)
                if problem:
                    errors.append(f"{cid}:{problem}")
        if verdict in {"CONFIRMED", "REFUTED"}:
            src = claim.get("source_probe")
            ver = claim.get("verifier_probe")
            if not src or not ver:
                errors.append(f"no-source-probe:{cid}")
            elif src == ver:
                errors.append(f"same-probe-rerun:{cid}")

    nc = doc.get("negative_control") or {}
    if str(nc.get("state_meant_to_reject") or "") != "ADOPTED-DESPITE-LITERATURE-MISS":
        errors.append("negative-control-state")
    if len(str(nc.get("verbatim") or "")) < 24:
        errors.append("negative-control-thin")

    return {
        "pass": len(errors) == 0,
        "errors": errors,
        "adoption": live["adoption"],
        "lit_misses": live["lit_misses"],
        "nl_hits": live["nl_hits"],
        "nl_n": live["nl_n"],
    }


def mutant_adopt_despite_miss(doc: dict) -> dict:
    mutant = json.loads(json.dumps(doc))
    mutant.setdefault("adoption", {})["status"] = "ADOPTED"
    mutant["adoption"]["reason"] = "mutant-adopted-despite-literature-miss"
    return mutant


def mutant_promote_elicited(doc: dict) -> dict:
    mutant = json.loads(json.dumps(doc))
    mutant.setdefault("promotion_guard", {})["elicited_promoted_to_measured"] = True
    for row in mutant.get("questions_no_literature") or []:
        if isinstance(row, dict):
            row["promoted_to_measured"] = True
            row["evidence_tier"] = "MEASURED"
    return mutant
