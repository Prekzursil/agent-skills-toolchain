#!/usr/bin/env python3
"""CNF-0149 probe1: three-route byte-table arithmetic - the 3837/3737/100-CRLF control must be
internally exact, the blob-source policy must forbid git archive and name the two allowed
routes, and every checkout-mode cell must carry coherent per-mode verdicts.
Emitted by shard8-w2 resume builder 2026-10-25. Self-contained; stdlib only."""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CHECKS = []

def ck(name, cond):
    CHECKS.append({"check": name, "ok": bool(cond)})
    return bool(cond)

def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))

def finish(pid, uid):
    raw = {"probe": pid, "unit": uid, "checks": CHECKS, "all_ok": all(c["ok"] for c in CHECKS)}
    (Path(__file__).parent / (pid + ".raw.json")).write_bytes(json.dumps(raw, indent=1).encode("utf-8"))
    print(json.dumps(raw))
    return 0 if raw["all_ok"] else 1

def main():
    d = load("command-center/receipts/CNF-0149.json")
    cc = d["classic_3837_3737_control"]
    ck("control_reproduced_flag", cc.get("reproduced") is True)
    ck("archive_delta_equals_crlf_delta",
       cc["archive_bytes"] - cc["cat_file_bytes"] == cc["archive_crlf"] - cc["cat_file_crlf"] == 100)
    ck("archive_is_the_crlf_polluted_route", cc["archive_crlf"] == 100 and cc["cat_file_crlf"] == 0)
    pol = d["blob_source_policy"]
    ck("policy_forbids_git_archive", "archive" in str(pol.get("forbidden", "")).lower())
    allowed = json.dumps(pol.get("allowed", [])).lower()
    ck("policy_allows_catfile_and_show", "cat-file" in allowed and "show" in allowed)
    blob = d["known_broken_crlf_blob"]
    cf = blob["cat_file"]
    ck("blob_counts_arithmetic_exact", cf["bytes"] == 62 and cf["cr"] == 3 and cf["crlf"] == 3 and cf["lf_newlines"] == 0)
    ck("blob_both_hashes_recorded", bool(cf.get("sha256")) and bool(cf.get("sha256_lf")) and cf["sha256"] != cf["sha256_lf"])
    cells = d["cells"]
    ok = len(cells) >= 5
    for c in cells:
        v = c.get("verdicts", {})
        holds_blob = (v.get("blob") == "PASS")
        holds_both = (v.get("autocrlf_false") == v.get("autocrlf_true"))
        ok &= (c.get("holds_on_ci_blob") == holds_blob)
        ok &= (c.get("holds_under_both_checkout_modes") == holds_both)
        ok &= len(v) >= 2
    ck("cells_verdicts_consistent_with_hold_flags", ok)
    neg = [c for c in cells if c["id"] == "bad-py_style"]
    ck("known_bad_style_fixture_fails_all_three_routes",
       bool(neg) and all(x == "FAIL" for x in neg[0]["verdicts"].values()))
    vsens = [c for c in cells if c.get("classification") == "version-sensitive"]
    ck("version_sensitive_cell_records_the_crlf_hazard",
       any(c["verdicts"].get("blob") == "PASS" and c["verdicts"].get("autocrlf_true") == "FAIL" for c in vsens))
    io = d.get("inputs_on_disk", {})
    ck("release_checklist_input_recorded", "RELEASE-CHECKLIST.md" in json.dumps(io))
    ck("sentinel_in_artifact", "SUCCESS:CNF-0149" in (REPO / "command-center/receipts/CNF-0149.json").read_text(encoding="utf-8"))
    return finish("probe1_selfcheck", "CNF-0149")

if __name__ == "__main__":
    sys.exit(main())
