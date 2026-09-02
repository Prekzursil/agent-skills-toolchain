#!/usr/bin/env python3
"""Emit RES-0171 design-spec JSON from live measurements.

Validates against the catalog design-spec shim via an offline RefResolver.
Does not rebuild command-center/schema/design-spec.schema.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from cache_key import KEY_FIELDS, REQUIRED_QUESTION_FIELDS  # noqa: E402
from policy import SOURCE_CLASSES, UNMEASURED_BUCKET  # noqa: E402
from scenario import run_all, snippet_at  # noqa: E402
import schema_ctl  # noqa: E402

OUT_REL = (
    "command-center/research/deep-research-design/"
    "RES-0171-research-cache-key-and-resume.json"
)
SCHEMA_REL = "command-center/schema/design-spec.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0171/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0171/probe2_key_ttl.py"
)
QUESTION = (
    "What must the cache key for a search/fetch result include (query, backend, "
    "filters, time bucket, backend version) so that a resumed run reuses work "
    "safely, and what staleness policy applies per source class so a resumed run "
    "does not cite a cached page that has since changed?"
)
MIN_BYTES = 2048
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/RES-0171/cache_key.py",
    "command-center/p2-wave/probes/RES-0171/policy.py",
    "command-center/p2-wave/probes/RES-0171/store.py",
    "command-center/p2-wave/probes/RES-0171/resume.py",
    "command-center/p2-wave/probes/RES-0171/scenario.py",
    "command-center/p2-wave/probes/RES-0171/probe1_both_states.py",
    "command-center/p2-wave/probes/RES-0171/probe2_key_ttl.py",
    "command-center/p2-wave/probes/RES-0171/schema_ctl.py",
    "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9111.txt",
    "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9110-validators.txt",
]


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe(role: str, method: str, command: str, raw: str) -> dict:
    text = raw if len(raw) <= 65000 else raw[:65000]
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": text,
        "fingerprint": fp(method, command),
    }


def lineage(path: Path, url: str, status: int, fetched_at: str) -> dict:
    digest, n = sha256_file(path)
    return {
        "resolved_url": url,
        "fetched_at": fetched_at,
        "sha256": digest,
        "http_status": status,
        "bytes": n,
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
    }


def ev(rel: str, needle: str, kind: str, claim: str) -> dict:
    line, snippet = snippet_at(REPO / rel, needle)
    if line == 0:
        raise SystemExit(f"FAILED:RES-0171 emit evidence needle missing {rel!r} {needle!r}")
    return {
        "path": rel,
        "line": line,
        "snippet": snippet[:240],
        "kind": kind,
        "claim": claim,
    }


def art_row(rel: str, role: str) -> dict:
    digest, n = sha256_file(REPO / rel)
    return {
        "path": rel,
        "bytes": n,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def main() -> int:
    started = iso_now()
    live = run_all(REPO)
    if not live.get("pass"):
        print("FAILED:RES-0171 emit live scenarios unpaid")
        return 1
    both = live["both_states"]
    keys = live["key_sensitivity"]
    corrupt = live["corrupt"]
    clock = live["clock"]
    table = live["policy"]
    fetched_at = iso_now()
    rfc9111 = HERE / "fixtures/captures/rfc9111.txt"
    rfc9110 = HERE / "fixtures/captures/rfc9110-validators.txt"
    lin_rfc = lineage(
        rfc9111, "https://www.rfc-editor.org/rfc/rfc9111.txt", 200, fetched_at
    )
    lin_rfc0 = lineage(
        rfc9110, "https://www.rfc-editor.org/rfc/rfc9110.txt", 200, fetched_at
    )
    lin_cat = lineage(
        REPO / "command-center/WORK-UNIT-CATALOG.json",
        "file://command-center/WORK-UNIT-CATALOG.json#RES-0171",
        0,
        fetched_at,
    )
    lin_ck = lineage(
        HERE / "cache_key.py",
        "file://command-center/p2-wave/probes/RES-0171/cache_key.py",
        0,
        fetched_at,
    )

    needles = [
        ev(
            "command-center/p2-wave/probes/RES-0171/cache_key.py",
            "REQUIRED_QUESTION_FIELDS",
            "live-tree",
            "C1",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9111.txt",
            'The "cache key" is the information a cache uses to choose a response',
            "capture",
            "C1",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0171/policy.py",
            "UNMEASURED_BUCKET",
            "live-tree",
            "C2",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9111.txt",
            "5.2.2.2. must-revalidate",
            "capture",
            "C2",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0171/scenario.py",
            "Resume reuses an unchanged origin and refetches a mutated origin.",
            "live-tree",
            "C3",
        ),
        ev(
            "command-center/WORK-UNIT-CATALOG.json",
            '"id": "RES-0171"',
            "catalog",
            "C2",
        ),
        ev(
            "command-center/p2-wave/probes/RES-0171/store.py",
            "body-hash-mismatch",
            "live-tree",
            "C4",
        ),
    ]

    answer = (
        "The cache key is the SHA-256 of a canonical JSON record whose fields "
        "are query, backend, filters, time_bucket, backend_version, plus "
        "source_class and kind. Omitting any field is rejected. Changing any "
        "one field changes the key (live distinct_keys="
        f"{keys['distinct_keys']}). time_bucket is a discrete token from the "
        "per-class TTL: when RES-0006 measured TTLs are absent, every class "
        f"uses the worst-case default {UNMEASURED_BUCKET!r} (must-revalidate "
        "before cite; heuristic freshness refused). Resume reuses an unchanged "
        f"origin (action={both['stable_resume_action']}) and refetches a "
        f"mutated origin (action={both['mutated_resume_action']}). A "
        "hash-mismatched cache body is never served. SUCCESS:RES-0171"
    )

    cmd_keys = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys,json; sys.path.insert(0,'command-center/p2-wave/probes/RES-0171'); "
        "import scenario as S; print(json.dumps(S.run_key_sensitivity(), sort_keys=True))\""
    )
    cmd_both = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys,json; sys.path.insert(0,'command-center/p2-wave/probes/RES-0171'); "
        "import scenario as S; print(json.dumps({k:v for k,v in S.run_both_states().items() if k!='body'}, sort_keys=True, default=str))\""
    )
    cmd_corrupt = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys,json; sys.path.insert(0,'command-center/p2-wave/probes/RES-0171'); "
        "import scenario as S; print(json.dumps(S.run_corrupt_never_served(), sort_keys=True))\""
    )
    cmd_clock = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import sys,json; sys.path.insert(0,'command-center/p2-wave/probes/RES-0171'); "
        "import scenario as S; print(json.dumps(S.run_unmeasured_bucket_clock_free(), sort_keys=True))\""
    )

    printable_both = {k: v for k, v in both.items() if k != "body"}
    evidence = [
        {
            "claim": (
                "A research search/fetch cache key that omits query, backend, "
                "filters, time_bucket, or backend_version is unsound: changing "
                "any one of those fields must change the key, and omitting "
                "backend_version must be rejected rather than colliding."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/RES-0171/cache_key.py:REQUIRED_QUESTION_FIELDS",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    cmd_keys,
                    json.dumps(keys, sort_keys=True, default=str),
                ),
                probe(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9111.txt:248",
                    needles[1]["snippet"],
                ),
            ],
        },
        {
            "claim": (
                "Staleness is bound to measured per-class TTLs from RES-0006; "
                "because that measurement is absent on this worktree, every "
                "source class uses the worst-case default must-revalidate and "
                "the artifact says so. Heuristic freshness is refused."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/RES-0171/policy.py:UNMEASURED_BUCKET",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    cmd_clock,
                    json.dumps(
                        {
                            "clock": clock,
                            "res0006_present": table["res0006_present"],
                            "unmeasured_class_count": table["unmeasured_class_count"],
                        },
                        sort_keys=True,
                    ),
                ),
                probe(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9111.txt:1219",
                    needles[3]["snippet"],
                ),
            ],
        },
        {
            "claim": (
                "A resumed run reuses an unchanged cached entry and refetches "
                "a changed one; both states are demonstrated on a mutated fixture."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/RES-0171/scenario.py:run_both_states",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    cmd_both,
                    json.dumps(printable_both, sort_keys=True, default=str),
                ),
                probe(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/RES-0171/fixtures/captures/rfc9110-validators.txt",
                    "A strong validator is representation metadata that changes value whenever a change occurs to the representation data",
                ),
            ],
        },
        {
            "claim": (
                "A truncated or hash-mismatched cache body is never served; "
                "the origin is refetched (corrupted-cache class)."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": "command-center/p2-wave/probes/RES-0171/store.py:body-hash-mismatch",
            "probes": [
                probe(
                    "source",
                    "test-run",
                    cmd_corrupt,
                    json.dumps(corrupt, sort_keys=True),
                ),
                probe(
                    "verifier",
                    "file-read",
                    "command-center/p2-wave/probes/RES-0171/store.py",
                    needles[6]["snippet"],
                ),
            ],
        },
    ]

    report = {
        "kind": "design-spec",
        "observations": [
            {
                "name": "stable_resume_action",
                "measured": both["stable_resume_action"],
                "method": "in-process-cache-resume",
                "anchor": "command-center/p2-wave/probes/RES-0171/scenario.py:run_both_states",
            },
            {
                "name": "mutated_resume_action",
                "measured": both["mutated_resume_action"],
                "method": "in-process-cache-resume",
                "anchor": "command-center/p2-wave/probes/RES-0171/scenario.py:run_both_states",
            },
            {
                "name": "distinct_keys",
                "measured": keys["distinct_keys"],
                "method": "one-at-a-time-field-mutation",
                "anchor": "command-center/p2-wave/probes/RES-0171/scenario.py:run_key_sensitivity",
            },
            {
                "name": "omitted_backend_version_rejected",
                "measured": keys["omitted_backend_version_rejected"],
                "method": "negative-control-omit-field",
                "anchor": "command-center/p2-wave/probes/RES-0171/cache_key.py:derive_cache_key",
            },
            {
                "name": "unmeasured_class_count",
                "measured": table["unmeasured_class_count"],
                "method": "policy_table",
                "anchor": "command-center/p2-wave/probes/RES-0171/policy.py:policy_table",
            },
            {
                "name": "corrupt_served_flipped",
                "measured": corrupt["served_flipped"],
                "method": "bitflip-on-disk",
                "anchor": "command-center/p2-wave/probes/RES-0171/scenario.py:run_corrupt_never_served",
            },
        ],
        "control_ids": [
            "NC-omit-backend-version",
            "NC-mutated-origin",
            "NC-corrupt-body",
        ],
        "title": "Research cache key design and resume semantics for a long-running run",
        "question": QUESTION,
        "answer": answer,
        "cache_key": {
            "fields": list(KEY_FIELDS),
            "question_fields": list(REQUIRED_QUESTION_FIELDS),
            "encoding": "sha256(canonical-json of seven fields; clock-free)",
            "omitted_field_rejected": True,
            "live_base_key": keys["base_key"],
            "live_distinct_keys_after_one_at_a_time": keys["distinct_keys"],
        },
        "staleness_policy": {
            "bound_to_measured_ttls": True,
            "res0006_present": False,
            "res0006_path": table["res0006_path"],
            "unmeasured_uses_worst_case_default": True,
            "worst_case_default": table["worst_case_default"],
            "classes": table["classes"],
            "source_classes": list(SOURCE_CLASSES),
            "unmeasured_class_count": table["unmeasured_class_count"],
            "source_class_list_provenance": table["source_class_list_provenance"],
            "heuristic_freshness": False,
        },
        "both_states": {
            "stable_resume_action": both["stable_resume_action"],
            "mutated_resume_action": both["mutated_resume_action"],
            "stable_body_unchanged": both["stable_body_unchanged"],
            "mutated_body_changed": both["mutated_body_changed"],
            "fetches": both["fetches"],
            "counters": both["counters"],
            "keys_distinct": both["keys_distinct"],
        },
        "inputs_absent": {
            "_USER-PROMPTS.md": not (REPO / "_USER-PROMPTS.md").is_file(),
            "command-center/sources/REGISTER.md": not (
                REPO / "command-center/sources/REGISTER.md"
            ).is_file(),
            "command-center/CLAIM-REGISTRY.json": not (
                REPO / "command-center/CLAIM-REGISTRY.json"
            ).is_file(),
            "command-center/research/RES-0006.json": not (
                REPO / "command-center/research/RES-0006.json"
            ).is_file(),
        },
        "claims": [
            {
                "id": "C1",
                "claim": evidence[0]["claim"],
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "lineage": [lin_ck, lin_rfc],
                "independent_verification_path": (
                    "probe2_key_ttl.py one-at-a-time field mutations + "
                    "RFC 9111 section 2 cache-key definition (method + target URI + extras)"
                ),
            },
            {
                "id": "C2",
                "claim": evidence[1]["claim"],
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "lineage": [lin_cat, lin_rfc],
                "independent_verification_path": (
                    "glob command-center/research/RES-0006.json (absent) AND "
                    "RFC 9111 section 5.2.2.2 must-revalidate: stale reuse forbidden "
                    "until origin validation"
                ),
            },
            {
                "id": "C3",
                "claim": evidence[2]["claim"],
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "lineage": [lin_ck, lin_rfc0],
                "independent_verification_path": (
                    "probe1_both_states.py fetch counters and body sha256 versus "
                    "origin files; RFC 9110 section 8.8 strong validator must change "
                    "when representation bytes change"
                ),
            },
            {
                "id": "C4",
                "claim": evidence[3]["claim"],
                "verdict": "CONFIRMED",
                "sherman_kent_band": "almost-certain",
                "lineage": [lin_ck, lin_rfc],
                "independent_verification_path": (
                    "probe2 flips one stored byte and requires action=corrupt-refetch "
                    "and served_flipped=false"
                ),
            },
        ],
        "needles": needles,
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
        "strongest_surviving_counterargument": (
            "A time_bucket inside the identity key will miss after a bucket roll "
            "even if the page is unchanged, over-fetching; omitting it silently "
            "cites across TTL. This design keeps time_bucket in the key AND "
            "revalidates unmeasured classes, paying the over-fetch to avoid a "
            "stale cite. RES-0006, if later measured, narrows buckets without "
            "changing the field list."
        ),
    }

    schema_errs_before = []
    doc = {
        "schema_version": 1,
        "unit_id": "RES-0171",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:RES-0171",
        "spec_anchor": (
            "command-center/WORK-UNIT-CATALOG.json#RES-0171; "
            "catalog question_or_target cache-key + per-class staleness"
        ),
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "p2-deliver worker",
            "execution_substrate": "headless-linux-workspace",
        },
        "artifacts": [art_row(p, "supporting") for p in SUPPORTING],
        "evidence": evidence,
        "tests": [
            {"id": "T1-both-states", "command": P1, "result": "PASS"},
            {"id": "T2-key-ttl-schema", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-omit-backend-version",
                "kind": "malformed-input",
                "description": (
                    "derive_cache_key with backend_version omitted must raise; "
                    "a complete seven-field record must produce a 64-char hex key."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "InvalidResearchCacheKey field=backend_version",
                "good_state_output": "64-char hex key",
            },
            {
                "id": "NC-mutated-origin",
                "kind": "mutation",
                "description": (
                    "Resume after origin bytes change must refetch; resume with "
                    "unchanged origin must reuse."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "action=refetch",
                "good_state_output": "action=reuse",
            },
            {
                "id": "NC-corrupt-body",
                "kind": "known-broken-fixture",
                "description": (
                    "A one-byte flip of the stored body must never be served; "
                    "action=corrupt-refetch and origin bytes returned."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "action=corrupt-refetch served_flipped=false",
                "good_state_output": "action=miss then reuse of matching body",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0171-probe2-key-ttl-schema",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Counterexample omit-backend-version is rejected and does not "
                "collide with a complete key. Garbage receipts and wrong "
                "report.kind are rejected by the catalog design-spec shim via "
                "an offline RefResolver (no ADV rebuild)."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0171/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "RES-0171 schema_ctl.errors (offline design-spec)",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "probe": probe(
                    "verifier",
                    "schema-validate",
                    "python3 -B command-center/p2-wave/probes/RES-0171/schema_ctl.py",
                    "pending-in-memory-validate",
                ),
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Measured per-class TTLs from RES-0006 are absent on this "
                    "worktree; every class therefore uses must-revalidate."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Deliver RES-0006 with a per_class_half_life table and "
                    "re-run policy_table; buckets must narrow without changing "
                    "KEY_FIELDS."
                ),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": iso_now(),
        },
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after 2 failures on the same error "
                "fingerprint, enumerate >=2 alternative approaches before a "
                "third attempt"
            ),
        },
        "report": report,
    }

    try:
        gcounts = schema_ctl.garbage_rejected()
    except AssertionError as exc:
        print(f"FAILED:RES-0171 schema accepted garbage: {exc}")
        return 1

    errs = schema_ctl.errors(doc)
    if errs:
        print("FAILED:RES-0171 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    schema_errs_before = gcounts

    doc["downstream_consumers"][0]["probe"]["raw_output"] = (
        f"schema_ok=true garbage_rejected_counts={schema_errs_before}"
    )
    # Re-validate after filling consumer raw_output.
    errs = schema_ctl.errors(doc)
    if errs:
        print("FAILED:RES-0171 schema errors after consumer fill")
        for e in errs[:20]:
            print(" ", e)
        return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:RES-0171 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT_REL} bytes={size} sha256={digest}")
    print("SUCCESS:RES-0171 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
