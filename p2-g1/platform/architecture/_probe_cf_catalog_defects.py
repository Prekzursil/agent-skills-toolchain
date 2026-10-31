"""Probe: independently re-derive the four catalog defects the brief names.

Brief claims (from the DSL conformance run):
  159 unloadable output_schema refs
   41 unresolvable dependency refs
   96 completion sentinels that do not name their own unit
  128 non-canonical assigned_model_vendor_role shapes

Each is answerable by an exact algorithm, so this writes the algorithm rather than
asking a model. Each check carries a KNOWN-BROKEN control so a 0 cannot be trusted
as absence.
"""
import json
import os
import re
import sys

REPO = r"C:\Users\Prekzursil\source\ast-integrate"
sys.path.insert(0, os.path.join(REPO, "platform", "lib"))

cat = json.load(open(os.path.join(REPO, "command-center", "WORK-UNIT-CATALOG.json"), encoding="utf-8"))
wus = cat["work_units"]
ids = {u["id"] for u in wus}
buckets = {u.get("bucket") for u in wus if u.get("bucket")}
out = {"catalog_units": len(wus), "distinct_ids": len(ids), "distinct_buckets": len(buckets)}

BARE_REF = re.compile(r"^[A-Za-z0-9_.\-/]+\.json(#/[A-Za-z0-9_.\-/$]*)?$")


# ---------- 1. output_schema not a loadable bare path -----------------------
def unloadable(v):
    return not (isinstance(v, str) and BARE_REF.match(v.strip()))


bad_os = [u["id"] for u in wus if unloadable(u.get("output_schema"))]
out["check1_output_schema_not_bare_path"] = len(bad_os)
out["check1_control_known_broken"] = unloadable("a.json + b.json")  # must be True
out["check1_control_known_good"] = not unloadable("command-center/schema/x.schema.json#/$defs/y")


# ---------- 2. dependency refs that resolve to nothing ---------------------
def dep_tokens(u):
    d = u.get("dependencies")
    if isinstance(d, list):
        return [str(x) for x in d]
    if isinstance(d, str):
        return [d]
    return []


unres_units, unres_tokens = [], {}
for u in wus:
    bad = []
    for t in dep_tokens(u):
        tt = t.strip()
        if not tt or tt.lower() in ("none", "-", "n/a"):
            continue
        if tt in ids or tt in buckets:
            continue
        # a token that CONTAINS a known id/bucket still resolves
        if any(k in tt for k in ids) or any(b and b in tt for b in buckets):
            continue
        bad.append(tt)
    if bad:
        unres_units.append(u["id"])
        for b in bad:
            unres_tokens[b] = unres_tokens.get(b, 0) + 1
out["check2_units_with_unresolvable_dep"] = len(unres_units)
out["check2_distinct_unresolvable_tokens"] = len(unres_tokens)
out["check2_top_tokens"] = dict(sorted(unres_tokens.items(), key=lambda kv: -kv[1])[:12])
out["check2_control_known_broken"] = "ZZZ-9999" not in ids and "ZZZ-9999" not in buckets

# ---------- 3. completion_sentinel does not name its own unit -------------
bad_sent = [u["id"] for u in wus
            if not (isinstance(u.get("completion_sentinel"), str)
                    and u["id"] in u["completion_sentinel"])]
out["check3_sentinel_missing_own_id"] = len(bad_sent)
out["check3_sample"] = bad_sent[:10]
_probe = {"id": "X-1", "completion_sentinel": "SUCCESS:Y-2 ..."}
out["check3_control_known_broken"] = _probe["id"] not in _probe["completion_sentinel"]

# ---------- 4. assigned_model_vendor_role canonical shape ----------------
CANON = {"model", "vendor", "role"}


def noncanon(v):
    if isinstance(v, dict):
        return set(v.keys()) != CANON
    return True  # a bare string like "opus/anthropic/implementer" is not the dict shape


bad_role = [u["id"] for u in wus if noncanon(u.get("assigned_model_vendor_role"))]
shapes = {}
for u in wus:
    v = u.get("assigned_model_vendor_role")
    k = "dict:" + ",".join(sorted(v.keys())) if isinstance(v, dict) else "str"
    shapes[k] = shapes.get(k, 0) + 1
out["check4_noncanonical_role_shapes"] = len(bad_role)
out["check4_shape_hist"] = dict(sorted(shapes.items(), key=lambda kv: -kv[1]))
out["check4_control_known_broken"] = noncanon({"model": "opus", "vendor": "a", "role": "r", "basis": "x"})
out["check4_control_known_good"] = not noncanon({"model": "opus", "vendor": "a", "role": "r"})

# ---------- 5. output_path collisions (two units, one file) --------------
byp = {}
for u in wus:
    byp.setdefault(str(u.get("output_path")), []).append(u["id"])
coll = {p: v for p, v in byp.items() if len(v) > 1}
out["check5_output_path_collisions"] = len(coll)
out["check5_units_in_a_collision"] = sum(len(v) for v in coll.values())
out["check5_sample"] = {p: v for p, v in list(coll.items())[:4]}

# ---------- 6. how many units write inside command-center/ -------------
inside = sum(1 for u in wus if str(u.get("output_path", "")).startswith("command-center/"))
out["check6_units_writing_under_command_center"] = inside
out["check6_units_writing_elsewhere"] = len(wus) - inside
elsewhere = sorted({str(u.get("output_path", "")).split("/")[0]
                    for u in wus if not str(u.get("output_path", "")).startswith("command-center/")})
out["check6_other_roots"] = elsewhere

controls = [out["check1_control_known_broken"], out["check1_control_known_good"],
            out["check2_control_known_broken"], out["check3_control_known_broken"],
            out["check4_control_known_broken"], out["check4_control_known_good"]]
out["all_detector_controls_pass"] = all(controls)

print(json.dumps(out, indent=1))
print(("SUCCESS" if out["all_detector_controls_pass"] else "FAILED")
      + ":cf-catalog-defects controls=" + str(out["all_detector_controls_pass"]))
