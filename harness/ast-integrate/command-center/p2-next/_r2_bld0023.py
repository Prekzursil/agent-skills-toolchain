"""ROUND-2: read BLD-0023 in full from the COMMITTED blob before accepting that the rule-D gate
moves it to SATISFIABLE. Also print the audit's CROSS-token hits on its operative text, because
the auditor's conservative classifier and my gated ladder DISAGREE on this one unit -- resolve
from the raw text, never by vote.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CROSS = re.compile(
    r"cross[-_ ]?vendor|cross[-_ ]?model|different\s+vendor|other\s+vendor|separate\s+vendor"
    r"|\bopenai\b|\bcodex\b|gpt-?5|non[-_ ]?anthropic",
    re.I,
)

cat = json.loads(
    subprocess.run(
        ["git", "show", "HEAD:command-center/WORK-UNIT-CATALOG.json"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
)
u = next(x for x in cat["work_units"] if x["id"] == "BLD-0023")
print("catalog output_path      :", u["output_path"])
print("catalog assigned         :", json.dumps(u.get("assigned_model_vendor_role")))
print("catalog reviewer_req     :", u.get("reviewer_requirement"))
print(
    "  CROSS hits in req      :",
    sorted(
        {
            m.group(0).lower()
            for m in CROSS.finditer(u.get("reviewer_requirement") or "")
        }
    ),
)

rec = json.loads(
    subprocess.run(
        ["git", "show", f"HEAD:{u['output_path']}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
)
print("\nstate        :", rec.get("state"))
print("produced_by  :", json.dumps(rec.get("produced_by")))
print("reviewer     :", json.dumps(rec.get("reviewer"))[:400])
f = rec.get("failure") or {}
print("\nfailure.classification:", json.dumps(f.get("classification")))
bo = f.get("blocked_on") or ""
print(f"\nfailure.blocked_on ({len(bo)} chars), VERBATIM:\n{bo}")
print(
    "\n  CROSS hits in blocked_on:",
    sorted({m.group(0).lower() for m in CROSS.finditer(bo)}),
)
for k, v in f.items():
    if k in ("blocked_on", "classification"):
        continue
    s = v if isinstance(v, str) else json.dumps(v)
    hits = sorted({m.group(0).lower() for m in CROSS.finditer(s)})
    print(f"  failure.{k}: CROSS hits {hits}  :: {s[:220]}")

print("\n--- top-level keys ---", list(rec.keys()))
for k in (
    "summary",
    "evidence",
    "notes",
    "completion_sentinel",
    "manifest_registration",
):
    if k in rec:
        s = json.dumps(rec[k])
        print(f"{k}: {s[:300]}")
