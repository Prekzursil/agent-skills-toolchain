#!/usr/bin/env python3
"""Reconstructed PRE-FIX claim_gate (the measured hole).

Authentic live `.agents/skills/claim-verify-gate/scripts/claim_gate.py` was
ABSENT on this worktree. This fixture reconstructs the catalog-described hole
so BEFORE can be re-run:

  * `_validate` requires id/text/verdict only (catalog ~:132-156).
  * `normalize` (~:173-185) fills missing source_probe / verifier_probe with
    empty tool/engine/shell/field strings.
  * same-probe-rerun therefore cannot fire on an absent source: empty strings
    trivially differ from any nonempty verifier.

Expected on a CONFIRMED claim with no source_probe and a valid verifier:
violations [], ok true, exit 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

EMPTY_PROBE = {"tool": "", "engine": "", "shell": "", "field": ""}


def normalize(claim: dict[str, Any]) -> dict[str, Any]:
    out = dict(claim)
    sp = out.get("source_probe")
    if not isinstance(sp, dict):
        out["source_probe"] = dict(EMPTY_PROBE)
    else:
        merged = dict(EMPTY_PROBE)
        merged.update(sp)
        for key in EMPTY_PROBE:
            if not isinstance(merged.get(key), str):
                merged[key] = ""
        out["source_probe"] = merged
    vp = out.get("verifier_probe", out.get("verify_probe"))
    if not isinstance(vp, dict):
        out["verifier_probe"] = dict(EMPTY_PROBE)
    else:
        merged = dict(EMPTY_PROBE)
        merged.update(vp)
        for key in EMPTY_PROBE:
            if not isinstance(merged.get(key), str):
                merged[key] = ""
        out["verifier_probe"] = merged
    return out


def _fp(probe: dict[str, Any]) -> str:
    return json.dumps(probe, sort_keys=True, separators=(",", ":"))


def _validate(claim: dict[str, Any]) -> list[dict[str, str]]:
    """PRE-FIX: id/text/verdict only. No source_probe requirement."""
    violations: list[dict[str, str]] = []
    for field in ("id", "text", "verdict"):
        val = claim.get(field)
        if not isinstance(val, str) or not val.strip():
            violations.append({"rule": f"no-{field}", "detail": f"missing {field}"})
    norm = normalize(claim)
    src = norm["source_probe"]
    ver = norm["verifier_probe"]
    if _fp(src) == _fp(ver):
        violations.append(
            {
                "rule": "same-probe-rerun",
                "detail": "source_probe fingerprint equals verifier_probe",
            }
        )
    return violations


def gate_report(payload: Any, *, subject: str = "") -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("claims"), list):
        claims = payload["claims"]
        subj = subject or str(payload.get("subject") or "claims")
    elif isinstance(payload, dict):
        claims = [payload]
        subj = subject or str(payload.get("id") or "claim")
    else:
        return {"subject": subject or "invalid", "claims": [], "ok": False, "violation_count": 1}

    out = []
    total = 0
    for raw in claims:
        if not isinstance(raw, dict):
            row_v = [{"rule": "claim-not-object", "detail": type(raw).__name__}]
        else:
            row_v = _validate(raw)
        total += len(row_v)
        out.append(
            {
                "id": raw.get("id", "") if isinstance(raw, dict) else "",
                "text": raw.get("text", "") if isinstance(raw, dict) else "",
                "verdict": raw.get("verdict", "") if isinstance(raw, dict) else "",
                "violations": row_v,
                "residual": False,
            }
        )
    return {
        "subject": subj,
        "claims": out,
        "violation_count": total,
        "residual_count": 0,
        "ok": total == 0,
        "rules": ["no-id", "no-text", "no-verdict", "same-probe-rerun"],
        "pre_fix": True,
        "note": "reconstructed hole: no no-source-probe rule; normalize fills empty strings",
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("FAILED:pre-fix-claim_gate usage: <payload.json>", file=sys.stderr)
        return 2
    path = Path(args[0])
    payload = json.loads(path.read_text(encoding="utf-8"))
    report = gate_report(payload, subject=path.name)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
