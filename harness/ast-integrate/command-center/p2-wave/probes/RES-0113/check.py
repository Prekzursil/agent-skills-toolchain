#!/usr/bin/env python3
"""Structural and evidence-quality checks for RES-0113 (no I/O beyond repo reads)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0113.json"
SENTINEL = (
    "SUCCESS:RES-0113 in the receipt AND an additive-versus-renaming split "
    "with at least one explicitly rejected technique"
)
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
BANDS = frozenset(
    {"almost-certain", "likely", "roughly-even", "unlikely", "remote"}
)
VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED"})


def load_art(path: Path | None = None) -> dict[str, Any]:
    p = path or ART
    return json.loads(p.read_text(encoding="utf-8"))


def _fail(msg: str) -> str:
    return msg


def resolve_anchor(path: str, line: int, must_contain: str) -> str | None:
    fp = REPO / path
    if not fp.is_file():
        return f"anchor-missing:{path}"
    lines = fp.read_text(encoding="utf-8").splitlines()
    if line < 1 or line > len(lines):
        return f"anchor-oob:{path}:{line}"
    text = lines[line - 1]
    if must_contain not in text:
        return f"anchor-mismatch:{path}:{line}: missing {must_contain!r}"
    return None


def check_split(doc: dict[str, Any]) -> str | None:
    if not isinstance(doc, dict):
        return _fail("not-object")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return _fail(f"self-declared:{st}")
    blob = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in blob:
        return _fail("sentinel-absent")
    split = doc.get("additive_versus_renaming_split")
    if not isinstance(split, dict):
        return _fail("split-absent")
    renaming = split.get("renaming") or []
    additive = split.get("additive") or []
    rejected = split.get("rejected") or []
    if not isinstance(renaming, list) or len(renaming) < 3:
        return _fail("renaming-too-few")
    if not isinstance(additive, list):
        return _fail("additive-not-list")
    if not isinstance(rejected, list) or len(rejected) < 1:
        return _fail("rejected-technique-absent")
    for row in rejected:
        if not isinstance(row, dict):
            return _fail("rejected-row-not-object")
        if not str(row.get("technique") or "").strip():
            return _fail("rejected-technique-unnamed")
        if not str(row.get("rejection_reason") or "").strip():
            return _fail("rejected-reason-absent")
        if row.get("worth_the_ceremony") is not False:
            return _fail("rejected-not-marked-unworthy")
    for row in renaming:
        if not isinstance(row, dict):
            return _fail("renaming-row-not-object")
        analog = row.get("program_analogue") or {}
        err = resolve_anchor(
            str(analog.get("path") or ""),
            int(analog.get("line") or 0),
            str(analog.get("must_contain") or ""),
        )
        if err:
            return _fail(err)
    # Additive rows may be empty or E3-unpromoted; they must not be silently
    # reclassified as renaming.
    ids_r = {str(r.get("id")) for r in renaming if isinstance(r, dict)}
    ids_a = {str(r.get("id")) for r in additive if isinstance(r, dict)}
    ids_j = {str(r.get("id")) for r in rejected if isinstance(r, dict)}
    if ids_r & ids_a or ids_r & ids_j or ids_a & ids_j:
        return _fail("split-id-overlap")
    return None


def check_evidence(doc: dict[str, Any]) -> str | None:
    mechs = doc.get("mechanisms")
    if not isinstance(mechs, list) or len(mechs) < 3:
        return _fail("mechanisms-too-few")
    promoted_n = 0
    rejected_with_numbers = 0
    for m in mechs:
        if not isinstance(m, dict):
            return _fail("mechanism-not-object")
        mid = str(m.get("id") or "")
        promoted = m.get("promoted") is True
        tier = str(m.get("evidence_tier") or "")
        doi = str(m.get("doi_or_arxiv") or "").strip()
        section = str(m.get("section_or_figure") or "").strip()
        effect = m.get("effect_size")
        baseline = m.get("baseline")
        clas = str(m.get("classification") or "")
        missing_numbers = effect in (None, "") or baseline in (None, "")
        if promoted:
            promoted_n += 1
            if missing_numbers:
                return _fail(f"promoted-without-numbers:{mid}")
            if not doi or not section:
                return _fail(f"promoted-without-citation:{mid}")
            if tier == "E3":
                return _fail(f"e3-promoted:{mid}")
            if str(m.get("confidence_band") or "") not in BANDS:
                return _fail(f"promoted-band-invalid:{mid}")
        else:
            if missing_numbers:
                if clas == "renaming":
                    continue
                if clas == "additive" and tier == "E3":
                    continue
                if clas == "not-SAT-contrast" and tier == "E3":
                    continue
                return _fail(f"unnumbered-not-e3:{mid}")
            if clas == "rejected":
                if not doi or not section:
                    return _fail(f"rejected-without-citation:{mid}")
                rejected_with_numbers += 1
    if rejected_with_numbers < 1:
        return _fail("rejected-without-effect-and-baseline")
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 2:
        return _fail("claims-too-few")
    for c in claims:
        if not isinstance(c, dict):
            return _fail("claim-not-object")
        if str(c.get("verdict") or "") not in VERDICTS:
            return _fail(f"claim-verdict-invalid:{c.get('id')}")
        if str(c.get("verdict")) in {"CONFIRMED", "PARTIAL"}:
            if not str(c.get("strongest_caveat") or "").strip():
                return _fail(f"surviving-claim-no-caveat:{c.get('id')}")
    rev = doc.get("reviewer") or {}
    if rev.get("defaults_to_REFUTED_when_insufficient") is not True:
        return _fail("reviewer-not-default-REFUTED")
    if rev.get("independent") is not True:
        return _fail("reviewer-not-independent")
    return None


def both_states_split(doc: dict[str, Any]) -> str | None:
    """Green on live; red if the rejected-technique control is stripped."""
    err = check_split(doc)
    if err:
        return f"live-split:{err}"
    mutant = copy.deepcopy(doc)
    mutant["additive_versus_renaming_split"]["rejected"] = []
    merr = check_split(mutant)
    if merr is None:
        return "split-silent-on-missing-reject"
    return None


def both_states_evidence(doc: dict[str, Any]) -> str | None:
    """Green on live; red if an E3 row is promoted without a baseline."""
    err = check_evidence(doc)
    if err:
        return f"live-evidence:{err}"
    mutant = copy.deepcopy(doc)
    mutant["mechanisms"].append(
        {
            "id": "M-PLANTED-E3-PROMOTE",
            "classification": "additive",
            "promoted": True,
            "evidence_tier": "E3",
            "doi_or_arxiv": "10.0000/planted",
            "section_or_figure": "§0",
            "effect_size": "headline 40% improvement",
            "baseline": None,
            "confidence_band": "likely",
        }
    )
    merr = check_evidence(mutant)
    if merr is None:
        return "evidence-silent-on-e3-promote"
    if "e3-promoted" not in merr and "promoted-without-numbers" not in merr:
        return f"evidence-mutant-wrong-reason:{merr}"
    return None
