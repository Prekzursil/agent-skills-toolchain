#!/usr/bin/env python3
"""Second-vendor (xai grok-4.7 via grok-lane) refutation pass for the three
units whose catalog reviewer_requirement asks for "two reviewers from DIFFERENT
vendors" (ADV-0096, ADV-0119, ADV-0123).

Reviewer 1 = Claude opus 5.5 (Anthropic) - this session's independent battery.
Reviewer 2 = grok-4.7 (xai, via grok-lane 127.0.0.1:8182) - re-derives the
central finding from the RAW ARTIFACT + freshly captured RAW probe outputs.
No builder report or receipt is shown to the model.

The openai-vendor lane was attempted first and is DOWN (codex CLI: no
auth.json -> 401; OPENAI_API_KEY -> 401; svcacct key -> 401 incorrect;
OpenRouter -> 402 insufficient credits). Evidence in _rev-w3-shard1/. The
requirement names no specific vendor pair, so Anthropic + xai satisfies it;
deviations from the named-lane preference are recorded in the receipt notes.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
OUTDIR = Path(__file__).resolve().parent / "grok_refutation"
OUTDIR.mkdir(exist_ok=True)
BASE = os.environ.get("GROK_LANE_BASE", "http://127.0.0.1:8182/v1")
MODEL = "grok-4.7"

UNITS = {
    "ADV-0096": ("probe1_live_gate.py", "probe2_semantic_space.py"),
    "ADV-0119": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0123": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
}

PROMPT_TMPL = """You are an INDEPENDENT second-vendor refutation reviewer for work-unit {uid} of a multi-agent verification program. The catalog requires two reviewers from DIFFERENT vendors to each independently reproduce the unit's counterexample; reviewer 1 (a different vendor from you) has already run a full independent battery.

You did NOT build this unit. You are given exactly two raw materials and nothing else:
  1. The unit's RAW ARTIFACT (verbatim JSON below).
  2. The RAW stdout of the artifact's two named probe scripts, re-executed live this session (both exited 0).

No builder report, no receipt, no other reviewer's conclusions are shown to you.

Your job:
  a. From the artifact alone, state what its CENTRAL FINDING is, in one sentence, in your own words.
  b. Re-derive that finding from the evidence inside the artifact + probe outputs. Does the evidence actually support it?
  c. Check every per-target verdict you can see: is each one of {{CONFIRMED, REFUTED, PARTIAL, NOT-CHECKED, BLOCKED}} and actually supported?
  d. Check the negative controls / listed control tests: are their results recorded, and do any contradict the central finding?
  e. Adversarially try to REFUTE the central finding. Only if your own re-derivation fails do you report REFUTE.

Your FINAL line must be exactly one JSON object prefixed GROK-VERDICT and nothing after it:
GROK-VERDICT {{"unit_id":"{uid}","verdict":"AGREE|REFUTE|PARTIAL","finding_rederived":"<one sentence>","objections":"<none, or the precise objection>"}}

=== RAW ARTIFACT ({art_rel}) ===
{artifact}

=== RAW PROBE OUTPUTS (re-executed this session, exit 0) ===
--- probe1 ({p1}) exit=0 ---
{p1_out}

--- probe2 ({p2}) exit=0 ---
{p2_out}
"""


def run_probe(uid: str, script: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.setdefault("AST_INTEGRATE_ROOT", str(REPO))
    rel = f"command-center/p2-wave/probes/{uid}/{script}"
    p = subprocess.run([sys.executable, "-B", rel], cwd=str(REPO),
                       capture_output=True, text=True, timeout=600, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[-6000:]


def call_grok(prompt: str) -> tuple[str, dict]:
    key = os.environ["GROK_LANE_KEY"]
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"]["content"], d.get("usage") or {}


def main() -> int:
    only = sys.argv[1:] or list(UNITS)
    results = {}
    for uid in only:
        p1, p2 = UNITS[uid]
        matches = sorted((REPO / "command-center" / "adversarial").glob(f"{uid}-*.json"))
        if not matches:
            print(f"FAILED:artifact-not-found {uid}")
            continue
        art_rel = matches[0].relative_to(REPO).as_posix()
        art_text = matches[0].read_text(encoding="utf-8")
        c1, o1 = run_probe(uid, p1)
        c2, o2 = run_probe(uid, p2)
        if c1 != 0 or c2 != 0:
            results[uid] = {"error": f"probe exit {c1}/{c2}", "verdict": None}
            print(f"FAILED:probes {uid} rc={c1}/{c2}")
            continue
        prompt = PROMPT_TMPL.format(uid=uid, art_rel=art_rel, artifact=art_text[:120000],
                                    p1=p1, p2=p2, p1_out=o1, p2_out=o2)
        t0 = time.monotonic()
        try:
            msg, usage = call_grok(prompt)
        except Exception as exc:
            results[uid] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "verdict": None}
            print(f"FAILED:api {uid} {type(exc).__name__}: {str(exc)[:120]}")
            continue
        dt = time.monotonic() - t0
        m = re.search(r"GROK-VERDICT\s*(\{.*\})", msg, re.S)
        verdict = None
        if m:
            try:
                verdict = json.loads(m.group(1))
            except json.JSONDecodeError:
                verdict = {"raw": m.group(1)[:400]}
        results[uid] = {"model": MODEL, "seconds": round(dt, 1), "usage": usage,
                        "verdict": verdict, "message_tail": msg[-1500:],
                        "probe_exits": [c1, c2]}
        v = (verdict or {}).get("verdict") if isinstance(verdict, dict) else None
        print(f"{'PASS' if v == 'AGREE' else 'NOTE'} {uid} grok-verdict={v} ({dt:.0f}s)")
        (OUTDIR / f"{uid}.result.json").write_text(json.dumps(results[uid], indent=1),
                                                   encoding="utf-8")
        (OUTDIR / f"{uid}.message.txt").write_text(msg, encoding="utf-8")
    (OUTDIR / "all_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
