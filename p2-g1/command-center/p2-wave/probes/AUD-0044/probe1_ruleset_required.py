#!/usr/bin/env python3
"""AUD-0044 probe 1 - branch-ruleset required_status_checks, live from the API.

Evidence requirement (catalog): "the ruleset required_status_checks list from the
API". Re-measures the live ruleset on Prekzursil/agent-skills-toolchain main and
compares it against the recorded artifact. Also re-runs the comparator control on
a scratch renamed-job fixture (both-states: silent on match, fires on rename).

Windows platform adaptation of the original probe: subprocess argv form (no
POSIX env-prefix) so cmd.exe can execute it; probe selection, exit-code contract
and all assertions unchanged.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ART = REPO / "command-center" / "audit" / "AUD-0044-required-context-audit.json"
UNIT = "AUD-0044"
SUBJECT = "Prekzursil/agent-skills-toolchain"


def gh_api(url: str) -> tuple[int, str]:
    """Call the GitHub API via gh; returns (rc, stdout+stderr tail)."""
    exe = "gh"
    try:
        p = subprocess.run(
            [exe, "api", url, "--paginate"],
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, f"gh-invoke-failed: {exc}"
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def fail(msg: str) -> int:
    print(json.dumps({"probe": "probe1-ruleset-required", "unit_id": UNIT,
                      "pass": False, "error": msg}))
    print(f"FAILED:{UNIT}-probe1 {msg}")
    return 1


def comparator(required: set, produced: set) -> dict:
    """The drift comparator under audit: symmetric-difference report."""
    sym = sorted(required ^ produced)
    return {
        "required_count": len(required),
        "produced_count": len(produced),
        "intersection_count": len(required & produced),
        "required_not_produced": sorted(required - produced),
        "produced_not_required": sorted(produced - required),
        "symmetric_difference": sym,
        "symmetric_difference_count": len(sym),
        "disagree": bool(sym),
    }


def control() -> tuple[bool, dict]:
    """Both-states control on a scratch renamed job (never touches CI config).

    good state: produced names == required names  -> comparator silent
    bad  state: one required job renamed          -> non-empty symmetric diff
    """
    req = {"gate-alpha", "gate-beta"}
    good = comparator(req, {"gate-alpha", "gate-beta"})
    bad = comparator(req, {"gate-alpha", "gate-beta-RENAMED"})
    ok = (good["symmetric_difference_count"] == 0
          and good["disagree"] is False
          and bad["symmetric_difference_count"] == 2
          and bad["disagree"] is True
          and "gate-beta-RENAMED" in bad["produced_not_required"]
          and "gate-beta" in bad["required_not_produced"])
    return ok, {"good": good, "bad": bad}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    sent = ("SUCCESS:AUD-0044 emitted only when the artifact at output_path exists, "
            "is non-empty, parses against output_schema, and both named probes are "
            "recorded with their verbatim output")
    if sent not in text and "SUCCESS:AUD-0044" not in text:
        return fail("sentinel absent")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")

    rc, out = gh_api(f"/repos/{SUBJECT}/rules/branches/main")
    live_ctx: list[str] = []
    api_ok = False
    parse = "ok"
    if rc == 0:
        try:
            rules = json.loads(out.splitlines()[0] if out else "[]")
            for rule in rules if isinstance(rules, list) else []:
                if rule.get("type") == "required_status_checks":
                    for c in (rule.get("parameters") or {}).get(
                            "required_status_checks") or []:
                        if c.get("context"):
                            live_ctx.append(c["context"])
            live_ctx = sorted(set(live_ctx))
            api_ok = bool(live_ctx)
        except (ValueError, IndexError, AttributeError) as exc:
            parse = f"parse-error: {type(exc).__name__}"

    # comparator control must fire in BOTH states before any live claim is trusted
    ctl_ok, ctl = control()
    if not ctl_ok:
        return fail("comparator control did not discriminate (silent-on-good or quiet-on-bad)")

    rec_req = sorted((doc.get("disagreement") or {}).get("intersection") or [])
    result = {
        "probe": "probe1-ruleset-required",
        "unit_id": UNIT,
        "subject_repo": SUBJECT,
        "endpoint": f"/repos/{SUBJECT}/rules/branches/main",
        "api_attempted": True,
        "api_rc": rc,
        "api_ok": api_ok,
        "parse": parse,
        "live_required_contexts": live_ctx,
        "artifact_recorded_required_contexts": rec_req,
        "live_equals_recorded": bool(live_ctx and live_ctx == rec_req),
        "live_required_count": len(live_ctx),
        "recorded_required_count": len(rec_req),
        "comparator_control": ctl,
        "control_discriminates": ctl_ok,
    }
    print(json.dumps(result, indent=1))

    if rc != 0:
        return fail(f"gh api rc={rc}: {out[-300:]}")
    if not api_ok:
        return fail("live ruleset yielded no required_status_checks contexts")
    if live_ctx != rec_req:
        return fail(f"live required set {live_ctx} != artifact-recorded {rec_req}")
    print("SUCCESS:AUD-0044-probe1 live ruleset required set matches artifact; comparator control discriminates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
