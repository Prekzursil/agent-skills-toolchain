"""Validators for RES-0097 claim record.

Probe 1 checks structural honesty (sentinel, split, citation fields, E3 gate).
Probe 2 checks overclaim: NEW rows must not be both-states paraphrases, and
the checker itself must fire on a relabel mutant and stay silent on the good
record (both-states of this unit's own detector).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART_REL = "command-center/research/RES-0097.json"
SENTINEL = (
    "SUCCESS:RES-0097 in the receipt AND an explicit new-versus-restated split, "
    "with a null result reported as a null result if that is the honest outcome"
)
BANDS = frozenset(
    {"almost-certain", "likely", "roughly-even", "unlikely", "remote"}
)
TIERS = frozenset({"E1", "E2", "E3", "E4"})
SPLITS = frozenset({"NEW", "RESTATED-NULL", "E3-NOT-PROMOTED"})
REQUIRED_MECH = (
    "id",
    "canonical_mechanism",
    "source_lineage",
    "evidence_tier",
    "confidence_band",
    "settling_probe",
    "doi_or_arxiv",
    "section_or_figure",
    "effect_size",
    "baseline",
    "split",
    "strongest_caveat",
    "not_already_in_rule",
)
NEW_NOVELTY = {
    "M-U-COMPARABLE": ("u-comparable", "unmeasured confounding", "second outcome", "negative control outcome"),
    "M-QUANT-NULL": ("numeric bound", "10^-15", "systematic error", "eotvos", "eötvös"),
    "M-PLACEBO-RITUAL": ("expectancy", "ritual", "placebo", "sham", "no-treatment"),
    "M-EMPIRICAL-NULL": ("empirical null", "calibrat", "negative control drugs", "type i"),
    "M-BLIND-FREEZE": ("hidden signal", "before unblind", "freeze", "hidden offset", "experimenter"),
}
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ARXIV_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
FIRE_SILENT = re.compile(
    r"\b(fire[sd]? on (the )?bad|silent on (the )?good|known-broken|known-good|"
    r"silent-in-both|fires-in-both|both-states discrimination|fired_on_bad|"
    r"silent_on_good)\b",
    re.I,
)


def load_art(repo: Path | None = None) -> dict:
    root = repo or REPO
    path = root / ART_REL
    return json.loads(path.read_text(encoding="utf-8"))


def load_numbers() -> dict:
    return json.loads((HERE / "snapshots" / "numbers.json").read_text(encoding="utf-8"))


def _reasons(ok: bool, msgs: list[str]) -> tuple[bool, str]:
    return ok, "; ".join(msgs) if msgs else "ok"


def check_sentinel_and_state(doc: dict) -> tuple[bool, str]:
    msgs: list[str] = []
    text = json.dumps(doc, ensure_ascii=True)
    if SENTINEL not in text:
        msgs.append("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        msgs.append(f"self-declared:{st}")
    split = doc.get("new_versus_restated")
    if not isinstance(split, dict):
        msgs.append("split-object-absent")
    else:
        if not split.get("new"):
            msgs.append("split-new-empty")
        if not split.get("restated_null_results"):
            msgs.append("split-restated-empty")
    null = str(doc.get("null_result_statement") or "")
    if "null result" not in null.lower():
        msgs.append("null-result-statement-absent")
    return _reasons(not msgs, msgs)


def _lineage_ok(lin: Any) -> bool:
    if not isinstance(lin, dict):
        return False
    url = str(lin.get("resolved_url") or "")
    sha = str(lin.get("sha256") or "")
    ts = str(lin.get("fetched_at") or "")
    return url.startswith("http") and len(sha) == 64 and bool(ts)


def _cite_ok(doi: str) -> bool:
    doi = doi.strip()
    if doi.lower().startswith("arxiv:"):
        return bool(ARXIV_RE.match(doi.split(":", 1)[1]))
    if ARXIV_RE.match(doi):
        return True
    return bool(DOI_RE.match(doi))


def check_mechanisms(doc: dict) -> tuple[bool, str]:
    msgs: list[str] = []
    mechs = doc.get("mechanisms")
    if not isinstance(mechs, list) or len(mechs) < 4:
        return False, "mechanisms-too-few"
    split = doc.get("new_versus_restated") or {}
    new_ids = set(split.get("new") or [])
    rest_ids = set(split.get("restated_null_results") or [])
    e3_ids = set(split.get("not_promoted_e3") or [])
    seen: set[str] = set()
    for m in mechs:
        if not isinstance(m, dict):
            msgs.append("mechanism-not-object")
            continue
        mid = str(m.get("id") or "")
        missing = [k for k in REQUIRED_MECH if k not in m]
        if missing:
            msgs.append(f"{mid or '?'} missing:{','.join(missing)}")
        if mid in seen:
            msgs.append(f"duplicate-id:{mid}")
        seen.add(mid)
        tier = str(m.get("evidence_tier") or "")
        if tier not in TIERS:
            msgs.append(f"{mid} bad-tier:{tier}")
        band = str(m.get("confidence_band") or "")
        if band not in BANDS:
            msgs.append(f"{mid} bad-band:{band}")
        sp = str(m.get("split") or "")
        if sp not in SPLITS:
            msgs.append(f"{mid} bad-split:{sp}")
        if not _lineage_ok(m.get("source_lineage")):
            msgs.append(f"{mid} lineage-incomplete")
        if not _cite_ok(str(m.get("doi_or_arxiv") or "")):
            msgs.append(f"{mid} doi-or-arxiv-malformed")
        sec = str(m.get("section_or_figure") or "")
        if len(sec) < 8:
            msgs.append(f"{mid} section-too-short")
        caveat = str(m.get("strongest_caveat") or "")
        if len(caveat) < 24:
            msgs.append(f"{mid} caveat-too-short")
        eff = m.get("effect_size")
        base = m.get("baseline")
        has_pair = isinstance(eff, str) and len(eff) >= 8 and isinstance(base, str) and len(base) >= 8
        if not has_pair:
            if tier != "E3":
                msgs.append(f"{mid} missing-effect-baseline-not-e3")
            if mid in new_ids:
                msgs.append(f"{mid} e3-cannot-promote")
        if sp == "NEW":
            if mid not in new_ids:
                msgs.append(f"{mid} split-NEW-not-listed")
            if tier == "E3":
                msgs.append(f"{mid} new-is-e3")
        if sp == "RESTATED-NULL":
            if mid not in rest_ids:
                msgs.append(f"{mid} restated-not-listed")
        if sp == "E3-NOT-PROMOTED":
            if mid not in e3_ids:
                msgs.append(f"{mid} e3-not-listed")
            if tier != "E3":
                msgs.append(f"{mid} marked-e3-split-but-tier-{tier}")
    if new_ids - seen:
        msgs.append(f"split-new-missing-row:{sorted(new_ids - seen)}")
    if rest_ids - seen:
        msgs.append(f"split-restated-missing-row:{sorted(rest_ids - seen)}")
    return _reasons(not msgs, msgs)


def _novelty_residue(text: str) -> str:
    return FIRE_SILENT.sub(" ", text)


def check_novelty_not_paraphrase(doc: dict) -> tuple[bool, str]:
    """NEW rows must name an object the both-states pair does not already require."""
    msgs: list[str] = []
    split = doc.get("new_versus_restated") or {}
    new_ids = list(split.get("new") or [])
    by_id = {m.get("id"): m for m in (doc.get("mechanisms") or []) if isinstance(m, dict)}
    for mid in new_ids:
        m = by_id.get(mid)
        if not isinstance(m, dict):
            msgs.append(f"{mid} missing-row")
            continue
        tokens = NEW_NOVELTY.get(mid)
        if not tokens:
            msgs.append(f"{mid} new-id-not-in-novelty-vocabulary")
            continue
        text = str(m.get("not_already_in_rule") or "")
        if len(text) < 40:
            msgs.append(f"{mid} novelty-too-short")
            continue
        residue = _novelty_residue(text)
        if len(residue.replace(" ", "")) < 32:
            msgs.append(f"{mid} novelty-is-both-states-paraphrase")
        if not any(t in text.lower() for t in tokens):
            msgs.append(f"{mid} novelty-missing-required-token")
    rest_ids = list(split.get("restated_null_results") or [])
    for mid in rest_ids:
        m = by_id.get(mid)
        if not isinstance(m, dict):
            continue
        if "null result" not in str(m.get("not_already_in_rule") or "").lower() and "null result" not in str(
            m.get("canonical_mechanism") or ""
        ).lower():
            # restated rows must declare the null, not dress agreement as novelty
            if str(m.get("split")) == "RESTATED-NULL" and "restat" not in str(
                m.get("not_already_in_rule") or ""
            ).lower():
                msgs.append(f"{mid} restated-not-labelled-null")
    return _reasons(not msgs, msgs)


def check_numbers_match_snapshots(doc: dict) -> tuple[bool, str]:
    nums = load_numbers()
    msgs: list[str] = []
    by_id = {m.get("id"): m for m in (doc.get("mechanisms") or []) if isinstance(m, dict)}
    pairs = (
        ("M-U-COMPARABLE", "jackson_2006", "0.39", "1.0"),
        ("M-QUANT-NULL", "microscope_2017", "10^-15", "0"),
        ("M-EMPIRICAL-NULL", "schuemie_2014", "50%", "5%"),
        ("M-PLACEBO-RITUAL", "hrobjartsson_2010", "-0.28", "0"),
        ("M-BLIND-FREEZE", "klein_roodman_2005", "3", "0"),
    )
    for mid, key, eff_tok, base_tok in pairs:
        m = by_id.get(mid)
        snap = nums.get(key) or {}
        if not isinstance(m, dict):
            msgs.append(f"{mid} missing-for-number-check")
            continue
        blob = (str(m.get("effect_size")) + " " + str(m.get("baseline"))).replace("×", "x")
        blob = blob.replace("−", "-").replace("–", "-")
        if key == "microscope_2017":
            if "10" not in blob or "15" not in blob:
                msgs.append(f"{mid} missing-e-15")
            if "0" not in str(m.get("baseline")):
                msgs.append(f"{mid} missing-null-baseline-0")
        elif key == "klein_roodman_2005":
            if "3" not in str(m.get("effect_size")):
                msgs.append(f"{mid} missing-3sigma")
            if "0" not in str(m.get("baseline")):
                msgs.append(f"{mid} missing-0sigma-baseline")
        else:
            if eff_tok not in blob:
                msgs.append(f"{mid} effect-token-absent:{eff_tok}")
            if base_tok not in (str(m.get("baseline")) + " " + blob):
                msgs.append(f"{mid} baseline-token-absent:{base_tok}")
        # snapshot itself must carry the same tokens (fixture integrity)
        sblob = json.dumps(snap)
        if key == "jackson_2006" and "0.39" not in sblob:
            msgs.append("snapshot-jackson-corrupt")
        if key == "schuemie_2014" and "50%" not in sblob:
            msgs.append("snapshot-schuemie-corrupt")
    return _reasons(not msgs, msgs)


def well_formed(doc: dict) -> tuple[bool, str]:
    a, ra = check_sentinel_and_state(doc)
    b, rb = check_mechanisms(doc)
    ok = a and b
    parts = [p for p, s in ((ra, a), (rb, b)) if not s]
    return ok, " | ".join(parts) if parts else "ok"


def overclaim_ok(doc: dict) -> tuple[bool, str]:
    a, ra = check_novelty_not_paraphrase(doc)
    b, rb = check_numbers_match_snapshots(doc)
    ok = a and b
    parts = [p for p, s in ((ra, a), (rb, b)) if not s]
    return ok, " | ".join(parts) if parts else "ok"
