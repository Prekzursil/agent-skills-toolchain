"""CC-0002 INDEPENDENT REVIEW -- the fifth mutant.

Reviewer contract (CC-0002.reviewer_requirement):
  "One independent reviewer who writes a fifth mutant the author did not anticipate and confirms
   it is rejected."

WHY THIS MUTANT, chosen before running anything. `receipt_validate.admit()` has four reject
conditions -- C1 parse, C2 schema, C3 catalog cross-reference, C4 sentinel binds to unit_id. The
author's four mutants exercise C1 (m4), C2 twice (m1, m2) and C3 (m3). **C4 is never exercised**:
m1 DELETES the sentinel, which C2 catches first as a missing required field, and m3 rewrites the
sentinel to match its forged unit_id. So the one condition with zero mutant coverage is C4, and a
receipt that is parseable, schema-valid, and for a REAL catalog unit, but whose sentinel belongs
to a DIFFERENT unit -- the copy-paste receipt -- reaches C4 and nothing else.

Three mutants are run. M5 is the contracted one; M6 and M7 are adversarial extras whose results
are reported either way, scoped to the question the module says it answers (ADMISSION, not
completion and not truthfulness).
"""

import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MUT = ROOT / "command-center/p2-next/_mutants"
MUT.mkdir(parents=True, exist_ok=True)
GOLDEN = ROOT / "command-center/receipts/TST-0334.json"

spec = importlib.util.spec_from_file_location(
    "receipt_validate", ROOT / "command-center/receipt_validate.py"
)
rv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rv)
gate = rv._load_gate()
ids = rv.catalog_ids()
golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
print(f"catalog ids loaded: {len(ids)}; golden unit_id={golden['unit_id']}")
print(f"golden sentinel   : {golden['sentinel']!r}\n")

out = {"unit": "CC-0002", "mutants": [], "findings": []}


