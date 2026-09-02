#!/usr/bin/env python3
"""Build vendor coverage index and grade practitioner candidates mechanically."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import REPO, VENDOR_SWEEP, folded, load_json  # noqa: E402
from grading import apply_rule, authority_for_class, production_claim, unaffiliated
from neutralize import neutralize

import html as htmlmod
import re


def html_to_text(raw: str) -> str:
    t = raw or ""
    t = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", t)
    t = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", t)
    t = re.sub(r"(?is)<svg[^>]*>.*?</svg>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = htmlmod.unescape(t)
    return " ".join(t.split())


def load_rule() -> dict:
    return load_json(HERE / "grading_rule.json")


def load_catalog() -> dict:
    return load_json(HERE / "sources.json")


def load_vendor_seed() -> dict:
    return load_json(HERE / "vendor_seed.json")


def capture_text(source_id: str) -> tuple[str, dict | None]:
    cap_dir = HERE / "captures"
    index_path = cap_dir / "INDEX.json"
    meta = None
    if index_path.is_file():
        for row in load_json(index_path):
            if row.get("id") == source_id:
                meta = row
                break
    body_path = cap_dir / f"{source_id}.body"
    if source_id == "planted-injection":
        body_path = HERE / "fixtures" / "planted_injection.body"
    if not body_path.is_file():
        return "", meta
    return body_path.read_text(encoding="utf-8", errors="replace"), meta


def vendor_coverage(rule: dict) -> dict:
    seed = load_vendor_seed()
    present = {}
    wfa21 = REPO / VENDOR_SWEEP
    from_artifact = False
    if wfa21.is_file() and wfa21.stat().st_size > 0:
        from_artifact = True
        try:
            doc = load_json(wfa21)
        except Exception:  # noqa: BLE001 - absent/invalid WFA-0021 is recorded, not rebuilt
            doc = {}
        for item in _iter_vendor_keys(doc):
            present[item["canon_key"]] = item
    # Always union catalog-named first-party keys that the vendor captures actually contain.
    for mech in seed.get("mechanisms") or []:
        key = mech["canon_key"]
        needles = mech.get("needles") or []
        hit_from = []
        for sid in (
            "vendor-claude-hooks",
            "vendor-claude-subagents",
            "vendor-agents-md",
        ):
            text, _ = capture_text(sid)
            fold = folded(text)
            if any(folded(n) in fold for n in needles):
                hit_from.append(sid)
        if hit_from or key in present:
            row = dict(mech)
            row["matched_vendor_captures"] = hit_from
            present[key] = row
    return {
        "wfa_0021_present": from_artifact,
        "wfa_0021_path": VENDOR_SWEEP,
        "keys": sorted(present),
        "records": present,
    }


def _iter_vendor_keys(doc) -> list[dict]:
    out = []
    if not isinstance(doc, dict):
        return out
    for bucket in (doc.get("mechanisms"), doc.get("findings"), doc.get("records")):
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if not isinstance(item, dict):
                continue
            key = item.get("canon_key") or item.get("id")
            if key:
                out.append({"canon_key": str(key), "id": item.get("id")})
    return out


def quote_window(text: str, needle: str, radius: int = 180) -> str | None:
    if not text or not needle:
        return None
    idx = text.find(needle)
    if idx < 0:
        idx = folded(text).find(folded(needle))
        if idx < 0:
            return None
        # folded index is not a byte index; fall back to original case-insensitive
        low = text.casefold()
        nlow = needle.casefold()
        idx = low.find(nlow)
        if idx < 0:
            return None
        start = max(0, idx - radius)
        end = min(len(text), idx + len(needle) + radius)
        return text[start:end]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(needle) + radius)
    return text[start:end]


def source_by_id(catalog: dict, sid: str) -> dict:
    for s in catalog.get("sources") or []:
        if s.get("id") == sid:
            return s
    raise KeyError(sid)


def candidate_hits(candidate: dict, catalog: dict, rule: dict) -> list[dict]:
    """Every source whose neutralized visible text contains a candidate needle."""
    hits = []
    needles = candidate.get("quote_needles") or []
    require_all = candidate.get("require_all") or []
    for src in catalog.get("sources") or []:
        text, meta = capture_text(src["id"])
        neu = neutralize(text, rule.get("injection_patterns"))
        visible = html_to_text(neu["neutralized"])
        if require_all and not all(
            folded(n) in folded(visible) or n in (neu["neutralized"] or "")
            for n in require_all
        ):
            continue
        found = None
        for n in needles:
            found = quote_window(visible, n) or quote_window(neu["neutralized"], n)
            if found:
                break
        if not found:
            continue
        hits.append(
            {
                "source": src,
                "meta": meta,
                "neutralize": {
                    "injection_detected": neu["injection_detected"],
                    "log": neu["log"],
                },
                "verbatim_quote": " ".join(found.split()),
                "production_claim": production_claim(visible, rule),
                "authority": authority_for_class(src["class"], rule),
            }
        )
    return hits


def grade_candidate(candidate: dict, catalog: dict, rule: dict, vendor: dict) -> dict:
    hits = candidate_hits(candidate, catalog, rule)
    primary = None
    for h in hits:
        if h["source"]["id"] == candidate.get("primary_source"):
            primary = h
            break
    if primary is None and hits:
        primary = hits[0]
    in_vendor = candidate["canon_key"] in set(vendor.get("keys") or [])
    if primary is None:
        result = apply_rule(
            injection_detected=False,
            verbatim_quote=None,
            authority="RETELLER",
            production_claim_value="NONE",
            corroboration="SINGLE",
            in_vendor=in_vendor,
        )
        return {
            "id": candidate["id"],
            "canon_key": candidate["canon_key"],
            "name": candidate["name"],
            "verbatim_quote": None,
            "source_id": candidate.get("primary_source"),
            "source_url": source_by_id(catalog, candidate["primary_source"]).get("url"),
            "retrieved_at": None,
            "http_status": None,
            "authority": "RETELLER",
            "production_claim": "NONE",
            "corroboration": "SINGLE",
            "corroborating_source_ids": [],
            "in_vendor": in_vendor,
            "duplicate_of": vendor["records"].get(candidate["canon_key"], {}).get("id")
            if in_vendor
            else None,
            "injection_log": [],
            "settling_experiment": (
                f"re-fetch {candidate.get('primary_source')} until quote needles land"
            ),
            **result,
        }

    others = [h for h in hits if h["source"]["id"] != primary["source"]["id"]]
    dual_ids = []
    for h in others:
        if unaffiliated(primary["source"], h["source"]):
            dual_ids.append(h["source"]["id"])
    corr = "DUAL" if dual_ids else "SINGLE"
    inj = bool(primary["neutralize"]["injection_detected"])
    result = apply_rule(
        injection_detected=inj,
        verbatim_quote=primary["verbatim_quote"],
        authority=primary["authority"],
        production_claim_value=primary["production_claim"],
        corroboration=corr,
        in_vendor=in_vendor,
    )
    settling = None
    if result["disposition"] == "UNVERIFIED":
        settling = (
            "Named second unaffiliated source (different registrable host, not the "
            f"same GitHub repo) quoting {candidate['canon_key']} as in-production, "
            "or an implementing code artifact on this estate."
        )
    meta = primary.get("meta") or {}
    dup = None
    if in_vendor:
        rec = vendor["records"].get(candidate["canon_key"]) or {}
        dup = rec.get("id") or f"vendor:{candidate['canon_key']}"
    return {
        "id": candidate["id"],
        "canon_key": candidate["canon_key"],
        "name": candidate["name"],
        "verbatim_quote": primary["verbatim_quote"],
        "source_id": primary["source"]["id"],
        "source_url": primary["source"].get("url"),
        "retrieved_at": meta.get("fetched_at"),
        "http_status": meta.get("http_status"),
        "authority": primary["authority"],
        "production_claim": primary["production_claim"],
        "corroboration": corr,
        "corroborating_source_ids": dual_ids,
        "in_vendor": in_vendor,
        "duplicate_of": dup,
        "injection_log": primary["neutralize"]["log"],
        "settling_experiment": settling,
        "hit_source_ids": [h["source"]["id"] for h in hits],
        **result,
    }


def run_sweep() -> dict:
    rule = load_rule()
    catalog = load_catalog()
    vendor = vendor_coverage(rule)
    mechanisms = [
        grade_candidate(c, catalog, rule, vendor)
        for c in catalog.get("candidates") or []
    ]
    source_rows = []
    for src in catalog.get("sources") or []:
        text, meta = capture_text(src["id"])
        neu = neutralize(text, rule.get("injection_patterns"))
        meta = meta or {}
        source_rows.append(
            {
                "id": src["id"],
                "class": src["class"],
                "role": src["role"],
                "url": src["url"],
                "host": src["host"],
                "authority": authority_for_class(src["class"], rule),
                "retrieved_at": meta.get("fetched_at"),
                "http_status": meta.get("http_status"),
                "ok": meta.get("ok"),
                "sha256": meta.get("sha256"),
                "bytes": meta.get("bytes") if meta.get("bytes") is not None else len(text.encode("utf-8")),
                "injection_detected": neu["injection_detected"],
                "injection_log": neu["log"],
            }
        )
    counts = {
        "FINDING": sum(1 for m in mechanisms if m["disposition"] == "FINDING"),
        "UNVERIFIED": sum(1 for m in mechanisms if m["disposition"] == "UNVERIFIED"),
        "DUPLICATE-OF": sum(1 for m in mechanisms if m["disposition"] == "DUPLICATE-OF"),
        "REJECTED": sum(1 for m in mechanisms if m["disposition"] == "REJECTED"),
        "NOT-PROMOTED": sum(1 for m in mechanisms if m["disposition"] == "NOT-PROMOTED"),
        "novel_findings": [
            m["id"] for m in mechanisms if m["disposition"] == "FINDING"
        ],
    }
    return {
        "rule": rule,
        "vendor": vendor,
        "sources": source_rows,
        "mechanisms": mechanisms,
        "counts": counts,
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_sweep()["counts"], indent=2, sort_keys=True))
