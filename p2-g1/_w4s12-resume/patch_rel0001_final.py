"""REL-0001 final: (1) nested-required detector in diff_schema (D3);
(2) D1-D3-only resolution; (3) honest BLOCKED disposition (D4-D6 open)."""
from pathlib import Path

LINT = Path(r"C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes\REL-0001\release_bump_linter.py")
t = LINT.read_text(encoding="utf-8")

old = """def diff_schema(old, new):
    op = old.get("properties") or {}
    np_ = new.get("properties") or {}
    oreq = set(old.get("required") or [])
    nreq = set(new.get("required") or [])
    for f in sorted(set(op) & set(np_)):
        if f in nreq and f not in oreq:
            yield ("SCHEMA-FIELD-BECAME-REQUIRED", "MAJOR",
                   "existing field became required: " + f)
        elif op[f] != np_[f]:
            yield ("SCHEMA-FIELD-REMOVED-OR-DOMAIN-NARROWED", "MAJOR",
                   "field domain narrowed or changed: " + f)
    for f in sorted(set(np_) - set(op)):
        yield ("SCHEMA-OPTIONAL-FIELD-OR-DOMAIN-ADDED", "MINOR",
               "field added inside schema: " + f)"""

new = '''def _nested_required(schema):
    """Every field named in ANY required list, at any nesting depth (D3 fix)."""
    req = set(schema.get("required") or [])
    for v in (schema.get("properties") or {}).values():
        if isinstance(v, dict):
            req |= _nested_required(v)
    return req


def diff_schema(old, new):
    op = old.get("properties") or {}
    np_ = new.get("properties") or {}
    oreq = set(old.get("required") or [])
    nreq = set(new.get("required") or [])
    for f in sorted(set(op) & set(np_)):
        grew = _nested_required(np_[f]) - _nested_required(op[f])
        if f in nreq and f not in oreq:
            yield ("SCHEMA-FIELD-BECAME-REQUIRED", "MAJOR",
                   "existing field became required: " + f)
        elif grew:
            yield ("SCHEMA-FIELD-BECAME-REQUIRED", "MAJOR",
                   "field gained required content (nested): " + f)
        elif op[f] != np_[f]:
            yield ("SCHEMA-FIELD-REMOVED-OR-DOMAIN-NARROWED", "MAJOR",
                   "field domain narrowed or changed: " + f)
    for f in sorted(set(np_) - set(op)):
        if _nested_required(np_[f]):
            yield ("SCHEMA-FIELD-BECAME-REQUIRED", "MAJOR",
                   "newly added schema object carries required fields: " + f)
        else:
            yield ("SCHEMA-OPTIONAL-FIELD-OR-DOMAIN-ADDED", "MINOR",
                   "field added inside schema: " + f)'''

assert old in t, "diff_schema block not found"
t = t.replace(old, new)
LINT.write_text(t, encoding="utf-8", newline="\n")
print("PATCHED linter (nested required)")

DRV = Path(r"C:\Users\Prekzursil\p2-g1\_w4s12-resume\complete_envelopes.py")
t2 = DRV.read_text(encoding="utf-8")

old2 = """    for d in old_defects:
        if isinstance(d, dict) and str(d.get("id", "")).startswith("REL-0001-D"):
            prior_ids.append(d)
            nd = dict(d)
            nd["status"] = "resolved"
            nd["resolution"] = ("max-rank bump derivation (w4s12 2026-10-26): required bump is the "
                                "highest matched rule bump, so a mixed diff can no longer be masked "
                                "down by a later lower rule; fix held by probe2 fix-hold recheck.")
            new_defects.append(nd)
        else:
            new_defects.append(d)
    rec["defects"] = new_defects"""
new2 = """    for d in old_defects:
        if isinstance(d, dict) and str(d.get("id", "")) in ("REL-0001-D1", "REL-0001-D2", "REL-0001-D3"):
            prior_ids.append(d)
            nd = dict(d)
            nd["status"] = "resolved"
            nd["resolution"] = ("max-rank bump derivation + nested-required descent (w4s12 2026-10-26): "
                                "required bump is the highest matched rule bump at any nesting depth, so "
                                "a mixed diff can no longer be masked down by a later lower rule; fix "
                                "held by probe2 fix-hold recheck. D4-D6 are substrate/tooling limitations "
                                "NOT addressed by this fix and stay open.")
            new_defects.append(nd)
        else:
            new_defects.append(d)
    rec["defects"] = new_defects"""
assert old2 in t2, "defect loop not found"
t2 = t2.replace(old2, new2)

# REL-0001 honest BLOCKED disposition, applied AFTER complete_envelope overwrites
old3 = """        if uid == "REL-0001":
            rec = rel0001_content_fix(rec, outs)
        rec = complete_envelope(uid, rec, unit, outs, trows, names)"""
new3 = """        if uid == "REL-0001":
            rec = rel0001_content_fix(rec, outs)
        rec = complete_envelope(uid, rec, unit, outs, trows, names)
        if uid == "REL-0001":
            open_p1 = [d.get("id") for d in rec.get("defects") or []
                       if isinstance(d, dict) and d.get("status") == "open"
                       and d.get("severity") in ("P0", "P1")]
            withheld = ("FAILED:REL-0001 SUCCESS withheld by builder lane: D1-D3 masking defects "
                        "fixed (max-rank + nested-required descent) and probe-verified; "
                        + (f"open P1 defects {open_p1} remain (substrate/tooling limitations); "
                           if open_p1 else "")
                        + "independent reviewer closure required before SUCCESS")
            rec["state"] = "BLOCKED"
            rec["completion_sentinel"] = withheld
            rec["sentinel"] = withheld
            ext = rec.get("extensions") if isinstance(rec.get("extensions"), dict) else {}
            rec["extensions"] = ext
            ext.setdefault("catalog_completion_sentinel", "SUCCESS:REL-0001")
            rec["failure"] = {
                "classification": ["reviewer-absent", "open-defects-p1"],
                "blocked_on": ("independent reviewer closure (fan-in reviewer lane); open "
                               "substrate/tooling defects D4-D6 recorded by the original build"),
                "reason": ("Builder lane may not self-certify. D1-D3 masking defects are fixed and "
                           "held by the fix-hold probes; D4-D6 (probe-scoped linter without live git "
                           "metadata; harvest sidecar integrity; stale harvest diagnostic) remain "
                           "open as recorded by the original build and are outside this shard's "
                           "file scope. Receipt receipt_core-valid at BLOCKED; SUCCESS requires "
                           "reviewer PASS + independent=true after D4-D6 disposition."),
            }"""
assert old3 in t2, "main rel0001 hook not found"
t2 = t2.replace(old3, new3)
DRV.write_text(t2, encoding="utf-8", newline="\n")
print("PATCHED driver (D1-D3-only resolution + BLOCKED disposition)")
print("DONE")
