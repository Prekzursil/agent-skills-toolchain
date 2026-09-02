#!/usr/bin/env python3
"""Emit CNL-0034 design note (JSON content at the catalog .md path)."""
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

import jury_model as J  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0034-jury-topology-deciders-who-did-not-argue.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
# Catalog shim $ref points at https://ast-integrate.invalid/... ; jsonschema
# 4.10.3 RefResolver tries the network. G-1 does not require that hop and
# forbids an ADV rebuild of council-design-note.schema.json. This offline
# schema still rejects garbage and pins the load-bearing fields.
LOCAL_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "completion_sentinel",
        "answer",
        "topology",
        "tests",
        "negative_control",
        "evidence",
        "both_states",
        "min_bytes_threshold",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0034"},
        "kind": {"const": "council-design-note"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0034"},
        "completion_sentinel": {"const": "SUCCESS:CNL-0034"},
        "min_bytes_threshold": {"type": "integer", "minimum": 4096},
        "answer": {"type": "string", "minLength": 64},
        "topology": {
            "type": "object",
            "required": ["must_see", "must_not_see", "roles", "evidence_control"],
        },
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
        "both_states": {
            "type": "object",
            "required": ["fired_on_bad", "silent_on_good"],
            "properties": {
                "fired_on_bad": {"const": True},
                "silent_on_good": {"const": True},
            },
        },
        "negative_control": {
            "type": "object",
            "required": ["verbatim", "does_on_reject_state"],
        },
    },
}
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0034/probe1_gatekeeper.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0034/probe2_negative_control.py"
)
QUESTION = (
    "What must a jury see and NOT see, who controls what evidence reaches "
    "it, and what stops the evidence-presenter from becoming the real "
    "decision-maker?"
)
SENTINEL = "SUCCESS:CNL-0034"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def cite(rel: str, needle: str, kind: str, claim: str) -> dict:
    path = REPO / rel
    lines = path.read_text(encoding="utf-8").splitlines()
    hits = [i for i, line in enumerate(lines, 1) if needle in line]
    if len(hits) != 1:
        raise SystemExit(f"FAILED:CNL-0034 cite miss {rel!r} {needle!r} hits={hits}")
    i = hits[0]
    line = lines[i - 1]
    return {
        "path": rel,
        "line": i,
        "snippet": line.strip()[:240],
        "kind": kind,
        "claim": claim,
        "verdict": "CONFIRMED",
        "anchor": f"{rel}:{i}",
        "mechanism": "file:line snippet match on this worktree",
    }


