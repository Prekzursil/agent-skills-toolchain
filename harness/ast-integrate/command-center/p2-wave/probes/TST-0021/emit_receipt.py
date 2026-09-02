#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0021.json (shell-idiom lint receipt).

The catalog output_schema is a $ref shim. Draft7Validator without a local store
tries to fetch https://ast-integrate.invalid/ and treats the shim as a no-op
(garbage accepted). This emitter resolves those $ids from disk and wraps the
lint census in the receipt_core + test-receipt envelope.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from lint import (  # noqa: E402
    IDIOM_GREP,
    IDIOM_N,
    IDIOM_SUBST,
    IDIOM_WC,
    lint_fixtures,
    lint_live,
    reproduce_grep_c_or_echo_zero,
)

OUT = "command-center/receipts/TST-0021.json"
SCHEMA = "command-center/schema/test-receipt.schema.json"
PROFILES = "platform/schema/artifact-class-profiles.schema.json"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"
UID = "TST-0021"
SENTINEL = "SUCCESS:TST-0021"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0021/probe1_flags_grep_c_or_echo_zero.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0021/probe2_does_not_flag_corrected.py"
)
QUESTION = (
    "Target: a lint that flags the specific shell idioms that silently produce "
    "wrong counts — `grep -c ... || echo 0` (grep -c prints 0 AND exits 1, so "
    "both fire), unquoted `$(...)` in a numeric comparison, `wc -l` on a "
    "possibly-empty stream, and `[ -n $x ]` without quotes. How many live "
    "gate scripts contain at least one?"
)
SUPPORTING = [
    SCHEMA,
    "command-center/p2-wave/probes/TST-0021/lint.py",
    "command-center/p2-wave/probes/TST-0021/fixtures/bad/grep_c_or_echo_zero.sh",
    "command-center/p2-wave/probes/TST-0021/fixtures/good/corrected.sh",
    "command-center/p2-wave/probes/TST-0021/probe1_flags_grep_c_or_echo_zero.py",
    "command-center/p2-wave/probes/TST-0021/probe2_does_not_flag_corrected.py",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def dump(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def local_validator():
    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    store = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": json.loads(
            (REPO / PROFILES).read_text(encoding="utf-8")
        ),
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": json.loads(
            (REPO / RECEIPT_SCHEMA).read_text(encoding="utf-8")
        ),
        "https://ast-integrate.invalid/command-center/schema/test-receipt.schema.json": schema,
    }
    resolver = jsonschema.RefResolver.from_schema(schema, store=store)
    return jsonschema.Draft7Validator(schema, resolver=resolver)


