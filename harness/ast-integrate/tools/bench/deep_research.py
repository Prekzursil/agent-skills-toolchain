"""Deep-research benchmark runner: quota adherence and contradiction retention (TST-0319).

The research workflow under test is configured with a favourable/unfavourable citation
quota, contradiction search and a requirement to preserve negative evidence.  On a seeded
corpus whose true support/contradict distribution is known by construction, this module
runs the honest workflow and writes artifacts an independent measurer can recount:

* ``notes.json`` - the working notes: every retrieved source, every contradiction found
  and the per-source-class query log.  Notes are never the final report.
* ``final_report.md`` / ``final_report.json`` - the final report.  The selected citations
  sit between :data:`MARK_SEL_BEGIN` and :data:`MARK_SEL_END`; the contradiction appendix
  (every retrieved contradiction, whether or not it was selected) sits between
  :data:`MARK_CON_BEGIN` and :data:`MARK_CON_END`.  Survival is scored on the appendix.
* ``impossibility.json`` - only when the asked-for claim has no evidence at all.  That
  is a typed proof-of-impossibility record produced by :func:`emit_impossibility_record`,
  a code path distinct from :func:`emit_final_report`; an empty retrieval is never
  reported as consensus over nothing.

Design rules the runner enforces rather than documents:

* the citation mix meets the configured quota from what was actually retrieved; missing
  unfavourable evidence is reported as a shortfall, never manufactured and never back-filled
  with favourable evidence (that would skew the mix, which is the failure under test);
* the verdict is scored on the strength sums of everything retrieved, not of the selected
  subset, so stronger contradictions cannot be hidden by selection; any surviving
  contradiction caps the verdict at ``CONTESTED`` - ``CONSENSUS`` needs zero of them;
* a configuration that disables contradiction search or negative-evidence preservation is
  refused (:class:`DeepResearchError`) instead of silently producing the useless answer.

Everything is stdlib and deterministic given the corpus and configuration (the
impossibility record's ``issued_at``/``expiry`` come from the configured clock when one is
supplied, otherwise from the wall clock).
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- constants
STANCE_SUPPORT = "support"
STANCE_CONTRADICT = "contradict"
STANCE_NEUTRAL = "neutral"
POLAR_STANCES = (STANCE_SUPPORT, STANCE_CONTRADICT)

VERDICT_CONSENSUS = "CONSENSUS"
VERDICT_CONTESTED = "CONTESTED"
VERDICT_CONTRADICTION_DOMINANT = "CONTRADICTION-DOMINANT"
VERDICT_IMPOSSIBLE = "IMPOSSIBLE"
VERDICTS = (
    VERDICT_CONSENSUS,
    VERDICT_CONTESTED,
    VERDICT_CONTRADICTION_DOMINANT,
    VERDICT_IMPOSSIBLE,
)

MARK_SEL_BEGIN = "<!-- BEGIN_SELECTED -->"
MARK_SEL_END = "<!-- END_SELECTED -->"
MARK_CON_BEGIN = "<!-- BEGIN_CONTRADICTIONS -->"
MARK_CON_END = "<!-- END_CONTRADICTIONS -->"

CODE_PATH_FINAL_REPORT = "emit_final_report"
CODE_PATH_IMPOSSIBILITY = "emit_impossibility_record"

DEFAULT_SOURCE_CLASSES: tuple[str, ...] = (
    "seeded-paper",
    "seeded-web",
    "seeded-archive",
)
IMPOSSIBILITY_TTL_DAYS = 30

DEFAULT_CONFIG: dict[str, Any] = {
    "favourable_quota": 0.70,
    "unfavourable_quota": 0.30,
    "contradiction_search": True,
    "preserve_negative": True,
    "report_slot_budget": 10,
}

NOTES_FILE = "notes.json"
FINAL_MD_FILE = "final_report.md"
FINAL_JSON_FILE = "final_report.json"
IMPOSSIBILITY_FILE = "impossibility.json"

_EPS = 1e-9


class DeepResearchError(ValueError):
    """Malformed corpus, source or configuration."""


# --------------------------------------------------------------------------- corpus access
def query_claim_id(corpus: Mapping[str, Any]) -> str:
    """The claim the research question asks about (``query_claim_id``, else ``claim_id``)."""
    claim = corpus.get("query_claim_id") or corpus.get("claim_id")
    if not isinstance(claim, str) or not claim:
        raise DeepResearchError("corpus has neither query_claim_id nor claim_id")
    return claim


def _strength(raw: Any, sid: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise DeepResearchError(
            f"source {sid!r}: strength must be a number, got {raw!r}"
        )
    value = float(raw)
    if math.isnan(value) or value < 0.0 or value > 1.0:
        raise DeepResearchError(
            f"source {sid!r}: strength must be within [0, 1], got {value!r}"
        )
    return value


def corpus_sources(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every well-formed source of the corpus, normalised and ordered by id.

    A source needs a string ``id``, ``claim_id``, ``stance`` and ``token``; ``strength``
    defaults to 0 and must lie in [0, 1]; ``source_class`` defaults to ``"unclassified"``.
    Non-dict entries are skipped, duplicate ids are an error.
    """
    raw = corpus.get("sources")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise DeepResearchError("corpus.sources must be a list")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        sid = entry.get("id")
        if not isinstance(sid, str) or not sid:
            raise DeepResearchError(f"source without a string id: {entry!r}")
        if sid in seen:
            raise DeepResearchError(f"duplicate source id {sid!r}")
        seen.add(sid)
        for key in ("claim_id", "stance", "token"):
            if not isinstance(entry.get(key), str) or not entry[key]:
                raise DeepResearchError(
                    f"source {sid!r}: {key} must be a non-empty string"
                )
        out.append(
            {
                "id": sid,
                "claim_id": entry["claim_id"],
                "stance": entry["stance"],
                "strength": _strength(entry.get("strength", 0.0), sid),
                "source_class": str(entry.get("source_class") or "unclassified"),
                "token": entry["token"],
                "body": str(entry.get("body") or ""),
            }
        )
    out.sort(key=lambda s: s["id"])
    return out


