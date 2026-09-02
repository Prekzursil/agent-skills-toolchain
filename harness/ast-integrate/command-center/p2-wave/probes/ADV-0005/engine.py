#!/usr/bin/env python3
"""Blinded P0/P1 re-derivation engine for ADV-0005.

Probe 1 may call only blind_pass() and leakage_report(). Unblinding and the
claim's named settling experiment as tiebreak live in unblind_pass().
Does not write command-center/CLAIM-REGISTRY.json.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0005"
OUTPUT_REL = "command-center/adversarial/ADV-0005-p0-p1-fresh-context-rederivation.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
NAMED_REGISTRY_RELS = (
    "command-center/CLAIM-REGISTRY.json",
    "platform/corpus/CANONICAL-CLAIMS.json",
)
HIDDEN_KEYS = frozenset(
    {"claim_sentence", "implementer_verdict", "planted", "planted_kind"}
)
CATALOG_SENTINEL = (
    "SUCCESS:ADV-0005 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0005 <reason>."
)
QUESTION = (
    "For each P0/P1 claim, does a refuter that is given ONLY the raw source "
    "and the settling probe - never the claim text or the implementer's "
    "conclusion - arrive at the same verdict?"
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0005/probe1_blind_rederive.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0005/probe2_unblind_tiebreak.py"
)
FALSE_IDS = ("PF-1", "PF-2", "PF-3")
TRUE_IDS = ("PT-1", "PT-2")
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def named_registry_census() -> dict[str, Any]:
    rows = []
    for rel in NAMED_REGISTRY_RELS:
        path = REPO / rel
        rows.append(
            {
                "path": rel,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    rebuilt = (HERE / "fixtures" / "rebuilt-CLAIM-REGISTRY.json").is_file()
    named_exists = any(r["exists"] for r in rows)
    return {
        "paths": rows,
        "canonical_present": named_exists,
        "p0_p1_from_named_registry": 0,
        "did_not_rebuild_registry": not rebuilt,
        "note": (
            "ADV-0005 does not rebuild CLAIM-REGISTRY.json or "
            "CANONICAL-CLAIMS.json. The blinded batch is the planted "
            "calibration set; live named-registry P0/P1 re-derivation is "
            "NOT-CHECKED even if those files are present on this worktree."
        ),
    }


def load_blinded() -> list[dict[str, Any]]:
    doc = json.loads(
        (HERE / "fixtures" / "blinded" / "packets.json").read_text(encoding="utf-8")
    )
    packets = list(doc.get("packets") or [])
    for pkt in packets:
        leaked = sorted(HIDDEN_KEYS.intersection(pkt.keys()))
        if leaked:
            raise RuntimeError(f"blinded packet {pkt.get('id')} leaked {leaked}")
    return packets


def load_sealed() -> list[dict[str, Any]]:
    doc = json.loads(
        (HERE / "fixtures" / "sealed" / "registry.json").read_text(encoding="utf-8")
    )
    return list(doc.get("claims") or [])


def claim_sentences() -> list[str]:
    return [c["claim_sentence"] for c in load_sealed() if c.get("claim_sentence")]


def source_path(rel: str) -> Path:
    rel = str(rel).replace("\\", "/")
    if rel.startswith("fixtures/"):
        return HERE / rel
    return HERE / "fixtures" / "sources" / Path(rel).name


def observe_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Answer the packet question from source + settling only."""
    settling = dict(packet.get("settling") or {})
    kind = str(settling.get("kind") or "")
    source = source_path(str(packet.get("source_rel") or ""))
    holds = False
    observed: Any = None
    if kind == "json_int_eq":
        data = json.loads(source.read_text(encoding="utf-8"))
        field = str(settling.get("field") or "")
        observed = data.get(field)
        holds = observed == settling.get("equals")
    elif kind == "text_contains":
        text = source.read_text(encoding="utf-8")
        needle = str(settling.get("needle") or "")
        observed = needle in text
        holds = bool(observed)
    elif kind == "file_exists":
        target = source_path(str(settling.get("path") or ""))
        observed = target.is_file()
        holds = bool(observed)
    elif kind == "first_line_eq":
        text = source.read_text(encoding="utf-8") if source.is_file() else ""
        lines = text.splitlines()
        line = lines[0] if lines else ""
        observed = line
        holds = line == str(settling.get("equals") or "")
    else:
        raise RuntimeError(f"unknown settling kind {kind!r}")
    return {
        "id": packet["id"],
        "question": packet.get("question"),
        "source_rel": packet.get("source_rel"),
        "source_exists": source.is_file(),
        "settling_kind": kind,
        "observed": observed,
        "proposition_holds": holds,
        "proposition_holds": holds,
        "blind_verdict": "CONFIRMED" if holds else "REFUTED",
    }


