"""Program-wide census: how close is the estate P2 program to 2007 green?

Sweeps every catalog unit: receipt present / parses / state / reviewer closure
/ schema-clean against the unit's catalog output_schema (canonical
interpretation, physical control plane). Read-only.
"""
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012


def retrieve(uri):
    prefix = "file:///C:/Users/Prekzursil/source/ast-integrate/"
    if uri.startswith(prefix):
        local = REPO / uri[len(prefix):]
        if local.exists():
            return Resource.from_contents(
                json.loads(local.read_text(encoding="utf-8")),
                default_specification=DRAFT202012,
            )
    raise RuntimeError("unresolvable: " + uri)


REG = Registry(retrieve=retrieve)

_schemas = {}


def validator_for(out_schema):
    """Canonical interpretation: fragment pointer mapped onto the physical
    control plane (receipt_schema_gate.parse_schema_ref semantics)."""
    text = (out_schema or "").strip()
    head = text.split(" profile=")[0].split(" + ")[0].split(" (")[0].strip()
    frag = None
    base = head
    if "#" in head:
        base, f = head.split("#", 1)
        frag = "#" + f.strip()
    key = (base, frag)
    if key not in _schemas:
        if (not base) or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", base):
            raise ValueError("non-repo-path output_schema: %r" % (base,))
        shim_path = REPO / base
        shim = json.loads(shim_path.read_text(encoding="utf-8"))
        target = {"$ref": shim["$id"] + frag} if frag else shim
        _schemas[key] = Draft202012Validator(target, registry=REG)
    return _schemas[key]


cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = [u for u in cat["work_units"] if isinstance(u, dict) and u.get("id")]

present = parse_fail = 0
states = Counter()
rev_pass = rev_pass_and_schema_ok = 0
schema_err_counter = Counter()
state_x_schema = Counter()
missing_by_phase = Counter()
bad_schema_decl = 0
for u in units:
    uid = u["id"]
    p = REPO / str(u["output_path"])
    if not p.exists():
        missing_by_phase[str(u.get("phase", "?"))] += 1
        states["<no-receipt>"] += 1
        continue
    present += 1
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        parse_fail += 1
        states["<unparseable>"] += 1
        continue
    st = str(doc.get("state", "")).upper() or "<none>"
    states[st] += 1
    try:
        errs = sorted(e.message for e in validator_for(u.get("output_schema")).iter_errors(doc))
    except ValueError:
        bad_schema_decl += 1
        errs = ["<non-repo-path output_schema>"]
    except Exception as exc:
        bad_schema_decl += 1
        errs = ["<schema-load-failed: %s>" % type(exc).__name__]
    sok = not errs
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    closed = rev.get("verdict") == "PASS" and rev.get("independent") is True
    if st == "SUCCESS" and closed:
        rev_pass += 1
        if sok:
            rev_pass_and_schema_ok += 1
    if sok:
        state_x_schema[st + " | schema-clean"] += 1
    else:
        state_x_schema[st + " | schema-DIRTY"] += 1
        for e in errs:
            schema_err_counter[re.sub(r"'[^']*'", "<x>", e)[:80]] += 1

out = {
    "catalog_units": len(units),
    "receipts_present": present,
    "receipts_missing": len(units) - present,
    "unparseable": parse_fail,
    "non_repo_path_output_schema": bad_schema_decl,
    "states": dict(states),
    "success_with_independent_pass": rev_pass,
    "success_with_independent_pass_AND_schema_clean": rev_pass_and_schema_ok,
    "state_x_schema": dict(state_x_schema),
    "top_schema_error_shapes": dict(schema_err_counter.most_common(12)),
    "missing_receipts_by_phase": dict(missing_by_phase.most_common(15)),
}
(REPO / "_reviewer-w4-shard18-r2/census-2007.json").write_text(
    json.dumps(out, indent=1), encoding="utf-8"
)
print(json.dumps(out, indent=1)[:4200])
