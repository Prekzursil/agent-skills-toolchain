#!/usr/bin/env python3
# REL-0001 probe2: live linter matrix + fix-hold recheck (2026-10-26, w4s12).
# Part A (matrix): crafted diffs per bump class exit exactly as the receipt
#   crafted_diff_exit_codes records {MAJOR:1, MINOR:1, PATCH:0}; pure-rename
#   same-version exits 0 silently.
# Part B (fix-hold recheck): the three RECORDED under-bump counterexamples
#   (receipt defects D1-D3, original candidate REFUTED - history preserved in
#   extensions.prior_candidate) MUST now be CAUGHT: linter exit 1 with
#   required_bump MAJOR (the max-rank fix), while the patch-only negative
#   control stays silent. If any counterexample masks again, the fix regressed
#   and this probe fails.
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LINTER = HERE / "release_bump_linter.py"
RULES = HERE / "release-bump-rules.json"
BUMP_RANK = {"NONE": 0, "PATCH": 1, "MINOR": 2, "MAJOR": 3}


def fail(msg):
    print("FAILED:REL-0001-probe2 " + str(msg))
    return 1


def write_tree(root, manifest, registry=None, blueprints=None, schema=None, impl=None):
    (root / "release").mkdir(parents=True)
    (root / "release/plugin-package.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8", newline="\n")
    if registry is not None:
        (root / "release/registry-entries.json").write_text(
            json.dumps(registry, indent=1), encoding="utf-8", newline="\n")
    if blueprints:
        (root / "release/blueprints").mkdir(parents=True)
        for bid, doc in blueprints.items():
            (root / "release/blueprints" / (bid + ".json")).write_text(
                json.dumps(doc, indent=1), encoding="utf-8", newline="\n")
    if schema is not None:
        (root / "release/councilspec.schema.json").write_text(
            json.dumps(schema, indent=1), encoding="utf-8", newline="\n")
    if impl:
        (root / "impl").mkdir(parents=True)
        for name, text in impl.items():
            p = root / "impl" / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")


def base_manifest(version):
    return {"name": "p2-plugin", "version": version, "permissions": ["read"],
            "hooks": {"PreToolUse": {"path": "hooks/a.py", "argv": ["python3"]}},
            "contract": {"mode": "strict"}}


def run_case(tmp, name, old_fn, new_fn):
    old, new = tmp / name / "old", tmp / name / "new"
    old_fn(old)
    new_fn(new)
    rpt = tmp / name / "report.json"
    p = subprocess.run([sys.executable, "-B", str(LINTER), "--rules", str(RULES),
                        "--old-tree", str(old), "--new-tree", str(new),
                        "--report", str(rpt)],
                       capture_output=True, text=True, timeout=300)
    rep = json.loads(rpt.read_text(encoding="utf-8")) if rpt.is_file() else {}
    return p.returncode, p.stderr.strip(), rep


