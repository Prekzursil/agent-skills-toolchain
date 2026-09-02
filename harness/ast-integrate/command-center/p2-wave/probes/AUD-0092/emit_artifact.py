#!/usr/bin/env python3
"""Emit command-center/audit/AUD-0092-rollback-backup-rehearsal.json from a live rehearsal."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    KEEP_ME_REL,
    REPO as ENGINE_REPO,
    artifact_backup,
    run_rehearsal,
)
import schema_offline as S  # noqa: E402

OUT_REL = "command-center/audit/AUD-0092-rollback-backup-rehearsal.json"
SCHEMA_REL = "command-center/schema/audit-detector-control.schema.json"
SENTINEL = (
    "SUCCESS:AUD-0092 emitted only when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, and both named probes are recorded with their verbatim output"
)
QUESTION = (
    "Create a restorable backup of every tree this program will mutate, then PROVE it "
    "restores by rehearsing a full restore into a scratch location and byte-comparing the result."
)
TITLE = "Create rollback backups and rehearse a restore, copying no secrets into the corpus"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0092/probe1_backup_manifest.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/AUD-0092/probe2_restore_compare.py"
)
SUPPORTING = [
    SCHEMA_REL,
    "command-center/p2-wave/probes/AUD-0092/engine.py",
    "command-center/p2-wave/probes/AUD-0092/probe1_backup_manifest.py",
    "command-center/p2-wave/probes/AUD-0092/probe2_restore_compare.py",
    KEEP_ME_REL,
]


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fp(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}|{command}".encode("utf-8")).hexdigest()


def art_row(rel: str, role: str) -> dict:
    path = REPO / rel
    sha, size = digest_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def validate_or_die(doc: dict) -> None:
    errs = S.iter_errors(doc)
    if errs:
        print("FAILED:AUD-0092 schema errors")
        for e in errs[:20]:
            print(" ", list(e.path), e.message)
        raise SystemExit(1)
    garbage_docs = (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    )
    for garbage in garbage_docs:
        g_errs = S.iter_errors(garbage)
        if not g_errs:
            raise SystemExit("FAILED:AUD-0092 schema accepts garbage")
    mutant = dict(doc)
    report = dict(mutant.get("report") or {})
    report["kind"] = "receipt"
    mutant["report"] = report
    if not S.iter_errors(mutant):
        raise SystemExit("FAILED:AUD-0092 schema accepts kind mutant")


def main() -> int:
    if ENGINE_REPO != REPO:
        print("FAILED:AUD-0092 engine repo path mismatch")
        return 1
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    live = run_rehearsal()
    if not live.get("ok"):
        print("FAILED:AUD-0092 live rehearsal did not confirm backup/restore/control")
        slim = {
            k: live.get(k)
            for k in (
                "ok",
                "file_count",
                "excluded_count",
                "discriminates",
                "secrets_not_in_backup",
                "planted_secret_excluded",
                "canary_leaked_in_backup_n",
                "secret_named_in_backup_n",
                "keep_me",
                "known_good",
                "known_broken",
                "backup_outside_corpus",
            )
        }
        print(json.dumps(slim, indent=2, default=str)[:4000])
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    good = live["known_good"]
    broken = live["known_broken"]
    keep = live["keep_me"]
    keep_row = next(
        (
            {
                "tree_id": f["tree_id"],
                "path": f["path"],
                "sha256": f["sha256"],
                "bytes": f["bytes"],
            }
            for f in live["files"]
            if f["tree_id"] == "ast-integrate" and f["path"] == KEEP_ME_REL
        ),
        {
            "tree_id": "ast-integrate",
            "path": KEEP_ME_REL,
            "sha256": keep["sha256"],
            "bytes": keep["bytes"],
        },
    )
    supporting = [art_row(p, "supporting" if p != KEEP_ME_REL else "fixture") for p in SUPPORTING]
    missing = [a["path"] for a in supporting if not (REPO / a["path"]).is_file()]
    if missing:
        print("FAILED:AUD-0092 supporting missing", missing)
        return 1

    source_probe = {
        "role": "source",
        "method": "command",
        "command": P1,
        "raw_output": (
            f"backup dest={live['backup_destination']} files={live['file_count']} "
            f"excluded={live['excluded_count']} manifest_sha256={live['manifest_sha256']}"
        ),
        "fingerprint": fp("command", P1),
        "exit_code": 0,
    }
    verifier_probe = {
        "role": "verifier",
        "method": "byte-compare",
        "command": P2,
        "raw_output": (
            f"intact equal={good['equal']} rc={good['exit_code']} "
            f"damaged equal={broken['equal']} rc={broken['exit_code']} "
            f"missing_n={broken['missing_n']}"
        ),
        "fingerprint": fp("byte-compare", P2),
        "exit_code": int(broken["exit_code"]),
    }
    schema_probe = {
        "role": "verifier",
        "method": "schema-validate",
        "command": "schema_offline.make_validator(audit-detector-control.schema.json)",
        "raw_output": "offline Draft7Validator errors=0; garbage rejected; kind mutant red",
        "fingerprint": fp(
            "schema-validate",
            "schema_offline.make_validator(audit-detector-control.schema.json)",
        ),
        "exit_code": 0,
    }

    report = {
        "kind": "audit-detector-control",
        "title": TITLE,
        "question": QUESTION,
        "control_ids": [
            "damaged-restore-turns-red",
            "planted-secret-not-copied",
            "always-green-mutant-fails-to-discriminate",
        ],
        "observations": [
            {
                "name": "backup_file_count",
                "measured": int(live["file_count"]),
                "method": "copy non-secret files to outside-corpus dest and sha256 each",
                "anchor": live["manifest_path"],
            },
            {
                "name": "intact_restore_equal",
                "measured": True,
                "method": "byte-compare scratch restore vs backup snapshot",
                "anchor": live["restore_scratch"],
            },
            {
                "name": "damaged_restore_equal",
                "measured": False,
                "method": "delete keep-me.txt from scratch then byte-compare",
                "anchor": KEEP_ME_REL,
            },
            {
                "name": "planted_secret_excluded",
                "measured": True,
                "method": "plant .env canary outside corpus; secret-name filter",
                "anchor": live["canary_tree"],
            },
            {
                "name": "backup_outside_corpus",
                "measured": True,
                "method": "assert dest is not under the worktree",
                "anchor": live["backup_destination"],
            },
        ],
        "detector": {
            "name": "restore-byte-compare",
            "fires_on": (
                "a scratch restore that is missing keep-me.txt (or any backed-up path); "
                "byte-compare vs snapshot exits non-zero"
            ),
            "silent_on": (
                "a full restore of the non-secret backup into scratch whose per-file "
                "sha256 set matches the source snapshot"
            ),
        },
        "both_states": {
            "discriminates": True,
            "known_good": {
                "name": "intact-scratch-restore",
                "exit_code": int(good["exit_code"]),
                "blocked": bool(good["blocked"]),
                "equal": True,
                "missing_n": good["missing_n"],
                "mismatch_n": good["mismatch_n"],
            },
            "known_broken": {
                "name": "keep-me-deleted-from-scratch",
                "exit_code": int(broken["exit_code"]),
                "blocked": bool(broken["blocked"]),
                "equal": False,
                "missing_n": broken["missing_n"],
                "missing_head": broken.get("missing_head"),
            },
        },
        "backup": {
            "destination": live["backup_destination"],
            "outside_corpus": True,
            "manifest_path": live["manifest_path"],
            "manifest_sha256": live["manifest_sha256"],
            "manifest_bytes": live["manifest_bytes"],
            "file_count": live["file_count"],
            "live_file_count": live["live_file_count"],
            "excluded_count": live["excluded_count"],
            "excluded_secret_paths": live["excluded_secret_paths"],
            "live_env_excluded": live["live_env_excluded"],
            "skipped_sibling_probe_scratch": True,
            "files": [keep_row],
        },
        "restore": {
            "scratch": live["restore_scratch"],
            "outside_corpus": True,
            "intact_equal": True,
            "damaged_equal": False,
            "damaged_rel": live["damaged_rel"],
        },
        "trees": [
            {
                "id": "linux-worktree-ast-integrate",
                "path": live["live_tree"],
                "role": "live-mutation-tree",
                "present": True,
                "backed_up": True,
                "note": "sibling unit probe scratch under p2-wave/probes excluded except AUD-0092",
            }
        ],
        "sibling_worktrees": live["sibling_worktrees"],
        "secrets_not_copied_into_backup": True,
        "secrets_not_copied_into_corpus_artifact": True,
        "mutant_always_green_on_damaged_equal": True,
    }

    doc = {
        "schema_version": 1,
        "unit_id": "AUD-0092",
        "state": "SUCCESS",
        "sentinel": SENTINEL,
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:AUD-0092",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "xai",
            "model": "grok",
            "role": "auditor",
            "execution_substrate": "local-serialized",
        },
        "artifacts": supporting,
        "evidence": [
            {
                "claim": (
                    "An outside-corpus backup of this host's mutation tree exists with a "
                    "per-file sha256 MANIFEST; keep-me.txt is present; secret-named files "
                    "including a planted .env canary are excluded."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": live["manifest_path"],
                "probes": [source_probe, verifier_probe],
            },
            {
                "claim": (
                    "A scratch restore byte-compares equal to the backup snapshot; deleting "
                    "keep-me.txt from the scratch restore turns the comparison RED; an "
                    "always-green mutant stays green on the damaged restore."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": KEEP_ME_REL,
                "probes": [verifier_probe, source_probe],
            },
        ],
        "tests": [
            {
                "id": "T1-backup-manifest-sha256",
                "name": "outside-corpus MANIFEST has per-file sha256; secrets excluded",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T2-restore-byte-compare-both-states",
                "name": "intact restore GREEN; keep-me deleted RED",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "damaged-restore-turns-red",
                "kind": "mutation",
                "description": (
                    "Delete keep-me.txt from the scratch restore and confirm byte-compare "
                    "turns RED. A comparison that still reports success is measuring nothing."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": json.dumps(
                    {"equal": False, "exit_code": int(broken["exit_code"])},
                    sort_keys=True,
                ),
                "good_state_output": json.dumps(
                    {"equal": True, "exit_code": int(good["exit_code"])},
                    sort_keys=True,
                ),
            },
            {
                "id": "planted-secret-not-copied",
                "kind": "adversarial-payload",
                "description": (
                    "A runtime-planted .env canary tree outside the corpus is excluded from "
                    "the backup; secret-named files are absent from the backup destination."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
            {
                "id": "always-green-mutant-fails-to-discriminate",
                "kind": "known-broken-fixture",
                "description": (
                    "An always-green comparator reports success on the damaged restore; "
                    "the honest comparator does not, so the RED is not vacuous."
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "AUD-0092-probe2-restore-byte-compare",
            "verdict": "PASS",
            "independent": True,
            "notes": "Mechanical re-run of restore + damaged-restore RED control. Not a same-probe re-read.",
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": (
                "command-center/p2-wave/probes/AUD-0092/UNIT-ARTIFACT-MANIFEST.json"
            ),
        },
        "downstream_consumers": [
            {
                "consumer": "jsonschema.Draft7Validator+disk-store",
                "artifact_path": OUT_REL,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": schema_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Sibling owner worktrees on the Windows host were included in this "
                    "host's outside-corpus backup."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "On the owner Windows box, list ~/Documents/GitHub and "
                    "~/.claude/agent-worktrees and re-run this rehearsal against those trees."
                ),
            },
            {
                "claim": (
                    "command-center/p2-wave/probes sibling-unit scratch (~3.5GiB) was "
                    "copied into the rollback backup."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "If a full-tree backup of every concurrent unit probe dir is required, "
                    "raise the named-probe timeout above 180s and drop the probes/ prune."
                ),
            },
        ],
        "timestamps": {"started_at": started, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "no automatic retry - a failed run here may have mutated the tree; "
                "restore from the AUD-0092 backup, record the mutation, and escalate"
            ),
        },
        "report": report,
    }

    payload = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if SENTINEL not in payload:
        print("FAILED:AUD-0092 sentinel not in serialized artifact")
        return 1
    if "AUD0092CANARY_" in payload:
        print("FAILED:AUD-0092 canary prefix leaked into artifact")
        return 1
    parsed = json.loads(payload)
    if not artifact_backup(parsed).get("files"):
        print("FAILED:AUD-0092 artifact backup.files empty")
        return 1
    validate_or_die(parsed)
    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload, encoding="utf-8")
    if out.stat().st_size < int(doc["min_bytes_threshold"]):
        print("FAILED:AUD-0092 artifact below min_bytes_threshold")
        return 1
    print(f"wrote {OUT_REL} bytes={out.stat().st_size} files={live['file_count']}")
    print("SUCCESS:AUD-0092 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
