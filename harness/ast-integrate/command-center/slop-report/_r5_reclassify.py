"""DoD-1 at round 5's rev, and the bucket-(c) criterion re-examined.

Round 4 classified a file as bucket (c) -- "reproducible scratch, safe to delete" -- when
a sibling script existed that names it as its output. `_r5_bucket_c.py` then showed that
test is too weak: `_secfirst_selfaudit.out.json` regenerates perfectly on this disk while
FOUR of its producer's six inputs are untracked, so nobody who clones the repo could
rebuild it. "Safe to delete" requires regenerable-from-the-repo, not regenerable-here.

This probe re-runs the SHIPPED classifier (`_r4_buckets.py`, whose five controls are
already committed and green -- reused rather than rebuilt) at this round's rev, then
applies the missing test to every bucket-(c) row:

    for each producer, resolve the file paths it names and ask whether each is TRACKED.

DETECTOR CONTROLS on the input extractor, because a static scan of source text is exactly
the kind of instrument that silently finds nothing:
  E1 KNOWN ANSWER. Run it on `_secfirst_selfaudit.py`, whose inputs were derived by hand
     in `_r5_bucket_c.py`. It must find all four untracked ones. If it finds fewer, the
     extractor is blind and every "clone_regenerable: true" below is worthless.
  E2 POSITIVE. A literal naming a known-TRACKED file must come back tracked.
  E3 NEGATIVE. A literal naming a fresh uuid4 basename must come back not-tracked and
     not-on-disk -- so "tracked" is a reading, not a default.

The classifier's own receipt is TRACKED, so it is snapshotted and then restored with
`git checkout --`; the snapshot this round cites is `_r5_buckets_snapshot.json`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid

REPO = "C:/Users/Prekzursil/source/ast-integrate"
SR = "command-center/slop-report"
CLASSIFIER = f"{SR}/_r4_buckets.py"
CLASSIFIER_OUT = f"{SR}/_r4_buckets.out.json"
SNAPSHOT = os.path.join(REPO, SR, "_r5_buckets_snapshot.json")
OUT = os.path.join(REPO, SR, "_r5_reclassify.out.json")

HAND_DERIVED_UNTRACKED = {
    "platform/architecture/_secfirst_measure.out.json",
    "platform/architecture/_secfirst_measure2.out.json",
    "platform/architecture/_secfirst_measure3.out.json",
    "platform/architecture/_secfirst_probe_denydefault.out.json",
}

FILE_LIT = re.compile(r"""['"]([A-Za-z0-9_./-]+\.(?:json|md|py|ya?ml|txt|toml))['"]""")


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, errors="replace"
    ).stdout


def lines(s: str) -> list[str]:
    return [ln for ln in s.replace("\r\n", "\n").split("\n") if ln.strip()]


def resolve_inputs(producer_rel: str, text: str, tracked: set[str]) -> list[dict]:
    """Every file-looking literal, resolved repo-relative or producer-dir-relative."""
    pdir = os.path.dirname(producer_rel)
    seen: dict[str, dict] = {}
    for lit in FILE_LIT.findall(text):
        cands = [lit.lstrip("./"), f"{pdir}/{os.path.basename(lit)}"]
        hit = next((c for c in cands if c in tracked), None)
        if hit is None:
            hit = next(
                (c for c in cands if os.path.exists(os.path.join(REPO, c))), cands[0]
            )
        if hit == producer_rel or hit.endswith(".out.json") and hit == producer_rel:
            continue
        seen[hit] = {
            "literal": lit,
            "resolved": hit,
            "tracked": hit in tracked,
            "on_disk": os.path.exists(os.path.join(REPO, hit)),
        }
    return sorted(seen.values(), key=lambda d: d["resolved"])


