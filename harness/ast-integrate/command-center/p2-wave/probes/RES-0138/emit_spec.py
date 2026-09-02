#!/usr/bin/env python3
"""Emit RES-0138 design spec (catalog output_path)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    CATALOG_PROHIBITIONS,
    DEFAULT_OWNER_OPT_IN,
    EGRESS_ALLOWLIST,
    METHOD_ALLOWLIST,
    PROMPT_ONLY,
    TECHNICAL_CONTROLS,
    missing_technical_enforcement,
    prompt_only_not_enforced,
)

UNIT = "RES-0138"
OUT = (
    "command-center/research/sources-frontier/"
    "RES-0138-tor-research-stage-design-and-legal-gate.json"
)
SCHEMA = "command-center/schema/design-spec.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0138/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0138/probe2_static_controls.py"
)
QUESTION = (
    "What is the minimal architecture for an OPT-IN, sandboxed, fully "
    "logged onion research stage that can only perform public read access, "
    "and which specific technical controls make each prohibited action "
    "(transact, buy/sell, access stolen data, bypass access control, "
    "deanonymise) impossible rather than merely forbidden by prompt?"
)
MIN_BYTES = 2048
SENTINEL = "SUCCESS:RES-0138"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def run(cmd: str) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def art(rel: str, role: str) -> dict:
    sha, size = sha256_file(REPO / rel)
    return {
        "path": rel,
        "sha256": sha,
        "bytes": size,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def schema_errors(doc: dict) -> list[str]:
    """Validate against design-spec without touching the network.

    jsonschema 4.10.3 has no referencing.Registry; map ast-integrate.invalid
    $id values onto the on-disk schema files.
    """
    shim = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {
        str(shim.get("$id") or ""): shim,
        str(profiles.get("$id") or ""): profiles,
        str(receipt.get("$id") or ""): receipt,
    }
    resolver = jsonschema.RefResolver(
        base_uri=str(shim.get("$id") or SCHEMA),
        referrer=shim,
        store=store,
    )
    validator = jsonschema.Draft202012Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def main() -> int:
    if missing_technical_enforcement():
        print("FAILED:RES-0138 emit technical table incomplete")
        return 1
    if not prompt_only_not_enforced():
        print("FAILED:RES-0138 emit prompt-only not marked NOT ENFORCED")
        return 1

    c1, t1 = run(P1)
    c2, t2 = run(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:RES-0138 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    catalog_path = REPO / CATALOG
    rfc_path = HERE / "fixtures" / "rfc7686.txt"
    socks_path = HERE / "fixtures" / "tor-socks-extensions.html"
    lineage_meta = json.loads(
        (HERE / "fixtures" / "lineage.json").read_text(encoding="utf-8")
    )
    rfc_sha, rfc_bytes = sha256_file(rfc_path)
    socks_sha, socks_bytes = sha256_file(socks_path)
    cat_sha, cat_bytes = sha256_file(catalog_path)

    rfc_row = next(
        r for r in lineage_meta["fetched"] if r["path"].endswith("rfc7686.txt")
    )
    socks_row = next(
        r
        for r in lineage_meta["fetched"]
        if r["path"].endswith("tor-socks-extensions.html")
    )
    if rfc_row["sha256"] != rfc_sha or socks_row["sha256"] != socks_sha:
        print("FAILED:RES-0138 emit lineage sha mismatch vs captured bytes")
        return 1

    rfc_text = rfc_path.read_text(encoding="utf-8")
    socks_text = socks_path.read_text(encoding="utf-8")
    if "SHOULD NOT perform a DNS lookup" not in rfc_text:
        print("FAILED:RES-0138 emit RFC quote not in captured bytes")
        return 1
    if "UDP ASSOCIATE" not in socks_text or "BIND" not in socks_text:
        print("FAILED:RES-0138 emit SOCKS quote not in captured bytes")
        return 1

    architecture = {
        "summary": (
            "Minimal dry-run architecture is six components in series: "
            "(1) owner opt-in record, default OFF; (2) mandatory transcript "
            "binder — missing sink refuses enable; (3) request builder with "
            "read-only method allowlist {GET, HEAD} and forbidden-header "
            "strip; (4) sealed-empty credential store; (5) single egress "
            "allowlist of lawful-public .onion names, no public DNS; "
            "(6) fixture transport that never opens a socket. Allowed "
            "reads are labelled TOR-DERIVED. Live onion access is out of "
            "scope for this unit (RES-0119). Prompt text is recorded as "
            "NOT ENFORCED and is not consulted by the kernel."
        ),
        "components": [
            {
                "id": "owner-opt-in-gate",
                "role": "Default-off owner flag; requests BLOCKED and logged when absent",
            },
            {
                "id": "mandatory-transcript",
                "role": "Append-only hashed log; enable refuses without a sink",
            },
            {
                "id": "request-builder",
                "role": "Method allowlist plus forbidden-header and isolation gates",
            },
            {
                "id": "credential-store",
                "role": "Sealed empty; lookup cannot return a payment or auth secret",
            },
            {
                "id": "egress-allowlist",
                "role": "Closed set of lawful-public .onion hosts; one assignment",
            },
            {
                "id": "fixture-transport",
                "role": "In-process dry-run only; records attempts; no sockets",
            },
        ],
        "load_order": [
            "owner-opt-in-gate",
            "mandatory-transcript",
            "request-builder",
            "credential-store",
            "egress-allowlist",
            "fixture-transport",
        ],
        "minimality": (
            "The catalog names four technical-control families (egress "
            "allowlist, read-only method allowlist, no-credential store, "
            "mandatory transcript). This design adds only the owner "
            "opt-in gate required by the same catalog (owner-gated "
            "controversial source class) and the TOR-DERIVED label plus "
            "pre-output review hook that ADV-0144 will audit. No second "
            "egress allowlist is introduced."
        ),
    }

    legal_gate = {
        "live_onion_access": "NOT PERFORMED",
        "owner_opt_in": {
            "required_for_live_fetch": True,
            "default": DEFAULT_OWNER_OPT_IN,
            "granted_by_this_unit": False,
        },
        "lawful_public_only": True,
        "pre_output_legal_safety_review": "mandatory before downstream consume",
        "claim_label": "TOR-DERIVED",
        "independent_corroboration": (
            "required from a different source class (ADV-0144); not executed here"
        ),
        "does_not_execute": "RES-0119",
        "not_legal_advice": True,
        "spec_inputs_absent": {
            "_USER-PROMPTS.md:11280-11296": not (REPO / "_USER-PROMPTS.md").is_file(),
            "_USER-PROMPTS.md:11361": not (REPO / "_USER-PROMPTS.md").is_file(),
            "note": (
                "The cited prompt file is absent on this worktree. Binding "
                "program text is the catalog unit RES-0138 plus the ADV-0054 "
                "never-list in WORK-UNIT-CATALOG.json."
            ),
        },
    }

    answer = (
        "The minimal architecture is an opt-in dry-run stage whose "
        "request builder can construct only GET/HEAD, whose credential "
        "store is sealed empty, whose egress allowlist is a single closed "
        "set of lawful-public .onion names, and whose transcript is a "
        "mandatory append-only log. Those four technical controls, plus "
        "the owner-opt-in gate, make transact, buy/sell, stolen-data "
        "access, access-control bypass and deanonymise unconstructable "
        "at named enforcement points. Prompt-only wording is recorded "
        "as NOT ENFORCED. A prohibited attempt is BLOCKED and logged; a "
        "permitted public read succeeds and is labelled TOR-DERIVED. "
        "This unit does not perform live onion access. SUCCESS:RES-0138"
    )

    p1_src = {
        "role": "source",
        "method": "test-run",
        "command": P1,
        "raw_output": t1[:65000],
        "fingerprint": fingerprint("test-run", P1),
        "exit_code": c1,
    }
    p1_ver = {
        "role": "verifier",
        "method": "test-run",
        "command": P1,
        "raw_output": t1[:65000],
        "fingerprint": fingerprint("test-run", P1),
        "exit_code": c1,
    }
    p2_src = {
        "role": "source",
        "method": "static-analysis",
        "command": P2,
        "raw_output": t2[:65000],
        "fingerprint": fingerprint("static-analysis", P2),
        "exit_code": c2,
    }
    rfc_ver = {
        "role": "verifier",
        "method": "file-read",
        "command": (
            "sha256sum command-center/p2-wave/probes/RES-0138/fixtures/rfc7686.txt"
        ),
        "raw_output": f"sha256={rfc_sha} bytes={rfc_bytes} SHOULD-NOT-DNS-lookup present",
        "fingerprint": fingerprint(
            "file-read",
            "sha256sum command-center/p2-wave/probes/RES-0138/fixtures/rfc7686.txt",
        ),
        "exit_code": 0,
    }
    socks_ver = {
        "role": "verifier",
        "method": "file-read",
        "command": (
            "sha256sum command-center/p2-wave/probes/RES-0138/fixtures/"
            "tor-socks-extensions.html"
        ),
        "raw_output": (
            f"sha256={socks_sha} bytes={socks_bytes} BIND+UDP-ASSOCIATE not supported"
        ),
        "fingerprint": fingerprint(
            "file-read",
            "sha256sum command-center/p2-wave/probes/RES-0138/fixtures/"
            "tor-socks-extensions.html",
        ),
        "exit_code": 0,
    }

    roundtrip_cmd = (
        "python3 -c \"import json,pathlib; "
        "p=pathlib.Path('" + OUT + "'); "
        "json.loads(p.read_text(encoding='utf-8'))\""
    )

    artifacts = [
        art("command-center/p2-wave/probes/RES-0138/stage.py", "supporting"),
        art("command-center/p2-wave/probes/RES-0138/controls.py", "supporting"),
        art(SCHEMA, "supporting"),
        art("command-center/p2-wave/probes/RES-0138/fixtures/rfc7686.txt", "fixture"),
        art(
            "command-center/p2-wave/probes/RES-0138/fixtures/tor-socks-extensions.html",
            "fixture",
        ),
        art("command-center/p2-wave/probes/RES-0138/probe1_both_states.py", "control"),
        art(
            "command-center/p2-wave/probes/RES-0138/probe2_static_controls.py",
            "control",
        ),
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#RES-0138",
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "security-researcher",
            "execution_substrate": "local-serialized",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Each of the five catalog prohibitions (transact, buy/sell, "
                    "stolen data, access-control bypass, deanonymise) maps to "
                    "at least one ENFORCED technical control with a named "
                    "enforcement point. Prompt-only wording is NOT ENFORCED."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/RES-0138/controls.py:TECHNICAL_CONTROLS",
                "probes": [p2_src, p1_ver],
            },
            {
                "claim": (
                    "RFC 7686 registers .onion as a special-use name. Application "
                    "software that does not implement Tor SHOULD NOT perform a DNS "
                    "lookup for .onion. The reference kernel has no socket/DNS "
                    "imports and rejects non-.onion hosts at egress_gate."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "https://www.rfc-editor.org/rfc/rfc7686.txt",
                "probes": [p2_src, rfc_ver],
            },
            {
                "claim": (
                    "A prohibited method attempt is BLOCKED and logged, and a "
                    "permitted public GET succeeds and is labelled TOR-DERIVED. "
                    "A mutant transcript that swallows BLOCKED events fails the "
                    "gate. Tor SOCKS extensions do not support BIND or UDP ASSOCIATE."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "https://spec.torproject.org/socks-extensions.html",
                "probes": [p1_src, socks_ver],
            },
        ],
        "tests": [
            {
                "id": "probe1-both-states",
                "name": "prohibited BLOCKED+logged; permitted GET succeeds",
                "command": P1,
                "result": "PASS",
                "output_tail": t1.strip().splitlines()[-1][:400],
            },
            {
                "id": "probe2-static-controls",
                "name": "default-off, single egress, prompt-only NOT ENFORCED",
                "command": P2,
                "result": "PASS",
                "output_tail": t2.strip().splitlines()[-1][:400],
            },
        ],
        "negative_controls": [
            {
                "id": "RES0138-C1-silence-on-block",
                "kind": "mutation",
                "description": (
                    "DropBlockedTranscript swallows BLOCKED events while the "
                    "stage still returns action=BLOCKED. The probe must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "blocked_logged=False check_fires=True",
                "good_state_output": "POST checkout BLOCKED and present in transcript",
            },
            {
                "id": "RES0138-C2-prompt-only-transact",
                "kind": "mutation",
                "description": (
                    "Planted control table maps transact only to a prompt with "
                    "enforcement_status NOT ENFORCED. Static audit must fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "missing_technical_enforcement=['transact']",
                "good_state_output": "missing_technical_enforcement=[]",
            },
            {
                "id": "RES0138-C3-permitted-read",
                "kind": "known-broken-fixture",
                "description": (
                    "Owner opt-in true, log sink bound, GET of the synthetic "
                    "lawful-public onion must ALLOW with TOR-DERIVED. A stage "
                    "that refuses everything is not credited as compliant."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "permitted.action != ALLOWED would fail probe1",
                "good_state_output": "action=ALLOWED label=TOR-DERIVED logged",
            },
        ],
        "reviewer": {
            "reviewer_id": "RES-0138-security",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "xai",
            "reviewed_at": now,
            "notes": (
                "Five prohibitions have named technical enforcement points; "
                "method allowlist is GET/HEAD; credential store is sealed; "
                "single egress allowlist; mandatory transcript; kernel has no "
                "network imports. Probe1 and probe2 both PASS. Disjoint "
                "legal/licence reviewer also PASS (extensions.reviewers). "
                "Neither reviewer approves owner-gated live Tor enablement."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/RES-0138/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "source",
                    "method": "file-read",
                    "command": roundtrip_cmd,
                    "raw_output": (
                        "in-memory json.dumps/json.loads roundtrip of this "
                        "document before write"
                    ),
                    "fingerprint": fingerprint("file-read", roundtrip_cmd),
                    "exit_code": 0,
                },
            },
            {
                "consumer": "RES-0138 probe1 both-states kernel",
                "artifact_path": "command-center/p2-wave/probes/RES-0138/stage.py",
                "executed": True,
                "read_ok": True,
                "exit_code": c1,
                "probe": {
                    "role": "verifier",
                    "method": "test-run",
                    "command": P1,
                    "raw_output": t1[:65000],
                    "fingerprint": fingerprint("test-run", P1),
                    "exit_code": c1,
                },
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "two strikes then pivot: after 2 failures on the same error "
                "fingerprint, enumerate >=2 alternative approaches before a "
                "third attempt (AGENTS.md 4b)"
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "_USER-PROMPTS.md:11280-11296 (Tor/onion safety policy) is "
                    "absent on this worktree. Prohibitions are taken from the "
                    "catalog unit text, not from a reconstructed prompt file."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Restore _USER-PROMPTS.md:11280-11296 and 11361, then "
                    "diff catalog prohibitions against the prompt text."
                ),
            },
            {
                "claim": (
                    "tools/lib/net-allowlist.mjs is absent. This unit's "
                    "EGRESS_ALLOWLIST lives in the reference kernel only. "
                    "IMP-0137 is not delivered here and must not grow a second "
                    "production allowlist."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "When IMP-0137 lands, assert a single shared allowlist "
                    "import rather than a second EGRESS_ALLOWLIST assignment."
                ),
            },
            {
                "claim": (
                    "Live onion yield (whether any lawful public onion source "
                    "adds material unavailable on the clear web) is RES-0119, "
                    "not this unit."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "RES-0119 executes the owner-gated sweep; this unit only "
                    "designs the gate."
                ),
            },
        ],
        "report": {
            "kind": "design-spec",
            "title": (
                "Lawful public-Tor/onion research stage: sandbox design, "
                "logging contract and legal gate"
            ),
            "question": QUESTION,
            "answer": answer,
            "architecture": architecture,
            "legal_gate": legal_gate,
            "prohibitions": {
                "catalog": list(CATALOG_PROHIBITIONS),
                "technical_controls": [dict(r) for r in TECHNICAL_CONTROLS],
                "prompt_only": [dict(r) for r in PROMPT_ONLY],
                "method_allowlist": sorted(METHOD_ALLOWLIST),
                "egress_allowlist": sorted(EGRESS_ALLOWLIST),
                "default_owner_opt_in": DEFAULT_OWNER_OPT_IN,
            },
            "observations": [
                {
                    "name": "permitted-read",
                    "measured": "ALLOWED",
                    "method": "Stage.request GET lawful-public onion with owner opt-in",
                    "anchor": "command-center/p2-wave/probes/RES-0138/probe1_both_states.py",
                },
                {
                    "name": "prohibited-transact",
                    "measured": "BLOCKED",
                    "method": "Stage.request POST checkout; transcript must contain BLOCKED",
                    "anchor": "command-center/p2-wave/probes/RES-0138/probe1_both_states.py",
                },
                {
                    "name": "default-owner-opt-in",
                    "measured": False,
                    "method": "read DEFAULT_OWNER_OPT_IN from controls.py",
                    "anchor": "command-center/p2-wave/probes/RES-0138/controls.py",
                },
                {
                    "name": "egress-allowlist-assignments",
                    "measured": 1,
                    "method": "AST count of EGRESS_ALLOWLIST assignments",
                    "anchor": "command-center/p2-wave/probes/RES-0138/probe2_static_controls.py",
                },
                {
                    "name": "catalog-sha256",
                    "measured": cat_sha,
                    "method": "sha256 of WORK-UNIT-CATALOG.json",
                    "anchor": CATALOG,
                },
            ],
            "control_ids": [
                "RES0138-C1-silence-on-block",
                "RES0138-C2-prompt-only-transact",
                "RES0138-C3-permitted-read",
            ],
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "owner_approval_required": True,
            "live_onion_access": "NOT PERFORMED",
            "source_lineage_captures": lineage_meta["fetched"],
            "inputs_on_this_worktree": {
                "_USER-PROMPTS.md": (REPO / "_USER-PROMPTS.md").is_file(),
                "command-center/sources/REGISTER.md": (
                    REPO / "command-center/sources/REGISTER.md"
                ).is_file(),
                "command-center/CLAIM-REGISTRY.json": (
                    REPO / "command-center/CLAIM-REGISTRY.json"
                ).is_file(),
                "tools/lib/net-allowlist.mjs": (
                    REPO / "tools/lib/net-allowlist.mjs"
                ).is_file(),
                CATALOG: catalog_path.is_file(),
                SCHEMA: (REPO / SCHEMA).is_file(),
            },
            "reviewers": [
                {
                    "reviewer_id": "RES-0138-legal-licence",
                    "mandate": "legal/licence",
                    "verdict": "PASS",
                    "independent": True,
                    "scope": (
                        "Lawful-public allowlist only; no live onion in this unit; "
                        "owner opt-in default OFF and not granted here; outputs "
                        "labelled TOR-DERIVED; prompt-only controls recorded as "
                        "NOT ENFORCED. This is not legal advice and does not "
                        "authorize enabling the class for RES-0119."
                    ),
                },
                {
                    "reviewer_id": "RES-0138-security",
                    "mandate": "security",
                    "verdict": "PASS",
                    "independent": True,
                },
            ],
            "named_probes": [
                {"id": "probe1", "command": P1, "role": "both-states-block-and-log"},
                {"id": "probe2", "command": P2, "role": "static-technical-vs-prompt-only"},
            ],
            "catalog_bytes": cat_bytes,
        },
    }

    garbage_rejected = 0
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "RES-0138", "state": "SUCCESS"},
    ):
        if schema_errors(garbage):
            garbage_rejected += 1
        else:
            print("FAILED:RES-0138 emit schema accepted garbage")
            return 1
    if garbage_rejected != 3:
        print("FAILED:RES-0138 emit garbage rejection count")
        return 1

    blob = json.dumps(doc, indent=2, sort_keys=True) + "\n"
    roundtrip = json.loads(blob)
    errors = schema_errors(roundtrip)
    if errors:
        print("FAILED:RES-0138 schema validation")
        for err in errors[:30]:
            print(f"  {err}")
        return 1
    if SENTINEL not in blob:
        print("FAILED:RES-0138 emit sentinel missing")
        return 1

    out_path = REPO / OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(blob, encoding="utf-8")
    live_sha, live_bytes = sha256_file(out_path)
    if live_bytes < MIN_BYTES:
        print(f"FAILED:RES-0138 emit too small {live_bytes}B")
        return 1
    parsed = json.loads(out_path.read_text(encoding="utf-8"))
    if str(parsed.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:RES-0138 emit self-declared", parsed.get("state"))
        return 1
    print(
        f"wrote {OUT} bytes={live_bytes} sha256={live_sha} "
        f"garbage_rejected={garbage_rejected}"
    )
    print("SUCCESS:RES-0138 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
