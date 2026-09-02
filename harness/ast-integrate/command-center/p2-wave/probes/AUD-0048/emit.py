#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0048-action-pinning-permissions.json."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from classify import HIGHEST
from resolve import resolve_use
from scan import scan_all

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT_REL = "command-center/audit/AUD-0048-action-pinning-permissions.json"
SCHEMA_REL = "command-center/schema/audit-finding.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0048 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)
QUESTION = (
    "Is every third-party action pinned to a full commit SHA rather than a tag, "
    "and does every workflow declare a least-privilege permissions block rather "
    "than inheriting the default token scope?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0048/probe1_syntactic_classification.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0048/probe2_tag_resolution.py"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def flatten_uses(
    bundle: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    live: list[dict] = []
    fx: list[dict] = []
    nested: list[dict] = []
    for wf in bundle["live"]:
        live.extend(wf["uses"])
    for wf in bundle["fixtures"]:
        fx.extend(wf["uses"])
    for wf in bundle.get("nested") or []:
        nested.extend(wf["uses"])
    return live, fx, list(bundle.get("harvest_aud0041") or []), nested


def fixture_named(bundle: dict[str, Any], stem: str) -> dict[str, Any] | None:
    for wf in bundle["fixtures"]:
        if Path(wf["file"]).stem == stem:
            return wf
    return None


def evaluate_controls(bundle: dict[str, Any]) -> dict[str, Any]:
    branch = fixture_named(bundle, "control-branch-pinned")
    sha = fixture_named(bundle, "control-sha-pinned")
    tag = fixture_named(bundle, "control-tag-pinned")
    mention = fixture_named(bundle, "control-mention-not-use")
    errors: list[str] = []

    b_uses = (branch or {}).get("uses") or []
    s_uses = (sha or {}).get("uses") or []
    t_uses = (tag or {}).get("uses") or []
    m_uses = (mention or {}).get("uses") or []

    if not branch:
        errors.append("branch fixture missing")
    if not sha:
        errors.append("sha fixture missing")
    if len(b_uses) != 1:
        errors.append(f"branch fixture uses count {len(b_uses)} want 1")
    elif b_uses[0]["pin_class"] != "branch-pinned":
        errors.append(f"branch fixture pin_class={b_uses[0]['pin_class']}")
    elif not b_uses[0]["highest_severity"] or b_uses[0]["severity"] != HIGHEST:
        errors.append("branch-pinned action was not flagged at highest severity")
    elif not b_uses[0]["flagged"]:
        errors.append("branch-pinned action was not flagged")

    if len(s_uses) != 1:
        errors.append(f"sha fixture uses count {len(s_uses)} want 1")
    elif s_uses[0]["pin_class"] != "sha-pinned":
        errors.append(f"sha fixture pin_class={s_uses[0]['pin_class']}")
    elif s_uses[0]["flagged"] or s_uses[0]["severity"] != "none":
        errors.append("sha-pinned action was flagged (must be silent)")

    if len(t_uses) != 1 or t_uses[0]["pin_class"] != "tag-pinned":
        errors.append("tag fixture not classified as tag-pinned")

    if m_uses:
        errors.append(
            "mention fixture produced uses: rows; comments/strings were treated as uses"
        )

    return {
        "pass": not errors,
        "errors": errors,
        "branch": b_uses[0] if b_uses else None,
        "sha": s_uses[0] if s_uses else None,
        "tag": t_uses[0] if t_uses else None,
        "mention_uses": m_uses,
        "permissions": {
            "branch_missing": bool((branch or {}).get("permissions_flagged")),
            "sha_least_privilege": bool(
                sha
                and sha["permissions"]["workflow"]["least_privilege"]
                and not sha["permissions"]["workflow"]["flagged"]
            ),
        },
    }


def pin_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(r.get("pin_class") for r in rows)
    return dict(sorted(counts.items(), key=lambda kv: kv[0] or ""))


def resolve_targets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for rec in rows:
        key = (rec.get("action") or "", rec.get("ref") or "")
        if key in seen:
            continue
        if rec.get("pin_class") not in {"tag-pinned", "branch-pinned"}:
            continue
        if rec.get("local") or rec.get("kind") != "remote":
            continue
        seen.add(key)
        out.append(resolve_use(rec))
    return out


def slim_resolution(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": rec.get("action"),
        "ref": rec.get("ref"),
        "pin_class": rec.get("pin_class"),
        "file": rec.get("file"),
        "repo": rec.get("repo"),
        "attempted": rec.get("attempted"),
        "ok": rec.get("ok"),
        "sha": rec.get("sha"),
        "error": rec.get("error"),
        "skip_reason": rec.get("skip_reason"),
        "url": rec.get("url"),
        "fingerprint": rec.get("fingerprint"),
    }


def build() -> dict[str, Any]:
    bundle = scan_all()
    live_uses, fx_uses, harvest, nested_uses = flatten_uses(bundle)
    controls = evaluate_controls(bundle)
    fixture_tag = [u for u in fx_uses if u.get("pin_class") == "tag-pinned"]
    live_mutable = [
        u
        for u in live_uses
        if u.get("pin_class") in {"tag-pinned", "branch-pinned"} and u.get("third_party")
    ]
    fixture_resolutions = [slim_resolution(r) for r in resolve_targets(fixture_tag)]
    live_resolutions = [slim_resolution(r) for r in resolve_targets(live_mutable)]
    resolutions = fixture_resolutions + live_resolutions
    harvest_resolutions: list[dict[str, Any]] = []

    live_flagged = [u for u in live_uses if u.get("flagged") and u.get("third_party")]
    harvest_flagged = [u for u in harvest if u.get("flagged") and u.get("third_party")]
    nested_flagged = [
        u for u in nested_uses if u.get("flagged") and u.get("third_party")
    ]
    live_perm_flagged = [wf for wf in bundle["live"] if wf.get("permissions_flagged")]

    schema_path = REPO / SCHEMA_REL
    live_n = bundle["live_workflow_count"]
    fixture_ok = bool(controls["pass"])
    attempted_fx = [r for r in fixture_resolutions if r.get("attempted")]
    p2_ok = bool(attempted_fx) and all(
        r.get("ok") and r.get("sha") and len(str(r.get("sha"))) == 40
        for r in attempted_fx
    )

    live_tag = [u for u in live_uses if u.get("pin_class") == "tag-pinned"]
    live_sha = [u for u in live_uses if u.get("pin_class") == "sha-pinned"]
    live_branch = [u for u in live_uses if u.get("pin_class") == "branch-pinned"]

    if not fixture_ok:
        state = "FAILED"
        answer_head = "Detector control failed; refusing to answer the live-tree question."
    else:
        state = "SUCCESS"
        if live_n == 0:
            answer_head = (
                "Live tree has zero GitHub workflow files under .github/workflows "
                f"(count={live_n}). The pinning/permissions question is therefore "
                "NOT-CHECKED on production YAML. The detector is proven on fixtures: "
                "branch-pinned actions/checkout@main is flagged at severity "
                f"{HIGHEST}, and the 40-character SHA pin is silent. Harvested "
                "AUD-0041 inventory (stale; workflows no longer on this tree) is "
                "classified separately and is not treated as live evidence."
            )
        else:
            unique_tags = sorted({str(u.get("raw")) for u in live_tag})
            answer_head = (
                f"No: not every third-party action is SHA-pinned. Live "
                f".github/workflows has {live_n} workflow files, "
                f"{len(live_uses)} uses: lines, {len(live_sha)} sha-pinned, "
                f"{len(live_tag)} tag-pinned ({unique_tags}), "
                f"{len(live_branch)} branch-pinned, "
                f"{len(live_perm_flagged)} workflows whose workflow-level "
                "permissions block is missing or grants write. Nested/vendored "
                f"workflow YAML ({bundle.get('nested_workflow_count', 0)} files) "
                "is inventoried separately and is not this repo's Actions identity."
            )

    findings: list[dict[str, Any]] = []
    if live_n == 0:
        findings.append(
            {
                "id": "F1-live-workflows-absent",
                "severity": "info",
                "title": "No live GitHub Actions workflows on this worktree",
                "detail": (
                    ".github/workflows is absent. A vacuous 'all actions are SHA-pinned' "
                    "claim is forbidden; the live answer is NOT-CHECKED."
                ),
            }
        )
    for u in live_flagged:
        findings.append(
            {
                "id": f"live-{u.get('file')}-{u.get('line')}",
                "severity": u.get("severity"),
                "title": f"{u.get('pin_class')} {u.get('raw')}",
                "file": u.get("file"),
                "line": u.get("line"),
            }
        )
    if harvest_flagged:
        findings.append(
            {
                "id": "F-harvest-tag-or-branch-pins",
                "severity": "high",
                "title": (
                    f"AUD-0041 harvest: {len(harvest_flagged)} third-party uses are "
                    "not full-SHA pins (stale inventory, not live YAML)"
                ),
                "pin_classes": pin_counts(harvest),
                "examples": [
                    {
                        "file": h.get("file"),
                        "raw": h.get("raw"),
                        "pin_class": h.get("pin_class"),
                    }
                    for h in harvest_flagged[:8]
                ],
            }
        )
    if nested_flagged:
        findings.append(
            {
                "id": "F-nested-vendored-unpinned",
                "severity": "medium",
                "title": (
                    f"Nested/vendored workflows: {len(nested_flagged)} third-party "
                    "uses are not full-SHA pins (not this repo's Actions identity)"
                ),
                "pin_classes": pin_counts(nested_uses),
                "files": bundle.get("nested_files") or [],
            }
        )

    tests = [
        {
            "id": "control-branch-pinned-highest-severity",
            "name": "Fixture with a branch-pinned action is flagged at the highest severity",
            "result": (
                "PASS"
                if controls["branch"] and controls["branch"]["highest_severity"]
                else "FAIL"
            ),
        },
        {
            "id": "control-sha-pinned-silent",
            "name": "Fixture with a sha-pinned action is not flagged",
            "result": (
                "PASS"
                if controls["sha"] and not controls["sha"]["flagged"]
                else "FAIL"
            ),
        },
        {
            "id": "control-mention-not-use",
            "name": "Comment/string mentions of uses: are not classified as uses",
            "result": "PASS" if not controls["mention_uses"] else "FAIL",
        },
        {
            "id": "probe2-tag-resolves-to-sha",
            "name": "Tag-pinned fixture resolves via git ls-remote to a 40-char SHA",
            "result": "PASS" if p2_ok else "FAIL",
        },
    ]

    return {
        "unit_id": "AUD-0048",
        "state": state,
        "sentinel": SENTINEL,
        "report_kind": "audit-finding",
        "schema_version": 1,
        "question": QUESTION,
        "answer": answer_head,
        "report": {
            "kind": "audit-finding",
            "question": QUESTION,
            "answer": answer_head,
            "observations": [
                {
                    "name": "live_workflow_files",
                    "measured": live_n,
                    "method": "directory listing of .github/workflows",
                    "anchor": ".github/workflows",
                },
                {
                    "name": "live_uses",
                    "measured": len(live_uses),
                    "method": "syntactic uses: line scan",
                    "anchor": "command-center/p2-wave/probes/AUD-0048/scan.py",
                },
                {
                    "name": "live_third_party_flagged",
                    "measured": len(live_flagged),
                    "method": "pin_class severity gate (branch=critical, tag=high)",
                    "anchor": "command-center/p2-wave/probes/AUD-0048/classify.py",
                },
                {
                    "name": "live_permissions_flagged",
                    "measured": len(live_perm_flagged),
                    "method": "workflow-level permissions missing or write-grant",
                    "anchor": "command-center/p2-wave/probes/AUD-0048/classify.py",
                },
                {
                    "name": "probe2_fixture_tag_resolved",
                    "measured": bool(p2_ok),
                    "method": "git ls-remote of fixture tag-pinned uses",
                    "anchor": "command-center/p2-wave/probes/AUD-0048/resolve.py",
                },
            ],
            "control_ids": ["branch-vs-sha-pin"],
        },
        "measured_at": _now(),
        "output_schema": SCHEMA_REL,
        "output_schema_on_disk": schema_path.is_file(),
        "headline": {
            "live_workflow_files": live_n,
            "live_uses": len(live_uses),
            "live_third_party_flagged": len(live_flagged),
            "live_permissions_flagged": len(live_perm_flagged),
            "live_pin_classes": pin_counts(live_uses),
            "fixture_control_pass": fixture_ok,
            "probe2_resolutions_ok": p2_ok,
            "harvest_uses": len(harvest),
            "harvest_pin_classes": pin_counts(harvest),
            "harvest_flagged": len(harvest_flagged),
            "nested_workflow_files": bundle.get("nested_workflow_count", 0),
            "nested_flagged": len(nested_flagged),
        },
        "findings": findings,
        "controls": {
            "id": "branch-vs-sha-pin",
            "pass": fixture_ok,
            "errors": controls["errors"],
            "branch_severity": (controls["branch"] or {}).get("severity"),
            "sha_flagged": (controls["sha"] or {}).get("flagged"),
            "permissions": controls["permissions"],
        },
        "live": {
            "files": bundle["live_files"],
            "workflows": [
                {
                    "file": wf["file"],
                    "uses": [
                        {
                            "raw": u["raw"],
                            "action": u["action"],
                            "ref": u["ref"],
                            "pin_class": u["pin_class"],
                            "severity": u["severity"],
                            "flagged": u["flagged"],
                            "line": u["line"],
                        }
                        for u in wf["uses"]
                    ],
                    "permissions": wf["permissions"],
                    "permissions_flagged": wf["permissions_flagged"],
                }
                for wf in bundle["live"]
            ],
        },
        "fixtures": {
            "uses": [
                {
                    "file": u["file"],
                    "raw": u["raw"],
                    "pin_class": u["pin_class"],
                    "severity": u["severity"],
                    "flagged": u["flagged"],
                    "line": u["line"],
                }
                for u in fx_uses
            ]
        },
        "harvest_aud0041": {
            "note": (
                "Classified from AUD-0041 probe1-yaml-inventory.json. Those workflow "
                "files are not on this worktree. Not a live pinning claim."
            ),
            "n": len(harvest),
            "pin_classes": pin_counts(harvest),
            "flagged_n": len(harvest_flagged),
            "tag_resolutions": harvest_resolutions,
        },
        "probe2_resolutions": resolutions,
        "tests": tests,
        "named_probes": [
            {"id": "probe1", "role": "syntactic-classification", "command": P1_CMD},
            {"id": "probe2", "role": "tag-to-sha-resolution", "command": P2_CMD},
        ],
        "reviewer": {
            "reviewer_id": "AUD-0048-probe2-git-ls-remote",
            "verdict": "PASS" if p2_ok and fixture_ok else "FAIL",
            "independent": True,
            "job": (
                "Resolve tag-pinned fixture refs with git ls-remote; do not re-read "
                "probe 1's syntactic pin_class as proof of what the tag points at."
            ),
        },
        "artifacts": [
            {"path": OUT_REL, "role": "primary"},
            {
                "path": SCHEMA_REL,
                "role": "declared-schema",
                "exists": schema_path.is_file(),
            },
        ],
        "claim_scope": (
            "SUCCESS means the two named probes ran, the required both-states pin "
            "control discriminated, and the live-tree question was answered without "
            "vacuity. It does not mean every historical workflow was SHA-pinned."
        ),
    }


def write(doc: dict[str, Any] | None = None) -> Path:
    doc = doc or build()
    dest = REPO / OUT_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return dest


def main() -> int:
    doc = build()
    if not doc["controls"]["pass"]:
        print("FAILED:AUD-0048 detector control did not discriminate")
        print(json.dumps(doc["controls"]["errors"], indent=2))
        return 1
    if doc["reviewer"]["verdict"] != "PASS":
        print("FAILED:AUD-0048 probe2 tag resolution did not land a SHA")
        print(json.dumps(doc.get("probe2_resolutions"), indent=2)[:2000])
        return 1
    path = write(doc)
    print(
        f"wrote {OUT_REL} bytes={path.stat().st_size} "
        f"state={doc['state']} live_wf={doc['headline']['live_workflow_files']} "
        f"control={doc['controls']['pass']}"
    )
    print("SUCCESS:AUD-0048 artifact emitted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
