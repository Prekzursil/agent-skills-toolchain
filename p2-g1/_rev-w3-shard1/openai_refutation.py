#!/usr/bin/env python3
"""Cross-vendor openai refutation pass via the OpenRouter lane.

Why this lane: the codex CLI has no auth.json (`codex login status` -> Not
logged in; exec -> 401 "Missing bearer"), and the env OPENAI_API_KEY returns
HTTP 401 on api.openai.com. Both are reported, not repaired (credential
non-intervention). OPENROUTER_API_KEY is live; openai/gpt-5.1-codex is a
genuine openai-vendor Codex-family model, satisfying the catalog's
"Codex (openai) refuter" vendor requirement.

Refuter contract (per reviewer_requirement): re-derive the finding from the
RAW ARTIFACT and the RAW live probe outputs - NOT from any builder report or
receipt. This driver hands the model exactly those two things and nothing else.
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
OUTDIR = Path(__file__).resolve().parent / "openai_refutation"
OUTDIR.mkdir(exist_ok=True)
MODEL = "openai/gpt-5.1-codex"

UNITS = {
    "ADV-0040": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0091": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0096": ("probe1_live_gate.py", "probe2_semantic_space.py"),
    "ADV-0100": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0109": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0110": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0119": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
    "ADV-0123": ("probe1_delivery_predicate.py", "probe2_independent_recheck.py"),
}

PROMPT_TMPL = """You are an INDEPENDENT cross-vendor refutation reviewer for work-unit {uid} of a multi-agent verification program.

You did NOT build this unit; a different vendor's agent did. You are given exactly two raw materials and nothing else:
  1. The unit's RAW ARTIFACT (verbatim JSON below).
  2. The RAW stdout of the artifact's two named probe scripts, re-executed live this session by the reviewing harness (both exited 0).

No builder report, no receipt, no other agent's conclusions are shown to you.

Your job:
  a. From the artifact alone, state what its CENTRAL FINDING is, in one sentence, in your own words.
  b. Re-derive that finding from the evidence inside the artifact + probe outputs. Does the evidence actually support it?
  c. Check every per-target verdict you can see: is each one of {{CONFIRMED, REFUTED, PARTIAL, NOT-CHECKED, BLOCKED}} and actually supported?
  d. Check the negative controls / listed control tests: are their results recorded, and do any of them contradict the central finding?
  e. Adversarially try to REFUTE the central finding. Only if your own re-derivation fails do you report REFUTE.

Your FINAL line must be exactly one JSON object prefixed CODEX-VERDICT and nothing after it:
CODEX-VERDICT {{"unit_id":"{uid}","verdict":"AGREE|REFUTE|PARTIAL","probes_rerun":{{"probe1_exit":0,"probe2_exit":0}},"finding_rederived":"<one sentence>","objections":"<none, or the precise objection>"}}

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
    p = subprocess.run(
        [sys.executable, "-B", rel], cwd=str(REPO), capture_output=True,
        text=True, timeout=600, env=env)
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()[-6000:]


def artifact_rel(uid: str) -> Path:
    matches = sorted((REPO / "command-center" / "adversarial").glob(f"{uid}-*.json"))
    if not matches:
        raise FileNotFoundError(uid)
    return matches[0]


def call_openrouter(prompt: str) -> str:
    key = os.environ["OPENROUTER_API_KEY"]
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "usage": {"include": True},
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.loads(r.read())
    msg = d["choices"][0]["message"]["content"]
    usage = d.get("usage") or {}
    return msg, usage


def main() -> int:
    only = sys.argv[1:] or list(UNITS)
    results = {}
    for uid in only:
        p1, p2 = UNITS[uid]
        art_path = artifact_rel(uid)
        art_text = art_path.read_text(encoding="utf-8")
        c1, o1 = run_probe(uid, p1)
        c2, o2 = run_probe(uid, p2)
        if c1 != 0 or c2 != 0:
            results[uid] = {"error": f"probe exit codes {c1}/{c2}", "verdict": None}
            print(f"FAILED:probes {uid} rc={c1}/{c2}")
            continue
        prompt = PROMPT_TMPL.format(
            uid=uid, art_rel=art_path.relative_to(REPO).as_posix(),
            artifact=art_text[:120000], p1=p1, p2=p2,
            p1_out=o1, p2_out=o2)
        t0 = time.monotonic()
        try:
            msg, usage = call_openrouter(prompt)
        except Exception as exc:
            results[uid] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}", "verdict": None}
            print(f"FAILED:api {uid} {type(exc).__name__}")
            continue
        dt = time.monotonic() - t0
        m = re.search(r"CODEX-VERDICT\s*(\{.*\})", msg, re.S)
        verdict = None
        if m:
            try:
                verdict = json.loads(m.group(1))
            except json.JSONDecodeError:
                verdict = {"raw": m.group(1)[:400]}
        results[uid] = {
            "model": MODEL,
            "seconds": round(dt, 1),
            "usage": usage,
            "verdict": verdict,
            "message_tail": msg[-1500:],
            "probe_exits": [c1, c2],
        }
        v = (verdict or {}).get("verdict") if isinstance(verdict, dict) else None
        print(f"{'PASS' if v == 'AGREE' else 'NOTE'} {uid} codex-verdict={v} ({dt:.0f}s, "
              f"prompt~{len(prompt)//1000}KB)")
        (OUTDIR / f"{uid}.result.json").write_text(
            json.dumps(results[uid], indent=1), encoding="utf-8")
        (OUTDIR / f"{uid}.message.txt").write_text(msg, encoding="utf-8")
    (OUTDIR / "all_results.json").write_text(
        json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
