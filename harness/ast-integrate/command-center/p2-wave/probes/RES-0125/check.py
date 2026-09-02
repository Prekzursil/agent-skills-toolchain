"""Independent checks for RES-0125 obligation table and pins."""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from labels import ALLOWED_LABELS, SENTINEL, UNIT
from table import MARKETPLACE_FIELDS, ROWS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0125.json"
CAP = HERE / "captures"

LOCKFILE = REPO / "tools/marketplace/schema/lockfile.schema.json"
A2_MARKET = (
    REPO
    / "command-center/p2-wave/probes/ARC-0055/fixtures/one-click-install/"
    / "marketplace/marketplace.harness.json"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def load_indexes() -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    for name in ("_index.json", "_index_wave2.json", "_index_wave3.json"):
        path = CAP / name
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = doc.get("captures") or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if isinstance(row, dict) and row.get("id"):
                by_id[str(row["id"])] = row
    return by_id


def capture_text(capture_id: str, indexes: dict[str, dict]) -> str:
    rec = indexes.get(capture_id)
    if not rec:
        raise FileNotFoundError(f"no index row for {capture_id}")
    rel = str(rec.get("capture_path") or "")
    path = REPO / rel if rel else CAP / capture_id
    if not path.is_file():
        # wave3 used the id as filename
        alt = CAP / capture_id
        if alt.is_file():
            path = alt
        else:
            raise FileNotFoundError(rel or capture_id)
    raw = path.read_bytes()
    live_sha = hashlib.sha256(raw).hexdigest()
    listed = rec.get("sha256")
    if listed and listed != live_sha:
        raise ValueError(f"sha mismatch {capture_id} listed={listed} live={live_sha}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def quote_in_capture(row: dict, indexes: dict[str, dict]) -> bool:
    blob = capture_text(str(row["capture_id"]), indexes)
    return str(row["quote"]) in blob


def labels_ok(rows: list[dict]) -> tuple[bool, str]:
    if not rows:
        return False, "empty-obligation-table"
    for row in rows:
        lab = row.get("required_versus_proposed")
        if lab not in ALLOWED_LABELS:
            return False, f"bad-label:{row.get('id')}:{lab}"
    return True, "ok"


def proposed_norm_present(rows: list[dict]) -> bool:
    return any(r.get("required_versus_proposed") == "proposed-norm" for r in rows)


def pin_ok(row: dict, indexes: dict[str, dict]) -> tuple[bool, str]:
    cid = str(row.get("capture_id") or "")
    rec = indexes.get(cid)
    if rec is None:
        return False, f"capture-missing:{cid}"
    if rec.get("http_status") != 200:
        return False, f"capture-not-200:{cid}:{rec.get('http_status')}"
    lineage = row.get("source_lineage") if isinstance(row.get("source_lineage"), dict) else {}
    ts = lineage.get("fetch_timestamp") or row.get("fetch_timestamp")
    sha = lineage.get("sha256") or row.get("capture_sha256")
    version = (
        row.get("document_version")
        or row.get("commit_sha")
        or lineage.get("version")
        or lineage.get("commit_sha")
    )
    if not ts or not sha or not version:
        return False, f"unpinned:{row.get('id')}"
    if rec.get("sha256") and sha != rec.get("sha256"):
        return False, f"sha-drift:{cid}"
    return True, "ok"


def lockfile_required_keys() -> set[str]:
    doc = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    defs = doc.get("$defs") or {}
    pkg = defs.get("package") or defs.get("locked_package") or {}
    return set(pkg.get("required") or [])


def a2_generated_keys() -> set[str]:
    doc = json.loads(A2_MARKET.read_text(encoding="utf-8"))
    gen = doc.get("_generated") or {}
    return set(gen.keys()) if isinstance(gen, dict) else set()


def check_artifact(doc: dict, indexes: dict[str, dict] | None = None) -> dict[str, Any]:
    indexes = indexes if indexes is not None else load_indexes()
    errors: list[str] = []
    if not isinstance(doc, dict):
        return {"pass": False, "errors": ["not-object"]}
    if doc.get("unit_id") != UNIT:
        errors.append("unit_id")
    text = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in text:
        errors.append("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"self-declared:{doc.get('state')}")
    if doc.get("not_legal_advice") is not True:
        errors.append("missing-not-legal-advice")
    rows = doc.get("obligation_table") or []
    if not isinstance(rows, list) or len(rows) < 8:
        errors.append(f"obligation-table-short:{len(rows) if isinstance(rows, list) else 0}")
        rows = []
    ok, why = labels_ok(rows if isinstance(rows, list) else [])
    if not ok:
        errors.append(why)
    if not proposed_norm_present(rows if isinstance(rows, list) else []):
        errors.append("proposed-norm-control-failed")
    for row in rows if isinstance(rows, list) else []:
        pok, pwhy = pin_ok(row, indexes)
        if not pok:
            errors.append(pwhy)
        try:
            if not quote_in_capture(row, indexes):
                errors.append(f"quote-absent:{row.get('id')}")
        except (OSError, ValueError, FileNotFoundError) as exc:
            errors.append(f"quote-check:{row.get('id')}:{type(exc).__name__}")
    fields = doc.get("marketplace_metadata") or []
    if not isinstance(fields, list) or len(fields) < 6:
        errors.append("marketplace-metadata-short")
    else:
        for field in fields:
            if field.get("required_versus_proposed") not in ALLOWED_LABELS:
                errors.append(f"field-label:{field.get('field')}")
        methods = [f for f in fields if f.get("field") == "generation_method"]
        if not methods:
            errors.append("generation_method-absent")
        elif methods[0].get("required_versus_proposed") != "required-by-terms":
            errors.append("generation_method-not-required-by-terms")
        c2pa = [f for f in fields if f.get("field") == "c2pa_manifest"]
        if c2pa and c2pa[0].get("required_versus_proposed") != "proposed-norm":
            errors.append("c2pa-not-proposed-norm")
    return {"pass": not errors, "errors": errors, "obligation_rows": len(rows)}


def mutant_drop_labels(doc: dict) -> dict:
    out = deepcopy(doc)
    for row in out.get("obligation_table") or []:
        row["required_versus_proposed"] = "unlabelled"
    return out


def mutant_all_required(doc: dict) -> dict:
    out = deepcopy(doc)
    for row in out.get("obligation_table") or []:
        row["required_versus_proposed"] = "required-by-terms"
    return out


def mutant_strip_pins(doc: dict) -> dict:
    out = deepcopy(doc)
    for row in out.get("obligation_table") or []:
        row["document_version"] = ""
        row["commit_sha"] = None
        row["source_lineage"] = {
            "fetch_timestamp": None,
            "sha256": None,
            "version": None,
        }
    return out