def main():
    print("NAMED PROBE 2: LINTER MATRIX + RECORDED-REFUTATION RECHECK")
    print("UNIT=REL-0001")
    tmp = Path(tempfile.mkdtemp(prefix="rel0001-probe2-"))
    results = {}
    try:
        def o1(r):
            write_tree(r, base_manifest("1.2.3"))

        def n1(r):
            m = base_manifest("1.2.4")
            m.pop("contract")
            write_tree(r, m)
        rc, err, rep = run_case(tmp, "major-manifest-key-removal", o1, n1)
        results["MAJOR"] = rc
        print("CASE=manifest-key-removal-underbumped LINTER_EXIT=%d required=%s declared=%s"
              % (rc, rep.get("required_bump"), rep.get("declared_bump")))
        if rc != 1 or rep.get("required_bump") != "MAJOR" or "REL-BUMP-LOW" not in err:
            return fail("major-case:" + str(rc) + "/" + str(rep.get("required_bump")))

        def o2(r):
            write_tree(r, base_manifest("1.2.3"))

        def n2(r):
            m = base_manifest("1.2.4")
            m["telemetry"] = {"opt_in": False}
            write_tree(r, m)
        rc, err, rep = run_case(tmp, "minor-optional-key", o2, n2)
        results["MINOR"] = rc
        print("CASE=optional-key-underbumped LINTER_EXIT=%d required=%s declared=%s"
              % (rc, rep.get("required_bump"), rep.get("declared_bump")))
        if rc != 1 or rep.get("required_bump") != "MINOR":
            return fail("minor-case:" + str(rc) + "/" + str(rep.get("required_bump")))

        def o3(r):
            write_tree(r, base_manifest("1.2.3"))

        def n3(r):
            m = base_manifest("1.2.4")
            m["description"] = "docs refreshed"
            write_tree(r, m)
        rc, err, rep = run_case(tmp, "patch-metadata", o3, n3)
        results["PATCH"] = rc
        print("CASE=metadata-patch LINTER_EXIT=%d required=%s" % (rc, rep.get("required_bump")))
        if rc != 0:
            return fail("patch-case:" + str(rc))

        def o4(r):
            write_tree(r, base_manifest("1.2.3"))

        def n4(r):
            write_tree(r, base_manifest("1.2.3"))
        rc, err, rep = run_case(tmp, "pure-rename-none", o4, n4)
        print("CASE=pure-rename LINTER_EXIT=%d required=%s" % (rc, rep.get("required_bump")))
        if rc != 0 or rep.get("required_bump") != "NONE":
            return fail("none-case:" + str(rc) + "/" + str(rep.get("required_bump")))

        rec = json.loads((REPO / "command-center/receipts/REL-0001.json").read_text(encoding="utf-8"))
        recorded = rec.get("crafted_diff_exit_codes") or {}
        print("CRAFTED_DIFF_EXIT_CODES=" + json.dumps(results)
              + " receipt=" + json.dumps(recorded))
        if (results.get("MAJOR") != recorded.get("MAJOR")
                or results.get("MINOR") != recorded.get("MINOR")
                or results.get("PATCH") != recorded.get("PATCH")):
            return fail("crafted-exit-codes-drift:" + json.dumps(results))

        def ob1(r):
            write_tree(r, base_manifest("1.2.3"))

        def nb1(r):
            m = base_manifest("1.3.0")
            m["telemetry"] = {"opt_in": False}
            m["contract"] = {"mode": "lenient"}
            write_tree(r, m)
        rc, err, rep = run_case(tmp, "fixhold-mixed-plugin-D1", ob1, nb1)
        print("FIXHOLD=D1-mixed-plugin LINTER_EXIT=%d linter_required=%s oracle=MAJOR"
              % (rc, rep.get("required_bump")))
        if rc != 1 or rep.get("required_bump") != "MAJOR" or "REL-BUMP-LOW" not in err:
            return fail("fixhold-D1-still-masks:" + str(rc) + "/" + str(rep.get("required_bump")))

        def ob2(r):
            write_tree(r, base_manifest("1.2.3"), blueprints={
                "alpha": {"version": 1, "permissions": ["read"], "contract": {"run": "auto"}}})

        def nb2(r):
            write_tree(r, base_manifest("1.3.0"), blueprints={
                "alpha": {"version": 1, "permissions": ["read"], "contract": {"run": "manual"}},
                "beta": {"version": 1, "permissions": ["read"], "contract": {"run": "auto"}}})
        rc, err, rep = run_case(tmp, "fixhold-mixed-blueprint-D2", ob2, nb2)
        print("FIXHOLD=D2-mixed-blueprint LINTER_EXIT=%d linter_required=%s oracle=MAJOR"
              % (rc, rep.get("required_bump")))
        if rc != 1 or rep.get("required_bump") != "MAJOR" or "REL-BUMP-LOW" not in err:
            return fail("fixhold-D2-still-masks:" + str(rc) + "/" + str(rep.get("required_bump")))

        def ob3(r):
            write_tree(r, base_manifest("1.2.3"), schema={
                "properties": {"keep": {"type": "string"}}, "required": []})

        def nb3(r):
            write_tree(r, base_manifest("1.3.0"), schema={
                "properties": {"keep": {"type": "string"},
                               "extra": {"type": "object",
                                         "properties": {"must": {"type": "string"}},
                                         "required": ["must"]}},
                "required": []})
        rc, err, rep = run_case(tmp, "fixhold-nested-required-D3", ob3, nb3)
        print("FIXHOLD=D3-nested-required LINTER_EXIT=%d linter_required=%s oracle=MAJOR"
              % (rc, rep.get("required_bump")))
        if rc != 1 or rep.get("required_bump") != "MAJOR" or "REL-BUMP-LOW" not in err:
            return fail("fixhold-D3-still-masks:" + str(rc) + "/" + str(rep.get("required_bump")))

        # negative control: a patch-only diff must stay SILENT (no false positive)
        def ob4(r):
            write_tree(r, base_manifest("1.2.3"))

        def nb4(r):
            m = base_manifest("1.2.4")
            m["description"] = "docs refreshed"
            write_tree(r, m)
        rc, err, rep = run_case(tmp, "fixhold-patch-silent-control", ob4, nb4)
        print("FIXHOLD=patch-silent-control LINTER_EXIT=%d linter_required=%s" % (rc, rep.get("required_bump")))
        if rc != 0:
            return fail("fixhold-patch-false-positive:" + str(rc))

        print("CANDIDATE_VERDICT=FIXED-D1-D3-MAX-RANK recorded-counterexamples-now-caught")
        print("PROBE-2-COMPLETE:REL-0001")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def fail(msg):
    print("FAILED:REL-0001-probe2 " + str(msg))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
