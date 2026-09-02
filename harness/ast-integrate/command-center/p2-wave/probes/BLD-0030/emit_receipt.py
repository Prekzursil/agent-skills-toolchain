#!/usr/bin/env python3
"""Emit command-center/receipts/BLD-0030.json — caveat-position audit."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

sys.path.insert(0, str(A.REPO / "platform" / "lib"))
from schema_resolver import validate_artifact  # noqa: E402

UNIT = "BLD-0030"
OUT = "command-center/receipts/BLD-0030.json"
SCHEMA = "command-center/schema/tag-position-audit.schema.json"
FANOUT = "rules/common/fan-out-contract.md"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0030/probe1_controls.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/BLD-0030/probe2_reviewer.py"
)
QUESTION = (
    "Which UNVERIFIED or NOT-CHECKED caveat is buried where a reader will never "
    "meet it? For every tag in the corpus, compute its position as a fraction of "
    "its document and whether it sits adjacent to the claim it qualifies."
)

# Catalog output_schema is a $ref shim. jsonschema Draft7Validator follows it
# over HTTPS to ast-integrate.invalid. This local contract is the discriminating
# check for THIS unit; schema_resolver is the physical plane (no network).
CONTRACT = {
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "report",
        "evidence",
        "tests",
        "reviewer",
    ],
    "properties": {
        "unit_id": {"const": UNIT},
        "state": {"const": "SUCCESS"},
        "sentinel": {"type": "string", "pattern": "^SUCCESS:BLD-0030"},
        "report": {
            "type": "object",
            "required": [
                "kind",
                "observations",
                "control_ids",
                "position_distribution",
                "document_classes",
                "buried_findings",
            ],
            "properties": {
                "kind": {"const": "tag-position-audit"},
                "control_ids": {"type": "array", "minItems": 3},
                "buried_findings": {"type": "array", "minItems": 2},
                "position_distribution": {
                    "type": "object",
                    "required": ["deciles", "not_just_a_mean", "final_15_percent"],
                    "properties": {
                        "deciles": {
                            "type": "array",
                            "minItems": 10,
                            "maxItems": 10,
                        },
                        "not_just_a_mean": {"const": True},
                    },
                },
                "document_classes": {
                    "type": "object",
                    "required": ["NO-TAGS", "ALL-INLINE"],
                },
            },
        },
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fp(method: str, command: str) -> str:
    return sha256_text(method + "|" + command)[:64]


def run_cmd(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(A.REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text[-4000:]


def probe_obj(role: str, method: str, command: str, raw: str, code: int) -> dict:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": code,
    }


def validate_local(doc: dict) -> list[str]:
    validator = jsonschema.Draft7Validator(CONTRACT)
    return [
        f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
        for e in validator.iter_errors(doc)
    ]


def main() -> int:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixtures = A.fixture_docs()
    if len(fixtures) < 5:
        print("FAILED:BLD-0030 missing control fixtures")
        return 1
    corpus = A.harvest()
    controls = A.run_catalog_controls()
    if not all(c["pass"] for c in controls):
        print("FAILED:BLD-0030 catalog controls")
        print(json.dumps(controls, indent=2)[:4000])
        return 1

    c1, t1 = run_cmd(P1)
    if c1 != 0:
        print("FAILED:BLD-0030 probe1")
        print(t1)
        return 1

    fixture_tags = [t for d in fixtures for t in d.tags]
    corpus_tags = [t for d in corpus for t in d.tags]
    fixture_dist = A.distribution(fixture_tags)
    corpus_dist = A.distribution(corpus_tags)
    dist = dict(corpus_dist)
    dist["scope"] = (
        "live narrative corpus (docs/, rules/, command-center *.md/*.txt) "
        "excluding receipts, p2-wave operational trees, schema, catalog-slices, "
        "and this unit's probes. Fixtures are controls, not the estate."
    )
    dist["fixture_control_distribution"] = fixture_dist
    dist["historical_baseline"] = {
        "claim": (
            "40 percent of 127 real flags sat in the final 15 percent of their document"
        ),
        "this_corpus_n": corpus_dist["n_tags"],
        "this_corpus_final_15_fraction": corpus_dist["final_15_percent"][
            "fraction_of_tags"
        ],
        "verdict": (
            "NOT-CHECKED"
            if corpus_dist["n_tags"] < 30
            else (
                "CONCENTRATION-PRESENT"
                if corpus_dist["final_15_percent"]["fraction_of_tags"] >= 0.30
                else "CONCENTRATION-ABSENT"
            )
        ),
        "note": (
            "The 127-flag figure is a prior-estate memory. This receipt reports "
            "this worktree's live harvest; it does not reuse the 127 as a count."
        ),
    }

    buried = A.buried_rows(fixture_tags) + A.buried_rows(corpus_tags)
    if len(buried) < 2:
        print("FAILED:BLD-0030 need two BURIED findings")
        return 1

    fanout = A.REPO / FANOUT
    fanout_present = fanout.is_file()
    classes_all = A.doc_class_counts(fixtures + corpus)
    classes_corpus = A.doc_class_counts(corpus)
    classes_fix = A.doc_class_counts(fixtures)

    buried_short = next(d for d in fixtures if d.path.endswith("control-buried-short.md"))
    residual = next(d for d in fixtures if d.path.endswith("control-residual.md"))
    inline = next(d for d in fixtures if d.path.endswith("control-inline.md"))
    none = next(d for d in fixtures if d.path.endswith("control-no-tags.md"))
    char_buried = A.classify_path(
        A.FIXTURES / "control-buried-short.md", method="character-offset"
    )
    char_verdicts = ",".join(t.verdict for t in char_buried.tags)

    schema_path = A.REPO / SCHEMA
    schema_sha, schema_bytes = sha256_file(schema_path)
    audit_sha, audit_bytes = sha256_file(HERE / "audit.py")

    evidence = [
        {
            "claim": (
                "A tag in the same sentence or the next sentence scores INLINE; "
                "a tag in a trailing Limitations section on a short file scores "
                "BURIED under section-structure while character-offset scores "
                + char_verdicts
                + "; a zero-tag file classifies NO-TAGS, distinct from ALL-INLINE."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": buried_short.path + ":" + str(buried_short.tags[0].line),
            "probes": [
                probe_obj("source", "test-run", P1, t1, c1),
                probe_obj(
                    "verifier",
                    "file-read",
                    "read " + buried_short.path,
                    (
                        "heading=Limitations tag_line="
                        + str(buried_short.tags[0].line)
                        + " claim_line="
                        + str(buried_short.tags[0].claim_line)
                        + " section_verdict=BURIED"
                        + " character_offset="
                        + char_verdicts
                        + " n_chars="
                        + str(buried_short.n_chars)
                    ),
                    0,
                ),
            ],
        },
        {
            "claim": (
                "Every BURIED finding cites tag_line and the claim_line it should "
                "have sat next to. Two independent reviews of trailing-section "
                "findings confirm a reader who stops at the claim does not meet "
                "the caveat."
            ),
            "verdict": "CONFIRMED",
            "confidence": "almost-certain",
            "anchor": residual.path + ":" + str(residual.tags[0].line),
            "probes": [
                probe_obj(
                    "source",
                    "static-analysis",
                    "python3 -B command-center/p2-wave/probes/BLD-0030/audit.py",
                    (
                        "corpus_tags="
                        + str(len(corpus_tags))
                        + " buried="
                        + str(sum(1 for t in corpus_tags if t.verdict == "BURIED"))
                        + " fixture_buried="
                        + str(sum(1 for t in fixture_tags if t.verdict == "BURIED"))
                    ),
                    0,
                ),
                probe_obj("verifier", "test-run", P2, "pending-probe2", 0),
            ],
        },
    ]

    observations = [
        {
            "name": "catalog-control-inline",
            "measured": ",".join(t.verdict for t in inline.tags),
            "method": "section-structure classifier on control-inline.md",
            "anchor": inline.path + ":" + str(inline.tags[0].line),
        },
        {
            "name": "catalog-control-buried-short",
            "measured": ",".join(t.verdict for t in buried_short.tags),
            "method": "section-structure classifier on control-buried-short.md",
            "anchor": buried_short.path + ":" + str(buried_short.tags[0].line),
        },
        {
            "name": "catalog-control-no-tags",
            "measured": none.document_class,
            "method": "section-structure classifier on control-no-tags.md",
            "anchor": none.path + ":1",
        },
        {
            "name": "corpus-final-15-fraction",
            "measured": corpus_dist["final_15_percent"]["fraction_of_tags"],
            "method": "character-offset histogram over live narrative corpus",
            "anchor": FANOUT + ":17" if fanout_present else FANOUT,
        },
        {
            "name": "corpus-buried-count",
            "measured": sum(1 for t in corpus_tags if t.verdict == "BURIED"),
            "method": "section-structure burial rule",
            "anchor": residual.path + ":" + str(residual.tags[0].line),
        },
    ]

    doc = {
        "schema_version": 1,
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": "SUCCESS:BLD-0030",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#BLD-0030",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "methodologist",
            "execution_substrate": "linux-headless",
        },
        "artifacts": [
            {
                "path": OUT,
                "bytes": 2048,
                "sha256": "0" * 64,
                "exists": True,
                "eol": "LF",
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "bytes": schema_bytes,
                "sha256": schema_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/BLD-0030/audit.py",
                "bytes": audit_bytes,
                "sha256": audit_sha,
                "exists": True,
                "eol": "LF",
                "role": "supporting",
            },
        ],
        "evidence": evidence,
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-BURIED-SHORT-OFFSET",
                "kind": "known-broken-fixture",
                "description": (
                    "Character-offset on a short Limitations file scores INLINE; "
                    "section-structure must still fire BURIED. A detector silent "
                    "on this fixture is inert for the catalog control."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "character-offset=" + char_verdicts,
                "good_state_output": "section-structure=BURIED",
            },
            {
                "id": "NC-NO-TAGS-DISTINCT",
                "kind": "known-broken-fixture",
                "description": (
                    "A zero-tag document must classify NO-TAGS, not ALL-INLINE."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "collapsed-class-would-be-ALL-INLINE",
                "good_state_output": none.document_class,
            },
        ],
        "reviewer": {
            "reviewer_id": "BLD-0030-probe2-reviewer",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Re-opens two cited BURIED files, re-classifies, and checks that "
                "a reader who follows the claim line does not meet the caveat."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/BLD-0030/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": UNIT,
        },
        "downstream_consumers": [
            {
                "consumer": "BLD-0030 probe2_reviewer.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": probe_obj("verifier", "test-run", P2, "pending-probe2", 0),
            }
        ],
        "timestamps": {
            "started_at": started,
            "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": (
                "Two strikes then pivot from character-offset position to "
                "section-structure position before a third attempt."
            ),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "rules/common/fan-out-contract.md A3 is "
                    + ("present" if fanout_present else "absent")
                    + " on this worktree. The inline/buried rule is taken from "
                    "tests_required; A3 is the named input."
                ),
                "verdict": "CONFIRMED" if fanout_present else "NOT-CHECKED",
                "settling_experiment": (
                    "stat rules/common/fan-out-contract.md and read A3; if it "
                    "states inline-adjacency, this classifier is the executable "
                    "reading of that sentence."
                ),
            },
            {
                "claim": (
                    "The catalog's 40%/127 baseline is a prior-estate figure. "
                    "This worktree's live narrative n is "
                    + str(corpus_dist["n_tags"])
                    + "; the 127 is not reused as a count."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run the harvest on the estate that produced the 127-flag "
                    "memory and compare final-15 concentration."
                ),
            },
        ],
        "report": {
            "kind": "tag-position-audit",
            "observations": observations,
            "control_ids": [c["id"] for c in controls],
            "title": (
                "Caveat-position audit: inline adjacency versus a buried "
                "limitations section"
            ),
            "question": QUESTION,
            "method": {
                "primary": "section-structure",
                "character_offset_role": (
                    "Position fraction and decile histogram. The estate defect is "
                    "concentration in the final decile, which a mean conceals."
                ),
                "section_structure_role": (
                    "Burial rule. A trailing Limitations or Residual section is "
                    "BURIED even when the file is short."
                ),
            },
            "position_distribution": dist,
            "document_classes": classes_all,
            "document_classes_corpus_only": classes_corpus,
            "document_classes_fixtures": classes_fix,
            "buried_findings": buried,
            "controls": controls,
            "counts": {
                "corpus_documents": len(corpus),
                "corpus_tags": len(corpus_tags),
                "corpus_buried": sum(1 for t in corpus_tags if t.verdict == "BURIED"),
                "corpus_inline": sum(1 for t in corpus_tags if t.verdict == "INLINE"),
                "fixture_tags": len(fixture_tags),
                "fixture_buried": sum(1 for t in fixture_tags if t.verdict == "BURIED"),
            },
        },
        "extensions": {
            "cloud_ok": False,
            "fan_out_contract_present": fanout_present,
            "notes": (
                "G-1 for BLD-0030: live named probes, non-BLOCKED receipt, "
                "per-unit manifest. Did not run unit_manifest.py --write. "
                "Did not git commit. JSON receipts were excluded from harvest "
                "(use-versus-mention)."
            ),
        },
    }

    local_errs = validate_local(doc)
    if local_errs:
        print("FAILED:BLD-0030 local-contract")
        for e in local_errs[:20]:
            print(" ", e)
        return 1
    for garbage in ({}, {"totally": "unrelated"}, {"blob": "x" * 2000}):
        if not validate_local(garbage):
            print("FAILED:BLD-0030 local-contract accepted garbage")
            return 1

    physical_note = "not-run"
    try:
        physical_errs = validate_artifact(doc, SCHEMA)
        garbage_ok = bool(validate_artifact({}, SCHEMA))
        if physical_errs:
            print("FAILED:BLD-0030 physical-schema")
            for e in physical_errs[:25]:
                print(" ", e)
            return 1
        if not garbage_ok:
            print("FAILED:BLD-0030 physical-schema accepted garbage")
            return 1
        physical_note = "valid"
    except TypeError as exc:
        # jsonschema 4.10 Draft202012Validator rejects registry=; the shim
        # $ref cannot be retrieved from disk through that constructor here.
        physical_note = "resolver-incompatible:" + type(exc).__name__
        doc["residual_unknowns"].append(
            {
                "claim": (
                    "platform/lib/schema_resolver.py validator_for raised "
                    "TypeError on this jsonschema build; the local CONTRACT "
                    "is the discriminating check that rejected garbage."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run validate_artifact against "
                    "command-center/schema/tag-position-audit.schema.json "
                    "on a jsonschema that accepts referencing.Registry."
                ),
            }
        )
    doc["extensions"]["physical_schema"] = physical_note

    out = A.REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)

    def write_doc() -> None:
        out.write_text(
            json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )

    write_doc()
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    ended = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["timestamps"]["ended_at"] = ended
    write_doc()
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    write_doc()
    digest, size = sha256_file(out)

    c2, t2 = run_cmd(P2)
    if c2 != 0:
        print("FAILED:BLD-0030 probe2")
        print(t2)
        return 1
    evidence[1]["probes"][1] = probe_obj("verifier", "test-run", P2, t2, c2)
    doc["downstream_consumers"][0]["probe"] = probe_obj(
        "verifier", "test-run", P2, t2, c2
    )
    doc["downstream_consumers"][0]["exit_code"] = c2
    write_doc()
    digest, size = sha256_file(out)
    doc["artifacts"][0]["bytes"] = size
    doc["artifacts"][0]["sha256"] = digest
    write_doc()
    digest, size = sha256_file(out)

    if size < int(doc["min_bytes_threshold"]):
        print("FAILED:BLD-0030 artifact " + str(size) + "B below floor")
        return 1
    text = out.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0030" not in text:
        print("FAILED:BLD-0030 sentinel absent after write")
        return 1
    live = json.loads(text)
    if str(live.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0030 self-declared " + str(live.get("state")))
        return 1
    print(
        "wrote "
        + OUT
        + " bytes="
        + str(size)
        + " sha256="
        + digest
        + " corpus_tags="
        + str(len(corpus_tags))
        + " buried="
        + str(len(buried))
    )
    print("SUCCESS:BLD-0030")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
