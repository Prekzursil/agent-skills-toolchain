"""Validators for the RES-0082 research-claim record.

The catalog requires:
  1. answer the identical-model partition question with a citation or mark
     it NOT-ESTABLISHED
  2. distinguish evidence from human studies from evidence from LLM studies
  3. a headline number without its baseline is E3 and cannot promote
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ARTIFACT = REPO / "command-center" / "research" / "RES-0082.json"
UNIT = "RES-0082"
SENTINEL = (
    "SUCCESS:RES-0082 in the receipt AND an explicit answer or "
    "NOT-ESTABLISHED verdict on partitioned independence, with human "
    "and LLM evidence reported separately"
)
ALLOWED_VERDICTS = frozenset({"ESTABLISHED", "REFUTED", "NOT-ESTABLISHED"})
PROMOTE_TIERS = frozenset({"E1", "E2"})
RAILS = frozenset({"human", "llm"})


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_artifact(path: Path | None = None) -> dict[str, Any]:
    p = path or ARTIFACT
    return json.loads(p.read_text(encoding="utf-8"))


def _require(cond: bool, msg: str, errors: list[str]) -> None:
    if not cond:
        errors.append(msg)


def _cite_fields_ok(row: dict[str, Any]) -> bool:
    cite = str(row.get("doi_or_arxiv") or "").strip()
    loc = str(row.get("section_or_figure") or "").strip()
    eff = str(row.get("effect_size") or "").strip()
    base = str(row.get("baseline") or "").strip()
    return all(len(x) >= 3 for x in (cite, loc, eff, base))


def check_record(doc: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return ["record is not an object"]
    blob = json.dumps(doc, ensure_ascii=False)
    _require(doc.get("unit_id") == UNIT, "unit_id mismatch", errors)
    _require(
        str(doc.get("state") or "").upper() not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"},
        f"self-declared {doc.get('state')}",
        errors,
    )
    _require(SENTINEL in blob, "completion sentinel absent from record text", errors)
    _require(SENTINEL in str(doc.get("sentinel") or ""), "sentinel field missing exact catalog string", errors)

    ident = doc.get("identical_model_partition") or {}
    if not isinstance(ident, dict):
        errors.append("identical_model_partition missing")
        ident = {}
    verdict = str(ident.get("verdict") or "").upper()
    _require(verdict in ALLOWED_VERDICTS, f"identical-model verdict {verdict!r} not in {sorted(ALLOWED_VERDICTS)}", errors)
    _require(len(str(ident.get("rationale") or "")) >= 40, "identical-model rationale too short", errors)
    _require(len(str(ident.get("doi_or_arxiv") or "")) >= 5, "identical-model citation missing", errors)
    if verdict == "ESTABLISHED":
        metric = ident.get("independence_metric") or {}
        _require(
            isinstance(metric, dict)
            and "correlation" in str(metric.get("name") or "").lower()
            and metric.get("value") is not None,
            "ESTABLISHED independence requires a measured correlation metric",
            errors,
        )

    human = doc.get("human_evidence") or []
    llm = doc.get("llm_evidence") or []
    _require(isinstance(human, list) and len(human) >= 2, "human_evidence must have >=2 rows", errors)
    _require(isinstance(llm, list) and len(llm) >= 2, "llm_evidence must have >=2 rows", errors)

    human_ids: set[str] = set()
    llm_ids: set[str] = set()
    for i, row in enumerate(human):
        if not isinstance(row, dict):
            errors.append(f"human_evidence[{i}] not object")
            continue
        _require(row.get("species") == "human", f"human_evidence[{i}] species={row.get('species')!r}", errors)
        pid = str(row.get("paper_id") or "")
        _require(len(pid) >= 4, f"human_evidence[{i}] paper_id missing", errors)
        human_ids.add(pid)
    for i, row in enumerate(llm):
        if not isinstance(row, dict):
            errors.append(f"llm_evidence[{i}] not object")
            continue
        _require(row.get("species") == "llm", f"llm_evidence[{i}] species={row.get('species')!r}", errors)
        pid = str(row.get("paper_id") or "")
        _require(len(pid) >= 4, f"llm_evidence[{i}] paper_id missing", errors)
        llm_ids.add(pid)
    overlap = human_ids & llm_ids
    _require(not overlap, f"human/LLM paper_id overlap {sorted(overlap)}", errors)

    mechs = doc.get("mechanisms") or []
    _require(isinstance(mechs, list) and len(mechs) >= 3, "mechanisms must have >=3 rows", errors)
    promoted = 0
    e3_unpromoted = 0
    for i, m in enumerate(mechs):
        if not isinstance(m, dict):
            errors.append(f"mechanisms[{i}] not object")
            continue
        tier = str(m.get("evidence_tier") or "")
        promo = m.get("promoted") is True
        complete = _cite_fields_ok(m)
        if promo:
            promoted += 1
            _require(tier in PROMOTE_TIERS, f"mechanisms[{i}] promoted at tier {tier}", errors)
            _require(complete, f"mechanisms[{i}] promoted without DOI+section+effect+baseline", errors)
        if tier == "E3":
            _require(promo is False, f"mechanisms[{i}] E3 must not be promoted", errors)
            _require(m.get("headline_without_baseline") is True, f"mechanisms[{i}] E3 missing headline_without_baseline", errors)
            e3_unpromoted += 1
    _require(promoted >= 2, "need >=2 promoted mechanisms with full citation quadruples", errors)
    _require(e3_unpromoted >= 1, "need >=1 E3 headline-without-baseline control that is not promoted", errors)

    reviewers = doc.get("reviewers") or []
    _require(isinstance(reviewers, list) and len(reviewers) == 2, "need exactly two partitioned reviewers", errors)
    rails = []
    seen_papers: list[set[str]] = []
    for i, r in enumerate(reviewers):
        if not isinstance(r, dict):
            errors.append(f"reviewers[{i}] not object")
            continue
        rail = str(r.get("rail") or "")
        rails.append(rail)
        _require(rail in RAILS, f"reviewers[{i}] rail {rail!r}", errors)
        papers = set(r.get("paper_ids") or [])
        _require(len(papers) >= 2, f"reviewers[{i}] must hold a disjoint half (>=2 papers)", errors)
        seen_papers.append(papers)
    _require(set(rails) == RAILS, f"reviewers must cover both rails, got {rails}", errors)
    if len(seen_papers) == 2:
        _require(seen_papers[0].isdisjoint(seen_papers[1]), "reviewer paper_ids are not partitioned", errors)

    tests = {str(t.get("id")): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    _require("identical-model-partition-verdict" in tests, "tests missing identical-model-partition-verdict", errors)
    _require("human-vs-llm-rails" in tests, "tests missing human-vs-llm-rails", errors)
    return errors


def mutant_drop_verdict(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    ident = dict(out.get("identical_model_partition") or {})
    ident["verdict"] = ""
    out["identical_model_partition"] = ident
    return out


def mutant_promote_e3(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    mechs = list(out.get("mechanisms") or [])
    for m in mechs:
        if m.get("evidence_tier") == "E3":
            m["promoted"] = True
            break
    out["mechanisms"] = mechs
    return out


def mutant_swap_species(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    human = list(out.get("human_evidence") or [])
    llm = list(out.get("llm_evidence") or [])
    if human:
        row = dict(human[0])
        row["species"] = "llm"
        llm = [row] + llm
        out["llm_evidence"] = llm
    return out


def mutant_merge_reviewers(doc: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(doc)
    revs = copy.deepcopy(out.get("reviewers") or [])
    if len(revs) == 2:
        papers = list(revs[0].get("paper_ids") or [])
        if papers:
            revs[1]["paper_ids"] = list(revs[1].get("paper_ids") or []) + [papers[0]]
        out["reviewers"] = revs
    return out
