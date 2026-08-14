#!/usr/bin/env python3
"""G5e: repo-vs-live drift of the hook SCRIPT BODIES.

Rounds 1-4 measured drift of `_dispatch/manifest.json` (which hooks are WIRED) and named two
specific undeployed fixes. Nobody measured the axis underneath: for every hook that exists in
BOTH trees, do the bytes agree? A wired hook whose live body is a different program is a
silent behaviour fork -- and the live body is the one that runs.

Method: sha256 over LF-normalised bytes, so a pure CRLF difference is NOT reported as drift
(windows-shell.md 8b: the repo blob is LF, the working tree may be CRLF; counting that as
drift manufactures a flood and trains the reader to ignore the report).

CONTROLS:
  D1 POSITIVE: at least one file must compare EQUAL. If nothing matches, the path mapping is
     wrong and every "differs" is a mapping artifact, not drift.
  D2 NEGATIVE: a synthetic mutation of a known-equal file must be reported as DIFFERS.
     Without this, "0 differs" cannot be distinguished from a comparator that never fires.
  D3 The two arms must disagree, or the run publishes INCONCLUSIVE.
"""

import hashlib
import json
import os
import sys

REPO_HOOKS = r"C:\Users\Prekzursil\source\ast-integrate\hooks"
LIVE_HOOKS = r"C:\Users\Prekzursil\.claude\hooks"
SKIP_DIRS = {"__pycache__", "_fleet-backups", ".pytest_cache"}


def norm_sha(path):
    with open(path, "rb") as f:
        b = f.read()
    b = b.replace(b"\r\n", b"\n")
    return hashlib.sha256(b).hexdigest(), len(b)


def walk(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.endswith((".py", ".ps1", ".sh", ".json")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            out[rel] = full
    return out


def main():
    repo = walk(REPO_HOOKS)
    live = walk(LIVE_HOOKS)
    both = sorted(set(repo) & set(live))

    equal, differs = [], []
    for rel in both:
        try:
            rs, rn = norm_sha(repo[rel])
            ls, ln = norm_sha(live[rel])
        except Exception as e:  # noqa: BLE001
            differs.append({"path": rel, "error": type(e).__name__})
            continue
        if rs == ls:
            equal.append(rel)
        else:
            differs.append(
                {
                    "path": rel,
                    "repo_bytes": rn,
                    "live_bytes": ln,
                    "delta_bytes": ln - rn,
                }
            )

    ctl = {"D1_positive_any_equal": len(equal) > 0}

    # D2: mutate a known-equal file in memory and confirm the comparator fires
    if equal:
        probe = equal[0]
        with open(repo[probe], "rb") as f:
            b = f.read().replace(b"\r\n", b"\n")
        mutated = hashlib.sha256(b + b"\n# synthetic mutation\n").hexdigest()
        original = hashlib.sha256(b).hexdigest()
        ctl["D2_negative_mutation_detected"] = mutated != original
        ctl["D2_probe_file"] = probe
    else:
        ctl["D2_negative_mutation_detected"] = False
    ctl["D3_arms_discriminate"] = (
        ctl["D1_positive_any_equal"] and ctl["D2_negative_mutation_detected"]
    )

    res = {
        "controls": ctl,
        "repo_files": len(repo),
        "live_files": len(live),
        "in_both": len(both),
        "equal_count": len(equal),
        "differs_count": len(differs),
        "repo_only_count": len(set(repo) - set(live)),
        "live_only_count": len(set(live) - set(repo)),
        "live_only": sorted(set(live) - set(repo))[:40],
    }
    if not ctl["D3_arms_discriminate"]:
        res["verdict"] = "INCONCLUSIVE - comparator failed its own controls"
        print(json.dumps(res, indent=2))
        return 1

    differs.sort(key=lambda d: -abs(d.get("delta_bytes", 0)))
    res["differs_top25"] = differs[:25]
    res["drift_pct_of_shared"] = round(100.0 * len(differs) / max(1, len(both)), 1)
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
