"""Shared verification for RES-0057 captures + research artifact."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from taxonomy import (
    CAPTURE_NEEDLES,
    ROWS,
    SENTINEL,
    gameable_rows,
    resistant_rows,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART_REL = "command-center/research/RES-0057.json"
CAPTURES = HERE / "captures"
LINEAGE_PATH = CAPTURES / "lineage.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
GAMEABLE_GRADES = {"GAMEABLE", "MIXED"}
RESISTANT_GRADES = {"RESISTANT", "MIXED"}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_lineage() -> list[dict]:
    rows = load_json(LINEAGE_PATH)
    if not isinstance(rows, list):
        raise ValueError("lineage.json is not a list")
    return [r for r in rows if isinstance(r, dict)]


def capture_blob() -> str:
    parts: list[str] = []
    for name in CAPTURE_NEEDLES:
        path = CAPTURES / name
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


def verify_captures() -> list[str]:
    failures: list[str] = []
    if not LINEAGE_PATH.is_file():
        return ["lineage.json missing"]
    by_name = {r["name"]: r for r in load_lineage()}
    for name, needles in CAPTURE_NEEDLES.items():
        rec = by_name.get(name)
        path = CAPTURES / name
        if rec is None:
            failures.append(f"lineage missing {name}")
            continue
        if rec.get("http_status") != 200:
            failures.append(f"{name} http_status={rec.get('http_status')}")
        if not path.is_file():
            failures.append(f"capture file missing {name}")
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != rec.get("sha256"):
            failures.append(f"{name} sha256 drift")
        if rec.get("bytes") != len(raw):
            failures.append(f"{name} byte-length drift")
        text = raw.decode("utf-8", errors="replace")
        for needle in needles:
            if needle not in text:
                failures.append(f"{name} missing needle {needle!r}")
    return failures


def api_differential() -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    path = CAPTURES / "scorecard-api-ossf.json"
    if not path.is_file():
        return {}, ["scorecard-api-ossf.json missing"]
    doc = load_json(path)
    checks = {c.get("name"): c for c in doc.get("checks") or [] if isinstance(c, dict)}
    lic = checks.get("License") or {}
    pol = checks.get("Security-Policy") or {}
    dep = checks.get("Dependency-Update-Tool") or {}
    vul = checks.get("Vulnerabilities") or {}

    def score_of(row: dict, default: int) -> int:
        val = row.get("score")
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    if score_of(lic, -1) < 8:
        failures.append(f"API License score not high: {lic.get('score')}")
    if score_of(pol, -1) < 8:
        failures.append(f"API Security-Policy score not high: {pol.get('score')}")
    if score_of(dep, -1) < 8:
        failures.append(f"API Dependency-Update-Tool score not high: {dep.get('score')}")
    if score_of(vul, 99) != 0:
        failures.append(f"API Vulnerabilities score expected 0, got {vul.get('score')}")
    details = " ".join(str(x) for x in (vul.get("details") or []))
    if "osv.dev" not in details:
        failures.append("API Vulnerabilities details lack osv.dev IDs")
    return {
        "license_score": lic.get("score"),
        "security_policy_score": pol.get("score"),
        "dependency_update_tool_score": dep.get("score"),
        "vulnerabilities_score": vul.get("score"),
        "vulnerabilities_n": details.count("osv.dev"),
        "repo": (doc.get("repo") or {}).get("name"),
    }, failures


def verify_taxonomy() -> list[str]:
    failures: list[str] = []
    blob = capture_blob()
    if not gameable_rows():
        failures.append("no gameable rows")
    if not any(r["check"] == "Vulnerabilities" and r["grade"] == "RESISTANT" for r in ROWS):
        failures.append("Vulnerabilities is not graded RESISTANT")
    if not resistant_rows():
        failures.append("no resistant rows")
    seen: set[str] = set()
    lineage_names = {r["name"] for r in load_lineage()}
    for row in ROWS:
        rid = row["id"]
        if rid in seen:
            failures.append(f"duplicate row {rid}")
        seen.add(rid)
        grade = row["grade"]
        recipe = row.get("cheap_satisfaction_recipe") or ""
        reason = row.get("resistant_reason") or ""
        if grade in GAMEABLE_GRADES and len(recipe) < 40:
            failures.append(f"{rid} gameable recipe too short")
        if grade in RESISTANT_GRADES and len(reason) < 40:
            failures.append(f"{rid} resistant reason too short")
        caps_text = ""
        for cap in (row.get("structured_captures") or []) + (row.get("prose_captures") or []):
            if cap not in lineage_names:
                failures.append(f"{rid} unknown capture {cap}")
            path = CAPTURES / cap
            if path.is_file():
                caps_text += path.read_text(encoding="utf-8", errors="replace")
        hay_recipe, hay_reason = recipe.lower(), reason.lower()
        hay_caps, hay_blob = caps_text.lower(), blob.lower()
        for tok in row.get("recipe_tokens") or []:
            needle = tok.lower()
            if grade == "GAMEABLE" and needle not in hay_recipe:
                failures.append(f"{rid} recipe missing token {tok!r}")
            if grade == "RESISTANT" and needle not in hay_reason:
                failures.append(f"{rid} reason missing token {tok!r}")
            if grade == "MIXED" and needle not in hay_recipe and needle not in hay_reason:
                failures.append(f"{rid} mixed row missing token {tok!r}")
            if needle not in hay_caps and needle not in hay_blob:
                failures.append(f"{rid} token {tok!r} absent from captures")
    return failures


def _rails_ok(rails: Any, label: str) -> list[str]:
    fails: list[str] = []
    if not isinstance(rails, list) or len(rails) < 2:
        return [f"{label} needs two rails"]
    kinds = " ".join(str(r.get("kind") or r.get("type") or "") for r in rails if isinstance(r, dict)).lower()
    if "struct" not in kinds and "api" not in kinds:
        fails.append(f"{label} missing structured rail")
    if "prose" not in kinds and "doc" not in kinds:
        fails.append(f"{label} missing prose rail")
    by_name = {r["name"]: r for r in load_lineage()}
    for rail in rails:
        if not isinstance(rail, dict):
            fails.append(f"{label} rail not object")
            continue
        for field in ("permalink", "fetch_timestamp", "http_status", "sha256"):
            if rail.get(field) in (None, ""):
                fails.append(f"{label} rail missing {field}")
        if int(rail.get("http_status") or 0) != 200:
            fails.append(f"{label} rail http_status {rail.get('http_status')}")
        cap = rail.get("capture") or rail.get("capture_name")
        if not cap:
            continue
        rec = by_name.get(str(cap))
        if rec and rec.get("sha256") != rail.get("sha256"):
            fails.append(f"{label} rail sha256 != lineage {cap}")
        path = CAPTURES / str(cap)
        if path.is_file():
            live = hashlib.sha256(path.read_bytes()).hexdigest()
            if live != rail.get("sha256"):
                fails.append(f"{label} rail sha256 != disk {cap}")
    return fails


def verify_artifact(doc: dict) -> list[str]:
    failures: list[str] = []
    if not isinstance(doc, dict):
        return ["artifact is not an object"]
    text = json.dumps(doc, ensure_ascii=False)
    if SENTINEL not in text:
        failures.append("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        failures.append(f"self-declared:{st}")
    if doc.get("unit_id") != "RES-0057":
        failures.append(f"unit_id {doc.get('unit_id')}")
    grades = doc.get("gameability_grades") or []
    if not isinstance(grades, list) or len(grades) < 10:
        failures.append(
            f"per-check grade table too small ({len(grades) if isinstance(grades, list) else 0})"
        )
        return failures
    by_id = {g.get("id"): g for g in grades if isinstance(g, dict)}
    gcount = rcount = 0
    for src in ROWS:
        got = by_id.get(src["id"])
        if not got:
            failures.append(f"artifact missing row {src['id']}")
            continue
        if got.get("grade") != src["grade"]:
            failures.append(f"{src['id']} grade {got.get('grade')} != taxonomy {src['grade']}")
        if src["grade"] in GAMEABLE_GRADES:
            gcount += 1
            rec = got.get("cheap_satisfaction_recipe") or ""
            if len(str(rec)) < 40:
                failures.append(f"{src['id']} artifact recipe missing")
        if src["grade"] in RESISTANT_GRADES:
            rcount += 1
            reason = got.get("resistant_reason") or ""
            if len(str(reason)) < 40:
                failures.append(f"{src['id']} artifact resistant reason missing")
        failures.extend(_rails_ok(got.get("rails"), src["id"]))
    if gcount < 1:
        failures.append("artifact has no gameable rows")
    if rcount < 1:
        failures.append("artifact has no resistant rows")
    vul = by_id.get("scorecard.Vulnerabilities") or {}
    if vul.get("grade") != "RESISTANT":
        failures.append("Vulnerabilities not RESISTANT in artifact")
    claims = doc.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 2:
        failures.append("claims < 2")
    else:
        for cl in claims:
            if not isinstance(cl, dict):
                failures.append("claim not object")
                continue
            if str(cl.get("evidence_grade") or "").upper() == "E3":
                failures.append(f"claim {cl.get('id')} is E3")
            failures.extend(_rails_ok(cl.get("rails"), f"claim:{cl.get('id')}"))
    rev = doc.get("reviewer") or {}
    if not rev.get("independent"):
        failures.append("reviewer.independent is not true")
    parts = rev.get("reviewers") or []
    if not isinstance(parts, list) or len(parts) < 2:
        failures.append("partitioned reviewers missing")
    else:
        vendors = {str(p.get("vendor_role") or p.get("id") or "") for p in parts if isinstance(p, dict)}
        if len(vendors) < 2:
            failures.append("reviewers not partitioned")
    marketplace = str(doc.get("marketplace_implication") or "")
    if "not" not in marketplace.lower() or "install" not in marketplace.lower():
        failures.append("marketplace implication missing")
    return failures


def mutant_strip_recipes(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    for row in mutant.get("gameability_grades") or []:
        if isinstance(row, dict) and row.get("grade") in GAMEABLE_GRADES:
            row["cheap_satisfaction_recipe"] = ""
    return mutant


def mutant_vuln_gameable(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    for row in mutant.get("gameability_grades") or []:
        if isinstance(row, dict) and row.get("id") == "scorecard.Vulnerabilities":
            row["grade"] = "GAMEABLE"
            row["resistant_reason"] = ""
            row["cheap_satisfaction_recipe"] = "add a file named VULNS.md"
    return mutant


def mutant_drop_resistant(doc: dict) -> dict:
    mutant = copy.deepcopy(doc)
    mutant["gameability_grades"] = [
        r
        for r in (mutant.get("gameability_grades") or [])
        if isinstance(r, dict) and r.get("grade") not in RESISTANT_GRADES
    ]
    return mutant


def evaluate_all(doc: dict | None = None) -> dict:
    failures: list[str] = []
    failures.extend(verify_captures())
    failures.extend(verify_taxonomy())
    diff, diff_fail = api_differential()
    failures.extend(diff_fail)
    if doc is not None:
        failures.extend(verify_artifact(doc))
        if not verify_artifact(mutant_strip_recipes(doc)):
            failures.append("mutant-strip-recipes did not go red")
        if not verify_artifact(mutant_vuln_gameable(doc)):
            failures.append("mutant-vuln-gameable did not go red")
        if not verify_artifact(mutant_drop_resistant(doc)):
            failures.append("mutant-drop-resistant did not go red")
    return {
        "ok": not failures,
        "failures": failures[:40],
        "failure_n": len(failures),
        "api_differential": diff,
        "gameable_n": len(gameable_rows()),
        "resistant_n": len(resistant_rows()),
        "row_n": len(ROWS),
        "sentinel": SENTINEL,
    }
