#!/usr/bin/env python3
"""Both-states checker for the RES-0100 research-claim record.

Green on a complete record. Red if any accuracy figure lacks catalog_size,
if a no-baseline figure is marked promotable, if the adopt-native verdict is
missing, or if reviewer partitions overlap.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
VERDICTS = frozenset({"CORROBORATE", "REFUTE", "CORROBORATED", "REFUTED"})
SENTINEL = "SUCCESS:RES-0100"


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def digest_file(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def _fail(reasons: list[str], msg: str) -> None:
    reasons.append(msg)


def figures(doc: dict) -> list[dict]:
    out: list[dict] = []
    for row in doc.get("accuracy_figures") or []:
        if isinstance(row, dict):
            out.append(row)
    return out


def check_record(doc: Any, repo: Path | None = None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(doc, dict):
        return False, ["record is not an object"]
    if str(doc.get("unit_id") or "") != "RES-0100":
        _fail(reasons, f"unit_id {doc.get('unit_id')!r} != RES-0100")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        _fail(reasons, f"self-declared {st}")
    blob = ""
    try:
        import json

        blob = json.dumps(doc, ensure_ascii=True)
    except TypeError:
        blob = str(doc)
    if SENTINEL not in blob:
        _fail(reasons, "SUCCESS:RES-0100 sentinel absent")
    if "corroborate-or-refute" not in blob.lower() and "corroborate or refute" not in blob.lower():
        # verdict object is the corroborate-or-refute; also require the phrase
        verdict = doc.get("adopt_native_verdict") or {}
        if str(verdict.get("verdict") or "").upper() not in VERDICTS:
            _fail(reasons, "corroborate-or-refute verdict absent")

    figs = figures(doc)
    if len(figs) < 6:
        _fail(reasons, f"accuracy_figures n={len(figs)} want>=6")
    sizes: set[int] = set()
    for fig in figs:
        fid = str(fig.get("id") or "?")
        if "catalog_size" not in fig:
            _fail(reasons, f"{fid} missing catalog_size")
            continue
        try:
            size = int(fig["catalog_size"])
        except (TypeError, ValueError):
            _fail(reasons, f"{fid} catalog_size not int: {fig.get('catalog_size')!r}")
            continue
        sizes.add(size)
        if "baseline" not in fig or fig.get("baseline") in (None, ""):
            if str(fig.get("evidence_tier") or "") != "E3":
                _fail(reasons, f"{fid} missing baseline but not E3")
            if fig.get("can_promote") is True:
                _fail(reasons, f"{fid} headline without baseline cannot promote")
        if fig.get("can_promote") is True and str(fig.get("evidence_tier") or "") == "E3":
            _fail(reasons, f"{fid} E3 cannot promote")
        if not fig.get("section_or_figure"):
            _fail(reasons, f"{fid} missing section_or_figure")
        if not (fig.get("arxiv") or fig.get("url") or fig.get("doi")):
            _fail(reasons, f"{fid} missing arxiv/url/doi")
        if fig.get("effect_size") is None and fig.get("can_promote") is True:
            _fail(reasons, f"{fid} null effect_size cannot promote")
    if len(sizes) < 3:
        _fail(reasons, f"catalog-size control failed: distinct sizes={sorted(sizes)}")

    verdict = doc.get("adopt_native_verdict") if isinstance(doc.get("adopt_native_verdict"), dict) else {}
    v = str(verdict.get("verdict") or "").upper()
    if v not in VERDICTS:
        _fail(reasons, f"adopt_native_verdict.verdict {v!r} not in {sorted(VERDICTS)}")
    if not str(verdict.get("settling_comparison") or "").strip():
        _fail(reasons, "settling_comparison absent")
    if not str(verdict.get("deciding_evidence") or "").strip() and not verdict.get("deciding_figure_ids"):
        _fail(reasons, "deciding evidence absent")

    reviewers = doc.get("reviewers") or []
    if not isinstance(reviewers, list) or len(reviewers) < 2:
        _fail(reasons, "need two partitioned reviewers")
    else:
        sets = []
        for rev in reviewers[:2]:
            part = rev.get("source_partition") or rev.get("families") or []
            sets.append(set(str(x) for x in part))
        if len(sets) == 2 and sets[0] & sets[1]:
            _fail(reasons, f"reviewer partitions overlap: {sorted(sets[0] & sets[1])}")
        if len(sets) == 2 and (not sets[0] or not sets[1]):
            _fail(reasons, "empty reviewer partition")

    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 3:
        _fail(reasons, "need >=3 canonical claims")
    else:
        for cl in claims:
            for key in (
                "claim_id",
                "canonical_mechanism",
                "source_lineage",
                "evidence_tier",
                "confidence_band",
                "settling_probe",
                "freshness_stamp",
            ):
                if not cl.get(key):
                    _fail(reasons, f"claim {cl.get('claim_id')} missing {key}")
            if "snapshot_sha256" not in cl:
                _fail(reasons, f"claim {cl.get('claim_id')} missing snapshot_sha256")

    if repo is not None:
        snap_root = repo / "command-center/p2-wave/probes/RES-0100/snapshots"
        for fig in figs:
            rel = str(fig.get("snapshot") or "")
            pin = str(fig.get("snapshot_pin") or "")
            if not rel or not pin:
                _fail(reasons, f"{fig.get('id')} missing snapshot/pin")
                continue
            path = snap_root / rel
            if not path.is_file():
                _fail(reasons, f"snapshot missing {rel}")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if pin not in text:
                _fail(reasons, f"{fig.get('id')} pin {pin!r} not in {rel}")
        recorded = doc.get("snapshot_sha256") or {}
        if isinstance(recorded, dict):
            for name, sha in recorded.items():
                path = snap_root / str(name)
                if not path.is_file():
                    _fail(reasons, f"hashed snapshot missing {name}")
                    continue
                live = digest_file(path)
                if live != sha:
                    _fail(reasons, f"snapshot sha mismatch {name}")

    return len(reasons) == 0, reasons


def mutant_strip_catalog_size(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    rows = mutant.get("accuracy_figures") or []
    for row in rows:
        if isinstance(row, dict) and "catalog_size" in row:
            del row["catalog_size"]
            break
    return mutant
