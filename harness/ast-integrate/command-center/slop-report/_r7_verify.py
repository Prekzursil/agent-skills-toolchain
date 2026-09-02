"""ROUND 7 verification: did the fix actually change what the gate measures?

The defect (`_r7_defect.out.json`) was that `_r6_transcript.py` bound its repo root to an
absolute literal, so a copy of it inside a fresh clone re-measured the SOURCE worktree and
wrote its receipt there. The fix resolves the root from `__file__`.

BOTH STATES, IN ONE RUN, IN THE SAME CLONE -- this is the whole point. A probe that only
ran the fixed version could not tell "the fix works" from "the clone happens to look like
the source". So each check below is run twice: once with the OLD gate (the committed blob
at HEAD, which still carries the literal) and once with the NEW gate (the working-tree
file). The OLD one must FAIL the check and the NEW one must PASS it. If both pass, the
check is inert and proves only that python ran.

  V1  REGRESSION -- in THIS tree the fixed gate must reach the same verdict, the same
      claim count and the same controls as round 6's committed receipt. A "fix" that
      changed the answer here would have broken the instrument, not repaired it.
  V2  CLONE-VALIDITY -- run in a clone, which tree does each version report?
      Discriminator is the DOC COUNT, not HEAD: the source carries an untracked SLOP doc
      that cannot exist in a clone, so the counts differ by construction. HEAD equality is
      unusable here and is recorded as refuted -- siblings commit under this lane mid-run.
  V3  NO WRITE-BACK -- does running the clone's copy mutate a file inside the SOURCE
      worktree? Mechanically independent of V2 and of HEAD.
  V4  COMMITTED MODE -- the new `--committed` question: do the numbers in the COMMITTED
      docs agree with the COMMITTED receipts? This is the verdict a clone would reach.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = (
    subprocess.run(
        ["git", "-C", HERE, "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    or ""
).replace("\\", "/")
SR = "command-center/slop-report"
GATE = "_r6_transcript.py"
OUT = os.path.join(REPO, SR, "_r7_verify.out.json")
SRC_RECEIPT = os.path.join(REPO, SR, "_r6_transcript.out.json")


def run(cmd, cwd=REPO):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def payload(stdout):
    try:
        return json.loads(stdout[: stdout.rindex("}") + 1])
    except (ValueError, AttributeError):
        return {}


def hardcoded(text) -> bool:
    """Does this module bind REPO/ROOT to an absolute string literal?"""
    try:
        tree = ast.parse(text)
    except (SyntaxError, TypeError):
        return False
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in ("REPO", "ROOT", "REPO_ROOT"):
                v = node.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    if ":" in v.value[:3] or v.value.startswith("/"):
                        return True
    return False


def prefix_rev():
    """Newest rev whose committed gate STILL carries the literal.

    The clone must be pinned here, not at HEAD. Once the fix is committed, a clone at HEAD
    would carry the FIXED gate, both trials would pass, and this probe would silently stop
    being a both-states check -- it would prove only that python ran.
    """
    rel = f"{SR}/{GATE}"
    for rev in run(["git", "log", "--format=%H", "--", rel]).stdout.split():
        blob = run(["git", "show", f"{rev}:{rel}"])
        if blob.returncode == 0 and hardcoded(blob.stdout):
            return rev
    return None


def main() -> int:
    res = {"v7_repo_root_resolved": REPO}
    res["v7_head_at_run"] = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    pinned = prefix_rev()
    res["v7_pinned_prefix_rev"] = pinned
    res["v7_pin_is_hardcoded"] = bool(
        pinned and hardcoded(run(["git", "show", f"{pinned}:{SR}/{GATE}"]).stdout)
    )

    # ---------------- V1 : regression in THIS tree ----------------
    r = run(["python", os.path.join(REPO, SR, GATE)])
    now = payload(r.stdout)
    # Round 6's receipt read at the PRE-FIX rev, not at HEAD: once this round commits, HEAD
    # carries MY receipt and the regression check would be comparing the fix against itself.
    before = run(["git", "show", f"{pinned}:{SR}/_r6_transcript.out.json"])
    r6 = json.loads(before.stdout) if before.returncode == 0 else {}
    res["v7_V1_regression"] = {
        "round6_committed": {
            k: r6.get(k) for k in ("verdict", "claims_found", "docs_scanned")
        },
        "round7_now": {
            k: now.get(k) for k in ("verdict", "claims_found", "docs_scanned")
        },
        "round6_controls_pass": (r6.get("controls") or {}).get("PASS"),
        "round7_controls_pass": (now.get("controls") or {}).get("PASS"),
        "verdict_unchanged": now.get("verdict") == r6.get("verdict"),
        "claims_unchanged": now.get("claims_found") == r6.get("claims_found"),
        "controls_still_pass": bool((now.get("controls") or {}).get("PASS")),
        "rc": r.returncode,
    }

    # ---------------- V2 / V3 : both versions, one fresh clone ----------------
    tmp = tempfile.mkdtemp(prefix="r7_verify_")
    clone = os.path.join(tmp, "c").replace("\\", "/")
    cl = run(["git", "clone", "--no-hardlinks", "--quiet", REPO, clone], cwd=REPO)
    both = {"clone_rc": cl.returncode, "clone_stderr": cl.stderr.strip()[:300]}
    if cl.returncode == 0:
        run(["git", "checkout", "--quiet", pinned], cwd=clone)
        both["clone_head"] = run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=clone
        ).stdout.strip()
        gate_path = os.path.join(clone, SR, GATE)

        def count(root):
            return len(
                [
                    n
                    for n in os.listdir(os.path.join(root, SR))
                    if n.startswith("SLOP-") and n.endswith(".md")
                ]
            )

        both["clone_docs_on_disk"] = count(clone)
        both["source_docs_on_disk"] = count(REPO)
        both["counts_differ_so_check_can_discriminate"] = (
            both["clone_docs_on_disk"] != both["source_docs_on_disk"]
        )

        def trial(label):
            snap = (
                open(SRC_RECEIPT, "rb").read() if os.path.exists(SRC_RECEIPT) else b""
            )
            out = run(["python", gate_path], cwd=clone)
            post = (
                open(SRC_RECEIPT, "rb").read() if os.path.exists(SRC_RECEIPT) else b""
            )
            wrote = snap != post
            if wrote and snap:  # never leave the source tree mutated by a probe
                with open(SRC_RECEIPT, "wb") as fh:
                    fh.write(snap)
            p = payload(out.stdout)
            return {
                "label": label,
                "reported_docs_scanned": p.get("docs_scanned"),
                "reported_repo_root": p.get("repo_root"),
                "measured_the_clone": p.get("docs_scanned")
                == both["clone_docs_on_disk"],
                "measured_the_source": p.get("docs_scanned")
                == both["source_docs_on_disk"],
                "wrote_into_source_worktree": wrote,
                "rc": out.returncode,
            }

        # OLD = the committed blob at HEAD, which still carries the absolute literal.
        both["OLD_committed_gate"] = trial("old")
        # NEW = this round's working-tree file, copied in.
        shutil.copyfile(os.path.join(REPO, SR, GATE), gate_path)
        both["NEW_fixed_gate"] = trial("new")

        old, new = both["OLD_committed_gate"], both["NEW_fixed_gate"]
        both["V2_fix_changed_which_tree_is_measured"] = bool(
            old["measured_the_source"] and new["measured_the_clone"]
        )
        both["V3_fix_stopped_the_write_back"] = bool(
            old["wrote_into_source_worktree"] and not new["wrote_into_source_worktree"]
        )
        both["both_states_distinguish"] = bool(
            both["V2_fix_changed_which_tree_is_measured"]
            and both["V3_fix_stopped_the_write_back"]
        )
        both["S1_head_equality_REFUTED_moving_head"] = (
            "recorded, never read: HEAD moves under this lane mid-run, so equality "
            "against a start-of-run HEAD decides nothing. Doc count is the discriminator."
        )
    res["v7_V2V3_clone_both_states"] = both
    shutil.rmtree(tmp, ignore_errors=True)

    # ---------------- V4 : the committed-mode question ----------------
    c = run(["python", os.path.join(REPO, SR, GATE), "--committed"])
    cp = payload(c.stdout)
    res["v7_V4_committed_mode"] = {
        "mode": cp.get("mode"),
        "verdict": cp.get("verdict"),
        "docs_scanned": cp.get("docs_scanned"),
        "receipts_indexed": cp.get("receipts_indexed"),
        "claims_found": cp.get("claims_found"),
        "controls_pass": (cp.get("controls") or {}).get("PASS"),
        "violation_count": len(cp.get("violations") or []),
        "violations": (cp.get("violations") or [])[:8],
        "rc": c.returncode,
        "wrote_no_receipt": cp.get("mode") == "committed",
    }

    v1 = res["v7_V1_regression"]
    res["v7_verdict"] = (
        "FIX-PROVEN"
        if (
            v1["verdict_unchanged"]
            and v1["claims_unchanged"]
            and v1["controls_still_pass"]
            and both.get("both_states_distinguish")
        )
        else "NOT-PROVEN"
    )
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()
    ok = res["v7_verdict"] == "FIX-PROVEN"
    print("SUCCESS:r7-verify" if ok else "FAILED:r7-verify see-v7_verdict")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
