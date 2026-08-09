"""Independently verify the checkable benchmark / spec claims in my 32, instead
of copying the prior doc's prose.

C1  memory-bench "13/16 = 81.25%"  -> recount from results.json in the tree.
C2  agentspec "closed 28-id violation set" -> count the violation ids in validate.py.
C3  fanout-schema "22.7% (849/3735)" -> recompute the arithmetic from the README's
    own numerator/denominator (arithmetic check only; the 10.65 GB re-mine is
    OUT OF SCOPE for this unit and is reported as such).
C4  ese-gate: does it really emit a deterministic escalate decision? -> find the
    decision function + any threshold constant.
C5  triage-router / rtv-pdr / memory-bench arXiv ids -> record them verbatim,
    flagged NOT-RESOLVED (no network probe run by this unit).
"""

import json
import re
import subprocess

MIRROR = r"C:\Users\Prekzursil\.claude\harness-restore-20260806\main-mirror.git"
REF = "07f465f37d49710f7060dcc7b567d6c58213177b"
out = {}


def blob(path):
    r = subprocess.run(
        ["git", "--git-dir", MIRROR, "cat-file", "-p", f"{REF}:{path}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (r.stdout or "") if r.returncode == 0 else None


# ---- C1 memory-bench ----------------------------------------------------
print("=== C1  memory-bench pass-rate recount ===")
rj = blob("tools/memory-bench/results.json")
if rj:
    try:
        data = json.loads(rj)
        print(
            "  results.json top-level keys:",
            list(data)[:12] if isinstance(data, dict) else type(data),
        )
        txt = json.dumps(data)
        # try to find explicit pass/total
        for k in ("overall", "summary", "score", "passed", "total", "results"):
            if isinstance(data, dict) and k in data:
                print(f"  {k}: {json.dumps(data[k])[:300]}")
        # count boolean pass fields if a probe list exists
        rows = data.get("results") if isinstance(data, dict) else None
        if isinstance(rows, list):
            passes = sum(
                1 for r in rows if r.get("pass") is True or r.get("passed") is True
            )
            print(
                f"  RECOUNT from rows: {passes}/{len(rows)} = {passes / len(rows) * 100:.2f}%"
            )
            out["C1"] = {
                "passes": passes,
                "total": len(rows),
                "pct": round(passes / len(rows) * 100, 2),
            }
        else:
            print("  no 'results' row list; raw head:", txt[:400])
    except Exception as e:
        print("  parse error:", e)
else:
    print("  results.json NOT PRESENT -> claim unverifiable from the tree")

pj = blob("tools/memory-bench/probes.jsonl")
if pj:
    n = sum(1 for ln in pj.splitlines() if ln.strip())
    print(f"  probes.jsonl rows = {n}  (README claims 16 probes)")
    out["C1_probes"] = n

# ---- C2 agentspec 28-id violation set -----------------------------------
print("\n=== C2  agentspec closed violation-id set ===")
v = blob("tools/agentspec/agentspec/validate.py")
if v:
    ids = sorted(set(re.findall(r"['\"]([A-Z]{2,10}-\d{2,3})['\"]", v)))
    print(f"  distinct violation ids found in validate.py: {len(ids)}")
    print(f"  ids: {ids}")
    out["C2"] = {"count": len(ids), "ids": ids}
    rd = blob("tools/agentspec/README.md") or ""
    m = re.search(r"closed\s+(\d+)-id\s+violation\s+set", rd)
    print(f"  README claim: {m.group(1) if m else 'not found'}")
    out["C2_claim"] = m.group(1) if m else None
else:
    print("  validate.py absent")

# ---- C3 fanout-schema arithmetic ---------------------------------------
print("\n=== C3  fanout-schema 22.7% arithmetic ===")
rd = blob("tools/fanout-schema/README.md") or ""
m = re.search(
    r"\|\s*StructuredOutput,\s*all\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*\*\*([\d.]+)%",
    rd,
)
if m:
    calls = int(m.group(1).replace(",", ""))
    errs = int(m.group(2).replace(",", ""))
    claimed = float(m.group(3))
    computed = errs / calls * 100
    print(f"  calls={calls} errors={errs} claimed={claimed}% computed={computed:.2f}%")
    print(
        f"  arithmetic {'CONSISTENT' if abs(computed - claimed) < 0.1 else 'INCONSISTENT'}"
    )
    out["C3"] = {
        "calls": calls,
        "errors": errs,
        "claimed_pct": claimed,
        "computed_pct": round(computed, 2),
    }
else:
    print("  table row not matched")
m2 = re.search(
    r"(\d[\d,]*)\s*/\s*(\d[\d,]*)\s*/\s*([\d.]+)%\s*from an independent implementation",
    rd,
)
if m2:
    print(f"  second implementation: {m2.group(1)} / {m2.group(2)} / {m2.group(3)}%")
    out["C3_second"] = m2.groups()

# ---- C4 ese-gate determinism -------------------------------------------
print("\n=== C4  ese-gate deterministic escalation ===")
eg = blob("tools/ese-gate/ese_gate.py") or ""
thr = re.findall(r"^([A-Z_]{3,40})\s*=\s*([0-9.]+)", eg, re.M)
print(f"  module-level numeric constants: {thr[:12]}")
funcs = re.findall(r"^def\s+(\w+)", eg, re.M)
print(f"  functions: {funcs[:20]}")
print(
    f"  mentions 'escalate': {len(re.findall('escalate', eg))}  'entropy': {len(re.findall('entropy', eg, re.I))}"
)
print(
    f"  uses random/time on the decision path: random={'random' in eg} time.time={'time.time' in eg}"
)
out["C4"] = {"constants": thr[:12], "functions": funcs[:20]}

# ---- C5 arXiv ids verbatim ---------------------------------------------
print("\n=== C5  arXiv ids cited by my 32 (NOT resolved -- no network probe) ===")
for p in (
    "tools/triage-router/README.md",
    "tools/memory-bench/README.md",
    "workflows/rtv-pdr.js",
    "tools/repomap/README.md",
    "tools/ese-gate/README.md",
):
    t = blob(p) or ""
    ids = sorted(set(re.findall(r"arXiv[:\s]*([0-9]{4}\.[0-9]{4,5})", t, re.I)))
    print(f"  {p:<42} {ids}")
    out.setdefault("C5", {})[p] = ids

with open("command-center/_wfa1_verify_claims.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=2)
print("\nwrote command-center/_wfa1_verify_claims.json")
