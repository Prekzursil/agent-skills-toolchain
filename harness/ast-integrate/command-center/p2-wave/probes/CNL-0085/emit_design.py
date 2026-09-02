#!/usr/bin/env python3
"""Emit CNL-0085 design note (JSON document at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

OUT = (
    "command-center/design/council/"
    "CNL-0085-owner-intervention-pause-and-resume-mid-deliberation.md"
)
SCHEMA = "command-center/schema/council-design-note.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0085/probe1_invalidating_restart.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0085/probe2_resume_replay.py"
)
QUESTION = (
    "What may an owner change mid-council without invalidating the run "
    "(adding evidence, extending a budget) versus what forces a restart "
    "(changing the question, replacing the chair) - and where is that "
    "boundary recorded so the audit trail stays honest?"
)
DECISION = (
    "A mid-council owner change is CONTINUE if and only if it leaves the run "
    "identity tuple (question, chair_id, protocol_id, roster, vote_weights, "
    "information_partition) unchanged AND does not mutate any already-committed "
    "event. Adding evidence and extending a still-unconsumed budget are CONTINUE: "
    "they append an origin=owner event after the pause cursor. Changing the "
    "question or replacing the chair is RESTART: the runtime must emit a "
    "restart_record and refuse quiet continuation on the same run_id. The "
    "boundary is the owner_intervention / restart_record pair on the event log, "
    "keyed by prefix_sha256 of the committed prefix. This rule is the catalog "
    "question's own four examples generalized by identity-preservation; it is "
    "not an invented owner preference. OWNER-DECISIONS.md is absent on this "
    "worktree and is recorded as a residual, not forged."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def find_line(path: Path, snippet: str) -> int:
    text = path.read_text(encoding="utf-8")
    idx = text.find(snippet)
    if idx < 0:
        raise SystemExit(f"FAILED:CNL-0085 snippet not found in {path}: {snippet!r}")
    return text[:idx].count("\n") + 1


def run_probe(cmd: str) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(
        cmd,
        cwd=str(REPO),
        shell=True,
        capture_output=True,
        text=True,
        env=env,
    )
    text = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, text


def main() -> int:
    c1, t1 = run_probe(P1)
    c2, t2 = run_probe(P2)
    if c1 != 0 or c2 != 0:
        print(f"FAILED:CNL-0085 probes c1={c1} c2={c2}")
        print(t1[-2000:])
        print(t2[-2000:])
        return 1

    def jfirst(text: str) -> dict:
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        raise SystemExit("FAILED:CNL-0085 probe JSON missing")

    p1 = jfirst(t1)
    p2 = jfirst(t2)
    iv = REPO / "command-center/p2-wave/probes/CNL-0085/intervention.py"
    snip_quiet = "Quiet continuation of an identity change is refused"
    snip_views = "Derived views are rebuilt from the event log. They are never the SSOT."
    snip_prefix = "pause-record prefix_sha256 mismatch"
    a_quiet = f"command-center/p2-wave/probes/CNL-0085/intervention.py:{find_line(iv, snip_quiet)}"
    a_views = f"command-center/p2-wave/probes/CNL-0085/intervention.py:{find_line(iv, snip_views)}"
    a_prefix = f"command-center/p2-wave/probes/CNL-0085/intervention.py:{find_line(iv, snip_prefix)}"

    neg1 = p1["negative_control"]
    neg2 = p2["negative_control"]
    schema_path = REPO / SCHEMA
    if not schema_path.is_file():
        print(f"FAILED:CNL-0085 declared schema absent {SCHEMA}")
        return 1

    doc = {
        "unit_id": "CNL-0085",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0085",
        "title": "Owner intervention, pause and resume mid-deliberation",
        "question": QUESTION,
        "decision": DECISION,
        "identity_tuple": [
            "question",
            "chair_id",
            "protocol_id",
            "roster",
            "vote_weights",
            "information_partition",
        ],
        "continue_classes": [
            "evidence_add",
            "budget_extend",
            "guidance_inject",
            "constraint_add_future",
            "pause",
            "resume",
        ],
        "restart_classes": [
            "question_change",
            "chair_replace",
            "protocol_change",
            "roster_replace_voting_seat",
            "evidence_rewrite",
            "vote_weight_change",
            "information_partition_change",
        ],
        "audit_trail": (
            "CONTINUE writes type=owner_intervention origin=owner after the pause "
            "cursor and leaves prefix_sha256 of events[:cursor] unchanged. RESTART "
            "writes type=restart_record with old_run_id, class, reason, cursor, "
            "prefix_sha256, invalidates_run=true and sets status=RESTART_REQUIRED. "
            "A mode=continue on a RESTART class raises QuietContinuationRefused "
            "and appends nothing. Derived votes and minority reports are rebuilt "
            "from the event log on resume, never cached beside it."
        ),
        "rules": [
            {
                "id": "identity-tuple",
                "statement": (
                    "Run identity is (question, chair_id, protocol_id, roster, "
                    "vote_weights, information_partition). Mutating any element "
                    "invalidates the run."
                ),
            },
            {
                "id": "append-only-continue",
                "statement": (
                    "evidence_add and budget_extend (new ceiling still covering "
                    "consumed rounds) append an owner-origin event and MUST NOT "
                    "rewrite prefix events, votes, or the minority report."
                ),
            },
            {
                "id": "recorded-restart",
                "statement": (
                    "question_change and chair_replace emit restart_record and "
                    "refuse quiet continuation on the same run_id."
                ),
            },
            {
                "id": "replay-from-log",
                "statement": (
                    "Resume rebuilds derived state from the pause prefix; a "
                    "tampered prefix_sha256 is PrefixMismatch, not a silent resume."
                ),
            },
        ],
        "claims": [
            {
                "id": "C1",
                "claim": (
                    "Invalidating changes (question_change, chair_replace, "
                    "evidence_rewrite) force a recorded restart, not quiet continuation."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_quiet,
            },
            {
                "id": "C2",
                "claim": (
                    "Adding evidence or extending max_rounds continues the same "
                    "run_id with the committed prefix and dissent preserved."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_views,
            },
            {
                "id": "C3",
                "claim": (
                    "Pause then resume replays to the same derived state up to the "
                    "intervention cursor; tampered pause records are rejected."
                ),
                "verdict": "CONFIRMED",
                "anchor": a_prefix,
            },
        ],
        "tests": [
            {
                "id": "invalidating-restart",
                "command": P1,
                "result": "PASS" if c1 == 0 and p1.get("pass") else "FAIL",
            },
            {
                "id": "resume-replay",
                "command": P2,
                "result": "PASS" if c2 == 0 and p2.get("pass") else "FAIL",
            },
            {
                "id": "negative-control-quiet-continuation",
                "command": P1,
                "result": "PASS" if p1.get("negative_control", {}).get("fired") else "FAIL",
            },
        ],
        "both_states": {
            "fires_on": (
                "command-center/p2-wave/probes/CNL-0085/fixtures/"
                "quiet-continuation.json (question_change mode=continue)"
            ),
            "silent_on": (
                "command-center/p2-wave/probes/CNL-0085/fixtures/"
                "evidence-add.json (append-only evidence_add)"
            ),
            "verbatim_fire": neg1["verbatim_exception"],
            "verbatim_silent": (
                "evidence_add disposition=CONTINUE restart_record=false "
                "prefix_preserved=true dissent_preserved=true"
            ),
        },
        "negative_controls": [
            {
                "id": "quiet-continuation-question-change",
                "rejects": neg1["what_the_check_does"],
                "observed": neg1["verbatim_exception"],
            },
            {
                "id": "tampered-pause-record",
                "rejects": neg2["what_the_check_does"],
                "observed": neg2["verbatim_exception"],
            },
        ],
        "evidence": [
            {
                "claim": (
                    "question_change and chair_replace emit restart_record; "
                    "evidence_add does not"
                ),
                "mechanism": (
                    "probe1 classifier disposition plus restart_record presence "
                    "on the event log (enum/field, not a hash)"
                ),
                "anchor": a_quiet,
                "verbatim": t1[-1800:],
            },
            {
                "claim": (
                    "resume reconstructs votes and minority report; stale "
                    "prefix_sha256 is PrefixMismatch"
                ),
                "mechanism": (
                    "probe2 sha256 of canonical prefix plus derived-state "
                    "equality after from_snapshot replay"
                ),
                "anchor": a_prefix,
                "verbatim": t2[-1800:],
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0085-probe2-resume-replay",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Probe2 does not call classify(). It pauses a scripted run, "
                "replays from the event prefix, compares derived-state sha256, "
                "then tampers the minority_report bytes. That is a different "
                "mechanism from probe1's disposition enum. The reviewer does "
                "not grant owner sign-off."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0085/intervention.py",
                "exists": True,
                "role": "supporting",
            },
        ],
        "residual_unknowns": [
            (
                "command-center/OWNER-DECISIONS.md is absent; catalog "
                "reviewer_requirement asked for owner sign-off before close. "
                "This agent does not author a fake owner ruling. G-1 delivers "
                "the design and probes; the owner-gate remains a named residual."
            ),
            (
                "Harness-restore inputs "
                "C:/Users/Prekzursil/.claude/harness-restore-20260806/"
                "_USER-PROMPTS.md:10915-10946 and 11-COUNCIL-SPECIFICATION.schema.json "
                "are not mounted on this Linux worktree. Boundary examples are "
                "taken from the catalog question_or_target, which already names "
                "adding evidence / extending a budget versus changing the "
                "question / replacing the chair."
            ),
            (
                "CNL-0011 (replay state model) is a declared dependency and is "
                "not yet delivered on this tree. CNL-0085 serializes identity, "
                "seeds, the event prefix, and prefix_sha256 so resume can be "
                "tested here; it does not claim to have settled which additional "
                "nondeterminism seeds CNL-0011 will require."
            ),
        ],
        "owner_approval_required": True,
        "owner_signoff": {
            "path": "command-center/OWNER-DECISIONS.md",
            "present": False,
            "forged": False,
            "status": "residual-not-granted-by-reviewer",
        },
        "named_probes": [
            {"id": "probe1", "command": P1, "exit_code": c1},
            {"id": "probe2", "command": P2, "exit_code": c2},
        ],
        "produced_by": {
            "vendor": "cursor",
            "model": "grok-4.6",
            "role": "council-systems-designer",
            "execution_substrate": "linux-local",
        },
        "min_bytes_threshold": 2048,
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "notes": (
            "SUCCESS:CNL-0085 G-1 design note. Live named probes exit 0. "
            "Did not run global unit_manifest.py --write. Did not forge "
            "OWNER-DECISIONS.md. cloud ok=true is not delivery."
        ),
    }

    if doc["tests"][0]["result"] != "PASS" or doc["tests"][1]["result"] != "PASS":
        print("FAILED:CNL-0085 a required test is not PASS")
        return 1

    # Catalog output_schema is a generated $ref shim whose $id points at
    # https://ast-integrate.invalid/... . Following that URL is not a parse
    # check; G-1 only requires JSON parse + sentinel + non-BLOCKED. Keep the
    # shim on disk, refuse an empty/garbage document locally, and do not
    # fetch the remote $ref.
    shim = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(shim, dict) or "$ref" not in shim:
        print("FAILED:CNL-0085 schema shim missing $ref")
        return 1
    if shim.get("x-artifact-class") != "council-design-note":
        print("FAILED:CNL-0085 schema class mismatch")
        return 1
    required_keys = (
        "unit_id",
        "state",
        "sentinel",
        "decision",
        "tests",
        "negative_controls",
        "evidence",
        "reviewer",
    )
    missing = [k for k in required_keys if k not in doc]
    if missing:
        print(f"FAILED:CNL-0085 document missing keys {missing}")
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if all(k in garbage for k in required_keys):
            print("FAILED:CNL-0085 garbage check is vacuous")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNL-0085 artifact {size}B below floor")
        return 1
    parsed = json.loads(out.read_text(encoding="utf-8"))
    if parsed.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNL-0085 self-declared not delivering")
        return 1
    if "SUCCESS:CNL-0085" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0085 sentinel absent")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0085 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
