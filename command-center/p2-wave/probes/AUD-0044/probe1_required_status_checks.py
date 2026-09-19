#!/usr/bin/env python3
"""AUD-0044 Probe 1: branch-protection / ruleset required_status_checks.

Documents which API answered:
  - classic GET /repos/{owner}/{repo}/branches/{branch}/protection → often 403
    for fine-grained / integration tokens without Administration:read
  - rulesets GET /repos/{owner}/{repo}/rulesets + /rulesets/{id} → preferred
    when classic protection is inaccessible

Writes:
  probe1-required-status-checks.json
  probe1-required-status-checks.raw.txt
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-required-status-checks.json"
OUT_RAW = PROBE / "probe1-required-status-checks.raw.txt"
REPO = "Prekzursil/agent-skills-toolchain"
DEFAULT_BRANCH = "main"


def gh_api(path: str) -> tuple[int, str]:
    r = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, out


def extract_classic_contexts(payload: dict) -> list[str]:
    rsc = (
        (payload.get("required_status_checks") or {})
        if isinstance(payload, dict)
        else {}
    )
    contexts = list(rsc.get("contexts") or [])
    checks = rsc.get("checks") or []
    for c in checks:
        if isinstance(c, dict) and c.get("context"):
            contexts.append(c["context"])
        elif isinstance(c, str):
            contexts.append(c)
    return sorted({c for c in contexts if c})


def extract_ruleset_contexts(ruleset: dict) -> list[str]:
    contexts: list[str] = []
    for rule in ruleset.get("rules") or []:
        if rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        for item in params.get("required_status_checks") or []:
            if isinstance(item, dict) and item.get("context"):
                contexts.append(item["context"])
            elif isinstance(item, str):
                contexts.append(item)
    return sorted({c for c in contexts if c})


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw_parts: list[str] = []

    classic_path = f"repos/{REPO}/branches/{DEFAULT_BRANCH}/protection"
    classic_rc, classic_raw = gh_api(classic_path)
    raw_parts.append(
        f"=== GET {classic_path} (classic branch protection) rc={classic_rc} ===\n"
    )
    raw_parts.append(classic_raw)
    classic_ok = False
    classic_contexts: list[str] = []
    classic_error = None
    try:
        classic_payload = json.loads(classic_raw.split("gh:")[0].strip() or classic_raw)
    except json.JSONDecodeError:
        classic_payload = None
    if (
        classic_rc == 0
        and isinstance(classic_payload, dict)
        and "required_status_checks" in classic_payload
    ):
        classic_ok = True
        classic_contexts = extract_classic_contexts(classic_payload)
    else:
        classic_error = {
            "http_or_exit": classic_rc,
            "message": (
                classic_payload.get("message")
                if isinstance(classic_payload, dict)
                else classic_raw[:500]
            ),
            "status": (
                classic_payload.get("status")
                if isinstance(classic_payload, dict)
                else None
            ),
        }

    rulesets_path = f"repos/{REPO}/rulesets"
    rulesets_rc, rulesets_raw = gh_api(rulesets_path)
    raw_parts.append(f"\n=== GET {rulesets_path} rc={rulesets_rc} ===\n")
    raw_parts.append(rulesets_raw)

    ruleset_details: list[dict] = []
    ruleset_contexts: list[str] = []
    rulesets_ok = False
    rulesets_error = None
    if rulesets_rc == 0:
        try:
            ruleset_list = json.loads(rulesets_raw)
        except json.JSONDecodeError as e:
            ruleset_list = []
            rulesets_error = f"rulesets list JSON decode failed: {e}"
        if isinstance(ruleset_list, list):
            for entry in ruleset_list:
                rid = entry.get("id")
                if rid is None:
                    continue
                detail_path = f"repos/{REPO}/rulesets/{rid}"
                d_rc, d_raw = gh_api(detail_path)
                raw_parts.append(f"\n=== GET {detail_path} rc={d_rc} ===\n")
                raw_parts.append(d_raw)
                if d_rc != 0:
                    continue
                try:
                    detail = json.loads(d_raw)
                except json.JSONDecodeError:
                    continue
                ctxs = extract_ruleset_contexts(detail)
                ruleset_details.append(
                    {
                        "id": rid,
                        "name": detail.get("name"),
                        "enforcement": detail.get("enforcement"),
                        "target": detail.get("target"),
                        "conditions": detail.get("conditions"),
                        "required_status_checks": ctxs,
                    }
                )
                ruleset_contexts.extend(ctxs)
            ruleset_contexts = sorted(set(ruleset_contexts))
            rulesets_ok = True
    else:
        try:
            err = json.loads(rulesets_raw.split("gh:")[0].strip() or rulesets_raw)
            rulesets_error = err if isinstance(err, dict) else rulesets_raw[:500]
        except json.JSONDecodeError:
            rulesets_error = rulesets_raw[:500]

    # Prefer ruleset contexts when available; else classic; never invent.
    api_used = None
    required: list[str] = []
    if rulesets_ok and ruleset_contexts:
        api_used = "rulesets"
        required = ruleset_contexts
    elif classic_ok and classic_contexts:
        api_used = "classic_branch_protection"
        required = classic_contexts
    elif rulesets_ok and not ruleset_contexts and classic_ok:
        api_used = "classic_branch_protection"
        required = classic_contexts
    elif rulesets_ok:
        api_used = "rulesets"
        required = ruleset_contexts
    elif classic_ok:
        api_used = "classic_branch_protection"
        required = classic_contexts
    else:
        api_used = "none"

    ok = bool(required) or (rulesets_ok and classic_error is not None)
    # Honest: if we got an empty required set because BOTH APIs failed, ok=False.
    if api_used == "none":
        ok = False
    elif not required and classic_error and not rulesets_ok:
        ok = False
    else:
        # Having a ruleset answer (even empty required list) is measurable.
        ok = rulesets_ok or classic_ok

    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "probe": "AUD-0044-probe1-required-status-checks",
        "started_at": started,
        "ended_at": ended,
        "repo": REPO,
        "default_branch": DEFAULT_BRANCH,
        "api_documentation": {
            "classic": (
                f"GET /repos/{REPO}/branches/{DEFAULT_BRANCH}/protection "
                "→ required_status_checks.contexts / .checks[].context"
            ),
            "rulesets": (
                f"GET /repos/{REPO}/rulesets then GET /repos/{REPO}/rulesets/{{id}} "
                "→ rules[type=required_status_checks].parameters.required_status_checks[].context"
            ),
            "selected": api_used,
            "selection_rule": (
                "Prefer rulesets when they return; fall back to classic protection. "
                "Never invent required contexts on 403/404."
            ),
        },
        "classic_branch_protection": {
            "ok": classic_ok,
            "error": classic_error,
            "required_status_checks": classic_contexts,
            "count": len(classic_contexts),
        },
        "rulesets": {
            "ok": rulesets_ok,
            "error": rulesets_error,
            "rulesets": ruleset_details,
            "required_status_checks": ruleset_contexts,
            "count": len(ruleset_contexts),
        },
        "required_status_checks": required,
        "required_count": len(required),
        "api_used": api_used,
        "ok": ok,
        "residual": (
            None
            if classic_ok
            else (
                "Classic branch-protection API returned "
                f"{(classic_error or {}).get('status') or classic_rc}; "
                "required contexts below come from rulesets only when rulesets_ok."
            )
        ),
    }

    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    OUT_RAW.write_text("".join(raw_parts), encoding="utf-8")
    print(
        f"probe1 ok={ok} api_used={api_used} required_count={len(required)} "
        f"classic_ok={classic_ok} rulesets_ok={rulesets_ok}"
    )
    for c in required:
        print(f"  required: {c}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
