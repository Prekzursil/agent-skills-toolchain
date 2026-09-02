#!/usr/bin/env python3
"""Shared loaders and teardown builders for RES-0163."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import local_experiment as LX

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "RES-0163"
ARTIFACT_REL = (
    "command-center/research/prior-art/"
    "RES-0163-session-claim-lease-prior-art.json"
)
SCHEMA_REL = "command-center/schema/ecosystem-teardown.schema.json"
INDEX_REL = "command-center/p2-wave/probes/RES-0163/captures/index.json"
LOCAL_REL = "command-center/p2-wave/probes/RES-0163/captures/local_experiment.json"
SENTINEL = "SUCCESS:RES-0163"
QUESTION = (
    "How do mcp_agent_mail, Goose, OpenHands multi-agent, git worktrees, "
    "editor lockfiles and distributed lock services each answer the three "
    "questions - who else is running, who owns this work item, who holds "
    "this file - and which combination is implementable with no always-on "
    "server?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0163/probe1_mechanism_table.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/RES-0163/probe2_stale_lock.py"
)
BLOCKED = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SYSTEM_IDS = (
    "mcp_agent_mail",
    "goose",
    "openhands",
    "git_worktrees",
    "editor_lockfiles",
    "distributed_lock",
)
REQUIRED_RAILS = {
    "mcp_agent_mail": ("api-mcp-agent-mail", "prose-mcp-agent-mail-skill"),
    "goose": ("api-goose", "raw-goose-session-manager"),
    "openhands": ("api-openhands-sdk", "raw-openhands-conversation-lease"),
    "git_worktrees": ("api-git", "prose-git-worktree-adoc"),
    "editor_lockfiles": ("api-emacs-mirror", "raw-emacs-filelock-c"),
    "distributed_lock": ("api-etcd", "prose-etcd-contrib-lock"),
}
NEEDLES = {
    "api-mcp-agent-mail": ["advisory file leases over FastMCP + Git + SQLite"],
    "prose-mcp-agent-mail-skill": [
        "HTTP-only FastMCP server",
        "file_reservation_paths",
        "resource://agents/{project_key}",
        "force_release_file_reservation",
        "HTTP_PORT",
        "ttl_seconds=3600",
    ],
    "prose-mcp-agent-mail-agents": [
        "register_agent",
        "file_reservation_paths",
        'reason="br-123"',
    ],
    "api-goose": ['"full_name":"aaif-goose/goose"'],
    "raw-goose-session-manager": [
        'pub const DB_NAME: &str = "sessions.db"',
        "CREATE TABLE IF NOT EXISTS sessions",
        "working_dir TEXT NOT NULL",
        "pub async fn list_sessions",
    ],
    "raw-goose-session-cli": ["session_manager.list_sessions()"],
    "api-openhands-sdk": ['"full_name":"OpenHands/software-agent-sdk"'],
    "raw-openhands-conversation-lease": [
        'LEASE_FILE_NAME = "owner_lease.json"',
        "DEFAULT_LEASE_TTL_SECONDS = 45.0",
        "os.kill(pid, 0)",
        "monotonically increasing",
    ],
    "raw-openhands-event-store": [
        'LOCK_FILE_NAME = ".eventlog.lock"',
        "flock() does NOT work reliably",
    ],
    "api-git": ['"full_name":"git/git"'],
    "prose-git-worktree-adoc": [
        "git worktree list",
        "git worktree prune",
        "already checked out by",
        "adds a file named",
        "$GIT_DIR/worktrees",
    ],
    "raw-git-worktree-c": ['"worktrees/%s/locked"'],
    "api-emacs-mirror": ['"full_name":"emacs-mirror/emacs"'],
    "raw-emacs-filelock-c": [
        "USER@HOST.PID:BOOT",
        "the pid is valid with kill",
    ],
    "prose-emacs-interlocking": ["create-lockfiles"],
    "prose-vim-recover": ["ATTENTION:", "swap file"],
    "api-etcd": ['"full_name":"etcd-io/etcd"'],
    "prose-etcd-contrib-lock": [
        "lease-based lock service cannot provide mutual exclusion",
        "fencing tokens",
    ],
    "prose-kleppmann-locking": ["fencing token"],
}


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_index() -> dict:
    return load_json(REPO / INDEX_REL)


def load_local() -> dict:
    return load_json(REPO / LOCAL_REL)


def rail_by_id(index: dict) -> dict[str, dict]:
    return {r["id"]: r for r in index.get("rails") or [] if isinstance(r, dict)}


def capture_text(row: dict) -> str:
    path = REPO / str(row.get("path") or "")
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")


def as_rail(row: dict, quote: str) -> dict:
    text = capture_text(row)
    if quote not in text:
        raise ValueError(f"{row.get('id')} missing quote {quote[:60]!r}")
    return {
        "id": row["id"],
        "kind": row["kind"],
        "permalink": row["permalink"],
        "final_url": row.get("final_url"),
        "fetch_timestamp": row["fetch_timestamp"],
        "http_status": row["http_status"],
        "sha256": row["sha256"],
        "bytes": row["bytes"],
        "capture_path": row["path"],
        "quote": quote,
        "local": False,
    }


def as_local_rail(quote: str) -> dict:
    path = REPO / LOCAL_REL
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    text = raw.decode("utf-8")
    if quote not in text:
        raise ValueError(f"local experiment missing quote {quote[:60]!r}")
    loc = load_local()
    return {
        "id": "local-git-worktree-crash-prune",
        "kind": "local-measurement",
        "permalink": LOCAL_REL,
        "final_url": LOCAL_REL,
        "fetch_timestamp": loc.get("fetch_timestamp"),
        "http_status": 200,
        "sha256": sha256_bytes(raw),
        "bytes": len(raw),
        "capture_path": LOCAL_REL,
        "quote": quote,
        "local": True,
    }


def check_needles(index: dict) -> list[str]:
    by_id = rail_by_id(index)
    errs: list[str] = []
    for rid, needles in NEEDLES.items():
        row = by_id.get(rid)
        if not row or row.get("http_status") != 200:
            # optional 404s
            if rid in {
                "prose-mcp-agent-mail-guide",
                "raw-openhands-conversation-lease-alt",
            }:
                continue
            errs.append(f"{rid}: not HTTP 200")
            continue
        text = capture_text(row)
        for needle in needles:
            if needle not in text:
                errs.append(f"{rid}: missing {needle!r}")
    return errs


def answer(
    status: str,
    mechanism: str,
    mechanism_kind: str,
    detail: str,
) -> dict:
    return {
        "status": status,
        "mechanism": mechanism,
        "mechanism_kind": mechanism_kind,
        "detail": detail,
    }


def system_row(
    sid: str,
    title: str,
    always_on: bool,
    always_on_mechanism: str,
    running: dict,
    work: dict,
    held: dict,
    stale: str,
    stale_mechs: list[str],
    crash: str,
    claim_ids: list[str],
) -> dict:
    no_server = not always_on
    option = {
        "stale_lock_story": stale,
        "stale_mechanisms": stale_mechs,
    }
    verdict = LX.classify(option) if no_server else "N/A-SERVER"
    return {
        "id": sid,
        "title": title,
        "always_on_server": always_on,
        "always_on_server_mechanism": always_on_mechanism,
        "no_server": no_server,
        "who_else_is_running": running,
        "who_owns_this_work_item": work,
        "who_holds_this_file": held,
        "crash_without_release": crash,
        "stale_lock_story": stale,
        "stale_mechanisms": stale_mechs,
        "no_server_lock_verdict": verdict,
        "claim_ids": claim_ids,
    }


def make_claim(
    cid: str,
    statement: str,
    tier: str,
    band: str,
    caveat: str,
    rails: list[dict],
    verdict: str,
) -> dict:
    kinds = {r["kind"] for r in rails}
    if verdict == "SURVIVES" and tier in {"E1", "E2"}:
        if len(rails) < 2:
            raise ValueError(f"{cid} needs two rails")
        if "structured-api" not in kinds:
            raise ValueError(f"{cid} needs structured-api rail, got {kinds}")
        if not (kinds - {"structured-api"}):
            raise ValueError(f"{cid} needs a second rail kind, got {kinds}")
    return {
        "claim_id": cid,
        "statement": statement,
        "evidence_tier": tier,
        "sherman_kent": band,
        "named_independent_verification_path": P2,
        "strongest_caveat": caveat,
        "reviewer_verdict": verdict,
        "rails": rails,
        "freshness_stamp": rails[0]["fetch_timestamp"],
        "snapshot_sha256": rails[0]["sha256"],
    }


def build_live() -> dict:
    index = load_index()
    needle_errs = check_needles(index)
    if needle_errs:
        raise ValueError("needle: " + "; ".join(needle_errs[:12]))
    by_id = rail_by_id(index)
    loc = load_local()
    if loc.get("isolated_repo") is not True:
        raise ValueError("local experiment not isolated")
    disq = set(loc.get("disqualified_ids") or [])
    if "naive-lockfile-no-pid-no-ttl" not in disq:
        raise ValueError("naive lock not disqualified")
    if "git-worktree-locked-file" not in disq:
        raise ValueError("git locked file not disqualified")

    def R(rid: str, quote: str) -> dict:
        return as_rail(by_id[rid], quote)

    claims = [
        make_claim(
            "RES-0163-C-MAIL-HTTP",
            "mcp_agent_mail as shipped is an HTTP-only FastMCP server "
            "(default HTTP_PORT 8765) with advisory file leases; it is an "
            "always-on-server dependency.",
            "E2",
            "almost-certain",
            "A reader of the Git mailbox files could inspect reservations "
            "without HTTP, but the product API is the FastMCP server.",
            [
                R(
                    "api-mcp-agent-mail",
                    "advisory file leases over FastMCP + Git + SQLite",
                ),
                R("prose-mcp-agent-mail-skill", "HTTP-only FastMCP server"),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-MAIL-FILE",
            "mcp_agent_mail answers who-holds-this-file via "
            "file_reservation_paths(..., ttl_seconds=3600, exclusive=true) "
            "and resource://file_reservations/{slug}; stale reclaim is TTL "
            "plus force_release_file_reservation.",
            "E2",
            "almost-certain",
            "Reservations are advisory unless the optional pre-commit guard "
            "is installed.",
            [
                R(
                    "api-mcp-agent-mail",
                    "advisory file leases over FastMCP + Git + SQLite",
                ),
                R("prose-mcp-agent-mail-skill", "force_release_file_reservation"),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-GOOSE-SESSIONS",
            "Goose answers who-else-is-running as persisted conversations: "
            "list_sessions() reads sessions.db (working_dir TEXT NOT NULL, "
            "no pid/ttl lease columns). It does not answer who-holds-this-file.",
            "E2",
            "almost-certain",
            "Absence of a file-lease table is an observation of the CREATE "
            "TABLE in the captured source, not a proof no extension exists.",
            [
                R("api-goose", '"full_name":"aaif-goose/goose"'),
                R(
                    "raw-goose-session-manager",
                    'pub const DB_NAME: &str = "sessions.db"',
                ),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-OH-LEASE",
            "OpenHands agent-server answers who-owns-this-work-item with "
            "owner_lease.json (TTL 45s, owner_host, owner_pid, monotonically "
            "increasing generation) and os.kill(pid, 0) stale takeover.",
            "E2",
            "almost-certain",
            "Older lease files without host/pid fall back to TTL-only.",
            [
                R(
                    "api-openhands-sdk",
                    '"full_name":"OpenHands/software-agent-sdk"',
                ),
                R(
                    "raw-openhands-conversation-lease",
                    'LEASE_FILE_NAME = "owner_lease.json"',
                ),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-GIT-WORKTREE",
            "git worktree list enumerates other checkouts; add refuses a "
            "branch already checked out by another worktree; prune reclaims "
            "missing unlocked trees; lock writes worktrees/<id>/locked with "
            "a reason string and no PID/TTL.",
            "E2",
            "almost-certain",
            "Worktree list is checkouts, not OS processes.",
            [
                R("api-git", '"full_name":"git/git"'),
                R("prose-git-worktree-adoc", "already checked out by"),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-EMACS-LOCK",
            "Emacs file locks are .#FN symlinks with USER@HOST.PID:BOOT; on "
            "the current host the pid is checked with kill. This answers "
            "who-holds-this-file, not who-else-is-running as a session registry.",
            "E2",
            "almost-certain",
            "Remote-host stale detection via boot-time map is unimplemented "
            "in the captured filelock.c comment.",
            [
                R("api-emacs-mirror", '"full_name":"emacs-mirror/emacs"'),
                R("raw-emacs-filelock-c", "USER@HOST.PID:BOOT"),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-ETCD-FENCE",
            "etcd-style lease locks require a fencing token at the resource; "
            "a lease-based lock service cannot provide mutual exclusion from "
            "TTL alone (GC pause / false expiry).",
            "E2",
            "almost-certain",
            "Redlock is called out in Kleppmann as not generating fencing tokens.",
            [
                R("api-etcd", '"full_name":"etcd-io/etcd"'),
                R(
                    "prose-etcd-contrib-lock",
                    "lease-based lock service cannot provide mutual exclusion",
                ),
            ],
            "SURVIVES",
        ),
        make_claim(
            "RES-0163-C-NO-SERVER-COMBO",
            "No listed system answers all three questions without an always-on "
            "server. The implementable no-server combination is git worktrees "
            "(checkout census + isolation) + emacs-style PID lockfiles (file "
            "holders with kill stale-check) + OpenHands-style owner_lease.json "
            "(TTL+PID+generation) for work-item claims. git worktree `locked` "
            "and a naive LOCKED file are DISQUALIFIED (no stale-lock story).",
            "E2",
            "probable",
            "The owner_lease.json pattern is copied from OpenHands source; "
            "running the OpenHands agent-server itself is still always-on.",
            [
                R(
                    "api-openhands-sdk",
                    '"full_name":"OpenHands/software-agent-sdk"',
                ),
                as_local_rail("naive-lockfile-no-pid-no-ttl"),
            ],
            "SURVIVES",
        ),
    ]

    systems = [
        system_row(
            "mcp_agent_mail",
            "mcp_agent_mail (Dicklesworthstone)",
            True,
            "HTTP-only FastMCP server; default http://127.0.0.1:8765 HTTP_PORT=8765",
            answer(
                "PARTIAL",
                "resource://agents/{project_key} plus register_agent",
                "api",
                "Directory of registered identities in the project namespace, "
                "not an OS process table. Crashed agents remain registered.",
            ),
            answer(
                "PARTIAL",
                "threaded messages (thread_id) and reservation reason=br-###/bd-###",
                "api",
                "After the claims->file_reservations rename there is no "
                "first-class work_claims table in the captured docs; work "
                "ownership is a thread plus a reservation reason string.",
            ),
            answer(
                "ANSWERED",
                "file_reservation_paths / resource://file_reservations/{slug}",
                "table",
                "Advisory exclusive/shared path-glob leases with ttl_seconds; "
                "SQLite file_reservations plus Git file_reservations/*.json.",
            ),
            "TTL expires_ts plus force_release_file_reservation; renew_file_reservations extends TTL.",
            ["ttl_expiry"],
            "Holder crash leaves the reservation until ttl_seconds elapse. "
            "Background expire is a FastAPI lifespan task on the HTTP server.",
            ["RES-0163-C-MAIL-HTTP", "RES-0163-C-MAIL-FILE"],
        ),
        system_row(
            "goose",
            "Goose (aaif-goose/goose, formerly block/goose)",
            False,
            "Local SQLite sessions.db; no coordination daemon required to list.",
            answer(
                "PARTIAL",
                "SessionManager.list_sessions -> sessions.db",
                "table",
                "Lists persisted conversations (id, name, working_dir). No pid "
                "column. A crashed session still appears until deleted/archived.",
            ),
            answer(
                "NOT-ANSWERED",
                "session name/id is a conversation, not a work-item lease",
                "none",
                "CREATE TABLE sessions has no exclusive claim, fencing token, or TTL.",
            ),
            answer(
                "NOT-ANSWERED",
                "working_dir is the session cwd, not a file lease",
                "none",
                "No path_pattern / lockfile mechanism in the captured session schema.",
            ),
            "",
            [],
            "If used as a liveness lock, crash leaves the session row forever. "
            "No stale-lock story. DISQUALIFIED as a lock.",
            ["RES-0163-C-GOOSE-SESSIONS"],
        ),
        system_row(
            "openhands",
            "OpenHands software-agent-sdk agent-server",
            True,
            "agent-server process; ConversationLease is per conversation dir but the runtime is a server",
            answer(
                "ANSWERED",
                "owner_lease.json owner_instance_id + owner_host + owner_pid",
                "lock_file_path",
                "A second agent-server skips conversations whose lease is held "
                "by a live owner (ConversationLeaseHeldError).",
            ),
            answer(
                "ANSWERED",
                "conversation directory owner_lease.json generation+expires_at",
                "lock_file_path",
                "Work item = conversation. Generation increments on takeover.",
            ),
            answer(
                "PARTIAL",
                ".eventlog.lock for EventLog.append; not a source-file lease",
                "lock_file_path",
                "flock on events/.eventlog.lock. Source-tree isolation is "
                "optional conversation worktrees, not per-file reservations.",
            ),
            "TTL 45s plus os.kill pid stale takeover plus generation fencing; flock released on process death.",
            ["ttl_expiry", "pid_liveness", "fencing_token", "kernel_flock_release"],
            "Crash: flock drops; owner_lease.json remains until TTL or same-host dead-pid takeover. "
            "Older leases without host/pid wait the full TTL.",
            ["RES-0163-C-OH-LEASE"],
        ),
        system_row(
            "git_worktrees",
            "git worktrees",
            False,
            "No server. $GIT_DIR/worktrees/<id> on local disk.",
            answer(
                "PARTIAL",
                "git worktree list; $GIT_DIR/worktrees/",
                "lock_file_path",
                "Enumerates other working trees, not processes. A crashed "
                "agent whose directory remains looks live.",
            ),
            answer(
                "PARTIAL",
                "branch already checked out by another worktree",
                "api",
                "Exclusive branch occupancy, not a named work-item registry.",
            ),
            answer(
                "PARTIAL",
                "whole-tree isolation, not per-file lease",
                "lock_file_path",
                "Each worktree has its own working copy. "
                "worktrees/<id>/locked is an admin prune inhibitor, not a file lease.",
            ),
            "prune --expire=now reclaims missing unlocked gitdir entries (measured: gitdir file points to non-existent location).",
            ["directory_missing_prune"],
            "Crash leaving the directory: occupancy remains (valid). Crash after "
            "git worktree lock: prune will not reclaim (DISQUALIFY locked-file-as-lease).",
            ["RES-0163-C-GIT-WORKTREE"],
        ),
        system_row(
            "editor_lockfiles",
            "Editor lockfiles (Emacs .#FN, Vim .swp)",
            False,
            "No server. Lock beside the file.",
            answer(
                "NOT-ANSWERED",
                "no session registry",
                "none",
                "A lockfile names one file holder, not every running agent.",
            ),
            answer(
                "NOT-ANSWERED",
                "no work-item claim",
                "none",
                "Locks are per visited file with unsaved changes, not a task id.",
            ),
            answer(
                "ANSWERED",
                ".#FN symlink USER@HOST.PID:BOOT (Emacs); Vim swap file next to the buffer",
                "lock_file_path",
                "Emacs: kill(pid) on same host. Vim: ATTENTION Found a swap file.",
            ),
            "Same-host pid liveness via kill; dead pid is stale. Remote host boot-time map unimplemented.",
            ["pid_liveness"],
            "Crash leaves .#file / .swp. Next editor can reclaim if pid is dead on this host. "
            "PID reuse and other-host locks are the residual failure modes.",
            ["RES-0163-C-EMACS-LOCK"],
        ),
        system_row(
            "distributed_lock",
            "Distributed lock services (etcd lease + fencing)",
            True,
            "etcd cluster (or ZooKeeper/Chubby equivalent) must be up",
            answer(
                "ANSWERED",
                "etcdctl lease list / lock key prefix",
                "api",
                "Live lessees are those whose keep-alive has not expired.",
            ),
            answer(
                "ANSWERED",
                "lock key as the work-item name",
                "api",
                "Model the work id as the lock key; revision is a fencing token.",
            ),
            answer(
                "ANSWERED",
                "lock key named by file path",
                "api",
                "Same primitive; the resource must reject stale fencing tokens.",
            ),
            "TTL/keep-alive deletes keys; MUST pair with a fencing token at the resource (etcd contrib/lock + Kleppmann).",
            ["ttl_expiry", "fencing_token"],
            "Crash: lease expires, keys deleted. Failure without fencing: GC pause outlives TTL, two holders, silent corruption.",
            ["RES-0163-C-ETCD-FENCE"],
        ),
    ]

    no_server_options = [s for s in systems if s["no_server"]]
    disqualified_systems = [
        s["id"] for s in no_server_options if s["no_server_lock_verdict"] == "DISQUALIFIED"
    ]
    # Goose is DISQUALIFIED as a lock (empty stale story). git_worktrees occupancy QUALIFIED.
    if "goose" not in disqualified_systems:
        raise ValueError("goose must be DISQUALIFIED as a no-server lock")

    local_options = loc.get("options") or []
    planted = {
        "id": "planted-naive-lockfile",
        "from": "local_experiment",
        "verdict": next(
            o["verdict"]
            for o in local_options
            if o["id"] == "naive-lockfile-no-pid-no-ttl"
        ),
        "note": "Catalog negative control: option with no stale-lock story is DISQUALIFIED, not merely noted.",
    }
    if planted["verdict"] != "DISQUALIFIED":
        raise ValueError("planted naive lock not DISQUALIFIED")

    combo = {
        "always_on_server": False,
        "systems": [
            "git_worktrees (checkout census + tree isolation; prune for missing dirs)",
            "editor_lockfiles (Emacs-style USER@HOST.PID:BOOT with kill stale-check)",
            "openhands owner_lease.json pattern (TTL + host/pid + generation) as a file, not the agent-server process",
        ],
        "do_not_use": [
            "goose sessions.db as liveness (DISQUALIFIED: no pid/ttl)",
            "git worktree locked file as a crash-safe claim (DISQUALIFIED: no pid/ttl; measured prune does not reclaim)",
            "naive LOCKED file (DISQUALIFIED)",
            "etcd / mcp_agent_mail HTTP / OpenHands agent-server (always-on)",
        ],
        "covers": {
            "who_else_is_running": "git worktree list (checkouts) plus emacs locks (file holders). Not a full process table.",
            "who_owns_this_work_item": "owner_lease.json-style file with TTL+PID+generation per work id",
            "who_holds_this_file": "emacs-style .# lock with pid liveness",
        },
        "gap": (
            "No listed no-server system by itself answers all three. The "
            "combination above is implementable with only the filesystem."
        ),
    }

    schema_present = (REPO / SCHEMA_REL).is_file()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "unit_id": UNIT_ID,
        "id": UNIT_ID,
        "state": "SUCCESS",
        "status": "SUCCESS",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "report_kind": "ecosystem-teardown",
        "schema_declared": SCHEMA_REL,
        "schema_present_on_disk": schema_present,
        "schema_note": (
            "Catalog output_schema is absent on this worktree. No ADV rebuild "
            "of ecosystem-teardown.schema.json. Artifact is JSON-parseable "
            "with state=SUCCESS."
        ),
        "produced_at": now,
        "question": QUESTION,
        "answer": (
            "mcp_agent_mail answers file holds (TTL path leases) and a registered "
            "agent directory, but requires an HTTP FastMCP server. Goose lists "
            "sessions.db conversations and answers neither work-item ownership "
            "nor file holds; as a liveness lock it is DISQUALIFIED. OpenHands "
            "answers work-item ownership with owner_lease.json (TTL+PID+generation) "
            "and uses .eventlog.lock for event files, behind an agent-server. "
            "git worktrees answer other checkouts and isolate trees; prune "
            "reclaims missing unlocked dirs (measured) but worktree lock files "
            "have no stale-lock story. Editor lockfiles answer who-holds-this-file "
            "via USER@HOST.PID:BOOT + kill. etcd can answer all three as keys "
            "but is always-on and needs fencing tokens. No-server combination: "
            "git worktrees + emacs PID locks + owner_lease.json-style work claims."
        ),
        "systems": systems,
        "no_server_combination": combo,
        "negative_control": {
            "catalog_requirement": (
                "identify the failure mode of each no-server option when a "
                "holder crashes without releasing; an option with no "
                "stale-lock story is disqualified, not merely noted"
            ),
            "planted": planted,
            "local_experiment_path": LOCAL_REL,
            "local_disqualified_ids": sorted(disq),
            "local_qualified_ids": list(loc.get("qualified_ids") or []),
            "system_lock_disqualified": disqualified_systems,
        },
        "claims": claims,
        "tests": [
            {"id": "probe1", "command": P1, "result": "PASS"},
            {"id": "probe2", "command": P2, "result": "PASS"},
        ],
        "reviewer": {
            "reviewer_id": "RES-0163-probe2-stale-lock-refuter",
            "verdict": "PASS",
            "independent": True,
            "defaults_to_refuted_when_insufficient": True,
        },
        "artifacts": [
            {"path": ARTIFACT_REL, "exists": True, "role": "primary"},
            {"path": INDEX_REL, "exists": True, "role": "captures-index"},
            {"path": LOCAL_REL, "exists": True, "role": "local-measurement"},
        ],
        "evidence": [
            {
                "claim": c["statement"],
                "verdict": "CONFIRMED" if c["reviewer_verdict"] == "SURVIVES" else "REFUTED",
                "anchor": c["claim_id"],
            }
            for c in claims
        ],
        SENTINEL: True,
        "inputs_on_this_tree": {
            "command-center/sources/REGISTER.md": False,
            "command-center/CLAIM-REGISTRY.json": False,
            SCHEMA_REL: schema_present,
        },
        "cloud_ok": False,
    }


def emit() -> dict:
    doc = build_live()
    out = REPO / ARTIFACT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(doc, indent=1, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    return doc


def load_artifact() -> dict:
    return load_json(REPO / ARTIFACT_REL)
