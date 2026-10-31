#!/usr/bin/env python3
"""Patch 8: idempotent re-run - a unit already closed by THIS reviewer (state=SUCCESS,
reviewer_id match) is re-verified (admission + gate + manifest + live probes) and
recorded as stays-SUCCESS instead of being rebuilt."""
from pathlib import Path

p = Path(__file__).resolve().parent / "close_shard22.py"
t = p.read_text(encoding="utf-8")

anchor = '''    fails, ctx = preflight(uid)
    CUR_CTX = ctx
    if not fails:'''
if anchor not in t:
    raise SystemExit("anchor not found")
new = '''    # idempotent re-run: a unit THIS reviewer already closed is re-verified, not rebuilt
    rp0 = REPO / f"command-center/receipts/{uid}.json"
    if rp0.is_file():
        try:
            prev = json.loads(rp0.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        if (prev.get("state") == "SUCCESS"
                and isinstance(prev.get("reviewer"), dict)
                and prev["reviewer"].get("reviewer_id") == REVIEWER_ID
                and prev["reviewer"].get("verdict") == "PASS"
                and prev["reviewer"].get("independent") is True):
            problems0: list[str] = []
            vrc0, vout0 = validator_rc(uid)
            if vrc0 != 0:
                problems0.append("re-admission-REJECT:" + vout0[:180])
            g0 = RSG.evaluate_gate_a(prev, repo_root=str(REPO), verify_filesystem=True)
            if not g0.complete:
                problems0.append("re-gate-incomplete:" + g0.marker()[:140])
            d0, _ = digest_lf(rp0)
            man0 = json.loads((PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
            pr0 = [a for a in man0.get("artifacts", [])
                   if a.get("path") == f"command-center/receipts/{uid}.json"]
            if not pr0 or pr0[0].get("sha256") != d0:
                problems0.append("re-manifest-mismatch")
            ret0 = json.loads((PROBES / uid / "SUBAGENT-RETURN.json").read_text(encoding="utf-8"))
            for np0 in ret0.get("named_probes", []):
                s0 = [x for x in str(np0.get("command", "")).split() if x.endswith(".py")]
                if s0:
                    rc0p, o0 = run_probe(s0[-1])
                    if rc0p != 0 or f"SUCCESS:{uid}-" not in o0:
                        problems0.append("re-probe-fail:" + Path(s0[-1]).name + f":rc={rc0p}")
            if problems0:
                row["verdict"] = "FAIL"
                row["reasons"] = problems0[:8]
                results[uid] = row
                print("FAILED:" + uid + "-reverify " + "; ".join(pp[:90] for pp in problems0[:3]))
            else:
                row["verdict"] = "PASS"
                row["note"] = "already closed by this reviewer; re-verified live, stays SUCCESS"
                results[uid] = row
                print("SUCCESS:" + uid + " re-verified live (stays SUCCESS, gate COMPLETE)")
            continue

    fails, ctx = preflight(uid)
    CUR_CTX = ctx
    if not fails:'''
t = t.replace(anchor, new)
p.write_bytes(t.encode("utf-8"))
import ast
ast.parse(t)
print("patched + syntax OK")
