"""Change-detection check for the freeze set.

An inventory with no detector is a list, not a freeze. This check turns red
when a frozen file's hash changes without BOTH a version bump in the file and
a matching migration record. Non-frozen files are silent.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from inventory import digest_file, extract_version

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(.*)$")
_INT = re.compile(r"^(\d+)$")


def bump_version(value: str | None) -> str:
    if value is None or value == "unversioned":
        return "0.1.0"
    s = str(value)
    m = _SEMVER.match(s)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{int(m.group(3)) + 1}{m.group(4)}"
    m = _INT.match(s)
    if m:
        return str(int(m.group(1)) + 1)
    return s + ".1"


def version_bumped(old: str | None, new: str | None) -> bool:
    if new is None:
        return False
    if old is None or old == "unversioned":
        return new != "unversioned" and new != ""
    return str(new) != str(old)


def _live_file(root: Path, rel: str) -> Path:
    return (root / rel).resolve()


def check_tree(
    root: Path,
    freeze_rows: list[dict[str, Any]],
    migrations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compare live files under root to freeze anchors.

    GREEN only when every present freeze member is unchanged, or changed with
    a matching migration (from_sha256, to_sha256, from_version, to_version)
    AND the live file embeds the bumped to_version.
    """
    migrations = list(migrations or [])
    findings: list[dict[str, Any]] = []
    reds: list[dict[str, Any]] = []

    def mig_for(path: str, from_sha: str, to_sha: str) -> dict[str, Any] | None:
        for m in migrations:
            if (
                str(m.get("path") or "").replace("\\", "/") == path
                and m.get("from_sha256") == from_sha
                and m.get("to_sha256") == to_sha
            ):
                return m
        return None

    for row in freeze_rows:
        if not row.get("present"):
            continue
        rel = str(row["path"]).replace("\\", "/")
        freeze_sha = row.get("sha256")
        freeze_ver = row.get("freeze_version")
        live_path = _live_file(root, rel)
        if not live_path.is_file():
            finding = {
                "path": rel,
                "verdict": "RED",
                "reason": "frozen-file-deleted-without-migration",
                "freeze_sha256": freeze_sha,
                "live_sha256": None,
                "migration_matched": False,
            }
            findings.append(finding)
            reds.append(finding)
            continue
        live_sha, live_bytes = digest_file(live_path)
        live_ver = extract_version(live_path)
        if live_sha == freeze_sha:
            findings.append(
                {
                    "path": rel,
                    "verdict": "GREEN",
                    "reason": "unchanged",
                    "freeze_sha256": freeze_sha,
                    "live_sha256": live_sha,
                    "live_bytes": live_bytes,
                    "freeze_version": freeze_ver,
                    "live_version": live_ver,
                    "migration_matched": False,
                }
            )
            continue
        mig = mig_for(rel, str(freeze_sha), live_sha)
        bumped = version_bumped(freeze_ver, live_ver)
        mig_ok = bool(mig) and bumped and str(mig.get("to_version")) == str(live_ver)
        if mig_ok:
            findings.append(
                {
                    "path": rel,
                    "verdict": "GREEN",
                    "reason": "migrated-with-version-bump",
                    "freeze_sha256": freeze_sha,
                    "live_sha256": live_sha,
                    "live_bytes": live_bytes,
                    "freeze_version": freeze_ver,
                    "live_version": live_ver,
                    "migration_id": mig.get("id"),
                    "migration_matched": True,
                }
            )
            continue
        why = []
        if not mig:
            why.append("no-matching-migration")
        if not bumped:
            why.append("no-version-bump")
        elif mig and str(mig.get("to_version")) != str(live_ver):
            why.append("migration-to_version-mismatch")
        finding = {
            "path": rel,
            "verdict": "RED",
            "reason": "unversioned-or-unmigrated-hash-change:" + ",".join(why),
            "freeze_sha256": freeze_sha,
            "live_sha256": live_sha,
            "live_bytes": live_bytes,
            "freeze_version": freeze_ver,
            "live_version": live_ver,
            "migration_matched": bool(mig),
        }
        findings.append(finding)
        reds.append(finding)

    red = bool(reds)
    return {
        "red": red,
        "verdict": "RED" if red else "GREEN",
        "red_count": len(reds),
        "checked": len(findings),
        "reds": reds,
        "findings": findings,
    }


