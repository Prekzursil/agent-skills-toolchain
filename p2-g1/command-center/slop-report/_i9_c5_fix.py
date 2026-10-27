"""INTEGRATE round 2 -- the contested residual: `_r4_buckets.py`'s C5 was an inert control.

An adversarial round called this BLOCKING and it was still in the committed bytes at HEAD.
The claim under test:

    C5 as shipped read `sorted(X) == sorted(<the expression that produced X>)`, i.e.
    f(x) == f(x). It cannot fail, yet it sat in the PASS conjunction as the ONLY control
    over S1 -- the signal the classifier calls its strongest.

Three parts, because "I fixed it" is three separate claims:

  P1 THE OLD FORM IS INERT. Evaluate it under three scan implementations: real, one that
     returns nothing, one that fabricates a constant. A real control must go false in at
     least one. If the old form is true in all three it is measuring that the module
     imported.
  P2 THE NEW FORM DISTINGUISHES. The same three states through the replacement mutation
     pair. It must be true for the real scan and false for BOTH broken ones -- otherwise I
     have swapped one inert control for another.
  P3 I DID NOT BREAK THE CLASSIFIER. The edited file is executed END TO END in a fresh
     clone, where regenerating its receipt costs nothing. The SOURCE receipt must be
     byte-and-mtime identical afterwards: it belongs to rounds 4 and 5, sibling documents
     publish numbers from it, and the claims gate wired this round compares those documents
     against it.

SELF-CONTROL: a probe that reports "false" everywhere would look like a successful
refutation. P0 asserts the comparator can produce BOTH booleans on inputs whose answers are
known independently of the code under test.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

import check_published_commands as G  # noqa: E402

ROOT = Path(
    subprocess.run(
        ["git", "-C", str(_HERE), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    ).stdout.strip()
)
SOURCE_RECEIPT = ROOT / "command-center/slop-report/_r4_buckets.out.json"
CLASSIFIER_REL = "command-center/slop-report/_r4_buckets.py"

FAKE = [{"target": "made/up/constant.py", "citer": "x.md", "line": 1}]


def scan_real(repo, tracked, corpus):
    return G.scan(repo, tracked, corpus)


def scan_empty(repo, tracked, corpus):
    return ([], 0, 0)


def scan_fabricating(repo, tracked, corpus):
    return (list(FAKE), 0, 0)


def old_c5(scan, repo, tracked, corpus) -> bool:
    """Verbatim shape of the shipped control: X computed, then compared to its own source."""
    gate_untracked_targets = {f["target"] for f in scan(repo, tracked, corpus)[0]}
    return sorted(gate_untracked_targets) == sorted(
        {f["target"] for f in scan(repo, tracked, corpus)[0]}
    )


def new_c5(scan, repo, tracked, corpus) -> dict:
    """Replacement: perturb the INPUT, require the OUTPUT to move."""
    base = {f["target"] for f in scan(repo, tracked, corpus)[0]}
    grew = len({f["target"] for f in scan(repo, set(), corpus)[0]}) > len(base)
    emptied = not {f["target"] for f in scan(repo, tracked | base, corpus)[0]}
    return {"C5a_grows": grew, "C5b_empties": emptied, "PASS": grew and emptied}


def sig(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {"exists": True, "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def run(cmd, cwd):
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr}


def main() -> int:
    res: dict = {"repo_root": str(ROOT).replace("\\", "/")}
    res["head"] = run(["git", "rev-parse", "--short", "HEAD"], str(ROOT))["out"].strip()

    tracked = set(
        x
        for x in run(["git", "ls-files"], str(ROOT))["out"]
        .replace("\r\n", "\n")
        .split("\n")
        if x
    )
    corpus = sorted(p for p in tracked if G.in_corpus(p))
    res["corpus_files"] = len(corpus)
    res["tracked_files"] = len(tracked)

    # ---- P0 self-control: can this probe observe both booleans? ----------------------
    res["P0_self_control"] = {
        "true_is_observable": sorted({"a"}) == sorted({"a"}),
        "false_is_observable": sorted({"a"}) == sorted({"b"}),
    }
    res["P0_PASS"] = (
        res["P0_self_control"]["true_is_observable"]
        and not res["P0_self_control"]["false_is_observable"]
    )

    states = {
        "real": scan_real,
        "broken_returns_nothing": scan_empty,
        "broken_fabricates_a_constant": scan_fabricating,
    }

    # ---- P1: the old form under all three states -------------------------------------
    old = {name: old_c5(fn, str(ROOT), tracked, corpus) for name, fn in states.items()}
    res["P1_old_form"] = old
    res["P1_old_form_is_inert"] = all(old.values())

    # ---- P2: the new form under the same three ---------------------------------------
    new = {name: new_c5(fn, str(ROOT), tracked, corpus) for name, fn in states.items()}
    res["P2_new_form"] = new
    res["P2_new_form_distinguishes"] = (
        new["real"]["PASS"]
        and not new["broken_returns_nothing"]["PASS"]
        and not new["broken_fabricates_a_constant"]["PASS"]
    )

    # ---- P3: the edited classifier still runs, proven in a clone ----------------------
    receipt_before = sig(SOURCE_RECEIPT)
    tmp = tempfile.mkdtemp(prefix="i9_c5_")
    try:
        clone = os.path.join(tmp, "c")
        c = run(
            [
                "git",
                "clone",
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.eol=lf",
                "--single-branch",
                str(ROOT),
                clone,
            ],
            tmp,
        )
        if c["rc"] != 0:
            res["verdict"] = "ABORTED: clone failed"
            print(json.dumps(res, indent=1, sort_keys=True))
            print("FAILED:i9-c5 clone failed -- refusing to file a reading")
            return 1
        # The edit is uncommitted, so carry the WORKING copy into the clone deliberately.
        shutil.copyfile(ROOT / CLASSIFIER_REL, os.path.join(clone, CLASSIFIER_REL))
        r = run([sys.executable, CLASSIFIER_REL], clone)
        res["P3_clone_run"] = {
            "rc": r["rc"],
            "tail": r["out"].strip().splitlines()[-6:],
        }
        out_path = os.path.join(
            clone, "command-center/slop-report/_r4_buckets.out.json"
        )
        if os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as fh:
                data = json.load(fh)
            ctl = data.get("controls") or data.get("CONTROLS") or {}
            res["P3_controls_in_clone"] = ctl
            res["P3_controls_PASS"] = bool(ctl.get("PASS"))
            res["P3_counts_in_clone"] = data.get("counts")
        else:
            res["P3_controls_PASS"] = False
            res["P3_controls_in_clone"] = "<no receipt produced>"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    receipt_after = sig(SOURCE_RECEIPT)
    res["P3_source_receipt_untouched"] = receipt_before == receipt_after
    res["P3_source_receipt_sig"] = {"before": receipt_before, "after": receipt_after}

    checks = {
        "P0_probe_can_observe_both_booleans": res["P0_PASS"],
        "P1_shipped_C5_is_inert_in_all_three_states": res["P1_old_form_is_inert"],
        "P2_replacement_separates_real_from_both_broken": res[
            "P2_new_form_distinguishes"
        ],
        "P3_edited_classifier_runs_green_in_a_clone": res["P3_controls_PASS"],
        "P3_source_receipt_not_regenerated": res["P3_source_receipt_untouched"],
    }
    res["checks"] = checks
    res["verdict"] = "C5-FIX-PROVEN" if all(checks.values()) else "FAILED"

    out = ROOT / "command-center/slop-report/_i9_c5_fix.out.json"
    out.write_text(
        json.dumps(res, indent=1, sort_keys=True), encoding="utf-8", newline="\n"
    )
    print(json.dumps(res, indent=1, sort_keys=True))
    print(
        "SUCCESS:i9-c5-fix" if res["verdict"] == "C5-FIX-PROVEN" else "FAILED:i9-c5-fix"
    )
    return 0 if res["verdict"] == "C5-FIX-PROVEN" else 1


if __name__ == "__main__":
    sys.exit(main())
