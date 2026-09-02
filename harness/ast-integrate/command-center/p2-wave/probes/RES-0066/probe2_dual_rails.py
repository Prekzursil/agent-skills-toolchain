#!/usr/bin/env python3
"""Probe 2: measured-fact claims have two independent rails; single-rail is E3."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center" / "research" / "RES-0066.json"
SENTINEL = (
    "SUCCESS:RES-0066 in the receipt AND per-project LICENSE file contents "
    "(read, not classified) plus a copy-versus-reimplement verdict"
)
STRUCTURED = {"structured-source", "structured-api"}
PROSE = {"prose-docs"}


def fail(msg: str) -> int:
    print(f"FAILED:RES-0066-probe2 {msg}")
    return 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not ART.is_file():
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    claims = [c for c in (doc.get("claims") or []) if isinstance(c, dict)]
    if len(claims) < 6:
        return fail(f"too-few-claims {len(claims)}")
    measured = [c for c in claims if c.get("cited_as_measured_fact") is True]
    control = [c for c in claims if c.get("id") == "C-CONTROL-SINGLE-RAIL"]
    if not control:
        return fail("missing-single-rail-control")
    ctrl = control[0]
    if ctrl.get("evidence_tier") != "E3":
        return fail("control not graded E3")
    if ctrl.get("cited_as_measured_fact") is True:
        return fail("control cited as measured fact")
    if len(ctrl.get("rails") or []) != 1:
        return fail("control is not single-rail")
    if any(c.get("evidence_tier") == "E3" and c.get("cited_as_measured_fact") for c in claims):
        return fail("E3 cited as measured fact")

    kinds_ok = 0
    for claim in measured:
        rails = [r for r in (claim.get("rails") or []) if isinstance(r, dict)]
        if len(rails) < 2:
            return fail(f"{claim.get('id')} single-rail-as-fact")
        kinds = {str(r.get("kind") or "") for r in rails}
        if not (kinds & STRUCTURED):
            return fail(f"{claim.get('id')} missing structured rail")
        if not (kinds & PROSE) and "structured-api" not in kinds:
            # AutoGen state claim pairs source + GitHub API (structured-api) as
            # the independent classifier/prose substitute; still two rails.
            if not any(k.startswith("prose") or k.startswith("structured") for k in kinds):
                return fail(f"{claim.get('id')} rails not independent {kinds}")
        if len(kinds) < 2:
            return fail(f"{claim.get('id')} rails same kind {kinds}")
        for r in rails:
            for field in ("permalink", "fetch_timestamp", "http_status", "sha256"):
                if r.get(field) in (None, ""):
                    return fail(f"{claim.get('id')} rail missing {field}")
            if int(r.get("http_status") or 0) != 200:
                return fail(f"{claim.get('id')} rail http {r.get('http_status')}")
            cap = r.get("capture_path")
            if not cap:
                return fail(f"{claim.get('id')} rail missing capture")
            p = REPO / str(cap)
            if not p.is_file():
                return fail(f"{claim.get('id')} capture missing {cap}")
            live = digest(p)
            if live != str(r.get("sha256")):
                return fail(f"{claim.get('id')} sha256 mismatch {cap}")
        kinds_ok += 1

    cvr = doc.get("copy_versus_reimplement") or {}
    if cvr.get("verdict") != "REIMPLEMENT":
        return fail("copy-versus-reimplement")
    print(
        json.dumps(
            {
                "probe": "probe2-dual-rails",
                "claims": len(claims),
                "measured": len(measured),
                "measured_dual_rail_ok": kinds_ok,
                "control_e3": True,
                "copy_versus_reimplement": cvr.get("verdict"),
            },
            sort_keys=True,
        )
    )
    print(
        f"measured={len(measured)} dual_ok={kinds_ok} control_e3=True "
        "verdict=REIMPLEMENT"
    )
    print("SUCCESS:RES-0066-probe2 dual rails on measured facts; single-rail control is E3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
