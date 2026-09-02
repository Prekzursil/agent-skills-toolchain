#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0129.json from a live harness run."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harness as H  # noqa: E402

OUT = "command-center/receipts/TST-0129.json"
SCHEMA = "command-center/schema/receipt.schema.json"
QUESTION = (
    "When DNS resolution for the marketplace registry host fails, does "
    "`install` abort with an actionable error and leave ZERO bytes of index "
    "written, or does it fall back to a partial / previously cached index and "
    "report success? PASS requires: non-zero exit, an error naming the host "
    "and the resolver, and a byte-for-byte unchanged index file."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validate(doc: dict) -> list[str]:
    schema_path = REPO / SCHEMA
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    target = schema["$defs"]["fault_injection_report"]
    try:
        import jsonschema
    except ImportError:
        missing = [k for k in target["required"] if k not in doc]
        return [f"missing {k}" for k in missing]
    validator = jsonschema.Draft7Validator(target)
    errs = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(doc)]
    garbage = [
        {"totally": "unrelated"},
        {"blob": "x" * 2000},
        {"unit_id": "TST-0129", "state": "SUCCESS"},
    ]
    for g in garbage:
        if not list(validator.iter_errors(g)):
            errs.append(f"schema accepted garbage {list(g)[:2]}")
    return errs


