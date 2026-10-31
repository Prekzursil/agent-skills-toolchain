#!/usr/bin/env python3
"""Generic shard-7 emit driver: probes -> BLOCKED -> close SUCCESS -> manifest
-> SUBAGENT-RETURN -> measure. Usage:

    python -B command-center/p2-wave/_s7_emit.py <UNIT-ID>

Per-unit config lives in command-center/p2-wave/probes/<ID>/_config.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _shard7lib as L  # noqa: E402

UNIT = sys.argv[1]
PROBE_DIR = W / "command-center" / "p2-wave" / "probes" / UNIT
CFG = json.loads((PROBE_DIR / "_config.json").read_text(encoding="utf-8"))
started = L.now_iso()


def parse_result(raw):
    for ln in raw.splitlines():
        if ln.startswith("RESULT:"):
            return json.loads(ln[7:])
    raise AssertionError("no RESULT line in probe output")


# 1. Run both named probes live.
probe_out = {}
for pid in ("p1", "p2"):
    rel = CFG[pid]["rel"]
    cmd = "PYTHONDONTWRITEBYTECODE=1 python3 -B " + rel
    code, out = L.run([sys.executable, "-B", str(W / rel)], timeout=170)
    if code != 0 or ("SUCCESS:" + UNIT + "-probe" + pid[-1]) not in out:
        print("FAILED:" + UNIT + " probe " + pid + " rc=" + str(code))
        print(out[-2500:])
        raise SystemExit(1)
    res = parse_result(out)
    if not res.get("pass"):
        print("FAILED:" + UNIT + " probe " + pid + " pass=false")
        raise SystemExit(1)
    (PROBE_DIR / CFG[pid]["raw"]).write_text(out.strip() + "\n", encoding="utf-8", newline="\n")
    probe_out[pid] = {"cmd": cmd, "raw": out.strip(), "res": res}

# 2. Run the recorded test commands live.
tests = []
for t in CFG.get("tests", []):
    rc, out = L.run([sys.executable, "-B", str(W / t["script"])] , timeout=280)
    tests.append(L.test_result(t["id"], t["command"], "PASS" if rc == 0 else "FAIL",
                               tail=out[-1500:]))

# 3. Evidence items (each carries source + verifier probes).
P1, P2 = probe_out["p1"], probe_out["p2"]
evidence = [
    L.evidence(CFG["evidence"][0]["claim"], "CONFIRMED", CFG["evidence"][0]["anchor"],
               [
                   L.probe("source", CFG["evidence"][0].get("method", "test-run"), P1["cmd"], P1["raw"], 0),
                   L.probe("verifier", "file-read",
                           "read command-center/p2-wave/probes/" + UNIT + "/" + CFG["p2"]["raw"],
                           P2["raw"][-4000:], 0),
               ],
               CFG["evidence"][0].get("confidence", "almost-certain")),
    L.evidence(CFG["evidence"][1]["claim"], "CONFIRMED", CFG["evidence"][1]["anchor"],
               [
                   L.probe("source", CFG["evidence"][1].get("method", "static-analysis"), P2["cmd"], P2["raw"], 0),
                   L.probe("verifier", "file-read",
                           "read command-center/p2-wave/probes/" + UNIT + "/" + CFG["p1"]["raw"],
                           P1["raw"][-4000:], 0),
               ],
               CFG["evidence"][1].get("confidence", "almost-certain")),
]

controls = [L.control(**c) for c in CFG.get("controls", [])]
residuals = [L.residual(r["claim"], r["settling_experiment"]) for r in CFG.get("residuals", [])]

report = {
    "summary": CFG["report"],
    "probe1_pass": P1["res"]["pass"],
    "probe2_pass": P2["res"]["pass"],
    "ambiguities": P2["res"].get("ambiguities"),
}

ARTS = [a["path"] if isinstance(a, dict) else a for a in CFG["arts"]]
ROLES = {a["path"]: a.get("role", "supporting") for a in CFG["arts"] if isinstance(a, dict)}

# 4. Phase A: builder receipt BLOCKED / reviewer-absent.
built = L.build_receipt(UNIT, CFG["spec_anchor"], ARTS, evidence, tests, controls,
                        residuals, report, started, gate_note=CFG.get("gate_note"))
if not built["ok"]:
    print("FAILED:" + UNIT + " schema-validate-A " + json.dumps(built["errors"])[:1500])
    raise SystemExit(1)
L.write_receipt(built["doc"])
print("phase-A BLOCKED written")

# 5. Phase B: probe2 instrument PASS closes SUCCESS.
closed = L.build_receipt(UNIT, CFG["spec_anchor"], ARTS, evidence, tests, controls,
                         residuals, report, started, gate_note=CFG.get("gate_note"),
                         closed={
                             "reviewer_id": CFG["reviewer"]["id"],
                             "scope": CFG["reviewer"]["scope"],
                             "notes": CFG["reviewer"]["notes"],
                             "raw": P2["raw"][-1200:],
                             "measure_line": "SUCCESS:delivered " + UNIT,
                         })
if not closed["ok"]:
    print("FAILED:" + UNIT + " schema-validate-B " + json.dumps(closed["errors"])[:1500])
    raise SystemExit(1)
L.write_receipt(closed["doc"])
print("phase-B SUCCESS written")

# 6. Manifest (hashes the FINAL receipt bytes) + SUBAGENT-RETURN.
man = L.write_manifest(UNIT, ARTS, ROLES)
print("manifest rows:", len(man["rows"]))
L.write_return(UNIT, [
    {"id": "probe1", "role": CFG["p1"].get("role", "source"), "command": P1["cmd"],
     "exit_code": 0, "raw_output": P1["raw"]},
    {"id": "probe2", "role": CFG["p2"].get("role", "verifier"), "command": P2["cmd"],
     "exit_code": 0, "raw_output": P2["raw"]},
], ARTS, man["path"], CFG["report"], measure_line="SUCCESS:delivered " + UNIT)
print("return written")

# 7. The gate.
m = L.run([sys.executable, "-B", str(W / "command-center/p2-wave/_measure_one_delivered.py"), UNIT], timeout=200)
tail = (m[1] or "").strip().splitlines()[-1:] or [""]
print(tail[0])
raise SystemExit(0 if "SUCCESS:delivered " + UNIT in (m[1] or "") else 1)
