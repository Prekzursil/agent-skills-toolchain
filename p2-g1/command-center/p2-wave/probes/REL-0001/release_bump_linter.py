#!/usr/bin/env python3
# REL-0001 release-bump linter (FIXED 2026-10-26, wave-4 shard-12 resume).
# argv: --rules <rules.json> --old-tree <dir> --new-tree <dir> [--report <json>]
#   classification collects EVERY rule finding and derives the required bump as
#   the HIGHEST-RANK matched bump (max-wins) - fixing the recorded masking
#   defect (receipt defects D1-D3, original candidate REFUTED; history kept
#   verbatim in the receipt's extensions.prior_candidate): a diff that BOTH
#   adds an optional key (MINOR) and widens a permission (MAJOR) must require
#   MAJOR, never the later/lower matched rule.
#   required bump = max-rank matched bump; declared bump derived from
#   previous -> candidate "version" in release/plugin-package.json.
#   exit 1 + stderr "REL-BUMP-LOW: required=<B> declared=<B> previous=<v>
#   candidate=<v>" when declared < required; exit 0 otherwise; stdout empty.
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BUMP_RANK = {"NONE": 0, "PATCH": 1, "MINOR": 2, "MAJOR": 3}
META_KEYS = {"description", "keywords", "metadata", "homepage", "changelog",
             "readme", "displayName"}
MANIFEST_REL = "release/plugin-package.json"


def load_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def bump_from(old, new):
    o = [int(x) for x in old.split(".")]
    n = [int(x) for x in new.split(".")]
    if n[0] != o[0]:
        return "MAJOR"
    if n[1] != o[1]:
        return "MINOR"
    if n[2] != o[2]:
        return "PATCH"
    return "NONE"


def diff_plugin(old, new):
    ok = set(old) - META_KEYS - {"version"}
    nk = set(new) - META_KEYS - {"version"}
    for k in sorted(ok - nk):
        yield ("PLUGIN-KEY-REMOVED", "MAJOR", "public manifest key removed: " + k)
    op = set(old.get("permissions") or [])
    np_ = set(new.get("permissions") or [])
    if np_ - op:
        yield ("PLUGIN-PERMISSION-WIDENED", "MAJOR",
               "declared permissions widened: " + ",".join(sorted(np_ - op)))
    oh = old.get("hooks") or {}
    nh = new.get("hooks") or {}
    for h in sorted(set(oh) & set(nh)):
        if oh[h] != nh[h]:
            yield ("PLUGIN-HOOK-SIGNATURE-CHANGED", "MAJOR",
                   "existing hook signature changed: " + h)
    changed_values = [k for k in sorted(ok & nk)
                      if k not in {"permissions", "hooks"} and old[k] != new[k]]
    for k in changed_values:
        yield ("PLUGIN-CONTRACT-VALUE-CHANGED", "MAJOR",
               "existing public contract value changed: " + k)
    for k in sorted(nk - ok):
        yield ("PLUGIN-OPTIONAL-KEY-ADDED", "MINOR",
               "non-metadata optional public key added: " + k)
    # w4s12 fix (part of the D1-D3 max-rank repair): this rule previously
    # fired on ANY structurally-unchanged diff - including ZERO change - so a
    # byte-identical rename classified PATCH once max-rank derivation stopped
    # masking it. Fire only when manifest metadata (META_KEYS) really changed.
    om_meta = {k: old[k] for k in sorted(set(old) & META_KEYS)}
    nm_meta = {k: new[k] for k in sorted(set(new) & META_KEYS)}
    meta_changed = om_meta != nm_meta
    if meta_changed and (not (ok - nk)) and (not (nk - ok)) and op == np_ \
            and oh == nh and not changed_values:
        touched = ",".join(sorted(
            k for k in set(om_meta) | set(nm_meta)
            if om_meta.get(k) != nm_meta.get(k)))
        yield ("PLUGIN-METADATA-OR-IMPLEMENTATION-CHANGED", "PATCH",
               "manifest metadata changed (structural contract unchanged): " + touched)


def diff_registry(old, new):
    o = {e.get("coordinate"): e for e in old}
    n = {e.get("coordinate"): e for e in new}
    for c in sorted(set(o) - set(n)):
        yield ("REGISTRY-ENTRY-REMOVED-OR-REWRITTEN", "MAJOR",
               "registry coordinate removed: " + str(c))
    for c in sorted(set(o) & set(n)):
        widened = set(n[c].get("permissions") or []) - set(o[c].get("permissions") or [])
        content_changed = (o[c].get("content") or "") != (n[c].get("content") or "")
        if widened:
            yield ("REGISTRY-PERMISSION-WIDENED", "MAJOR",
                   "registry permissions widened: " + str(c))
        elif content_changed:
            yield ("REGISTRY-ENTRY-REMOVED-OR-REWRITTEN", "MAJOR",
                   "immutable content rewritten: " + str(c))
    for c in sorted(set(n) - set(o)):
        yield ("REGISTRY-ENTRY-ADDED", "MINOR",
               "registry coordinate appended: " + str(c))
    for c in sorted(set(o) & set(n)):
        widened = set(n[c].get("permissions") or []) - set(o[c].get("permissions") or [])
        content_changed = (o[c].get("content") or "") != (n[c].get("content") or "")
        if o[c] != n[c] and not widened and not content_changed:
            yield ("REGISTRY-METADATA-CHANGED", "PATCH",
                   "registry descriptive metadata changed: " + str(c))


