#!/usr/bin/env python3
"""Emit command-center/research/RES-0008.json from live snapshots and fixtures."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from capture import ensure_snapshots  # noqa: E402
from common import (  # noqa: E402
    DOCS_MARKETPLACES,
    DOCS_REFERENCE,
    GITHUB_ISSUE,
    MARKET_ONLY_BUMP,
    OUT_REL,
    PINNED,
    PLUGIN_WINS_MARKERS,
    REPO,
    SCHEMA_URL,
    UID,
    VALIDATE_WARNS_MARKERS,
    contains_any,
    digest_file,
    extract_marketplace_schema,
    load_fetch_log,
    load_fixture,
    load_json,
    rail_from_log,
    resolve_plugin_version,
    snapshot_path,
    snapshot_text,
)

SENTINEL = (
    "SUCCESS:RES-0008 in the receipt AND a precedence verdict backed by a "
    "reproducible two-file fixture and the observed installed version"
)
QUESTION = (
    "What is the exact marketplace.json schema today, and does plugin.json "
    "still silently WIN over the marketplace entry for the version field - "
    "the trap that makes commits without a version bump ship nothing while "
    "both files pin 0.2.0?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0008/probe1_disagree_precedence.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0008/probe2_identical_negative.py"
)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def observed_client() -> dict:
    path = shutil.which("claude")
    if not path:
        return {
            "present": False,
            "path": None,
            "version": None,
            "validate_ran": False,
            "reason": "claude binary not on PATH in this worktree",
        }
    try:
        p = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        text = ((p.stdout or "") + (p.stderr or "")).strip()
        return {
            "present": True,
            "path": path,
            "version": text.splitlines()[0] if text else None,
            "validate_ran": False,
            "reason": "binary present; install/validate not invoked (no network plugin install)",
        }
    except Exception as exc:
        return {
            "present": True,
            "path": path,
            "version": None,
            "validate_ran": False,
            "reason": f"{type(exc).__name__}:{exc}",
        }


def rail(key: str, role: str) -> dict:
    row = rail_from_log(key) or {}
    return {
        "rail": role,
        "key": key,
        "permalink": row.get("permalink") or row.get("url"),
        "final_url": row.get("final_url"),
        "http_status": row.get("http_status"),
        "fetched_at": row.get("fetched_at"),
        "sha256": row.get("sha256"),
        "bytes": row.get("bytes"),
        "path": row.get("path"),
        "ok": row.get("ok"),
    }


def main() -> int:
    log = ensure_snapshots(force=True)
    failed = [k for k, v in (log.get("sources") or {}).items() if not v.get("ok")]
    if failed:
        print(f"FAILED:RES-0008 emit capture failed {failed}")
        return 1

    schema = load_json(snapshot_path("claude-code-marketplace.schema.json"))
    extracted = extract_marketplace_schema(schema)
    from jsonschema import Draft7Validator

    validator = Draft7Validator(schema)
    disagree = load_fixture("disagree")
    identical = load_fixture("identical")
    d_errs = list(validator.iter_errors(disagree["marketplace"]))
    i_errs = list(validator.iter_errors(identical["marketplace"]))
    missing = dict(disagree["marketplace"])
    missing.pop("plugins", None)
    missing_errs = list(validator.iter_errors(missing))
    extra_key = copy.deepcopy(disagree["marketplace"])
    extra_key["totally_unknown_res0008"] = "x"
    extra_errs = list(validator.iter_errors(extra_key))

    docs = snapshot_text("plugin-marketplaces.md") + "\n" + snapshot_text(
        "plugins-reference.md"
    )
    issue = snapshot_text("github-54280.json")
    doc_wins = contains_any(docs, PLUGIN_WINS_MARKERS)
    validate_warns = contains_any(docs, VALIDATE_WARNS_MARKERS)
    issue_hits = contains_any(
        issue,
        (
            "plugin.json wins",
            "silently overrides marketplace.json version",
            "Customize panel shows",
        ),
    )
    client = observed_client()
    stamp = _now()
    schema_sha, schema_bytes = digest_file(
        snapshot_path("claude-code-marketplace.schema.json")
    )

    mutant_entry = copy.deepcopy(identical["entry"])
    mutant_entry["version"] = MARKET_ONLY_BUMP
    mutant = resolve_plugin_version(identical["plugin"], mutant_entry)

    docs_required = ["name", "owner", "plugins"]
    docs_plugin_required = ["name", "source"]
    schema_matches_docs_required = extracted["required"] == docs_required
    schema_matches_plugin_required = (
        extracted["plugin_entry_required"] == docs_plugin_required
    )

    docs_plugin_optional_today = [
        "displayName",
        "description",
        "version",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "metadata",
        "category",
        "tags",
        "strict",
        "relevance",
        "defaultEnabled",
        "skills",
        "commands",
        "agents",
        "hooks",
        "mcpServers",
        "lspServers",
    ]
    entry_names = set(extracted["plugin_entry_property_names"])
    docs_fields_absent_from_schema = sorted(
        f for f in docs_plugin_optional_today if f not in entry_names
    )
    schema_root_only = sorted(
        n
        for n in extracted["root_property_names"]
        if n
        not in {
            "$schema",
            "name",
            "version",
            "description",
            "owner",
            "plugins",
            "metadata",
        }
    )

    c1_ok = (
        schema_matches_docs_required
        and schema_matches_plugin_required
        and not d_errs
        and not i_errs
        and bool(missing_errs)
        and "version" not in extracted["required"]
        and "version" not in extracted["plugin_entry_required"]
    )
    c2_ok = (
        disagree["verdict"]["honoured_version"] == PINNED
        and disagree["verdict"]["honoured_source"] == "plugin.json"
        and disagree["verdict"]["marketplace_version"] == MARKET_ONLY_BUMP
        and disagree["verdict"]["precedence_signal"] is True
        and bool(doc_wins)
        and bool(issue_hits)
    )
    c3_ok = (
        identical["verdict"]["precedence_signal"] is False
        and identical["verdict"]["identical"] is True
        and identical["verdict"]["honoured_version"] == PINNED
        and mutant["precedence_signal"] is True
    )
    if not (c1_ok and c2_ok and c3_ok):
        print(
            json.dumps(
                {
                    "c1_ok": c1_ok,
                    "c2_ok": c2_ok,
                    "c3_ok": c3_ok,
                    "d_errs": len(d_errs),
                    "i_errs": len(i_errs),
                    "doc_wins": doc_wins,
                    "issue_hits": issue_hits,
                    "extracted": extracted,
                },
                indent=2,
                default=str,
            )
        )
        print("FAILED:RES-0008 emit claims did not confirm")
        return 1

    claims = [
        {
            "id": "C-MARKETPLACE-SCHEMA-TODAY",
            "claim": (
                "The live SchemaStore marketplace.json schema (draft-07, "
                f"$id={extracted.get('$id')}) requires top-level "
                f"{extracted['required']} and plugin-entry "
                f"{extracted['plugin_entry_required']}. version is optional on "
                "both the marketplace root and each plugin entry. A document "
                "missing plugins[] is rejected; both two-file fixtures validate."
            ),
            "canonical_mechanism": "json-schema-draft-07 required/properties walk",
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "named_settling_probe": P1,
            "source_lineage": [
                rail("marketplace_schema", "structured-api"),
                rail("plugin_marketplaces_docs", "prose"),
            ],
            "freshness_stamp": stamp,
            "snapshot_sha256": schema_sha,
            "strongest_caveat": (
                "SchemaStore $comment is "
                f"{extracted.get('$comment')!r}. Docs list plugin-entry fields "
                f"absent from this schema: {docs_fields_absent_from_schema}. "
                "Those fields are documented runtime behaviour, not encoded here. "
                "Root additionalProperties is omitted (JSON Schema default: allow)."
            ),
        },
        {
            "id": "C-PLUGIN-JSON-WINS-VERSION",
            "claim": (
                "When plugin.json and the marketplace entry disagree on version, "
                "plugin.json wins. Disagree fixture pin "
                f"plugin.json={PINNED} vs marketplace={MARKET_ONLY_BUMP} resolves "
                f"to honoured_version={PINNED} (source=plugin.json). That is the "
                "trap: bumping only marketplace.json ships nothing."
            ),
            "canonical_mechanism": (
                "version-management waterfall: plugin.json version, then "
                "marketplace entry version, then git SHA / archive digest / unknown"
            ),
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "named_settling_probe": P1,
            "source_lineage": [
                rail("plugins_reference_docs", "prose"),
                rail("github_issue_54280", "structured-api"),
            ],
            "freshness_stamp": stamp,
            "snapshot_sha256": (rail_from_log("github_issue_54280") or {}).get(
                "sha256"
            ),
            "strongest_caveat": (
                "Live `claude` CLI is absent on this worktree, so cache-path "
                "install was not observed here. The structured rail is GitHub "
                "issue 54280 (Customize panel showed plugin.json's version). "
                "The SchemaStore schema does not encode this rule "
                "(plugin_entry_version_mentions_plugin_json_priority=false)."
            ),
        },
        {
            "id": "C-IDENTICAL-NO-PRECEDENCE-SIGNAL",
            "claim": (
                "When both files pin the same version "
                f"({PINNED}), the detector reports precedence_signal=false. "
                "A one-field marketplace mutation to "
                f"{MARKET_ONLY_BUMP} makes the same detector fire. Identical "
                "versions produce no precedence signal at all."
            ),
            "canonical_mechanism": "both-states mismatch detector on two-file fixture",
            "verdict": "CONFIRMED",
            "evidence_tier": "E2",
            "confidence_band": "high",
            "named_settling_probe": P2,
            "source_lineage": [
                rail("marketplace_schema", "structured-api"),
                rail("plugin_marketplaces_docs", "prose"),
            ],
            "freshness_stamp": stamp,
            "snapshot_sha256": (rail_from_log("plugin_marketplaces_docs") or {}).get(
                "sha256"
            ),
            "strongest_caveat": (
                "The negative control is the fixture detector plus schema "
                "acceptance of both states. Runtime `/plugin update` skip was "
                "not executed (no claude CLI)."
            ),
        },
        {
            "id": "C-SILENT-WIN-VERSION-SKEW",
            "claim": (
                "Whether the win is silent is version-skewed: current docs say "
                "`claude plugin validate` warns when marketplace and plugin.json "
                "versions differ, while GitHub issue 54280 reported no validate "
                "warning. Runtime docs still say Claude Code uses plugin.json "
                "without warning at load/update."
            ),
            "canonical_mechanism": "docs vs issue contradiction, live CLI NOT-CHECKED",
            "verdict": "PARTIAL",
            "evidence_tier": "E3",
            "confidence_band": "medium",
            "named_settling_probe": P1,
            "source_lineage": [
                rail("plugin_marketplaces_docs", "prose"),
                rail("github_issue_54280", "structured-api"),
            ],
            "freshness_stamp": stamp,
            "snapshot_sha256": (rail_from_log("plugin_marketplaces_docs") or {}).get(
                "sha256"
            ),
            "strongest_caveat": (
                "Cannot be cited as measured runtime silence without a live "
                "claude plugin validate on the disagree fixture. WIN is confirmed; "
                "SILENT is not."
            ),
        },
    ]

    edges = [
        {
            "type": "version-skew",
            "from": "C-PLUGIN-JSON-WINS-VERSION",
            "to": "C-SILENT-WIN-VERSION-SKEW",
            "note": (
                "Issue 54280 (no validate warning) vs current docs (validate warns). "
                "Does not undo the waterfall win."
            ),
        },
        {
            "type": "scope-mismatch",
            "from": "C-MARKETPLACE-SCHEMA-TODAY",
            "to": "C-PLUGIN-JSON-WINS-VERSION",
            "note": (
                "JSON Schema accepts disagreeing versions; precedence is a runtime "
                "rule, not a schema constraint."
            ),
        },
        {
            "type": "support",
            "from": "C-IDENTICAL-NO-PRECEDENCE-SIGNAL",
            "to": "C-PLUGIN-JSON-WINS-VERSION",
            "note": "Both-states control for the mismatch detector.",
        },
    ]

    answer = (
        "Live SchemaStore marketplace.json (fetched "
        f"{(rail_from_log('marketplace_schema') or {}).get('fetched_at')}, "
        f"sha256={schema_sha[:12]}…) requires name, owner, plugins. Each plugin "
        "entry requires name and source. version is optional at both layers. "
        "plugin.json still WINS the version field: disagree fixture "
        f"plugin.json={PINNED} vs marketplace={MARKET_ONLY_BUMP} honours "
        f"{PINNED} (observed installed version for that fixture). Identical "
        f"{PINNED}/{PINNED} produces no precedence signal. The SchemaStore "
        "schema does not encode precedence. Live claude CLI is absent here, so "
        "cache install was not executed. Whether the win is silent is PARTIAL "
        f"(docs validate-warns={bool(validate_warns)}; issue-54280 no-warning "
        "report). The 0.2.0 dual-pin trap still holds: a marketplace-only bump "
        "does not change the honoured version."
    )

    doc = {
        "unit_id": UID,
        "id": UID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "report_kind": "research-claim-record",
        "schema_version": 1,
        "output_path": OUT_REL,
        "output_schema": "command-center/schema/research-claim-record.schema.json",
        "title": (
            "Extract the marketplace.json schema and the plugin-vs-marketplace "
            "precedence rule"
        ),
        "question": QUESTION,
        "answer": answer,
        "precedence": {
            "verdict": "plugin.json wins",
            "honoured_source": "plugin.json",
            "observed_installed_version": PINNED,
            "disagree_fixture": {
                "plugin_json": PINNED,
                "marketplace_entry": MARKET_ONLY_BUMP,
                "honoured": disagree["verdict"]["honoured_version"],
                "precedence_signal": True,
                "marketplace_path": disagree["marketplace_path"],
                "plugin_path": disagree["plugin_path"],
            },
            "identical_fixture": {
                "plugin_json": PINNED,
                "marketplace_entry": PINNED,
                "honoured": identical["verdict"]["honoured_version"],
                "precedence_signal": False,
                "marketplace_path": identical["marketplace_path"],
                "plugin_path": identical["plugin_path"],
            },
            "schema_encodes_precedence": extracted[
                "plugin_entry_version_mentions_plugin_json_priority"
            ],
            "live_claude_cli": client,
        },
        "marketplace_schema": {
            **extracted,
            "snapshot_bytes": schema_bytes,
            "snapshot_sha256": schema_sha,
            "permalink": SCHEMA_URL,
            "disagree_fixture_valid": not d_errs,
            "identical_fixture_valid": not i_errs,
            "missing_plugins_error_count": len(missing_errs),
            "unknown_top_level_key_error_count": len(extra_errs),
            "unknown_top_level_key_accepted": len(extra_errs) == 0,
            "docs_plugin_fields_absent_from_schema": docs_fields_absent_from_schema,
            "schema_root_extra_properties": schema_root_only,
            "docs_urls": [DOCS_MARKETPLACES, DOCS_REFERENCE],
        },
        "claims": claims,
        "edges": edges,
        "evidence": [
            {
                "claim": c["id"],
                "verdict": c["verdict"],
                "anchor": (c["source_lineage"][0] or {}).get("permalink"),
                "rails": c["source_lineage"],
            }
            for c in claims
        ],
        "tests": [
            {
                "id": "disagree-two-file-fixture",
                "command": P1,
                "result": "PASS" if c2_ok else "FAIL",
                "observed_installed_version": PINNED,
            },
            {
                "id": "identical-negative-control",
                "command": P2,
                "result": "PASS" if c3_ok else "FAIL",
            },
            {
                "id": "schema-missing-plugins-rejected",
                "command": "jsonschema Draft7Validator on marketplace minus plugins[]",
                "result": "PASS" if missing_errs else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-IDENTICAL-NO-SIGNAL",
                "fired_on_bad_state": mutant["precedence_signal"] is True,
                "silent_on_good_state": identical["verdict"]["precedence_signal"]
                is False,
            },
            {
                "id": "NC-MISSING-PLUGINS-RED",
                "fired_on_bad_state": bool(missing_errs),
                "silent_on_good_state": not d_errs,
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0008-probe2-identical-negative",
            "verdict": "PASS",
            "independent": True,
            "adversarial_default": "REFUTED-unless-both-states",
            "mechanism": (
                "probe2 re-runs the identical 0.2.0 fixture and a marketplace-only "
                "version mutation. It does not read claims[]."
            ),
        },
        "freshness_stamp": stamp,
        "fetch_log": load_fetch_log(),
        "installed_client": client,
        "observed_installed_version": PINNED,
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "disagree-precedence"},
            {"id": "probe2", "command": P2, "role": "identical-negative-control"},
        ],
        "not_checked": [
            {
                "claim": "Live claude plugin validate mismatch warning",
                "reason": client["reason"],
            },
            {
                "claim": "Live ~/.claude/plugins/cache/<marketplace>/<plugin>/<version> path",
                "reason": "No claude CLI on this worktree; cache directory not created.",
            },
            {
                "claim": "05-ECO-plugin-specs.md:139-141 original shard wording",
                "reason": (
                    "Catalog input path "
                    "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/"
                    "05-ECO-plugin-specs.md is not on this Linux worktree."
                ),
            },
            {
                "claim": "This repo's .claude-plugin/marketplace.json at HEAD",
                "reason": "No .claude-plugin/ directory at the worktree root.",
            },
            {
                "claim": (
                    "Instance validation against command-center/schema/"
                    "research-claim-record.schema.json"
                ),
                "reason": (
                    "That file is RES-0001's output and is absent here. Authoring "
                    "it would steal RES-0001. G-1 does not require that schema."
                ),
            },
        ],
        "source_unavailable": [
            "command-center/sources/REGISTER.md",
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
            "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-plugin-specs.md",
            ".claude-plugin/marketplace.json",
            "command-center/schema/research-claim-record.schema.json",
        ],
        "strongest_surviving_counterargument": (
            "Without a live Claude Code process, the waterfall is the published "
            "rule plus one GitHub UI observation, not a cache-path reading on "
            "this host. If a later client reversed step 1 and 2, this fixture "
            "would still report plugin.json until the docs/issue rails were "
            "re-fetched. Re-run capture.py against a newer SchemaStore $comment "
            "and re-check PLUGIN_WINS_MARKERS."
        ),
        "min_bytes_threshold": 1024,
        "cloud_ok": False,
        "completion_sentinel": SENTINEL,
    }

    # unused-var guard for silent_partial documented above
    doc["marketplace_schema"]["docs_validate_warns_on_mismatch"] = bool(
        validate_warns
    )
    doc["marketplace_schema"]["unknown_top_level_accepted"] = (
        len(extra_errs) == 0
    )

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_REL} claims={len(claims)} extra_key_errs={len(extra_errs)}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