def source_classes(corpus: Mapping[str, Any]) -> list[str]:
    """Search classes: the defaults first, then any extra class the corpus declares."""
    classes = list(DEFAULT_SOURCE_CLASSES)
    for src in corpus_sources(corpus):
        if src["source_class"] not in classes:
            classes.append(src["source_class"])
    return classes


def run_queries(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    """One query per source class for the asked-for claim, with its hit count and hit ids."""
    claim = query_claim_id(corpus)
    sources = corpus_sources(corpus)
    log: list[dict[str, Any]] = []
    for cls in source_classes(corpus):
        hits = [
            s["id"]
            for s in sources
            if s["source_class"] == cls and s["claim_id"] == claim
        ]
        log.append(
            {
                "source_class": cls,
                "query": f"claim_id == {claim!r} in {cls}",
                "hits": len(hits),
                "hit_ids": hits,
            }
        )
    return log


def exhausted_source_classes(queries: Iterable[Mapping[str, Any]]) -> list[str]:
    """Classes that were searched and returned nothing."""
    return [str(q["source_class"]) for q in queries if int(q.get("hits") or 0) == 0]


def retrieve(corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every source whose ``claim_id`` is the asked-for claim, ordered by id.

    Retrieval is stance-blind: supporting, contradicting and neutral sources all come
    back.  Filtering by stance happens later and only where the contract allows it.
    """
    claim = query_claim_id(corpus)
    return [s for s in corpus_sources(corpus) if s["claim_id"] == claim]


# --------------------------------------------------------------------------- evidence analysis
def find_contradictions(retrieved: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Contradiction search over the retrieved set.

    Each contradicting source is paired against the supporting sources it opposes on the
    same claim.  The list has one record per contradicting source, ordered by id, so the
    appendix can carry every one of them and a measurer can count them.
    """
    by_claim_support: dict[str, list[Mapping[str, Any]]] = {}
    for src in retrieved:
        if src.get("stance") == STANCE_SUPPORT:
            by_claim_support.setdefault(str(src.get("claim_id")), []).append(src)
    out: list[dict[str, Any]] = []
    for src in sorted(retrieved, key=lambda s: str(s.get("id"))):
        if src.get("stance") != STANCE_CONTRADICT:
            continue
        claim = str(src.get("claim_id"))
        opposed = sorted(
            by_claim_support.get(claim, []), key=lambda s: str(s.get("id"))
        )
        out.append(
            {
                "kind": "stance-conflict",
                "claim_id": claim,
                "contradict_id": src.get("id"),
                "contradict_token": src.get("token"),
                "contradict_strength": float(src.get("strength") or 0.0),
                "source_class": src.get("source_class"),
                "against_ids": [str(s.get("id")) for s in opposed],
                "against_strength": round(
                    sum(float(s.get("strength") or 0.0) for s in opposed), 12
                ),
            }
        )
    return out


def strength_sums(retrieved: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Counts and strength sums per polar stance over everything retrieved."""
    n_support = n_contradict = 0
    s_support = s_contradict = 0.0
    for src in retrieved:
        stance = src.get("stance")
        strength = float(src.get("strength") or 0.0)
        if stance == STANCE_SUPPORT:
            n_support += 1
            s_support += strength
        elif stance == STANCE_CONTRADICT:
            n_contradict += 1
            s_contradict += strength
    return {
        "support": n_support,
        "contradict": n_contradict,
        "support_strength": round(s_support, 12),
        "contradict_strength": round(s_contradict, 12),
        "contradict_stronger": s_contradict > s_support + _EPS,
    }


def judge_verdict(retrieved: Sequence[Mapping[str, Any]]) -> str:
    """Verdict from the retrieved strength sums, never from the selected subset.

    * nothing retrieved                      -> ``IMPOSSIBLE``
    * contradict strength > support strength -> ``CONTRADICTION-DOMINANT``
    * any contradiction at all               -> ``CONTESTED``
    * no contradicting evidence              -> ``CONSENSUS``
    """
    if not retrieved:
        return VERDICT_IMPOSSIBLE
    sums = strength_sums(retrieved)
    if sums["contradict_stronger"]:
        return VERDICT_CONTRADICTION_DOMINANT
    if sums["contradict"] > 0:
        return VERDICT_CONTESTED
    return VERDICT_CONSENSUS


# --------------------------------------------------------------------------- configuration + quota
def _quota(cfg: Mapping[str, Any], key: str) -> float:
    raw = cfg.get(key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise DeepResearchError(f"{key} must be a number in [0, 1], got {raw!r}")
    value = float(raw)
    if math.isnan(value) or value < 0.0 or value > 1.0:
        raise DeepResearchError(f"{key} must be within [0, 1], got {value!r}")
    return value


def _round_half_up(x: float) -> int:
    return int(math.floor(x + 0.5))


def quota_counts(cfg: Mapping[str, Any]) -> tuple[int, int, int]:
    """``(budget, n_favourable, n_unfavourable)`` citation slots for a configuration.

    ``report_slot_budget`` is a positive integer; the two quotas lie in [0, 1] and sum to
    at most 1.  Slots are split by rounding half up; when the quotas sum to 1 the
    unfavourable count is the remainder so the split always fills the budget exactly.
    """
    raw_budget = cfg.get("report_slot_budget")
    if (
        isinstance(raw_budget, bool)
        or not isinstance(raw_budget, int)
        or raw_budget < 1
    ):
        raise DeepResearchError(
            f"report_slot_budget must be a positive int, got {raw_budget!r}"
        )
    fav = _quota(cfg, "favourable_quota")
    unfav = _quota(cfg, "unfavourable_quota")
    if fav + unfav > 1.0 + _EPS:
        raise DeepResearchError(f"quotas sum to {fav + unfav:.6f} > 1")
    n_fav = min(raw_budget, _round_half_up(raw_budget * fav))
    if abs(fav + unfav - 1.0) <= _EPS:
        n_unfav = raw_budget - n_fav
    else:
        n_unfav = min(raw_budget - n_fav, _round_half_up(raw_budget * unfav))
    return raw_budget, n_fav, n_unfav


def validate_config(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Merge ``config`` over :data:`DEFAULT_CONFIG` and refuse configurations that drop evidence."""
    cfg: dict[str, Any] = dict(DEFAULT_CONFIG)
    if config:
        cfg.update(config)
    quota_counts(cfg)
    if not cfg.get("contradiction_search"):
        raise DeepResearchError(
            "contradiction_search=False is refused: the verdict is scored on contradictions"
        )
    if not cfg.get("preserve_negative"):
        raise DeepResearchError(
            "preserve_negative=False is refused: this runner never drops negative evidence"
        )
    return cfg


def select_citations(
    retrieved: Sequence[Mapping[str, Any]], cfg: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Fill the quota slots from what was retrieved; report shortfall, never back-fill.

    Within a stance the strongest sources come first (ties broken by id).  A stance with
    fewer sources than slots leaves its slots empty and the deficit is returned as
    ``shortfall`` - the runner does not fill unfavourable slots with favourable evidence.
    """
    budget, n_fav, n_unfav = quota_counts(cfg)
    ordered = sorted(
        retrieved, key=lambda s: (-float(s.get("strength") or 0.0), str(s.get("id")))
    )
    support = [s for s in ordered if s.get("stance") == STANCE_SUPPORT][:n_fav]
    contradict = [s for s in ordered if s.get("stance") == STANCE_CONTRADICT][:n_unfav]
    selected = [
        {
            "id": s["id"],
            "claim_id": s.get("claim_id"),
            "stance": s["stance"],
            "strength": float(s.get("strength") or 0.0),
            "source_class": s.get("source_class"),
            "token": s["token"],
        }
        for s in support + contradict
    ]
    shortfall = {
        "favourable": n_fav - len(support),
        "unfavourable": n_unfav - len(contradict),
        "budget": budget,
    }
    return selected, shortfall


def returned_proportion(selected: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Support/contradict share of the selected polar citations, with their tokens."""
    support = [str(s["token"]) for s in selected if s.get("stance") == STANCE_SUPPORT]
    contradict = [
        str(s["token"]) for s in selected if s.get("stance") == STANCE_CONTRADICT
    ]
    polar = len(support) + len(contradict)
    return {
        "support": (len(support) / polar) if polar else 0.0,
        "contradict": (len(contradict) / polar) if polar else 0.0,
        "polar_n": polar,
        "support_tokens": support,
        "contradict_tokens": contradict,
    }


# --------------------------------------------------------------------------- notes + reports
def build_notes(
    corpus: Mapping[str, Any],
    retrieved: Sequence[Mapping[str, Any]],
    contradictions: Sequence[Mapping[str, Any]],
    queries: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Working notes: every retrieved source, every contradiction and the query log."""
    sums = strength_sums(retrieved)
    return {
        "kind": "working-notes",
        "corpus_id": corpus.get("id"),
        "query_claim_id": query_claim_id(corpus),
        "query": corpus.get("query"),
        "retrieved_count": len(retrieved),
        "sources": [dict(s) for s in retrieved],
        "support_ids": [
            s["id"] for s in retrieved if s.get("stance") == STANCE_SUPPORT
        ],
        "contradict_ids": [
            s["id"] for s in retrieved if s.get("stance") == STANCE_CONTRADICT
        ],
        "neutral_ids": [
            s["id"] for s in retrieved if s.get("stance") not in POLAR_STANCES
        ],
        "strength": sums,
        "contradictions": [dict(c) for c in contradictions],
        "queries_run": [
            dict(q) for q in (queries if queries is not None else run_queries(corpus))
        ],
        "note": (
            "working notes are not the final report; survival of a contradiction is scored "
            "on the final report appendix, not here"
        ),
    }


def emit_final_report(
    corpus: Mapping[str, Any],
    cfg: Mapping[str, Any],
    retrieved: Sequence[Mapping[str, Any]],
    selected: Sequence[Mapping[str, Any]],
    shortfall: Mapping[str, int],
    contradictions: Sequence[Mapping[str, Any]],
    verdict: str,
) -> dict[str, Any]:
    """The final report for a non-empty retrieval; the appendix carries every contradiction."""
    if verdict not in VERDICTS:
        raise DeepResearchError(f"unknown verdict {verdict!r}")
    budget, n_fav, n_unfav = quota_counts(cfg)
    appendix = [str(c["contradict_token"]) for c in contradictions]
    return {
        "kind": "final-report",
        "code_path": CODE_PATH_FINAL_REPORT,
        "corpus_id": corpus.get("id"),
        "query_claim_id": query_claim_id(corpus),
        "query": corpus.get("query"),
        "verdict": verdict,
        "verdict_basis": strength_sums(retrieved),
        "configured_quota": {
            "favourable": float(cfg["favourable_quota"]),
            "unfavourable": float(cfg["unfavourable_quota"]),
            "report_slot_budget": budget,
            "favourable_slots": n_fav,
            "unfavourable_slots": n_unfav,
        },
        "returned_proportion": returned_proportion(selected),
        "shortfall": dict(shortfall),
        "selected": [dict(s) for s in selected],
        "selected_ids": [s["id"] for s in selected],
        "selected_tokens": [s["token"] for s in selected],
        "contradiction_appendix_tokens": appendix,
        "contradiction_pair_count": len(contradictions),
        "retrieved_count": len(retrieved),
        "preserve_negative": True,
        "contradiction_search": True,
    }


def emit_impossibility_record(
    corpus: Mapping[str, Any],
    cfg: Mapping[str, Any],
    queries: Sequence[Mapping[str, Any]],
    issued_at: datetime | None = None,
) -> dict[str, Any]:
    """Typed proof that the asked-for claim has no evidence in the searched classes.

    Distinct from :func:`emit_final_report`: it names every exhausted class, the zero-hit
    query per class, what the corpus does talk about, a falsifier and an expiry.  Any hit
    is a programming error here - the caller routes non-empty retrievals elsewhere.
    """
    if any(int(q.get("hits") or 0) for q in queries):
        raise DeepResearchError(
            "impossibility record requested although queries returned hits"
        )
    claim = query_claim_id(corpus)
    exhausted = exhausted_source_classes(queries)
    if not exhausted:
        raise DeepResearchError(
            "cannot prove impossibility without an exhausted source class"
        )
    present = sorted({s["claim_id"] for s in corpus_sources(corpus)})
    when = issued_at if issued_at is not None else _clock(cfg)
    ttl = int(cfg.get("impossibility_ttl_days") or IMPOSSIBILITY_TTL_DAYS)
    return {
        "kind": "proof-of-impossibility",
        "code_path": CODE_PATH_IMPOSSIBILITY,
        "corpus_id": corpus.get("id"),
        "claim_id": claim,
        "query": corpus.get("query"),
        "verdict": VERDICT_IMPOSSIBLE,
        "exhausted_source_classes": exhausted,
        "queries_run": [dict(q) for q in queries],
        "present_claims": present,
        "falsifier": (
            f"a source whose claim_id is {claim!r} with a polar stance in any of "
            f"{', '.join(exhausted)}; re-run the research on the amended corpus"
        ),
        "issued_at": _iso(when),
        "expiry": _iso(when + timedelta(days=ttl)),
        "ttl_days": ttl,
    }


def _clock(cfg: Mapping[str, Any]) -> datetime:
    raw = cfg.get("issued_at")
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    if isinstance(raw, str) and raw:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _iso(when: datetime) -> str:
    return when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _impossibility_notice(
    corpus: Mapping[str, Any], cfg: Mapping[str, Any], record: Mapping[str, Any]
) -> dict[str, Any]:
    budget, n_fav, n_unfav = quota_counts(cfg)
    return {
        "kind": "impossibility-notice",
        "code_path": CODE_PATH_IMPOSSIBILITY,
        "corpus_id": corpus.get("id"),
        "query_claim_id": query_claim_id(corpus),
        "query": corpus.get("query"),
        "verdict": VERDICT_IMPOSSIBLE,
        "configured_quota": {
            "favourable": float(cfg["favourable_quota"]),
            "unfavourable": float(cfg["unfavourable_quota"]),
            "report_slot_budget": budget,
            "favourable_slots": n_fav,
            "unfavourable_slots": n_unfav,
        },
        "returned_proportion": returned_proportion([]),
        "selected": [],
        "selected_ids": [],
        "selected_tokens": [],
        "contradiction_appendix_tokens": [],
        "contradiction_pair_count": 0,
        "retrieved_count": 0,
        "exhausted_source_classes": list(record["exhausted_source_classes"]),
        "impossibility_file": IMPOSSIBILITY_FILE,
        "preserve_negative": True,
        "contradiction_search": True,
    }


# --------------------------------------------------------------------------- rendering + writing
def _fmt_ratio(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _citation_line(token: str, by_token: Mapping[str, Mapping[str, Any]]) -> str:
    src = by_token.get(token)
    if src is None:
        return f"- {token}"
    return (
        f"- {src.get('id')} [{src.get('stance')}, strength {float(src.get('strength') or 0.0):.2f}, "
        f"{src.get('source_class')}] {token}"
    )


def render_final_markdown(result: Mapping[str, Any]) -> str:
    """Markdown final report; the two marker blocks are what the measurer recounts."""
    report = result.get("final_report") or {}
    by_token: dict[str, Mapping[str, Any]] = {}
    for src in list(result.get("retrieved") or []) + list(result.get("selected") or []):
        if isinstance(src, Mapping) and isinstance(src.get("token"), str):
            by_token.setdefault(src["token"], src)
    quota = report.get("configured_quota") or {}
    returned = report.get("returned_proportion") or {}
    lines = [
        f"# Research report: {report.get('corpus_id')}",
        "",
        f"Claim: {report.get('query_claim_id')}",
        f"Query: {report.get('query') or ''}",
        f"Verdict: {report.get('verdict')}",
        f"Code path: {report.get('code_path')}",
        "",
        "## Configured quota",
        f"- favourable: {_fmt_ratio(quota.get('favourable'))}",
        f"- unfavourable: {_fmt_ratio(quota.get('unfavourable'))}",
        f"- report slot budget: {quota.get('report_slot_budget')}",
        "",
        "## Returned proportion (selected polar citations)",
        f"- support: {_fmt_ratio(returned.get('support'))}",
        f"- contradict: {_fmt_ratio(returned.get('contradict'))}",
        f"- polar citations: {returned.get('polar_n')}",
        "",
        "## Selected citations",
        MARK_SEL_BEGIN,
    ]
    lines.extend(
        _citation_line(str(t), by_token) for t in report.get("selected_tokens") or []
    )
    lines.append(MARK_SEL_END)
    lines.extend(
        [
            "",
            "## Contradiction appendix",
            f"- contradictions found: {report.get('contradiction_pair_count')}",
            MARK_CON_BEGIN,
        ]
    )
    lines.extend(
        _citation_line(str(t), by_token)
        for t in report.get("contradiction_appendix_tokens") or []
    )
    lines.append(MARK_CON_END)
    record = result.get("impossibility")
    if isinstance(record, Mapping):
        lines.extend(
            [
                "",
                "## Proof of impossibility",
                f"- claim: {record.get('claim_id')}",
                f"- exhausted source classes: {', '.join(record.get('exhausted_source_classes') or [])}",
                f"- present claims: {', '.join(record.get('present_claims') or [])}",
                f"- falsifier: {record.get('falsifier')}",
                f"- expiry: {record.get('expiry')}",
                f"- record: {IMPOSSIBILITY_FILE}",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def write_artifacts(out_dir: Path, result: Mapping[str, Any]) -> dict[str, Path]:
    """Write notes, final report (md + json) and, when present, the impossibility record."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}
    notes_path = out / NOTES_FILE
    notes_path.write_text(
        json.dumps(result.get("notes") or {}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["notes"] = notes_path
    final_json = out / FINAL_JSON_FILE
    final_json.write_text(
        json.dumps(result.get("final_report") or {}, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["final_report_json"] = final_json
    final_md = out / FINAL_MD_FILE
    final_md.write_text(render_final_markdown(result), encoding="utf-8")
    written["final_report_md"] = final_md
    record = result.get("impossibility")
    if record is not None:
        imp_path = out / IMPOSSIBILITY_FILE
        imp_path.write_text(
            json.dumps(record, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
        written["impossibility"] = imp_path
    return written


# --------------------------------------------------------------------------- the workflow
def run_research(
    corpus: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the honest research workflow on one corpus and optionally write its artifacts.

    Returns ``verdict``, ``notes``, ``final_report``, ``impossibility`` (record or None),
    ``selected``, ``retrieved``, ``contradictions``, ``queries_run`` and, when ``out_dir``
    is given, the ``artifacts`` written.
    """
    cfg = validate_config(config)
    queries = run_queries(corpus)
    retrieved = retrieve(corpus)
    contradictions = find_contradictions(retrieved)
    notes = build_notes(corpus, retrieved, contradictions, queries)
    if not retrieved:
        record = emit_impossibility_record(corpus, cfg, queries)
        result: dict[str, Any] = {
            "verdict": VERDICT_IMPOSSIBLE,
            "notes": notes,
            "final_report": _impossibility_notice(corpus, cfg, record),
            "impossibility": record,
            "selected": [],
            "retrieved": [],
            "contradictions": contradictions,
            "queries_run": queries,
        }
    else:
        verdict = judge_verdict(retrieved)
        selected, shortfall = select_citations(retrieved, cfg)
        result = {
            "verdict": verdict,
            "notes": notes,
            "final_report": emit_final_report(
                corpus, cfg, retrieved, selected, shortfall, contradictions, verdict
            ),
            "impossibility": None,
            "selected": selected,
            "retrieved": [dict(s) for s in retrieved],
            "contradictions": contradictions,
            "queries_run": queries,
        }
    if out_dir is not None:
        result["artifacts"] = write_artifacts(Path(out_dir), result)
    return result


__all__ = [
    "CODE_PATH_FINAL_REPORT",
    "CODE_PATH_IMPOSSIBILITY",
    "DEFAULT_CONFIG",
    "DEFAULT_SOURCE_CLASSES",
    "DeepResearchError",
    "FINAL_JSON_FILE",
    "FINAL_MD_FILE",
    "IMPOSSIBILITY_FILE",
    "IMPOSSIBILITY_TTL_DAYS",
    "MARK_CON_BEGIN",
    "MARK_CON_END",
    "MARK_SEL_BEGIN",
    "MARK_SEL_END",
    "NOTES_FILE",
    "POLAR_STANCES",
    "STANCE_CONTRADICT",
    "STANCE_NEUTRAL",
    "STANCE_SUPPORT",
    "VERDICTS",
    "VERDICT_CONSENSUS",
    "VERDICT_CONTESTED",
    "VERDICT_CONTRADICTION_DOMINANT",
    "VERDICT_IMPOSSIBLE",
    "build_notes",
    "corpus_sources",
    "emit_final_report",
    "emit_impossibility_record",
    "exhausted_source_classes",
    "find_contradictions",
    "judge_verdict",
    "query_claim_id",
    "quota_counts",
    "render_final_markdown",
    "retrieve",
    "returned_proportion",
    "run_queries",
    "run_research",
    "select_citations",
    "source_classes",
    "strength_sums",
    "validate_config",
    "write_artifacts",
]