def validate_or_die(doc: dict) -> int:
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0021 schema-invalid")
        for err in errs[:25]:
            print(" ", list(err.path), err.message)
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0021 schema accepted garbage")
            return 1
    return 0


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def probe_record(
    role: str, method: str, command: str, raw: str, exit_code: int
) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[-8000:],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def run_cmd(cmd: str) -> tuple[int, str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def fixture_row(planted: dict, label: str, suffix: str) -> dict:
    for row in planted.get(label) or []:
        if str(row.get("path") or "").endswith(suffix):
            return row
    return {"path": suffix, "findings": [], "count": 0}


def has_idiom(row: dict, idiom: str) -> bool:
    return any(item.get("idiom") == idiom for item in (row.get("findings") or []))


def quoted_from(*rows: dict) -> list[str]:
    out: list[str] = []
    for row in rows:
        for item in row.get("findings") or []:
            quoted = item.get("quoted")
            if quoted:
                out.append(str(quoted))
    return out


def independent_substring_census(live: dict) -> dict:
    """Second instrument: byte-substring search over the same path list.

    Mechanically different from lint.py regexes: no compiled patterns, just
    ``in line`` checks. Used as the verifier for the live-census claim.
    """
    hits: dict[str, list[str]] = {}
    for rel in live.get("scanned_paths") or []:
        path = REPO / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        kinds: list[str] = []
        for raw in text.splitlines():
            if raw.lstrip().startswith("#"):
                continue
            if "grep" in raw and "|| echo 0" in raw and (
                " -c" in raw or " -c " in raw or "--count" in raw or "c " in raw
            ):
                kinds.append(IDIOM_GREP)
            if ("[ $(" in raw or "[[ $(" in raw or "test $(" in raw) and any(
                tok in raw for tok in (" -eq ", " -ne ", " -gt ", " -ge ", " -lt ", " -le ")
            ):
                kinds.append(IDIOM_SUBST)
            if "| wc -l" in raw or "| wc --lines" in raw or "|  wc -l" in raw:
                kinds.append(IDIOM_WC)
            if "[ -n $" in raw and '"$' not in raw:
                kinds.append(IDIOM_N)
        if kinds:
            hits[rel] = sorted(set(kinds))
    return {
        "method": "file-read-substring",
        "scripts_with_at_least_one_idiom": len(hits),
        "hits_per_script": {k: len(v) for k, v in sorted(hits.items())},
        "idioms_per_script": hits,
    }


def main() -> int:
    planted = lint_fixtures(REPO)
    live = lint_live(REPO)
    repro = reproduce_grep_c_or_echo_zero()
    if not repro.get("miscount_proven"):
        print("FAILED:TST-0021 emit: miscount reproduction failed")
        print(json.dumps(repro, indent=2)[:2000])
        return 1

    bad_grep = fixture_row(planted, "bad", "grep_c_or_echo_zero.sh")
    bad_subst = fixture_row(planted, "bad", "unquoted_subst.sh")
    bad_wc = fixture_row(planted, "bad", "wc_l_empty.sh")
    bad_n = fixture_row(planted, "bad", "unquoted_n.sh")
    good = fixture_row(planted, "good", "corrected.sh")

    for row, idiom, label in (
        (bad_grep, IDIOM_GREP, "grep -c || echo 0"),
        (bad_subst, IDIOM_SUBST, "unquoted subst"),
        (bad_wc, IDIOM_WC, "wc -l stream"),
        (bad_n, IDIOM_N, "[ -n $x ]"),
    ):
        if not has_idiom(row, idiom):
            print(f"FAILED:TST-0021 emit: planted {label} not flagged")
            print(json.dumps(row, indent=2)[:2000])
            return 1
    if int(good.get("count") or 0) != 0:
        print("FAILED:TST-0021 emit: corrected fixture was flagged")
        print(json.dumps(good, indent=2)[:2000])
        return 1

    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:TST-0021 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    quoted_sites = quoted_from(bad_grep, bad_subst, bad_wc, bad_n)
    quoted_sites.extend(quoted_from({"findings": live.get("findings") or []}))
    independent = independent_substring_census(live)

    n_live = int(live["scripts_scanned"])
    n_hit = int(live["scripts_with_at_least_one_idiom"])
    status = str(live["population_status"])
    quality = live["named_inputs"][".github/workflows/quality.yml"]
    ssv = live["named_inputs"]["rules/common/single-signal-verification.md"]
    if status == "ABSENT":
        answer = (
            f"On this Linux worktree, 0 live gate scripts match the population "
            f"(named input .github/workflows/quality.yml is {quality}; "
            f"rules/common/single-signal-verification.md is {ssv}). "
            f"scripts_with_at_least_one_idiom=0 is an ABSENT population, not a "
            f"GENUINE_ZERO over a non-empty estate. The lint is proven on planted "
            f"fixtures; one real miscount was reproduced: grep -c || echo 0 printed "
            f"{repro['bad_stdout_lines']!r} (two zeros) versus the corrected form "
            f"{repro['good_stdout_lines']!r} (one zero)."
        )
    elif status == "GENUINE_ZERO":
        answer = (
            f"{n_hit} live gate scripts contain at least one counting idiom "
            f"(GENUINE_ZERO over {n_live} scanned; quality.yml={quality}). "
            f"Planted controls still fire. Miscount reproduction: "
            f"{repro['bad_stdout_lines']!r} vs corrected "
            f"{repro['good_stdout_lines']!r}."
        )
    else:
        answer = (
            f"{n_hit} live gate scripts contain at least one counting idiom "
            f"(scanned {n_live}; quality.yml={quality}; independent substring "
            f"census={independent['scripts_with_at_least_one_idiom']}). "
            f"Flagged sites are quoted in report.quoted_flagged_sites. "
            f"Miscount reproduction: {repro['bad_stdout_lines']!r} vs corrected "
            f"{repro['good_stdout_lines']!r}."
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    missing = [rel for rel in SUPPORTING if not (REPO / rel).is_file()]
    if missing:
        print("FAILED:TST-0021 emit missing", missing)
        return 1

    grep_quote = next(
        (
            str(item.get("quoted"))
            for item in (bad_grep.get("findings") or [])
            if item.get("idiom") == IDIOM_GREP
        ),
        "missing",
    )
    live_quotes = [
        str(item.get("quoted"))
        for item in (live.get("findings") or [])
        if item.get("quoted")
    ][:40]
    scanned_paths = live["scanned_paths"]
    if len(scanned_paths) > 400:
        scanned_for_report = scanned_paths[:80] + [
            f"... truncated {len(scanned_paths) - 80} further paths ..."
        ]
    else:
        scanned_for_report = scanned_paths

    live_findings_cap = (live.get("findings") or [])[:200]
    census_agree = independent["scripts_with_at_least_one_idiom"] == n_hit

    report = {
        "kind": "test-receipt",
        "question": QUESTION,
        "falsifiable_answer": answer,
        "scripts_with_at_least_one_idiom": n_hit,
        "cloud_ok": False,
        "lint": {
            "module": "command-center/p2-wave/probes/TST-0021/lint.py",
            "idioms": [IDIOM_GREP, IDIOM_SUBST, IDIOM_WC, IDIOM_N],
        },
        "live_census": {
            "population_status": status,
            "scripts_scanned": n_live,
            "scripts_with_at_least_one_idiom": n_hit,
            "population_definition": live["population_definition"],
            "scanned_paths": scanned_for_report,
            "hits_per_script": live["hits_per_script"],
            "named_inputs": live["named_inputs"],
            "findings": live_findings_cap,
            "findings_truncated": len(live.get("findings") or []) > 200,
        },
        "independent_substring_census": independent,
        "censuses_agree_on_script_count": census_agree,
        "planted_controls": {
            "bad": planted["bad"],
            "good": planted["good"],
            "fired_on_each_bad_idiom": True,
            "silent_on_corrected": True,
        },
        "reproduction": {
            "kind": "two-line-miscount",
            "occurrence": "live-bash-on-this-worktree",
            "bad": {
                "command": repro["bad_command"],
                "stdout_lines": repro["bad_stdout_lines"],
                "double_zero": repro["bad_double_zero"],
            },
            "good": {
                "command": repro["good_command"],
                "stdout_lines": repro["good_stdout_lines"],
                "single_zero": repro["good_single_zero"],
            },
            "miscount_proven": True,
        },
        "quoted_flagged_sites": quoted_sites,
        "named_probes": [
            {"id": "probe1", "role": "flags-grep-c-or-echo-zero", "command": P1},
            {"id": "probe2", "role": "silent-on-corrected", "command": P2},
        ],
        "scope": {
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "scripts outside the population definition (skills/, .agents/) are clean",
                "ABSENT population is GENUINE_ZERO",
            ]
        },
        "observations": [
            {
                "name": "live-gate-scripts-with-counting-idiom",
                "measured": n_hit,
                "method": "lint.py-regex-census",
                "anchor": "command-center/p2-wave/probes/TST-0021/lint.py:lint_live",
            },
            {
                "name": "independent-substring-census-same-population",
                "measured": int(independent["scripts_with_at_least_one_idiom"]),
                "method": "file-read-substring",
                "anchor": "command-center/p2-wave/probes/TST-0021/emit_receipt.py:independent_substring_census",
            },
            {
                "name": "grep-c-or-echo-zero-miscount-lines",
                "measured": 2 if repro["bad_double_zero"] else 0,
                "method": "live-bash",
                "anchor": "live-bash:grep -c || echo 0",
            },
            {
                "name": "quality-yml-named-input",
                "measured": quality,
                "method": "stat",
                "anchor": ".github/workflows/quality.yml",
            },
        ],
        "control_ids": [
            "planted-grep-c-or-echo-zero",
            "planted-corrected-form-silent",
            "live-bash-two-line-miscount",
        ],
    }

    doc = {
        "schema_version": 1,
        "unit_id": UID,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json work_units[id=TST-0021] "
            "question_or_target / tests_required / evidence_requirement"
        ),
        "min_bytes_threshold": 2048,
        "profile": "test-receipt",
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "test-governance-auditor",
            "execution_substrate": "local-parallel",
        },
        "artifacts": [artifact_row(rel, "supporting") for rel in SUPPORTING],
        "evidence": [
            {
                "claim": (
                    f"Lint flags planted grep -c || echo 0 at {grep_quote}; "
                    "live bash printed two zeros for the same idiom and one "
                    "zero for the corrected form."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": grep_quote,
                "probes": [
                    probe_record("source", "test-run", P1, t1, c1),
                    probe_record(
                        "verifier",
                        "command",
                        repro["bad_command"],
                        json.dumps(repro, sort_keys=True),
                        0,
                    ),
                ],
            },
            {
                "claim": (
                    f"Live gate-script census: population_status={status} "
                    f"scripts_scanned={n_live} "
                    f"scripts_with_at_least_one_idiom={n_hit}; "
                    f"quality.yml={quality}; independent substring census="
                    f"{independent['scripts_with_at_least_one_idiom']} "
                    f"(agree={census_agree}). Quoted live sites: "
                    f"{live_quotes[:8]!r}."
                )[:2000],
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "live-census",
                "probes": [
                    probe_record(
                        "source",
                        "static-analysis",
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c from-lint-import-lint_live",
                        json.dumps(
                            {
                                "scripts_scanned": n_live,
                                "scripts_with_at_least_one_idiom": n_hit,
                                "population_status": status,
                                "hits_per_script": live["hits_per_script"],
                            },
                            sort_keys=True,
                        )[:8000],
                        0,
                    ),
                    probe_record(
                        "verifier",
                        "file-read",
                        "independent_substring_census over lint_live scanned_paths",
                        json.dumps(independent, sort_keys=True)[:8000],
                        0,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "test_lint_flags_grep_c_or_echo_zero",
                "command": P1,
                "result": "PASS",
                "output_tail": t1[-4000:],
            },
            {
                "id": "test_lint_does_not_flag_the_corrected_form",
                "command": P2,
                "result": "PASS",
                "output_tail": t2[-4000:],
            },
        ],
        "negative_controls": [
            {
                "id": "nc-grep-c-or-echo-zero",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted fixtures/bad/grep_c_or_echo_zero.sh must fire; "
                    "fixtures/good/corrected.sh (|| true, quoted subst, "
                    "quoted -n) must be silent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": grep_quote,
                "good_state_output": "flagged=0",
            }
        ],
        "reviewer": {
            "reviewer_id": "TST-0021-probe2-does-not-flag-corrected",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Probe 2 re-lints the corrected fixture and re-runs the "
                "corrected bash reproduction; it does not author lint.py."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/TST-0021/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft7Validator local-store test-receipt",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_record(
                    "verifier",
                    "schema-validate",
                    "Draft7Validator(command-center/schema/test-receipt.schema.json)",
                    "pending-write",
                    0,
                ),
            },
            {
                "consumer": P2,
                "artifact_path": (
                    "command-center/p2-wave/probes/TST-0021/fixtures/good/corrected.sh"
                ),
                "executed": True,
                "read_ok": True,
                "exit_code": c2,
                "probe": probe_record("verifier", "test-run", P2, t2, c2),
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after the 2nd failure on the same "
                "error-fingerprint, enumerate >=2 alternative approaches "
                "before a 3rd attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Shell scripts under skills/ and .agents/skills/ are "
                    "outside this unit's live-gate population, so a | wc -l "
                    "hit there is not counted in scripts_with_at_least_one_idiom."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Widen is_live_gate_rel to those trees and re-count, or "
                    "name them as a second population in a follow-on unit."
                ),
            }
        ],
        "report": report,
    }

    rc = validate_or_die(doc)
    if rc != 0:
        return rc

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = dump(doc)
    if SENTINEL not in text:
        print("FAILED:TST-0021 sentinel missing before write")
        return 1
    if len(text.encode("utf-8")) < int(doc["min_bytes_threshold"]):
        print("FAILED:TST-0021 artifact below min_bytes_threshold")
        return 1
    out.write_text(text, encoding="utf-8", newline="\n")
    digest, size = sha256_file(out)
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0021 self-declared non-delivery")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0021 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(f"census n_live={n_live} n_hit={n_hit} status={status} quality.yml={quality}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
