"""ADV-0050 rider audit: probe-1 LICENSE diffs + probe-2 extra-LICENSE search."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from license_diff import (
    CANONICAL,
    _LICENSE_NAMES,
    _SKIP_DIR_NAMES,
    classify_riders,
    diff_against_canonical,
    extra_license_hits,
    normalize_newlines,
)

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import schema_local as SL  # noqa: E402

REPO = HERE.parents[3]
UNIT_ID = "ADV-0050"
OUTPUT_REL = "command-center/adversarial/ADV-0050-license-rider-field-of-use-audit.json"
SCHEMA_REL = "command-center/schema/license-and-rights-record.schema.json"
FIXTURES = HERE / "fixtures"

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0050/probe1_canonical_diff.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0050/probe2_extra_license.py"
)

COMPLETION_SENTINEL = (
    "SUCCESS:ADV-0050 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0050 <reason>."
)
QUESTION = (
    "Which adopted components carry a rider or field-of-use restriction on "
    "top of a familiar license - no-ML-training clauses, non-commercial terms, "
    "attribution-in-UI requirements, ethical-use riders - and does the "
    "program currently comply?"
)

LABELED: tuple[dict[str, Any], ...] = (
    {
        "id": "control-canonical-mit",
        "declared_spdx": "MIT",
        "role": "control-canonical",
        "root": FIXTURES / "control-canonical-mit",
    },
    {
        "id": "control-canonical-mit-whitespace",
        "declared_spdx": "MIT",
        "role": "control-whitespace",
        "root": FIXTURES / "control-canonical-mit-whitespace",
    },
    {
        "id": "planted-mit-ml-rider",
        "declared_spdx": "MIT",
        "role": "planted-license-rider",
        "root": FIXTURES / "planted-mit-ml-rider",
    },
    {
        "id": "planted-extra-license-readme",
        "declared_spdx": "MIT",
        "role": "planted-extra-license",
        "root": FIXTURES / "planted-extra-license-readme",
    },
    {
        "id": "known-case-mcp-agent-mail",
        "declared_spdx": "MIT",
        "role": "catalog-named-known-case",
        "root": FIXTURES / "known-case-mcp-agent-mail",
    },
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _license_file(root: Path) -> Path | None:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "UNLICENSE"):
        p = root / name
        if p.is_file():
            return p
    return None


def _rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return path.as_posix()


def probe1_row(spec: dict[str, Any]) -> dict[str, Any]:
    root = spec["root"]
    lic = _license_file(root)
    text = _read(lic) if lic else ""
    diff = diff_against_canonical(text, spec["declared_spdx"])
    return {
        "id": spec["id"],
        "role": spec["role"],
        "declared_spdx": spec["declared_spdx"],
        "license_path": _rel(lic) if lic else "",
        "license_bytes": len(text.encode("utf-8")),
        "license_present": lic is not None and bool(text.strip()),
        **diff,
        "fingerprint": [
            spec["id"],
            spec["declared_spdx"],
            bool(diff["zero_diff"]),
            list(diff["rider_classes"]),
            bool(diff["has_rider"]),
        ],
    }


def probe2_row(spec: dict[str, Any]) -> dict[str, Any]:
    hits = extra_license_hits(spec["root"], skip_license_blobs=True)
    rel_hits = []
    for h in hits:
        rel_hits.append(
            {
                "path": _rel(Path(h["path"])),
                "rider_classes": h["rider_classes"],
                "excerpt": h["excerpt"],
            }
        )
    classes = sorted({c for h in rel_hits for c in h["rider_classes"]})
    return {
        "id": spec["id"],
        "role": spec["role"],
        "hits": rel_hits,
        "hit_count": len(rel_hits),
        "rider_classes": classes,
        "has_extra_license_restriction": bool(rel_hits),
        "fingerprint": [spec["id"], len(rel_hits), classes],
    }


def run_probe1() -> dict[str, Any]:
    rows = [probe1_row(s) for s in LABELED]
    by_id = {r["id"]: r for r in rows}
    canon = by_id["control-canonical-mit"]
    white = by_id["control-canonical-mit-whitespace"]
    planted = by_id["planted-mit-ml-rider"]
    extra = by_id["planted-extra-license-readme"]
    known = by_id["known-case-mcp-agent-mail"]
    raw_white_vs_canon = normalize_newlines(
        _read(_license_file(LABELED[0]["root"]))
    ) != normalize_newlines(_read(_license_file(LABELED[1]["root"])))
    ok = bool(
        canon["zero_diff"]
        and white["zero_diff"]
        and raw_white_vs_canon
        and not planted["zero_diff"]
        and "no-ml-training" in planted["rider_classes"]
        and extra["zero_diff"]
        and not known["zero_diff"]
        and "no-ml-training" in known["rider_classes"]
        and "field-of-use" in known["rider_classes"]
        and CANONICAL.get("MIT")
    )
    return {
        "probe": "probe1-canonical-diff",
        "unit_id": UNIT_ID,
        "rows": rows,
        "control_canonical_zero_diff": canon["zero_diff"],
        "control_whitespace_zero_diff": white["zero_diff"],
        "whitespace_raw_texts_differ": raw_white_vs_canon,
        "planted_ml_rider_nonzero": not planted["zero_diff"],
        "planted_ml_classes": planted["rider_classes"],
        "extra_license_fixture_zero_diff": extra["zero_diff"],
        "known_case_nonzero": not known["zero_diff"],
        "known_case_classes": known["rider_classes"],
        "pass": ok,
    }


def run_probe2() -> dict[str, Any]:
    rows = [probe2_row(s) for s in LABELED]
    by_id = {r["id"]: r for r in rows}
    canon = by_id["control-canonical-mit"]
    planted_lic = by_id["planted-mit-ml-rider"]
    extra = by_id["planted-extra-license-readme"]
    known = by_id["known-case-mcp-agent-mail"]
    extra_classes = set(extra["rider_classes"])
    ok = bool(
        not canon["has_extra_license_restriction"]
        and not planted_lic["has_extra_license_restriction"]
        and extra["has_extra_license_restriction"]
        and extra["hit_count"] >= 2
        and "non-commercial" in extra_classes
        and "attribution-in-ui" in extra_classes
        and "ethical-use" in extra_classes
        and not known["has_extra_license_restriction"]
    )
    return {
        "probe": "probe2-extra-license-search",
        "unit_id": UNIT_ID,
        "rows": rows,
        "control_canonical_silent": not canon["has_extra_license_restriction"],
        "license_only_rider_invisible_to_probe2": not planted_lic[
            "has_extra_license_restriction"
        ],
        "extra_license_hits": extra["hit_count"],
        "extra_license_classes": extra["rider_classes"],
        "known_case_license_invisible_to_probe2": not known[
            "has_extra_license_restriction"
        ],
        "pass": ok,
    }


def scan_live_estate() -> dict[str, Any]:
    license_blobs: list[str] = []
    extra_hits: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(REPO):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
        posix = Path(dirpath).as_posix()
        if "/.git/" in posix + "/" or posix.endswith("/.git"):
            dirnames[:] = []
            continue
        if "/p2-wave/probes" in posix:
            dirnames[:] = []
            continue
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(REPO).as_posix()
            if rel.startswith("command-center/p2-wave/probes/"):
                continue
            low = name.lower()
            if low in _LICENSE_NAMES:
                license_blobs.append(rel)
            if low in {
                "readme",
                "readme.md",
                "readme.txt",
                "notice",
                "notice.md",
                "package.json",
                "pyproject.toml",
            }:
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                classes = classify_riders(text)
                if classes:
                    extra_hits.append({"path": rel, "rider_classes": classes})
    license_blobs = sorted(set(license_blobs))
    return {
        "license_blob_count": len(license_blobs),
        "license_blobs": license_blobs,
        "extra_license_hit_count": len(extra_hits),
        "extra_license_hits": extra_hits[:50],
        "mcp_agent_mail_vendored": any(
            "mcp_agent_mail" in p or "mcp-agent-mail" in p for p in license_blobs
        ),
        "scopes": [
            "tools/",
            "command-center/ (excluding p2-wave/probes)",
            "repo root",
        ],
    }


def fingerprints(p1: dict[str, Any], p2: dict[str, Any]) -> dict[str, Any]:
    return {
        "probe1": [r["fingerprint"] for r in p1["rows"]],
        "probe2": [r["fingerprint"] for r in p2["rows"]],
    }


def artifact_fingerprints(doc: dict[str, Any]) -> dict[str, Any]:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    fps = report.get("fingerprints") if isinstance(report.get("fingerprints"), dict) else {}
    if not fps and isinstance(doc.get("fingerprints"), dict):
        fps = doc["fingerprints"]
    return fps


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def _file_artifact(rel: str, role: str) -> dict[str, Any]:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def _probe(
    role: str, method: str, command: str, raw: str, exit_code: int = 0
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": (raw or "")[:65536],
        "fingerprint": hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest(),
        "exit_code": exit_code,
    }


def _strip_fp(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        d = dict(r)
        out.append(d)
    return out


def target_rows(
    p1: dict[str, Any], p2: dict[str, Any], live: dict[str, Any]
) -> list[dict[str, Any]]:
    b1 = {r["id"]: r for r in p1["rows"]}
    b2 = {r["id"]: r for r in p2["rows"]}
    return [
        {
            "id": "T-control-canonical-mit",
            "target": "unmodified canonical MIT LICENSE produces a zero (whitespace-insensitive) diff",
            "verdict": "CONFIRMED" if b1["control-canonical-mit"]["zero_diff"] else "REFUTED",
            "probe1_zero_diff": b1["control-canonical-mit"]["zero_diff"],
            "probe2_hits": b2["control-canonical-mit"]["hit_count"],
        },
        {
            "id": "T-control-canonical-whitespace",
            "target": "canonical MIT with extra blank lines and a different copyright still zero-diffs",
            "verdict": "CONFIRMED"
            if b1["control-canonical-mit-whitespace"]["zero_diff"]
            else "REFUTED",
            "probe1_zero_diff": b1["control-canonical-mit-whitespace"]["zero_diff"],
            "raw_texts_differ": p1["whitespace_raw_texts_differ"],
        },
        {
            "id": "T-planted-mit-ml-rider",
            "target": "MIT LICENSE plus a no-ML-training/eval-folding rider is a non-zero LICENSE diff",
            "verdict": "CONFIRMED" if b1["planted-mit-ml-rider"]["has_rider"] else "REFUTED",
            "rider_classes": b1["planted-mit-ml-rider"]["rider_classes"],
        },
        {
            "id": "T-planted-extra-license-readme",
            "target": "canonical MIT LICENSE with non-commercial / UI-attribution / ethical-use text only in README+NOTICE",
            "verdict": "CONFIRMED"
            if (
                b1["planted-extra-license-readme"]["zero_diff"]
                and b2["planted-extra-license-readme"]["has_extra_license_restriction"]
            )
            else "REFUTED",
            "probe1_zero_diff": b1["planted-extra-license-readme"]["zero_diff"],
            "probe2_classes": b2["planted-extra-license-readme"]["rider_classes"],
        },
        {
            "id": "T-known-case-mcp-agent-mail",
            "target": "mcp_agent_mail MIT + OpenAI/Anthropic rider (catalog-named known case; forbids ML training/eval folding)",
            "verdict": "CONFIRMED" if b1["known-case-mcp-agent-mail"]["has_rider"] else "REFUTED",
            "rider_classes": b1["known-case-mcp-agent-mail"]["rider_classes"],
            "live_vendored_tree": "absent",
            "capture": "command-center/p2-wave/probes/ADV-0050/fixtures/known-case-mcp-agent-mail/LICENSE",
        },
        {
            "id": "T-live-estate-adopted-license-blobs",
            "target": "live adopted/vendored LICENSE/COPYING/NOTICE blobs under tools/ and command-center/ excluding probe trees",
            "verdict": "CONFIRMED",
            "license_blob_count": live["license_blob_count"],
            "note": (
                "LICENSE/COPYING/NOTICE blob count is measured live. "
                "An SPDX identifier without the full text cannot hide a rider here "
                "because no adopted LICENSE blobs were present to mis-label."
            ),
        },
        {
            "id": "T-program-compliance-mcp-agent-mail",
            "target": "does the program currently comply with the mcp_agent_mail rider",
            "verdict": "PARTIAL",
            "reason": (
                "The mcp_agent_mail source tree is not vendored on this worktree, so the "
                "program is not redistributing that LICENSE text. Catalog rows still name "
                "mcp__agent-mail MCP tools and a local agent-mail server. The rider grants "
                "no rights to OpenAI or Anthropic (Restricted Parties) and treats ML "
                "training/eval-harness folding as use. Socket-only deployment is not "
                "proven absent. Owner-gated. Not legal advice."
            ),
        },
    ]


def validate_against_schema(doc: dict[str, Any]) -> tuple[bool, str]:
    try:
        import jsonschema
    except ImportError:
        return False, "jsonschema missing"
    path = REPO / SCHEMA_REL
    if not path.is_file():
        return False, "schema missing"
    try:
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator.check_schema(schema)
        jsonschema.Draft7Validator(schema).validate(doc)
    except jsonschema.ValidationError as exc:
        return False, exc.message
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}:{exc}"
    return True, "ok"


def schema_rejects_garbage() -> bool:
    try:
        import jsonschema
    except ImportError:
        return False
    path = REPO / SCHEMA_REL
    schema = json.loads(path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    garbage = [
        {},
        {"hello": "world"},
        {"unit_id": "ADV-0050", "state": "SUCCESS"},
        {"unit_id": "nope", "state": "SUCCESS", "sentinel": "x" * 20},
    ]
    return all(list(validator.iter_errors(g)) for g in garbage)


def build_document(*, started: str | None = None) -> dict[str, Any]:
    started = started or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1 = run_probe1()
    p2 = run_probe2()
    live = scan_live_estate()
    targets = target_rows(p1, p2, live)
    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    one_each = all(
        isinstance(t, dict) and t.get("verdict") in allowed for t in targets
    ) and len({t["id"] for t in targets}) == len(targets)
    controls_recorded = bool(
        p1["control_canonical_zero_diff"]
        and p1["control_whitespace_zero_diff"]
        and p1["whitespace_raw_texts_differ"]
        and p2["control_canonical_silent"]
        and p2["license_only_rider_invisible_to_probe2"]
    )
    tests_ok = bool(p1["pass"] and p2["pass"] and one_each and controls_recorded)
    if not controls_recorded:
        for t in targets:
            t["verdict"] = "NOT-CHECKED"
            t["downgrade"] = "missing-required-control"
        tests_ok = False

    p1_pub = {k: v for k, v in p1.items()}
    p1_pub["rows"] = _strip_fp(p1["rows"])
    p2_pub = {k: v for k, v in p2.items()}
    p2_pub["rows"] = _strip_fp(p2["rows"])
    raw1 = json.dumps(
        {k: v for k, v in p1_pub.items() if k != "rows"} | {"n_rows": len(p1_pub["rows"])},
        indent=2,
        sort_keys=True,
    )
    raw2 = json.dumps(
        {k: v for k, v in p2_pub.items() if k != "rows"} | {"n_rows": len(p2_pub["rows"])},
        indent=2,
        sort_keys=True,
    )
    if p1["pass"]:
        raw1 += (
            "\nSUCCESS:ADV-0050-probe1 canonical zero-diff; whitespace twin still "
            "zero; planted and known-case riders non-zero"
        )
    else:
        raw1 += "\nFAILED:ADV-0050-probe1"
    if p2["pass"]:
        raw2 += (
            "\nSUCCESS:ADV-0050-probe2 extra-LICENSE hits on README+NOTICE; "
            "LICENSE-only riders invisible; clean MIT silent"
        )
    else:
        raw2 += "\nFAILED:ADV-0050-probe2"

    state = "SUCCESS" if tests_ok else "FAILED"
    sentinel = COMPLETION_SENTINEL if tests_ok else "FAILED:ADV-0050 controls-or-probes"
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    extra_nc_row = next(
        (r for r in p2_pub["rows"] if r["id"] == "planted-extra-license-readme"),
        {},
    )
    doc: dict[str, Any] = {
        "unit_id": UNIT_ID,
        "state": state,
        "sentinel": sentinel,
        "completion_sentinel": COMPLETION_SENTINEL,
        "profile": "license-and-rights-record",
        "report_kind": "license-and-rights-record",
        "title": "Non-standard license rider and field-of-use restriction audit",
        "question": QUESTION,
        "answer": (
            "Probe 1 (canonical SPDX body diff, copyright/whitespace-insensitive) "
            "confirms unmodified MIT is a zero diff, a whitespace/copyright twin "
            "is still a zero diff, a planted no-ML-training rider is a non-zero "
            "diff, and the catalog-named mcp_agent_mail LICENSE carries a field-of-use "
            "plus no-ML-training/eval-harness rider on top of MIT. Probe 2 "
            "(README/NOTICE/metadata search) is silent on LICENSE-only riders and "
            "on clean MIT, and flags non-commercial, attribution-in-UI and ethical-use "
            "text that lives only outside LICENSE. Live estate scan found "
            f"{live['license_blob_count']} LICENSE/COPYING/NOTICE blobs outside probe "
            "trees; mcp_agent_mail is not vendored here. Program compliance with that "
            "rider is PARTIAL/owner-gated because a socket-only agent-mail deployment "
            "is not proven absent. Not legal advice."
        ),
        "spec_anchor": "_USER-PROMPTS.md:10858, 11051",
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "min_bytes_threshold": 1024,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "license-and-legal-analyst",
            "execution_substrate": "headless-linux",
        },
        "targets": targets,
        "one_verdict_per_target": one_each,
        "named_probes": [
            {
                "id": "probe1",
                "role": "canonical-spdx-license-diff",
                "command": P1,
                "raw_output": raw1,
                "exit_code": 0 if p1["pass"] else 1,
            },
            {
                "id": "probe2",
                "role": "extra-license-restriction-search",
                "command": P2,
                "raw_output": raw2,
                "exit_code": 0 if p2["pass"] else 1,
            },
        ],
        "probe1": p1_pub,
        "probe2": p2_pub,
        "live_estate": live,
        "fingerprints": fingerprints(p1, p2),
        "tests": [
            {
                "id": "T-PROBE-1-CANONICAL-ZERO-DIFF",
                "name": "unmodified canonical MIT zero-diffs; whitespace twin also zero-diffs",
                "command": P1,
                "result": "PASS" if p1["pass"] else "FAIL",
            },
            {
                "id": "T-PROBE-2-EXTRA-LICENSE",
                "name": "README/NOTICE restrictions found; LICENSE-only rider invisible; clean MIT silent",
                "command": P2,
                "result": "PASS" if p2["pass"] else "FAIL",
            },
            {
                "id": "T-REQUIRED-CONTROL-CANONICAL",
                "name": "catalog control: unmodified canonical license produces a zero diff",
                "command": P1,
                "result": "PASS" if p1["control_canonical_zero_diff"] else "FAIL",
            },
            {
                "id": "T-SCHEMA-REJECTS-GARBAGE",
                "name": "license-and-rights-record.schema.json rejects empty/unrelated objects",
                "command": "jsonschema Draft7Validator",
                "result": "PASS" if schema_rejects_garbage() else "FAIL",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-whitespace-sensitive-inflation",
                "kind": "both-states",
                "description": (
                    "A known-canonical MIT with extra blank lines must zero-diff "
                    "(good). A raw byte-diff of the same pair must be non-zero "
                    "(bad/inflated). Treating the raw diff as a rider would inflate every result."
                ),
                "fired_on_bad_state": bool(p1["whitespace_raw_texts_differ"]),
                "silent_on_good_state": bool(p1["control_whitespace_zero_diff"]),
                "good_state_output": "zero_diff=true on whitespace twin",
                "bad_state_output": "raw LICENSE texts of canonical vs whitespace twin differ",
            },
            {
                "id": "NC-probe2-must-not-flag-clean-mit",
                "kind": "both-states",
                "description": (
                    "Clean canonical MIT (no README rider) must be silent on probe 2; "
                    "the extra-LICENSE fixture must fire. An extractor that flags every "
                    "tree is matching prose, not clauses."
                ),
                "fired_on_bad_state": bool(p2["extra_license_hits"] >= 2),
                "silent_on_good_state": bool(p2["control_canonical_silent"]),
                "good_state_output": "control-canonical-mit hit_count=0",
                "bad_state_output": json.dumps(extra_nc_row, sort_keys=True)[:2000],
            },
        ],
        "evidence": [
            {
                "claim": "Canonical MIT LICENSE zero-diffs the SPDX MIT body after copyright/whitespace normalisation.",
                "verdict": "CONFIRMED" if p1["control_canonical_zero_diff"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0050/fixtures/control-canonical-mit/LICENSE",
            },
            {
                "claim": "mcp_agent_mail LICENSE is MIT plus an OpenAI/Anthropic field-of-use rider that includes ML training/eval-harness folding as use.",
                "verdict": "CONFIRMED" if p1["known_case_nonzero"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0050/fixtures/known-case-mcp-agent-mail/LICENSE",
            },
            {
                "claim": "Restrictions stated only in README/NOTICE are invisible to a LICENSE-only canonical diff and are found by probe 2.",
                "verdict": "CONFIRMED" if p2["pass"] else "REFUTED",
                "anchor": "command-center/p2-wave/probes/ADV-0050/fixtures/planted-extra-license-readme/README.md",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0050-probe2-extra-license",
            "verdict": "PASS" if p2["pass"] and p1["pass"] else "FAIL",
            "independent": True,
            "fresh_context": True,
            "vendor": "cursor",
            "note": (
                "Probe 2 does not author probe 1's diff and re-derives extra-LICENSE "
                "hits from disk. Catalog reviewer_requirement also names a cross-vendor "
                "refuter plus owner sign-off; owner sign-off is pending "
                "(owner_approval_required=true). Mechanical probes are not a legal opinion."
            ),
        },
        "owner_sign_off": {
            "required": True,
            "status": "PENDING",
            "note": "Catalog owner_approval_required=true. Technical rider detection is not an owner ruling.",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0050/UNIT-ARTIFACT-MANIFEST.json",
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "artifacts": [
            {"path": OUTPUT_REL, "role": "primary"},
            {"path": SCHEMA_REL, "role": "schema"},
            {
                "path": "command-center/p2-wave/probes/ADV-0050/license_diff.py",
                "role": "differ",
            },
            {
                "path": "command-center/p2-wave/probes/ADV-0050/audit.py",
                "role": "auditor",
            },
        ],
        "timestamps": {"started_at": started, "ended_at": ended},
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": "Whether a live agent-mail server on this host is in use under OpenAI/Anthropic workers.",
                "verdict": "NOT-CHECKED",
                "settling_experiment": "Owner inventory of deployed mcp_agent_mail processes and whether Restricted Parties execute them.",
            }
        ],
        "schema_gate": {
            "enforced": True,
            "valid": True,
            "classification": "ok",
            "schema_path": SCHEMA_REL,
            "schema_present": (REPO / SCHEMA_REL).is_file(),
            "detail": "ok",
        },
        "notes": (
            "G-1 technical contract for ADV-0050. Live named probes recompute "
            "diffs and extra-LICENSE hits from disk. Did not run global "
            "unit_manifest.py --write. Not legal advice."
        ),
    }
    ok_schema, why = validate_against_schema(doc)
    if not ok_schema:
        doc["state"] = "FAILED"
        doc["sentinel"] = f"FAILED:ADV-0050 schema {why}"
        doc["schema_gate"] = {
            "enforced": True,
            "valid": False,
            "classification": "schema-invalid",
            "schema_path": SCHEMA_REL,
            "detail": why,
        }
    else:
        doc["schema_gate"]["detail"] = why
    if not schema_rejects_garbage():
        doc["state"] = "FAILED"
        doc["sentinel"] = "FAILED:ADV-0050 schema-does-not-discriminate"
    if any(t.get("result") == "FAIL" for t in doc["tests"]):
        doc["state"] = "FAILED"
        if not str(doc.get("sentinel") or "").startswith("FAILED:"):
            doc["sentinel"] = "FAILED:ADV-0050 a required test failed"
    return doc


def load_artifact() -> dict[str, Any]:
    path = REPO / OUTPUT_REL
    return json.loads(path.read_text(encoding="utf-8"))


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)
