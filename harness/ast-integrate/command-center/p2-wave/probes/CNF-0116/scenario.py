"""Run both independent surfaces and the live-tree archive stand-in."""
from __future__ import annotations

import tempfile
from pathlib import Path

from inventory import (
    KNOWN_PRESENT_LIVE,
    KNOWN_PRESENT_REL,
    ROTATION_POOL_BASENAME,
    hits_in,
    inventory_doc,
)
from surfaces import (
    INCLUDE_RULES,
    LIVE_SKIP_PARTS,
    build_payload,
    enumerate_by_include_rules,
    git_check_ignore,
    git_history_names,
    git_is_tracked,
    git_ls_files,
    git_staged,
    init_git_repo,
    live_git_state,
    rotation_pool_state,
    zip_named,
    zip_tree,
    zip_namelist,
)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _surface(
    sid: str,
    method: str,
    entries: list[str],
    known_present: str,
    extra: dict | None = None,
) -> dict:
    found = known_present in entries
    row = {
        "id": sid,
        "method": method,
        "entry_count": len(entries),
        "entries_sample": entries[:40],
        "known_present": known_present,
        "known_present_found": found,
        "credential_hits": hits_in(entries),
        "enumerated_from": sid,
    }
    if extra:
        row.update(extra)
    return row


