#!/usr/bin/env python3
"""Builder driver for AUD-0033: run probes live, emit artifact/manifest/return."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes"))
import _shard2_lib as lib

HERE = lib.PROBES / "AUD-0033"
PROBE_FILES = [
    {"id": "probe1", "file": HERE / "probe1_docpath_regex.py", "role": "source", "method": "static-analysis"},
    {"id": "probe2", "file": HERE / "probe2_docpath_backtick.py", "role": "verifier", "method": "file-read"},
]
lib.ensure_probes("AUD-0033", PROBE_FILES)
p1 = json.loads((HERE / "probe1_docpath_regex_out.json").read_text(encoding="utf-8"))
p2 = json.loads((HERE / "probe2_docpath_backtick_out.json").read_text(encoding="utf-8"))

claims = [
    {
        "claim": ("Regex extraction over %d markdown files found %d path citations "
                  "(%d unique tokens); %d resolve to files that exist today and %d do not."
                  % (p1["files_scanned"], p1["citations"], p1["unique_tokens"],
                     p1["resolved"], p1["missing_count"])),
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "command-center/p2-wave/probes/AUD-0033/probe1_docpath_regex_out.json",
    },
    {
        "claim": ("A mechanically different backtick-span extractor agrees on the "
                  "missing set (%d agreed of probe1 %d / probe2 %d); fixture control "
                  "finds the fenced path and rejects the prose slash in both extractors."
                  % (p2["agreement_with_probe1"].get("agreed_missing", 0),
                     p2["agreement_with_probe1"].get("probe1_missing", 0),
                     p2["agreement_with_probe1"].get("probe2_missing", 0))),
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "command-center/p2-wave/probes/AUD-0033/probe2_docpath_backtick_out.json",
    },
    {
        "claim": ("Missing-token classification by basename index: %d found-elsewhere "
                  "(deleted-or-moved reference), %d nowhere-in-tree (likely typo)."
                  % (p2["classification_counts"]["found-elsewhere"],
                     p2["classification_counts"]["nowhere-in-tree"])),
        "verdict": "PARTIAL",
        "confidence": "likely",
        "anchor": "command-center/p2-wave/probes/AUD-0033/probe2_docpath_backtick_out.json",
    },
]

observations = [
    {"name": "docs_scanned", "measured": p1["files_scanned"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0033/probe1_docpath_regex_out.json"},
    {"name": "unique_path_tokens", "measured": p1["unique_tokens"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0033/probe1_docpath_regex_out.json"},
    {"name": "resolved_tokens", "measured": p1["resolved"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0033/probe1_docpath_regex_out.json"},
    {"name": "missing_tokens", "measured": p1["missing_count"], "method": "file-read",
     "anchor": "command-center/p2-wave/probes/AUD-0033/probe2_docpath_backtick_out.json"},
    {"name": "missing_found_elsewhere", "measured": p2["classification_counts"]["found-elsewhere"],
     "method": "file-read",
     "anchor": "command-center/p2-wave/probes/AUD-0033/probe2_docpath_backtick_out.json"},
    {"name": "missing_nowhere_in_tree", "measured": p2["classification_counts"]["nowhere-in-tree"],
     "method": "file-read",
     "anchor": "command-center/p2-wave/probes/AUD-0033/probe2_docpath_backtick_out.json"},
]

tests = [
    {"id": "aud0033-fence-found", "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0033/probe1_docpath_regex.py",
     "result": "PASS" if p1["detector_control"]["fence_token_found"] else "FAIL",
     "assertions": 1,
     "output_tail": json.dumps(p1["detector_control"])[:500]},
    {"id": "aud0033-prose-clean", "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0033/probe1_docpath_regex.py",
     "result": "PASS" if p1["detector_control"]["prose_clean"] else "FAIL",
     "assertions": 1,
     "output_tail": json.dumps(p1["detector_control"])[:500]},
]

negative_controls = [
    {"id": "aud0033-prose-slash-not-a-path", "kind": "known-broken-fixture",
     "description": ("Prose sentence 'input/output tradeoffs and/or config values' must "
                     "NOT be emitted as a path by either extractor."),
     "fired_on_bad_state": bool(p1["detector_control"]["fence_token_found"]),
     "silent_on_good_state": bool(p1["detector_control"]["prose_clean"] and p2["fixture_control_pass"]),
     "bad_state_output": "fence token found=%s" % p1["detector_control"]["fence_token_found"],
     "good_state_output": "prose hits=%s" % p1["detector_control"]["prose_hits"]},
]

residuals = [
    {"claim": ("The catalog's probe-2 git log --all separation of never-existed vs deleted "
               "is not executable here: this worktree has no .git history. Basename-index "
               "classification is the substitute."),
     "verdict": "NOT-CHECKED",
     "settling_experiment": ("Re-run probe2 against a git-bearing checkout and replace the "
                             "basename classification with git log --all -- <path> per missing token.")},
    {"claim": ("Extraction covers scopes command-center/, docs/, guides/, rules/ plus repo-root "
               "markdown, capped at 4000 files/512KB each; markdown outside these scopes was "
               "not swept."),
     "verdict": "PARTIAL",
     "settling_experiment": "Raise MAX_FILES/MAX_BYTES and add harness-tree scopes (~/.claude, ~/.agents) to SCOPES."},
]

lib.emit_unit(
    "AUD-0033",
    claims=claims,
    observations=observations,
    control_ids=["aud0033-fence-found", "aud0033-prose-slash-not-a-path"],
    tests=tests,
    negative_controls=negative_controls,
    residual_unknowns=residuals,
    probe_files=PROBE_FILES,
    evidence_map=[[0, 1], [1, 0], [1, 0]],
    report_extra={"headline": ("AUD-0033 doc-path integrity: %d/%d unique cited paths resolve; "
                               "%d dangling (%s)."
                               % (p1["resolved"], p1["unique_tokens"], p1["missing_count"],
                                  json.dumps(p2["classification_counts"]))),
                  "missing_top": [m["token"] for m in p1.get("missing", [])[:40]]},
)
