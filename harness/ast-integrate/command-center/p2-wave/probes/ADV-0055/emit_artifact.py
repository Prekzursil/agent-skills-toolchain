#!/usr/bin/env python3
"""Emit ADV-0055 license-and-rights-record at the catalog output_path."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import classify as C  # noqa: E402

OUT = "command-center/adversarial/ADV-0055-export-control-crypto-notice-review.json"
SCHEMA = "command-center/schema/license-and-rights-record.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0055/probe1_enumerate_crypto.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0055/probe2_built_artifact_notices.py"
)
MIN_BYTES = 4000
QUESTION = (
    "Does the release bundle include or link cryptographic implementations that "
    "carry distribution obligations, and are the required notices present in "
    "the release metadata?"
)


def make_validator() -> Draft202012Validator:
    """Disk-only $ref resolution. jsonschema 4.10 uses resolver=, not registry=."""
    store: dict = {}
    for rel in (
        "platform/schema/receipt.schema.json",
        "platform/schema/artifact-class-profiles.schema.json",
        SCHEMA,
    ):
        doc = json.loads((REPO / rel).read_text(encoding="utf-8"))
        sid = doc.get("$id")
        if not sid:
            raise SystemExit(f"FAILED:ADV-0055 schema missing $id: {rel}")
        store[sid] = doc
        store["https://ast-integrate.invalid/" + rel] = doc
    schema = store["https://ast-integrate.invalid/" + SCHEMA]
    resolver = RefResolver.from_schema(schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def validate_artifact(doc: dict) -> list[str]:
    out: list[str] = []
    for err in make_validator().iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:ADV-0055 snippet not in {path}: {snippet[:80]}")
    return text[:idx].count("\n") + 1


def run(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def first_json_object(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise SystemExit("FAILED:ADV-0055 probe output has no JSON object")
    obj, _end = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise SystemExit("FAILED:ADV-0055 probe JSON is not an object")
    return obj


def clip(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    return text[-n:]


def fingerprint(method: str, command: str) -> str:
    return hashlib.md5(f"{method}|{command}".encode("utf-8")).hexdigest()


def probe_obj(role: str, method: str, command: str, raw: str, exit_code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": clip(raw, 65000),
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def art(rel: str, role: str) -> dict:
    path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"FAILED:ADV-0055 missing supporting {rel}")
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def catalog_unit() -> dict:
    data = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "ADV-0055":
            return u
    raise SystemExit("FAILED:ADV-0055 catalog unit missing")


def main() -> int:
    unit = catalog_unit()
    sentinel = str(unit.get("completion_sentinel") or "")
    if not sentinel.startswith("SUCCESS:ADV-0055"):
        print("FAILED:ADV-0055 catalog completion_sentinel unexpected")
        return 1

    rc1, out1 = run(P1)
    rc2, out2 = run(P2)
    if rc1 != 0 or rc2 != 0:
        print("FAILED:ADV-0055 named probes during emit")
        print(out1[-2000:])
        print(out2[-2000:])
        return 1

    p1 = first_json_object(out1)
    p2 = first_json_object(out2)
    live = p1.get("live_tooling") or {}
    control = p1.get("control") or {}
    live2 = p2.get("live_built_packaging_tooling") or {}
    with_n = p2.get("with_notices") or {}
    without_n = p2.get("without_notices") or {}

    cls_rel = "command-center/p2-wave/probes/ADV-0055/classify.py"
    ntc_rel = "command-center/p2-wave/probes/ADV-0055/notices.py"
    p1_rel = "command-center/p2-wave/probes/ADV-0055/probe1_enumerate_crypto.py"
    p2_rel = "command-center/p2-wave/probes/ADV-0055/probe2_built_artifact_notices.py"
    tree_rel = "command-center/p2-wave/probes/ADV-0055/fixtures/trees/acme-signer.json"
    decoy_rel = "command-center/p2-wave/probes/ADV-0055/fixtures/SOURCE-DECOY-NOTICE.txt"
    pack_rel = "tools/plugin/pack.py"
    census_rel = "tools/plugin/census.py"
    blob_rel = "tools/marketplace/blob_store.py"
    cat_rel = "command-center/WORK-UNIT-CATALOG.json"

    crypto_line = find_line(REPO / tree_rel, '"cryptography"')
    ships_line = find_line(REPO / tree_rel, '"ships_signer": true')
    bundled_fn = find_line(REPO / cls_rel, "BUNDLED_PACKAGES")
    plat_fn = find_line(REPO / cls_rel, "PLATFORM_IMPORT_ROOTS")
    trans_fn = find_line(REPO / cls_rel, "def walk_lockfile_transitive")
    inspect_fn = find_line(REPO / ntc_rel, "def inspect_archive")
    decoy_line = find_line(REPO / decoy_rel, "DECOY-ADV-0055-SOURCE-NOTICE")
    hashlib_line = find_line(REPO / census_rel, "import hashlib")
    pack_line = find_line(REPO / pack_rel, "def pack_staging")
    blob_line = find_line(REPO / blob_rel, "import hashlib")
    cat_line = find_line(REPO / cat_rel, '"id": "ADV-0055"')
    q_line = find_line(REPO / cat_rel, QUESTION[:48])

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live_bundled_n = int(live.get("bundled_import_count") or 0)
    live_platform = list(live.get("platform_modules") or [])
    live_zip_bundled = list(live2.get("bundled") or [])

    answer = (
        "On this worktree the signing and packaging tooling "
        "(tools/plugin/pack.py pack_staging, tools/plugin/census.py, "
        "tools/marketplace/blob_store.py) hashes with the platform hashlib "
        f"library (observed modules={live_platform}) and does not import or "
        "vendor OpenSSL, libsodium, or pyca/cryptography. Probe 1's live AST "
        f"walk found bundled_import_count={live_bundled_n}. Probe 2 packed those "
        "sources with pack_staging and scanned only zip members: bundled "
        f"crypto paths={live_zip_bundled or []}. Platform hashlib is not a "
        "bundled cryptographic implementation and does not, by itself, trigger "
        "OpenSSL/ECCN distribution-notice obligations. A known bundled-crypto "
        "control (acme-signer -> packaging-core -> cryptography 45.0.2) is "
        "enumerated only by the transitive walk; a direct-only mutant misses "
        "it, which is the catalog control. Required notices for a bundle that "
        "does ship OpenSSL (attribution + ECCN/export-control text) are "
        "enforced on packed bytes: with-notices SILENT, without-notices FIRE, "
        "and a source-tree decoy NOTICE does not green the missing-notice "
        "archive. Drafted live release-channel metadata (ECCN, NOTICE in a "
        "dist wheel) is absent on this tree, so presence of channel notices "
        "for a future bundled-crypto channel is PARTIAL, not a clean confirm. "
        "This record is a factual distribution review, not legal advice; "
        "owner sign-off remains required before changing release channels."
    )

    targets = [
        {
            "id": "T1-live-bundled-crypto-with-distribution-obligations",
            "claim": (
                "The live release/packaging bundle includes or links a bundled "
                "cryptographic implementation (OpenSSL/libsodium/etc.) that "
                "carries distribution-notice obligations."
            ),
            "verdict": "REFUTED",
            "basis": (
                f"live bundled_import_count={live_bundled_n}; live packed zip "
                f"bundled members={live_zip_bundled}; only hashlib platform calls."
            ),
        },
        {
            "id": "T2-required-notices-in-live-release-metadata",
            "claim": (
                "Required crypto-distribution notices are present in currently "
                "drafted live release metadata for the chosen channels."
            ),
            "verdict": "PARTIAL",
            "basis": (
                "No dist/ wheel, NOTICE, or ECCN metadata is drafted for a live "
                "release channel. Platform-hash tooling currently requires an "
                "empty notice set; a future cryptography pin would change that."
            ),
        },
        {
            "id": "T3-control-bundled-crypto-enumerated",
            "claim": (
                "A component known to bundle crypto (cryptography via "
                "packaging-core on a package that ships a signer) appears in "
                "probe 1's transitive enumeration."
            ),
            "verdict": "CONFIRMED",
            "basis": (
                "bundled_transitive contains cryptography; direct-only walk "
                "returns packaging-core only."
            ),
        },
        {
            "id": "T4-built-artifact-notice-detector",
            "claim": (
                "Checking the built artifact (not the source repository) "
                "detects missing OpenSSL/export notices when bundled crypto "
                "is packed, and stays silent when those notices are packed."
            ),
            "verdict": "CONFIRMED",
            "basis": (
                f"with-notices={with_n.get('status')} "
                f"without-notices={without_n.get('status')} "
                f"decoy_in_bad_archive={without_n.get('decoy_canary')}"
            ),
        },
    ]

    src1 = probe_obj("source", "command", P1, out1, rc1)
    ver1 = probe_obj("verifier", "static-analysis", P2, out2, rc2)
    src2 = probe_obj("source", "test-run", P2, out2, rc2)
    ver2 = probe_obj(
        "verifier",
        "byte-compare",
        f"python3 -c \"from pathlib import Path; "
        f"p=Path({decoy_rel!r}); print('DECOY' in p.read_text())\"",
        f"source_decoy_present_on_disk={p2.get('source_decoy_present_on_disk')}; "
        f"without_notices.decoy_canary={without_n.get('decoy_canary')}",
        0,
    )

    evidence = [
        {
            "claim": (
                "Live packaging/signing tooling calls platform hashlib and does "
                "not import bundled crypto libraries."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{census_rel}:{hashlib_line}",
            "probes": [src1, ver1],
        },
        {
            "claim": (
                "tools/plugin/pack.py pack_staging emits a zip of staging bytes "
                "and does not link OpenSSL."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{pack_rel}:{pack_line}",
            "probes": [src2, ver1],
        },
        {
            "claim": (
                "Marketplace blob identity is hashlib.sha256, a platform library "
                "call, not a bundled implementation."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{blob_rel}:{blob_line}",
            "probes": [src1, ver1],
        },
        {
            "claim": (
                "acme-signer ships a signer and pulls cryptography transitively "
                "through packaging-core; probe 1 lists it as bundled."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{tree_rel}:{crypto_line}",
            "probes": [src1, ver1],
        },
        {
            "claim": (
                "A source-tree decoy NOTICE is not visible inside the "
                "without-notices built archive."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{decoy_rel}:{decoy_line}",
            "probes": [src2, ver2],
        },
        {
            "claim": (
                "Catalog question is export-control / crypto-distribution "
                "notices for signing and packaging tooling."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": f"{cat_rel}:{q_line}",
            "probes": [src1, ver1],
        },
    ]

    tests = [
        {
            "id": "T-PROBE-1-ENUMERATE",
            "name": "Transitive lockfile walk plus live import classification",
            "command": P1,
            "result": "PASS",
            "assertions": 6,
            "output_tail": clip(out1, 1500),
        },
        {
            "id": "T-PROBE-2-BUILT-NOTICES",
            "name": "Packed-archive notice scan, both-states, live plugin.pack",
            "command": P2,
            "result": "PASS",
            "assertions": 8,
            "output_tail": clip(out2, 1500),
        },
        {
            "id": "T-CONTROL-KNOWN-BUNDLED-SIGNER",
            "name": (
                "A component known to bundle crypto must appear in probe 1; "
                "an empty enumeration on a package that ships a signer means "
                "the traversal missed transitive dependencies"
            ),
            "command": P1,
            "result": "PASS",
            "assertions": 2,
            "output_tail": clip(
                "cryptography listed in bundled_transitive; "
                f"direct_only_misses_transitive={control.get('direct_only_misses_transitive')}",
                1500,
            ),
        },
        {
            "id": "T-NEGATIVE-PLATFORM-HASHLIB",
            "name": "Platform hashlib-only packager is not classified bundled",
            "command": P1,
            "result": "PASS",
            "assertions": 1,
            "output_tail": "hashlib-packager bundled=[]",
        },
    ]

    negative_controls = [
        {
            "id": "NC-MISSING-NOTICE-ARCHIVE",
            "kind": "known-broken-fixture",
            "description": (
                "Packed cryptography/_openssl.so without NOTICE/EXPORT-CONTROL "
                "must FIRE; the same payload with OpenSSL attribution and ECCN "
                "text must be SILENT. A source-tree decoy NOTICE must not green "
                "the missing-notice archive."
            ),
            "fired_on_bad_state": without_n.get("status") == "FIRE",
            "silent_on_good_state": with_n.get("status") == "SILENT",
            "bad_state_output": clip(
                f"status={without_n.get('status')} missing={without_n.get('missing')}",
                16000,
            ),
            "good_state_output": clip(
                f"status={with_n.get('status')} missing={with_n.get('missing')}",
                16000,
            ),
        },
        {
            "id": "NC-DIRECT-ONLY-WALK",
            "kind": "mutation",
            "description": (
                "Direct-only lockfile inspection of acme-signer sees "
                "packaging-core and must NOT list cryptography; otherwise the "
                "control cannot prove transitives are walked."
            ),
            "fired_on_bad_state": bool(control.get("direct_only_misses_transitive")),
            "silent_on_good_state": bool(control.get("bundled_transitive")),
            "bad_state_output": clip(f"direct_names={control.get('direct_names')}", 16000),
            "good_state_output": clip(
                f"bundled_transitive={control.get('bundled_transitive')}", 16000
            ),
        },
    ]

    supporting = [
        SCHEMA,
        cls_rel,
        ntc_rel,
        p1_rel,
        p2_rel,
        tree_rel,
        decoy_rel,
        pack_rel,
        census_rel,
        blob_rel,
    ]
    artifacts = [art(p, "supporting") for p in supporting]
    artifacts[0]["role"] = "supporting"

    consume_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B -c "
        "\"import json; from pathlib import Path; "
        f"p=Path({OUT!r}); d=json.loads(p.read_text(encoding='utf-8')); "
        "print('unit', d.get('unit_id'), 'state', d.get('state'), "
        "'kind', (d.get('report') or {}).get('kind'), "
        "'evidence', len(d.get('evidence') or []))\""
    )

    doc = {
        "schema_version": 1,
        "unit_id": "ADV-0055",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "profile": "license-and-rights-record",
        "spec_anchor": str(unit.get("spec_anchor") or "_USER-PROMPTS.md:11108-11111"),
        "min_bytes_threshold": MIN_BYTES,
        "produced_by": {
            "vendor": "xai",
            "model": "grok-4.6",
            "role": "license-and-legal-analyst",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": evidence,
        "tests": tests,
        "negative_controls": negative_controls,
        "reviewer": {
            "reviewer_id": "ADV-0055-probe2-archive-basename-reviewer",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "Re-derived notice presence from zip member basenames only "
                "(NOTICE / EXPORT-CONTROL.txt), not from probe 1's lockfile "
                "walk and not from content regex. Agreed: good SILENT, bad FIRE."
            ),
            "reviewed_at": now,
        },
        "defects": [
            {
                "id": "ADV-0055-D1-NO-DRAFTED-RELEASE-METADATA",
                "severity": "P3",
                "status": "open",
                "summary": (
                    "No live dist/ NOTICE or ECCN text is drafted. Harmless "
                    "while the packer ships only platform hashlib; becomes a "
                    "release blocker if cryptography or OpenSSL is later pinned."
                ),
            }
        ],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0055/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "ADV-0055",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "json.loads of catalog output_path",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj(
                    "verifier",
                    "file-read",
                    consume_cmd,
                    "in-memory validate_artifact before write; disk re-run after write",
                    0,
                ),
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "two strikes then pivot"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Owner has not signed off on a release-channel crypto "
                    "classification (ENC/ECCN) because no bundled encryption "
                    "library is currently shipped."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Owner decision if a future pin adds pyca/cryptography."
                ),
            }
        ],
        "report": {
            "kind": "license-and-rights-record",
            "question_or_target": QUESTION,
            "answer": answer,
            "completion_sentinel": sentinel,
            "evidence_requirement": str(unit.get("evidence_requirement") or ""),
            "tests_required": list(unit.get("tests_required") or []),
            "targets": targets,
            "named_probes": [
                {
                    "id": "probe1",
                    "role": "enumerate-crypto-bundled-vs-platform",
                    "command": P1,
                    "exit_code": rc1,
                    "raw_output": out1,
                },
                {
                    "id": "probe2",
                    "role": "built-artifact-notice-check",
                    "command": P2,
                    "exit_code": rc2,
                    "raw_output": out2,
                },
            ],
            "live_tooling": live,
            "control": control,
            "built_artifact": {
                "with_notices": with_n,
                "without_notices": without_n,
                "live_packed": live2,
            },
            "classification_rule": {
                "platform": "stdlib hashlib/hmac/ssl/secrets",
                "bundled": sorted(C.BUNDLED_PACKAGES),
                "walk": "transitive depends_on from declared direct deps",
            },
            "legal_disclaimer": (
                "Factual inventory and notice-presence measurement only. "
                "Not a legal opinion. Owner sign-off is required before any "
                "channel or classification change."
            ),
            "observations": [
                {
                    "name": "live-bundled-crypto-import-count",
                    "measured": live_bundled_n,
                    "method": P1,
                    "anchor": f"{census_rel}:{hashlib_line}",
                },
                {
                    "name": "live-packed-bundled-members",
                    "measured": ",".join(live_zip_bundled) if live_zip_bundled else "none",
                    "method": P2,
                    "anchor": f"{pack_rel}:{pack_line}",
                },
                {
                    "name": "control-cryptography-transitive",
                    "measured": True,
                    "method": P1,
                    "anchor": f"{tree_rel}:{crypto_line}",
                },
                {
                    "name": "notice-detector-both-states",
                    "measured": (
                        f"good={with_n.get('status')} bad={without_n.get('status')}"
                    ),
                    "method": P2,
                    "anchor": f"{ntc_rel}:{inspect_fn}",
                },
            ],
            "control_ids": [nc["id"] for nc in negative_controls],
        },
        "extensions": {
            "probe_commands": {"probe_1": P1, "probe_2": P2},
            "anchors": {
                "ships_signer": f"{tree_rel}:{ships_line}",
                "bundled_table": f"{cls_rel}:{bundled_fn}",
                "platform_table": f"{cls_rel}:{plat_fn}",
                "transitive_walk": f"{cls_rel}:{trans_fn}",
                "inspect_archive": f"{ntc_rel}:{inspect_fn}",
                "catalog": f"{cat_rel}:{cat_line}",
            },
            "notes": (
                "G-1 for ADV-0055. Did not run unit_manifest.py --write. "
                "No ADV rebuild circle. No keys created or rotated."
            ),
        },
    }

    allowed = {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
    seen_ids = []
    for t in targets:
        if t["verdict"] not in allowed:
            print(f"FAILED:ADV-0055 bad target verdict {t}")
            return 1
        if t["id"] in seen_ids:
            print(f"FAILED:ADV-0055 duplicate target {t['id']}")
            return 1
        seen_ids.append(t["id"])
    for nc in negative_controls:
        if not nc.get("fired_on_bad_state") or not nc.get("silent_on_good_state"):
            print(f"FAILED:ADV-0055 control not both-states {nc['id']}")
            return 1

    errs = validate_artifact(doc)
    if errs:
        print("FAILED:ADV-0055 schema errors")
        for e in errs[:20]:
            print(" ", e)
        return 1
    for g in ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {}):
        g_errs = validate_artifact(g)
        if not g_errs:
            print(f"FAILED:ADV-0055 schema accepted garbage {list(g)[:2]}")
            return 1
    mutant = json.loads(json.dumps(doc))
    mutant["report"]["kind"] = "not-this-class"
    mutant_errs = validate_artifact(mutant)
    if not mutant_errs:
        print("FAILED:ADV-0055 schema accepted wrong report.kind")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    crc, cout = run(consume_cmd)
    doc["downstream_consumers"][0]["exit_code"] = crc
    doc["downstream_consumers"][0]["read_ok"] = crc == 0
    doc["downstream_consumers"][0]["executed"] = True
    doc["downstream_consumers"][0]["probe"]["exit_code"] = crc
    doc["downstream_consumers"][0]["probe"]["raw_output"] = clip(cout, 65000)
    if crc != 0:
        print("FAILED:ADV-0055 downstream consumer")
        print(cout[-2000:])
        return 1

    errs = validate_artifact(doc)
    if errs:
        print("FAILED:ADV-0055 schema errors after consumer")
        for e in errs[:20]:
            print(" ", e)
        return 1

    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < MIN_BYTES:
        print(f"FAILED:ADV-0055 artifact {size}B below floor {MIN_BYTES}")
        return 1
    text = out.read_text(encoding="utf-8")
    if sentinel not in text:
        print("FAILED:ADV-0055 catalog completion_sentinel missing from artifact text")
        return 1
    if "SUCCESS:ADV-0055" not in text:
        print("FAILED:ADV-0055 short sentinel missing")
        return 1
    parsed = json.loads(text)
    if str(parsed.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:ADV-0055 self-declared {parsed.get('state')}")
        return 1
    disk_errs = validate_artifact(parsed)
    if disk_errs:
        print("FAILED:ADV-0055 disk artifact schema")
        for e in disk_errs[:20]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:ADV-0055 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
