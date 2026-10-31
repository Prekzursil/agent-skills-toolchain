#!/usr/bin/env python3
"""TST-0113 probe2 -- rubric re-scored on captured text + live refuse-path re-trigger.

Resumes the reviewer-closed receipt: (1) every recorded path's rubric is
recomputed from the captured text (never from source); (2) the bare-message
negative control must still score below PASS; (3) the LIVE client_negotiate
surface is re-triggered and every live refusal message must score 3/3.
Live-vs-recorded drift is reported, not hidden.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
RECEIPT = REPO / "command-center/receipts/TST-0113.json"

FAILS: list[str] = []


def chk(ok: bool, label: str, detail: object = "") -> None:
    if not ok:
        FAILS.append(label + (": " + str(detail) if detail != "" else ""))


def rubric(text: str) -> dict:
    t = text.lower()
    what = any(w in t for w in ("version", "client", "manifest", "registry", "install refused"))
    why = any(w in t for w in ("unparsable", "below", "not-a-semver", "not in", "empty", "missing", "is below", "unsupported"))
    remedy = "required" in t
    parts = {"what": what, "why": why, "remedy": remedy}
    return {"parts": parts, "pass": all(parts.values()), "score": sum(parts.values()), "max": 3, "scored_from": "captured-text"}


def main() -> int:
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    paths = doc.get("triggered_paths") or []
    chk(len(paths) == 5, "paths!=5", len(paths))
    reasons = []
    for row in paths:
        cap = str(row.get("captured_text") or "")
        lib = str(row.get("library_text") or "")
        chk(cap == lib, "captured!=library", row.get("id"))
        chk(row.get("cli_exit_code") == 1, "exit-not-1", row.get("id"))
        rc = rubric(cap)
        rec = (row.get("rubric") or {})
        chk(rc["pass"] is True, "rubric-not-pass", row.get("id"))
        chk(rc["score"] == rec.get("score") == 3, "score-mismatch", (row.get("id"), rc["score"], rec.get("score")))
        reasons.append(str(row.get("reason")))
    inv = doc.get("closed_inventory") or {}
    chk(sorted(inv.get("triggered_reasons") or []) == sorted(reasons), "inventory!=triggered")
    chk(inv.get("complete") is True, "inventory-incomplete")

    # negative control: bare failure texts must NOT pass the rubric
    for nc in doc.get("negative_controls") or []:
        for planted in nc.get("planted") or []:
            chk(rubric(str(planted))["pass"] is False, "nc-passed-on-bare", planted)

    # live re-run against the live module (Windows PowerShell-hosted python here)
    spec = importlib.util.spec_from_file_location(
        "live_client_negotiate", REPO / "tools/plugin/client_negotiate.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["live_client_negotiate"] = mod
    spec.loader.exec_module(mod)
    manifest = mod.load_manifest(None)
    live_cases = {
        "unparsable-version": mod.negotiate(manifest, "claude-code", "not-a-semver"),
        "below-floor": mod.negotiate(manifest, "claude-code", "0.9.0"),
    }
    live_reasons = []
    for name, n in live_cases.items():
        chk(n.allowed is False, "live-allowed", name)
        rc = rubric(n.message)
        chk(rc["pass"] is True, "live-message-rubric-fail", (name, n.message))
        live_reasons.append(n.reason)
    drift = sorted(set(reasons) - set(live_reasons))
    if drift:
        print("NOTE drift: recorded-only refuse reasons (worktree build had install_gate CLI absent live): %s" % ",".join(drift))
    chk(len(FAILS) == 0, "failures", FAILS)
    if FAILS:
        print("FAILED:TST-0113-probe2 " + " ; ".join(FAILS))
        return 1
    print("SUCCESS:TST-0113-probe2 5/5 recorded paths re-score 3/3 on captured text; bare-message control fires; live refuse messages (unparsable-version, below-floor) score 3/3 live")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
