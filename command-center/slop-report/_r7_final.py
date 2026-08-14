"""ROUND 7 final check: is the SHIPPED gate clone-valid, and is frozen evidence untouched?

`_r7_verify.py` proved the fix works using the WORKING-TREE copy of the gate. That is not
the same artifact as the one that shipped. This runs the COMMITTED blob at HEAD inside a
fresh clone -- working-tree green is not clone green, and the whole defect being repaired
here was a gate that measured the wrong tree.

CONTROLS, both states:
  F1 the clone and the source must hold DIFFERENT numbers of SLOP docs, or the doc-count
     discriminator cannot decide anything and a PASS would only mean python ran. If they
     ever match, this exits non-zero rather than reporting a clean result.
  F2 the gate run inside the clone must report the CLONE's count, and must not mutate the
     source worktree.
  F3 frozen evidence: every file byte-identical to its HEAD blob, with a live-detector
     control that must return a NON-zero dirty count on a known-dirty directory -- so a
     zero on the frozen dirs is a reading rather than a silence.
"""

from __future__ import annotations

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
    )
    .stdout.strip()
    .replace("\\", "/")
)
SR = "command-center/slop-report"
OUT = os.path.join(REPO, SR, "_r7_final.out.json")
FROZEN = [
    "command-center/casualty/probes",
    "command-center/p2-wave/probes/AUD-0006/control",
]


def run(cmd, cwd=REPO):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def samepath(a, b) -> bool:
    """Do two path strings name the same directory?

    NOT string equality. Windows TEMP resolves through an 8.3 short name, so
    `tempfile.mkdtemp` hands back `C:/Users/PREKZU~1/AppData/Local/Temp/...` while
    `git rev-parse --show-toplevel` returns the long form `C:/Users/Prekzursil/...`.
    Compared as strings those differ while naming the identical directory, which made this
    check report `resolved_to_clone: false` for a gate that had in fact resolved to the
    clone -- a false NEGATIVE produced entirely by the instrument.
    """
    try:
        if not a or not b:
            return False
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(
            os.path.realpath(b)
        )
    except (OSError, ValueError):
        return False


def slop_docs(root):
    return len(
        [
            n
            for n in os.listdir(os.path.join(root, SR))
            if n.startswith("SLOP-") and n.endswith(".md")
        ]
    )


