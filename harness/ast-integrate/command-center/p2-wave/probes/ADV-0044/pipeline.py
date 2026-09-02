#!/usr/bin/env python3
"""Isolated erasure campaign against stores that exist in this worktree.

ADV-0044 measures whether a seeded artifact and its derivatives can actually
be purged. Production has no artifact-erase API. The campaign therefore:

  * seeds two synthetic artifacts (purge target + keep-control) into an
    isolated tempfile tree, never into owner receipts/events
  * writes primary bodies, receipts, an append-only event-log copy via the
    real event_log.append_record writer, a unit_manifest index, and
    content-addressed digest/summary derivatives that omit the artifact id
  * applies the strongest deletion today's tree offers (operator unlink of
    the primary body + receipt; no event-log rewrite)
  * searches remaining bytes by id/hash (probe 1) and by body TOKEN (probe 2)

Caches, embeddings, backups, and mirrors are inventoried; when the
production module is absent they are NOT-CHECKED rather than faked.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS_CC = REPO / "tools" / "command-center"
if str(TOOLS_CC) not in sys.path:
    sys.path.insert(0, str(TOOLS_CC))

import event_log as elog  # noqa: E402
import unit_manifest as um  # noqa: E402

UNIT = "ADV-0044"
TARGET_ID = "adv44-seed-purge-target"
CONTROL_ID = "adv44-seed-keep-control"
TARGET_TOKEN = "ADV44CANARY_PURGE_xk9mQ2wL7nP4sT8v"
CONTROL_TOKEN = "ADV44CANARY_KEEP_bR3yU6cE1hJ5fA0z"
ABSENT_TOKEN = "ADV44CANARY_ABSENT_never_seeded_9zQ"

P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0044/probe1_id_hash_survivors.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0044/probe2_token_derivatives.py"
)

PURGE_DEF_RE = re.compile(
    r"^\s*def\s+(purge|erase|forget|delete_artifact|shred)\s*\(",
    re.MULTILINE,
)

CACHE_CANDIDATES = [
    "tools/agentspec/agentspec/artifact_cache.py",
    "tools/agentspec/agentspec/cache.py",
    "platform/cache/artifact_cache.py",
]
EMBED_CANDIDATES = [
    "tools/embeddings",
    "platform/embeddings",
    "tools/agentspec/agentspec/embed.py",
]
BACKUP_CANDIDATES = [
    "command-center/backups",
    "tools/command-center/backup.py",
]
MIRROR_CANDIDATES = [
    "command-center/mirrors",
    "tools/command-center/mirror.py",
]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def owner_receipt_digests(repo: Path) -> dict[str, str]:
    root = repo / "command-center" / "receipts"
    if not root.is_dir():
        return {}
    out: dict[str, str] = {}
    for path in sorted(root.glob("*.json")):
        rel = path.relative_to(repo).as_posix()
        out[rel] = sha256_file(path)
    return out


def existing_paths(repo: Path, rels: list[str]) -> list[str]:
    return [rel for rel in rels if (repo / rel).exists()]


def scan_purge_entrypoints(repo: Path) -> list[str]:
    hits: list[str] = []
    root = repo / "tools" / "command-center"
    if not root.is_dir():
        return hits
    for path in sorted(root.glob("*.py")):
        if PURGE_DEF_RE.search(path.read_text(encoding="utf-8")):
            hits.append(path.relative_to(repo).as_posix())
    return hits


def payload_doc(artifact_id: str, token: str, role: str) -> dict[str, Any]:
    return {
        "id": artifact_id,
        "kind": "adv44-seeded-test-artifact",
        "role": role,
        "body": (
            f"synthetic erasure-drill payload token={token} "
            "contains-no-owner-data"
        ),
        "token": token,
    }


def classify_rel(rel: str) -> str:
    posix = rel.replace("\\", "/")
    if posix.startswith("payloads/") or posix.startswith("command-center/receipts/"):
        return "primary"
    if "EVENTS.jsonl" in posix or posix.startswith("command-center/events/"):
        return "event_log"
    if posix.endswith("UNIT-ARTIFACT-MANIFEST.json"):
        return "index"
    if posix.startswith("derivatives/"):
        return "derivatives"
    if posix.startswith("cache/"):
        return "cache"
    if posix.startswith("embeddings/"):
        return "embeddings"
    if posix.startswith("backups/"):
        return "backups"
    if posix.startswith("mirrors/"):
        return "mirrors"
    return "other"


def iter_files(root: Path) -> list[Path]:
    files = [p for p in root.rglob("*") if p.is_file()]
    files.sort(key=lambda p: p.relative_to(root).as_posix())
    return files


def search(root: Path, needle: str) -> list[dict[str, Any]]:
    blob = needle.encode("utf-8")
    hits: list[dict[str, Any]] = []
    for path in iter_files(root):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        rel = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if blob in data:
            hits.append({"path": rel, "store": classify_rel(rel), "bytes": len(data)})
    return hits


def search_hash_file(root: Path, digest: str) -> list[dict[str, Any]]:
    hits = search(root, digest)
    seen = {h["path"] for h in hits}
    for path in iter_files(root):
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            continue
        if sha256_file(path) == digest:
            hits.append(
                {
                    "path": rel,
                    "store": classify_rel(rel),
                    "bytes": path.stat().st_size,
                    "match": "content-hash",
                }
            )
    return hits


def stores_of(hits: list[dict[str, Any]]) -> list[str]:
    return sorted({h["store"] for h in hits})


def present_on(hits: list[dict[str, Any]], store: str) -> bool:
    return any(h["store"] == store for h in hits)


def seed_into(sandbox: Path) -> dict[str, Any]:
    payloads = sandbox / "payloads"
    receipts = sandbox / "command-center" / "receipts"
    events_dir = sandbox / "command-center" / "events"
    deriv = sandbox / "derivatives"
    for folder in (
        payloads,
        receipts,
        events_dir,
        deriv / "digests",
        deriv / "summaries",
    ):
        folder.mkdir(parents=True, exist_ok=True)

    target_doc = payload_doc(TARGET_ID, TARGET_TOKEN, "purge-target")
    control_doc = payload_doc(CONTROL_ID, CONTROL_TOKEN, "keep-control")
    target_raw = dump(target_doc).encode("utf-8")
    control_raw = dump(control_doc).encode("utf-8")
    target_sha = sha256_bytes(target_raw)
    control_sha = sha256_bytes(control_raw)

    (payloads / "target.json").write_bytes(target_raw)
    (payloads / "control.json").write_bytes(control_raw)
    (receipts / "target.json").write_text(
        dump(
            {
                "unit_id": TARGET_ID,
                "artifacts": [{"path": "payloads/target.json"}],
                "note": "ADV-0044 seeded purge target; not owner data",
            }
        ),
        encoding="utf-8",
    )
    (receipts / "control.json").write_text(
        dump(
            {
                "unit_id": CONTROL_ID,
                "artifacts": [{"path": "payloads/control.json"}],
                "note": "ADV-0044 seeded keep-control; not owner data",
            }
        ),
        encoding="utf-8",
    )

    events_path = events_dir / "EVENTS.jsonl"
    elog.append_record(
        events_path,
        {
            "kind": "artifact-seeded",
            "artifact_id": TARGET_ID,
            "content_sha256": target_sha,
            "preview": TARGET_TOKEN,
            "seq": 1,
            "writer_id": 44,
        },
    )
    elog.append_record(
        events_path,
        {
            "kind": "artifact-seeded",
            "artifact_id": CONTROL_ID,
            "content_sha256": control_sha,
            "preview": CONTROL_TOKEN,
            "seq": 2,
            "writer_id": 44,
        },
    )

    (deriv / "digests" / f"{target_sha}.digest").write_text(
        f"digest-of-body {TARGET_TOKEN}\n", encoding="utf-8"
    )
    (deriv / "digests" / f"{control_sha}.digest").write_text(
        f"digest-of-body {CONTROL_TOKEN}\n", encoding="utf-8"
    )
    (deriv / "summaries" / f"{target_sha}.json").write_text(
        dump(
            {
                "content_sha256": target_sha,
                "excerpt": f"mentions {TARGET_TOKEN}",
                "kind": "seeded-summary-derivative",
            }
        ),
        encoding="utf-8",
    )
    (deriv / "summaries" / f"{control_sha}.json").write_text(
        dump(
            {
                "content_sha256": control_sha,
                "excerpt": f"mentions {CONTROL_TOKEN}",
                "kind": "seeded-summary-derivative",
            }
        ),
        encoding="utf-8",
    )

    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        rc = um.write(sandbox)
    if rc != 0:
        raise RuntimeError(
            "unit_manifest.write failed inside sandbox: "
            + captured.getvalue().strip()
        )
    return {
        "target_sha256": target_sha,
        "control_sha256": control_sha,
        "events_path": events_path.relative_to(sandbox).as_posix(),
        "index_path": um.MANIFEST_REL.replace("\\", "/"),
        "target_primary": "payloads/target.json",
        "control_primary": "payloads/control.json",
        "target_receipt": "command-center/receipts/target.json",
        "control_receipt": "command-center/receipts/control.json",
        "target_digest": f"derivatives/digests/{target_sha}.digest",
        "target_summary": f"derivatives/summaries/{target_sha}.json",
    }


def apply_purge(
    sandbox: Path, seed: dict[str, Any], purge_apis: list[str]
) -> dict[str, Any]:
    removed: list[str] = []
    for rel in (seed["target_primary"], seed["target_receipt"]):
        path = sandbox / rel
        if path.is_file():
            path.unlink()
            removed.append(rel)
    return {
        "production_purge_api": purge_apis,
        "production_purge_api_absent": not purge_apis,
        "action": "operator-unlink-primary-body-and-receipt",
        "removed": removed,
        "not_rewritten": [
            seed["events_path"],
            seed["index_path"],
            seed["target_digest"],
            seed["target_summary"],
        ],
        "control_untouched": [seed["control_primary"], seed["control_receipt"]],
    }


def snapshot(sandbox: Path, seed: dict[str, Any]) -> dict[str, Any]:
    return {
        "by_target_id": search(sandbox, TARGET_ID),
        "by_control_id": search(sandbox, CONTROL_ID),
        "by_target_hash": search_hash_file(sandbox, seed["target_sha256"]),
        "by_control_hash": search_hash_file(sandbox, seed["control_sha256"]),
        "by_target_token": search(sandbox, TARGET_TOKEN),
        "by_control_token": search(sandbox, CONTROL_TOKEN),
        "by_absent_token": search(sandbox, ABSENT_TOKEN),
    }


def decide(controls_ok: bool, *, absent: bool, survivors: bool) -> str:
    if not controls_ok or absent:
        return "NOT-CHECKED"
    return "CONFIRMED" if not survivors else "REFUTED"


def run_campaign(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    before_owner = owner_receipt_digests(repo)
    purge_apis = scan_purge_entrypoints(repo)
    inventory = {
        "event_log_module": (TOOLS_CC / "event_log.py").is_file(),
        "unit_manifest_module": (TOOLS_CC / "unit_manifest.py").is_file(),
        "cache_modules": existing_paths(repo, CACHE_CANDIDATES),
        "embedding_modules": existing_paths(repo, EMBED_CANDIDATES),
        "backup_modules": existing_paths(repo, BACKUP_CANDIDATES),
        "mirror_modules": existing_paths(repo, MIRROR_CANDIDATES),
        "production_purge_api": purge_apis,
    }
    with tempfile.TemporaryDirectory(prefix="adv44-erase-") as tmp:
        sandbox = Path(tmp)
        seed = seed_into(sandbox)
        pre = snapshot(sandbox, seed)
        purge = apply_purge(sandbox, seed, purge_apis)
        post = snapshot(sandbox, seed)
        owner_unchanged = before_owner == owner_receipt_digests(repo)

        search_works_pre = all(
            [
                pre["by_target_id"],
                pre["by_target_hash"],
                pre["by_target_token"],
                pre["by_control_id"],
                pre["by_control_token"],
            ]
        )
        control_id_post = bool(post["by_control_id"] and post["by_control_hash"])
        control_token_post = bool(post["by_control_token"])
        control_primary_alive = (sandbox / seed["control_primary"]).is_file()
        target_primary_gone = not (sandbox / seed["target_primary"]).is_file()

        tests = [
            {
                "id": "search-finds-target-before-purge",
                "result": "PASS" if search_works_pre else "FAIL",
                "detail": {
                    "id_hits": len(pre["by_target_id"]),
                    "hash_hits": len(pre["by_target_hash"]),
                    "token_hits": len(pre["by_target_token"]),
                },
            },
            {
                "id": "control-still-findable-by-id-hash",
                "result": "PASS" if control_id_post and control_primary_alive else "FAIL",
                "detail": {
                    "id_hits": len(post["by_control_id"]),
                    "hash_hits": len(post["by_control_hash"]),
                    "primary_alive": control_primary_alive,
                },
            },
            {
                "id": "control-still-findable-by-token",
                "result": "PASS" if control_token_post else "FAIL",
                "detail": {"token_hits": len(post["by_control_token"])},
            },
            {
                "id": "purge-only-seeded-target",
                "result": "PASS"
                if target_primary_gone and control_primary_alive
                else "FAIL",
                "detail": {
                    "target_primary_gone": target_primary_gone,
                    "control_primary_alive": control_primary_alive,
                    "removed": purge["removed"],
                },
            },
            {
                "id": "no-owner-data-deleted",
                "result": "PASS" if owner_unchanged else "FAIL",
                "detail": {
                    "owner_receipt_files": len(before_owner),
                    "unchanged": owner_unchanged,
                },
            },
            {
                "id": "absent-token-zero-hits",
                "result": "PASS"
                if (not pre["by_absent_token"] and not post["by_absent_token"])
                else "FAIL",
                "detail": {
                    "pre": len(pre["by_absent_token"]),
                    "post": len(post["by_absent_token"]),
                    "token": ABSENT_TOKEN,
                },
            },
        ]
        controls_ok = all(t["result"] == "PASS" for t in tests)

        primary_survivors = present_on(post["by_target_id"], "primary") or present_on(
            post["by_target_hash"], "primary"
        )
        event_survivors = present_on(post["by_target_id"], "event_log") or present_on(
            post["by_target_hash"], "event_log"
        )
        index_survivors = present_on(post["by_target_id"], "index") or present_on(
            post["by_target_hash"], "index"
        )
        deriv_token = present_on(post["by_target_token"], "derivatives")
        deriv_hash = present_on(post["by_target_hash"], "derivatives")

        targets = [
            {
                "id": "primary-store",
                "question": (
                    "After purge, does the primary body/receipt still hold "
                    "the target id or hash?"
                ),
                "verdict": decide(
                    controls_ok, absent=False, survivors=primary_survivors
                ),
                "post_id_hits": [
                    h for h in post["by_target_id"] if h["store"] == "primary"
                ],
                "source_probe": P1_CMD,
                "verifier_probe": P2_CMD,
            },
            {
                "id": "event-log-refs",
                "question": (
                    "Do append-only event-log records still name the purged artifact?"
                ),
                "verdict": decide(
                    controls_ok,
                    absent=not inventory["event_log_module"],
                    survivors=event_survivors,
                ),
                "post_id_hits": [
                    h for h in post["by_target_id"] if h["store"] == "event_log"
                ],
                "source_probe": P1_CMD,
                "verifier_probe": P2_CMD,
            },
            {
                "id": "indexes",
                "question": (
                    "Does the unit-manifest index still list the purged artifact?"
                ),
                "verdict": decide(
                    controls_ok,
                    absent=not inventory["unit_manifest_module"],
                    survivors=index_survivors,
                ),
                "post_id_hits": [
                    h for h in post["by_target_id"] if h["store"] == "index"
                ],
                "source_probe": P1_CMD,
                "verifier_probe": P2_CMD,
            },
            {
                "id": "body-token-derivatives",
                "question": (
                    "Do digest/summary derivatives still carry the body TOKEN "
                    "after id-based purge?"
                ),
                "verdict": decide(
                    controls_ok,
                    absent=False,
                    survivors=deriv_token or deriv_hash,
                ),
                "token_hits": [
                    h for h in post["by_target_token"] if h["store"] == "derivatives"
                ],
                "source_probe": P2_CMD,
                "verifier_probe": P1_CMD,
            },
            {
                "id": "caches",
                "question": "Can a production artifact cache still serve the purged body?",
                "verdict": "NOT-CHECKED",
                "reason": "production artifact-cache modules are absent on this worktree",
                "found": inventory["cache_modules"],
            },
            {
                "id": "embeddings",
                "question": "Do embedding vectors still encode the purged body?",
                "verdict": "NOT-CHECKED",
                "reason": "no embedding runtime or store on this worktree",
                "found": inventory["embedding_modules"],
            },
            {
                "id": "backups",
                "question": "Does a backup copy of the purged artifact remain?",
                "verdict": "NOT-CHECKED",
                "reason": "no production artifact-backup store on this worktree",
                "found": inventory["backup_modules"],
            },
            {
                "id": "mirrors",
                "question": "Does a mirror still hold the purged artifact?",
                "verdict": "NOT-CHECKED",
                "reason": "no production artifact-mirror store on this worktree",
                "found": inventory["mirror_modules"],
            },
        ]
        if not controls_ok:
            for row in targets:
                row["verdict"] = "NOT-CHECKED"
                row["downgraded"] = "missing-or-failed-control"

        return {
            "unit_id": UNIT,
            "inventory": inventory,
            "seed": {
                "target_id": TARGET_ID,
                "control_id": CONTROL_ID,
                "target_token": TARGET_TOKEN,
                "control_token": CONTROL_TOKEN,
                "target_sha256": seed["target_sha256"],
                "control_sha256": seed["control_sha256"],
            },
            "purge": purge,
            "tests": tests,
            "controls_ok": controls_ok,
            "targets": targets,
            "counts": {
                "pre_target_id": len(pre["by_target_id"]),
                "post_target_id": len(post["by_target_id"]),
                "pre_target_token": len(pre["by_target_token"]),
                "post_target_token": len(post["by_target_token"]),
                "post_control_id": len(post["by_control_id"]),
                "post_control_token": len(post["by_control_token"]),
                "post_target_id_stores": stores_of(post["by_target_id"]),
                "post_target_token_stores": stores_of(post["by_target_token"]),
            },
            "post_target_id_hits": post["by_target_id"],
            "post_target_token_hits": post["by_target_token"],
            "post_control_id_hits": post["by_control_id"],
            "post_control_token_hits": post["by_control_token"],
        }


def targets_from_artifact(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Read enumerated targets from a receipt-shaped or legacy artifact."""
    if not isinstance(doc, dict):
        return []
    for bag in (doc, doc.get("report") or {}, doc.get("extensions") or {}):
        if not isinstance(bag, dict):
            continue
        rows = bag.get("targets")
        if isinstance(rows, list) and rows:
            return [r for r in rows if isinstance(r, dict)]
    return []