def diff_blueprints(old_dir, new_dir):
    def ids(d):
        return {p.stem: p for p in sorted(d.glob("*.json"))} if d.is_dir() else {}
    o, n = ids(old_dir), ids(new_dir)
    for b in sorted(set(o) - set(n)):
        yield ("BLUEPRINT-ID-RETIRED", "MAJOR", "exported blueprint id retired: " + b)
    for b in sorted(set(o) & set(n)):
        od, nd = load_json(o[b]), load_json(n[b])
        if set(nd.get("permissions") or []) - set(od.get("permissions") or []):
            yield ("BLUEPRINT-PERMISSION-WIDENED", "MAJOR",
                   "blueprint permission widened: " + b)
        if (od.get("hook") or {}) != (nd.get("hook") or {}):
            yield ("BLUEPRINT-HOOK-SIGNATURE-CHANGED", "MAJOR",
                   "blueprint hook signature changed: " + b)
        if (od.get("contract") or {}) != (nd.get("contract") or {}):
            yield ("BLUEPRINT-CONTRACT-CHANGED", "MAJOR",
                   "exported execution contract changed: " + b)
        elif od != nd:
            yield ("BLUEPRINT-METADATA-CHANGED", "PATCH",
                   "blueprint descriptive metadata changed: " + b)
    for b in sorted(set(n) - set(o)):
        yield ("BLUEPRINT-ID-ADDED", "MINOR", "blueprint id added: " + b)


def _nested_required(schema):
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
                   "field added inside schema: " + f)


def manifest(man):
    return json.loads((man / MANIFEST_REL).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--old-tree", required=True)
    ap.add_argument("--new-tree", required=True)
    ap.add_argument("--report")
    a = ap.parse_args()
    rules = load_json(Path(a.rules))["rules"]
    old_t, new_t = Path(a.old_tree), Path(a.new_tree)
    findings = []
    for rule in rules:
        rid, bump = rule["id"], rule["bump"]
        matches = []
        def maybe(rel):
            q = old_t / rel
            r = new_t / rel
            try:
                return load_json(q), load_json(r)
            except (OSError, json.JSONDecodeError):
                return None, None

        if rid.startswith("PLUGIN-"):
            om, nm = maybe("release/plugin-package.json")
            if om is None:
                om, nm = {}, {}
            matches = [m for m in diff_plugin(om, nm) if m[0] == rid]
        elif rid.startswith("REGISTRY-"):
            od, nd = maybe("release/registry-entries.json")
            if od is not None:
                matches = [m for m in diff_registry(od, nd) if m[0] == rid]
        elif rid.startswith("BLUEPRINT-"):
            matches = [m for m in diff_blueprints(old_t / "release/blueprints",
                                                  new_t / "release/blueprints")
                       if m[0] == rid]
        elif rid.startswith("SCHEMA-"):
            od, nd = maybe("release/councilspec.schema.json")
            if od is not None:
                matches = [m for m in diff_schema(od, nd) if m[0] == rid]
        elif rid == "PURE-BYTE-IDENTICAL-RENAME":
            try:
                same = (old_t / MANIFEST_REL).read_bytes() == (new_t / MANIFEST_REL).read_bytes()
            except OSError:
                same = False
            if same:
                matches = [("PURE-BYTE-IDENTICAL-RENAME", "NONE", "byte-identical content")]
        elif rid == "RELEVANT-IMPLEMENTATION-CHANGE":
            impl = new_t / "impl"
            if impl.is_dir():
                for p in sorted(impl.rglob("*")):
                    if not p.is_file():
                        continue
                    q = old_t / p.relative_to(new_t)
                    if (not q.is_file()) or q.read_bytes() != p.read_bytes():
                        matches = [("RELEVANT-IMPLEMENTATION-CHANGE", "PATCH",
                                    "implementation bytes changed: "
                                    + p.relative_to(new_t).as_posix())]
                        break
        for m in matches:
            findings.append({"bump": bump, "detail": m[2], "path": "release/",
                             "rule_id": rid})
    # max-rank classification (fix for the recorded masking defect, D1-D3):
    # the required bump is the HIGHEST bump any single rule matched, so a
    # mixed diff can never be masked down by a later, lower rule.
    required_bump = max(findings, key=lambda f: BUMP_RANK[f["bump"]])["bump"] if findings else "NONE"
    om, nm = manifest(old_t), manifest(new_t)
    prev_v, cand_v = str(om.get("version")), str(nm.get("version"))
    declared = bump_from(prev_v, cand_v)
    compliant = BUMP_RANK[declared] >= BUMP_RANK[required_bump]
    report = {
        "schema_version": 1,
        "unit_id": "REL-0001",
        "compliant": compliant,
        "declared_bump": declared,
        "declared_version": cand_v,
        "declared_version_source": "candidate-plugin-manifest",
        "findings": findings,
        "previous_version": prev_v,
        "previous_version_source": "previous-plugin-manifest",
        "required_bump": required_bump,
    }
    if a.report:
        rp = Path(a.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8",
                      newline="\n")
    if not compliant:
        sys.stderr.write("REL-BUMP-LOW: required=%s declared=%s previous=%s candidate=%s\n"
                         % (required_bump, declared, prev_v, cand_v))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
