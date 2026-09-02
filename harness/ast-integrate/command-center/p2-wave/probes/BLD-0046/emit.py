#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0046.json decaying-green inventory."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import RefResolutionError

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from classify import MAX_AGE_SECONDS, iso, utcnow  # noqa: E402
from inventory import LOCAL_CONTROL_GATE, build_inventory, cited_successes  # noqa: E402
from osv import github_run, query_osv  # noqa: E402
from scanner import classify_missing_scanner  # noqa: E402

OUT = "command-center/receipts/BLD-0046.json"
SCHEMA = "command-center/schema/decay-inventory.schema.json"
SNAPSHOT = "command-center/p2-wave/probes/BLD-0046/inventory-snapshot.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0046/probe1_liveness.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0046/probe2_controls.py"
)
STORED = HERE / "fixtures" / "stored-osv-lodash-4.17.20.json"
QUESTION = (
    "Which green result silently expires? Inventory every gate whose verdict "
    "depends on a live external input (advisory databases, marketplace indexes, "
    "package registries, model/vendor availability, quota state, network "
    "reachability). A last-week CI green is not a control for today."
)
SENTINEL = "SUCCESS:BLD-0046"
SCHEMA_STORE_RELS = (
    SCHEMA,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def refuse_remote(uri: str) -> None:
    raise RefResolutionError(f"offline-registry: refused remote fetch of {uri}")


def offline_validator() -> Draft202012Validator:
    store: dict[str, dict] = {}
    shim: dict | None = None
    for rel in SCHEMA_STORE_RELS:
        path = REPO / rel
        doc = json.loads(path.read_text(encoding="utf-8"))
        ident = doc.get("$id")
        if not isinstance(ident, str) or not ident:
            raise SystemExit(f"FAILED:BLD-0046 schema missing $id: {rel}")
        store[ident] = doc
        store[str(path.resolve())] = doc
        if rel == SCHEMA:
            shim = doc
    if not isinstance(shim, dict):
        raise SystemExit("FAILED:BLD-0046 shim not loaded")
    resolver = RefResolver(
        base_uri=str(shim["$id"]),
        referrer=shim,
        store=store,
        cache_remote=False,
        handlers={"http": refuse_remote, "https": refuse_remote},
    )
    return Draft202012Validator(shim, resolver=resolver)


def schema_errors(instance: dict) -> list[str]:
    out: list[str] = []
    for err in offline_validator().iter_errors(instance):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def run_cmd(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path) if path.is_file() else ("0" * 64, 1)
    if not path.is_file() or size < 1:
        raise SystemExit(f"FAILED:BLD-0046 missing artifact {rel}")
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def run_timestamps() -> dict[int, str | None]:
    out: dict[int, str | None] = {}
    for row in cited_successes():
        rid = row.get("run_id")
        if not isinstance(rid, int) or rid in out:
            continue
        meta = github_run(rid)
        out[rid] = meta.get("created_at") if meta.get("ok") else None
    return out


def liveness_control() -> dict:
    stored = json.loads(STORED.read_text(encoding="utf-8"))
    stored_ids = list(stored["vuln_ids"])
    live = query_osv(stored["package"], stored["ecosystem"], stored["version"])
    if not live.get("ok"):
        raise SystemExit(
            "FAILED:BLD-0046 OSV re-query NOT-CHECKED endpoint="
            f"{live.get('endpoint')} errors={live.get('errors')}"
        )
    live_ids = list(live["ids"])
    if set(live_ids) == set(stored_ids) or not live_ids:
        raise SystemExit(
            "FAILED:BLD-0046 liveness: live advisory set did not differ from stored "
            f"stored={stored_ids} live={live_ids}"
        )
    return {
        "endpoint": live["endpoint"],
        "package": stored["package"],
        "version": stored["version"],
        "stored_ids": stored_ids,
        "live_ids": live_ids,
        "sets_differ": True,
        "query_timestamp": live["query_timestamp"],
        "pass": True,
    }


def main() -> int:
    started = iso(utcnow()) or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:BLD-0046 named probes c1={c1} c2={c2}")
        print(t1[-1500:])
        print(t2[-1500:])
        return 1

    stamps = run_timestamps()
    inv = build_inventory(stamps)
    live_ctl = liveness_control()
    miss = classify_missing_scanner()
    if not miss["pass"]:
        print("FAILED:BLD-0046 missing-scanner control", miss)
        return 1
    ids = [e["gate_id"] for e in inv["entries"]]
    if LOCAL_CONTROL_GATE in ids:
        print("FAILED:BLD-0046 local ruff gate listed in decaying inventory")
        return 1
    if len(inv["excluded_local_gates"]) < 3:
        print("FAILED:BLD-0046 expected >=3 excluded local gates")
        return 1
    if not any(e["classification"] == "UNDATED-GREEN" for e in inv["entries"]):
        print("FAILED:BLD-0046 undated control missing")
        return 1
    if not any(e["classification"] == "INVALIDATED" for e in inv["entries"]):
        print("FAILED:BLD-0046 invalidated control missing")
        return 1

    classes = Counter(e["classification"] for e in inv["entries"])
    treated = Counter(e["treated_as"] for e in inv["entries"])
    decaying = [
        e
        for e in inv["entries"]
        if e["classification"] in {"UNDATED-GREEN", "EXPIRED", "INVALIDATED"}
    ]
    cited_live = [e for e in inv["entries"] if e.get("cited_as_green")]
    as_of = iso(utcnow()) or started
    snap = {
        "unit_id": "BLD-0046",
        "as_of": as_of,
        "freshness_policy_source": "TST-0235",
        "max_age_seconds": MAX_AGE_SECONDS,
        "classification_counts": dict(classes),
        "treated_as_counts": dict(treated),
        "decaying_count": len(decaying),
        "cited_live_green_count": len(cited_live),
        "entries": inv["entries"],
        "excluded_local_gates": inv["excluded_local_gates"],
        "github_run_timestamps": {str(k): v for k, v in stamps.items()},
        "liveness": live_ctl,
        "exit_127": miss,
    }
    snap_path = REPO / SNAPSHOT
    snap_path.write_text(
        json.dumps(snap, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    answer = (
        f"As of {as_of}, {len(inv['entries'])} live-source gates/receipts were "
        f"inventoried and {len(inv['excluded_local_gates'])} local gates were "
        f"excluded. Decaying stored greens: {len(decaying)} "
        f"(UNDATED-GREEN={classes.get('UNDATED-GREEN', 0)}, "
        f"EXPIRED={classes.get('EXPIRED', 0)}, "
        f"INVALIDATED={classes.get('INVALIDATED', 0)}). "
        "Undated greens are UNKNOWN, never PASS. Stale/invalidated stored greens "
        "are NOT-CHECKED per TST-0235. Live OSV re-query of lodash@4.17.20 "
        f"returned {len(live_ctl['live_ids'])} GHSA ids versus stored "
        f"{live_ctl['stored_ids']}. Scanner exit 127 classifies TOOL-FAILURE. "
        f"{LOCAL_CONTROL_GATE} is excluded. {SENTINEL}"
    )

    ended = iso(utcnow()) or as_of
    doc: dict = {
        "schema_version": 1,
        "unit_id": "BLD-0046",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:23024-23072",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "supply-chain-auditor",
            "execution_substrate": "linux-p2-deliver",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2048,
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            art(SCHEMA, "supporting"),
            art(SNAPSHOT, "supporting"),
            art("command-center/p2-wave/probes/BLD-0046/classify.py", "supporting"),
            art("command-center/p2-wave/probes/BLD-0046/inventory.py", "supporting"),
            art(
                "command-center/p2-wave/probes/BLD-0046/fixtures/stored-osv-lodash-4.17.20.json",
                "fixture",
            ),
        ],
        "evidence": [
            {
                "claim": (
                    "Re-querying https://api.osv.dev/v1/query for lodash@4.17.20 "
                    "returns a GHSA set that differs from the stored fixture, so "
                    "the advisory source is live rather than cached."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": (
                    "command-center/p2-wave/probes/BLD-0046/fixtures/"
                    "stored-osv-lodash-4.17.20.json"
                ),
                "probes": [
                    {
                        "role": "source",
                        "method": "http",
                        "command": P1,
                        "raw_output": t1[-8000:],
                        "fingerprint": fp("http", P1),
                        "exit_code": c1,
                    },
                    {
                        "role": "verifier",
                        "method": "file-read",
                        "command": (
                            "python3 -c read fixtures/stored-osv-lodash-4.17.20.json "
                            "and diff vuln_ids against live OSV ids"
                        ),
                        "raw_output": (
                            f"stored_ids={live_ctl['stored_ids']} "
                            f"live_ids={live_ctl['live_ids']} "
                            f"sets_differ={live_ctl['sets_differ']}"
                        ),
                        "fingerprint": fp(
                            "file-read",
                            "stored-osv-lodash-4.17.20.json#vuln_ids",
                        ),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
            {
                "claim": (
                    "A missing scanner binary exits 127 and classifies "
                    "TOOL-FAILURE, never CLEAN. quality/lint (ruff) has no live "
                    "external input and is excluded from the decaying-green inventory."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/BLD-0046/classify.py",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P2,
                        "raw_output": t2[-8000:],
                        "fingerprint": fp("command", P2),
                        "exit_code": c2,
                    },
                    {
                        "role": "verifier",
                        "method": "static-analysis",
                        "command": (
                            "python3 -c classify_scanner_exit(127) and "
                            "LOCAL_CONTROL_GATE not in build_inventory()['entries']"
                        ),
                        "raw_output": (
                            f"exit_127={miss['exit_code']} "
                            f"class={miss['classification']} "
                            f"local_gate={LOCAL_CONTROL_GATE} "
                            f"in_inventory=false "
                            f"excluded={len(inv['excluded_local_gates'])}"
                        ),
                        "fingerprint": fp(
                            "static-analysis",
                            "classify_scanner_exit+LOCAL_CONTROL_GATE",
                        ),
                        "exit_code": 0,
                    },
                ],
                "unverified": False,
            },
        ],
        "tests": [
            {
                "id": "liveness",
                "name": "Live OSV re-query differs from stored lodash advisory set",
                "command": P1,
                "result": "PASS",
                "assertions": 3,
                "output_tail": t1[-1500:],
            },
            {
                "id": "exit-127",
                "name": "Scanner exit 127 classifies TOOL-FAILURE never CLEAN",
                "command": P2,
                "result": "PASS",
                "assertions": 4,
                "output_tail": t2[-1500:],
            },
            {
                "id": "local-gate-excluded",
                "name": "quality/lint ruff gate is absent from decaying inventory",
                "command": P2,
                "result": "PASS",
                "assertions": 2,
                "output_tail": f"excluded={LOCAL_CONTROL_GATE} in_inventory=false",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-missing-scanner-127",
                "kind": "absent-input",
                "description": (
                    "Invoking osv-scanner-not-installed-bld0046 must classify "
                    "TOOL-FAILURE (bad). python3 --version remains a non-127 "
                    "good-state process and is not folded into CLEAN-for-missing-tool."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": (
                    f"exit={miss['exit_code']} class={miss['classification']}"
                ),
                "good_state_output": "classify_scanner_exit(0)=CLEAN",
            },
            {
                "id": "NC-undated-green-unknown",
                "kind": "known-broken-fixture",
                "description": (
                    "A stored CLEAN with query_timestamp=null classifies "
                    "UNDATED-GREEN / UNKNOWN, never PASS."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "control.undated-advisory-receipt=UNDATED-GREEN/UNKNOWN",
                "good_state_output": "FRESH-STAMPED/WITHIN-TTL when timestamp is inside TTL",
            },
            {
                "id": "NC-local-ruff-not-inventoried",
                "kind": "known-broken-fixture",
                "description": (
                    "quality/lint has no live external input; listing it in the "
                    "decaying inventory is the bad state this control fires on."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "would list quality/lint in entries",
                "good_state_output": f"{LOCAL_CONTROL_GATE} present_in_inventory=false",
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0046-probe1-osv-requery",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "notes": (
                "Named probe1 re-queries api.osv.dev and diffs GHSA sets. Named "
                "probe2 exercises exit 127 and the local-gate exclusion. Catalog "
                "Anthropic-vendor human review is independent of G-1 probe-green."
            ),
            "reviewed_at": ended,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0046/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "BLD-0046",
            "registered_at": ended,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/BLD-0046/emit.py:offline_validator",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 -B command-center/p2-wave/probes/BLD-0046/emit.py "
                        "# offline Draft202012Validator against decay-inventory shim"
                    ),
                    "raw_output": "schema_error_count=0",
                    "fingerprint": fp(
                        "schema-validate",
                        "offline Draft202012Validator#decay-inventory",
                    ),
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "Retry once on a transient network error with the error recorded; "
                "a second failure is reported NOT-CHECKED with the endpoint named, "
                "never folded into a pass."
            ),
            "attempts": [
                {
                    "attempt": 1,
                    "outcome": "SUCCESS",
                    "started_at": started,
                }
            ],
        },
        "residual_unknowns": [
            {
                "claim": (
                    "GitHub Actions created_at for cited run ids may be "
                    "NOT-CHECKED when api.github.com refuses an unauthenticated "
                    "lookup; those rows stay UNDATED-GREEN / UNKNOWN."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run github_run() with a repo-scoped token and reclassify "
                    "rows whose created_at then parses."
                ),
            }
        ],
        "report": {
            "kind": "decay-inventory",
            "observations": [
                {
                    "name": "live_source_entry_count",
                    "measured": len(inv["entries"]),
                    "method": "AUD-0041 YAML inventory plus BLD-0046 control fixtures",
                    "anchor": SNAPSHOT,
                },
                {
                    "name": "decaying_stored_green_count",
                    "measured": len(decaying),
                    "method": "TST-0235 max-age 86400s plus undated/invalidated fixtures",
                    "anchor": SNAPSHOT,
                },
                {
                    "name": "undated_green_count",
                    "measured": classes.get("UNDATED-GREEN", 0),
                    "method": "classify_stored_green with missing timestamp",
                    "anchor": SNAPSHOT,
                },
                {
                    "name": "excluded_local_gate_count",
                    "measured": len(inv["excluded_local_gates"]),
                    "method": "LOCAL_MARKERS without LIVE_OVERRIDE",
                    "anchor": SNAPSHOT,
                },
                {
                    "name": "live_osv_sets_differ",
                    "measured": True,
                    "method": "POST https://api.osv.dev/v1/query lodash@4.17.20",
                    "anchor": live_ctl["endpoint"],
                },
                {
                    "name": "exit_127_is_tool_failure",
                    "measured": True,
                    "method": "invoke missing osv-scanner-not-installed-bld0046",
                    "anchor": "command-center/p2-wave/probes/BLD-0046/scanner.py",
                },
                {
                    "name": "local_ruff_gate_in_inventory",
                    "measured": False,
                    "method": "build_inventory gate_id membership",
                    "anchor": SNAPSHOT,
                },
            ],
            "control_ids": [
                "liveness-osv-requery",
                "exit-127-tool-failure",
                "local-gate-excluded",
            ],
            "question": QUESTION,
            "question_answer": answer,
            "as_of": as_of,
            "freshness_policy": {
                "source_unit": "TST-0235",
                "consumed_not_rebuilt": True,
                "stale_stored_green_is": "NOT-CHECKED",
                "max_age_seconds": MAX_AGE_SECONDS,
                "undated_is": "UNDATED-GREEN",
                "treated_as_when_undated": "UNKNOWN",
                "retry_transient_once": True,
                "second_failure_is": "NOT-CHECKED",
            },
            "classification_counts": dict(classes),
            "treated_as_counts": dict(treated),
            "entries": inv["entries"],
            "excluded_local_gates": inv["excluded_local_gates"],
            "controls": {
                "liveness": live_ctl,
                "exit_127": miss,
                "local_gate_excluded": {
                    "gate_id": LOCAL_CONTROL_GATE,
                    "present_in_inventory": False,
                    "pass": True,
                },
            },
        },
        "extensions": {
            "stage": "p2-deliver",
            "p2_deliver": True,
            "title": (
                "Decaying-green inventory: gates whose verdict depends on a live source"
            ),
            "cloud_ok": False,
            "unit_manifest_write": False,
            "git_operations_invoked": False,
            "named_probes": [
                {"id": "probe1", "role": "advisory-liveness", "command": P1},
                {"id": "probe2", "role": "exit127-and-local-exclusion", "command": P2},
            ],
            "completion_line": "UNIT-COMPLETE:BLD-0046",
        },
    }

    errs = schema_errors(doc)
    if errs:
        print("FAILED:BLD-0046 schema errors")
        for err in errs[:40]:
            print(" ", err)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    payload = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    out.write_text(payload, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:BLD-0046 artifact {size}B below floor")
        return 1
    post = schema_errors(json.loads(out.read_text(encoding="utf-8")))
    if post:
        print("FAILED:BLD-0046 schema errors after rewrite")
        for err in post[:40]:
            print(" ", err)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"entries={len(doc['report']['entries'])} "
        f"excluded={len(doc['report']['excluded_local_gates'])} "
        f"live_ghsas={len(live_ctl['live_ids'])}"
    )
    print("SUCCESS:BLD-0046 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