def qualitative(campaign: dict[str, Any]) -> dict[str, str]:
    return {row["id"]: row["verdict"] for row in campaign["targets"]}


def render_probe1(campaign: dict[str, Any]) -> str:
    payload = {
        "probe": "probe1-id-hash-survivors",
        "unit_id": UNIT,
        "controls_ok": campaign["controls_ok"],
        "purge_api_absent": campaign["purge"]["production_purge_api_absent"],
        "post_target_id_stores": campaign["counts"]["post_target_id_stores"],
        "post_control_id_hits": len(campaign["post_control_id_hits"]),
        "verdicts": qualitative(campaign),
    }
    return "\n".join(
        [
            json.dumps(payload, sort_keys=True),
            "id-survivors={stores} control-id-hits={n} purge-api-absent={abs}".format(
                stores=",".join(campaign["counts"]["post_target_id_stores"]) or "-",
                n=len(campaign["post_control_id_hits"]),
                abs=campaign["purge"]["production_purge_api_absent"],
            ),
            "SUCCESS:ADV-0044-probe1 id-hash survivor search after purge",
        ]
    )


def render_probe2(campaign: dict[str, Any]) -> str:
    payload = {
        "probe": "probe2-token-derivatives",
        "unit_id": UNIT,
        "controls_ok": campaign["controls_ok"],
        "post_target_token_stores": campaign["counts"]["post_target_token_stores"],
        "post_control_token_hits": len(campaign["post_control_token_hits"]),
        "verdicts": qualitative(campaign),
    }
    return "\n".join(
        [
            json.dumps(payload, sort_keys=True),
            "token-survivors={stores} control-token-hits={n}".format(
                stores=",".join(campaign["counts"]["post_target_token_stores"]) or "-",
                n=len(campaign["post_control_token_hits"]),
            ),
            "SUCCESS:ADV-0044-probe2 body-token derivative search after purge",
        ]
    )


if __name__ == "__main__":
    doc = run_campaign()
    print(
        json.dumps(
            {"controls_ok": doc["controls_ok"], "verdicts": qualitative(doc)},
            indent=2,
            sort_keys=True,
        )
    )
    raise SystemExit(0 if doc["controls_ok"] else 1)
