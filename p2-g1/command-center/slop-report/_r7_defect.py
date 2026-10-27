"""ROUND 7 probe: the round-6 transcription gate can only ever measure THIS disk.

Round 6 shipped `_r6_transcript.py`, the instrument that catches a published number
disagreeing with its receipt. It hardcodes `REPO = "C:/Users/Prekzursil/source/ast-integrate"`.
Its own sibling -- the CI-wired `check_published_commands.py` -- carries a PORTABILITY
paragraph naming that exact construction as the reason another gate "cannot run on a CI
runner at all". So the lane documented the defect class and then committed it.

Three measurements. Each carries a control that must DISTINGUISH the two hypotheses, not
merely prove the instrument ran.

P1  HARDCODED ROOT -- decided by `ast` over the module body, never a regex over prose.
    H1: the gate resolves its root dynamically.   H2: it binds an absolute literal.
    CONTROL both ways: the same detector must report NOT-hardcoded for
    `check_published_commands.py` (which uses `git rev-parse --show-toplevel`) and
    hardcoded for `_aud3_clone_gate.py` (which does bind a literal). A detector that
    answers the same for all three is reading files, not measuring the claim.

P2  PORTABILITY, BOTH STATES, IN A REAL FRESH CLONE.
    Copy the gate into a fresh clone, run it with cwd=clone.
    H1 it measures the clone       -> reported `head` == clone HEAD
    H2 it measures the source tree -> reported `head` == source HEAD
    H2 is strictly worse than not cloning at all: it manufactures precisely the confidence
    a clone is supposed to establish. Second, independent signal on the same hypothesis:
    whether running the CLONE's copy mutates a file inside the SOURCE worktree.

P3  WORKING-TREE RECEIPTS vs COMMITTED RECEIPTS -- the false-negative direction.
    The gate indexes receipts by globbing the WORKING TREE. Receipts in this directory have
    been dirty for several rounds. So a document may publish a number that matches only
    this disk and still be certified TRANSCRIPTION-CLEAN, while a clone reading the
    committed blob disagrees. Proven in memory on a REAL divergent key, in BOTH directions,
    with no file mutated.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SR = "command-center/slop-report"
GATE = "_r6_transcript.py"
OUT = os.path.join(REPO, SR, "_r7_defect.out.json")


def run(cmd, cwd=REPO):
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def literal_of(node):
    """Return the string literal a module-level assignment binds, else None.

    Unwraps `Path("...")` / `pathlib.Path("...")` so the detector is not fooled by the
    wrapper the sibling gate's docstring actually quotes.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name == "Path" and len(node.args) == 1:
            return literal_of(node.args[0])
    return None


def blob_at(rev, rel):
    """The committed bytes of a path at a rev -- `git show`, which returns the stored blob."""
    r = run(["git", "show", f"{rev}:{rel}"])
    return r.stdout if r.returncode == 0 else None


def prefix_rev():
    """Newest rev whose committed gate STILL carries the absolute literal.

    Discovered, not pinned by hand. Once the fix is committed the working tree is DYNAMIC,
    so a probe that measured only the live file would go silent the moment the defect was
    repaired and could never demonstrate it again -- the exact trap round 6 avoided by
    holding its T1/T2 fixtures inside the gate. Anchoring on the last hardcoded BLOB keeps
    this receipt re-runnable and truthful after the fix lands.
    """
    rel = f"{SR}/{GATE}"
    revs = run(["git", "log", "--format=%H", "--", rel]).stdout.split()
    for rev in revs:  # newest first
        text = blob_at(rev, rel)
        if text and root_binding_text(text)["hardcoded_absolute"]:
            return rev
    return None


