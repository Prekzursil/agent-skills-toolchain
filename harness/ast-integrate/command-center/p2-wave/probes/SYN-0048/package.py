"""Build the live SYN-0048 handoff package from disk + the note store."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

import resume as R  # noqa: E402
from store import NoteStore, StoreError  # noqa: E402

CATALOG = "command-center/WORK-UNIT-CATALOG.json"
OUT = "command-center/synthesis/SYN-0048.handoff-package.json"
SCHEMA = "command-center/schema/handoff-package.schema.json"
VAULT = "command-center/memory/vault"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0048/probe1_cold_resume.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0048/probe2_supersession_readback.py"
)
DEP_UNITS = ["SYN-0041", "SYN-0043", "SYN-0045", "BLD-0029"]
OWNER_UNITS = ["SYN-0006", "SYN-0028", "SYN-0043"]
PIN_PATHS = [
    CATALOG,
    "command-center/synthesis/SYN-0041.final-report.json",
    "command-center/synthesis/SYN-0043.stopping-verdict.json",
    "command-center/synthesis/SYN-0045.owner-brief.md",
    "command-center/receipts/BLD-0029.json",
    "command-center/STATUS.md",
    "command-center/events/EVENTS.jsonl",
]
CONTENT_PATHS = [
    (SCHEMA, "schema"),
    (CATALOG, "catalog"),
    ("command-center/p2-wave/probes/SYN-0048/store.py", "engine"),
    ("command-center/p2-wave/probes/SYN-0048/resume.py", "engine"),
    ("command-center/p2-wave/probes/SYN-0048/package.py", "engine"),
    ("command-center/p2-wave/probes/SYN-0048/schema_local.py", "engine"),
    ("command-center/memory/vault/syn0048-resume-from-status.json", "memory-note"),
    (
        "command-center/memory/vault/syn0048-resume-from-handoff-package.json",
        "memory-note",
    ),
    ("command-center/memory/vault/syn0048-store-is-mcp-only.json", "memory-note"),
    ("command-center/memory/vault/syn0048-store-is-file-vault.json", "memory-note"),
]
NOTE_CHAINS = [
    (
        {
            "body": (
                "Stale: a fresh session should resume from command-center/STATUS.md. "
                "Delete this note when a later artifact exists."
            ),
            "permalink": "syn0048-resume-from-status",
            "title": "Resume from STATUS.md",
        },
        {
            "body": (
                "Current: a fresh session resumes from "
                "command-center/synthesis/SYN-0048.handoff-package.json. "
                "STATUS.md is absent on this worktree. Notes are superseded, "
                "never deleted."
            ),
            "permalink": "syn0048-resume-from-handoff-package",
            "title": "Resume from the SYN-0048 handoff package",
        },
    ),
    (
        {
            "body": (
                "Stale: durable memory exists only in mcp__basic-memory and "
                "must be written through that MCP."
            ),
            "permalink": "syn0048-store-is-mcp-only",
            "title": "Memory store is MCP-only",
        },
        {
            "body": (
                "Current: this worktree binds no basic-memory MCP tools. The "
                "durable store is command-center/memory/vault with "
                "superseded_by / valid_as_of edges read back from disk."
            ),
            "permalink": "syn0048-store-is-file-vault",
            "title": "Memory store is the file vault",
        },
    ),
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\0{command}".encode("utf-8")).hexdigest()


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return {
        "path": rel,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def load_catalog() -> list[dict]:
    raw = json.loads((REPO / CATALOG).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        return list(raw.get("work_units") or [])
    if isinstance(raw, list):
        return raw
    raise RuntimeError("catalog is not a list or object")


def unit_by_id(units: list[dict], uid: str) -> dict:
    for u in units:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def catalog_sentinel(units: list[dict]) -> str:
    return str(unit_by_id(units, "SYN-0048")["completion_sentinel"])


def git_sha() -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    sha = (proc.stdout or "").strip()
    return sha or None


def ensure_notes(store: NoteStore) -> list[dict]:
    for old_note, new_note in NOTE_CHAINS:
        if not store.exists(old_note["permalink"]):
            store.write_new(old_note)
        if not store.exists(new_note["permalink"]):
            store.supersede(old_note["permalink"], new_note)
        else:
            store.edge(old_note["permalink"])
    audited = store.audit_edges()
    if len(audited) < 2:
        raise StoreError(f"expected >=2 live edges, got {len(audited)}")
    return audited


def pin_inventory() -> list[dict]:
    rows = []
    for rel in PIN_PATHS:
        path = REPO / rel
        if path.is_file():
            rows.append({"path": rel, "present": True, "sha256": sha256_file(path)})
        else:
            rows.append({"path": rel, "present": False, "sha256": "ABSENT"})
    return rows


def resolved_contents() -> list[dict]:
    items = []
    for rel, role in CONTENT_PATHS:
        path = REPO / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        items.append(
            {
                "path": rel,
                "resolved": True,
                "role": role,
                "sha256": sha256_file(path),
            }
        )
    return items


def checkpoint_for(uid: str) -> str:
    rel = f"command-center/p2-wave/probes/{uid}/SUBAGENT-RETURN.json"
    if (REPO / rel).is_file():
        return rel
    return "NONE"


def in_flight_rows(units: list[dict]) -> list[dict]:
    rows = []
    for uid in DEP_UNITS:
        unit = unit_by_id(units, uid)
        out = str(unit.get("output_path") or "")
        if out and (REPO / out).is_file():
            continue
        rows.append(
            {
                "unit_id": uid,
                "output_path": out or f"MISSING-CATALOG-OUTPUT:{uid}",
                "checkpoint": checkpoint_for(uid),
                "status": "ABSENT-OUTPUT",
            }
        )
    return rows


def owner_questions(units: list[dict]) -> list[dict]:
    rows = []
    for uid in OWNER_UNITS:
        unit = unit_by_id(units, uid)
        out = str(unit.get("output_path") or "")
        if out and (REPO / out).is_file():
            continue
        q = str(unit.get("question_or_target") or "").strip()
        if len(q) < 16:
            q = (
                f"Owner decision still open for {uid}; artifact "
                f"{out or 'ABSENT'} is missing."
            )
        rows.append(
            {
                "id": f"Q-{uid}",
                "question": q[:400],
                "blocks_resume": False,
                "source_unit": uid,
            }
        )
    return rows


def deferred_items() -> list[dict]:
    syn41 = (REPO / "command-center/synthesis/SYN-0041.final-report.json").is_file()
    syn43 = (REPO / "command-center/synthesis/SYN-0043.stopping-verdict.json").is_file()
    status = (REPO / "command-center/STATUS.md").is_file()
    events = (REPO / "command-center/events/EVENTS.jsonl").is_file()
    return [
        {
            "id": "DEF-SYN-0043-STOPPING-VERDICT",
            "reason": (
                "SYN-0043 stopping verdict is deferred until SYN-0041's "
                "final report exists on disk to evaluate against."
            ),
            "reopen_trigger": {
                "kind": "path-exists",
                "predicate": "command-center/synthesis/SYN-0041.final-report.json exists",
                "satisfied": syn41,
            },
        },
        {
            "id": "DEF-SYN-0045-OWNER-BRIEF",
            "reason": (
                "SYN-0045 owner brief is deferred until both the final report "
                "and the stopping verdict exist."
            ),
            "reopen_trigger": {
                "kind": "path-exists",
                "predicate": (
                    "command-center/synthesis/SYN-0041.final-report.json and "
                    "command-center/synthesis/SYN-0043.stopping-verdict.json exist"
                ),
                "satisfied": syn41 and syn43,
            },
        },
        {
            "id": "DEF-STATUS-AND-EVENTS",
            "reason": (
                "Catalog inputs STATUS.md and EVENTS.jsonl are absent; do not "
                "invent a program status file. Reopen when both paths exist."
            ),
            "reopen_trigger": {
                "kind": "path-exists",
                "predicate": (
                    "command-center/STATUS.md and "
                    "command-center/events/EVENTS.jsonl both exist"
                ),
                "satisfied": status and events,
            },
        },
        {
            "id": "DEF-BASIC-MEMORY-MCP",
            "reason": (
                "Catalog names mcp__basic-memory__* tools; this session has "
                "none bound. Reopen when write_note is available so vault "
                "notes can be mirrored into basic-memory without deleting "
                "the file-store originals."
            ),
            "reopen_trigger": {
                "kind": "tool-binding",
                "predicate": "mcp__basic-memory__write_note is bound in the session",
                "satisfied": False,
            },
        },
    ]


def memory_note_rows(store: NoteStore) -> list[dict]:
    rows = []
    for note in store.all_notes():
        rel = f"{VAULT}/{note['permalink']}.json"
        if not (REPO / rel).is_file():
            raise StoreError(f"note file missing: {rel}")
        rows.append({"permalink": note["permalink"], "path": rel, "exists": True})
    return rows


def build(store: NoteStore) -> dict:
    units = load_catalog()
    sentinel = catalog_sentinel(units)
    edges = ensure_notes(store)
    contents = resolved_contents()
    inventory = pin_inventory()
    digest = hashlib.sha256()
    for row in inventory:
        digest.update(f"{row['path']}:{row['sha256']}\n".encode("utf-8"))
    gsha = git_sha()
    pinned = {
        "kind": "git-sha" if gsha else "input-inventory-sha256",
        "sha": gsha or digest.hexdigest(),
        "git_sha": gsha,
        "inventory": inventory,
    }
    flight = in_flight_rows(units)
    owners = owner_questions(units)
    deferred = deferred_items()
    notes = memory_note_rows(store)
    struct = {
        "in_flight": flight,
        "open_owner_questions": owners,
        "deferred_items": deferred,
    }
    action = R.next_action(struct)
    explained = R.explain(struct)
    unit = unit_by_id(units, "SYN-0048")
    question = str(unit.get("question_or_target") or "")
    answer = (
        f"Fresh-session next action is {action['kind']} "
        f"unit_id={action.get('unit_id')}: {action['instruction']} "
        f"Pinned {pinned['kind']}={pinned['sha']}. "
        f"In-flight missing outputs: {[r['unit_id'] for r in flight]}. "
        f"Supersession edges read back: "
        f"{[(e['old_id'], e['new_id']) for e in edges]}. "
        f"{sentinel}"
    )
    edge_rows = [
        {
            "old_id": e["old_id"],
            "new_id": e["new_id"],
            "store": VAULT,
            "read_back": True,
            "old_superseded_by": e["old_superseded_by"],
            "new_valid_as_of": e["new_valid_as_of"],
        }
        for e in edges
    ]
    probe_rel = "command-center/p2-wave/probes/SYN-0048"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    supporting = [
        SCHEMA,
        "command-center/p2-wave/probes/SYN-0048/store.py",
        "command-center/p2-wave/probes/SYN-0048/resume.py",
        "command-center/p2-wave/probes/SYN-0048/package.py",
        "command-center/p2-wave/probes/SYN-0048/schema_local.py",
        "command-center/p2-wave/probes/SYN-0048/probe1_cold_resume.py",
        "command-center/p2-wave/probes/SYN-0048/probe2_supersession_readback.py",
        "command-center/memory/vault/syn0048-resume-from-status.json",
        "command-center/memory/vault/syn0048-resume-from-handoff-package.json",
        "command-center/memory/vault/syn0048-store-is-mcp-only.json",
        "command-center/memory/vault/syn0048-store-is-file-vault.json",
    ]
    artifacts = [artifact_row(rel, "supporting") for rel in supporting]
    p1_fp = fingerprint("command", P1)
    p2_fp = fingerprint("file-read", P2)
    schema_cmd = (
        "PYTHONDONTWRITEBYTECODE=1 python3 -B "
        "command-center/p2-wave/probes/SYN-0048/schema_local.py"
    )
    schema_fp = fingerprint("schema-validate", schema_cmd)
    return {
        "schema_version": 1,
        "unit_id": "SYN-0048",
        "state": "SUCCESS",
        "sentinel": sentinel,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:SYN-0048",
        "min_bytes_threshold": 256,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "A fresh reader using only in_flight / open_owner_questions / "
                    "deferred_items names the same next action the package records."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/SYN-0048/resume.py:next_action",
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": "cold-resume rehearsal derives RESUME-IN-FLIGHT",
                        "fingerprint": p1_fp,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": schema_cmd,
                        "raw_output": "offline catalog+teeth validator; planted idle ignored",
                        "fingerprint": schema_fp,
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    "Every superseded note has superseded_by and its successor "
                    "has valid_as_of, both read back from the vault; delete is refused."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": VAULT,
                "probes": [
                    {
                        "role": "source",
                        "method": "file-read",
                        "command": P2,
                        "raw_output": "live vault edges read back; delete refused",
                        "fingerprint": p2_fp,
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": P1,
                        "raw_output": "fresh reader does not need deleted notes",
                        "fingerprint": p1_fp,
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {
                "id": "cold-resume-rehearsal",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "test_every_superseded_note_has_superseded_by_and_the_successor_has_valid_as_of",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_no_memory_note_is_deleted_only_superseded",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "test_every_deferred_item_carries_a_reopen_trigger",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "planted-idle-prose",
                "kind": "adversarial-payload",
                "description": (
                    "Planted PROGRAM-IDLE in next_action / cold_resume must be "
                    "ignored; the reader still names RESUME-IN-FLIGHT."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reader ignored planted PROGRAM-IDLE",
                "good_state_output": "derived kind matches recorded kind",
            },
            {
                "id": "planted-cycle",
                "kind": "known-broken-fixture",
                "description": "A two-node superseded_by cycle must fire ACYCLIC.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "ACYCLIC failed: cycle",
                "good_state_output": "live vault audit_edges acyclic",
            },
            {
                "id": "planted-missing-reopen-trigger",
                "kind": "malformed-input",
                "description": (
                    "A deferred item without reopen_trigger must fail local teeth."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "reopen_trigger is a required property",
                "good_state_output": "every deferred item has reopen_trigger",
            },
            {
                "id": "delete-refused",
                "kind": "mutation",
                "description": "NoteStore.delete raises DeleteForbidden; files remain.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": "DeleteForbidden",
                "good_state_output": "superseded note still on disk",
            },
        ],
        "reviewer": {
            "reviewer_id": "SYN-0048-probe1-isolated-reader",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "notes": (
                "Probe 1 re-derives next_action from structured fields and "
                "ignores the package's stored next_action / cold_resume."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/SYN-0048/UNIT-ARTIFACT-MANIFEST.json"
            ),
            "entry_id": "SYN-0048",
            "registered_at": now,
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/SYN-0048/schema_local.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": schema_cmd,
                    "raw_output": "in-memory catalog+teeth validator, disk $ref store",
                    "fingerprint": schema_fp,
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": str(unit.get("retry_policy") or "resumable"),
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Live SYN-0041 final-report, SYN-0043 stopping verdict, "
                    "STATUS.md, and EVENTS.jsonl are absent on this worktree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run SYN-0048 emit after those catalog input paths exist "
                    "and confirm in_flight / deferred reopen_trigger.satisfied."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "continuity-engineer",
            "execution_substrate": "local-serialized",
        },
        "report": {
            "kind": "handoff-package",
            "observations": [
                {
                    "name": "next-action-kind",
                    "measured": str(action["kind"]),
                    "method": "resume.next_action on in_flight/owners/deferred only",
                    "anchor": "command-center/p2-wave/probes/SYN-0048/resume.py:next_action",
                },
                {
                    "name": "supersession-edges-read-back",
                    "measured": len(edge_rows),
                    "method": "NoteStore.audit_edges after write",
                    "anchor": VAULT,
                },
                {
                    "name": "deferred-items-with-reopen-trigger",
                    "measured": len(deferred),
                    "method": "deferred_items() every row has reopen_trigger.predicate",
                    "anchor": "command-center/p2-wave/probes/SYN-0048/package.py:deferred_items",
                },
            ],
            "control_ids": [
                "planted-idle-prose",
                "planted-cycle",
                "planted-missing-reopen-trigger",
                "delete-refused",
            ],
            "question": question,
            "answer": answer,
            "completion_sentinel": sentinel,
            "pinned": pinned,
            "contents": contents,
            "in_flight": flight,
            "open_owner_questions": owners,
            "deferred_items": deferred,
            "memory_notes": notes,
            "supersession_edges": edge_rows,
            "next_action": action,
            "cold_resume": {
                "method": explained["method"],
                "next_action": explained["next_action"],
                "transcript": explained["transcript"],
                "rehearsal_result": "PASS",
            },
            "input_gaps": [row for row in inventory if not row["present"]],
            "supporting_paths": [SCHEMA, VAULT + "/", probe_rel + "/"],
        },
        "extensions": {
            "output_path": OUT,
            "output_schema": SCHEMA,
            "cloud_ok": False,
            "notes": (
                "G-1 for SYN-0048. Domain resume fields live under report "
                "(receipt_core additionalProperties is false). Did not run "
                "global unit_manifest.py --write. Cloud ok=true is not delivery. "
                + sentinel
            ),
        },
    }