def run_scenario(live_root: Path | None = None) -> dict:
    live_root = live_root or REPO
    live_method = "zipfile.ZipFile.namelist on a packed live-tree archive (not include-rules)"
    git_method = (
        "git ls-files -z --cached; git diff --cached --name-only -z; "
        "git log --all --name-only --pretty=format: (not .gitignore)"
    )
    art_method = "zipfile.ZipFile.namelist (not include-rules)"

    with tempfile.TemporaryDirectory(prefix="cnf0116-") as tmp:
        root = Path(tmp)
        payload = root / "payload"
        meta = build_payload(payload)
        archives = root / "archives"
        clean_zip = archives / "clean.zip"
        dirty_zip = archives / "polluted.zip"
        live_zip = archives / "live-tree.zip"

        clean_rels = list(INCLUDE_RULES)
        dirty_rels = list(INCLUDE_RULES) + [meta["planted"]]
        clean_entries = zip_named(payload, clean_zip, clean_rels)
        dirty_entries = zip_named(payload, dirty_zip, dirty_rels)
        rules_listing = enumerate_by_include_rules(payload, list(INCLUDE_RULES))
        rules_missed_planted = meta["planted"] not in rules_listing and meta["planted"] in dirty_entries

        live_entries = zip_tree(
            live_root,
            live_zip,
            skip_parts=LIVE_SKIP_PARTS,
        )
        # Re-read from the archive so the listing is the artifact, not the walk.
        live_from_zip = zip_namelist(live_zip)
        if live_from_zip != live_entries:
            live_entries = live_from_zip

        git_root = root / "git-surface"
        # Copy payload into a dedicated git worktree (same bytes, independent root).
        for rel in (
            "README.md",
            "plugin.json",
            "dist/app.py",
            "rule.no-secrets.md",
            ".gitignore",
            "secrets/planted.credentials.json",
            ROTATION_POOL_BASENAME,
        ):
            src = payload / rel
            dst = git_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            dst.chmod(src.stat().st_mode)
        git_meta = {
            "rotation_pool_size": (git_root / ROTATION_POOL_BASENAME).stat().st_size,
            "rotation_pool_mtime_ns": (git_root / ROTATION_POOL_BASENAME).stat().st_mtime_ns,
        }
        init_git_repo(git_root)
        tracked = git_ls_files(git_root)
        staged = git_staged(git_root)
        history = git_history_names(git_root)
        planted = meta["planted"]
        ignore_would_drop = git_check_ignore(git_root, planted)
        ignore_not_evidence = ignore_would_drop and git_is_tracked(git_root, planted)
        pool = rotation_pool_state(
            git_root, git_meta["rotation_pool_size"], git_meta["rotation_pool_mtime_ns"]
        )
        # History must still name .env after deletion from HEAD.
        history_has_env = ".env" in history
        head_has_env = ".env" in tracked

        live_git = live_git_state(live_root)
        if live_git.get("present"):
            live_git["known_present_found"] = KNOWN_PRESENT_LIVE in (live_git.get("tracked") or [])
            live_git["credential_hits_tracked"] = hits_in(live_git.get("tracked") or [])
            live_git["credential_hits_history"] = hits_in(live_git.get("history_names") or [])

        clean_surface = _surface("artifact-clean-control", art_method, clean_entries, KNOWN_PRESENT_REL)
        dirty_surface = _surface(
            "artifact-polluted-control",
            art_method,
            dirty_entries,
            KNOWN_PRESENT_REL,
            extra={
                "include_rules_listing": rules_listing,
                "include_rules_missed_planted": rules_missed_planted,
                "planted_in_artifact": planted in dirty_entries,
            },
        )
        live_surface = _surface(
            "artifact-live-tree-archive",
            live_method,
            live_entries,
            KNOWN_PRESENT_LIVE,
        )
        git_union = sorted(set(tracked) | set(history) | set(staged))
        git_surface = _surface(
            "git-index-and-history",
            git_method,
            git_union,
            KNOWN_PRESENT_REL,
            extra={
                "tracked": tracked,
                "staged": staged,
                "history_names": history,
                "head_has_deleted_env": head_has_env,
                "history_has_deleted_env": history_has_env,
                "ignore_would_drop_planted": ignore_would_drop,
                "ignore_not_evidence": ignore_not_evidence,
                "planted_tracked": git_is_tracked(git_root, planted),
                "rotation_pool": pool,
                "working_tree_only_would_miss_history_env": (not head_has_env) and history_has_env,
            },
        )

        both_found = bool(dirty_surface["known_present_found"] and git_surface["known_present_found"])
        independent_fail = bool(
            (not dirty_surface["credential_hits"]) is False and git_surface["credential_hits"]
        )
        # One clean surface is not evidence for the other:
        # clean zip has zero hits; git fixture has tracked planted name.
        one_clean_not_other = bool(
            len(clean_surface["credential_hits"]) == 0 and len(git_surface["credential_hits"]) > 0
        )

        ok = (
            both_found
            and rules_missed_planted
            and ignore_not_evidence
            and pool["exists"]
            and not pool["tracked"]
            and not pool["staged"]
            and pool["unmodified"]
            and history_has_env
            and not head_has_env
            and one_clean_not_other
            and live_surface["known_present_found"]
        )
        return {
            "pass": ok,
            "inventory": inventory_doc(),
            "payload_meta": {k: meta[k] for k in ("known_present", "planted", "rotation_pool", "include_rules")},
            "surfaces": [clean_surface, dirty_surface, live_surface, git_surface],
            "live_git": live_git,
            "controls": {
                "known_present_on_artifact": dirty_surface["known_present_found"],
                "known_present_on_git": git_surface["known_present_found"],
                "known_present_on_live_archive": live_surface["known_present_found"],
                "include_rules_missed_planted": rules_missed_planted,
                "ignore_not_evidence": ignore_not_evidence,
                "rotation_pool_untracked": not pool["tracked"],
                "rotation_pool_unstaged": not pool["staged"],
                "rotation_pool_unmodified": pool["unmodified"],
                "one_clean_surface_is_not_evidence_for_the_other": one_clean_not_other,
                "history_not_working_tree_only": (not head_has_env) and history_has_env,
            },
            "independent_failure_demo": independent_fail or one_clean_not_other,
        }


def main() -> int:
    run = run_scenario()
    print(
        "ok={ok} artifact_ctrl={a} git_ctrl={g} live_ctrl={l} "
        "ignore_not_evidence={i} pool_untracked={p} rules_miss={r}".format(
            ok=run["pass"],
            a=run["controls"]["known_present_on_artifact"],
            g=run["controls"]["known_present_on_git"],
            l=run["controls"]["known_present_on_live_archive"],
            i=run["controls"]["ignore_not_evidence"],
            p=run["controls"]["rotation_pool_untracked"],
            r=run["controls"]["include_rules_missed_planted"],
        )
    )
    return 0 if run["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