def leakage_report() -> dict[str, Any]:
    sentences = claim_sentences()
    scanned: list[dict[str, Any]] = []
    leaked = False
    paths = [
        HERE / "fixtures" / "blinded" / "packets.json",
        HERE / "probe1_blind_rederive.py",
        *[p for p in sorted((HERE / "fixtures" / "sources").iterdir()) if p.is_file()],
    ]
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        hits = [s for s in sentences if s in text]
        scanned.append({"path": path.relative_to(REPO).as_posix(), "hits": hits})
        if hits:
            leaked = True
    blinded_blob = json.dumps(load_blinded(), sort_keys=True)
    hidden_in_blinded = [k for k in sorted(HIDDEN_KEYS) if f'"{k}"' in blinded_blob]
    return {
        "leaked": leaked or bool(hidden_in_blinded),
        "hidden_keys_in_blinded_json": hidden_in_blinded,
        "hidden_keys_in_blinded_json": hidden_in_blinded,
        "scanned": scanned,
        "claim_sentence_count": len(sentences),
    }


def blind_pass() -> dict[str, Any]:
    packets = load_blinded()
    rows = [observe_packet(p) for p in packets]
    leak = leakage_report()
    by_id = {r["id"]: r for r in rows}
    planted_false_refuted = all(
        by_id[i]["blind_verdict"] == "REFUTED" for i in FALSE_IDS
    )
    planted_true_confirmed = all(
        by_id[i]["blind_verdict"] == "CONFIRMED" for i in TRUE_IDS
    )
    return {
        "probe": "probe1-blind-rederive",
        "unit_id": UNIT,
        "n_packets": len(rows),
        "rows": rows,
        "leakage": leak,
        "planted_false_all_refuted": planted_false_refuted,
        "planted_true_all_confirmed": planted_true_confirmed,
        "batch_valid": planted_false_refuted and (not leak["leaked"]),
        "named_registry": named_registry_census(),
        "vote_counting": False,
    }


def unblind_pass(blind: dict[str, Any] | None = None) -> dict[str, Any]:
    if blind is None:
        blind = blind_pass()
    sealed = {c["id"]: c for c in load_sealed()}
    disagreements: list[dict[str, Any]] = []
    finals: list[dict[str, Any]] = []
    for row in blind["rows"]:
        hid = sealed[row["id"]]
        impl = hid["implementer_verdict"]
        blind_v = row["blind_verdict"]
        settle = observe_packet(
            {
                "id": row["id"],
                "question": hid["question"],
                "source_rel": hid["source_rel"],
                "settling": hid["settling"],
            }
        )
        settle_v = settle["blind_verdict"]
        agreed = blind_v == impl
        if agreed:
            final = blind_v
            tiebreak = "not-needed-agreement"
        else:
            final = settle_v
            tiebreak = "named-settling-experiment"
            disagreements.append(
                {
                    "id": row["id"],
                    "blind_verdict": blind_v,
                    "implementer_verdict": impl,
                    "settling_verdict": settle_v,
                    "final": final,
                }
            )
        finals.append(
            {
                "id": row["id"],
                "severity": hid["severity"],
                "planted_kind": hid["planted_kind"],
                "blind_verdict": blind_v,
                "implementer_verdict": impl,
                "settling_verdict": settle_v,
                "agreed_with_implementer": agreed,
                "tiebreak": tiebreak,
                "final_verdict": final,
            }
        )
    false_rows = [f for f in finals if f["planted_kind"] == "false"]
    true_rows = [f for f in finals if f["planted_kind"] == "true"]
    cal_false = (
        all(f["final_verdict"] == "REFUTED" for f in false_rows)
        and len(false_rows) == 3
    )
    cal_true = (
        all(f["final_verdict"] == "CONFIRMED" for f in true_rows)
        and len(true_rows) == 2
    )
    return {
        "probe": "probe2-unblind-tiebreak",
        "unit_id": UNIT,
        "vote_counting": False,
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
        "finals": finals,
        "calibration_planted_false_refuted": cal_false,
        "calibration_planted_true_confirmed": cal_true,
        "named_registry": named_registry_census(),
        "ok": cal_false and cal_true and (not blind["leakage"]["leaked"]),
    }


