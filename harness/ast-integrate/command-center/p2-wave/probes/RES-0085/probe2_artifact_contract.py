#!/usr/bin/env python3
"""Probe 2: independent artifact contract (not a re-run of probe 1).

Checks the research record, not the fixture engine path:
  - catalog sentinel present
  - format comparison with a written unanswered-rebuttal check per checkable format
  - control: at least one format uncheckable or too costly
  - every surviving claim has two independent rails whose sha256 matches captured bytes
  - dropping the IBIS unanswered-rebuttal check from a copy of the artifact fails
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0085.json"
CAP = HERE / "fixtures" / "captures"
SENTINEL = (
    "SUCCESS:RES-0085 in the receipt AND a format comparison with a written "
    "unanswered-rebuttal check per checkable format"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0085-probe2 {msg}")
    return 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def has_written_check(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 40:
        return False
    if t.upper().startswith("UNCHECKABLE") or t.upper().startswith("TOO COSTLY"):
        return True
    return "def " in t and "return" in t


def rails_ok(claim: dict) -> tuple[bool, str]:
    rails = claim.get("rails") or []
    if len(rails) < 2:
        return False, "fewer than two rails"
    classes = {str(r.get("rail_class") or "") for r in rails}
    if "structured-api" not in classes:
        return False, f"no structured-api rail {classes}"
    if "prose" not in classes:
        return False, f"no prose rail {classes}"
    for r in rails:
        for k in ("permalink", "fetched_at", "http_status", "sha256"):
            if r.get(k) in (None, "", []):
                return False, f"rail missing {k}"
        if int(r.get("http_status") or 0) != 200:
            return False, f"http_status {r.get('http_status')}"
        cid = r.get("capture_id")
        if not cid:
            return False, "rail missing capture_id"
        body = CAP / f"{cid}.body"
        if not body.is_file():
            return False, f"capture body missing {cid}"
        live = digest(body)
        if live != str(r.get("sha256") or ""):
            return False, f"sha256 mismatch {cid}"
    return True, "ok"


def comparison_contract(doc: dict) -> tuple[bool, str]:
    rows = doc.get("format_comparison") or []
    if len(rows) < 3:
        return False, f"format_comparison rows={len(rows)}"
    ids = {str(r.get("id") or "") for r in rows if isinstance(r, dict)}
    if not {"ibis", "toulmin", "dung_af"} <= ids:
        return False, f"missing format ids {ids}"
    checkable = []
    control = []
    for r in rows:
        ur = str(r.get("checkability_unanswered_rebuttal") or "")
        cost = str(r.get("emit_cost") or "")
        check_text = str(r.get("unanswered_rebuttal_check") or "")
        if not has_written_check(check_text):
            return False, f"{r.get('id')} unanswered-rebuttal check missing"
        if ur == "checkable":
            checkable.append(r)
            if "def " not in check_text:
                return False, f"{r.get('id')} checkable but no pseudocode"
        if ur == "uncheckable" or cost == "too_costly_to_emit":
            control.append(r)
    if not checkable:
        return False, "no checkable unanswered-rebuttal format"
    if not control:
        return False, "control: no uncheckable/too-costly format"
    rec = [r.get("id") for r in rows if r.get("recommended_for_council")]
    if rec != ["ibis"]:
        return False, f"recommendation {rec}"
    return True, "ok"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    raw = ART.read_text(encoding="utf-8")
    doc = json.loads(raw)
    if SENTINEL not in raw:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")
    if str(doc.get("unit_id") or "") != "RES-0085":
        return fail("unit_id")
    ok, why = comparison_contract(doc)
    print(f"format_comparison {ok} {why}")
    if not ok:
        return fail(why)

    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 3:
        return fail(f"claims={len(claims)}")
    cited = 0
    for c in claims:
        verdict = str(c.get("verdict") or c.get("status") or "").upper()
        if verdict in {"REFUTED", "E3", "DROPPED"}:
            continue
        rok, rwhy = rails_ok(c)
        print(f"claim {c.get('id')} rails {rok} {rwhy}")
        if not rok:
            return fail(f"claim {c.get('id')} {rwhy}")
        cited += 1
    if cited < 3:
        return fail("fewer than 3 two-rail claims")

    mutant = copy.deepcopy(doc)
    stripped = False
    for r in mutant.get("format_comparison") or []:
        if r.get("id") == "ibis" and r.get("unanswered_rebuttal_check"):
            r["unanswered_rebuttal_check"] = ""
            stripped = True
            break
    if not stripped:
        return fail("could not strip IBIS check for mutant")
    mok, mwhy = comparison_contract(mutant)
    print(f"mutant_without_ibis_check ok={mok} {mwhy}")
    if mok:
        return fail("mutant missing IBIS unanswered-rebuttal check was accepted")

    rec = str(doc.get("recommendation") or doc.get("answer") or "")
    if "IBIS" not in rec.upper():
        return fail("recommendation does not name IBIS")

    print("SUCCESS:RES-0085-probe2 artifact contract two-rail format-comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
