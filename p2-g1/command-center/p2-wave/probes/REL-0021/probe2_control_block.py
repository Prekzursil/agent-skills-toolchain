#!/usr/bin/env python3
# REL-0021 probe2: two-directional BLOCK + owner-destroy catch (resume 2026-10-25).
# Control fixture (receipt four_way: identical=3, package-only=1,
# deployed-only=1, divergent-both-ways=1) must produce verdict=BLOCK - the
# two-directional case where reconciling in either direction destroys work.
# The reviewer destroy catch: an overwrite attempt on the deployed-only
# owner-authored file must be refused, never silently synced.
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
spec = importlib.util.spec_from_file_location("rel0021_parity", HERE / "parity.py")
P = importlib.util.module_from_spec(spec)
sys.modules["rel0021_parity"] = P
spec.loader.exec_module(P)


def fail(msg):
    print("FAILED:REL-0021-probe2 " + str(msg))
    return 1


def main():
    sys.path.insert(0, str(HERE))
    import probe1_recipe_healthy as PR
    tmp = Path(tempfile.mkdtemp(prefix="rel0021-p2-"))
    try:
        repo, pkg, dep = PR.build_case(tmp, "control")
        # third identical trio: commit third.txt to git, mirror in pkg + deployed
        third = b"third shipped file" + chr(10).encode()
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, timeout=120)
        (repo / "shipped" / "third.txt").write_bytes(third)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], capture_output=True, timeout=120)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "third"],
                       capture_output=True, timeout=120, check=True)
        with zipfile_append(pkg) as z:
            z.writestr("shipped/third.txt", third)
        (dep / "shipped" / "third.txt").write_bytes(third)
        # package-only: a file only the package carries
        with zipfile_append(pkg) as z:
            z.writestr("shipped/pkg-only.txt", "package-only bytes\n")
        # deployed-only: an owner-authored file only the deployment carries
        owner = dep / "shipped" / "owner-notes.txt"
        owner.write_text("owner-authored notes; do not delete\n", encoding="utf-8", newline="\n")
        # divergent-both-ways: known.txt content differs in the deployment
        (dep / "shipped" / "known.txt").write_bytes(b"deployed unique divergence\n")
        rep = P.three_way_report(repo, pkg, dep,
                                 ["shipped/known.txt", "shipped/second.txt", "README.md",
                                  "shipped/third.txt",
                                  "shipped/pkg-only.txt", "shipped/owner-notes.txt"])
        print("control four_way=" + json.dumps(rep["four_way"]) + " verdict=" + rep["verdict"])
        want = {"identical": 3, "package-only": 1, "deployed-only": 1,
                "divergent-both-ways": 1, "mixed-missing": 0}
        if rep["four_way"] != want:
            return fail("four-way-counts:" + json.dumps(rep["four_way"]))
        if rep["verdict"] != "BLOCK":
            return fail("verdict-not-block")
        for f in rep["files"]:
            if f["class"] in ("deployed-only", "divergent-both-ways"):
                if f["sync_proposal"] is not None:
                    return fail("sync-proposal-for-unique-content:" + f["path"])
        rec = json.loads((REPO / "command-center/receipts/REL-0021.json").read_text(encoding="utf-8"))
        st = str(rec.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return fail("self-declared:" + st)
        if rec.get("control_verdict") != "BLOCK" or rec.get("healthy_verdict") != "PROMOTE":
            return fail("receipt-verdicts-drift")
        fw = rec.get("four_way") or {}
        if (fw.get("identical"), fw.get("package-only"), fw.get("deployed-only"),
                fw.get("divergent-both-ways")) != (3, 1, 1, 1):
            return fail("receipt-four-way-drift")
        # reviewer destroy catch: overwrite of the deployed-only owner file refused
        try:
            P.attempt_owner_overwrite(dep, "shipped/owner-notes.txt",
                                      b"package bytes that would destroy owner work\n")
            return fail("owner-destroy-not-caught")
        except PermissionError as exc:
            print("owner-destroy caught: " + str(exc)[:110])
        if not owner.is_file() or not owner.read_text(encoding="utf-8").startswith("owner-authored"):
            return fail("owner-content-damaged")
        print("SUCCESS:REL-0021-probe2 control-block-and-owner-destroy")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def zipfile_append(pkg):
    import zipfile
    return zipfile.ZipFile(pkg, "a")


if __name__ == "__main__":
    raise SystemExit(main())
