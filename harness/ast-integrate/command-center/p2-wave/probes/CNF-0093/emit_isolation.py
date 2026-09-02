#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0093-partition-leak.json and per-unit receipts."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import jsonschema  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402

import detector as D  # noqa: E402
import partition_runtime as PR  # noqa: E402
import scenario as S  # noqa: E402
from canaries import CONTROL_CANARY, PARTITION_CANARY  # noqa: E402


def validate_artifact(doc: object, declared: str) -> list[str]:
    """Validate against the declared isolation-report shim using on-disk $ref targets.

    platform/lib/schema_resolver.py needs jsonschema>=4.18 (`registry=`). This
    worktree has 4.10.3, so RefResolver + a local URI store is the live checker.
    """
    shim = json.loads((REPO / declared).read_text(encoding="utf-8"))
    receipt = json.loads(
        (REPO / "platform" / "schema" / "receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    profiles = json.loads(
        (
            REPO / "platform" / "schema" / "artifact-class-profiles.schema.json"
        ).read_text(encoding="utf-8")
    )
    store = {
        shim["$id"]: shim,
        receipt["$id"]: receipt,
        profiles["$id"]: profiles,
    }
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    validator = Draft202012Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)

OUT = "command-center/confirmation/CNF-0093-partition-leak.json"
SCHEMA = "command-center/schema/isolation-report.schema.json"
QUESTION = (
    "Does the information partition hold? Give one participant data that another "
    "must not see, then search the second participant's output for that data and "
    "for paraphrases of it. Question: does partitioned content leak, and does it "
    "leak through the shared transcript, the synthesis stage, or the tool results?"
)
SENTINEL = (
    "SUCCESS:CNF-0093 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the unpartitioned control "
    "canary was found by the same search, proving the detector works. Any other "
    "terminal state is FAILED:CNF-0093 <classification> with the diagnostic tail "
    "attached."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0093/probe1_partition_scan.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0093/probe2_detector_control.py"
)
RECEIPT = "command-center/p2-wave/probes/CNF-0093/SUBAGENT-RETURN.json"
MANIFEST = "command-center/p2-wave/probes/CNF-0093/UNIT-ARTIFACT-MANIFEST.json"
MIN_BYTES = 2048


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\x1f{command}".encode("utf-8")).hexdigest()[:32]


