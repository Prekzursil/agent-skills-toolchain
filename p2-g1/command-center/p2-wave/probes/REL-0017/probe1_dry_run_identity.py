#!/usr/bin/env python3
# REL-0017 probe1: dry-run identity (resume 2026-10-25).
# T1: the printed dry-run plan must equal the independently measured applied
#   delta (diff empty; create count matches recorded applied 5: 4 creates +
#   1 overwrite). T2: SOURCE-ONLY files land with their raw sha intact.
# Negative control: assert_copy_allowed must refuse the live profile and the
#   frozen captured original.
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
    print("FAILED:REL-0017-probe1 " + str(msg))
    return 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel0017-p1-"))
    copy_root = tmp / "copy"
    try:
        captured = tmp / "captured-frozen"
        M.build_captured(captured)
        copy_root.mkdir()
        shutil.copytree(captured / "hand", copy_root / "hand")
        shutil.copytree(captured / "plugin", copy_root / "plugin")
        M.assert_copy_allowed(copy_root, captured)
        # negative control: live profile refused
        try:
            M.assert_copy_allowed(Path.home() / ".claude", captured)
            return fail("live-profile-not-refused")
        except M.Refusal:
            pass
        # negative control: frozen captured original refused
        try:
            M.assert_copy_allowed(captured, captured)
            return fail("captured-original-not-refused")
        except M.Refusal:
            pass
        print("isolation: copy_root=" + str(copy_root))
        hand, plugin = copy_root / "hand", copy_root / "plugin"
        before = M.tree_hashes(plugin)
        plan = M.plan_dry_run(hand, plugin)
        creates = [r for r in plan if r["op"] == "create"]
        refuses = [r for r in plan if r["op"] == "refuse"]
        skips = [r for r in plan if r["op"] == "skip"]
        overwrites = [r for r in plan if r["op"] == "overwrite"]
        print("plan: create=%d skip=%d refuse=%d overwrite=%d"
              % (len(creates), len(skips), len(refuses), len(overwrites)))
        backup = tmp / "backup"
        M.backup_tree(plugin, backup)
        applied = M.apply_plan(hand, plugin, plan, backup)
        after = M.tree_hashes(plugin)
        predicted = {r["target_rel"]: r["content_sha256"] for r in plan if r["op"] in ("create", "overwrite")}
        measured = {rel: h for rel, h in after.items() if before.get(rel) != h}
        diff = {k: (predicted.get(k), measured.get(k)) for k in set(predicted) | set(measured)
                if predicted.get(k) != measured.get(k)}
        print("plan_vs_applied_diff=" + json.dumps(diff) + " writes=%d" % len(applied))
        if diff:
            return fail("plan-vs-applied-not-identical")
        if len(applied) != 5:
            return fail("applied-write-count:" + str(len(applied)))
        for r in creates:
            live = plugin / r["target_rel"]
            if M.sha_bytes(live.read_bytes()) != r["content_sha256"]:
                return fail("source-unique-hash-drift:" + r["target_rel"])
        rec = json.loads((REPO / "command-center/receipts/REL-0017.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if "SUCCESS:REL-0017" not in json.dumps(rec):
            return fail("sentinel-absent")
        iso = rec.get("isolation") or {}
        if iso.get("ran_against_copy") is not True or iso.get("live_tree_untouched") is not True:
            return fail("receipt-isolation-drift")
        print("SUCCESS:REL-0017-probe1 dry-run-identity")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