def _mutate_json_title(path: Path, suffix: str) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"not a JSON object: {path}")
    title = str(doc.get("title") or path.name)
    doc["title"] = title + suffix
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _set_json_version(path: Path, version: str) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"not a JSON object: {path}")
    doc["schema_version"] = version
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def pick_target(freeze_rows: list[dict[str, Any]]) -> dict[str, Any]:
    schemas = [
        r
        for r in freeze_rows
        if r.get("present")
        and r.get("class") == "schema"
        and str(r.get("path") or "").endswith(".json")
        and r.get("freeze_version")
    ]
    if not schemas:
        present = [r for r in freeze_rows if r.get("present")]
        if not present:
            raise RuntimeError("freeze set has no present files")
        return present[0]
    preferred = [
        r
        for r in schemas
        if r["path"].endswith("claim-record.schema.json")
        or r["path"].endswith("audit-detector-control.schema.json")
    ]
    return preferred[0] if preferred else schemas[0]


def materialize_scratch(
    repo: Path, freeze_rows: list[dict[str, Any]], dest: Path
) -> None:
    for row in freeze_rows:
        if not row.get("present"):
            continue
        src = repo / row["path"]
        dst = dest / row["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def run_both_states(
    repo: Path | None = None, freeze_rows: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Scratch-copy both-states control required by the catalog.

    1. Modify one frozen file without bumping version -> check RED.
    2. Bump version and add a matching migration -> check GREEN.
    3. Modify a non-frozen file -> check stays GREEN (does not freeze the repo).
    """
    from inventory import enumerate_freeze_set

    repo = (repo or Path(__file__).resolve().parents[3]).resolve()
    if freeze_rows is None:
        freeze_rows = enumerate_freeze_set(repo)["inventory"]
    target = pick_target(freeze_rows)
    rel = target["path"]
    decoy_rel = "command-center/audit/_AUD-0095-not-frozen.txt"

    with tempfile.TemporaryDirectory(prefix="AUD-0095-scratch-") as td:
        scratch = Path(td) / "tree"
        materialize_scratch(repo, freeze_rows, scratch)
        decoy = scratch / decoy_rel
        decoy.parent.mkdir(parents=True, exist_ok=True)
        decoy.write_text("not frozen\n", encoding="utf-8")

        target_path = scratch / rel
        _mutate_json_title(target_path, " [AUD-0095-unversioned-mutation]")
        unversioned = check_tree(scratch, freeze_rows, migrations=[])
        unversioned_red = unversioned["red"] is True
        verbatim_unversioned = (
            f"unversioned edit of {rel}: verdict={unversioned['verdict']} "
            f"red_count={unversioned['red_count']} "
            f"reason={(unversioned['reds'][0]['reason'] if unversioned['reds'] else 'none')}"
        )

        from_sha = target["sha256"]
        from_ver = target.get("freeze_version")
        to_ver = bump_version(from_ver)
        _set_json_version(target_path, to_ver)
        to_sha, _ = digest_file(target_path)
        migration = {
            "id": "AUD-0095-scratch-m1",
            "path": rel,
            "from_sha256": from_sha,
            "to_sha256": to_sha,
            "from_version": from_ver,
            "to_version": to_ver,
            "up": "scratch title mutation plus schema_version bump",
            "down": "restore freeze-anchor bytes",
        }
        migrated = check_tree(scratch, freeze_rows, migrations=[migration])
        migrated_green = migrated["red"] is False
        verbatim_migrated = (
            f"version bump+migration of {rel}: verdict={migrated['verdict']} "
            f"red_count={migrated['red_count']} to_version={to_ver}"
        )

        # Reset target to freeze-anchor bytes, then mutate only the decoy.
        orig = repo / rel
        target_path.write_bytes(orig.read_bytes())
        decoy.write_text("not frozen; mutated decoy\n", encoding="utf-8")
        silent = check_tree(scratch, freeze_rows, migrations=[])
        non_frozen_silent = silent["red"] is False
        verbatim_silent = (
            f"non-frozen {decoy_rel} mutated: freeze-check verdict="
            f"{silent['verdict']} red_count={silent['red_count']}"
        )

    passed = unversioned_red and migrated_green and non_frozen_silent
    return {
        "pass": passed,
        "target_path": rel,
        "target_class": target["class"],
        "unversioned_edit_red": unversioned_red,
        "version_bump_green": migrated_green,
        "non_frozen_silent": non_frozen_silent,
        "verbatim_unversioned": verbatim_unversioned,
        "verbatim_migrated": verbatim_migrated,
        "verbatim_silent": verbatim_silent,
        "unversioned": {
            "verdict": unversioned["verdict"],
            "red_count": unversioned["red_count"],
            "reason": unversioned["reds"][0]["reason"] if unversioned["reds"] else None,
        },
        "migrated": {
            "verdict": migrated["verdict"],
            "red_count": migrated["red_count"],
            "to_version": to_ver,
            "from_version": from_ver,
        },
        "non_frozen": {
            "verdict": silent["verdict"],
            "red_count": silent["red_count"],
            "path": decoy_rel,
        },
    }
