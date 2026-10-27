#!/usr/bin/env python3
"""Shared contract checks for RES-0137 gem-candidate scan.

A scan that marks every mechanism TRANSFER has not modelled the control plane.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = (
    REPO
    / "command-center/research/sources-frontier/RES-0137-cross-domain-niche-community-scan.json"
)
INDEX = HERE / "sources_index.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
BANDS = {
    "almost-certain",
    "likely",
    "roughly-even",
    "unlikely",
    "remote",
}
REQUIRED_COMMUNITIES = {
    "bioinformatics-pipeline-runners",
    "game-modding-toolchains",
    "reverse-engineering-automation",
    "hpc-job-schedulers",
    "vfx-render-farms",
}
SENTINEL = "SUCCESS:RES-0137"
LEAST_THREE = {
    "MECH-NF-TASK-HASH-CACHE",
    "MECH-CWLPROV-BAGIT",
    "MECH-SLURM-AFTEROK",
}
NEGATIVE_ID = "MECH-MO2-USVFS"


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_index() -> dict[str, dict]:
    rows = load_json(INDEX)
    out: dict[str, dict] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("ok") and row.get("id"):
            out[str(row["id"])] = row
    return out


def quote_in_snapshot(source_id: str, quote: str, index: dict[str, dict]) -> bool:
    row = index.get(source_id)
    if not row:
        return False
    path = HERE / str(row.get("path") or "")
    if not path.is_file():
        return False
    raw = path.read_bytes()
    if sha256_bytes(raw) != str(row.get("sha256") or ""):
        return False
    if quote.encode("utf-8") in raw:
        return True
    return quote in raw.decode("utf-8", "replace")


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


def transfer_scan(doc: dict) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {
            "pass": False,
            "errors": ["not-object"],
            "n_transfer": 0,
            "n_not_transfer": 0,
            "n_claims": 0,
        }
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        errors.append(f"self-declared:{doc.get('state')}")
    blob = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in blob:
        errors.append("sentinel-absent")
    if str(doc.get("report_kind") or "") != "gem-candidate":
        errors.append("report-kind")

    communities = {
        str(c.get("id"))
        for c in (doc.get("communities_scanned") or [])
        if isinstance(c, dict)
    }
    missing_c = REQUIRED_COMMUNITIES - communities
    if missing_c:
        errors.append(f"communities-missing:{sorted(missing_c)}")

    mechs = [m for m in (doc.get("mechanisms") or []) if isinstance(m, dict)]
    if len(mechs) < 5:
        errors.append("mechanisms-lt-5")
    transfers = [m for m in mechs if m.get("transfer_verdict") == "TRANSFER"]
    nontransfers = [m for m in mechs if m.get("transfer_verdict") == "NOT_TRANSFERABLE"]
    if not nontransfers:
        errors.append("negative-control-absent")
    if len(transfers) < 3:
        errors.append("transfer-lt-3")
    if mechs and not nontransfers:
        errors.append("control-plane-unmodelled")
        errors.append("everything-transfers")

    nc = doc.get("negative_control") or {}
    nc_id = str(nc.get("mechanism_id") or "")
    block = str(nc.get("blocking_reason") or "")
    if len(block) < 24:
        errors.append("blocking-reason-thin")
    if nc_id != NEGATIVE_ID:
        errors.append("negative-control-id")
    nc_mech = next((m for m in mechs if str(m.get("id")) == nc_id), None)
    if nc_mech is None:
        errors.append("negative-control-id-unknown")
    elif nc_mech.get("transfer_verdict") != "NOT_TRANSFERABLE":
        errors.append("negative-control-not-marked")
    else:
        mech_block = str(nc_mech.get("blocking_reason") or "")
        if len(mech_block) < 24:
            errors.append("mechanism-blocking-thin")

    three = [str(x) for x in (doc.get("least_adaptation_three") or [])]
    if set(three) != LEAST_THREE:
        errors.append(f"least-adaptation-set:{three}")
    by_id = {str(m.get("id")): m for m in mechs}
    for mid in three:
        m = by_id.get(mid)
        if m is None:
            errors.append(f"least-adaptation-unknown:{mid}")
            continue
        if m.get("transfer_verdict") != "TRANSFER":
            errors.append(f"least-adaptation-not-transfer:{mid}")
        cost = m.get("adaptation_cost") or {}
        rewrite = cost.get("must_rewrite") or []
        if not isinstance(rewrite, list) or len(rewrite) < 1:
            errors.append(f"adaptation-cost-missing:{mid}")
        if mid == nc_id:
            errors.append("negative-control-in-top-three")

    covered = {str(m.get("community_id")) for m in mechs}
    if not REQUIRED_COMMUNITIES <= covered:
        errors.append(f"mechanism-communities:{sorted(REQUIRED_COMMUNITIES - covered)}")

    for m in mechs:
        docs = m.get("community_tool_docs") or []
        if not isinstance(docs, list) or len(docs) < 1:
            errors.append(f"docs-missing:{m.get('id')}")
        if m.get("transfer_verdict") == "TRANSFER":
            cost = m.get("adaptation_cost") or {}
            if not (cost.get("must_rewrite") or []):
                errors.append(f"transfer-without-rewrite:{m.get('id')}")

    index = snapshot_index()
    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 4:
        errors.append("claims-lt-4")
    for claim in claims:
        cid = str(claim.get("claim_id") or "?")
        if str(claim.get("sherman_kent_band") or "") not in BANDS:
            errors.append(f"band:{cid}")
        path = str(claim.get("independent_verification_path") or "")
        if len(path) < 16:
            errors.append(f"verify-path:{cid}")
        lin = [x for x in (claim.get("source_lineage") or []) if isinstance(x, dict)]
        if len(lin) < 2:
            errors.append(f"single-signal:{cid}")
            continue
        urls = {str(x.get("resolved_url")) for x in lin}
        sids = {str(x.get("source_id")) for x in lin}
        if len(urls) < 2 and len(sids) < 2:
            errors.append(f"signals-not-independent:{cid}")
        for entry in lin[:2]:
            problem = lineage_ok(entry, index)
            if problem:
                errors.append(f"{cid}:{problem}")

    return {
        "pass": len(errors) == 0,
        "errors": errors,
        "n_transfer": len(transfers),
        "n_not_transfer": len(nontransfers),
        "n_claims": len(claims),
    }


def everything_transfers_mutant(doc: dict) -> dict:
    mutant = json.loads(json.dumps(doc))
    for m in mutant.get("mechanisms") or []:
        if isinstance(m, dict):
            m["transfer_verdict"] = "TRANSFER"
            m["blocking_reason"] = None
            cost = m.setdefault("adaptation_cost", {})
            if not cost.get("must_rewrite"):
                cost["must_rewrite"] = ["mutant-placeholder"]
    nc = mutant.setdefault("negative_control", {})
    nc["blocking_reason"] = ""
    nc["mechanism_id"] = ""
    return mutant
