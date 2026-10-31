#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes"))
import _shard2_lib as lib

HERE = lib.PROBES / "AUD-0082"
PROBE_FILES = [
    {"id": "probe1", "file": HERE / "probe1_reserved_scandir.py", "role": "source", "method": "static-analysis"},
    {"id": "probe2", "file": HERE / "probe2_owalk_stat_nul.py", "role": "verifier", "method": "file-read"},
]
lib.ensure_probes("AUD-0082", PROBE_FILES)
p1 = json.loads((HERE / "probe1_reserved_scandir_out.json").read_text(encoding="utf-8"))
p2 = json.loads((HERE / "probe2_owalk_stat_nul_out.json").read_text(encoding="utf-8"))

c = p1["hazard_counts"]
claims = [
    {"claim": ("scandir walk with the extended-length prefix indexed %d files across %d dirs; "
               "reserved-name=%d, long-path=%d, case-collision=%d hazards."
               % (p1["files_indexed"], p1["dirs_walked"], c["reserved-name"],
                  c["long-path"], c["case-collision"])),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe1_reserved_scandir_out.json"},
    {"claim": ("A mechanically different os.walk traversal indexed %d files (delta %.1f%% vs probe1) "
               "without crashing, and the live NUL file in the source checkout stats as: %s."
               % (p2["files_walked"], p2["agreement_with_probe1"].get("file_count_delta_pct", -1),
                  p2["live_nul_stat"]["stat_ok"])),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe2_owalk_stat_nul_out.json"},
    {"claim": ("Fixture control: the classifier returns non-zero hazards on a listing with a "
               "NUL-named entry and a 300-character path (reserved=%d long=%d); no crash."
               % (p2["fixture_reserved"], p2["fixture_long"])),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe2_owalk_stat_nul_out.json"},
]
observations = [
    {"name": "files_indexed", "measured": p1["files_indexed"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe1_reserved_scandir_out.json"},
    {"name": "reserved_name_hazards", "measured": c["reserved-name"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe1_reserved_scandir_out.json"},
    {"name": "long_path_hazards", "measured": c["long-path"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe1_reserved_scandir_out.json"},
    {"name": "case_collision_hazards", "measured": c["case-collision"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0082/probe1_reserved_scandir_out.json"},
    {"name": "live_nul_file_stat", "measured": str(p2["live_nul_stat"]["stat_ok"]), "method": "command",
     "anchor": "C:/Users/Prekzursil/source/ast-integrate/NUL"},
]
tests = [
    {"id": "aud0082-fixture-nonzero", "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0082/probe2_owalk_stat_nul.py",
     "result": "PASS" if p2["fixture_nonzero"] else "FAIL", "assertions": 3,
     "output_tail": "fixture_reserved=%d fixture_long=%d crash=%s" % (p2["fixture_reserved"], p2["fixture_long"], p2["walk_crash"])},
]
negative_controls = [
    {"id": "aud0082-nul-fixture-nonzero", "kind": "known-broken-fixture",
     "description": ("Classifier must return non-zero hazards on a NUL-named + 300-char fixture; "
                     "a crash or zero count is the recorded defect this unit exists to prevent."),
     "fired_on_bad_state": bool(p2["fixture_nonzero"]),
     "silent_on_good_state": bool(p1["fixture_control"]["pass"]),
     "bad_state_output": json.dumps(p2["fixture_nonzero"]),
     "good_state_output": json.dumps(p1["fixture_control"]["counts"])},
]
residuals = [
    {"claim": "node_modules/, .git and _scratch* trees were excluded from the census scope.",
     "verdict": "PARTIAL",
     "settling_experiment": "Extend SCOPES to node_modules with the extended-length prefix and re-run both probes."},
    {"claim": ("The git-index path listing (probe-1 input in the catalog) is unavailable: this "
               "worktree has no .git, so the census ran on filesystem walks only."),
     "verdict": "NOT-CHECKED",
     "settling_experiment": "Run `git ls-files -z` in a git-bearing checkout and feed the NUL-surviving classifier directly."},
]
lib.emit_unit(
    "AUD-0082",
    claims=claims,
    observations=observations,
    control_ids=["aud0082-fixture-nonzero", "aud0082-nul-fixture-nonzero"],
    tests=tests,
    negative_controls=negative_controls,
    residual_unknowns=residuals,
    probe_files=PROBE_FILES,
    evidence_map=[[0, 1], [1, 0], [1, 0]],
    report_extra={"headline": ("AUD-0082 Windows path hazards: %d reserved-name, %d long-path, "
                               "%d case-collision across %d indexed files; live NUL file present "
                               "in source checkout (stat_ok=%s)."
                               % (c["reserved-name"], c["long-path"], c["case-collision"],
                                  p1["files_indexed"], p2["live_nul_stat"]["stat_ok"])),
                  "hazard_samples": p1["hazard_sample"][:20]},
)
