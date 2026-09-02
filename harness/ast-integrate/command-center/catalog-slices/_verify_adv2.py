#!/usr/bin/env python3
"""Verify ADV-2.json off disk. Never trusts the generator's in-memory list."""
from __future__ import annotations

import json
import pathlib
import re
import glob
import itertools

HERE = pathlib.Path(__file__).parent
TARGET = HERE / "ADV-2.json"

REQUIRED = ["id", "title", "phase", "question_or_target", "inputs", "dependencies",
            "assigned_model_vendor_role", "tool_permissions", "execution_substrate",
            "timeout_seconds", "output_path", "output_schema", "evidence_requirement",
            "tests_required", "reviewer_requirement", "completion_sentinel", "retry_policy",
            "failure_classification", "owner_approval_required"]
PHASES = {"0", "1", "2", "2A", "2B", "2C", "3", "4", "5", "6", "7", "7A", "8", "9",
          "10", "11", "12", "13", "14", "15", "16"}
SUBSTRATES = {"local-serialized", "local-parallel", "worktree-isolated", "cloud-batch"}

fail: list[str] = []
info: list[str] = []


def chk(cond: bool, msg: str) -> None:
    if not cond:
        fail.append(msg)


raw = TARGET.read_bytes()
chk(raw.count(b"\r\n") == 0, f"CRLF present ({raw.count(chr(13).encode()+chr(10).encode())})")
chk(all(c < 128 for c in raw), "non-ascii bytes present")
units = json.loads(raw.decode("utf-8"))
chk(isinstance(units, list), "top level is not a JSON array")
info.append(f"UNITS-ON-DISK={len(units)}  BYTES={len(raw)}")

# --- 1. field completeness (all 19 spec fields + the 20th, owner_approval_required, is in REQUIRED)
for x in units:
    missing = [f for f in REQUIRED if f not in x or x[f] in (None, "", [], {})]
    # owner_approval_required False is legitimate, not "missing"
    missing = [m for m in missing if not (m == "owner_approval_required" and x.get(m) is False)]
    chk(not missing, f"{x.get('id')}: missing/empty {missing}")

# --- 2. id format, uniqueness, sequence from 129
ids = [x["id"] for x in units]
chk(len(set(ids)) == len(ids), "duplicate ids within slice")
for i, uid in enumerate(ids):
    chk(re.fullmatch(r"ADV-\d{4}", uid) is not None, f"bad id format {uid}")
    chk(uid == f"ADV-{129 + i:04d}", f"id out of sequence at index {i}: {uid}")

# --- 3. enum validity + type checks
for x in units:
    chk(str(x["phase"]) in PHASES, f"{x['id']}: bad phase {x['phase']}")
    chk(x["execution_substrate"] in SUBSTRATES, f"{x['id']}: bad substrate")
    chk(isinstance(x["timeout_seconds"], int) and x["timeout_seconds"] > 0, f"{x['id']}: bad timeout")
    chk(isinstance(x["owner_approval_required"], bool), f"{x['id']}: owner_approval_required not bool")
    for arr in ("inputs", "dependencies", "tool_permissions", "tests_required", "failure_classification"):
        chk(isinstance(x[arr], list) and len(x[arr]) > 0, f"{x['id']}: {arr} not a non-empty list")
    a = x["assigned_model_vendor_role"]
    chk(isinstance(a, dict) and {"model", "vendor", "role"} <= set(a), f"{x['id']}: bad assignment")
    chk(x["id"] in x["completion_sentinel"], f"{x['id']}: sentinel does not name the unit")
    chk(x["id"] in x["output_path"], f"{x['id']}: output_path does not name the unit")
    q = x["question_or_target"]
    chk("?" in q or "target" in q.lower() or q.rstrip().endswith("."),
        f"{x['id']}: question_or_target is not a question or target")

# --- 4. DEFAULTS-IN-DISGUISE: the measured P1 on WORK-UNIT-CATALOG.json.
#        A field carrying exactly one distinct value across the whole slice is a global
#        default wearing a per-unit costume.
VARY = ["assigned_model_vendor_role", "tool_permissions", "execution_substrate",
        "timeout_seconds", "output_schema", "evidence_requirement", "tests_required",
        "reviewer_requirement", "retry_policy", "failure_classification",
        "owner_approval_required", "phase"]
