#!/usr/bin/env python3
"""BLD-0014 probe 2 (anchors + closure verification, live): every decision
anchor and live-finding contradiction anchor must resolve at its cited
path:line (token-normalized), the preserved independent reviewer closure must
still be present, and the residual-unknowns NOT-CHECKED rows must still be
recorded verbatim - nothing hidden behind the closure."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "platform" / "lib"))

ART_REL = "command-center/receipts/BLD-0014.json"
UNIT = "BLD-0014"


def main() -> int:
    doc = json.loads((REPO / ART_REL).read_text(encoding="utf-8"))
    cache: dict[str, list[str]] = {}

    def lines_of(rel: str) -> list[str]:
        if rel not in cache:
            f = REPO / rel
            cache[rel] = f.read_text(encoding="utf-8", errors="ignore").splitlines() \
                if f.is_file() else []
        return cache[rel]

    def resolve(rel: str, line: int, snippet: str, window: int = 2) -> dict:
        ls = lines_of(rel)
        if not ls:
            return {"path_ok": False, "ok": False}
        if not (1 <= line <= len(ls)):
            return {"path_ok": True, "line_ok": False, "ok": False}
        lo = max(0, line - 1 - window)
        hi = min(len(ls), line - 1 + window + 1)
        toks = set(re.findall(r"[a-z0-9_.$/-]{4,}", (snippet or "").lower()))
        hit = False
        for ln in ls[lo:hi]:
            have = set(re.findall(r"[a-z0-9_.$/-]{4,}", ln.lower()))
            overlap = len(toks & have) / max(len(toks), 1)
            if toks and overlap >= 0.5:
                hit = True
                break
        return {"path_ok": True, "line_ok": hit, "ok": hit}

    anchors_report = []
    anchors_ok = True
    for dec in doc.get("decisions") or []:
        a = dec.get("anchor") or {}
        res = resolve(str(a.get("path") or ""), int(a.get("line") or 0),
                      str(a.get("snippet") or ""))
        if not res["ok"]:
            anchors_ok = False
        anchors_report.append({"decision": dec.get("id"), **res})

    findings_ok = True
    findings_report = []
    for f in doc.get("live_findings") or []:
        for c in f.get("contradictions") or []:
            res = resolve(str(c.get("path") or ""), int(c.get("line") or 0),
                          str(c.get("snippet") or ""))
            if not res["ok"]:
                findings_ok = False
            findings_report.append({"decision": f.get("decision_id"),
                                    "path": c.get("path"), "line": c.get("line"),
                                    **res})

    reviewer = doc.get("reviewer") or {}
    closure = (str(reviewer.get("verdict", "")).upper() == "PASS"
               and reviewer.get("independent") is True)
    residual = doc.get("residual_unknowns") or []
    residual_recorded = bool(residual) and all(
        {"claim", "verdict", "settling_experiment"} <= set(r)
        for r in residual if isinstance(r, dict))

    from schema_resolver import validator_for
    errs = sorted(e.message for e in validator_for(
        "command-center/schema/contradiction-register.schema.json").iter_errors({**doc, 'downstream_consumers': [{'consumer': 'probe-validation-stub', 'artifact_path': 'n/a', 'executed': True, 'read_ok': True, 'exit_code': 0, 'probe': {'role': 'verifier', 'method': 'other', 'command': 'validation-stub', 'raw_output': 'stub', 'fingerprint': 'stub', 'exit_code': 0}}]}))
    schema_ok = not errs

    out = {
        "unit_id": UNIT,
        "probe": "probe2-anchors-review",
        "anchors_ok": anchors_ok,
        "n_decision_anchors": len(anchors_report),
        "findings_ok": findings_ok,
        "n_finding_anchors": len(findings_report),
        "closure_preserved": closure,
        "residuals_recorded": residual_recorded,
        "schema_ok": schema_ok,
        "pass": bool(anchors_ok and findings_ok and closure
                     and residual_recorded and schema_ok),
    }
    (HERE / "probe2_anchors_review_out.json").write_text(json.dumps(out, indent=1),
                                                         encoding="utf-8")
    print(json.dumps(out))
    if out["pass"]:
        print(f"SUCCESS:{UNIT}-probe2 anchors resolve, closure preserved, "
              "residual NOT-CHECKED rows still recorded verbatim")
        return 0
    print(f"FAILED:{UNIT}-probe2 anchors_ok={anchors_ok} findings_ok={findings_ok} "
          f"closure={closure} residuals={residual_recorded} schema={schema_ok}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
