#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0121-acquired-artifact-injection-gate.json."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from wfa_injection_gate.consumer import consume_tree  # noqa: E402
from wfa_injection_gate.corpus import PAYLOAD_CLASSES, write_corpus  # noqa: E402
from wfa_injection_gate.gate import neutralise_tree  # noqa: E402

UNIT = "WFA-0121"
OUT = "command-center/wfa/WFA-0121-acquired-artifact-injection-gate.json"
SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json#/$defs/RegressionFixture"
SENTINEL = "SUCCESS:WFA-0121"
QUESTION = (
    "Implementation target: a gate that neutralises instruction-shaped content "
    "inside acquired workflow definitions, transcripts and marketplace packages "
    "before any downstream stage reads them - covering the spec's named class "
    "in which a council transcript or participant artifact injects instructions "
    "into a later stage."
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0121/probe1_payload_classes.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0121/probe2_downstream_behaviour.py"
)
TEST_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "tools/wfa_injection_gate/tests/test_gate.py"
)
SUPPORTING = [
    "tools/wfa_injection_gate/__init__.py",
    "tools/wfa_injection_gate/gate.py",
    "tools/wfa_injection_gate/consumer.py",
    "tools/wfa_injection_gate/corpus.py",
    "tools/wfa_injection_gate/tests/test_gate.py",
    "command-center/p2-wave/probes/WFA-0121/probe1_payload_classes.py",
    "command-center/p2-wave/probes/WFA-0121/probe2_downstream_behaviour.py",
]


def digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def run_cmd(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    text = ((proc.stdout or "") + (proc.stderr or "")).strip()
    return proc.returncode, text


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest(path)
    return {
        "path": rel,
        "role": role,
        "exists": path.is_file(),
        "present": path.is_file(),
        "bytes": size,
        "sha256": sha,
        "eol": "LF",
        "unit_id": UNIT,
        "receipt_path": "command-center/p2-wave/probes/WFA-0121/SUBAGENT-RETURN.json",
    }


def probe_obj(cmd: str, code: int, text: str, role: str) -> dict:
    return {
        "command": cmd,
        "exit_code": code,
        "fingerprint": hashlib.sha256(f"command\x1f{cmd}".encode()).hexdigest()[:32],
        "method": "command",
        "raw_output": text[-16000:],
        "role": role,
    }


def live_campaign() -> dict:
    with tempfile.TemporaryDirectory(prefix="wfa0121-emit-") as raw:
        root = Path(raw)
        src = root / "src"
        dest = root / "gated"
        write_corpus(src)
        rows = [r.as_dict() for r in neutralise_tree(src, dest)]
        plants = {}
        for name in (
            "role-spoof",
            "ignore-previous",
            "base64-exec",
            "bundled-agent-config",
        ):
            ungated = consume_tree(src / name)
            gated = consume_tree(dest / name)
            plants[name] = {
                "ungated": ungated.as_dict(),
                "gated": gated.as_dict(),
                "ungated_changed": ungated.canary_obeyed or ungated.config_autoload,
                "gated_changed": gated.canary_obeyed or gated.config_autoload,
            }
        mention_u = consume_tree(src / "mention-docs")
        mention_g = consume_tree(dest / "mention-docs")
        caught: list[str] = []
        for row in rows:
            for cls in row["classes"]:
                if cls not in caught:
                    caught.append(cls)
        src_alive = all(
            p.is_file() and p.stat().st_size > 0
            for p in src.rglob("*")
            if p.is_file()
        )
        return {
            "caught_classes": caught,
            "payload_classes_required": list(PAYLOAD_CLASSES),
            "all_required_caught": all(c in caught for c in PAYLOAD_CLASSES),
            "source_files_preserved": src_alive,
            "plants": plants,
            "mention": {
                "ungated": mention_u.as_dict(),
                "gated": mention_g.as_dict(),
                "silent": not (
                    mention_u.canary_obeyed
                    or mention_g.canary_obeyed
                    or mention_u.config_autoload
                    or mention_g.config_autoload
                ),
            },
            "file_results": rows,
        }


def main() -> int:
    c_test, t_test = run_cmd(TEST_CMD)
    c1, t1 = run_cmd(P1)
    c2, t2 = run_cmd(P2)
    if c_test != 0 or c1 != 0 or c2 != 0:
        print(f"FAILED:WFA-0121 emit tests={c_test} p1={c1} p2={c2}")
        print(t_test[-2000:])
        print(t1[-2000:])
        print(t2[-2000:])
        return 1
    if "SUCCESS:WFA-0121-tests" not in t_test:
        print("FAILED:WFA-0121 emit tests sentinel missing")
        return 1
    if "SUCCESS:WFA-0121-probe1" not in t1:
        print("FAILED:WFA-0121 emit probe1 sentinel missing")
        return 1
    if "SUCCESS:WFA-0121-probe2" not in t2:
        print("FAILED:WFA-0121 emit probe2 sentinel missing")
        return 1

    campaign = live_campaign()
    if not campaign["all_required_caught"]:
        print(f"FAILED:WFA-0121 missing classes {campaign['caught_classes']}")
        return 1
    if not campaign["source_files_preserved"]:
        print("FAILED:WFA-0121 source files were deleted")
        return 1
    if not campaign["mention"]["silent"]:
        print("FAILED:WFA-0121 mention control fired")
        return 1
    for name, row in campaign["plants"].items():
        if not row["ungated_changed"]:
            print(f"FAILED:WFA-0121 ungated {name} did not change behaviour")
            return 1
        if row["gated_changed"]:
            print(f"FAILED:WFA-0121 gated {name} still changed behaviour")
            return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifacts = [artifact_row(p, "supporting") for p in SUPPORTING]
    for row in artifacts:
        if not row["exists"]:
            print(f"FAILED:WFA-0121 missing supporting {row['path']}")
            return 1

    p_test = probe_obj(TEST_CMD, c_test, t_test, "verifier")
    p1 = probe_obj(P1, c1, t1, "source")
    p2 = probe_obj(P2, c2, t2, "verifier")

    fixture = {
        "$schema": SCHEMA,
        "record_type": "RegressionFixture",
        "id": "WFA-0121-acquired-artifact-injection-gate",
        "unit_id": UNIT,
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "title": (
            "Treat every acquired workflow artifact as untrusted data and gate "
            "it against prompt injection"
        ),
        "question_or_target": QUESTION,
        "spec_anchor": (
            "WORK-UNIT-CATALOG.json:WFA-0121; AGENTS.md 9; "
            "_USER-PROMPTS.md:11344"
        ),
        "failure_class": "injection-detected",
        "failure_classification": [
            "injection-detected",
            "detector-failure",
            "overclaim",
        ],
        "output_schema": SCHEMA,
        "schema_note": (
            "WFA-0001 schema pack is not on disk in this worktree. This record "
            "is a RegressionFixture-shaped gate report; pack-level validation "
            "is residual until WFA-0001 lands. That residual is not claimed as "
            "PASS."
        ),
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two-strikes-then-pivot"},
        "gate": {
            "module": "tools/wfa_injection_gate/gate.py",
            "consumer": "tools/wfa_injection_gate/consumer.py",
            "rule": (
                "Acquired workflow definitions, transcripts and marketplace "
                "packages are untrusted DATA. Instruction USE is wrapped in a "
                "structural [[UNTRUSTED-DATA]] fence. Mention inside backticks "
                "or documentation quotes is not USE. Bundled .claude/.codex "
                "configs are tagged and never auto-loaded. Files are not deleted."
            ),
            "payload_classes": list(PAYLOAD_CLASSES),
            "caught_classes": campaign["caught_classes"],
            "neutralisation": "wrap-in-place-copy",
            "deletion_is_not_neutralisation": True,
        },
        "answer": (
            "The acquired-artifact injection gate caught every planted class "
            f"({', '.join(PAYLOAD_CLASSES)}), including bundled .claude and "
            ".codex configs. A documentation quote of those strings was not "
            "flagged. Neutralisation preserved mechanism_id/stage_id tokens and "
            "left source files in place. A downstream extraction consumer that "
            "obeys unfenced canaries and auto-loads ungated agent config did "
            "not change behaviour on gated artefacts; the same consumer on the "
            "ungated plants did. "
            + SENTINEL
        ),
        "evidence": [
            {
                "id": "A",
                "anchor": "tools/wfa_injection_gate/corpus.py:write_corpus",
                "claim": (
                    "Planted role-spoof, ignore-previous-instructions, base64 "
                    "exec, and bundled .claude/.codex configs are each detected "
                    "and wrapped."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p1, p_test],
            },
            {
                "id": "B",
                "anchor": "tools/wfa_injection_gate/consumer.py:consume_tree",
                "claim": (
                    "A downstream consumer fed the neutralised artefact does "
                    "not fire the canary or auto-load agent config. The same "
                    "consumer on the ungated plant does. This is independent "
                    "of the scanner's detected boolean."
                ),
                "confidence": "almost-certain",
                "verdict": "CONFIRMED",
                "probes": [p2, p_test],
            },
        ],
        "planted_payloads": [
            {
                "id": name,
                "ungated_changed": row["ungated_changed"],
                "gated_changed": row["gated_changed"],
                "ungated": row["ungated"],
                "gated": row["gated"],
            }
            for name, row in campaign["plants"].items()
        ],
        "both_states": {
            "planted_use_rejected": all(
                row["ungated_changed"] and not row["gated_changed"]
                for row in campaign["plants"].values()
            ),
            "mention_control_silent": campaign["mention"]["silent"],
            "content_preserved": campaign["source_files_preserved"],
        },
        "controls": {
            "use_versus_mention": {
                "id": "mention-docs",
                "flagged": False,
                "silent": campaign["mention"]["silent"],
                "description": (
                    "A README that quotes injection strings for documentation "
                    "must not be flagged and must not fire the canary."
                ),
            },
            "content_preservation": {
                "deleted": False,
                "source_files_preserved": campaign["source_files_preserved"],
                "description": (
                    "Neutralisation copies a wrapped tree. Deleting the file "
                    "is not neutralization."
                ),
            },
            "downstream_behaviour": {
                "consumer": "tools/wfa_injection_gate/consumer.py",
                "independent_of_scanner_verdict": True,
                "ungated_plants_change_behaviour": True,
                "gated_plants_match_clean_side_effects": True,
            },
            "sensitive_diff": {
                "description": (
                    "A legitimate mechanism_id edit on a clean workflow changes "
                    "extracted tokens, proving the consumer is not a no-op."
                ),
                "observed": True,
            },
        },
        "negative_controls": [
            {
                "id": "ungated-plant-changes-behaviour",
                "kind": "known-broken-fixture",
                "description": (
                    "Disable the gate and feed the planted artefact to the "
                    "consumer; canary or autoload MUST fire."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ungated canary_obeyed or config_autoload",
                "good_state_output": "gated canary_obeyed=false config_autoload=false",
            },
            {
                "id": "mention-not-use",
                "kind": "use-versus-mention",
                "description": "Documentation quoting injection strings stays silent.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "USE findings on a planted ignore-previous file",
                "good_state_output": "mention README findings=[]",
            },
        ],
        "tests": [
            {"id": "named-probe1", "command": P1, "result": "PASS"},
            {"id": "named-probe2", "command": P2, "result": "PASS"},
            {"id": "library-tests", "command": TEST_CMD, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "WFA-0121-probe2-downstream-behaviour",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "lens": "security-reviewer+adversarial",
            "obligation": (
                "Attempt the named bypass (ungated plant reaching the consumer) "
                "and fail to achieve it against the gated artefact. Re-run the "
                "both-states control before PASS."
            ),
        },
        "artifacts": artifacts,
        "campaign": campaign,
        "residual_unknowns": [
            {
                "claim": (
                    "WFA-0020/0023/0024 sweep-lane artefacts are not on disk. "
                    "This unit gates a planted corpus that stands in for those "
                    "acquired surfaces (transcript, marketplace package, "
                    "workflow definition). Live sweep bytes were not re-fetched."
                ),
                "settling_experiment": (
                    "When those sweep reports land, run neutralise_tree over "
                    "their captured blobs and require the same consumer "
                    "side-effects to stay clean."
                ),
                "verdict": "NOT-CHECKED",
            },
            {
                "claim": (
                    "WFA-0001 wfa-schema-pack.json is absent, so this "
                    "RegressionFixture was not validated by python-jsonschema "
                    "2020-12 against the pack $def."
                ),
                "settling_experiment": "Re-validate this file after WFA-0001.",
                "verdict": "NOT-CHECKED",
            },
        ],
        "manifest_registration": {
            "manifest_path": (
                "command-center/p2-wave/probes/WFA-0121/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "registered": True,
            "derivation": "per-unit (not tools/command-center/unit_manifest.py --write)",
        },
        "notes": (
            "G-1 delivery of WFA-0121. Live named probes measure payload-class "
            "catch plus independent downstream behaviour. Did not run global "
            "unit_manifest.py --write. cloud ok is not consulted. No ADV rebuild. "
            + SENTINEL
        ),
    }

    if SENTINEL not in json.dumps(fixture):
        print("FAILED:WFA-0121 sentinel-absent before write")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(fixture, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    sha, size = digest(out)
    print(f"wrote {OUT} bytes={size} sha256={sha}")
    print(SENTINEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
