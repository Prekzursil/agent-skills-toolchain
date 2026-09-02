#!/usr/bin/env python3
"""Probe 1: backup destination outside the corpus, per-file sha256 manifest, secrets excluded."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from engine import (  # noqa: E402
    KEEP_ME_REL,
    artifact_backup,
    is_secret_name,
    iter_files,
    run_rehearsal,
)

ART = REPO / "command-center/audit/AUD-0092-rollback-backup-rehearsal.json"
SENTINEL = (
    "SUCCESS:AUD-0092 emitted only when the artifact at output_path exists, is non-empty, "
    "parses against output_schema, and both named probes are recorded with their verbatim output"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0092-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if "AUD0092CANARY_" in text:
        return fail("canary prefix leaked into artifact")

    live = run_rehearsal()
    if not live.get("ok"):
        return fail("live rehearsal not ok")
    if live["file_count"] < 1:
        return fail("backup file_count < 1")
    if not live["backup_outside_corpus"]:
        return fail("backup destination is not outside corpus")
    keep = live["keep_me"]
    if not keep.get("in_backup"):
        return fail("keep-me missing from backup")
    if keep.get("sha256") != next(
        (
            f["sha256"]
            for f in live["files"]
            if f["tree_id"] == "ast-integrate" and f["path"] == KEEP_ME_REL
        ),
        None,
    ):
        return fail("keep-me sha256 mismatch vs manifest")

    man_path = Path(live["manifest_path"])
    if not man_path.is_file():
        return fail("outside-corpus MANIFEST.json missing")
    man = json.loads(man_path.read_text(encoding="utf-8"))
    files = man.get("files") or []
    if len(files) != live["file_count"]:
        return fail(f"manifest len {len(files)} != live {live['file_count']}")
    for row in files:
        sha = str(row.get("sha256") or "")
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            return fail("manifest row missing sha256")
        if is_secret_name(Path(str(row.get("path") or "")).name):
            return fail("secret-named path present in backup manifest")

    backup_dest = Path(live["backup_destination"])
    secret_hits = [p.name for p in iter_files(backup_dest) if is_secret_name(p.name)]
    if secret_hits:
        return fail(f"secret-named files in backup dest: {secret_hits[:8]}")
    if not live["planted_secret_excluded"]:
        return fail("planted .env canary was not excluded")
    if live["canary_leaked_in_backup_n"] != 0:
        return fail("canary bytes leaked into backup")
    if live["secret_named_in_backup_n"] != 0:
        return fail("secret-named files copied into backup")

    art_backup = artifact_backup(doc)
    art_files = art_backup.get("files") or []
    if len(art_files) < 1:
        return fail("artifact backup.files empty")
    if not art_backup:
        return fail("artifact backup object missing")

    print(
        json.dumps(
            {
                "file_count": live["file_count"],
                "excluded_count": live["excluded_count"],
                "manifest_sha256": live["manifest_sha256"],
                "backup_outside_corpus": True,
                "keep_me_in_backup": True,
                "keep_me_sha256": keep["sha256"],
                "planted_secret_excluded": True,
                "secret_named_in_backup_n": 0,
                "computed_not_asserted": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"manifest files={live['file_count']} excluded={live['excluded_count']} "
        f"sha256={live['manifest_sha256'][:16]} dest={live['backup_destination']}"
    )
    print("SUCCESS:AUD-0092-probe1 backup manifest with per-file sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