def root_binding_text(text):
    """Module-level REPO/ROOT bindings and whether any is an absolute literal."""
    tree = ast.parse(text)
    found = []
    for node in tree.body:  # module level ONLY -- a local in a function is not the root
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in ("REPO", "ROOT", "REPO_ROOT"):
                lit = literal_of(node.value)
                found.append({"name": tgt.id, "literal": lit})
    absolute = [
        f
        for f in found
        if f["literal"] and (":" in f["literal"][:3] or f["literal"].startswith("/"))
    ]
    return {"bindings": found, "hardcoded_absolute": bool(absolute)}


def root_binding(path):
    """Same check, against a file on disk."""
    with open(path, encoding="utf-8") as fh:
        return root_binding_text(fh.read())


def leaf_index(obj, into):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                leaf_index(v, into)
            else:
                into.setdefault(k, []).append(v)
    elif isinstance(obj, list):
        for v in obj:
            leaf_index(v, into)


def committed_receipts(skip_basename):
    """Receipt index built from HEAD blobs -- what a clone would read."""
    ls = run(["git", "ls-files", "--", f"{SR}/_*.out.json"])
    out = {}
    for rel in [p for p in ls.stdout.splitlines() if p.strip()]:
        base = os.path.basename(rel)
        if base == skip_basename:
            continue
        blob = run(["git", "show", f"HEAD:{rel}"])
        if blob.returncode != 0:
            continue
        try:
            data = json.loads(blob.stdout)
        except ValueError:
            continue
        idx = {}
        leaf_index(data, idx)
        out[base] = {"index": idx, "raw": data}
    return out