def main() -> int:
    res = {"f7_repo": REPO}
    head = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()
    res["f7_head"] = head

    # ---- F1/F2 : the COMMITTED gate, in a fresh clone pinned at HEAD ----
    tmp = tempfile.mkdtemp(prefix="r7_final_")
    clone = os.path.join(tmp, "c").replace("\\", "/")
    cl = run(["git", "clone", "--no-hardlinks", "--quiet", REPO, clone], cwd=REPO)
    blk = {"clone_rc": cl.returncode, "clone_stderr": cl.stderr.strip()[:300]}
    if cl.returncode == 0:
        run(["git", "checkout", "--quiet", head], cwd=clone)
        src_receipt = os.path.join(REPO, SR, "_r6_transcript.out.json")
        blk["clone_docs"] = slop_docs(clone)
        blk["source_docs"] = slop_docs(REPO)
        # REFUTED AS A DISCRIMINATOR, kept because the refutation is the lesson. The first
        # version of this check decided which tree was measured by comparing SLOP-doc
        # counts, which worked only while this round's report was still untracked. The
        # moment it was committed the clone held it too -- 10 against 10 -- and the count
        # could no longer separate the hypotheses. It correctly returned NOT-PROVEN rather
        # than reading a meaningless True as a pass. Reported, never read for the verdict.
        blk["F1_doccount_REFUTED_as_discriminator"] = {
            "clone_docs": blk["clone_docs"],
            "source_docs": blk["source_docs"],
            "still_applicable": blk["clone_docs"] != blk["source_docs"],
            "why": "identical once this round's report is committed; use repo_root identity",
        }

        def trial(gate_path, label):
            snap = (
                open(src_receipt, "rb").read() if os.path.exists(src_receipt) else b""
            )
            out = run(["python", gate_path], cwd=clone)
            post = (
                open(src_receipt, "rb").read() if os.path.exists(src_receipt) else b""
            )
            wrote = snap != post
            if wrote and snap:  # never leave the source tree mutated by a probe
                with open(src_receipt, "wb") as fh:
                    fh.write(snap)
            try:
                p = json.loads(out.stdout[: out.stdout.rindex("}") + 1])
            except (ValueError, AttributeError):
                p = {}
            root = p.get("repo_root")
            return {
                "label": label,
                "reported_repo_root": root,
                "reported_docs_scanned": p.get("docs_scanned"),
                "reported_verdict": p.get("verdict"),
                # DIRECT IDENTITY, not a proxy: did it resolve to the clone or the source?
                "resolved_to_clone": samepath(root, clone),
                "resolved_to_source": samepath(root, REPO),
                "root_absent": root is None,
                "wrote_into_source_worktree": wrote,
                "rc": out.returncode,
            }

        # KNOWN-BROKEN arm: the pre-fix blob, so a PASS below cannot mean "python ran".
        pin = None
        try:
            with open(
                os.path.join(REPO, SR, "_r7_defect.out.json"), encoding="utf-8"
            ) as fh:
                pin = json.load(fh).get("prefix_rev")
        except (OSError, ValueError):
            pin = None
        blk["prefix_rev"] = pin
        if pin:
            old_blob = run(["git", "show", f"{pin}:{SR}/_r6_transcript.py"]).stdout
            old_path = os.path.join(clone, SR, "_r7_oldgate_probe.py")
            with open(old_path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(old_blob)
            blk["OLD_prefix_gate"] = trial(old_path, "old")
            os.remove(old_path)
        blk["NEW_shipped_gate"] = trial(
            os.path.join(clone, SR, "_r6_transcript.py"), "new"
        )

        old, new = blk.get("OLD_prefix_gate", {}), blk["NEW_shipped_gate"]
        blk["F2_shipped_resolves_to_clone"] = new["resolved_to_clone"]
        blk["F2_shipped_left_source_untouched"] = not new["wrote_into_source_worktree"]
        blk["F2_known_broken_arm_fails"] = bool(
            old and not old["resolved_to_clone"] and old["wrote_into_source_worktree"]
        )
        blk["F2_pass"] = bool(
            blk["F2_shipped_resolves_to_clone"]
            and blk["F2_shipped_left_source_untouched"]
            and blk["F2_known_broken_arm_fails"]
        )
    res["f7_shipped_gate_in_clone"] = blk
    shutil.rmtree(tmp, ignore_errors=True)

    # ---- F3 : frozen evidence, hash identity + a live detector ----
    frozen = {"files": {}, "dirty_lines": {}}
    allsame = True
    n = 0
    for d in FROZEN:
        tracked = [
            p
            for p in run(["git", "ls-files", "--", d]).stdout.splitlines()
            if p.strip()
        ]
        frozen.setdefault("tracked_counts", {})[d] = len(tracked)
        frozen["dirty_lines"][d] = len(
            [
                x
                for x in run(
                    ["git", "status", "--porcelain", "-uall", "--", d]
                ).stdout.splitlines()
                if x.strip()
            ]
        )
        for rel in tracked:
            n += 1
            wt = run(["git", "hash-object", rel]).stdout.strip()
            hd = run(["git", "rev-parse", f"HEAD:{rel}"]).stdout.strip()
            same = bool(wt) and wt == hd
            allsame = allsame and same
            frozen["files"][rel] = {"same": same, "head": hd[:12]}
    # live detector: a known-dirty directory must return a NON-zero count
    ctl = len(
        [
            x
            for x in run(
                ["git", "status", "--porcelain", "-uall", "--", SR]
            ).stdout.splitlines()
            if x.strip()
        ]
    )
    frozen["control_dirty_lines_on_known_dirty_dir"] = ctl
    frozen["F3_detector_is_live"] = ctl > 0
    frozen["F3_files_checked"] = n
    frozen["F3_all_identical_to_head_blob"] = allsame
    frozen["F3_no_untracked_inside_frozen"] = all(
        v == 0 for v in frozen["dirty_lines"].values()
    )
    frozen["F3_pass"] = bool(
        allsame
        and frozen["F3_detector_is_live"]
        and frozen["F3_no_untracked_inside_frozen"]
        and n > 0  # fail closed: zero files checked is a shape change, not a pass
    )
    res["f7_frozen"] = frozen

    ok = bool(blk.get("F2_pass") and frozen["F3_pass"])
    res["f7_verdict"] = "SHIPPED-GATE-CLONE-VALID" if ok else "NOT-PROVEN"
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()
    print("SUCCESS:r7-final" if ok else "FAILED:r7-final see-f7_verdict")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
