#!/usr/bin/env python3
"""CC-0016 PROBE 2: regeneration -- gate silent on the derived fields recomputed
from the AUTHORED edges/phases arrays; honest measurement that TRUE regeneration
from the external spec-prose source is not possible in this environment.

PHASE-GRAPH.json's own ``source_spec.path`` is
``C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md`` -- a
Windows-local absolute path on a different machine than this one. This probe
measures, on THIS machine, that the file is absent everywhere on disk, so
byte-for-byte re-derivation from the cited external source (the AUD-0040 style
of "regeneration") is not a question this environment can answer. That is
recorded as a residual_unknown in the receipt, not silently worked around.

What this probe DOES measure, honestly: phase_graph_gate.py's ``compute()``
recomputes edge_count / hard_edge_count / soft_edge_count / critical_path
purely from the sidecar's own ``phases``/``edges`` arrays (the AUTHORED
material). Running that recomputation against the live, unmodified sidecar and
finding zero violations is the closest available "regeneration is silent"
proof: the derived summary has not drifted from the hand-authored edge list it
claims to summarize.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
GATE = REPO / "command-center/p2-wave/probes/CC-0016/phase_graph_gate.py"
LIVE_GRAPH = REPO / "command-center/PHASE-GRAPH.json"
OUT_JSON = Path(__file__).resolve().parent / "probe2-regeneration-silent.json"
OUT_RAW = Path(__file__).resolve().parent / "probe2-regeneration-silent.raw.txt"


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    lines: list[str] = []
    lines.append("CC-0016 PROBE2 regeneration-silent + source-availability measurement")
    lines.append(f"REPO={REPO}")

    data = json.loads(LIVE_GRAPH.read_text(encoding="utf-8"))
    src = data.get("source_spec", {}) if isinstance(data.get("source_spec"), dict) else {}
    src_path = str(src.get("path", ""))
    lines.append(f"CITED_SOURCE_SPEC_PATH={src_path!r}")

    rc_find, out_find = run(["find", "/", "-iname", "_USER-PROMPTS.md"])
    hits = [
        ln
        for ln in out_find.splitlines()
        if ln.strip() and not ln.startswith("find:")
    ]
    source_present_anywhere = len(hits) > 0
    lines.append(
        f"SOURCE_FILE_SEARCH find / -iname _USER-PROMPTS.md -> hits={len(hits)} {hits}"
    )
    lines.append(
        f"TRUE_BYTE_REGENERATION_FROM_EXTERNAL_SOURCE_POSSIBLE={source_present_anywhere}"
    )

    # Regeneration proxy: recompute derived fields from the AUTHORED edges/phases
    # and confirm the gate is silent against the live, unmodified sidecar.
    rc_gate, out_gate = run([sys.executable, "-B", str(GATE), "--graph", str(LIVE_GRAPH)])
    lines.append(f"GATE_ON_LIVE_UNMODIFIED exit={rc_gate}")
    lines.append("  | " + out_gate.strip().replace("\n", "\n  | "))
    gate_silent = rc_gate == 0

    # Gate silence on the live, unmodified sidecar is the thing this probe
    # proves; source-file absence is disclosed as a residual scope note, not
    # folded into the pass/fail condition (that would misrepresent an
    # environment limitation as a measured success or failure of the gate).
    ok = gate_silent

    summary = {
        "cited_source_spec_path": src_path,
        "source_file_present_on_this_machine": source_present_anywhere,
        "true_external_regeneration_possible": source_present_anywhere,
        "derived_field_regeneration_gate_exit_code": rc_gate,
        "derived_field_regeneration_gate_silent": gate_silent,
        "ok": ok,
        "scope_note": (
            "Regeneration here means recomputing edge_count/hard_edge_count/"
            "soft_edge_count/critical_path from the sidecar's own authored "
            "phases[]/edges[] arrays, NOT re-deriving those arrays from the "
            "external spec prose (which is absent on this machine). This is a "
            "disclosed scope reduction, not an invented pass."
        ),
    }
    lines.append(f"PROBE2_OK={ok}")
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
