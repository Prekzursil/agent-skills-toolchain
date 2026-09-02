"""AUDIT R2 probe 3: is the re-run receipt drift BENIGN, as builder residual #6 claims?

Claim under test (builder residual #6): "Re-running the probe suite dirties 6
receipts ... the ONLY changed fields are rev, head, live_head, measured_at_rev,
growing counts, and live git-status strings -- ZERO verdict/checks/pass/GREEN
lines move."

H1 (benign): every changed JSON leaf is a rev/host/count/status field.
H2 (rot):    a verdict or a check boolean flipped -- i.e. a committed receipt
             asserts something a re-run no longer reproduces. That is the D2
             defect class, and finding it here would REFUTE the residual.

SELF-CONTAINED. An earlier version of this probe classified whatever happened to
be dirty in the ambient tree. On a clean tree it found nothing, could not build
its control, and returned DETECTOR-INERT -- failing closed, correctly, but
proving nothing. That is the same "verdict depends on ambient state" rot the
lane is auditing, reproduced in the auditor's own instrument. This version
CREATES the drift itself: assert clean -> run the builder's probe suite ->
classify -> restore. It is re-runnable from any clean checkout.

CONTROL (must distinguish H1 from H2): the classifier is also run against a
SYNTHETIC mutation of a committed receipt with every verdict string and boolean
flipped. It MUST report those. Silence on the real receipts is meaningless
otherwise. The control is built from a COMMITTED blob, so it runs even if the
suite produces no drift at all.
"""

import copy
import json
import os
import subprocess
import sys

REPO = "C:/Users/Prekzursil/source/ast-integrate"
S = "command-center/slop-report/"
SUITE = [
    "_b1_control.py",
    "_r2_d2_reproduce.py",
    "_r2_fix_verify.py",
    "_r2_predcheck.py",
    "_r2_bucket_c.py",
    "_r2_frozen.py",
]
CONTROL_RECEIPT = "_r2_frozen.out.json"

VOLATILE = (
    "rev",
    "head",
    "measured_at",
    "_at_rev",
    "count",
    "counts",
    "dirty",
    "status",
    "citers",
    "hash",
    "sha",
    "mtime",
    "timestamp",
    "considered",
    "n_",
    "_n",
    "live_",
    "paths",
    "utc",
    "time",
)
VERDICT_KEYS = (
    "verdict",
    "check",
    "pass",
    "ok",
    "fail",
    "green",
    "held",
    "untouched",
    "reconciled",
    "proven",
    "armed",
    "holds",
    "distinguishable",
    "unmodified",
    "restored",
    "identical",
    "closes",
    "differ",
    "unchanged",
)