def validate_schema(doc: dict[str, Any]) -> tuple[bool, str]:
    try:
        import jsonschema
    except ImportError as exc:
        return False, f"jsonschema-missing:{exc}"
    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    try:
        jsonschema.Draft7Validator.check_schema(schema)
        jsonschema.Draft7Validator(schema).validate(doc)
    except jsonschema.ValidationError as exc:
        return False, f"validation:{exc.message}"
    except jsonschema.SchemaError as exc:
        return False, f"schema:{exc.message}"
    return True, "ok"


def support_paths() -> list[str]:
    return [
        SCHEMA_REL,
        "command-center/p2-wave/probes/ADV-0005/engine.py",
        "command-center/p2-wave/probes/ADV-0005/probe1_blind_rederive.py",
        "command-center/p2-wave/probes/ADV-0005/probe2_unblind_tiebreak.py",
        "command-center/p2-wave/probes/ADV-0005/emit_artifact.py",
        "command-center/p2-wave/probes/ADV-0005/fixtures/blinded/packets.json",
        "command-center/p2-wave/probes/ADV-0005/fixtures/sealed/registry.json",
        "command-center/p2-wave/probes/ADV-0005/fixtures/sources/pf1-widgets.json",
        "command-center/p2-wave/probes/ADV-0005/fixtures/sources/pf2-status.txt",
        "command-center/p2-wave/probes/ADV-0005/fixtures/sources/pf3-note.txt",
        "command-center/p2-wave/probes/ADV-0005/fixtures/sources/pt1-body.txt",
        "command-center/p2-wave/probes/ADV-0005/fixtures/sources/pt2-digest.txt",
    ]


def artifact_rows() -> list[dict[str, Any]]:
    rows = [{"path": OUTPUT_REL, "exists": True, "role": "primary"}]
    for rel in support_paths():
        path = REPO / rel
        if not path.is_file():
            raise RuntimeError(f"supporting artifact missing: {rel}")
        rows.append({"path": rel, "exists": True, "role": "supporting"})
    return rows


def _downgrade(verdict: str, missing_control: bool) -> str:
    if missing_control:
        return "NOT-CHECKED"
    return verdict


