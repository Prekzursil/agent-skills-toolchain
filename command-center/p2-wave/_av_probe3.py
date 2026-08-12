"""ADVERSARIAL VERIFIER probe 3.

Q8.  Blob-level verification done MY way (git cat-file -p on the ls-tree hash, not the
     builder's script, not the worktree copy). Per-unit corruption control on ALL FIVE,
     not just AUD-0020 (the gap the auditor named).
Q9.  Are these artifacts SUBSTANCE or padding? A verifier in this program returned CONFIRMED
     for a file asserting 999999 passing tests and for 2,000 x characters. So: measure
     distinct-key count, max run of a repeated character, and distinct value count.
Q10. Half-gate: does parse_schema_ref really drop everything after ' + '? Count units.
Q11. Independent re-derivation of AUD-0041's headline (workflows/jobs/steps) with my own
     YAML walk, including the bare `on:` -> True trap.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
CAT = REPO / "command-center/WORK-UNIT-CATALOG.json"


def load(name: str, rel: str):
    p = REPO / rel
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(p.parent))
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


sr = load("schema_resolver", "platform/lib/schema_resolver.py")
rsg = load("receipt_schema_gate", "platform/lib/receipt_schema_gate.py")
units = json.loads(CAT.read_text(encoding="utf-8"))["work_units"]
by_id = {u["id"]: u for u in units}
FIVE = ["IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020"]


def git(*a: str) -> bytes:
    return subprocess.run(
        ["git", *a], cwd=str(REPO), capture_output=True, check=True
    ).stdout


def blob_bytes(path: str) -> bytes:
    out = git("ls-files", "-s", "--", path).decode().strip()
    if not out:
        raise SystemExit(f"NOT TRACKED: {path}")
    sha = out.split()[1]
    return git("cat-file", "-p", sha)


def deep_stats(o, keys: set, vals: list, depth=0):
    if depth > 40:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            keys.add(k)
            deep_stats(v, keys, vals, depth + 1)
    elif isinstance(o, list):
        for v in o:
            deep_stats(v, keys, vals, depth + 1)
    else:
        vals.append(o)


print(
    "=== Q8/Q9: stored-blob verification + substance, with a per-unit corruption control ==="
)
hdr = f"{'unit':10s} {'blobB':>7s} {'CRLF':>5s} {'parse':>5s} {'errs':>5s} {'ctlErr':>6s} {'keys':>5s} {'vals':>6s} {'uniqV':>6s} {'maxRun':>6s} state"
print(hdr)
for uid in FIVE:
    u = by_id[uid]
    p = u["output_path"]
    raw = blob_bytes(p)
    crlf = raw.count(b"\r\n")
    try:
        doc = json.loads(raw.decode("utf-8"))
        parsed = True
    except Exception:  # noqa: BLE001
        doc, parsed = None, False
    declared = u["output_schema"]
    errs = sr.validate_artifact(doc, declared) if parsed else ["UNPARSED"]
    # per-unit corruption control: delete the first top-level key that is not `state`
    ctl = "n/a"
    if parsed and isinstance(doc, dict):
        victim = next((k for k in doc if k != "state"), None)
        if victim is not None:
            mut = {k: v for k, v in doc.items() if k != victim}
            ctl = len(sr.validate_artifact(mut, declared))
    keys: set = set()
    vals: list = []
    deep_stats(doc, keys, vals)
    txt = raw.decode("utf-8", "replace")
    maxrun = max((len(m.group(0)) for m in re.finditer(r"(.)\1{3,}", txt)), default=0)
    uniq = len({repr(v) for v in vals})
    print(
        f"{uid:10s} {len(raw):7d} {crlf:5d} {str(parsed):>5s} {len(errs):5d} "
        f"{str(ctl):>6s} {len(keys):5d} {len(vals):6d} {uniq:6d} {maxrun:6d} "
        f"{(doc or {}).get('state')}"
    )

print("\n=== Q10: half-gate -- does ' + ' get dropped? ===")
two = [
    u
    for u in units
    if isinstance(u.get("output_schema"), str) and " + " in u["output_schema"]
]
print(f"units declaring a two-schema expression: {len(two)}")
if two:
    d = two[0]["output_schema"]
    lg, frag = rsg.parse_schema_ref(d)
    print(f"  sample declared : {d}")
    print(f"  parse_schema_ref -> logical={lg!r} fragment={frag!r}")
    halves = [h.strip() for h in d.split("+")]
    print(f"  declared halves : {halves}")
    probe = {"totally": "unrelated"}
    for h in halves:
        try:
            n = len(sr.validate_artifact(probe, h))
            print(f"    half {h[:60]:60s} -> errors={n}")
        except Exception as e:  # noqa: BLE001
            print(f"    half {h[:60]:60s} -> RAISED {type(e).__name__}")
    try:
        n = len(sr.validate_artifact(probe, d))
        print(
            f"    COMBINED expression -> errors={n}  "
            f"(if the 2nd half raises alone but the combo does not, half B is DROPPED)"
        )
    except Exception as e:  # noqa: BLE001
        print(f"    COMBINED expression -> RAISED {type(e).__name__}")

print("\n=== Q11: independent AUD-0041 headline re-derivation ===")
try:
    import yaml
except ImportError:
    print("  pyyaml missing -- NOT-CHECKED")
    yaml = None
if yaml:
    wf = sorted((REPO / ".github/workflows").glob("*.yml")) + sorted(
        (REPO / ".github/workflows").glob("*.yaml")
    )
    jobs = steps = 0
    on_via_true = 0
    for f in wf:
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        if "on" not in d and True in d:
            on_via_true += 1
        for _jn, j in (d.get("jobs") or {}).items():
            jobs += 1
            steps += len(j.get("steps") or [])
    print(
        f"  workflow files={len(wf)} jobs={jobs} steps={steps} "
        f"files where bare `on:` parsed as boolean True={on_via_true}"
    )
    a = json.loads(blob_bytes(by_id["AUD-0041"]["output_path"]).decode("utf-8"))
    flat = json.dumps(a)
    for n in (len(wf), jobs, steps):
        print(f"    does the artifact contain the number {n}? {str(n) in flat}")
print("\nDONE:av-probe3")