def git(*a):
    r = subprocess.run(
        ["git", "-C", REPO, *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


def dirty_tracked():
    _rc, out, _ = git("status", "--porcelain", "--", S)
    return [
        ln[3:].strip()
        for ln in out.splitlines()
        if ln.strip() and not ln.startswith("??")
    ]


def walk(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, obj


def classify(committed, live):
    a, b = dict(walk(committed)), dict(walk(live))
    verdict_changes, volatile_changes, unclassified = [], [], []
    for k in sorted(set(a) | set(b)):
        va, vb = a.get(k, "<ABSENT>"), b.get(k, "<ABSENT>")
        if va == vb:
            continue
        leaf = k.split(".")[-1].split("[")[0].lower()
        full = k.lower()
        if any(t in leaf or t in full for t in VERDICT_KEYS):
            verdict_changes.append({"path": k, "committed": va, "live": vb})
        elif any(t in leaf for t in VOLATILE):
            volatile_changes.append(k)
        else:
            unclassified.append(
                {"path": k, "committed": str(va)[:60], "live": str(vb)[:60]}
            )
    return verdict_changes, volatile_changes, unclassified


res = {"probe": "_aud2_rot", "head": git("rev-parse", "HEAD")[1].strip()}

# ---- 0. precondition: my scope must start clean ---------------------------
pre = dirty_tracked()
res["dirty_before_suite"] = pre
if pre:
    res["verdict"] = "PRECONDITION-FAILED-TREE-ALREADY-DIRTY"
    res["ok"] = False
    print(json.dumps(res, indent=2))
    sys.exit(1)

# ---- 1. CREATE the drift by running the builder's suite -------------------
suite_rc = {}
for script in SUITE:
    p = subprocess.run(
        [sys.executable, os.path.join(REPO, S, script)],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    suite_rc[script] = p.returncode
res["suite_return_codes"] = suite_rc

dirty = dirty_tracked()
res["dirty_after_suite"] = dirty
res["n_receipts_dirtied"] = len(dirty)
res["builder_claimed_6"] = 6
res["matches_builder_count"] = len(dirty) == 6

# ---- 2. classify every changed leaf ---------------------------------------
rows, any_verdict_moved = [], False
for p in dirty:
    if not p.endswith(".json"):
        rows.append({"path": p, "note": "non-json, skipped"})
        continue
    _rc, blob, _ = git("show", f"HEAD:{p}")
    try:
        committed = json.loads(blob)
        with open(os.path.join(REPO, p), encoding="utf-8") as fh:
            live = json.load(fh)
    except Exception as e:  # noqa: BLE001
        rows.append({"path": p, "error": str(e)})
        continue
    vc, vol, unc = classify(committed, live)
    if vc:
        any_verdict_moved = True
    rows.append(
        {
            "path": p,
            "verdict_bearing_changes": vc,
            "volatile_changed_count": len(vol),
            "volatile_changed_sample": vol[:8],
            "unclassified_changes": unc,
        }
    )
res["receipts"] = rows
res["any_verdict_bearing_change"] = any_verdict_moved

# ---- 3. CONTROL from a COMMITTED blob (runs regardless of drift) ----------
_rc, blob, _ = git("show", f"HEAD:{S}{CONTROL_RECEIPT}")
committed = json.loads(blob)
mutated = copy.deepcopy(committed)


def flip(o):
    hit = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k.lower() == "verdict" and isinstance(v, str):
                o[k] = "FAIL-SYNTHETIC"
                hit.append(k)
            elif isinstance(v, bool):
                o[k] = not v
                hit.append(k)
            else:
                hit += flip(v)
    elif isinstance(o, list):
        for v in o:
            hit += flip(v)
    return hit


flipped = flip(mutated)
cvc, _cvol, _cunc = classify(committed, mutated)
res["control_synthetic_verdict_flip"] = {
    "source": f"HEAD:{S}{CONTROL_RECEIPT} (committed blob)",
    "leaves_flipped": len(flipped),
    "classifier_reported_verdict_changes": len(cvc),
    "detector_fires_on_H2": len(cvc) > 0,
    "sample": cvc[:3],
}

# ---- 4. restore every receipt the suite dirtied ---------------------------
if dirty:
    git("checkout", "--", *dirty)
res["dirty_after_restore"] = dirty_tracked()
res["restored_clean"] = not res["dirty_after_restore"]

ok = (
    (not any_verdict_moved)
    and res["control_synthetic_verdict_flip"]["detector_fires_on_H2"]
    and res["restored_clean"]
    and len(dirty) > 0
)
res["verdict"] = (
    "DRIFT-BENIGN-AND-DETECTOR-PROVEN"
    if ok
    else (
        "VERDICT-BEARING-DRIFT-FOUND"
        if any_verdict_moved
        else ("NO-DRIFT-PRODUCED" if not dirty else "DETECTOR-INERT")
    )
)
res["ok"] = ok

with open(
    os.path.join(REPO, S, "_aud2_rot.out.json"), "w", encoding="utf-8", newline="\n"
) as fh:
    json.dump(res, fh, indent=2)

print(
    json.dumps(
        {k: v for k, v in res.items() if k != "receipts"},
        indent=2,
    )
)
for r in res["receipts"]:
    print(
        f"  {r['path'].split('/')[-1]:34s} verdict_changes="
        f"{len(r.get('verdict_bearing_changes', []))} "
        f"volatile={r.get('volatile_changed_count')} "
        f"unclassified={len(r.get('unclassified_changes', []))}"
    )
sys.exit(0 if ok else 1)