def main() -> int:
    res: dict = {"rev": git("rev-parse", "HEAD").strip()[:8]}
    tracked = {p for p in lines(git("ls-files"))}

    # ---- rerun the shipped classifier, snapshot, restore ------------------
    was_dirty = bool(lines(git("status", "--porcelain", "--", CLASSIFIER_OUT)))
    res["classifier_receipt_was_dirty_before"] = was_dirty
    proc = subprocess.run(
        ["python", CLASSIFIER], cwd=REPO, capture_output=True, text=True
    )
    res["classifier_rc"] = proc.returncode
    body = json.load(open(os.path.join(REPO, CLASSIFIER_OUT), encoding="utf-8"))
    with open(SNAPSHOT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(body, fh, indent=1, sort_keys=True)
    if not was_dirty:
        git("checkout", "--", CLASSIFIER_OUT)
        res["classifier_receipt_restored"] = not lines(
            git("status", "--porcelain", "--", CLASSIFIER_OUT)
        )
    else:
        res["classifier_receipt_restored"] = "left as found (was already dirty)"

    rows = body.get("rows", [])
    hist: dict[str, int] = {}
    for r in rows:
        hist[r.get("bucket")] = hist.get(r.get("bucket"), 0) + 1
    res["classifier_controls"] = body.get("controls")
    res["untracked_total"] = body.get("untracked_total", len(rows))
    res["row_count"] = len(rows)
    res["partition_total"] = sum(hist.values()) == len(rows)
    res["histogram"] = hist

    # ---- detector controls on the extractor -------------------------------
    probe_src = open(
        os.path.join(REPO, "platform/architecture/_secfirst_selfaudit.py"),
        encoding="utf-8",
    ).read()
    found = {
        d["resolved"]
        for d in resolve_inputs(
            "platform/architecture/_secfirst_selfaudit.py", probe_src, tracked
        )
    }
    e1 = HAND_DERIVED_UNTRACKED <= found
    nonce = f"{uuid.uuid4().hex}.json"
    synth = f'x = "command-center/WORK-UNIT-CATALOG.json"\ny = "{nonce}"\n'
    srows = {
        d["resolved"]: d for d in resolve_inputs("command-center/x.py", synth, tracked)
    }
    e2 = srows.get("command-center/WORK-UNIT-CATALOG.json", {}).get("tracked") is True
    nrow = next((v for k, v in srows.items() if nonce in k), None)
    e3 = nrow is not None and not nrow["tracked"] and not nrow["on_disk"]
    res["extractor_controls"] = {
        "E1_known_answer_finds_hand_derived": e1,
        "E1_missing": sorted(HAND_DERIVED_UNTRACKED - found),
        "E2_known_tracked_reads_tracked": e2,
        "E3_uuid4_reads_untracked_and_absent": e3,
        "PASS": e1 and e2 and e3,
    }
    if not res["extractor_controls"]["PASS"]:
        res["verdict"] = "DETECTOR-FAILED: no reclassification may be cited"
        json.dump(res, sys.stdout, indent=1, sort_keys=True)
        return 1

    # ---- apply the missing test to every bucket-(c) row -------------------
    verdicts = []
    for r in rows:
        if r.get("bucket") != "c":
            continue
        prod = (r.get("producer") or "").replace("python ", "").strip()
        pabs = os.path.join(REPO, prod)
        if not prod or not os.path.exists(pabs):
            verdicts.append(
                {"path": r["path"], "producer": prod, "verdict": "PRODUCER-MISSING"}
            )
            continue
        src = open(pabs, encoding="utf-8", errors="replace").read()
        ins = [
            d for d in resolve_inputs(prod, src, tracked) if d["resolved"] != r["path"]
        ]
        untracked_in = [d["resolved"] for d in ins if not d["tracked"] and d["on_disk"]]
        verdicts.append(
            {
                "path": r["path"],
                "producer": prod,
                "producer_tracked": prod in tracked,
                "n_inputs_resolved": len(ins),
                "untracked_inputs": untracked_in,
                "clone_regenerable": prod in tracked and not untracked_in,
                "verdict": (
                    "BUCKET-C-CONFIRMED"
                    if prod in tracked and not untracked_in
                    else "RECLASSIFY-TO-B"
                ),
            }
        )
    res["bucket_c_rows"] = verdicts
    res["bucket_c_confirmed"] = sum(
        1 for v in verdicts if v["verdict"] == "BUCKET-C-CONFIRMED"
    )
    res["bucket_c_reclassified_to_b"] = sum(
        1 for v in verdicts if v["verdict"] == "RECLASSIFY-TO-B"
    )
    res["verdict"] = "MEASURED"

    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()
    print("SUCCESS:r5-reclassify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