def run(name, doc_or_bytes, want_reject, want_code, rationale):
    p = MUT / f"{name}.json"
    if isinstance(doc_or_bytes, (bytes, str)):
        p.write_text(
            doc_or_bytes if isinstance(doc_or_bytes, str) else doc_or_bytes.decode(),
            encoding="utf-8",
        )
    else:
        p.write_text(
            json.dumps(doc_or_bytes, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    got, uid, reason = rv.admit(p, ids, gate)
    rejected = not got
    code = reason.split()[0] if reason else ""
    ok = (rejected == want_reject) and (not want_code or code == want_code)
    print(f"  {name}")
    print(f"    rationale : {rationale}")
    print(
        f"    want      : {'REJECT' if want_reject else 'ACCEPT'}"
        f"{' on ' + want_code if want_code else ''}"
    )
    print(
        f"    got       : {'REJECT' if rejected else 'ACCEPT'}  [{code}] {reason[:110]}"
    )
    print(f"    -> {'AS EXPECTED' if ok else '*** UNEXPECTED ***'}\n")
    out["mutants"].append(
        {
            "name": name,
            "path": str(p.relative_to(ROOT)).replace("\\", "/"),
            "rationale": rationale,
            "expected": "REJECT" if want_reject else "ACCEPT",
            "expected_condition": want_code,
            "observed": "REJECT" if rejected else "ACCEPT",
            "observed_condition": code,
            "reason": reason,
            "as_expected": ok,
        }
    )
    return rejected, code, reason


# ---- CONTROL FIRST: the golden must still be ACCEPTED, or a blanket-reject validator would
# "pass" every mutant for free. This is the both-states half.
g_ok, g_uid, g_reason = rv.admit(GOLDEN, ids, gate)
print(f"CONTROL golden -> {'ACCEPT' if g_ok else 'REJECT'}: {g_reason}")
out["control_golden_accepted"] = g_ok
if not g_ok:
    print(
        "FAILED:cc0002-review the golden is rejected, so no mutant rejection means anything"
    )
    sys.exit(1)
print()

# ---- M5: THE CONTRACTED FIFTH MUTANT -- the only uncovered condition, C4.
# The sentinel grammar (read from platform/schema/receipt.schema.json) is
# SUCCESS:<ID> or SENTINEL:<ID>:<TOKEN>, with <ID> = ^[A-Z][A-Z0-9]*-[0-9]{4}$. A first attempt
# used "SUCCESS:AUD-0006-uncommitted-work-census", which is NOT schema-valid, so it died at C2
# and never reached C4 -- a reviewer-instrument miss, recorded rather than hidden. The mutant
# below is schema-valid by construction, so C4 is the only condition left that can reject it.
m5 = json.loads(json.dumps(golden))
victim = "AUD-0006"
assert victim in ids and victim != m5["unit_id"]
m5["sentinel"] = (
    f"SENTINEL:{victim}:BLOCKED-ON-INDEPENDENT-REVIEW copy-pasted from another unit"
)
run(
    "m5-sentinel-belongs-to-a-different-real-unit",
    m5,
    True,
    "C4",
    "parseable, SCHEMA-VALID sentinel, unit_id is a REAL catalog unit -- but the sentinel binds "
    "to a DIFFERENT real unit. This is the copy-paste receipt, and C4 is the one admit() "
    "condition no author mutant reaches (m1 deletes the sentinel and dies at C2; m3 rewrites "
    "the sentinel to match its own forged id).",
)

m5b = json.loads(json.dumps(golden))
m5b["sentinel"] = f"SUCCESS:{victim}"
run(
    "m5b-sentinel-other-unit-SUCCESS-family",
    m5b,
    True,
    "C4",
    "the same attack in the other sentinel family (1,911 of 2,007 catalogued sentinels are "
    "bare SUCCESS:<ID>), so C4 is shown to hold for both grammars, not just one.",
)

# ---- M6: is C4's containment test exploitable by an id that CONTAINS another id?
prefix_pairs = sorted((a, b) for a in ids for b in ids if a != b and b.startswith(a))
print(
    f"  [survey] catalog ids that are a strict prefix of another id: {len(prefix_pairs)}"
    f" {prefix_pairs[:3]}"
)
out["catalog_prefix_pairs"] = len(prefix_pairs)
m6 = json.loads(json.dumps(golden))
m6["sentinel"] = f"SUCCESS:{m6['unit_id']}0"
run(
    "m6-sentinel-superstring-of-the-unit-id",
    m6,
    True,
    "",
    "C4 binds by SUBSTRING (`uid not in sentinel`), which in isolation would admit a sentinel "
    "naming a longer id that merely CONTAINS the real one. Probing whether the schema's "
    f"fixed-width id pattern closes that hole. Survey: {len(prefix_pairs)} catalog ids are a "
    "strict prefix of another.",
)

# ---- M7: does the substrate detect a receipt that LIES about its own artifacts?
m7 = json.loads(json.dumps(golden))
if isinstance(m7.get("artifacts"), list) and m7["artifacts"]:
    m7["artifacts"][0] = dict(m7["artifacts"][0])
    m7["artifacts"][0]["path"] = (
        "command-center/p2-next/_mutants/this-file-does-not-exist.txt"
    )
    m7["artifacts"][0]["exists"] = True
    m7["artifacts"][0]["sha256"] = "0" * 64
    m7["artifacts"][0]["bytes"] = 999999
run(
    "m7-artifact-claims-a-nonexistent-file-exists",
    m7,
    False,
    "",
    "asserts exists=true, bytes=999999 and a fabricated sha256 for a path that is not on disk. "
    "receipt_validate's docstring scopes it to ADMISSION -- well-formedness, not truthfulness -- "
    "so acceptance here is IN SCOPE for this module; recorded because 'a gate that reads a claim "
    "is not a gate' and no layer in the substrate currently re-derives artifact metadata.",
)

# ---- does the shipped self-test still pass after this reviewer poked at it?
r = subprocess.run(
    [sys.executable, "command-center/receipt_validate.py", "--self-test"],
    cwd=ROOT,
    capture_output=True,
    text=True,
)
print(f"shipped --self-test rc={r.returncode}")
print("  " + "\n  ".join(r.stdout.strip().splitlines()[-6:]))
out["shipped_selftest_rc"] = r.returncode

rows = {
    m["name"]: m for m in out["mutants"]
}  # key by NAME: index-keying silently dropped a row
m5_row = rows["m5-sentinel-belongs-to-a-different-real-unit"]
verdict_pass = (
    m5_row["as_expected"]
    and m5_row["observed"] == "REJECT"
    and m5_row["observed_condition"] == "C4"
    and g_ok
    and r.returncode == 0
)
if not m5_row["as_expected"]:
    out["findings"].append(
        {
            "severity": "HIGH",
            "kind": "uncovered-condition-is-broken",
            "defect": f"the fifth mutant was {m5_row['observed']} on [{m5_row['observed_condition']}]",
        }
    )
if rows["m6-sentinel-superstring-of-the-unit-id"]["observed"] == "ACCEPT":
    out["findings"].append(
        {
            "severity": "LOW",
            "kind": "substring-sentinel-binding",
            "defect": "C4 binds the sentinel by substring containment, so a sentinel naming a "
            "SUPERSTRING id is admitted",
            "reachable_with_real_ids": prefix_pairs != [],
            "suggested_fix": "bind on a delimiter, e.g. require f'{uid}-' or f'{uid}:' in sentinel",
        }
    )
else:
    out["observations"] = out.get("observations", []) + [
        {
            "kind": "substring-binding-is-closed-upstream",
            "note": "C4's substring test would in isolation admit a superstring id, but the schema's "
            "fixed-width id pattern ^[A-Z][A-Z0-9]*-[0-9]{4}$ rejects such a sentinel at C2, "
            f"and {len(prefix_pairs)} real catalog ids are a strict prefix of another. Not a "
            "hole; recorded so a future schema relaxation knows it is load-bearing.",
        }
    ]
if rows["m7-artifact-claims-a-nonexistent-file-exists"]["observed"] == "ACCEPT":
    out["observations"] = out.get("observations", []) + [
        {
            "kind": "artifact-metadata-never-re-derived",
            "defect": "a receipt may assert exists=true, a fabricated sha256 and a fabricated byte "
            "count for a path that is not on disk, and the substrate admits it",
            "in_scope_for_this_module": False,
            "why_not_a_CC-0002_refutation": "receipt_validate.py's own docstring scopes it to "
            "ADMISSION and says completion is receipt_schema_gate "
            "layer 2; neither layer claims to re-derive artifacts. "
            "This is a substrate GAP to file, not a broken promise.",
            "suggested_owner": "a new condition C5, or an artifact-verifier unit",
        }
    ]
out["verdict"] = "PASS" if verdict_pass else "FAIL"
print(
    f"\nCC-0002 reviewer verdict: {out['verdict']}  (findings={len(out['findings'])})"
)
(ROOT / "command-center/p2-next/REVIEW-CC-0002.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8"
)
print("SUCCESS:cc0002-fifth-mutant")
