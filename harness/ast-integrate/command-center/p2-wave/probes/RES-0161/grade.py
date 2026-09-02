"""Live grade: re-check CELL_SPEC needles against captured bytes."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CAPTURES = HERE / "captures"
INDEX_PATH = CAPTURES / "INDEX.json"
DEFINITION_PATH = HERE / "DEFINITION.json"

import sources as S  # noqa: E402

FAMILY_TOKENS: tuple[tuple[bytes, str], ...] = (
    (b"research/evidence ", "research-evidence"),
    (b"engineering/reliability ", "engineering-reliability"),
    (b"security/governance ", "security-governance"),
    (b"product/design ", "product-design"),
    (b"data/science ", "data-science"),
    (b"collective-intelligence/meta ", "collective-intelligence-meta"),
)


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def evaluate_presence(presence: str, hits: list[bool]) -> bool:
    if presence in {"PRESENT", "PARTIAL"}:
        return bool(hits) and all(hits)
    if presence == "ABSENT":
        return bool(hits) and all(not h for h in hits)
    return False


def wish_list(necessity: dict) -> bool:
    return bool(necessity) and all(
        (v or {}).get("verdict") == "NECESSARY" for v in necessity.values()
    )


def load_index() -> dict:
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def capture_bytes(cid: str) -> bytes:
    path = CAPTURES / f"{cid}.bin"
    if not path.is_file():
        raise FileNotFoundError(cid)
    return path.read_bytes()


def quote_around(body: bytes, needle: str, width: int = 72) -> str | None:
    nb = needle.encode("utf-8")
    i = body.find(nb)
    if i < 0:
        return None
    lo = max(0, i - width)
    hi = min(len(body), i + len(nb) + width)
    frag = body[lo:hi].decode("utf-8", "replace")
    return re.sub(r"\s+", " ", frag).strip()


def parse_family_counts(raw: bytes) -> list[dict]:
    """Parse family sizes from catalog bytes. The sum is computed, not hardcoded."""
    out: list[dict] = []
    for token, fid in FAMILY_TOKENS:
        i = raw.find(token)
        if i < 0:
            raise ValueError(f"catalog-token-missing:{fid}")
        rest = raw[i + len(token) : i + len(token) + 8]
        m = re.match(rb"(\d+)", rest)
        if not m:
            raise ValueError(f"catalog-token-unparsed:{fid}")
        out.append({"id": fid, "n": int(m.group(1)), "token": token.decode("ascii")})
    return out


def rail_record(index_row: dict, needle: str, body: bytes, kind: str) -> dict:
    hit = needle.encode("utf-8") in body
    permalink = index_row.get("url") or ""
    return {
        "kind": kind,
        "capture_id": index_row["id"],
        "permalink": permalink,
        "requested_url": index_row.get("url"),
        "final_url": index_row.get("final_url") or permalink,
        "fetch_timestamp": index_row.get("fetched_at"),
        "http_status": int(index_row.get("http_status") or 0),
        "sha256": index_row.get("sha256"),
        "bytes": index_row.get("bytes"),
        "capture_path": index_row.get("path"),
        "needle": needle,
        "hit": hit,
        "quote": quote_around(body, needle) if hit else None,
    }


def grade() -> dict:
    defn_sha = sha256_file(DEFINITION_PATH)
    defn = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    if tuple(defn["engines"]) != S.ENGINES:
        raise SystemExit("FAILED:RES-0161 DEFINITION engines drifted from sources.py")
    if tuple(defn["features"]) != S.FEATURES:
        raise SystemExit("FAILED:RES-0161 DEFINITION features drifted from sources.py")
    if defn.get("negative_control_feature") != "matrix_expansion":
        raise SystemExit("FAILED:RES-0161 DEFINITION negative control drifted")
    if defn.get("negative_control_verdict") != "NOT-NECESSARY":
        raise SystemExit("FAILED:RES-0161 DEFINITION negative verdict drifted")
    if defn.get("frozen_before_count") is not True:
        raise SystemExit("FAILED:RES-0161 DEFINITION not frozen_before_count")
    if defn.get("same_rule_all_vendors") is not True:
        raise SystemExit("FAILED:RES-0161 DEFINITION same_rule_all_vendors is not true")

    index = load_index()
    by_id = {c["id"]: c for c in index.get("captures") or [] if isinstance(c, dict)}
    integrity: list[str] = []
    for cid, rec in by_id.items():
        path = CAPTURES / f"{cid}.bin"
        if not path.is_file():
            integrity.append(f"missing:{cid}")
            continue
        live = sha256_bytes(path.read_bytes())
        if live != rec.get("sha256"):
            integrity.append(f"sha-mismatch:{cid}")
        if rec.get("ok") is not True:
            integrity.append(f"not-ok:{cid}")

    expected = [(e, f) for e in S.ENGINES for f in S.FEATURES]
    missing_cells = [k for k in expected if k not in S.CELL_SPEC]
    extra_cells = [k for k in S.CELL_SPEC if k not in set(expected)]

    cells: list[dict] = []
    mismatches: list[str] = []
    for engine, feature in expected:
        spec = S.CELL_SPEC[(engine, feature)]
        rails_out: list[dict] = []
        hits: list[bool] = []
        kinds: list[str] = []
        for rail in spec["rails"]:
            cid = rail["capture_id"]
            needle = rail["needle"]
            rec = by_id.get(cid)
            if rec is None:
                mismatches.append(f"{engine}/{feature}:capture-missing:{cid}")
                continue
            body = capture_bytes(cid)
            kind = rec.get("kind") or "prose"
            kinds.append(kind)
            rr = rail_record(rec, needle, body, kind)
            rails_out.append(rr)
            hits.append(bool(rr["hit"]))
        presence = spec["presence"]
        ok = evaluate_presence(presence, hits)
        if not ok:
            mismatches.append(
                f"{engine}/{feature}:{presence}:hits={hits}"
            )
        band = {
            "PRESENT": "almost-certain",
            "PARTIAL": "highly-likely",
            "ABSENT": "highly-likely",
        }.get(presence, "roughly-even")
        cells.append(
            {
                "row": engine,
                "column": feature,
                "engine": engine,
                "feature": feature,
                "presence": presence,
                "ok": ok,
                "note": spec["note"],
                "confidence_band": band,
                "sherman_kent_band": band,
                "rails": rails_out,
                "rail_kinds": kinds,
            }
        )

    declared_supported = sum(
        1 for c in cells if c["presence"] in {"PRESENT", "PARTIAL"}
    )
    observed_hits = sum(
        1 for c in cells if c["rails"] and all(r.get("hit") for r in c["rails"])
    )
    rel = (
        0.0
        if max(declared_supported, observed_hits) == 0
        else abs(declared_supported - observed_hits)
        / max(declared_supported, observed_hits)
    )

    catalog_row = by_id.get("local-catalog") or {}
    catalog_body = capture_bytes("local-catalog")
    parsed_families = parse_family_counts(catalog_body)
    parsed_sum = sum(f["n"] for f in parsed_families)
    defn_sum = sum(int(f["n"]) for f in defn["blueprint_families"])

    nec_rows = []
    for feat in S.FEATURES:
        n = S.NECESSITY[feat]
        nec_rows.append(
            {
                "feature": feat,
                "verdict": n["verdict"],
                "category_id": n.get("category_id"),
                "spec_anchor": n.get("spec_anchor"),
                "cannot_express_without": n.get("cannot_express_without"),
                "why_not_necessary": n.get("why_not_necessary"),
                "negative_control": bool(n.get("negative_control")),
            }
        )

    gha_matrix = next(
        c for c in cells if c["engine"] == "github-actions" and c["feature"] == "matrix_expansion"
    )
    return {
        "definition_id": defn["id"],
        "definition_sha256": defn_sha,
        "definition_locked_hash_before_enumerate": True,
        "same_rule_all_vendors": True,
        "index_integrity_errors": integrity,
        "missing_cells": [f"{a}/{b}" for a, b in missing_cells],
        "extra_cells": [f"{a}/{b}" for a, b in extra_cells],
        "mismatches": mismatches,
        "n_cells": len(cells),
        "n_ok": sum(1 for c in cells if c["ok"]),
        "cells": cells,
        "necessity": nec_rows,
        "wish_list": wish_list(S.NECESSITY),
        "negative_control": {
            "feature": "matrix_expansion",
            "verdict": S.NECESSITY["matrix_expansion"]["verdict"],
            "github_actions_presence": gha_matrix["presence"],
            "why": S.NECESSITY["matrix_expansion"]["why_not_necessary"],
        },
        "two_pass": {
            "vendor_id": "dsl-feature-presence",
            "pass_a": "CELL_SPEC declared PRESENT+PARTIAL",
            "pass_b": "live both-needles-hit count",
            "pass_a_count": declared_supported,
            "pass_b_count": observed_hits,
            "relative_delta": rel,
            "within_10_percent": rel <= 0.10,
        },
        "families": {
            "parsed": parsed_families,
            "parsed_sum": parsed_sum,
            "definition_sum": defn_sum,
            "sums_agree": parsed_sum == defn_sum,
            "catalog_sha256": catalog_row.get("sha256"),
        },
        "index_fetched_at": index.get("fetched_at"),
        "n_captures": len(by_id),
    }
