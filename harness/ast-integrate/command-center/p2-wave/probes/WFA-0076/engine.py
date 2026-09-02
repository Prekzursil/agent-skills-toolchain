#!/usr/bin/env python3
"""Terminal-disposition preservation gate for WFA-0076.

A RETIRE or REJECT row is recorded only after content is retrieved from a
named preserved location and the retrieved bytes hash-match the claimed
content hash. Squash-merge / commit-ancestry claims are refused: on this
estate they are not preservation evidence.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
EXPORTS = HERE / "fixtures" / "exports"
TERMINAL = frozenset({"RETIRE", "REJECT"})
FORBIDDEN_KINDS = frozenset(
    {
        "squash-merge-history",
        "squash-merge",
        "commit-ancestry",
        "three-dot-diff",
        "merged-branch-ahead",
        "squash_merge_history",
    }
)
LIVE_CANDIDATES = (
    "command-center/wfa/WFA-0071-retire-readjudication.json",
    "command-center/_wfa2_entries.json",
    "command-center/08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def git_blob_id(data: bytes) -> str:
    payload = b"blob %d\0" % len(data) + data
    return hashlib.sha1(payload).hexdigest()


def write_git_blob(store: Path, data: bytes) -> str:
    oid = git_blob_id(data)
    dest = store / oid[:2] / oid[2:]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(zlib.compress(b"blob %d\0" % len(data) + data, level=1))
    return oid


def read_git_blob(store: Path, oid: str) -> bytes | None:
    path = store / oid[:2] / oid[2:]
    if not path.is_file():
        return None
    raw = zlib.decompress(path.read_bytes())
    header, sep, body = raw.partition(b"\0")
    if not sep or not header.startswith(b"blob "):
        return None
    try:
        declared = int(header.split()[1])
    except (IndexError, ValueError):
        return None
    if declared != len(body):
        return None
    return body


@dataclass
class Retrieval:
    ok: bool
    reason: str
    location_kind: str
    named_location: str
    retrieved_hash: str | None = None
    retrieved_bytes: bytes | None = None
    squash_merge_rejected: bool = False


@dataclass
class Decision:
    recorded: bool
    reason: str
    record_id: str
    disposition: str


def retrieve(location: dict[str, Any], *, repo: Path, store: Path | None) -> Retrieval:
    kind = str(location.get("kind") or "")
    named = str(
        location.get("path")
        or location.get("blob_id")
        or location.get("ref")
        or location.get("note")
        or kind
        or "unnamed"
    )
    if kind in FORBIDDEN_KINDS:
        return Retrieval(
            ok=False,
            reason="squash-merge-not-evidence",
            location_kind=kind,
            named_location=named,
            squash_merge_rejected=True,
        )
    if kind == "named-export":
        rel = str(location.get("path") or "")
        path = Path(rel) if Path(rel).is_absolute() else repo / rel
        if not path.is_file():
            return Retrieval(
                ok=False,
                reason="export-not-found",
                location_kind=kind,
                named_location=rel,
            )
        data = path.read_bytes()
        return Retrieval(
            ok=True,
            reason="retrieved-named-export",
            location_kind=kind,
            named_location=rel,
            retrieved_hash=sha256_bytes(data),
            retrieved_bytes=data,
        )
    if kind == "git-blob":
        oid = str(location.get("blob_id") or "")
        if not oid or store is None:
            return Retrieval(
                ok=False,
                reason="git-blob-unspecified",
                location_kind=kind,
                named_location=oid or named,
            )
        data = read_git_blob(store, oid)
        if data is None:
            return Retrieval(
                ok=False,
                reason="git-blob-not-found",
                location_kind=kind,
                named_location=oid,
            )
        return Retrieval(
            ok=True,
            reason="retrieved-git-blob",
            location_kind=kind,
            named_location=f"git-blob:{oid}",
            retrieved_hash=sha256_bytes(data),
            retrieved_bytes=data,
        )
    return Retrieval(
        ok=False,
        reason="unknown-location-kind",
        location_kind=kind or "missing",
        named_location=named,
    )


def naive_ancestry_would_accept(location: dict[str, Any]) -> bool:
    """The detector this estate must not use: squash-merge/ancestry as proof."""
    kind = str(location.get("kind") or "")
    if kind in FORBIDDEN_KINDS:
        return True
    return bool(location.get("claimed_merged"))


def attempt_record(
    candidate: dict[str, Any],
    retrieval: Retrieval,
    ledger: list[dict[str, Any]],
) -> Decision:
    rid = str(candidate.get("id") or "")
    disp = str(candidate.get("disposition") or "")
    if disp not in TERMINAL:
        return Decision(False, "not-terminal", rid, disp)
    if retrieval.squash_merge_rejected or retrieval.location_kind in FORBIDDEN_KINDS:
        return Decision(False, "squash-merge-not-evidence", rid, disp)
    if not retrieval.ok:
        return Decision(False, retrieval.reason, rid, disp)
    claimed = str(candidate.get("content_hash") or "")
    if not claimed or retrieval.retrieved_hash != claimed:
        return Decision(False, "hash-mismatch", rid, disp)
    if retrieval.retrieved_bytes is None:
        return Decision(False, "empty-retrieval", rid, disp)
    ledger.append(
        {
            "id": rid,
            "disposition": disp,
            "content_hash": claimed,
            "named_location": retrieval.named_location,
            "location_kind": retrieval.location_kind,
            "retrieval_reason": retrieval.reason,
            "retrieval_ok": True,
        }
    )
    return Decision(True, "retrieval-receipt", rid, disp)


def restore_rehearsal(retrieval: Retrieval, claimed_hash: str) -> dict[str, Any]:
    if not retrieval.ok or retrieval.retrieved_bytes is None:
        return {
            "ok": False,
            "reason": retrieval.reason,
            "dest_hash": None,
            "claimed_hash": claimed_hash,
            "bytes": 0,
            "end_to_end": False,
        }
    with tempfile.TemporaryDirectory(prefix="wfa0076-restore-") as tmp:
        dest = Path(tmp) / "restored.bin"
        dest.write_bytes(retrieval.retrieved_bytes)
        got = dest.read_bytes()
        dest_hash = sha256_bytes(got)
        match = dest_hash == claimed_hash == retrieval.retrieved_hash
        return {
            "ok": match,
            "reason": "restored-and-hash-matched" if match else "restore-hash-mismatch",
            "dest_hash": dest_hash,
            "claimed_hash": claimed_hash,
            "bytes": len(got),
            "end_to_end": match,
        }


def load_export(name: str) -> bytes:
    return (EXPORTS / name).read_bytes()


def build_scenario(repo: Path) -> dict[str, Any]:
    retire = load_export("retire-source.txt")
    reject = load_export("reject-source.txt")
    store = Path(tempfile.mkdtemp(prefix="wfa0076-objects-"))
    blob_id = write_git_blob(store, reject)
    retire_rel = (
        "command-center/p2-wave/probes/WFA-0076/fixtures/exports/retire-source.txt"
    )
    missing_rel = (
        "command-center/p2-wave/probes/WFA-0076/fixtures/exports/absent-export.txt"
    )
    candidates = [
        {
            "id": "wf-fixture-retire-demo",
            "disposition": "RETIRE",
            "content_hash": sha256_bytes(retire),
            "location": {"kind": "named-export", "path": retire_rel},
            "role": "happy-retire",
        },
        {
            "id": "wf-fixture-reject-demo",
            "disposition": "REJECT",
            "content_hash": sha256_bytes(reject),
            "location": {"kind": "git-blob", "blob_id": blob_id},
            "role": "happy-reject",
        },
        {
            "id": "wf-fixture-squash-claim",
            "disposition": "RETIRE",
            "content_hash": sha256_bytes(retire),
            "location": {
                "kind": "squash-merge-history",
                "ref": "origin/main",
                "note": "branch was squash-merged; ancestry reports AHEAD",
                "claimed_merged": True,
            },
            "role": "squash-negative",
        },
        {
            "id": "wf-fixture-missing-export",
            "disposition": "RETIRE",
            "content_hash": sha256_bytes(retire),
            "location": {"kind": "named-export", "path": missing_rel},
            "role": "missing-negative",
        },
        {
            "id": "wf-fixture-hash-mismatch",
            "disposition": "REJECT",
            "content_hash": "0" * 64,
            "location": {"kind": "named-export", "path": retire_rel},
            "role": "mismatch-negative",
        },
    ]
    return {
        "candidates": candidates,
        "object_store": store,
        "retire_hash": sha256_bytes(retire),
        "reject_hash": sha256_bytes(reject),
        "reject_blob_id": blob_id,
        "repo": repo,
    }


def scan_live(repo: Path) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    for rel in LIVE_CANDIDATES:
        path = repo / rel
        found.append(
            {
                "path": rel,
                "exists": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    wfa0071 = repo / "command-center/wfa/WFA-0071-retire-readjudication.json"
    return {
        "wfa0071_artifact_present": wfa0071.is_file(),
        "git_dir_present": (repo / ".git").exists(),
        "registry_candidates": found,
        "live_terminal_records_processed": 0,
        "note": (
            "WFA-0071 RETIRE re-adjudication artifact and 08-WORKFLOW-"
            "CANDIDATE-REGISTRY.json are absent on this Linux worktree. The "
            "gate is proven on planted RETIRE/REJECT records with named-export "
            "and git-blob retrieval. No live terminal disposition was written "
            "onto the estate."
        ),
    }


def process_scenario(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    scen = build_scenario(repo)
    store: Path = scen["object_store"]
    ledger: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    rehearsal: dict[str, Any] = {}
    try:
        for cand in scen["candidates"]:
            retrieval = retrieve(cand["location"], repo=repo, store=store)
            decision = attempt_record(cand, retrieval, ledger)
            rows.append(
                {
                    "id": cand["id"],
                    "disposition": cand["disposition"],
                    "role": cand["role"],
                    "claimed_hash": cand["content_hash"],
                    "location_kind": retrieval.location_kind,
                    "named_location": retrieval.named_location,
                    "retrieval_ok": retrieval.ok,
                    "retrieval_reason": retrieval.reason,
                    "retrieved_hash": retrieval.retrieved_hash,
                    "squash_merge_rejected": retrieval.squash_merge_rejected,
                    "naive_ancestry_would_accept": naive_ancestry_would_accept(
                        cand["location"]
                    ),
                    "recorded": decision.recorded,
                    "decision_reason": decision.reason,
                }
            )
        happy = next(r for r in rows if r["role"] == "happy-retire" and r["recorded"])
        loc = next(c["location"] for c in scen["candidates"] if c["id"] == happy["id"])
        happy_ret = retrieve(loc, repo=repo, store=store)
        rehearsal = restore_rehearsal(happy_ret, happy["claimed_hash"])
        rehearsal["record_id"] = happy["id"]
        rehearsal["disposition"] = happy["disposition"]
    finally:
        shutil.rmtree(store, ignore_errors=True)

    recorded = [r for r in rows if r["recorded"]]
    refused = [r for r in rows if not r["recorded"]]
    squash = next(r for r in rows if r["role"] == "squash-negative")
    return {
        "rows": rows,
        "ledger": ledger,
        "recorded_ids": [r["id"] for r in recorded],
        "refused_ids": [r["id"] for r in refused],
        "recorded_count": len(recorded),
        "refused_count": len(refused),
        "rehearsal": rehearsal,
        "squash": squash,
        "gate": {
            "no_terminal_without_retrieval": all(
                (not r["recorded"]) or r["retrieval_ok"] for r in rows
            ),
            "squash_merge_refused": squash["decision_reason"]
            == "squash-merge-not-evidence"
            and not squash["recorded"],
            "naive_would_accept_squash": squash["naive_ancestry_would_accept"],
            "happy_retire_recorded": any(
                r["role"] == "happy-retire" and r["recorded"] for r in rows
            ),
            "happy_reject_recorded": any(
                r["role"] == "happy-reject" and r["recorded"] for r in rows
            ),
            "missing_refused": any(
                r["role"] == "missing-negative" and not r["recorded"] for r in rows
            ),
            "mismatch_refused": any(
                r["role"] == "mismatch-negative" and not r["recorded"] for r in rows
            ),
        },
        "live": scan_live(repo),
        "retire_hash": scen["retire_hash"],
        "reject_hash": scen["reject_hash"],
        "reject_blob_id": scen["reject_blob_id"],
    }


def gate_holds(result: dict[str, Any]) -> bool:
    g = result["gate"]
    r = result["rehearsal"]
    return bool(
        g["no_terminal_without_retrieval"]
        and g["squash_merge_refused"]
        and g["naive_would_accept_squash"]
        and g["happy_retire_recorded"]
        and g["happy_reject_recorded"]
        and g["missing_refused"]
        and g["mismatch_refused"]
        and r.get("ok")
        and r.get("end_to_end")
        and result["recorded_count"] == 2
        and result["refused_count"] == 3
    )


if __name__ == "__main__":
    out = process_scenario()
    print(
        json.dumps(
            {k: out[k] for k in ("recorded_ids", "refused_ids", "gate", "rehearsal")},
            indent=2,
            sort_keys=True,
        )
    )
    print("GATE_HOLDS" if gate_holds(out) else "GATE_FAILS")
    raise SystemExit(0 if gate_holds(out) else 1)