def load_gate_module():
    spec = importlib.util.spec_from_file_location(
        "_r6_transcript_probe", os.path.join(REPO, SR, GATE)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # main() is guarded by __name__
    return mod


def main() -> int:
    res = {"repo": REPO, "gate": GATE}
    res["source_head"] = run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip()

    # ---------------- P1 : hardcoded root, decided by ast ----------------
    pin = prefix_rev()
    res["prefix_rev"] = pin
    as_shipped = (
        root_binding_text(blob_at(pin, f"{SR}/{GATE}")) if pin else {"bindings": []}
    )
    now = root_binding(os.path.join(REPO, SR, GATE))
    ctl_neg = root_binding(os.path.join(REPO, SR, "check_published_commands.py"))
    ctl_pos = root_binding(os.path.join(REPO, SR, "_aud3_clone_gate.py"))
    res["P1"] = {
        # THE DEFECT, measured against the blob that shipped it -- durable after the fix.
        "subject_AS_SHIPPED_at_prefix_rev": as_shipped,
        # THE FIX, measured against the live file. Reported beside it, never instead of it.
        "subject_NOW_worktree": now,
        "control_negative__check_published_commands": ctl_neg,
        "control_positive__aud3_clone_gate": ctl_pos,
        # The control pair must still separate the two hypotheses on files this probe does
        # NOT edit, so it keeps working after the subject is repaired.
        "control_distinguishes": (
            ctl_pos["hardcoded_absolute"] and not ctl_neg["hardcoded_absolute"]
        ),
        "verdict": (
            "HARDCODED-AS-SHIPPED"
            if as_shipped.get("hardcoded_absolute")
            else "NOT-REPRODUCED"
        ),
        "fixed_in_worktree": not now["hardcoded_absolute"],
    }

    # ---------------- P2 : run it inside a real fresh clone ----------------
    tmp = tempfile.mkdtemp(prefix="r7_clone_")
    clone = os.path.join(tmp, "c").replace("\\", "/")
    cl = run(["git", "clone", "--no-hardlinks", "--quiet", REPO, clone], cwd=REPO)
    p2 = {"clone_rc": cl.returncode, "clone_stderr": cl.stderr.strip()[:400]}
    if cl.returncode == 0:
        # Pinned to the PRE-FIX rev so the clone carries the gate that still has the
        # literal. Checking out HEAD would stop demonstrating anything the moment the fix
        # is committed.
        run(["git", "checkout", "--quiet", pin or res["source_head"]], cwd=clone)
        p2["clone_head"] = run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=clone
        ).stdout.strip()
        gate_in_clone = os.path.join(clone, SR, GATE)
        # the clone has the COMMITTED gate; that is the artifact under test
        p2["gate_present_in_clone"] = os.path.exists(gate_in_clone)
        src_out = os.path.join(REPO, SR, "_r6_transcript.out.json")
        before = open(src_out, "rb").read() if os.path.exists(src_out) else b""
        r = run(["python", gate_in_clone], cwd=clone)
        after = open(src_out, "rb").read() if os.path.exists(src_out) else b""
        try:
            payload = json.loads(r.stdout[: r.stdout.rindex("}") + 1])
            p2["reported_head"] = payload.get("head")
            p2["reported_docs_scanned"] = payload.get("docs_scanned")
            p2["reported_receipts_indexed"] = payload.get("receipts_indexed")
        except (ValueError, AttributeError):
            p2["stdout_head"] = r.stdout[:300]
        p2["clone_docs_on_disk"] = len(
            [
                n
                for n in os.listdir(os.path.join(clone, SR))
                if n.startswith("SLOP-") and n.endswith(".md")
            ]
        )
        p2["source_docs_on_disk"] = len(
            [
                n
                for n in os.listdir(os.path.join(REPO, SR))
                if n.startswith("SLOP-") and n.endswith(".md")
            ]
        )
        # SIGNAL 1 -- REFUTED AS A DETECTOR, kept because the refutation is the lesson.
        # Comparing the reported `head` against a HEAD read at probe start cannot decide
        # anything here: siblings commit continuously, so the two differ for a reason that
        # has nothing to do with which tree was measured. First run: source_head=245a24ec,
        # clone_head=245a24ec, reported_head=c3cfefde -- matching NEITHER, and the probe
        # called the confirmed defect INCONCLUSIVE. Equality against a moving value is not
        # an invariant. Recorded, never read for the verdict.
        p2["S1_head_equality_REFUTED_moving_head"] = {
            "reported_head": p2.get("reported_head"),
            "clone_head": p2.get("clone_head"),
            "source_head_at_probe_start": res["source_head"],
            "why_unusable": "HEAD moves under this lane mid-run; equality is not an invariant",
        }
        # SIGNAL 2 -- doc COUNT. Independent of HEAD entirely. The source tree carries an
        # untracked SLOP-*.md that cannot exist in a fresh clone, so the two counts differ
        # by construction and the reported number names the tree that was read.
        p2["S2_measured_the_source_by_doccount"] = (
            p2.get("reported_docs_scanned") == p2["source_docs_on_disk"]
            and p2["source_docs_on_disk"] != p2["clone_docs_on_disk"]
        )
        p2["S2_measured_the_clone_by_doccount"] = (
            p2.get("reported_docs_scanned") == p2["clone_docs_on_disk"]
            and p2["source_docs_on_disk"] != p2["clone_docs_on_disk"]
        )
        # SIGNAL 3 -- mechanically independent of both: did the CLONE's run mutate a file
        # inside the SOURCE worktree? Only a hardcoded root can do that.
        p2["S3_clone_run_wrote_into_source_worktree"] = before != after
        p2["counts_differ_so_doccount_can_discriminate"] = (
            p2["source_docs_on_disk"] != p2["clone_docs_on_disk"]
        )
        p2["source_out_restored"] = False
        if before != after and before:
            with open(src_out, "wb") as fh:
                fh.write(before)
            p2["source_out_restored"] = True
    res["P2"] = p2
    shutil.rmtree(tmp, ignore_errors=True)

    # ------- P3 : working-tree receipts vs committed receipts (false negative) -------
    mod = load_gate_module()
    wt = mod.load_receipts()
    cm = committed_receipts(os.path.basename(mod.OUT))

    def owners(index_map, key):
        return {b for b, d in index_map.items() if key in d["index"]}

    divergent = []
    for base, wtdata in wt.items():
        cmdata = cm.get(base)
        if not cmdata:
            continue
        for key, wvals in wtdata["index"].items():
            cvals = cmdata["index"].get(key)
            if cvals is None or wvals == cvals:
                continue
            if len(set(map(str, wvals))) != 1 or len(set(map(str, cvals))) != 1:
                continue  # need an unambiguous single value on both sides
            if not isinstance(wvals[0], (bool, int, str)) or isinstance(
                wvals[0], float
            ):
                continue
            # The gate matches a doc value against EVERY receipt holding that key. So a key
            # carried by more than one receipt cannot decide anything: the mirror control
            # came back AGREE-on-both the first time purely because a SECOND receipt held
            # the other value. Require the key to be unique to this receipt on BOTH sides.
            uniq = owners(wt, key) == {base} and owners(cm, key) == {base}
            divergent.append(
                {
                    "receipt": base,
                    "key": key,
                    "worktree": wvals[0],
                    "committed": cvals[0],
                    "key_unique_to_this_receipt": uniq,
                }
            )
    usable = [d for d in divergent if d["key_unique_to_this_receipt"]]
    p3 = {
        "divergent_keys_found": len(divergent),
        "divergent_keys_usable_unique": len(usable),
        "sample": divergent[:6],
    }
    if usable:
        pick = next((d for d in usable if isinstance(d["worktree"], bool)), usable[0])
        p3["chosen"] = pick

        def verdicts(text, receipts):
            claims = mod.analyze_text(text, receipts, doc="<r7-fixture>", base=0)
            mine = [c for c in claims if c.get("key") == pick["key"]]
            return {
                "claims": len(mine),
                "verdict": mine[0]["verdict"] if mine else None,
                "violation": bool(mine and mod.is_violation(mine[0])),
            }

        def as_doc(v):
            return json.dumps(v) if isinstance(v, bool) else str(v)

        text_wt = f"the receipt says `{pick['key']}: {as_doc(pick['worktree'])}`"
        text_cm = f"the receipt says `{pick['key']}: {as_doc(pick['committed'])}`"
        p3["claim_matching_WORKTREE_value"] = {
            "text": text_wt,
            "against_worktree_receipts": verdicts(text_wt, wt),
            "against_committed_receipts": verdicts(text_wt, cm),
        }
        p3["claim_matching_COMMITTED_value"] = {
            "text": text_cm,
            "against_worktree_receipts": verdicts(text_cm, wt),
            "against_committed_receipts": verdicts(text_cm, cm),
        }
        a = p3["claim_matching_WORKTREE_value"]
        b = p3["claim_matching_COMMITTED_value"]
        # The dangerous direction: green here, red in a clone.
        p3["false_negative_demonstrated"] = (
            a["against_worktree_receipts"]["verdict"] == "AGREE"
            and a["against_committed_receipts"]["verdict"] == "DISAGREE"
        )
        # The mirror, proving the two indices really differ and the comparator is live.
        p3["mirror_demonstrated"] = (
            b["against_worktree_receipts"]["verdict"] == "DISAGREE"
            and b["against_committed_receipts"]["verdict"] == "AGREE"
        )
        p3["both_directions"] = bool(
            p3["false_negative_demonstrated"] and p3["mirror_demonstrated"]
        )
    res["P3"] = p3

    res["verdict"] = (
        "CONFIRMED-NOT-CLONE-VALID"
        if res["P1"]["verdict"] == "HARDCODED-AS-SHIPPED"
        and p2.get("S2_measured_the_source_by_doccount")
        and p2.get("S3_clone_run_wrote_into_source_worktree")
        else "INCONCLUSIVE"
    )
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, __import__("sys").stdout, indent=1, sort_keys=True)
    print()
    ok = res["P1"]["control_distinguishes"] and cl.returncode == 0
    print("SUCCESS:r7-defect" if ok else "FAILED:r7-defect controls-or-clone")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