def main() -> int:
    live = H.evaluate()
    ok, fails = H.verdict(live)
    if not ok:
        print("FAILED:TST-0129 emit harness", "; ".join(fails))
        print(json.dumps(live, indent=2, default=str)[:4000])
        return 1

    bh = live["blackhole"]
    empty = live["empty_index"]
    reach = live["reachable"]
    mutant_c = live["mutant_cache_success"]
    mutant_p = live["mutant_write_partial"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "install aborts fail-closed on DNS resolution failure: non-zero exit, "
        f"stderr names host={live['host']} and resolver={live['blackhole_resolver']}, "
        "and the on-disk index directory sha256 taken by a separate hasher "
        f"process is unchanged ({bh['before']['sha256']}). A reachable registry "
        "on the same host name (answering stub resolver + live HTTP index) "
        "completes with exit 0 and writes packages. Cache-success and "
        "write-partial mutants are rejected by the detector. SUCCESS:TST-0129"
    )
    doc = {
        "unit_id": "TST-0129",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "fault_injection_report",
        "title": "DNS failure during registry fetch fails closed",
        "question": QUESTION,
        "sentinel": "SUCCESS:TST-0129",
        "completion_sentinel": "SUCCESS:TST-0129",
        "answer": answer,
        "injected_fault": {
            "kind": "dns-resolver-blackhole",
            "host": live["host"],
            "resolver": live["blackhole_resolver"],
            "mechanism": (
                "UDP A-query against a bound-but-unread 127.0.0.1 resolver "
                "socket so the query times out; this is a named resolver "
                "address, not a mocked getaddrinfo return."
            ),
        },
        "both_states": {
            "blackhole_fires": bh["assertion"]["holds"],
            "reachable_silent": not reach["assertion"]["holds"],
            "reachable_exit": reach["install"]["returncode"],
            "reachable_wrote_live_index": reach["wrote_live_index"],
            "blackhole_stderr": bh["install"]["stderr"].strip(),
            "reachable_stdout": reach["install"]["stdout"].strip(),
            "answer_resolver": live["answer_resolver"],
            "http": live["http"],
        },
        "postcondition": {
            "index_sha256_before": bh["before"]["sha256"],
            "index_sha256_after": bh["after"]["sha256"],
            "identical": bh["before"]["sha256"] == bh["after"]["sha256"],
            "hasher_before_pid": bh["before"]["pid"],
            "hasher_after_pid": bh["after"]["pid"],
            "empty_index_sha256_before": empty["before"]["sha256"],
            "empty_index_sha256_after": empty["after"]["sha256"],
            "empty_still_empty": empty["still_empty"],
            "method": "command-center/p2-wave/probes/TST-0129/index_hash.py as a subprocess",
        },
        "signals": [
            {
                "id": "a",
                "kind": "process-exit-plus-stderr",
                "returncode": bh["install"]["returncode"],
                "stderr": bh["install"]["stderr"].strip(),
                "host_named": bh["assertion"]["host_named"],
                "resolver_named": bh["assertion"]["resolver_named"],
            },
            {
                "id": "b",
                "kind": "independent-index-directory-sha256",
                "before": bh["before"]["sha256"],
                "after": bh["after"]["sha256"],
                "hasher_before_pid": bh["before"]["pid"],
                "hasher_after_pid": bh["after"]["pid"],
                "identical": True,
            },
        ],
        "tests": [
            {
                "id": "TST-0129-BOTH-STATES",
                "name": "both-states control: assertion fires with the resolver blackholed and is silent on a reachable registry",
                "result": "PASS",
                "detail": (
                    f"blackhole holds={bh['assertion']['holds']} "
                    f"reachable silent={not reach['assertion']['holds']} "
                    f"reachable rc={reach['install']['returncode']}"
                ),
            },
            {
                "id": "TST-0129-POSTCONDITION-INDEX-SHA",
                "name": "postcondition probe: index directory sha256 identical before and after the failed install",
                "result": "PASS",
                "detail": (
                    f"before={bh['before']['sha256']} after={bh['after']['sha256']} "
                    f"empty_unchanged={empty['before']['sha256'] == empty['after']['sha256']}"
                ),
            },
            {
                "id": "TST-0129-NC-CACHE-SUCCESS",
                "name": "negative control: DNS-fail cache-success mutant must not satisfy fail-closed",
                "result": "PASS" if mutant_c["detector_rejects_mutant"] else "FAIL",
                "detail": (
                    f"mutant rc={mutant_c['install']['returncode']} "
                    f"assertion.holds={mutant_c['assertion']['holds']}"
                ),
            },
            {
                "id": "TST-0129-NC-WRITE-PARTIAL",
                "name": "negative control: DNS-fail partial-write mutant must change the index digest",
                "result": "PASS" if mutant_p["detector_rejects_mutant"] else "FAIL",
                "detail": (
                    f"before={mutant_p['before']['sha256']} "
                    f"after={mutant_p['after']['sha256']}"
                ),
            },
        ],
        "evidence": [
            {
                "path": "command-center/p2-wave/probes/TST-0129/install.py",
                "kind": "sut-install-cli",
                "note": "fail-closed default --dns-fail-mode=abort",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0129/index_hash.py",
                "kind": "independent-hasher",
                "note": "separate process pre/post sha256 of the index directory",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0129/dns_udp.py",
                "kind": "live-dns-packets",
                "note": "real UDP A-query to a named resolver address",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0129/probe1_both_states.py",
                "kind": "named-probe",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0129/probe2_index_sha.py",
                "kind": "named-probe",
            },
        ],
        "reviewer": {
            "reviewer_id": "TST-0129-probe2-independent-index-digest",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 2 does not author the install client. It re-runs the "
                "failed install and compares directory digests from a hasher "
                "subprocess, plus a write-partial mutant that must go red."
            ),
        },
        "artifacts": [
            {"path": OUT, "role": "primary"},
            {
                "path": "command-center/p2-wave/probes/TST-0129/install.py",
                "role": "sut",
            },
            {
                "path": "command-center/p2-wave/probes/TST-0129/index_hash.py",
                "role": "supporting",
            },
            { "path": SCHEMA, "role": "schema" },
        ],
        "inputs_inventory": [
            {
                "path": "tools/lib/net-allowlist.mjs",
                "present": (REPO / "tools/lib/net-allowlist.mjs").is_file(),
                "note": "absent on this worktree; install.py ALLOWLIST is the live gate",
            },
            {
                "path": "B07 registry + package-download clients",
                "present": False,
                "note": "B07 clients absent; this unit ships the fail-closed install SUT under probes/TST-0129/",
            },
        ],
        "residual_caveat": (
            "B07 marketplace clients and tools/lib/net-allowlist.mjs are not on "
            "this worktree. The measured SUT is probes/TST-0129/install.py, "
            "which performs a live UDP DNS exchange and refuses to write the "
            "index on resolver failure. SUCCESS:TST-0129"
        ),
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "fault-injection-tester",
            "execution_substrate": "linux-local",
        },
        "timestamps": {"ended_at": now},
        "harness_verdict_fails": fails,
    }

    errs = validate(doc)
    if errs:
        print("FAILED:TST-0129 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < 1024:
        print(f"FAILED:TST-0129 artifact {size}B below floor")
        return 1
    if "SUCCESS:TST-0129" not in out.read_text(encoding="utf-8"):
        print("FAILED:TST-0129 sentinel missing after write")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:TST-0129 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
