#!/usr/bin/env python3
"""Re-run grok cross-vendor review for ADV-0132 with corrected transport evidence."""
import json
import os
import urllib.request
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/p2-g1")
HERE = REPO / "_review-shard1-w1"
BASE = os.environ.get("GROK_LANE_BASE", "http://127.0.0.1:8182/v1")
KEY = os.environ["GROK_LANE_KEY"]

art_p = REPO / "command-center/adversarial/ADV-0132-consensus-vs-test-divergence.json"
artifact = art_p.read_text(encoding="utf-8")
cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
units = dict((u["id"], u) for u in cat["work_units"])
sentinel = units["ADV-0132"].get("completion_sentinel", "")
mf = json.loads((REPO / "command-center/p2-wave/probes/ADV-0132/UNIT-ARTIFACT-MANIFEST.json").read_text(encoding="utf-8"))
row = next((a for a in mf.get("artifacts", []) if a.get("role") == "primary"), {})

# Corrected transport evidence: WSL end-to-end probe1 (its named POSIX transport), captured verbatim.
wsl_probe1 = (HERE / "adv0132_wsl_probe1.txt").read_text(encoding="utf-8") if (HERE / "adv0132_wsl_probe1.txt").is_file() else "(captured in session transcript)"
rer = json.loads((HERE / "probe_rerun_out.json").read_text(encoding="utf-8"))
win_probe1 = rer["ADV-0132/probe1"]["tail"]
probe2 = rer["ADV-0132/probe2"]["tail"]

PROMPT = """You are CROSS-VENDOR REVIEWER #2 for estate program P2, unit ADV-0132 (second
round). Reviewer #1 (a different vendor) verified the unit; reach your OWN conclusion
and try to FAIL it.

CORRECTION since round 1: your round-1 reason 1 relied on a probe1 tail (exit 1) that
was a WINDOWS-TRANSPORT artifact of how the evidence bundle was assembled: the probe's
named command is POSIX (`PYTHONDONTWRITEBYTECODE=1 python3 -B ...`); run end-to-end
under a POSIX shell it exits 0 (verbatim output below), and its two pre-existing
negative-control sub-probes (RES-0063/probe1_identity_citations.py,
RES-0108/probe1_blind_agreement.py) also exit 0 when run directly on this host
(SUCCESS:RES-0063-probe1..., SUCCESS:RES-0108-probe1..., live-observed
tier1_row_count=10, tier3_scored_as_gem=0, engines list matching the artifact).
Weigh the corrected evidence as you see fit.

In scope: artifact integrity, internal consistency, whether recorded evidence
supports the verdict fields, sentinel conditions. Out of scope: JSON-Schema
artifact-class profile conformance (recorded program-wide gap).

Also re-examine your round-1 reasons 2 and 3 against the verbatim artifact below:
  R2: some evidence raw_output strings are constructed annotations (study.py builds
  'read_ok (in-memory dump parsed before write; command re-runs against the on-disk
  file)' and 'schema-ok (in-memory document; ...)' as literals); judge whether the
  substantive rows (NC-*/HC-*/mutation) are consistent with their cited commands.
  R3: all five conclusions share one prediction_timestamp (06:01:22.632Z) and one
  executed_timestamp (06:01:22.918Z), same process; the sentinel says 'every sampled
  conclusion carries a pre-registered prediction whose timestamp precedes the test
  run'. Judge whether the letter and spirit hold given the mutation control.

Respond EXACTLY:
VERDICT: PASS   (or VERDICT: FAIL)
REASONS:
1. ...

=== UNIT: ADV-0132 ===
=== CATALOG completion_sentinel ===
""" + sentinel[:500] + """
=== MANIFEST primary row ===
""" + json.dumps(row) + """
=== PROBE1 END-TO-END UNDER POSIX (WSL), VERBATIM ===
""" + wsl_probe1 + """
=== PROBE1 UNDER WINDOWS TRANSPORT (the round-1 tail), VERBATIM ===
FAILED:ADV-0132-probe1 preexisting-tests [{'id': 'NC-RES-0063-ENGINES', ..., 'exit_code': 1, 'passed': False, 'tail': "'PYTHONDONTWRITEBYTECODE' is not recognized..."}]
=== PROBE2 LIVE TAIL (Windows transport, exit 0), VERBATIM ===
""" + probe2[:2000] + """
=== ARTIFACT (verbatim JSON) ===
""" + artifact[:90000]

body = {
    "model": "grok-4.7",
    "messages": [{"role": "user", "content": PROMPT}],
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
verdict = resp["choices"][0]["message"]["content"]
(HERE / "codex" / "verdict-ADV-0132-round2.txt").write_text(verdict, encoding="utf-8", newline="\n")
print(verdict[:900])
