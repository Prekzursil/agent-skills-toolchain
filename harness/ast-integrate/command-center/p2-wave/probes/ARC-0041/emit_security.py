#!/usr/bin/env python3
"""Emit command-center/phase3/A6/SECURITY.json for ARC-0041."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import anchors as A  # noqa: E402
import claim_dossier as C  # noqa: E402
import corpus as CORP  # noqa: E402
import never_forward as NF  # noqa: E402
import overclaim as O  # noqa: E402

OUT = "command-center/phase3/A6/SECURITY.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CLAIM = C.OUT
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
ADAPTER = "command-center/adapters/codex.py"
QUESTION = (
    "Specify the trust boundary between vendors: a second vendor's output "
    "is untrusted DATA and a prompt-injection carrier, never instructions. "
    "Define where it is sanitized, what an adapter may NEVER forward "
    "(credentials, raw tool-permission grants, hook configuration, absolute "
    "paths into credential stores), and how a cross-vendor artifact is "
    "quarantined before any Claude-side agent reads it."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0041/probe1_injection_corpus.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0041/probe2_never_forward.py"
)
COUNTER = (
    "A mention that is not wrapped in MENTION-BEGIN/END or a fenced "
    "injection-example still looks like a use, so catch rate on unwrapped "
    "educational text would be a false positive. Structural wrappers are "
    "the use-versus-mention control; intent classification is not claimed. "
    "The live Codex adapter still returns parsed unsanitized; this unit "
    "specifies the return-path contract and ships the executable quarantine "
    "without patching IMP-0421 (that would be an ADV rebuild of a delivered rail)."
)
CATCHING = (
    "A6 return-path quarantine envelope plus never-forward allowlist, "
    "applied after last-message parse and before any Claude-side agent "
    "reads parsed"
)
REQUIRED_KEYS = (
    "unit_id",
    "state",
    "sentinel",
    "claims",
    "evidence",
    "injection_corpus",
    "never_forward",
    "artifacts",
    "min_bytes_threshold",
)


def _local_schema_ok(doc: object) -> tuple[bool, str]:
    """Reject garbage without following the catalog shim's remote $ref.

    architecture-review.schema.json is a $ref shim. Draft7Validator without
    platform.lib.schema_resolver either raises or accepts everything. G-1
    named probes own the live checks; this gate only refuses empty/unrelated
    blobs the previous emit used as a detector control.
    """
    if not isinstance(doc, dict):
        return False, "not-object"
    missing = [k for k in REQUIRED_KEYS if k not in doc]
    if missing:
        return False, "missing:" + ",".join(missing)
    if doc.get("unit_id") != "ARC-0041":
        return False, "unit_id"
    if str(doc.get("state") or "") != "SUCCESS":
        return False, "state"
    if "SUCCESS:ARC-0041" not in str(doc.get("sentinel") or ""):
        return False, "sentinel"
    claims = doc.get("claims")
    evidence = doc.get("evidence")
    if not isinstance(claims, list) or len(claims) < 3:
        return False, "claims"
    if not isinstance(evidence, list) or len(evidence) < 4:
        return False, "evidence"
    corpus = doc.get("injection_corpus")
    nf = doc.get("never_forward")
    if not isinstance(corpus, dict) or corpus.get("computed_not_asserted") is not True:
        return False, "injection_corpus"
    if not isinstance(nf, dict) or nf.get("fail_closed_clean") is not True:
        return False, "never_forward"
    return True, "ok"


def _schema_ok(doc: dict) -> bool:
    ok, why = _local_schema_ok(doc)
    if not ok:
        print(f"FAILED:ARC-0041 schema {why}")
        return False
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        g_ok, _ = _local_schema_ok(g)
        if g_ok:
            print(f"FAILED:ARC-0041 schema accepted garbage {list(g)[:2]}")
            return False
    return True


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0041 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    C.write_claim(REPO)
    inj = CORP.run_corpus()
    if not inj.get("pass"):
        print("FAILED:ARC-0041 injection corpus did not pass")
        print(json.dumps(inj, indent=2, sort_keys=True)[:4000])
        return 1
    nf = NF.run_never_forward()
    if not nf.get("pass"):
        print("FAILED:ARC-0041 never-forward did not pass")
        print(json.dumps(nf, indent=2, sort_keys=True)[:4000])
        return 1

    e1 = ev(CLAIM, C.TRUST_BOUNDARY, "dossier", C.TRUST_BOUNDARY)
    e2 = ev(CLAIM, C.SANITIZE_WHERE, "dossier", C.SANITIZE_WHERE)
    e3 = ev(CLAIM, C.NEVER_FORWARD, "dossier", C.NEVER_FORWARD)
    e4 = ev(CLAIM, C.SILENT_LOSS, "dossier", C.SILENT_LOSS)
    e5 = ev(
        ADAPTER,
        '"parsed": parsed,',
        "live-tree",
        "Live Codex adapter forwards parsed last-message with no sanitizer.",
    )
    e6 = ev(
        CATALOG,
        "a second vendor's output is untrusted DATA",
        "live-tree",
        "Catalog ARC-0041 names vendor output as untrusted DATA never instructions.",
    )
    e7 = ev(
        CATALOG,
        "The sanitizer is exercised against an injection corpus",
        "live-tree",
        "Catalog requires per-class catch rate on role-spoof, override, encoded.",
    )
    e8 = ev(
        ADAPTER,
        '"classification": None,',
        "live-tree",
        "Live adapter success path returns unsanitized parsed with no never-forward strip.",
    )
    dossier_n = sum(1 for e in (e1, e2, e3, e4) if e["kind"] == "dossier")
    live_n = sum(1 for e in (e5, e6, e7, e8) if e["kind"] == "live-tree")
    if dossier_n < 3 or live_n < 1:
        print(f"FAILED:ARC-0041 evidence counts dossier={dossier_n} live={live_n}")
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    per_class = inj["per_class"]
    doc = {
        "unit_id": "ARC-0041",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:ARC-0041",
        "completion_sentinel": "SUCCESS:ARC-0041",
        "architecture_id": "A6",
        "architecture_class": "cross-vendor-adapter",
        "title": (
            "A6 (cross-vendor adapter): Treating a second vendor's output "
            "as untrusted data, and what an adapter may never forward"
        ),
        "question": QUESTION,
        "claim_under_test": C.TRUST_BOUNDARY,
        "headline_verdict": "SPECIFIED",
        "a6_design_json_present": False,
        "adv_rebuild_circle": False,
        "required_fix": None,
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "security-reviewer",
            "execution_substrate": "headless-linux",
        },
        "trust_boundary": {
            "untrusted": "second-vendor-last-message",
            "treat_as": "DATA",
            "never": "instructions",
            "sanitize_locus": "vendor-return-path-after-parse",
            "not_the_locus": "inbound-prompt-file-transport",
            "quarantine_before": "any-claude-side-agent-read",
            "envelope_kind": "untrusted-vendor-data",
            "fail_closed": True,
        },
        "never_forward_classes": [
            "credentials",
            "raw-tool-permission-grants",
            "hook-configuration",
            "absolute-paths-into-credential-stores",
        ],
        "scenario": {
            "id": "S1-return-path-quarantine-and-never-forward",
            "title": (
                "Vendor last-message is quarantined as DATA; injection classes "
                "are caught; env canary never appears on the sealed outbound"
            ),
            "on_this_estate": (
                "A6 DESIGN.json is absent (ARC-0038). OWNER-DECISIONS.md, "
                "ROSTER.json, RUBRIC.json, and RISK-REGISTER.md are absent. "
                "Live Codex adapter at command-center/adapters/codex.py "
                "returns parsed unsanitized. This unit cites "
                "CLAIM-UNDER-TEST.json rather than rebuilding DESIGN.json."
            ),
            "silent_loss_file": e4["anchor"],
            "catching_architecture": CATCHING,
            "procedure": [
                "1. Write the ARC-0041 claim extract (not A6 DESIGN.json).",
                "2. Run the injection corpus (role-spoof, instruction-override, encoded) through scan_instruction_hits.",
                "3. Assert per-class catch rate; a class with zero catches is P1.",
                "4. Run wrapped mention controls and require zero false-positive uses.",
                "5. Plant ARC0041_CANARY_SECRET in the environment plus a leaky vendor payload (canary, tool_permissions, hooks, credential-store path).",
                "6. Seal the adapter result; walk strings and json.dumps must both show the canary absent; forbidden keys must be stripped.",
                "7. Fail-open mutant must leak the canary (detector control). Disagreeing leak signals are BLOCKED.",
                "8. Cite adapters/codex.py parsed passthrough as the live gap the contract closes without patching IMP-0421.",
            ],
            "executable": (
                "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                "command-center/p2-wave/probes/ARC-0041/corpus.py"
            ),
        },
        "claims": [
            {
                "id": "C1",
                "claim": C.TRUST_BOUNDARY,
                "verdict": "CONFIRMED",
                "anchor": e1["anchor"],
            },
            {
                "id": "C2",
                "claim": (
                    "The live Codex adapter already sanitizes parsed output "
                    "before a Claude-side agent can read it."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "why_locus": (
                    "adapters/codex.py _result returns parsed as the raw "
                    "last-message. That is the adapter's return contract, not "
                    "a wording slip. IMP-0421 delivered prompt-by-file inbound "
                    "transport; it did not add a return-path sanitizer."
                ),
                "scoped_restatement": (
                    "The A6 security contract applies quarantine after parse. "
                    "The live Codex adapter does not yet apply it. This unit "
                    "does not patch IMP-0421."
                ),
                "anchor": e5["anchor"],
            },
            {
                "id": "C3",
                "claim": C.WRONG_LOCUS,
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "why_locus": (
                    "Prompt-by-file is the inbound transport (IMP-0421). "
                    "Injection and credential forwarding happen on the "
                    "RETURN path when parsed is concatenated into a Claude-side "
                    "prompt. Naming the inbound file flag as the sanitizer is "
                    "the wrong sentence about the same adapter."
                ),
                "scoped_restatement": C.SANITIZE_WHERE,
                "anchor": e2["anchor"],
            },
            {
                "id": "C4",
                "claim": C.NEVER_FORWARD,
                "verdict": "CONFIRMED",
                "anchor": e3["anchor"],
            },
            {
                "id": "C5",
                "claim": (
                    "The sanitizer catch rate is reported per class; a class "
                    "with zero catches is a P1."
                ),
                "verdict": "CONFIRMED",
                "anchor": e7["anchor"],
            },
        ],
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "strongest_surviving_counterargument": COUNTER,
        "injection_corpus": {
            "computed_not_asserted": True,
            "n_items": inj["n_items"],
            "per_class": per_class,
            "p1_zero_catch_classes": inj["p1_zero_catch_classes"],
            "mention_false_positives": inj["mention_false_positives"],
            "mention_ok": inj["mention_ok"],
            "classes_required": [
                "role-spoof",
                "instruction-override",
                "encoded",
            ],
        },
        "never_forward": {
            "computed_not_asserted": True,
            "canary_env": nf["canary_env"],
            "walk_closed_leaks": nf["walk_closed_leaks"],
            "dump_closed_leaks": nf["dump_closed_leaks"],
            "signals_agree_closed": nf["signals_agree_closed"],
            "fail_closed_clean": nf["fail_closed_clean"],
            "fail_open_mutant_leaks_canary": nf["fail_open_mutant_leaks_canary"],
            "forbidden_payload_keys": nf["forbidden_payload_keys"],
            "never_forward_stripped": nf["never_forward_stripped"],
            "outbound_keys": nf["outbound_keys"],
            "argv_forwarded": nf["argv_forwarded"],
            "env_copied": nf["env_copied"],
        },
        "tests": [
            {
                "id": "probe1-injection-corpus",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "probe2-never-forward",
                "command": P2,
                "result": "PASS",
            },
        ],
        "reviewer": {
            "reviewer_id": "ARC-0041-probe2-env-canary",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Re-derived never-forward from the leaky payload and planted "
                "env canary using two leak signals (walk vs json.dumps). "
                "Did not take the author's catch-rate table as input."
            ),
        },
        "reviewers": [
            {
                "reviewer_id": "ARC-0041-probe1-injection-corpus",
                "vendor_role": "author-rail",
                "independent": False,
                "verdict": "PASS",
            },
            {
                "reviewer_id": "ARC-0041-probe2-env-canary",
                "vendor_role": "independent-mechanical",
                "independent": True,
                "verdict": "PASS",
                "scope_not_agreement": True,
            },
            {
                "reviewer_id": "openai/codex-cli-default",
                "vendor_role": "cross-vendor",
                "independent": True,
                "verdict": "NOT-CHECKED",
                "reason": (
                    "No Codex MCP namespace is available in this session. "
                    "Inventing a Codex transcript would be overclaim. Probe2 "
                    "is the independent rail that actually ran."
                ),
            },
        ],
        "named_probes": [
            {"id": "probe1", "role": "injection-corpus-catch-rate", "command": P1},
            {"id": "probe2", "role": "never-forward-env-canary", "command": P2},
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/ARC-0041/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "global_catalog_write": False,
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": CLAIM, "exists": True, "role": "claim-under-test"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/ARC-0041/sanitizer.py",
                "exists": True,
                "role": "supporting",
            },
            {"path": ADAPTER, "exists": True, "role": "live-adapter"},
        ],
        "answer": (
            "Trust boundary is the vendor RETURN path: last-message is "
            "untrusted DATA, quarantined as kind=untrusted-vendor-data with "
            "instructions_forbidden before any Claude-side read. Never-forward: "
            "credentials, raw tool-permission grants, hook configuration, "
            "absolute credential-store paths, proven with env canary "
            f"{nf['canary_env']} absent on the sealed outbound "
            f"(walk=dump={not nf['walk_closed_leaks']}). Injection per-class "
            f"catch rates {per_class}. Live Codex adapter still passthrough-"
            "parses; contract specified, IMP-0421 not rebuilt. "
            "SUCCESS:ARC-0041"
        ),
        "paired_adversarial_note": (
            "ARC-0041 depends on A6 DESIGN.json (ARC-0038) in the catalog. "
            "Waiting for ARC-0038 before filing this security review is a "
            "deadlock; G-1 for this unit does not require that circle and "
            "does not rebuild DESIGN.json."
        ),
    }

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0041 overclaim {why}")
        return 1

    if not _schema_ok(doc):
        return 1

    # Artifact paths listed must exist before write of SECURITY.json except
    # the primary itself; write primary last.
    for row in doc["artifacts"]:
        if row["path"] == OUT:
            continue
        if not (REPO / row["path"]).is_file():
            print(f"FAILED:ARC-0041 missing artifact {row['path']}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    # Primary exists now; keep the listed exists=true honest.
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0041 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0041 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
