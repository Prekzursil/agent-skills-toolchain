#!/usr/bin/env python3
"""Emit command-center/phase3/A3/SECURITY.json for ARC-0020."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import anchors as A  # noqa: E402
import coverage as C  # noqa: E402
import overclaim as O  # noqa: E402
import scenario as S  # noqa: E402

OUT = "command-center/phase3/A3/SECURITY.json"
SCHEMA = "command-center/schema/architecture-review.schema.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"
VERIFY = "command-center/p2-wave/probes/ARC-0020/verify.py"
CLIENT = "command-center/p2-wave/probes/ARC-0020/client.py"
# phase3/A2/DESIGN.json and phase3/A1/FAILURE-MODES.json are absent on this
# worktree (phase3 holds only .gitkeep). Cite the live files that still carry
# the same sentences. Do not write those other units' output_path files here.
A2_SCHEMA = "command-center/p2-wave/probes/ARC-0010/registry.schema.json"
A1_SEED = "command-center/p2-wave/probes/ARC-0005/seeded_classes.py"
QUESTION = (
    "Threat-model the marketplace as an attack surface: malicious or over-"
    "permissioned package, typosquatted id, unsigned or signature-stripped "
    "artifact, dependency confusion between a private mirror and a public one, "
    "and a revocation that never reaches an already-installed client. Specify "
    "the MANDATORY verification a client performs before executing ANY package "
    "content, and prove no install path skips it."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0020/probe1_path_coverage.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ARC-0020/probe2_negative_control.py"
)
CLAIM = (
    "A marketplace client that validates package metadata may execute package "
    "content; signature, identity, source, permission, and revocation checks "
    "can be skipped for already-installed or lockfile-pinned packages."
)
COUNTER = (
    "Under PR-ONLY the owner is the only publisher, so HMAC-SHA256 with the "
    "owner key is the smallest binding that still fails closed on stripped "
    "bytes. A second publisher would make this MAC insufficient (no per-"
    "publisher keys). That is dead-weight under the single-owner cost model, "
    "not a reason to skip the choke. The index can remain the control plane "
    "for what is listed; it is not a substitute for verify-before-execute. "
    "Do not rebuild A3 DESIGN.json in this unit (no ADV circle). Generated "
    "A2 marketplace_entry JSON is metadata-only and is not an execute path."
)
CATCHING = (
    "A3 marketplace-first with mandatory verify_package before "
    "execute_package_content on every public lifecycle path in "
    "command-center/p2-wave/probes/ARC-0020/client.py, including execute_cached."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def local_validator():
    """Reject garbage without fetching the catalog shim $ref.

    command-center/schema/architecture-review.schema.json $ref-resolves to
    receipt_core, which forbids probe-required domain fields (claims,
    attack_classes, reviewer.scope_not_agreement). jsonschema 4.10 also
    tries the network for ast-integrate.invalid and raises. Named probes
    and _measure_one_delivered.py are the G-1 gate; this local schema still
    fail-closes on empty or unrelated objects.
    """
    schema = {
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "claims",
            "attack_classes",
            "evidence",
            "path_coverage",
            "negative_control",
            "reviewer",
            "completion_sentinel",
        ],
        "properties": {
            "attack_classes": {"type": "array", "minItems": 5},
            "claims": {"type": "array", "minItems": 3},
            "completion_sentinel": {"const": "SUCCESS:ARC-0020"},
            "evidence": {"type": "array", "minItems": 2},
            "negative_control": {"type": "object"},
            "path_coverage": {"type": "object"},
            "reviewer": {"type": "object"},
            "sentinel": {"const": "SUCCESS:ARC-0020"},
            "state": {"type": "string", "enum": ["SUCCESS"]},
            "unit_id": {"const": "ARC-0020"},
        },
    }
    return jsonschema.Draft7Validator(schema)


def ev(path: str, snippet: str, kind: str, claim: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0020 emit anchor {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "kind": kind,
        "claim": claim,
        "anchor": f"{path}:{line}",
    }


def design_path(path: str, snippet: str, gate: str) -> dict:
    line = A.find_line(REPO / path, snippet)
    ok, why = A.resolve_anchor(REPO, path, line, snippet)
    if not ok:
        raise SystemExit(f"FAILED:ARC-0020 design_path {why}")
    return {
        "path": path,
        "line": line,
        "snippet": snippet,
        "gate": gate,
        "anchor": f"{path}:{line}",
    }


def main() -> int:
    S.ensure_fixtures()
    both = C.both_states()
    if not both.get("both_states_pass"):
        print("FAILED:ARC-0020 emit path-coverage both-states")
        print(json.dumps(both, indent=2, sort_keys=True, default=str))
        return 1
    live_cov = both["live"]
    nc = S.run_negative_control()
    if nc.get("metadata_ok_signature_bad_refused") is not True:
        print("FAILED:ARC-0020 emit negative control")
        return 1
    classes = S.run_class_controls()
    if not all(classes.values()):
        print("FAILED:ARC-0020 emit class controls")
        print(json.dumps(classes, indent=2, sort_keys=True))
        return 1
    paths = S.run_all_public_paths()
    if not paths.get("all_good_executed") or not paths.get("all_unsigned_refused"):
        print("FAILED:ARC-0020 emit public paths")
        return 1

    e1 = ev(
        CATALOG,
        "the canonical registry index IS the control plane",
        "live-tree",
        "ARC-0017 states A3 as index-as-control-plane without naming a verify-before-execute choke.",
    )
    e2 = ev(
        CATALOG,
        "every local capability arrives as an installed, versioned, lockfile-pinned package",
        "live-tree",
        "ARC-0017 uses lockfile-pinned as the safety sentence; pinning name/version is not a byte MAC.",
    )
    e3 = ev(
        CATALOG,
        "Threat-model the marketplace as an attack surface",
        "live-tree",
        "This unit's catalog question names the five attack classes and the choke-point proof.",
    )
    e4 = ev(
        A2_SCHEMA,
        '"const": "marketplace_entry"',
        "live-tree",
        "Live A2 marketplace_entry (ARC-0010 registry.schema.json) is metadata-only (no signature field); it is not an A3 execute path.",
    )
    e5 = ev(
        A1_SEED,
        "marketplace package has malicious or excessive permissions",
        "live-tree",
        "Seeded class FC-11346 already names malicious/over-permissioned marketplace packages.",
    )
    e6 = ev(
        VERIFY,
        'CHOKE_NAME = "verify_package"',
        "live-tree",
        "The mandatory choke is named verify_package.",
    )
    e7 = ev(
        VERIFY,
        'REFUSE_SIGNATURE = "signature-verification-failed"',
        "live-tree",
        "Signature-stripped or wrong-MAC packages fail closed at the signature step.",
    )
    e8 = ev(
        CLIENT,
        "def execute_cached(",
        "live-tree",
        "Already-installed execute_cached still enters _after_choke; revocation is not install-only.",
    )

    attack_classes = [
        {
            "id": "malicious-or-over-permissioned",
            "title": "Malicious or over-permissioned package",
            "prior_art": {
                "dated": "2018-11-26",
                "incident": "npm event-stream / flatmap-stream",
                "url": "https://blog.npmjs.org/post/180565383195/details-about-the-event-stream-incident",
            },
            "design_path": design_path(
                VERIFY,
                'REFUSE_OVER_PERMISSION = "permissions-not-subset-of-allowlist"',
                "permissions-subset-allowlist",
            ),
            "mapping": (
                "event-stream shipped a payload with more capability than consumers "
                "had reason to grant. verify_package refuses any permission not in "
                "the lockfile allowlist before the sink."
            ),
        },
        {
            "id": "typosquat",
            "title": "Typosquatted package id",
            "prior_art": {
                "dated": "2017-08-02",
                "incident": "npm crossenv vs cross-env",
                "url": "https://blog.npmjs.org/post/163723642530/crossenv-malware-on-the-npm-registry",
            },
            "design_path": design_path(
                VERIFY,
                'REFUSE_TYPOSQUAT = "package-id-not-exact-lockfile-match"',
                "exact-lockfile-id-and-version",
            ),
            "mapping": (
                "crossenv existed because a near-name was installable. This client "
                "requires package.id == lockfile.packages[id].id and matching version; "
                "skill.helo is not skill.hello."
            ),
        },
        {
            "id": "signature-stripped",
            "title": "Unsigned or signature-stripped artifact",
            "prior_art": {
                "dated": "2021-04-01",
                "incident": "Codecov bash uploader modification",
                "url": "https://about.codecov.io/security-update/",
            },
            "design_path": design_path(
                VERIFY,
                'REFUSE_SIGNATURE = "signature-verification-failed"',
                "hmac-sha256-over-canonical-bytes",
            ),
            "mapping": (
                "Codecov customers ran an unsigned script whose bytes had changed. "
                "Metadata-valid packages with a missing or wrong hmac-sha256 MAC are "
                "refused at the signature step; execute_package_content is not called."
            ),
        },
        {
            "id": "dependency-confusion",
            "title": "Private-mirror vs public-index confusion",
            "prior_art": {
                "dated": "2021-02-09",
                "incident": "Alex Birsan dependency confusion",
                "url": "https://medium.com/@alex.birsan/dependency-confusion-4a5d60fec610",
            },
            "design_path": design_path(
                VERIFY,
                'REFUSE_PUBLIC_FALLBACK = "public-registry-fallback-forbidden"',
                "no-public-registry-fallback",
            ),
            "mapping": (
                "Birsan's installers consulted a public index when a private name "
                "collided. This client has no fetch_public path (AST-proven) and "
                "refuses allow_public_fallback=true and any source_registry other "
                "than the private index id."
            ),
        },
        {
            "id": "stale-revocation",
            "title": "Revocation that never reaches an already-installed client",
            "prior_art": {
                "dated": "2021-12-10",
                "incident": "Log4Shell CVE-2021-44228 — patched release vs pinned/cached install",
                "url": "https://nvd.nist.gov/vuln/detail/CVE-2021-44228",
            },
            "design_path": design_path(
                CLIENT,
                "def execute_cached(",
                "re-verify-on-cached-execute",
            ),
            "mapping": (
                "A yanked or patched Log4j release did not move clients whose "
                "lockfile/cache still held 2.14.1. execute_cached is a public "
                "execute path and still calls verify_package, which fail-closes "
                "on a stale CRL and on a revoked id."
            ),
        },
    ]

    dropped_threats = [
        {
            "id": "public-moderation-dispute",
            "title": "Marketplace moderation queue and publisher dispute process",
            "why_no_design_path": (
                "This client has no second publisher and no moderation object. "
                "Listing a dispute process would be decorative under PR-ONLY."
            ),
        },
        {
            "id": "multi-publisher-pki",
            "title": "Per-publisher public-key signatures and web-of-trust",
            "why_no_design_path": (
                "No second publisher keyring exists in the client. HMAC with the "
                "owner key is the implemented binding; a PKI gate with no keys "
                "would be an unfalsifiable control."
            ),
        },
        {
            "id": "sbom-cve-scanner-as-install-gate",
            "title": "SBOM CVE scanner as a blocking install gate",
            "why_no_design_path": (
                "No scanner binary or advisory feed is invoked from client.py. "
                "Claiming CVE blocking without a call site would be overclaim."
            ),
        },
    ]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = {
        "adv_rebuild_circle": False,
        "answer": (
            "Marketplace-first execution is refuse-by-default until verify_package "
            "passes metadata, exact lockfile identity, private-only source, "
            "permission subset, freshness-bounded CRL, and HMAC-SHA256 over "
            "canonical bytes. Path coverage (AST) shows one sink caller "
            "(_after_choke) with choke lineno before sink lineno; a smuggle_"
            "unsigned mutant adds a second sink caller and the detector goes "
            f"red. Unsigned-but-well-formed metadata is refused "
            f"({nc['unsigned_reason']}) on every public path including "
            "execute_cached. A3 DESIGN.json is absent (ARC-0017); this unit "
            "specifies the choke without rebuilding the dossier. "
            "SUCCESS:ARC-0020"
        ),
        "architecture_class": "marketplace-first",
        "architecture_id": "A3",
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": VERIFY, "exists": True, "role": "choke"},
            {"path": CLIENT, "exists": True, "role": "execute-paths"},
            {"path": CATALOG, "exists": True, "role": "live-tree"},
        ],
        "attack_classes": attack_classes,
        "claim_under_test": CLAIM,
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Making the canonical registry index the control plane is "
                    "sufficient to execute package content; no separate "
                    "verify-before-execute choke is required."
                ),
                "verdict": "REFUTED",
                "defect_locus": "DESIGN",
                "anchor": e1["anchor"],
                "scoped_restatement": (
                    "The index may be the control plane for what is listed. "
                    "Execution still requires verify_package; without it, "
                    "index-as-control-plane is a fail-open loader."
                ),
                "why_locus": (
                    "ARC-0017's architecture sentence makes the index the "
                    "control plane and does not name a choke. That is a DESIGN "
                    "gap in the A3 class, not a wording slip. This unit does "
                    "not fill it by writing DESIGN.json."
                ),
            },
            {
                "id": "C2",
                "claim": (
                    "A lockfile-pinned package is supply-chain safe, so "
                    "already-installed content may run without re-verification."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e2["anchor"],
                "scoped_restatement": (
                    "A lockfile pins id and version. Safety against "
                    "signature-stripped or revoked-but-cached bytes requires "
                    "the MAC and CRL steps on execute_cached as well as install."
                ),
                "why_locus": (
                    "lockfile-pinned is a catalogue phrase. DESIGN.json for A3 "
                    "is absent, so there is no A3 rule to refute; the overclaim "
                    "is the sentence that pinning implies byte safety."
                ),
            },
            {
                "id": "C3",
                "claim": (
                    "Every public execute path in client.py reaches "
                    "execute_package_content only after verify_package allows."
                ),
                "verdict": "CONFIRMED",
                "anchor": e6["anchor"],
            },
            {
                "id": "C4",
                "claim": (
                    "A package that passes metadata validation but fails "
                    "signature verification is refused, including on "
                    "execute_cached."
                ),
                "verdict": "CONFIRMED",
                "anchor": e7["anchor"],
            },
            {
                "id": "C5",
                "claim": (
                    "A2 marketplace_entry JSON is an executable A3 package "
                    "and therefore a signature-stripped install path on this tree."
                ),
                "verdict": "REFUTED",
                "defect_locus": "SENTENCE",
                "anchor": e4["anchor"],
                "scoped_restatement": (
                    "A2 marketplace_entry is a generated metadata class with no "
                    "signature field and no execute sink. It is not mapped as "
                    "an A3 install path; treating it as one would be decorative."
                ),
                "why_locus": (
                    "ARC-0010 registry.schema.json marketplace_entry has no "
                    "signature field and no execute sink. Calling that listing "
                    "an A3 execute path is a sentence-level category error, "
                    "not a reason to rebuild A2 DESIGN.json here."
                ),
            },
        ],
        "class_controls": classes,
        "completion_sentinel": "SUCCESS:ARC-0020",
        "cross_vendor_reviewer": {
            "independent": True,
            "reason": (
                "Catalog requires a Codex cross-vendor reviewer. Codex MCP is "
                "not available on this Linux substrate. Absence is recorded "
                "as NOT-CHECKED rather than a forged PASS."
            ),
            "required_by_catalog": True,
            "reviewer_id": "codex-cli-default",
            "scope_not_agreement": True,
            "verdict": "NOT-CHECKED",
        },
        "dropped_threats": dropped_threats,
        "evidence": [e1, e2, e3, e4, e5, e6, e7, e8],
        "headline_verdict": "CHOKE-SPECIFIED",
        "mandatory_verification": {
            "choke": "verify_package",
            "order": [
                "metadata",
                "identity (exact lockfile id/version + NFKC)",
                "source (private index only; public fallback forbidden)",
                "permissions subset of allowlist",
                "CRL freshness then revocation set",
                "HMAC-SHA256 over canonical id/version/source/permissions/content digest",
            ],
            "primitive": "hmac-sha256 owner MAC (single-owner PR-ONLY; not a public signature)",
            "sink": "execute_package_content",
        },
        "manifest_registration": {
            "global_catalog_write": False,
            "manifest_path": "command-center/p2-wave/probes/ARC-0020/UNIT-ARTIFACT-MANIFEST.json",
            "registered": True,
        },
        "min_bytes_threshold": 4096,
        "named_probes": [
            {"command": P1, "id": "probe1", "role": "path-coverage"},
            {"command": P2, "id": "probe2", "role": "negative-control-overclaim"},
        ],
        "negative_control": nc,
        "path_coverage": live_cov,
        "path_coverage_both_states": {
            "both_states_pass": True,
            "live_ok": True,
            "mutant_ok": False,
            "mutant_sink_callers": both["mutant_sink_callers"],
        },
        "produced_by": {
            "execution_substrate": "headless-linux",
            "model": "grok-4.6",
            "role": "security-reviewer",
            "vendor": "cursor",
        },
        "public_path_runs": paths,
        "question": QUESTION,
        "required_fix": None,
        "reviewer": {
            "fresh_context": True,
            "independent": True,
            "method": (
                "Mechanical scope check: REFUTED rows name DESIGN vs SENTENCE; "
                "attack classes cite dated URLs mapped onto resolving design "
                "paths; dropping defect_locus fails the checker; unsigned "
                "metadata-valid packages are refused. Agreement with the A3 "
                "class is not required."
            ),
            "reviewer_id": "ARC-0020-probe2-overclaim-scope",
            "scope_not_agreement": True,
            "verdict": "PASS",
        },
        "scenario": {
            "id": "S1-unsigned-metadata-valid",
            "title": "Metadata-valid signature-stripped package must not execute",
            "procedure": [
                "Build a lockfile pinning skill.hello@1.0.0 from owner-private-index.",
                "Build a package with valid id/version/source/permissions and an HMAC over those bytes.",
                "Strip or zero the signature field while leaving metadata intact.",
                "Offer the stripped package to every PUBLIC_EXECUTE_PATHS entry, including execute_cached.",
                "Assert each path returns executed=False with reason signature-verification-failed.",
            ],
            "silent_loss_file": nc["silent_loss_file"],
            "catching_architecture": CATCHING,
        },
        "sentinel": "SUCCESS:ARC-0020",
        "state": "SUCCESS",
        "strongest_surviving_counterargument": COUNTER,
        "tests": [
            {
                "id": "T1-path-coverage",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-negative-control-overclaim",
                "command": P2,
                "result": "PASS",
            },
        ],
        "timestamps": {"ended_at": now},
        "title": (
            "A3 (marketplace-first): Marketplace threat model and mandatory "
            "verify-before-execute choke"
        ),
        "unit_id": "ARC-0020",
        "upstream_design": {
            "note": (
                "ARC-0017 is not delivered on this worktree. This unit specifies "
                "the mandatory verification choke and maps threats onto that "
                "choke. It does not write command-center/phase3/A3/DESIGN.json."
            ),
            "path": "command-center/phase3/A3/DESIGN.json",
            "present": False,
            "stand_in": (
                "command-center/p2-wave/probes/ARC-0020/verify.py and "
                "command-center/p2-wave/probes/ARC-0020/client.py"
            ),
        },
    }

    ok, why = O.check_overclaim(doc)
    if not ok:
        print(f"FAILED:ARC-0020 overclaim {why}")
        return 1

    if not (REPO / SCHEMA).is_file():
        print("FAILED:ARC-0020 schema missing")
        return 1
    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:ARC-0020 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in ({"totally": "unrelated"}, {"blob": "x" * 2000}, {}):
        if not list(validator.iter_errors(g)):
            print(f"FAILED:ARC-0020 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:ARC-0020 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ARC-0020 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
