#!/usr/bin/env python3
"""Cross-vendor reviewer #2 via grok lane (codex 401-unavailable).
Sends the verbatim evidence bundle per unit; asks for an adversarial verdict.
Writes verdict-<UID>.txt next to this script."""
import json
import os
import sys
import urllib.request
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
HERE = REPO / "_review-shard1-w1"
BASE = os.environ.get("GROK_LANE_BASE", "http://127.0.0.1:8182/v1")
KEY = os.environ["GROK_LANE_KEY"]
MODEL = os.environ.get("GROK_LANE_MODEL", "grok-4.7")

UNITS = {
    "ADV-0132": {
        "artifact": "command-center/adversarial/ADV-0132-consensus-vs-test-divergence.json",
        "probe1": "command-center/p2-wave/probes/ADV-0132/probe1_preregistration_and_negative.py",
        "probe2": "command-center/p2-wave/probes/ADV-0132/probe2_mutation_and_independence.py",
    },
    "ARC-0013": {
        "artifact": "command-center/phase3/A2/SECURITY.json",
        "probe1": "command-center/p2-wave/probes/ARC-0013/probe1_planted_edit.py",
        "probe2": "command-center/p2-wave/probes/ARC-0013/probe2_whitespace.py",
    },
    "ARC-0020": {
        "artifact": "command-center/phase3/A3/SECURITY.json",
        "probe1": "command-center/p2-wave/probes/ARC-0020/probe1_path_coverage.py",
        "probe2": "command-center/p2-wave/probes/ARC-0020/probe2_negative_control.py",
    },
    "ARC-0048": {
        "artifact": "command-center/phase3/A7/SECURITY.json",
        "probe1": "command-center/p2-wave/probes/ARC-0048/probe1_markers.py",
        "probe2": "command-center/p2-wave/probes/ARC-0048/probe2_classification.py",
    },
}

HEADER = """You are CROSS-VENDOR REVIEWER #2 for estate program P2. Reviewer #1 (a different
vendor's model) already verified this unit; you must reach your OWN conclusion and
try to FAIL the unit. You cannot execute code, so reviewer #1's raw instrument
outputs are provided verbatim below; your value-add is independent judgment over
the evidence, especially internal contradictions the instruments might not check.

Checks already executed live (with raw outputs below):
  A. artifact exists/non-empty/parses; no state/status/verdict/result field self-declares BLOCKED/FAILED; no UNIT-INCOMPLETE marker; parked absent; no open P0/P1 defects
  B. both named probes re-run live, exit 0
  C. artifact sha256 (CRLF->LF normalized) matches UNIT-ARTIFACT-MANIFEST.json primary row (hash + byte count)
  D. catalog completion_sentinel starts with SUCCESS:<id>; conditions verified
  E. out-of-scope note: JSON-Schema artifact-class profile conformance is a recorded program-wide gap, NOT part of your verdict

Your job: read the ARTIFACT below and answer
  1) do its own recorded observations/probe outputs contradict its claims anywhere?
  2) do the live probe outputs actually support the artifact's verdict fields?
  3) anything that looks like a rigged instrument, a vacuous pass, or a claim without evidence?

Respond with EXACTLY:
VERDICT: PASS   (or VERDICT: FAIL)
REASONS:
1. ...
2. ...

=== UNIT: <UID> ===
=== CATALOG completion_sentinel ===
<sentinel>
=== MANIFEST primary row ===
<manifest_row>
=== LIVE PROBE OUTPUTS (verbatim tails) ===
<probe_tails>
=== ARTIFACT (verbatim JSON) ===
<artifact>
"""


def chat(prompt: str) -> str:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 2000,
    }
    req = urllib.request.Request(
        BASE + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + KEY},
    )
    with urllib.request.urlopen(req, timeout=600) as fh:
        resp = json.loads(fh.read().decode("utf-8"))
    return resp["choices"][0]["message"]["content"]


def main():
    out = {}
    for uid, spec in UNITS.items():
        art_p = REPO / spec["artifact"]
        artifact = art_p.read_text(encoding="utf-8")
        cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
        units = dict((u["id"], u) for u in cat["work_units"])
        sentinel = units[uid].get("completion_sentinel", "")
        mf = json.loads((REPO / ("command-center/p2-wave/probes/" + uid + "/UNIT-ARTIFACT-MANIFEST.json")).read_text(encoding="utf-8"))
        row = next((a for a in mf.get("artifacts", []) if a.get("role") == "primary"), {})
        rer = json.loads((HERE / "probe_rerun_out.json").read_text(encoding="utf-8"))
        tails = "\n\n".join(
            "--- " + k + " (exit " + str(rer[k]["exit_code"]) + ") ---\n" + rer[k]["tail"]
            for k in (uid + "/probe1", uid + "/probe2") if k in rer
        )
        prompt = (HEADER
                  .replace("<UID>", uid)
                  .replace("<sentinel>", sentinel[:400])
                  .replace("<manifest_row>", json.dumps(row))
                  .replace("<probe_tails>", tails[:6000])
                  .replace("<artifact>", artifact[:90000]))
        try:
            verdict = chat(prompt)
        except Exception as e:
            verdict = "ERROR: " + str(e)[:300]
        (HERE / "codex" / ("verdict-" + uid + ".txt")).write_text(verdict, encoding="utf-8", newline="\n")
        out[uid] = verdict[:400]
        print(uid, "=>", verdict[:150].replace("\n", " "), flush=True)
    (HERE / "grok_verdicts.json").write_text(json.dumps(out, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
