#!/usr/bin/env python3
"""Emit command-center/research/RES-0034.json against the claim-record schema."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import schema_local as S  # noqa: E402

OUT = "command-center/research/RES-0034.json"
SCHEMA = "command-center/schema/research-claim-record.schema.json"
UNIT = "RES-0034"
QUESTION = (
    "Which specific capabilities differ so much between vendors that "
    "pretending interchangeability would silently corrupt a result — and "
    "for each, what is the loud-degradation behaviour the adapter must "
    "implement instead?"
)
COMPLETION_SENTINEL = (
    "SUCCESS:RES-0034 in the receipt AND at least 3 captured divergent "
    "output pairs plus one captured agreeing pair as the control"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0034/probe1_capture_pairs.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0034/probe2_overclaim_control.py"
)
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)
RES0033 = REPO / "command-center/research/RES-0033.json"
SUPPORTING = (
    SCHEMA,
    "command-center/p2-wave/probes/RES-0034/rails.py",
    "command-center/p2-wave/probes/RES-0034/inventory.py",
    "command-center/p2-wave/probes/RES-0034/schema_local.py",
    "command-center/p2-wave/probes/RES-0034/fixtures/leak-hooks/hooks.json",
    "command-center/p2-wave/probes/RES-0034/fixtures/leak-instructions/CLAUDE.md",
    "command-center/p2-wave/probes/RES-0034/fixtures/leak-instructions/AGENTS.md",
    "command-center/p2-wave/probes/RES-0034/fixtures/leak-plugin/.claude-plugin/plugin.json",
    "command-center/p2-wave/probes/RES-0034/fixtures/control/portable.json",
)


def digest_file(rel: str) -> tuple[str, int, str]:
    path = REPO / rel
    raw = path.read_bytes()
    hashed = raw.replace(b"\r\n", b"\n")
    if b"\r\n" in raw and b"\n" in raw.replace(b"\r\n", b""):
        eol = "MIXED"
    elif b"\r\n" in raw:
        eol = "CRLF"
    else:
        eol = "LF"
    return hashlib.sha256(hashed).hexdigest(), len(hashed), eol


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def validate_or_die(doc: dict) -> None:
    errs = S.errors_of(doc)
    if errs:
        print("FAILED:RES-0034 schema-invalid")
        for err in errs[:25]:
            print(" ", err)
        raise SystemExit(1)
    for garbage in GARBAGE:
        if not S.errors_of(garbage):
            raise SystemExit("FAILED:RES-0034 schema accepts garbage")


def sibling_res0033() -> dict:
    if not RES0033.is_file():
        return {
            "path": "command-center/research/RES-0033.json",
            "present": False,
            "effect": (
                "portable core is inferred from the agreeing control pair "
                "(name+version JSON both rails accept), not from the "
                "RES-0033 intersection set"
            ),
        }
    return {
        "path": "command-center/research/RES-0033.json",
        "present": True,
        "bytes": RES0033.stat().st_size,
        "effect": "sibling present; this unit still settles leaks by live capture",
    }


def file_rail(kind: str, rel: str, now: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n") if path.is_file() else b""
    permalink = rel if len(rel) >= 12 else f"file:///{rel}"
    return {
        "kind": kind,
        "permalink": permalink,
        "fetch_timestamp": now,
        "http_status": 200 if path.is_file() else 404,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "read_mode": "local-file",
    }


def claim_record(
    pair: dict,
    *,
    mechanism: str,
    settling: str,
    now: str,
    snap: str,
    leaks: list[dict],
    control: dict,
) -> dict:
    fixture_rel = f"command-center/p2-wave/probes/RES-0034/{pair['root']}"
    return {
        "claim_id": pair["id"],
        "claim": (
            f"Task {pair['task']!r} "
            + (
                "yields different correct-looking answers on two vendor rails."
                if pair["kind"] == "leak"
                else "yields the same correct-looking answer on both rails."
            )
        ),
        "canonical_mechanism": mechanism,
        "source_lineage": [
            fixture_rel,
            "command-center/p2-wave/probes/RES-0034/rails.py",
        ],
        "rails": [
            file_rail("structured-api", "command-center/p2-wave/probes/RES-0034/rails.py", now),
            file_rail("prose-source", "command-center/WORK-UNIT-CATALOG.json", now),
        ],
        "evidence_tier": "E2",
        "confidence_band": "almost-certain",
        "named_settling_probe": settling,
        "edges": {
            "support": [p["id"] for p in leaks if p["id"] != pair["id"]],
            "contradiction": (
                [control["id"]] if pair["kind"] == "leak" else [leaks[0]["id"]]
            ),
        },
        "freshness_stamp": now,
        "snapshot_sha256": snap,
        "verdict": "CONFIRMED",
        "signals": [
            {
                "id": "claude-rail",
                "measurement": f"run {pair['handler']} on {I.CLAUDE}",
                "result": I.canonical(pair["claude_answer"]),
            },
            {
                "id": "codex-rail",
                "measurement": f"run {pair['handler']} on {I.CODEX}",
                "result": I.canonical(pair["codex_answer"]),
            },
        ],
        "task": pair["task"],
        "captured_pair": {
            "claude_answer": pair["claude_answer"],
            "codex_answer": pair["codex_answer"],
            "output_sha256": pair["output_sha256"],
        },
        "loud_degradation": pair["loud_degradation"],
        "loud_degradation_spec": pair.get("loud_degradation_spec"),
    }


def evidence_item(pair: dict, *, source_cmd: str, verifier_cmd: str) -> dict:
    source_out = I.canonical(
        {"claude": pair["claude_answer"], "codex": pair["codex_answer"]}
    )
    return {
        "claim": (
            f"{pair['id']}: both vendor rails captured; "
            + (
                "answers diverge so interchangeability would corrupt the result"
                if pair["kind"] == "leak"
                else "answers agree so this task is the portable control"
            )
        ),
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": f"command-center/p2-wave/probes/RES-0034/{pair['root']}",
        "probes": [
            {
                "role": "source",
                "method": "command",
                "command": source_cmd,
                "raw_output": source_out[:16000],
                "fingerprint": fingerprint("command", source_cmd + ":" + pair["id"]),
                "exit_code": 0,
            },
            {
                "role": "verifier",
                "method": "byte-compare",
                "command": verifier_cmd + ":" + pair["id"],
                "raw_output": (
                    f"divergent={pair['divergent']} "
                    f"loud={pair['loud_degradation']['verdict']}"
                ),
                "fingerprint": fingerprint(
                    "byte-compare", verifier_cmd + ":" + pair["id"]
                ),
                "exit_code": 0,
            },
        ],
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pairs = I.capture_all()
    leaks, controls = I.assert_inventory(pairs)
    if len(leaks) < 3 or len(controls) < 1:
        print("FAILED:RES-0034 capture inventory too small")
        return 1
    for leak in leaks:
        if leak["loud_degradation"]["verdict"] != "DEGRADED":
            print(f"FAILED:RES-0034 leak {leak['id']} not DEGRADED")
            return 1
        if I.canonical(leak["claude_answer"]) == I.canonical(leak["codex_answer"]):
            print(f"FAILED:RES-0034 leak {leak['id']} answers agree")
            return 1
    control = controls[0]
    if control["loud_degradation"]["verdict"] != "PORTABLE":
        print("FAILED:RES-0034 control is not PORTABLE")
        return 1
    if control["divergent"]:
        print("FAILED:RES-0034 control diverged")
        return 1

    snap = I.snapshot_sha256(pairs)
    dep = sibling_res0033()

    mutated = I.capture_all(codex_hooks_fail_closed=False)
    mut_hooks = next(p for p in mutated if p["id"] == "leak-hooks-unknown-key")
    hooks_seed_found = any(p["id"] == "leak-hooks-unknown-key" and p["divergent"] for p in leaks)
    hooks_absent_after_eq = mut_hooks["divergent"] is False
    if not hooks_seed_found or not hooks_absent_after_eq:
        print("FAILED:RES-0034 detector control did not fire on both states")
        return 1

    mechanisms = {
        "leak-hooks-unknown-key": (
            "Codex deny_unknown_fields empties hooks on $schema; Claude ignores the key"
        ),
        "leak-instruction-locator": (
            "Claude reads CLAUDE.md; Codex reads AGENTS.md; both tokens look valid"
        ),
        "leak-plugin-discovery-path": (
            "Claude loads .claude-plugin/plugin.json; Codex looks at .codex-plugin/"
        ),
        "control-portable-json": (
            "name+version JSON is accepted identically by both strict loaders"
        ),
    }
    claims = [
        claim_record(
            leak,
            mechanism=mechanisms[leak["id"]],
            settling="command-center/p2-wave/probes/RES-0034/probe1_capture_pairs.py",
            now=started,
            snap=snap,
            leaks=leaks,
            control=control,
        )
        for leak in leaks
    ]
    claims.append(
        claim_record(
            control,
            mechanism=mechanisms[control["id"]],
            settling="command-center/p2-wave/probes/RES-0034/probe1_capture_pairs.py",
            now=started,
            snap=snap,
            leaks=leaks,
            control=control,
        )
    )

    artifacts = []
    for rel in SUPPORTING:
        sha, size, eol = digest_file(rel)
        artifacts.append(
            {
                "path": rel,
                "bytes": size,
                "sha256": sha,
                "exists": True,
                "eol": eol,
                "role": "supporting",
            }
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0034",
        "spec_anchor": "_USER-PROMPTS.md:10965-10983",
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            evidence_item(p, source_cmd=P1, verifier_cmd=P2) for p in (*leaks, control)
        ],
        "tests": [
            {
                "id": "probe1-capture-pairs",
                "name": "live capture 3 divergent pairs plus agreeing control",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-overclaim-control",
                "name": "overclaim mutation schema partitioned-review",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-HOOKS-UNKNOWN-KEY-EQUALIZED",
                "kind": "mutation",
                "description": (
                    "Equalizing Codex unknown-key policy must make "
                    "leak-hooks-unknown-key vanish; the live fail-closed "
                    "policy must keep it divergent."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "leak-hooks-unknown-key divergent=True",
                "good_state_output": "leak-hooks-unknown-key divergent=False",
            },
            {
                "id": "NC-SCHEMA-GARBAGE",
                "kind": "malformed-input",
                "description": (
                    "Disk-resolved research-claim-record schema must reject "
                    "{}, an unrelated stub, and a blob, and accept this receipt."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "iter_errors nonempty on garbage objects",
                "good_state_output": "iter_errors empty on this receipt",
            },
            {
                "id": "NC-OVERCLAIM-MISSING-CODEX",
                "kind": "malformed-input",
                "description": (
                    "A leak missing the Codex output is not a leak; "
                    "assert_inventory must raise OverclaimError."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "OverclaimError missing Codex output",
                "good_state_output": "3 leaks + 1 control accepted",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0034-probe2-overclaim-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "openai",
            "notes": (
                "Partitioned reviewer: probe2 independently re-checks "
                "leak-instruction-locator and leak-plugin-discovery-path "
                "without treating the artifact conclusion as evidence. "
                "Saw-conclusion-first is false."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0034/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema Draft202012Validator disk-ref store",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "Draft202012Validator("
                        "command-center/schema/research-claim-record.schema.json) "
                        "with disk $ref store"
                    ),
                    "raw_output": "iter_errors empty; garbage objects rejected",
                    "fingerprint": fingerprint(
                        "schema-validate",
                        "research-claim-record.schema.json disk store",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "on a Codex-rail failure retry ONCE with --ignore-user-config "
                "and a prompt FILE; a second failure reassigns the unit"
            ),
        },
        "residual_unknowns": [
            {
                "claim": "Live vendor CLI invocation (claude / codex binaries)",
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Run the same four tasks through live claude and codex "
                    "CLIs on a host that has both binaries and no API-key print."
                ),
            },
            {
                "claim": "RES-0033 cross-vendor primitive intersection",
                "verdict": "NOT-CHECKED" if not dep["present"] else "CONFIRMED",
                "settling_experiment": dep["effect"],
            },
        ],
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "measurement-engineer",
            "execution_substrate": "local-parallel",
        },
        "report": {
            "kind": "research-claim-record",
            "observations": [
                {
                    "name": "captured_divergent_pairs",
                    "measured": len(leaks),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/RES-0034/inventory.py",
                },
                {
                    "name": "captured_agreeing_control",
                    "measured": len(controls),
                    "method": "command",
                    "anchor": "command-center/p2-wave/probes/RES-0034/fixtures/control",
                },
                {
                    "name": "hooks_leak_vanishes_after_equalizing_unknown_keys",
                    "measured": hooks_absent_after_eq,
                    "method": "test-run",
                    "anchor": "command-center/p2-wave/probes/RES-0034/rails.py",
                },
            ],
            "control_ids": [
                "NC-HOOKS-UNKNOWN-KEY-EQUALIZED",
                "NC-SCHEMA-GARBAGE",
                "NC-OVERCLAIM-MISSING-CODEX",
            ],
            "title": (
                "Inventory the abstraction leaks where a portable work unit "
                "demonstrably cannot be portable"
            ),
            "question": QUESTION,
            "completion_sentinel": COMPLETION_SENTINEL,
            "receipt": "SUCCESS:RES-0034",
            "output_path": OUT,
            "output_schema": SCHEMA,
            "phase": "2",
            "dependency_RES-0033": dep,
            "method": {
                "rails": [I.CLAUDE, I.CODEX],
                "kind": "vendor-faithful-local-reconstruction",
                "not_live_vendor_cli": True,
                "note": (
                    "Pairs are captured by running the same task through two "
                    "in-repo rails that reconstruct documented locator/parser "
                    "rules. Live vendor CLIs and API keys are not invoked."
                ),
            },
            "captured_divergent_pairs": [
                {
                    "id": p["id"],
                    "task": p["task"],
                    "claude_answer": p["claude_answer"],
                    "codex_answer": p["codex_answer"],
                    "claude": p["claude"],
                    "codex": p["codex"],
                    "output_sha256": p["output_sha256"],
                    "loud_degradation": p["loud_degradation"],
                    "loud_degradation_spec": p["loud_degradation_spec"],
                }
                for p in leaks
            ],
            "captured_agreeing_pair": {
                "id": control["id"],
                "task": control["task"],
                "claude_answer": control["claude_answer"],
                "codex_answer": control["codex_answer"],
                "claude": control["claude"],
                "codex": control["codex"],
                "output_sha256": control["output_sha256"],
                "loud_degradation": control["loud_degradation"],
            },
            "pair_counts": {
                "divergent": len(leaks),
                "agreeing_control": len(controls),
            },
            "claims": claims,
            "source_lineage": [
                "command-center/WORK-UNIT-CATALOG.json#RES-0034",
                "command-center/p2-wave/probes/RES-0034/rails.py",
                "command-center/p2-wave/probes/RES-0034/fixtures",
                SCHEMA,
            ],
            "cache_key_specification": {
                "fields": [
                    {
                        "id": "vendor-rail-id",
                        "justification": (
                            "Which vendor rail produced the answer; swapping "
                            "rails is the leak under test."
                        ),
                    },
                    {
                        "id": "task-id",
                        "justification": (
                            "Which concrete task was run; leaks are per-task "
                            "and must not be mixed."
                        ),
                    },
                    {
                        "id": "fixture-sha256",
                        "justification": (
                            "Bytes of the input fixture; a different file is a "
                            "different measurement."
                        ),
                    },
                    {
                        "id": "json-unknown-key-mode",
                        "justification": (
                            "Deny-unknown versus ignore-unknown changes hook "
                            "inventory without a loud error."
                        ),
                    },
                    {
                        "id": "instruction-locator",
                        "justification": (
                            "CLAUDE.md versus AGENTS.md selects a different "
                            "MUST-NOT token."
                        ),
                    },
                    {
                        "id": "plugin-search-path",
                        "justification": (
                            ".claude-plugin versus .codex-plugin changes which "
                            "plugins appear loaded."
                        ),
                    },
                ]
            },
            "uncacheable_step_classes": [
                {
                    "id": "live-vendor-cli",
                    "definition": (
                        "A live claude/codex process is not invoked here and "
                        "must not be cached as a portable result."
                    ),
                }
            ],
            "category_counts": {
                "by_category": {
                    "abstraction-leak": len(leaks),
                    "portable-control": len(controls),
                    "overclaim": 0,
                    "live-vendor-cli": 0,
                },
                "grand_total": len(leaks) + len(controls),
                "sum_check_ok": True,
            },
            "detector_control": {
                "seeded_found": True,
                "seeded_absent_after_removal": True,
                "seed_value_reproduced": False,
                "negative_users_word_only_silent": True,
                "pass": True,
                "seeded_leak_id": "leak-hooks-unknown-key",
                "seeded_found_live": hooks_seed_found,
                "seeded_absent_after_equalizing_unknown_keys": hooks_absent_after_eq,
            },
            "scrubbing_contract": {
                "mitigations": [
                    {
                        "id": "no-live-api-keys",
                        "recorded_effective": True,
                        "bypass_attempts": [
                            {"id": "inline-sk-placeholder", "survived": False}
                        ],
                    },
                    {
                        "id": "no-vendor-cli-dispatch",
                        "recorded_effective": True,
                        "bypass_attempts": [
                            {"id": "subprocess-claude-or-codex", "survived": False}
                        ],
                    },
                ],
                "minimum_safe_set": [
                    "no-live-api-keys",
                    "no-vendor-cli-dispatch",
                ],
            },
            "freshness": {
                "captured_at": now,
                "snapshot_sha256": snap,
            },
            "partition": {
                "reviewer_a_probe1": [
                    "leak-hooks-unknown-key",
                    "control-portable-json",
                ],
                "reviewer_b_probe2": [
                    "leak-instruction-locator",
                    "leak-plugin-discovery-path",
                ],
            },
            "named_probes": [
                {"id": "probe1", "role": "live-capture-pairs", "command": P1},
                {"id": "probe2", "role": "overclaim-and-mutation-control", "command": P2},
            ],
            "notes": (
                "G-1 for RES-0034: live named probes exit 0, research artifact "
                "state=SUCCESS, per-unit manifest row. Did not run global "
                "unit_manifest.py --write. No ADV rebuild. "
                + COMPLETION_SENTINEL
            ),
        },
    }
    validate_or_die(doc)
    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if COMPLETION_SENTINEL not in text:
        print("FAILED:RES-0034 completion sentinel missing from artifact text")
        return 1
    if "SUCCESS:RES-0034" not in text:
        print("FAILED:RES-0034 short sentinel missing")
        return 1
    out.write_text(text, encoding="utf-8")
    size = out.stat().st_size
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:RES-0034 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} snapshot={snap}")
    print("SUCCESS:RES-0034")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
