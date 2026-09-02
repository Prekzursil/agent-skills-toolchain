"""MD/JSON mirror parity gate: id-set equality (A) plus field-level (B)."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from extract import (
    COMPARE_FIELDS,
    heading_ids,
    heading_records,
    id_set_equal,
    json_record_list,
    load_json_records,
    naive_backtick_ids,
    normalize_fields,
)
from newer import newer_side

SAMPLE_N = 30


def stratified_sample(records: list[dict[str, Any]], n: int = SAMPLE_N) -> list[dict[str, Any]]:
    """Round-robin across families so a 30-row sample is not one family."""
    if len(records) <= n:
        return list(records)
    by_fam: dict[str, list[dict[str, Any]]] = {}
    for rec in records:
        fam = str(rec.get("family") or "UNKNOWN")
        by_fam.setdefault(fam, []).append(rec)
    families = sorted(by_fam)
    iters = {f: iter(by_fam[f]) for f in families}
    out: list[dict[str, Any]] = []
    while len(out) < n:
        progressed = False
        for fam in families:
            try:
                out.append(next(iters[fam]))
                progressed = True
                if len(out) >= n:
                    break
            except StopIteration:
                continue
        if not progressed:
            break
    return out


def compare_texts(
    markdown: str,
    json_text: str,
    *,
    md_path: Path | None = None,
    json_path: Path | None = None,
    repo: Path | None = None,
    clocks: dict[str, int] | None = None,
    sample_n: int = SAMPLE_N,
) -> dict[str, Any]:
    md_ids = heading_ids(markdown)
    md_recs = {r["id"]: r for r in heading_records(markdown)}
    js_recs_raw = load_json_records(json_text)
    js_recs = [normalize_fields(r) for r in js_recs_raw]
    js_ids = [r["id"] for r in js_recs]
    js_map = {r["id"]: r for r in js_recs}

    signal_a = id_set_equal(md_ids, js_ids)
    signal_a["naive_backtick_ids"] = naive_backtick_ids(markdown)
    signal_a["naive_extra_vs_headings"] = sorted(
        set(signal_a["naive_backtick_ids"]) - set(md_ids)
    )

    universe = [r for r in js_recs if r["id"] in md_recs]
    sample = stratified_sample(universe, n=sample_n)
    drifts: list[dict[str, Any]] = []
    for rec in sample:
        ident = rec["id"]
        md_f = md_recs.get(ident) or {}
        js_f = js_map.get(ident) or {}
        for field in COMPARE_FIELDS:
            mv = str(md_f.get(field) or "")
            jv = str(js_f.get(field) or "")
            if mv != jv:
                drifts.append(
                    {
                        "id": ident,
                        "field": field,
                        "markdown": mv,
                        "json": jv,
                    }
                )
    fam_counts = Counter(str(r.get("family") or "") for r in sample)
    signal_b = {
        "sample_size": len(sample),
        "requested": sample_n,
        "sample_ids": [r["id"] for r in sample],
        "family_counts_in_sample": dict(sorted(fam_counts.items())),
        "fields": list(COMPARE_FIELDS),
        "drifts": drifts,
        "equal": len(drifts) == 0,
        "note": (
            "Set equality of ids cannot see a per-field drift. Signal B "
            "compares classification/licence/family on a stratified sample."
        ),
    }

    newer = None
    if repo is not None:
        newer = newer_side(md_path, json_path, repo, clocks=clocks)

    return {
        "signal_a": signal_a,
        "signal_b": signal_b,
        "newer": newer,
        "parity": bool(signal_a["equal"] and signal_b["equal"]),
        "json_record_n": len(js_recs_raw),
        "markdown_heading_n": len(md_ids),
    }


def compare_paths(
    md_path: Path,
    json_path: Path,
    repo: Path,
    clocks: dict[str, int] | None = None,
    sample_n: int = SAMPLE_N,
) -> dict[str, Any]:
    md = md_path.read_text(encoding="utf-8")
    js = json_path.read_text(encoding="utf-8")
    report = compare_texts(
        md,
        js,
        md_path=md_path,
        json_path=json_path,
        repo=repo,
        clocks=clocks,
        sample_n=sample_n,
    )
    report["markdown_path"] = md_path.as_posix()
    report["json_path"] = json_path.as_posix()
    return report


def plant_field_drift(markdown: str, ident: str, field: str, new_value: str) -> str:
    """Rewrite one field line under a named id heading. Leaves id set intact."""
    recs = heading_records(markdown)
    if ident not in {r["id"] for r in recs}:
        raise KeyError(ident)
    lines = markdown.splitlines(keepends=True)
    in_block = False
    field_keys = {field, "license"} if field == "licence" else {field}
    out: list[str] = []
    heading_hit = False
    replaced = False
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("#") and f"`{ident}`" in stripped:
            in_block = True
            heading_hit = True
            out.append(line)
            continue
        if in_block and stripped.startswith("#"):
            in_block = False
        if in_block and not replaced:
            low = stripped.lstrip("-* ").lower()
            if any(low.startswith(k + ":") for k in field_keys):
                nl = "\n" if line.endswith("\n") else ""
                prefix = "-" if stripped.lstrip().startswith("-") else "*"
                key = "licence" if field == "licence" else field
                # Keep US spelling if the original line used license.
                if low.startswith("license:"):
                    key = "license"
                out.append(f"{prefix} {key}: {new_value}{nl}")
                replaced = True
                continue
        out.append(line)
    if not heading_hit or not replaced:
        raise ValueError(f"plant failed heading={heading_hit} replaced={replaced}")
    return "".join(out)


def json_record_list_from_obj(doc: Any) -> list[dict[str, Any]]:
    return json_record_list(doc)


compare_texts = compare_texts
compare_paths = compare_paths
plant_field_drift = plant_field_drift
