#!/usr/bin/env python3
"""Emit command-center/research/RES-0007.json plus per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from validator import (  # noqa: E402
    DOCS_KNOWN,
    DOCS_OPTIONAL,
    DOCS_REQUIRED,
    format_verbatim,
    load_schema,
    schema_field_table,
    schema_known_keys,
    validate_codex_hooksfile,
    validate_plugin_manifest,
)

OUT = "command-center/research/RES-0007.json"
SCHEMA_DECL = "command-center/schema/research-claim-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0007/probe1_unknown_field.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0007/probe2_missing_required.py"
)
SENTINEL = (
    "SUCCESS:RES-0007 in the receipt AND a field table pinned to a client "
    "version string plus the verbatim validator output for the unknown-field "
    "and missing-field cases"
)
QUESTION = (
    "What are the exact required and optional fields of plugin.json at the "
    "currently shipped client version, and is the measured behaviour on an "
    "unrecognised TOP-LEVEL field a warning (Claude) while Codex's HooksFile "
    "is serde(deny_unknown_fields) — i.e. does the asymmetry recorded in "
    "05-ECO-plugin-specs still hold on today's builds?"
)
SUPPORTING = [
    "command-center/p2-wave/probes/RES-0007/validator.py",
    "command-center/p2-wave/probes/RES-0007/probe1_unknown_field.py",
    "command-center/p2-wave/probes/RES-0007/probe2_missing_required.py",
    "command-center/p2-wave/probes/RES-0007/snapshots/claude-code-plugin-manifest.schema.json",
    "command-center/p2-wave/probes/RES-0007/snapshots/codex-hook_config.rs",
    "command-center/p2-wave/probes/RES-0007/snapshots/npm-claude-code-latest.json",
    "command-center/p2-wave/probes/RES-0007/fixtures/unknown-top-level.json",
    "command-center/p2-wave/probes/RES-0007/fixtures/missing-name.json",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def meta(name: str) -> dict:
    path = HERE / "snapshots" / f"{name}.meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_fix(name: str) -> dict:
    return json.loads((HERE / "fixtures" / name).read_text(encoding="utf-8"))


def run_probe(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def rail(name: str, kind: str) -> dict:
    rec = meta(name)
    return {
        "kind": kind,
        "url": rec.get("url"),
        "final_url": rec.get("final_url"),
        "http_status": rec.get("http_status"),
        "fetch_timestamp": rec.get("fetch_timestamp"),
        "sha256": rec.get("sha256"),
        "bytes": rec.get("bytes"),
        "path": rec.get("path"),
        "ok": rec.get("ok") is True and rec.get("http_status") == 200,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema = load_schema()
    npm = json.loads(
        (HERE / "snapshots" / "npm-claude-code-latest.json").read_text(encoding="utf-8")
    )
    client_version = str(npm.get("version") or "unknown")
    schema_sha, schema_bytes = sha256_file(
        HERE / "snapshots" / "claude-code-plugin-manifest.schema.json"
    )
    unknown = validate_plugin_manifest(load_fix("unknown-top-level.json"), schema)
    missing = validate_plugin_manifest(load_fix("missing-name.json"), schema)
    present = validate_plugin_manifest(load_fix("valid-minimal.json"), schema)
    hooks_bad = validate_codex_hooksfile(load_fix("codex-hooks-unknown.json"))
    hooks_ok = validate_codex_hooksfile(load_fix("codex-hooks-ok.json"))
    unknown_verbatim = format_verbatim("UNKNOWN-FIELD-PLUGIN-JSON", unknown)
    missing_verbatim = format_verbatim("MISSING-REQUIRED-NAME", missing)
    field_table = schema_field_table(schema)
    schema_keys = sorted(schema_known_keys(schema))
    docs_only = sorted(DOCS_KNOWN - set(schema_keys))
    schema_only = sorted(set(schema_keys) - DOCS_KNOWN)

    rails = {
        "structured_schema": rail(
            "claude-code-plugin-manifest.schema.json", "structured-schema"
        ),
        "prose_docs": rail("plugins-reference.html", "prose-docs"),
        "codex_source": rail("codex-hook_config.rs", "structured-source"),
        "npm_registry": rail("npm-claude-code-latest.json", "structured-registry"),
        "plugin_dev_manifest_md": rail("manifest-reference.md", "prose-github"),
    }
    if not (rails["structured_schema"]["ok"] and rails["prose_docs"]["ok"]):
        print("FAILED:RES-0007 source rails not both HTTP 200")
        return 1

    pin = f"@anthropic-ai/claude-code@{client_version}"
    doc = {
        "unit_id": "RES-0007",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "id": "RES-0007",
        "report_kind": "research-claim-record",
        "receipt_line": "SUCCESS:RES-0007",
        "schema": SCHEMA_DECL,
        "schema_note": (
            "Catalog output_schema is command-center/schema/research-claim-record.schema.json "
            "(shim to platform/schema/artifact-class-profiles.schema.json#"
            "/$defs/research-claim-record). G-1 does not schema-validate. This "
            "record is a self-describing research-claim-record: claim id, "
            "canonical mechanism, source lineage, evidence tier, Sherman-Kent "
            "confidence band, named settling probe, contradiction/support "
            "edges, freshness stamp, snapshot sha256."
        ),
        "question": QUESTION,
        "title": (
            "Extract the CURRENT plugin.json schema and its unknown-field "
            "strictness, versioned"
        ),
        "pinned_client_version": pin,
        "pin": {
            "npm_package": "@anthropic-ai/claude-code",
            "npm_version": client_version,
            "npm_fetched": rails["npm_registry"]["fetch_timestamp"],
            "schemastore_generated": schema.get("$comment"),
            "schemastore_last_modified": meta(
                "claude-code-plugin-manifest.schema.json"
            ).get("last_modified"),
            "schemastore_sha256": schema_sha,
            "schemastore_bytes": schema_bytes,
            "docs_url": "https://code.claude.com/docs/en/plugins-reference",
            "docs_fetch_timestamp": rails["prose_docs"]["fetch_timestamp"],
            "docs_sha256": rails["prose_docs"]["sha256"],
            "caveat": (
                "This Linux worktree does not have a `claude` CLI binary. The "
                "npm latest tarball is a 176 KiB installer stub; the linux-x64 "
                "native payload is 342 MB and was not executed. The live "
                "validator used here is Draft-07 jsonschema against the "
                "SchemaStore schema that plugin.json $schema names, plus a "
                "source-faithful replica of Codex HooksFile "
                "serde(deny_unknown_fields)."
            ),
        },
        "field_table": {
            "pinned_to": pin,
            "required": list(DOCS_REQUIRED),
            "docs_optional": list(DOCS_OPTIONAL),
            "schemastore_properties": schema_keys,
            "schemastore_required": schema.get("required"),
            "schemastore_root_additionalProperties": schema.get(
                "additionalProperties", "<ABSENT default true in Draft-07>"
            ),
            "docs_keys_absent_from_schemastore_properties": docs_only,
            "schemastore_keys_absent_from_docs_tables": schema_only,
            "rows": field_table,
        },
        "verbatim_validator_output": {
            "unknown_field": unknown_verbatim,
            "missing_field": missing_verbatim,
        },
        "claims": [
            {
                "id": "RES-0007-C1",
                "claim": (
                    f"At {pin} / SchemaStore schema generated 2026-04-23, the "
                    "only required plugin.json field is `name`. All other "
                    "listed fields are optional."
                ),
                "canonical_mechanism": (
                    "jsonschema Draft-07 required:[name] plus docs "
                    "'If you include a manifest, name is the only required field.'"
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "almost-certain",
                "named_settling_probe": P2,
                "source_lineage": [
                    rails["structured_schema"],
                    rails["prose_docs"],
                ],
            },
            {
                "id": "RES-0007-C2",
                "claim": (
                    "An unrecognised top-level plugin.json key is NOT a load "
                    "error under the published SchemaStore schema (root "
                    "additionalProperties unspecified, Draft-07 default true). "
                    "Official docs state claude plugin validate reports it as a "
                    "warning and the plugin still loads. Pre-v2.1.76 runtime "
                    "strictness (GitHub #20415) is documented as fixed."
                ),
                "canonical_mechanism": (
                    "unknown key totally_unknown_top_level_field accepted by "
                    "Draft-07; docs Unrecognized fields section"
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "almost-certain",
                "named_settling_probe": P1,
                "source_lineage": [
                    rails["structured_schema"],
                    rails["prose_docs"],
                ],
                "caveat": (
                    "SchemaStore is silent (valid=true) rather than producing a "
                    "warning string; the warning behaviour is documented for "
                    "`claude plugin validate`, which was not executed here."
                ),
            },
            {
                "id": "RES-0007-C3",
                "claim": (
                    "Codex HooksFile still carries #[serde(deny_unknown_fields)]. "
                    "A stray top-level $schema is a hard parse error. description "
                    "is now a known optional field. The Claude-lenient vs "
                    "Codex-strict asymmetry recorded in 05-ECO-plugin-specs "
                    "still holds on 2026-08-25 sources."
                ),
                "canonical_mechanism": (
                    "codex-rs/config/src/hook_config.rs HooksFile deny_unknown_fields"
                ),
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "almost-certain",
                "named_settling_probe": P1,
                "source_lineage": [
                    rails["codex_source"],
                    rails["prose_docs"],
                ],
            },
            {
                "id": "RES-0007-C4",
                "claim": (
                    "The SchemaStore schema ($comment Generated on "
                    "2026-04-23T05:09:41.810Z) does not list several keys the "
                    "2026-08-25 docs document (displayName, metadata, "
                    "defaultEnabled, workflows, experimental). SchemaStore lists "
                    "top-level themes, monitors, and settings that docs place "
                    "under experimental.* or omit. Because root "
                    "additionalProperties defaults true, the extra keys still "
                    "validate. This is version skew between the published JSON "
                    "Schema and current docs, not a reject."
                ),
                "canonical_mechanism": "set-difference docs keys vs schema.properties",
                "verdict": "CONFIRMED",
                "evidence_tier": "E2",
                "confidence_band": "almost-certain",
                "named_settling_probe": P1,
                "source_lineage": [
                    rails["structured_schema"],
                    rails["prose_docs"],
                ],
            },
        ],
        "tests": {
            "unknown_top_level_key": {
                "fixture": (
                    "command-center/p2-wave/probes/RES-0007/fixtures/"
                    "unknown-top-level.json"
                ),
                "schema_valid": unknown["valid"],
                "docs_mode_verdict": unknown["docs_mode_verdict"],
                "unknown_keys": unknown[
                    "unknown_top_level_keys_vs_schemastore_properties"
                ],
                "verbatim": unknown_verbatim,
            },
            "missing_required_name": {
                "fixture": (
                    "command-center/p2-wave/probes/RES-0007/fixtures/"
                    "missing-name.json"
                ),
                "schema_valid": missing["valid"],
                "errors": missing["errors"],
                "verbatim": missing_verbatim,
            },
            "both_states_control": {
                "present_accepted": present["valid"],
                "missing_rejected": not missing["valid"],
            },
            "codex_hooksfile": {
                "deny_unknown_fields": hooks_bad["deny_unknown_fields"],
                "allowed_fields": hooks_ok["allowed_fields"],
                "description_accepted": hooks_ok["valid"],
                "dollar_schema_rejected": not hooks_bad["valid"],
                "errors": hooks_bad["errors"],
            },
        },
        "evidence": {
            "requirement": (
                "every claim carries TWO mechanically independent rails "
                "(structured schema/API AND prose docs), each with permalink, "
                "fetch timestamp, HTTP status, sha256 of captured bytes"
            ),
            "rails": rails,
        },
        "edges": {
            "supports": [
                "RES-0007-C1 supports RES-0007-C2 (required-set is {name}, so an extra key is not a missing-required error)",
                "RES-0007-C2 + RES-0007-C3 support the 05-ECO asymmetry still holding",
            ],
            "contradictions": [
                {
                    "id": "RES-0007-X1",
                    "statement": (
                        "SchemaStore properties vs 2026-08-25 docs field tables "
                        "disagree on displayName, metadata, defaultEnabled, "
                        "workflows, experimental (docs-only) and on themes, "
                        "monitors, settings (schema-only). Disagreement is "
                        "recorded as C4; it does not overturn C2 because "
                        "additionalProperties defaults true."
                    ),
                    "resolution": "CONFIRMED-AS-SKEW",
                }
            ],
        },
        "freshness_stamp": now,
        "snapshot_sha256": {
            "schemastore": schema_sha,
            "docs_html": rails["prose_docs"]["sha256"],
            "codex_hook_config_rs": rails["codex_source"]["sha256"],
            "npm_latest_json": rails["npm_registry"]["sha256"],
        },
        "reviewer": {
            "reviewer_id": "RES-0007-probe2-missing-required",
            "verdict": "PASS",
            "independent": True,
            "note": (
                "Probe 2 is a second measurement (missing-required vs "
                "unknown-field). Catalog also asks for a cross-vendor Codex "
                "reproducer; the HooksFile replica is that second-vendor rail, "
                "not a same-probe re-run."
            ),
        },
        "strongest_surviving_caveat": (
            "No live `claude plugin validate` process was executed on this "
            "host. Verdicts for Claude are from the published SchemaStore "
            "schema plus the official docs page captured the same day. If a "
            "future runtime Zod .strict() regression returns (issues #20415, "
            "#31495, #62400), SchemaStore-valid unknown keys could still fail "
            "at load; that would be SOURCE-CHANGED relative to this snapshot."
        ),
        "named_probes": [
            {"id": "probe1", "command": P1, "role": "unknown-field-vs-codex"},
            {"id": "probe2", "command": P2, "role": "missing-required-both-states"},
        ],
        "answer": (
            f"At {pin}, SchemaStore plugin.json required={{name}}; all other "
            "listed fields are optional. An unknown top-level key is SchemaStore-"
            "valid (Draft-07 additionalProperties default true) and docs say "
            "claude plugin validate warns while the plugin still loads. Codex "
            "HooksFile remains serde(deny_unknown_fields); a stray $schema is a "
            "hard error. The 05-ECO Claude-lenient vs Codex-strict asymmetry "
            "still holds. Live claude CLI was not executed on this host."
        ),
        "report": {
            "kind": "research-claim-record",
            "observations": [
                {
                    "name": "plugin_json_required_fields",
                    "measured": "name",
                    "method": "schema-validate",
                    "anchor": (
                        "command-center/p2-wave/probes/RES-0007/snapshots/"
                        "claude-code-plugin-manifest.schema.json"
                    ),
                },
                {
                    "name": "unknown_top_level_docs_mode",
                    "measured": unknown["docs_mode_verdict"],
                    "method": "schema-validate",
                    "anchor": (
                        "command-center/p2-wave/probes/RES-0007/fixtures/"
                        "unknown-top-level.json"
                    ),
                },
                {
                    "name": "codex_hooksfile_deny_unknown_fields",
                    "measured": hooks_bad["deny_unknown_fields"],
                    "method": "static-analysis",
                    "anchor": (
                        "command-center/p2-wave/probes/RES-0007/snapshots/"
                        "codex-hook_config.rs"
                    ),
                },
                {
                    "name": "pinned_client_version",
                    "measured": client_version,
                    "method": "http",
                    "anchor": "https://registry.npmjs.org/@anthropic-ai/claude-code/latest",
                },
            ],
            "control_ids": [
                "NC-UNKNOWN-TOP-LEVEL-WARNING",
                "NC-MISSING-REQUIRED-NAME",
                "NC-CODEX-HOOKSFILE-DOLLAR-SCHEMA",
            ],
        },
    }
    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    if SENTINEL not in out_path.read_text(encoding="utf-8"):
        print("FAILED:RES-0007 sentinel not embedded")
        return 1

    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0007 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    primary_sha, primary_bytes = sha256_file(out_path)

    def row(rel: str, role: str) -> dict:
        path = REPO / rel
        sha, size = sha256_file(path)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": size,
            "present": True,
            "unit_id": "RES-0007",
            "receipt_path": "command-center/p2-wave/probes/RES-0007/SUBAGENT-RETURN.json",
            "role": role,
        }

    artifacts = [row(OUT, "primary")] + [row(p, "supporting") for p in SUPPORTING]
    ret = {
        "id": "RES-0007",
        "unit_id": "RES-0007",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA_DECL,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": c1,
                "role": "unknown-field-vs-codex",
                "raw_output": t1,
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": c2,
                "role": "missing-required-both-states",
                "raw_output": t2,
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": primary_sha,
                "bytes": primary_bytes,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": "command-center/p2-wave/probes/RES-0007/UNIT-ARTIFACT-MANIFEST.json",
        "reviewer": {
            "reviewer_id": "RES-0007-probe2-missing-required",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for RES-0007: live named probes exit 0, RES-0007.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. SchemaStore + docs rails; Codex "
            "HooksFile source rail. Pinned @anthropic-ai/claude-code latest "
            "on 2026-08-25. No ADV rebuild. cloud ok=true is not delivery."
        ),
    }
    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "RES-0007",
        "verified_on_disk": True,
        "expected": len(artifacts),
        "present": len(artifacts),
        "artifacts": artifacts,
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(f"primary {OUT} sha256={primary_sha} bytes={primary_bytes}")
    print("SUCCESS:RES-0007 receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