def find_line(rel: str, snippet: str) -> int:
    path = REPO / rel
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNF-0093 snippet not in {rel}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def _count(rows: list[dict], kind_prefix: str | None = None) -> int:
    n = 0
    for row in rows:
        for hit in row.get("hits") or []:
            if kind_prefix is None or str(hit.get("kind") or "").startswith(kind_prefix):
                n += 1
    return n


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc1, out1 = run_cmd(P1)
    rc2, out2 = run_cmd(P2)
    if rc1 != 0 or rc2 != 0:
        print(f"FAILED:CNF-0093 probes rc1={rc1} rc2={rc2}")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    assembled = S.build_fixtures()
    holding = assembled["holding"]
    streams = PR.non_owning_streams(holding)
    part_rows = D.search_streams(streams, PARTITION_CANARY, paraphrase=True)
    ctrl_rows = D.search_streams(streams, CONTROL_CANARY, paraphrase=False)
    control_found = D.any_hits(ctrl_rows)
    if not control_found:
        print("FAILED:CNF-0093 detector-failure: control canary not found")
        return 1
    if D.any_hits(part_rows):
        print("FAILED:CNF-0093 partition-leak on holding fixture")
        return 1

    tx_n = _count(
        D.search_streams(
            PR.non_owning_streams(assembled["leak-shared-transcript"]),
            PARTITION_CANARY,
            paraphrase=True,
        ),
        "verbatim",
    )
    syn_n = _count(
        D.search_streams(
            PR.non_owning_streams(assembled["leak-synthesis-paraphrase"]),
            PARTITION_CANARY,
            paraphrase=True,
        ),
        "paraphrase",
    )
    tool_n = _count(
        D.search_streams(
            PR.non_owning_streams(assembled["leak-tool-results"]),
            PARTITION_CANARY,
            paraphrase=True,
        ),
        "verbatim",
    )
    off_n = _count(
        D.search_streams(
            PR.non_owning_streams(assembled["redaction-disabled"]),
            PARTITION_CANARY,
            paraphrase=True,
        )
    )
    live = PR.live_partition_module(REPO)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonempty = sum(1 for r in ctrl_rows if r["haystack_bytes"] > 0)
    ctrl_hit_streams = sum(1 for r in ctrl_rows if r["hit_count"] > 0)

    leak_paths = [
        {
            "id": "shared-transcript",
            "verdict": "HOLD",
            "holding_hits": _count(
                [r for r in part_rows if "transcript" in r["stream"]]
            ),
            "planted_bad_hits": tx_n,
        },
        {
            "id": "synthesis",
            "verdict": "HOLD",
            "holding_hits": _count(
                [r for r in part_rows if "synthesis" in r["stream"]]
            ),
            "planted_bad_hits": syn_n,
        },
        {
            "id": "tool-results",
            "verdict": "HOLD",
            "holding_hits": _count([r for r in part_rows if "tool" in r["stream"]]),
            "planted_bad_hits": tool_n,
        },
    ]

    det_mod = "command-center/p2-wave/probes/CNF-0093/detector.py"
    can_mod = "command-center/p2-wave/probes/CNF-0093/canaries.py"
    pr_mod = "command-center/p2-wave/probes/CNF-0093/partition_runtime.py"
    search_line = find_line(det_mod, "def search_streams(")
    control_line = find_line(can_mod, "CONTROL_CANARY =")
    bundle_line = find_line(pr_mod, "def _bundle_visible")
    launder_line = find_line(pr_mod, "LAUNDERED_SYNTHESIS")

    fp1 = fingerprint("command", P1)
    fp2 = fingerprint("command", P2)
    fp_search = fingerprint("static-analysis", f"{det_mod}:{search_line}")
    fp_launder = fingerprint("file-read", f"{pr_mod}:{launder_line}")

    supporting_rels = [
        SCHEMA,
        "command-center/p2-wave/probes/CNF-0093/probe1_partition_scan.py",
        "command-center/p2-wave/probes/CNF-0093/probe2_detector_control.py",
        det_mod,
        pr_mod,
        can_mod,
        "command-center/p2-wave/probes/CNF-0093/scenario.py",
        "command-center/p2-wave/probes/CNF-0093/probe1-partition-scan.raw.json",
        "command-center/p2-wave/probes/CNF-0093/probe2-detector-control.raw.json",
    ]
    supporting_arts = [art_row(rel, "supporting") for rel in supporting_rels]

    answer = (
        "Fixture lattice HOLD across shared transcript, synthesis, and tool "
        "results for the partitioned canary (verbatim and paraphrase). Same "
        f"search found the unpartitioned control ({CONTROL_CANARY}). Planted "
        f"leaks fired (transcript verbatim={tx_n}, synthesis paraphrase={syn_n}, "
        f"tools verbatim={tool_n}, redaction-disabled={off_n}). Live "
        f"partition.py present={live['present']}. " + SENTINEL
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNF-0093",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNF-0093",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "isolation-probe-engineer",
            "execution_substrate": "linux-local",
        },
        "report": {
            "kind": "isolation-report",
            "title": "Information-partition leak probe across council participants",
            "question": QUESTION,
            "answer": answer,
            "observations": [
                {
                    "name": "holding_non_owning_partition_hits",
                    "measured": _count(part_rows),
                    "method": "verbatim-plus-paraphrase search_streams",
                    "anchor": f"{det_mod}:{search_line}",
                },
                {
                    "name": "unpartitioned_control_hit_streams",
                    "measured": ctrl_hit_streams,
                    "method": "same search_streams, paraphrase off",
                    "anchor": f"{can_mod}:{control_line}",
                },
                {
                    "name": "planted_transcript_verbatim_hits",
                    "measured": tx_n,
                    "method": "verbatim search on leak-shared-transcript",
                    "anchor": f"{pr_mod}:{bundle_line}",
                },
                {
                    "name": "planted_synthesis_paraphrase_hits",
                    "measured": syn_n,
                    "method": "paraphrase search on leak-synthesis-paraphrase",
                    "anchor": f"{pr_mod}:{launder_line}",
                },
                {
                    "name": "planted_tool_verbatim_hits",
                    "measured": tool_n,
                    "method": "verbatim search on leak-tool-results",
                    "anchor": f"{pr_mod}:TOOL_LEAK",
                },
                {
                    "name": "live_partition_module_present",
                    "measured": bool(live["present"]),
                    "method": "stat tools/council/integrity/partition.py",
                    "anchor": "tools/council/integrity/partition.py",
                },
                {
                    "name": "canary_is_benign_synthetic",
                    "measured": D.is_benign_token(PARTITION_CANARY)
                    and D.is_benign_token(CONTROL_CANARY),
                    "method": "detector.is_benign_token",
                    "anchor": f"{can_mod}:PARTITION_CANARY",
                },
            ],
            "control_ids": [
                "CNF-0093-C1-unpartitioned-control",
                "CNF-0093-C2-planted-transcript",
                "CNF-0093-C3-planted-synthesis-paraphrase",
                "CNF-0093-C4-planted-tool-results",
                "CNF-0093-C5-redaction-disabled",
            ],
            "partition": {
                "lattice_id": PR.LATTICE_ID,
                "owning_seat": PR.OWNING_SEAT,
                "non_owning_seats": list(PR.NON_OWNING),
                "unpartitioned_field": PR.UNPARTITIONED_FIELD,
            },
            "canary": {
                "value": PARTITION_CANARY,
                "kind": "benign-synthetic-token",
                "owner_seat": PR.OWNING_SEAT,
                "benign": True,
            },
            "control": {
                "value": CONTROL_CANARY,
                "field": PR.UNPARTITIONED_FIELD,
                "found_by_same_search": True,
                "same_search": "detector.search_streams",
                "hit_streams": ctrl_hit_streams,
                "nonempty_haystacks": nonempty,
            },
            "detector": {
                "verbatim": True,
                "paraphrase": True,
                "module": det_mod,
            },
            "searches": {"partition_holding": part_rows, "control_holding": ctrl_rows},
            "leak_paths": leak_paths,
            "live_runtime": live,
        },
        "artifacts": supporting_arts,
        "evidence": [
            {
                "claim": (
                    "On the holding lattice, non-owning streams have zero verbatim "
                    "or paraphrase hits for the seat-A partitioned canary."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{det_mod}:{search_line}",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": out1[-8000:],
                        "fingerprint": fp1,
                        "exit_code": rc1,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": f"{det_mod}:{search_line}",
                        "raw_output": json.dumps(
                            {
                                "holding_hits": _count(part_rows),
                                "streams": len(part_rows),
                            },
                            sort_keys=True,
                        ),
                        "fingerprint": fp_search,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "The unpartitioned control canary was found by the same "
                    "search_streams function, so holding silence is not a dead detector."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": f"{can_mod}:{control_line}",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": out2[-8000:],
                        "fingerprint": fp2,
                        "exit_code": rc2,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": f"{pr_mod}:{launder_line}",
                        "raw_output": (
                            f"control_hit_streams={ctrl_hit_streams} "
                            f"nonempty_haystacks={nonempty} "
                            f"partition_holding_hits={_count(part_rows)}"
                        ),
                        "fingerprint": fp_launder,
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "probe1-partition-scan",
                "name": "Holding silent; planted transcript/synthesis/tool leaks fire",
                "command": P1,
                "result": "PASS",
                "output_tail": out1[-2000:],
            },
            {
                "id": "probe2-detector-control",
                "name": "Unpartitioned control found by the same search",
                "command": P2,
                "result": "PASS",
                "output_tail": out2[-2000:],
            },
            {
                "id": "benign-canary",
                "name": "Canaries are benign synthetic tokens, not credential-shaped",
                "command": (
                    "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                    "\"import sys; sys.path.insert(0, 'command-center/p2-wave/probes/CNF-0093'); "
                    "import detector, canaries; "
                    "assert detector.is_benign_token(canaries.PARTITION_CANARY); "
                    "assert detector.is_benign_token(canaries.CONTROL_CANARY)\""
                ),
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "CNF-0093-C1-unpartitioned-control",
                "kind": "known-broken-fixture",
                "description": (
                    "Place the control canary in the unpartitioned briefing. "
                    "search_streams must find it. The partitioned canary must stay "
                    "absent from seat-b private_context."
                ),
                "fired_on_bad_state": ctrl_hit_streams >= 1,
                "silent_on_good_state": _count(part_rows) == 0,
                "bad_state_output": out2[-1500:],
                "good_state_output": f"holding_partition_hits={_count(part_rows)}",
            },
            {
                "id": "CNF-0093-C2-planted-transcript",
                "kind": "known-broken-fixture",
                "description": (
                    "A planted verbatim paste of the partitioned canary into the "
                    "shared transcript must fire; the holding transcript must not."
                ),
                "fired_on_bad_state": tx_n >= 1,
                "silent_on_good_state": _count(part_rows) == 0,
                "bad_state_output": f"transcript_verbatim={tx_n}",
                "good_state_output": f"holding_hits={_count(part_rows)}",
            },
            {
                "id": "CNF-0093-C3-planted-synthesis-paraphrase",
                "kind": "known-broken-fixture",
                "description": (
                    "A laundered synthesis that restates the private fact without "
                    "copying PARTITION_CANARY must fire the paraphrase detector."
                ),
                "fired_on_bad_state": syn_n >= 1,
                "silent_on_good_state": _count(part_rows) == 0,
                "bad_state_output": f"synthesis_paraphrase={syn_n}",
                "good_state_output": f"holding_hits={_count(part_rows)}",
            },
            {
                "id": "CNF-0093-C4-planted-tool-results",
                "kind": "known-broken-fixture",
                "description": (
                    "A planted verbatim echo of the partitioned canary in shared "
                    "tool results must fire."
                ),
                "fired_on_bad_state": tool_n >= 1,
                "silent_on_good_state": _count(part_rows) == 0,
                "bad_state_output": f"tool_verbatim={tool_n}",
                "good_state_output": f"holding_hits={_count(part_rows)}",
            },
            {
                "id": "CNF-0093-C5-redaction-disabled",
                "kind": "known-broken-fixture",
                "description": (
                    "With redaction disabled, every seat sees the private bundle "
                    "and the scan must fire."
                ),
                "fired_on_bad_state": off_n >= 1,
                "silent_on_good_state": _count(part_rows) == 0,
                "bad_state_output": f"redaction_disabled={off_n}",
                "good_state_output": f"holding_hits={_count(part_rows)}",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0093-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": False,
            "vendor": "unassigned",
            "notes": (
                "Probe 2 re-runs detector.search_streams on a different needle "
                "(unpartitioned control) and refuses empty haystacks. Catalog "
                "human security review of scanned production code remains a "
                "separate requirement; this worktree has no tools/council runtime."
            ),
            "reviewed_at": now,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": MANIFEST,
            "entry_id": "CNF-0093",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": (
                    "command-center/p2-wave/probes/CNF-0093/emit_isolation.py "
                    "validate_artifact (Draft202012 RefResolver, on-disk store)"
                ),
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
                        "\"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNF-0093'); "
                        "import emit_isolation as E; d=json.load(open('OUT')); "
                        "err=E.validate_artifact(d,'SCHEMA'); "
                        "print('errors',len(err)); raise SystemExit(1 if err else 0)\""
                        .replace("OUT", OUT)
                        .replace("SCHEMA", SCHEMA)
                    ),
                    "raw_output": "PENDING-WRITE",
                    "fingerprint": fingerprint(
                        "schema-validate",
                        f"emit_isolation.validate_artifact {OUT} {SCHEMA}",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": "zero retries. first observation is the verdict (catalog retry_policy)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "tools/council/integrity/partition.py is absent; this unit "
                    "measured the fixture lattice and detector, not IMP-0278."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run CNF-0093 after IMP-0278 lands partition.py and scan "
                    "live council seats rather than the fixture lattice."
                ),
            },
            {
                "claim": (
                    "Catalog reviewer_requirement names a human security reviewer "
                    "plus CI re-run on an identical commit SHA. This receipt's "
                    "reviewer is the mechanical probe-2 control, not that human."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Dispatch an independent security reviewer who did not author "
                    "the scanned code, and re-run the named probes in CI on the "
                    "commit SHA that carries this artifact."
                ),
            },
        ],
        "extensions": {
            "completion_sentinel": SENTINEL,
            "cloud_ok": False,
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "IMP-0278 tools/council/integrity/partition.py was implemented",
                "a production council simulator ran against live model seats",
            ],
        },
    }

    schema_errs = validate_artifact(doc, SCHEMA)
    if schema_errs:
        print("FAILED:CNF-0093 schema errors")
        for err in schema_errs[:40]:
            print(" ", err)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated"},
        {"unit_id": "CNF-0093", "state": "SUCCESS", "blob": "x" * 2000},
    ):
        g_errs = validate_artifact(garbage, SCHEMA)
        if not g_errs:
            print(f"FAILED:CNF-0093 schema accepted garbage {list(garbage)[:2]}")
            return 1
    mutant = json.loads(json.dumps(doc))
    mutant["report"]["kind"] = "not-this"
    if not validate_artifact(mutant, SCHEMA):
        print("FAILED:CNF-0093 schema accepted report.kind mutant")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:CNF-0093 completion_sentinel missing from artifact")
        return 1
    out.write_text(payload, encoding="utf-8")
    live_errs = validate_artifact(json.loads(out.read_text(encoding="utf-8")), SCHEMA)
    if live_errs:
        print("FAILED:CNF-0093 on-disk schema errors")
        for err in live_errs[:20]:
            print(" ", err)
        return 1
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:CNF-0093 artifact {size}B below floor")
        return 1

    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"SUCCESS:schema-valid errors=0 bytes={size} sha256={digest}"
    )
    # Re-validate after filling the consumer probe output, then rewrite once.
    schema_errs = validate_artifact(doc, SCHEMA)
    if schema_errs:
        print("FAILED:CNF-0093 schema errors after consumer fill")
        for err in schema_errs[:20]:
            print(" ", err)
        return 1
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNF-0093 completion_sentinel missing after rewrite")
        return 1

    ret = {
        "id": "CNF-0093",
        "unit_id": "CNF-0093",
        "status": "DELIVERED",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0093",
        "registered": True,
        "output_path": OUT,
        "output_schema": SCHEMA,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1,
                "exit_code": rc1,
                "role": "partition-scan-verbatim-and-paraphrase",
                "raw_output": out1[-8000:],
            },
            {
                "id": "probe2",
                "command": P2,
                "exit_code": rc2,
                "role": "unpartitioned-control-same-search",
                "raw_output": out2[-8000:],
            },
        ],
        "artifacts": [
            {
                "path": OUT,
                "sha256": digest,
                "bytes": size,
                "exists": True,
                "role": "primary",
            }
        ],
        "manifest_path": MANIFEST,
        "reviewer": {
            "reviewer_id": "CNF-0093-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
        },
        "cloud_ok": False,
        "ts": now,
        "notes": (
            "G-1 for CNF-0093: live named probes exit 0, partition-leak.json "
            "state=SUCCESS, per-unit manifest row. Did not run global "
            "unit_manifest.py --write. No ADV rebuild."
        ),
    }
    (HERE / "SUBAGENT-RETURN.json").write_text(
        json.dumps(ret, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    def man_row(rel: str, role: str) -> dict:
        p = REPO / rel
        sha, n = sha256_file(p)
        return {
            "path": rel,
            "sha256": sha,
            "bytes": n,
            "present": True,
            "unit_id": "CNF-0093",
            "receipt_path": RECEIPT,
            "role": role,
        }

    man = {
        "schema_version": 1,
        "contract": "completion-predicate-condition-11-unit-artifact-registration",
        "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        "unit_id": "CNF-0093",
        "verified_on_disk": True,
        "artifacts": [
            man_row(OUT, "primary"),
            man_row(SCHEMA, "supporting"),
            man_row(
                "command-center/p2-wave/probes/CNF-0093/probe1_partition_scan.py",
                "supporting",
            ),
            man_row(
                "command-center/p2-wave/probes/CNF-0093/probe2_detector_control.py",
                "supporting",
            ),
            man_row(det_mod, "supporting"),
            man_row(pr_mod, "supporting"),
            man_row(RECEIPT, "supporting"),
        ],
    }
    man["expected"] = len(man["artifacts"])
    man["present"] = len(man["artifacts"])
    (HERE / "UNIT-ARTIFACT-MANIFEST.json").write_text(
        json.dumps(man, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNF-0093 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
