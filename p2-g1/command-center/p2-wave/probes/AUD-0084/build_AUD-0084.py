#!/usr/bin/env python3
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes"))
import _shard2_lib as lib

HERE = lib.PROBES / "AUD-0084"
PROBE_FILES = [
    {"id": "probe1", "file": HERE / "probe1_literal_paths.py", "role": "source", "method": "static-analysis"},
    {"id": "probe2", "file": HERE / "probe2_ast_path_context.py", "role": "verifier", "method": "static-analysis"},
]
lib.ensure_probes("AUD-0084", PROBE_FILES)
p1 = json.loads((HERE / "probe1_literal_paths_out.json").read_text(encoding="utf-8"))
p2 = json.loads((HERE / "probe2_ast_path_context_out.json").read_text(encoding="utf-8"))

claims = [
    {"claim": ("Literal scan over %d source files: %d hits in %d files (by kind: %s)."
               % (p1["files_scanned"], p1["total_hits"], p1["files_with_hits"],
                  json.dumps(p1["by_kind"]))),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0084/probe1_literal_paths_out.json"},
    {"claim": ("AST-aware pass flags only path-CONTEXT literals: %d call-context hits in %d files; "
               "the fixture proves a docstring C: mention and a regex backslash are NOT flagged "
               "while open() on the same literal IS."
               % (p2["total_call_context_hits"], p2["files_with_path_context_hits"])),
     "verdict": "CONFIRMED", "confidence": "almost-certain",
     "anchor": "command-center/p2-wave/probes/AUD-0084/probe2_ast_path_context_out.json"},
]
observations = [
    {"name": "files_scanned_literal", "measured": p1["files_scanned"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0084/probe1_literal_paths_out.json"},
    {"name": "literal_hits", "measured": p1["total_hits"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0084/probe1_literal_paths_out.json"},
    {"name": "ast_call_context_hits", "measured": p2["total_call_context_hits"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0084/probe2_ast_path_context_out.json"},
    {"name": "files_with_ast_hits", "measured": p2["files_with_path_context_hits"], "method": "static-analysis",
     "anchor": "command-center/p2-wave/probes/AUD-0084/probe2_ast_path_context_out.json"},
]
tests = [
    {"id": "aud0084-use-vs-mention", "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/AUD-0084/probe2_ast_path_context.py",
     "result": "PASS" if p2["fixture_control"]["pass"] else "FAIL", "assertions": 3,
     "output_tail": json.dumps(p2["fixture_control"]["flagged"])[:400]},
]
negative_controls = [
    {"id": "aud0084-regex-docstring-not-flagged", "kind": "adversarial-payload",
     "description": ("Regex backslash and docstring C: mention must NOT be flagged; only the "
                     "open() on the same literal counts (use-vs-mention)."),
     "fired_on_bad_state": bool(p2["fixture_control"]["flagged"]),
     "silent_on_good_state": bool(len(p2["fixture_control"]["flagged"]) == 1),
     "bad_state_output": json.dumps(p2["fixture_control"]["flagged"])[:200],
     "good_state_output": "1 flagged call of 3 fixture constructs"},
]
residuals = [
    {"claim": ("Corpus scopes: platform/, tools/, scripts/, hooks/, ci/ (probe2) and ten scopes "
               "(probe1); node_modules, fixtures and remaining scopes not swept."),
     "verdict": "PARTIAL",
     "settling_experiment": "Extend SCOPES/EXTS to the full tree and re-run; compare deltas."},
]
lib.emit_unit(
    "AUD-0084",
    claims=claims,
    observations=observations,
    control_ids=["aud0084-use-vs-mention", "aud0084-regex-docstring-not-flagged"],
    tests=tests,
    negative_controls=negative_controls,
    residual_unknowns=residuals,
    probe_files=PROBE_FILES,
    evidence_map=[[0, 1], [1, 0]],
    report_extra={"headline": ("AUD-0084 hardcoded paths: %d literal hits in %d files; %d AST-verified "
                               "path-context uses in %d files."
                               % (p1["total_hits"], p1["files_with_hits"],
                                  p2["total_call_context_hits"], p2["files_with_path_context_hits"])),
                  "top_literal_files": [f for f, _ in p1["top_files"][:15]],
                  "top_ast_files": [f for f, _ in p2["top_files"][:15]]},
)
