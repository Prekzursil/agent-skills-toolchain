"""Contract checks for RES-0071 (no network)."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
UNIT = "RES-0071"
OUT_REL = "command-center/research/RES-0071.json"
SENTINEL = (
    "SUCCESS:RES-0071 in the receipt AND a per-system accuracy column "
    "where unpublished figures are explicitly marked NOT-PUBLISHED"
)
UNPUB = "NOT-PUBLISHED"
RAIL_KINDS = {"structured-api", "prose-source"}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _rail_errors(rail: Any, prefix: str) -> list[str]:
    errs: list[str] = []
    if not isinstance(rail, dict):
        return [f"{prefix}: rail is not an object"]
    for key in ("rail_id", "kind", "permalink", "fetched_at", "http_status", "sha256"):
        if key not in rail:
            errs.append(f"{prefix}: missing {key}")
    kind = rail.get("kind")
    if kind not in RAIL_KINDS:
        errs.append(f"{prefix}: kind {kind!r} not in {sorted(RAIL_KINDS)}")
    status = rail.get("http_status")
    if status != 200:
        errs.append(f"{prefix}: http_status={status} (need 200)")
    snap = rail.get("snapshot")
    sha = rail.get("sha256")
    if not isinstance(snap, str) or not snap:
        errs.append(f"{prefix}: snapshot path missing")
        return errs
    path = REPO / snap
    if not path.is_file():
        errs.append(f"{prefix}: snapshot absent {snap}")
        return errs
    live = sha256_bytes(path.read_bytes())
    if not isinstance(sha, str) or live != sha:
        errs.append(f"{prefix}: sha256 mismatch live={live} recorded={sha}")
    return errs


def _two_rail_errors(rails: Any, prefix: str) -> list[str]:
    errs: list[str] = []
    if not isinstance(rails, list) or len(rails) < 2:
        return [f"{prefix}: need >=2 rails"]
    kinds = set()
    for i, rail in enumerate(rails):
        errs.extend(_rail_errors(rail, f"{prefix}.rails[{i}]"))
        if isinstance(rail, dict):
            kinds.add(rail.get("kind"))
    if "structured-api" not in kinds or "prose-source" not in kinds:
        errs.append(f"{prefix}: need both structured-api and prose-source rails")
    return errs


def check_doc(doc: Any) -> list[str]:
    errs: list[str] = []
    if not isinstance(doc, dict):
        return ["document is not an object"]
    blob = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in blob:
        errs.append("sentinel string absent from artifact")
    if str(doc.get("unit_id") or doc.get("id")) != UNIT:
        errs.append(f"unit_id mismatch {doc.get('unit_id')!r}")
    state = str(doc.get("state") or "").upper()
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errs.append(f"self-declared {state}")
    if state != "SUCCESS":
        errs.append(f"state {state!r} is not SUCCESS")
    systems = doc.get("systems")
    if not isinstance(systems, list) or len(systems) < 4:
        errs.append("systems[] must list >=4 surveyed systems")
        return errs
    unpublished = 0
    numeric_without_pub = 0
    for i, sys in enumerate(systems):
        pfx = f"systems[{i}]"
        if not isinstance(sys, dict):
            errs.append(f"{pfx}: not an object")
            continue
        sid = sys.get("id")
        col = sys.get("accuracy_column")
        if not isinstance(sid, str) or not sid:
            errs.append(f"{pfx}: missing id")
        if col == UNPUB:
            unpublished += 1
            pub = sys.get("published_estimate_versus_actual")
            if pub not in (None, {}, []):
                errs.append(f"{pfx}: NOT-PUBLISHED but published_estimate_versus_actual is set")
        elif isinstance(col, str) and col.strip():
            pub = sys.get("published_estimate_versus_actual")
            if not isinstance(pub, dict) or not pub.get("citation"):
                numeric_without_pub += 1
                errs.append(
                    f"{pfx}: accuracy_column={col!r} has no published estimate-versus-actual citation"
                )
            errs.extend(_two_rail_errors(sys.get("rails"), pfx))
        else:
            errs.append(f"{pfx}: accuracy_column missing")
        errs.extend(_two_rail_errors(sys.get("rails"), pfx))
        for flag in ("previews_cost_before_run", "previews_touch_before_run"):
            if not isinstance(sys.get(flag), bool):
                errs.append(f"{pfx}: {flag} must be boolean")
        caveat = sys.get("strongest_caveat")
        if not isinstance(caveat, str) or len(caveat) < 24:
            errs.append(f"{pfx}: strongest_caveat too short")
    if unpublished < 1:
        errs.append("control failed: zero systems marked NOT-PUBLISHED")
    if numeric_without_pub:
        errs.append("numeric accuracy without published comparison")
    claims = doc.get("claims")
    if not isinstance(claims, list) or len(claims) < 2:
        errs.append("claims[] missing")
    else:
        for i, claim in enumerate(claims):
            pfx = f"claims[{i}]"
            if not isinstance(claim, dict):
                errs.append(f"{pfx}: not an object")
                continue
            tier = str(claim.get("evidence_tier") or "")
            rails = claim.get("rails")
            n_rails = len(rails) if isinstance(rails, list) else 0
            if n_rails < 2 and tier in {"E1", "E2"}:
                errs.append(f"{pfx}: E1/E2 claim with {n_rails} rails")
            if n_rails >= 2:
                errs.extend(_two_rail_errors(rails, pfx))
            if not claim.get("strongest_caveat"):
                errs.append(f"{pfx}: missing strongest_caveat")
    mvd = doc.get("minimum_viable_dry_run")
    if not isinstance(mvd, dict):
        errs.append("minimum_viable_dry_run missing")
    else:
        for key in ("steps", "non_goals", "cost_bound_kind"):
            if key not in mvd:
                errs.append(f"minimum_viable_dry_run missing {key}")
        if mvd.get("cost_bound_kind") not in {"CEILING", "POINT-ESTIMATE-NOT-CLAIMED"}:
            errs.append("minimum_viable_dry_run.cost_bound_kind must be CEILING")
        if mvd.get("spawns_model") is not False:
            errs.append("minimum_viable_dry_run must set spawns_model=false")
    tests = doc.get("tests")
    if not isinstance(tests, list) or len(tests) < 2:
        errs.append("tests[] missing")
    return errs


def check_path(path: Path) -> list[str]:
    try:
        doc = load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"unparseable: {exc}"]
    return check_doc(doc)


def plant_numeric_without_citation(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    systems = mutant.get("systems") or []
    if not systems:
        return mutant
    systems[0]["accuracy_column"] = "99.2%"
    systems[0]["published_estimate_versus_actual"] = None
    return mutant


def plant_strip_unpublished(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    for sys in mutant.get("systems") or []:
        if sys.get("accuracy_column") == UNPUB:
            sys["accuracy_column"] = "0% MAPE"
            sys["published_estimate_versus_actual"] = None
    return mutant
