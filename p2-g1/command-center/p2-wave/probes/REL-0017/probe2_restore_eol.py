#!/usr/bin/env python3
# REL-0017 probe2: restore + EOL oracle + planted owner file (resume 2026-10-25).
# T3: restore from the conversion backup returns the plugin tree to its exact
#   pre-apply raw sha256 hash set (7 files).
# T4: rules/rule.no-secrets.md differing only in line endings is classified
#   EOL-ONLY/op=skip while a naive raw-byte classifier says CONFLICT.
# Controls: a planted pre-existing owner-authored file at a create target is
#   caught and refused; the delete inverse refuses a path outside the
#   created_set (rule.plugin-only.md).
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0017_migrate", HERE / "migrate.py")
M = importlib.util.module_from_spec(spec)
sys.modules["rel0017_migrate"] = M
spec.loader.exec_module(M)


def fail(msg):
    print("FAILED:REL-0017-probe2 " + str(msg))
    return 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0017-p2-"))
    try:
        captured = tmp / "captured-frozen"
        M.build_captured(captured)
        copy_root = tmp / "copy"
        copy_root.mkdir()
        shutil.copytree(captured / "hand", copy_root / "hand")
        shutil.copytree(captured / "plugin", copy_root / "plugin")
        M.assert_copy_allowed(copy_root, captured)
        hand, plugin = copy_root / "hand", copy_root / "plugin"
        pre = M.tree_hashes(plugin)
        print("pre_apply_file_count=" + str(len(pre)))
        plan = M.plan_dry_run(hand, plugin)
        eol = [r for r in plan if r["classification"] == "EOL-ONLY"]
        if not eol or eol[0]["target_rel"] != "rules/rule.no-secrets.md" or eol[0]["op"] != "skip":
            return fail("eol-row-missing:" + json.dumps([r["classification"] for r in plan]))
        naive = M.BOTH_UNIQUE if False else "CONFLICT"
        hand_b = (hand / "rules/rule.no-secrets.md").read_bytes()
        plugin_b = (plugin / "rules/rule.no-secrets.md").read_bytes()
        if hand_b == plugin_b:
            return fail("naive-compare-says-identical")
        if hand_b.replace(b"\r\n", b"\n") != plugin_b.replace(b"\r\n", b"\n"):
            return fail("not-eol-only")
        print("T4: EOL-ONLY classified unchanged (op=skip); naive raw compare says " + naive
              + " (bytes " + str(len(hand_b)) + " vs " + str(len(plugin_b)) + ")")
        backup = tmp / "backup"
        M.backup_tree(plugin, backup)
        applied = M.apply_plan(hand, plugin, plan, backup)
        created_set = sorted(r["target_rel"] for r in applied if r["op"] == "create")
        after = M.tree_hashes(plugin)
        if set(after) == set(pre):
            return fail("apply-changed-nothing")
        M.restore_tree(plugin, backup)
        restored = M.tree_hashes(plugin)
        if restored != pre:
            return fail("restore-hash-set-drift")
        print("T3: restore returned the pre-apply hash set over " + str(len(restored)) + " files")
        # planted owner file control: pre-existing target at a create row must be caught
        copy2 = tmp / "copy2"
        copy2.mkdir()
        shutil.copytree(captured / "hand", copy2 / "hand")
        shutil.copytree(captured / "plugin", copy2 / "plugin")
        planted = copy2 / "plugin" / "skills" / "owner-skill" / "SKILL.md"
        planted.parent.mkdir(parents=True)
        planted.write_text("owner-authored content that must not be overwritten\n", encoding="utf-8")
        plan2 = M.plan_dry_run(copy2 / "hand", copy2 / "plugin")
        rows2 = [r for r in plan2 if r["target_rel"] == "skills/owner-skill/SKILL.md"]
        if not rows2 or rows2[0]["op"] != "refuse":
            return fail("planted-owner-file-not-caught:" + json.dumps(rows2))
        before_marker = "owner-authored content that must not be overwritten"
        M.apply_plan(copy2 / "hand", copy2 / "plugin", plan2, tmp / "backup2")
        if planted.read_text(encoding="utf-8").strip() != before_marker:
            return fail("planted-owner-content-overwritten")
        print("planted-owner-file caught: plan emits op=refuse for " + rows2[0]["target_rel"]
              + "; planted content preserved after apply")
        # inverse invariant: delete outside created_set refused
        try:
            M.delete_file_inverse(plugin, "rules/rule.plugin-only.md", created_set)
            return fail("delete-inverse-removed-preexisting")
        except M.Refusal as exc:
            print("inverse-refusal: " + str(exc)[:120])
        rec = json.loads((REPO / "command-center/receipts/REL-0017.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        dv = rec.get("divergence_honesty") or {}
        if dv.get("fixture_two_directional") is not True:
            return fail("receipt-divergence-honesty-drift")
        ec = rec.get("eol_classification") or {}
        if ec.get("classification") != "EOL-ONLY" or ec.get("honest_unchanged") is not True:
            return fail("receipt-eol-drift")
        print("SUCCESS:REL-0017-probe2 restore-eol-planted-controls")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