for f in VARY:
    vals = {json.dumps(x[f], sort_keys=True) for x in units}
    chk(len(vals) > 1, f"FIELD {f} has a single distinct value across all 16 units (default in disguise)")
    info.append(f"distinct[{f}]={len(vals)}")

# --- 5. NEAR-DUPLICATE detection within the slice, with a planted-mutant control.
STOP = set("the a an of to and or is are be for with that this it its on in by not no as at from "
           "every each any all must may can does do did which what who whom whose than then "
           "into over under between across per via one two three unit units program spec".split())


def toks(x: dict) -> set[str]:
    blob = " ".join([x["title"], x["question_or_target"], x["evidence_requirement"]]).lower()
    return {w for w in re.findall(r"[a-z][a-z0-9-]{2,}", blob) if w not in STOP}


def jac(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a | b) else 0.0


pairs = []
for x, y in itertools.combinations(units, 2):
    pairs.append((jac(toks(x), toks(y)), x["id"], y["id"]))
pairs.sort(reverse=True)
worst = pairs[0]
info.append(f"max intra-slice Jaccard = {worst[0]:.3f} between {worst[1]} and {worst[2]}")
info.append("top5 pairs: " + ", ".join(f"{s:.3f} {a}/{b}" for s, a, b in pairs[:5]))

# DETECTOR CONTROL for check 5: plant a near-duplicate of unit 0 (reworded, same mechanism)
# and prove the detector separates it from the real corpus.
plant = json.loads(json.dumps(units[0]))
plant["id"] = "ADV-PLANT"
plant["title"] = plant["title"].replace("Refuter-corps calibration", "Measuring the refuter corps")
plant["question_or_target"] = plant["question_or_target"].replace("What are", "Determine what are")
plant_score = jac(toks(plant), toks(units[0]))
chk(plant_score > 0.85, f"CONTROL FAILED: planted reworded duplicate scored only {plant_score:.3f}")
chk(worst[0] < plant_score, "CONTROL FAILED: a real pair scores as high as the planted duplicate")
info.append(f"planted-duplicate control = {plant_score:.3f} (must exceed every real pair)")

# also prove the detector is not silent on the healthy side: two hand-picked distinct units
lo = min(pairs)
info.append(f"min intra-slice Jaccard = {lo[0]:.3f} between {lo[1]} and {lo[2]}")

# --- 6. cross-slice id collision (siblings are writing concurrently)
mine = set(ids)
for f in sorted(glob.glob(str(HERE / "*.json"))):
    p = pathlib.Path(f)
    if p.name == "ADV-2.json":
        continue
    try:
        other = json.load(open(p, encoding="utf-8"))
    except Exception as exc:                      # a sibling mid-write is not my failure
        info.append(f"skip {p.name}: {type(exc).__name__}")
        continue
    if not isinstance(other, list):
        continue
    clash = mine & {o.get("id") for o in other if isinstance(o, dict)}
    chk(not clash, f"id collision with {p.name}: {sorted(clash)}")

# --- 7. dependency references: bucket codes or plausible unit ids only
DEP = re.compile(r"^(B\d{2}|[A-Z]{2,4}-\d{4})$")
for x in units:
    bad = [d for d in x["dependencies"] if not DEP.match(d)]
    chk(not bad, f"{x['id']}: unparseable dependency refs {bad}")

# --- 8. every unit must carry a negative control / mutation in tests_required (spec 11026)
NEG = re.compile(r"control|negative|planted|plant |mutation|falsif|both.states|invert", re.I)
for x in units:
    chk(any(NEG.search(t) for t in x["tests_required"]),
        f"{x['id']}: no negative control or mutation in tests_required")

print("\n".join(info))
print()
if fail:
    print(f"FAILED:verify-ADV-2 {len(fail)} violation(s)")
    for m in fail:
        print("  -", m)
    raise SystemExit(1)
print(f"SUCCESS:verify-ADV-2 units={len(units)} first={ids[0]} last={ids[-1]}")