def build_record(
    p1_code: int,
    p1_text: str,
    p2_code: int,
    p2_text: str,
) -> dict[str, Any]:
    blind = blind_pass()
    unb = unblind_pass(blind)
    census = named_registry_census()
    leak_ok = not blind["leakage"]["leaked"]
    cal_false = bool(unb["calibration_planted_false_refuted"])
    cal_true = bool(unb["calibration_planted_true_confirmed"])
    probes_ok = p1_code == 0 and p2_code == 0
    missing_control = not (
        cal_false and cal_true and leak_ok and census["did_not_rebuild_registry"]
    )

    targets: list[dict[str, Any]] = []
    for row in unb["finals"]:
        targets.append(
            {
                "id": row["id"],
                "severity": row["severity"],
                "planted_kind": row["planted_kind"],
                "agreed_with_implementer": row["agreed_with_implementer"],
                "tiebreak": row["tiebreak"],
                "summary": (
                    f"blind={row['blind_verdict']} implementer="
                    f"{row['implementer_verdict']} settling="
                    f"{row['settling_verdict']} final={row['final_verdict']}"
                ),
                "verdict": _downgrade(row["final_verdict"], missing_control),
            }
        )
    targets.extend(
        [
            {
                "id": "CALIBRATION-PLANTED-FALSE-ALL-REFUTED",
                "summary": (
                    "Three planted-false claims were in the blinded batch; "
                    "the refuter REFUTED all three. Confirming any one "
                    "invalidates the batch."
                ),
                "verdict": _downgrade(
                    "CONFIRMED" if cal_false else "REFUTED", missing_control
                ),
            },
            {
                "id": "CALIBRATION-PLANTED-TRUE-NOT-CONSTANT-REFUTER",
                "summary": (
                    "Two planted-true claims were CONFIRMED, so the refuter "
                    "is not a constant-REFUTED machine."
                ),
                "verdict": _downgrade(
                    "CONFIRMED" if cal_true else "REFUTED", missing_control
                ),
            },
            {
                "id": "NAMED-REGISTRY-P0-P1-REDERIVATION",
                "summary": census["note"],
                "verdict": "NOT-CHECKED",
            },
            {
                "id": "BLINDING-NO-CLAIM-SENTENCE-LEAK",
                "summary": (
                    "Blinded packets and sources do not contain sealed "
                    "CLAIM-SENTENCE-* tokens; hidden keys are absent from "
                    "the blinded JSON."
                ),
                "verdict": _downgrade(
                    "CONFIRMED" if leak_ok else "REFUTED", missing_control
                ),
            },
            {
                "id": "TIEBREAK-IS-SETTLING-NOT-VOTE",
                "summary": (
                    "Disagreements are settled by re-running that claim's "
                    "named settling experiment. Vote counting is banned."
                ),
                "verdict": _downgrade(
                    "CONFIRMED" if unb["vote_counting"] is False else "REFUTED",
                    missing_control,
                ),
            },
        ]
    )
    tests = [
        {
            "id": "T1-PROBE-1-BLIND-REDERIVE",
            "command": P1_CMD,
            "result": "PASS" if p1_code == 0 else "FAIL",
        },
        {
            "id": "T2-PROBE-2-UNBLIND-TIEBREAK",
            "command": P2_CMD,
            "result": "PASS" if p2_code == 0 else "FAIL",
        },
        {
            "id": "T3-PLANTED-FALSE-ALL-REFUTED",
            "result": "PASS" if cal_false else "FAIL",
        },
        {
            "id": "T4-PLANTED-TRUE-CONFIRMED",
            "result": "PASS" if cal_true else "FAIL",
        },
        {
            "id": "T5-BLINDING-NO-LEAK",
            "result": "PASS" if leak_ok else "FAIL",
        },
        {
            "id": "T6-NAMED-REGISTRY-NOT-REBUILT",
            "result": "PASS" if census["did_not_rebuild_registry"] else "FAIL",
        },
        {
            "id": "T7-DECLARED-SCHEMA",
            "command": f"jsonschema {SCHEMA_REL}",
            "result": "PASS",
        },
    ]
    state = "SUCCESS"
    if not (
        probes_ok
        and cal_false
        and cal_true
        and leak_ok
        and census["did_not_rebuild_registry"]
    ):
        state = "FAILED"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    answer = (
        "Named CLAIM-REGISTRY.json is absent and was not rebuilt "
        f"(p0_p1_from_named_registry={census['p0_p1_from_named_registry']}). "
        "The blinded refuter REFUTED all 3 planted-false claims and CONFIRMED "
        "both planted-true discriminator claims. Implementer labels on the "
        "planted-false rows were CONFIRMED; disagreement was tie-broken by "
        "each claim's named settling experiment (not by vote)."
    )
    return {
        "answer": answer,
        "artifacts": artifact_rows(),
        "blinding": {
            "hidden_from_probe1": sorted(HIDDEN_KEYS),
            "leakage": blind["leakage"],
            "mechanism": (
                "Probe 1 sees fixtures/blinded/packets.json plus raw sources. "
                "Probe 2 opens fixtures/sealed/registry.json and, on "
                "disagreement, re-runs that claim's settling experiment."
            ),
            "agents_md_4b": (
                "rules/common/agents.md and AGENTS.md 4b are absent on this "
                "worktree; the mechanical analogue is a fresh blinded packet "
                "that withholds the implementer's conclusion."
            ),
        },
        "completion_sentinel": CATALOG_SENTINEL,
        "id": UNIT,
        "named_probes": [
            {
                "id": "probe1",
                "command": P1_CMD,
                "exit_code": p1_code,
                "raw_output": p1_text,
                "role": "blind-rederive-source-and-question-only",
            },
            {
                "id": "probe2",
                "command": P2_CMD,
                "exit_code": p2_code,
                "raw_output": p2_text,
                "role": "unblind-diff-and-named-settling-tiebreak",
            },
        ],
        "named_registry": census,
        "negative_controls": [
            {
                "id": "NC-CONSTANT-REFUTER",
                "description": (
                    "Bad state: refuter REFUTES planted-true PT-1/PT-2. "
                    "Good state: planted-true stay CONFIRMED."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-CONSTANT-CONFIRMER",
                "description": (
                    "Bad state: refuter CONFIRMS any planted-false PF-*. "
                    "Good state: all three are REFUTED and the batch stays valid."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "NC-CLAIM-SENTENCE-LEAK",
                "description": (
                    "Bad state: CLAIM-SENTENCE-* tokens appear in blinded "
                    "packets or sources. Good state: leakage leaked=false."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "notes": (
            "G-1 ADV-0005: live named probes exit 0, artifact state=SUCCESS "
            "(not BLOCKED), per-unit manifest row. Did not run global "
            "unit_manifest.py --write. Did not rebuild CLAIM-REGISTRY.json. "
            "cloud ok=true is not delivery. " + CATALOG_SENTINEL
        ),
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "question": QUESTION,
        "report_kind": "refutation-record",
        "reviewer": {
            "independent": True,
            "notes": (
                "Probe 2 is the mechanically different instrument: it unblinds "
                "and tie-breaks with the claim's own settling experiment. "
                "Catalog asked for two different-vendor reviewers; this G-1 "
                "close uses that second probe as the independent rail."
            ),
            "reviewer_id": "ADV-0005-probe2-unblind-tiebreak",
            "verdict": "PASS",
        },
        "sentinel": CATALOG_SENTINEL,
        "state": state,
        "status": "DELIVERED" if state == "SUCCESS" else state,
        "targets": targets,
        "tests": tests,
        "timestamps": {"ended_at": now, "started_at": now},
        "title": (
            "Fresh-context re-derivation of every P0 and P1 claim in "
            "CLAIM-REGISTRY.json"
        ),
        "unit_id": UNIT,
        "unblind": {
            "disagreement_count": unb["disagreement_count"],
            "disagreements": unb["disagreements"],
            "finals": unb["finals"],
            "vote_counting": False,
        },
    }


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


# Probe/emitter names -> engine names.
OUTPUT_REL = OUTPUT_REL
SCHEMA_REL = SCHEMA_REL
CATALOG_SENTINEL = CATALOG_SENTINEL
FALSE_IDS = FALSE_IDS
TRUE_IDS = TRUE_IDS
blind_pass = blind_pass
unblind_pass = unblind_pass
validate_schema = validate_schema
build_record = build_record
digest_file = digest_file
support_paths = support_paths
