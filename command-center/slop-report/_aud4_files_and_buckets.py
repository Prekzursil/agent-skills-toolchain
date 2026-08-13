"""AUDIT probe 4: Test-Path every claimed artifact, verify the 45 names, verify DoD1/DoD2.

A digest is a claim, not a receipt -- so every path the builder says it created or committed
is existence-checked AND tracked-checked here, plus the four-bucket content of the report.
"""

import json
import re
import subprocess
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
SR = REPO / "command-center" / "slop-report"


def git(*a):
    r = subprocess.run(
        ["git", "-C", str(REPO), *a],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.returncode, r.stdout, r.stderr


out = {}
rc, so, _ = git("ls-files")
tracked = set(so.splitlines())

# ---------- the 45 names the builder listed in files_touched ----------
claimed45 = """_a3_probe _a3_rules_skills _adv0031_inventory _b2_m09_probe _b2_m09_probe2 _baseline_probe
_baseline_tests _c1_probe_dangling _c1_probe_delivmap _c1_probe_p15_units _c1_probe_phase1516
_c1_probe_ready _c1_probe_schemas _c2_c21_probe _catalog_integrity _catalog_shortfall_attrib
_d1_reverify_artifacts _d1_reverify_f345 _d1_reverify_followup _d1_reverify_probes _imp2_build
_m1_bak_probe _m1_deny_cost _m1_drift_probe _p14_floors _p14_manifest_verify
_proto3_probe_sem001_vs_sem012 _sub1_normalize_probe _synth_probe _synth_probe2 _wave1_floor_audit
_wave1_floor_audit2 _wave1_fork_probe _wave1_fork_probe_fast _wave1_mutation_control
_wave2_blindspot_check _wave2_floor_audit _wave2_floor_audit2 _wave2_floor_audit3
_wave2_floor_audit4 _wave2_floor_audit5 _wfa1_cross_unit_overlap _wfa1_final_check _wfa2b_probe
_wfa3_build_registry""".split()
claimed45 = [f"command-center/{n}.py" for n in claimed45]
pat = re.compile(r"^command-center/_[A-Za-z0-9_]+\.py$")
actual45 = sorted(x for x in tracked if pat.match(x))
out["dod2_45_probe_scripts"] = {
    "n_claimed": len(claimed45),
    "n_tracked_actual": len(actual45),
    "claimed_set_equals_tracked_set": sorted(claimed45) == actual45,
    "claimed_not_tracked": sorted(set(claimed45) - set(actual45)),
    "tracked_not_claimed": sorted(set(actual45) - set(claimed45)),
    "all_exist_on_disk": all((REPO / x).exists() for x in actual45),
    "n_missing_on_disk": len([x for x in actual45 if not (REPO / x).exists()]),
}

# worktree bytes == HEAD blob bytes  (no post-commit edit / no CRLF re-insertion)
mism = []
for rel in actual45:
    rc, so, _ = git("cat-file", "-p", f"HEAD:{rel}")
    blob = so
    disk = (REPO / rel).read_text(encoding="utf-8", errors="replace", newline="")
    # git returns the blob with LF; compare after normalising the disk copy's EOL
    if blob.replace("\r\n", "\n") != disk.replace("\r\n", "\n"):
        mism.append(rel)
out["dod2_worktree_matches_blob"] = {"n_mismatch": len(mism), "mismatched": mism[:5]}

# ---------- every slop-report artifact the builder claims ----------
claimed_sr = [
    "SLOP-BUILD-R1.md",
    "SLOP-REPORT.md",
    "_c4_commitmsg.txt",
    "_c5_commitmsg.txt",
    "_b9_commitmsg.txt",
    "_b1_cited_list.txt",
]
probes = [
    "_b1_cited_probes",
    "_b1_control",
    "_b2_ruff_surface",
    "_b2_blob_check",
    "_b3_head_blob_gate",
    "_b4_clone_gate",
    "_b5_digest_lock",
    "_b6_digest_match",
    "_b7_candidate_gate",
    "_b8_apply",
    "_c1_widen_probe",
    "_c2_final_census",
    "_c3_bucket_c_exec",
]
for p in probes:
    claimed_sr += [p + ".py", p + ".out.json"]
for i in ["", "2", "3", "4", "5", "6", "7"]:
    claimed_sr += [f"_slop_measure{i}.py", f"_slop_measure{i}.out.json"]
claimed_sr += ["_slop_verify_regen.py", "_slop_verify_regen.out.json"]

exists, missing, untracked_of_them = [], [], []
for n in claimed_sr:
    rel = f"command-center/slop-report/{n}"
    if (REPO / rel).exists():
        exists.append(n)
        if rel not in tracked:
            untracked_of_them.append(n)
    else:
        missing.append(n)
out["claimed_artifacts"] = {
    "n_claimed": len(claimed_sr),
    "n_exist": len(exists),
    "missing": missing,
    "exist_but_UNTRACKED": untracked_of_them,
}

# ---------- DoD1: four buckets present in the report, with evidence ----------
rep = (SR / "SLOP-BUILD-R1.md").read_text(encoding="utf-8", errors="replace")
out["dod1_report"] = {
    "bytes": len(rep),
    "has_bucket_a": bool(re.search(r"\(a\)", rep)),
    "has_bucket_b": bool(re.search(r"\(b\)", rep)),
    "has_bucket_c": bool(re.search(r"\(c\)", rep)),
    "has_bucket_d": bool(re.search(r"\(d\)", rep)),
    "n_bucket_headings": len(re.findall(r"BUCKET\s*\(?[abcd]\)?", rep, re.I)),
    "mentions_frozen": ("casualty/probes" in rep) and ("p2-wave/probes" in rep),
    "mentions_parallel_folders": bool(
        re.search(r"parallel|SSOT|dual-write", rep, re.I)
    ),
    "n_out_json_citations": len(re.findall(r"\.out\.json", rep)),
}

# ---------- deletions: did any lane commit delete a tracked file? ----------
dels = {}
for c in ["f5b596e6", "fa87d1a2", "ebe02d62"]:
    rc, so, _ = git("show", "--diff-filter=D", "--name-only", "--format=", c)
    dels[c] = [x for x in so.splitlines() if x.strip()]
out["dod2_no_tracked_deletions"] = {
    "per_commit": dels,
    "total": sum(len(v) for v in dels.values()),
}

# ---------- attribution of the 8 red files ----------
rc, so, _ = git("ls-files", "command-center/grounding/")
s2 = [
    x for x in so.splitlines() if re.match(r"^command-center/grounding/_s2_.*\.py$", x)
]
attrib = {}
for rel in s2:
    rc, so2, _ = git("log", "--format=%h", "--diff-filter=A", "--", rel)
    attrib[rel] = (so2.splitlines() or ["?"])[-1]
out["red_file_attribution"] = {"n_s2_py": len(s2), "added_by": attrib}

print(json.dumps(out, indent=2))
Path(__file__).with_suffix(".out.json").write_text(
    json.dumps(out, indent=2), encoding="utf-8", newline="\n"
)