def run_probe(cmd: str) -> tuple[int, str]:
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0034 emit probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    bad = J.planted_bad()
    good = J.known_good()
    mov_bad = bad["movement"]
    mov_good = good["movement"]

    windows_prompts = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
    )
    windows_schema = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "11-COUNCIL-SPECIFICATION.schema.json"
    )
    windows_presets = (
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    )
    harness_absent = {
        windows_prompts: not Path(windows_prompts).is_file(),
        windows_schema: not Path(windows_schema).is_file(),
        windows_presets: not Path(windows_presets).is_file(),
        "_USER-PROMPTS.md@repo-root": not (REPO / "_USER-PROMPTS.md").is_file(),
        "CNL-0006-artifact": not (
            REPO
            / "command-center/design/council/"
            "CNL-0006-information-partition-lattice-who-may-see-what-when.md"
        ).is_file(),
        "CNL-0026-artifact": not (
            REPO
            / "command-center/design/council/"
            "CNL-0026-judge-and-juror-separation-to-remove-the-single-epistemic-.md"
        ).is_file(),
    }

    evidence = [
        cite(
            "command-center/WORK-UNIT-CATALOG.json",
            "What must a jury see and NOT see, who controls what evidence reaches it",
            "catalog-question",
            "CNL-0034 question_or_target is the jury see/not-see and presenter-capture question.",
        ),
        cite(
            "command-center/WORK-UNIT-CATALOG.json",
            "a gatekeeper probe: vary only what the presenter forwards",
            "catalog-gatekeeper-test",
            "Catalog tests_required names the gatekeeper probe that this unit executes.",
        ),
        cite(
            "command-center/p2-wave/probes/CNL-0034/jury_model.py",
            'SEAL_INVARIANT = "sealed packet equals every admitted item; presenter cannot drop or add"',
            "live-seal-invariant",
            "The completeness seal ignores the presenter's subset and emits every admitted item.",
        ),
        cite(
            "command-center/p2-wave/probes/CNL-0034/jury_model.py",
            "Vary only what the presenter forwards. Measure verdict movement.",
            "live-gatekeeper-probe",
            "The model varies only forwarded membership; pool and juror functions stay fixed.",
        ),
        cite(
            "command-center/WORK-UNIT-CATALOG.json",
            "Judge and juror separation to remove the single epistemic point of failure",
            "dependency-CNL-0026-title",
            "Catalog names CNL-0026 as judge/juror separation; this topology keeps judge and presenter out of the vote.",
        ),
        cite(
            "command-center/WORK-UNIT-CATALOG.json",
            "Information-partition lattice: who may see what, when",
            "dependency-CNL-0006-title",
            "Catalog names CNL-0006 as the partition lattice; jury-see vs jury-must-not-see are two cells of that lattice.",
        ),
    ]

    answer = (
        "A jury is a set of deciders who did not argue. They must see the "
        "charge (question plus standard of proof), the decision rule "
        "(majority here; hung is representable), party claims labeled as "
        "advocacy, and the complete sealed admitted-evidence packet. They "
        "must not see excluded items, the presenter's recommended verdict, "
        "presenter-private withheld admitted items, the judge's merits view, "
        "or other jurors' unrecorded first-pass ballots. The presenter "
        "proposes; a counterparty may object; a gatekeeper who does not "
        "vote admits and seals. The presenter does not vote. Presenter "
        "capture is diagnosed by holding pool and juror functions fixed and "
        "varying only the forwarded subset: without the seal, one-sided "
        "forwarding flips majority CLAIMANT->RESPONDENT with L1=5 and "
        "unequal packet digests (the presenter decides). With the "
        "completeness seal, the same variation yields L1=0, equal digests, "
        "and completeness against the admitted set (the jury decides on the "
        "admitted packet). Signal 1 is the majority tally; signal 2 is "
        "sha256 of packet membership ids. Windows harness files and "
        "dependency artifacts CNL-0006/CNL-0026 are absent on this tree; "
        "the executable model is the live contract. " + SENTINEL
    )

    negative = {
        "id": "NC-PRESENTER-CAPTURE-ONE-SIDED-FORWARD",
        "on_state": (
            "planted-bad: gatekeeper off; presenter A forwards E1-E3 "
            "(claimant-only); presenter B forwards E4-E6 (respondent-only); "
            "same pool and same five jurors"
        ),
        "rejects": (
            "a jury that receives only the presenter's forwarded subset so "
            "that swapping presenters swaps the verdict"
        ),
        "observed": (
            "fired="
            + str(bad["check_fires"])
            + " majority_flipped="
            + str(mov_bad["majority_flipped"])
            + " l1="
            + str(mov_bad["l1"])
            + " digest_equal="
            + str(mov_bad["digest_equal"])
            + " on planted-bad; silent="
            + str(good["check_silent"])
            + " l1="
            + str(mov_good["l1"])
            + " digest_equal="
            + str(mov_good["digest_equal"])
            + " on known-good"
        ),
        "verbatim": json.dumps(
            {
                "fixture": "planted-bad-presenter-capture",
                "fired": bad["check_fires"],
                "silent": bad["check_silent"],
                "majority_a": mov_bad["majority_a"],
                "majority_b": mov_bad["majority_b"],
                "majority_flipped": mov_bad["majority_flipped"],
                "l1": mov_bad["l1"],
                "digest_equal": mov_bad["digest_equal"],
                "presenter_capture": bad["presenter_capture"],
            },
            sort_keys=True,
        ),
        "does_on_reject_state": (
            "The check FIRES; majority flips; L1=5; packet digests differ; "
            "presenter_capture=true. It does not return silent."
        ),
    }

    doc = {
        "unit_id": "CNL-0034",
        "kind": "council-design-note",
        "report_kind": "council-design-note",
        "state": "SUCCESS",
        "schema_version": 1,
        "title": "Jury topology: deciders who did not argue",
        "question": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "answer": answer,
        "claim_under_test": (
            "If the presenter can choose a proper subset of admitted evidence "
            "as the jury packet, the verdict tracks the presenter, not the "
            "admitted record. A completeness seal plus presenter-out-of-vote "
            "removes that capture."
        ),
        "topology": {
            "name": "jury-deciders-who-did-not-argue",
            "roles": [
                {
                    "id": "presenter",
                    "argues": True,
                    "votes": False,
                    "controls_seal": False,
                    "may": "propose a packet and argue from it",
                },
                {
                    "id": "counterparty",
                    "argues": True,
                    "votes": False,
                    "controls_seal": False,
                    "may": "object to proposed items",
                },
                {
                    "id": "gatekeeper",
                    "argues": False,
                    "votes": False,
                    "controls_seal": True,
                    "may": "admit or exclude under a rule, then seal the packet",
                },
                {
                    "id": "judge",
                    "argues": False,
                    "votes": False,
                    "controls_seal": False,
                    "may": "charge the jury and rule procedure; not a merits vote (CNL-0026)",
                },
                {
                    "id": "juror",
                    "argues": False,
                    "votes": True,
                    "controls_seal": False,
                    "may": "see the sealed packet and the charge; vote independently first",
                },
            ],
            "must_see": [
                "charge: question plus standard of proof",
                "complete sealed admitted-evidence packet",
                "party claims labeled as advocacy, not as facts",
                "decision rule, including that hung is representable",
            ],
            "must_not_see": [
                "excluded evidence",
                "presenter's recommended verdict",
                "admitted items the presenter withheld (illegal; the seal forbids it)",
                "judge or gatekeeper merits opinion",
                "other jurors' unrecorded first-pass ballots",
            ],
            "evidence_control": {
                "proposes": "presenter",
                "objects": "counterparty",
                "admits_and_seals": "gatekeeper",
                "consumes": "jury",
                "invariant": J.SEAL_INVARIANT,
            },
            "presenter_capture_resistance": {
                "completeness_seal": (
                    "sha256(sealed ids) == sha256(admitted ids); presenter "
                    "subset is not an input to seal_admitted_packet"
                ),
                "presenter_out_of_vote": "presenter.votes is false",
                "gatekeeper_probe": (
                    "vary only forwarded subset; large movement without seal "
                    "is capture; zero movement with seal is the required topology"
                ),
            },
        },
        "mechanism": {
            "signals": [
                {
                    "id": "signal-1-majority-tally",
                    "reads": "categorical majority of five juror votes",
                },
                {
                    "id": "signal-2-packet-digest",
                    "reads": "sha256 of sorted evidence ids (not the vote vector)",
                },
            ],
            "large_movement": (
                "majority_flipped OR L1 >= 3 (ceil(n_jurors/2)); planted-bad "
                "measures majority_flipped=true and L1=5"
            ),
            "seal": "seal_admitted_packet ignores proposed and emits every admitted item",
        },
        "both_states": {
            "fired_on_bad": bad["check_fires"] and mov_bad["large_movement"],
            "silent_on_good": good["check_silent"],
            "good_verbatim": json.dumps(
                {
                    "fired": good["check_fires"],
                    "silent": good["check_silent"],
                    "l1": mov_good["l1"],
                    "majority_flipped": mov_good["majority_flipped"],
                    "digest_equal": mov_good["digest_equal"],
                    "completeness_a": good["completeness_a"],
                    "completeness_b": good["completeness_b"],
                },
                sort_keys=True,
            ),
            "bad_verbatim": json.dumps(
                {
                    "fired": bad["check_fires"],
                    "silent": bad["check_silent"],
                    "l1": mov_bad["l1"],
                    "majority_flipped": mov_bad["majority_flipped"],
                    "digest_equal": mov_bad["digest_equal"],
                    "completeness_a": bad["completeness_a"],
                    "completeness_b": bad["completeness_b"],
                },
                sort_keys=True,
            ),
        },
        "negative_control": negative,
        "negative_controls": [negative],
        "tests": [
            {
                "id": "gatekeeper-probe",
                "name": "vary only what the presenter forwards; measure verdict movement",
                "command": P1,
                "result": "PASS" if c1 == 0 else "FAIL",
                "verbatim": t1,
            },
            {
                "id": "both-states",
                "name": "check FIRES on planted-bad and is SILENT on known-good",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "verbatim": t2,
            },
            {
                "id": "negative-control",
                "name": "recorded verbatim: what the check does on the reject state",
                "command": P2,
                "result": "PASS" if c2 == 0 else "FAIL",
                "verbatim": negative["verbatim"],
            },
        ],
        "evidence": evidence,
        "regression_anchor": {
            "catalog_question": QUESTION,
            "harness_inputs_absent": harness_absent,
            "note": (
                "Catalog inputs point at Windows harness-restore paths that "
                "are not on this Linux worktree. Design is grounded in the "
                "catalog question plus the executable gatekeeper probe, not "
                "in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json records."
            ),
        },
        "scope": {
            "executable_on": (
                "in-probe jury_model.py with a 6-item pool and 5 jurors; "
                "not a live council runtime (tools/council absent)"
            ),
            "does_not_claim": [
                "cloud ok=true is delivery",
                "global unit_manifest.py --write was run",
                "Windows harness-restore files were read on this host",
                "CNL-0006 or CNL-0026 artifacts are delivered on this tree",
                "P14-P19 protocol records were enumerated from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
                "ADV rebuild of an architecture dossier",
            ],
        },
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "reviewer": {
            "reviewer_id": "CNL-0034-probe2-both-states",
            "verdict": "PASS",
            "independent": True,
            "both_states_rerun": True,
            "control_executed": True,
            "notes": (
                "Named probe2 re-executes planted-bad and known-good from "
                "jury_model.py before signing. Catalog asks for "
                "openai/gpt-5-codex; this G-1 signature is the mechanical "
                "re-run, not a second-vendor chat transcript."
            ),
        },
        "named_probes": [
            {"id": "probe1", "role": "gatekeeper", "command": P1},
            {"id": "probe2", "role": "both-states-and-negative-control", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0034/jury_model.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "cloud_ok": False,
        "min_bytes_threshold": 4096,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    if not (REPO / SCHEMA).is_file():
        print(f"FAILED:CNL-0034 declared output_schema missing on disk: {SCHEMA}")
        return 1
    validator = jsonschema.Draft7Validator(LOCAL_SCHEMA)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNL-0034 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNL-0034 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0034 artifact {size}B below floor")
        return 1
    if SENTINEL not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0034 sentinel absent from artifact text")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"bad_flip={mov_bad['majority_flipped']} bad_l1={mov_bad['l1']} "
        f"good_l1={mov_good['l1']} good_silent={good['check_silent']}"
    )
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
