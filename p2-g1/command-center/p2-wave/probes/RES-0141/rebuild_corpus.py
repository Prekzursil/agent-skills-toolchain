#!/usr/bin/env python3
"""Rebuild corpus.json from frozen GitHub captures + changelog files.

Does not call api.github.com. Does not import detector.py or labels.py.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from changelogs import changelog_index  # noqa: E402
from common import (  # noqa: E402
    CAPTURES,
    CORPUS,
    dump_json,
    is_x_0_0,
    parse_semver,
    sha256_bytes,
)
from contract import N_NOTES  # noqa: E402
from fetch_corpus import REPOS  # noqa: E402

STEM_TO_REPO = {f"github-{o}-{r}-releases": (o, r) for o, r in REPOS}


def owner_repo(stem: str) -> tuple[str, str] | None:
    return STEM_TO_REPO.get(stem)


def previous_in_order(
    ver: tuple[int, int, int], versions: list[tuple[int, int, int]]
) -> tuple[int, int, int] | None:
    lower = [v for v in versions if v < ver]
    return max(lower) if lower else None


def is_patch_step(
    cur: tuple[int, int, int] | None, prev: tuple[int, int, int] | None
) -> bool:
    if not cur or not prev:
        return False
    return cur[0] == prev[0] and cur[1] == prev[1] and cur[2] == prev[2] + 1


def main() -> int:
    gh_notes: list[dict] = []
    for body_path in sorted(CAPTURES.glob("github-*-releases.body")):
        stem = body_path.name[: -len(".body")]
        loc = owner_repo(stem)
        if not loc:
            continue
        owner, repo = loc
        meta = json.loads((CAPTURES / f"{stem}.meta.json").read_text(encoding="utf-8"))
        releases = json.loads(body_path.read_text(encoding="utf-8"))
        if not isinstance(releases, list):
            continue
        cl_idx = changelog_index(owner, repo)
        parsed_versions: list[tuple[int, int, int]] = []
        rows: list[dict] = []
        for rel in releases:
            if not isinstance(rel, dict) or rel.get("draft"):
                continue
            tag = str(rel.get("tag_name") or "")
            ver = parse_semver(tag)
            if ver is None:
                continue
            if rel.get("prerelease"):
                continue
            body = str(rel.get("body") or "").strip()
            ver_s = f"{ver[0]}.{ver[1]}.{ver[2]}"
            cl = cl_idx.get(ver_s) or cl_idx.get(tag.lstrip("v"))
            changelog_text = (cl or {}).get("text") or ""
            combined = body
            if changelog_text and changelog_text not in combined:
                combined = (body + "\n\n" + changelog_text).strip() if body else changelog_text
            if len(combined) < 40:
                continue
            parsed_versions.append(ver)
            rows.append(
                {
                    "owner": owner,
                    "repo": repo,
                    "tag": tag,
                    "semver": list(ver),
                    "name": rel.get("name") or tag,
                    "html_url": rel.get("html_url"),
                    "api_url": rel.get("url"),
                    "published_at": rel.get("published_at"),
                    "github_body": body,
                    "changelog_text": changelog_text,
                    "text": combined,
                    "gh_capture_id": stem,
                    "gh_lineage": {
                        "resolved_url": rel.get("html_url") or meta.get("resolved_url"),
                        "api_url": rel.get("url") or meta.get("requested_url"),
                        "fetch_timestamp": meta.get("fetched_at"),
                        "http_status": meta.get("http_status"),
                        "sha256_fetched_bytes": meta.get("sha256"),
                        "sha256_note_text": sha256_bytes(combined.encode("utf-8")),
                        "capture_path": f"command-center/p2-wave/probes/RES-0141/captures/{stem}.body",
                    },
                    "changelog_lineage": (
                        {
                            "resolved_url": cl.get("resolved_url"),
                            "requested_url": cl.get("requested_url"),
                            "fetch_timestamp": cl.get("fetched_at"),
                            "http_status": cl.get("http_status"),
                            "sha256_fetched_bytes": cl.get("sha256"),
                            "capture_id": cl.get("capture_id"),
                            "path": cl.get("path"),
                            "ref": cl.get("ref"),
                        }
                        if cl
                        else None
                    ),
                }
            )
        versions_u = sorted(set(tuple(r["semver"]) for r in rows))
        for r in rows:
            ver_t = tuple(r["semver"])
            prev = previous_in_order(ver_t, list(versions_u))
            r["previous_semver"] = list(prev) if prev else None
            r["previous_tag"] = (
                f"{prev[0]}.{prev[1]}.{prev[2]}" if prev else None
            )
            r["id"] = f"{owner}-{repo}-{r['tag']}".replace("/", "_")
            gh_notes.append(r)

        # changelog-only X.0.0 not already present
        have = {tuple(r["semver"]) for r in rows}
        for ver_s, cl in cl_idx.items():
            ver = parse_semver(ver_s)
            if not is_x_0_0(ver) or ver in have:
                continue
            text = cl["text"]
            if len(text) < 80:
                continue
            nid = f"{owner}-{repo}-{ver_s}-changelog"
            gh_notes.append(
                {
                    "id": nid,
                    "owner": owner,
                    "repo": repo,
                    "tag": ver_s,
                    "semver": list(ver),
                    "name": ver_s,
                    "html_url": cl.get("resolved_url"),
                    "api_url": None,
                    "published_at": None,
                    "github_body": "",
                    "changelog_text": text,
                    "text": text,
                    "gh_capture_id": None,
                    "previous_semver": None,
                    "previous_tag": None,
                    "gh_lineage": None,
                    "changelog_lineage": {
                        "resolved_url": cl.get("resolved_url"),
                        "requested_url": cl.get("requested_url"),
                        "fetch_timestamp": cl.get("fetched_at"),
                        "http_status": cl.get("http_status"),
                        "sha256_fetched_bytes": cl.get("sha256"),
                        "sha256_note_text": sha256_bytes(text.encode("utf-8")),
                        "capture_id": cl.get("capture_id"),
                        "path": cl.get("path"),
                        "ref": cl.get("ref"),
                    },
                    "source_kind": "changelog-only",
                }
            )

    # previous for changelog-only using all versions of that repo
    by_repo: dict[tuple[str, str], list[tuple[int, int, int]]] = {}
    for n in gh_notes:
        by_repo.setdefault((n["owner"], n["repo"]), []).append(tuple(n["semver"]))
    for n in gh_notes:
        if n.get("previous_semver"):
            continue
        ver_t = tuple(n["semver"])
        prev = previous_in_order(ver_t, list(set(by_repo[(n["owner"], n["repo"])])))
        n["previous_semver"] = list(prev) if prev else None
        n["previous_tag"] = f"{prev[0]}.{prev[1]}.{prev[2]}" if prev else None
        n.setdefault("source_kind", "github+changelog" if n.get("changelog_text") else "github")

    majors = [n for n in gh_notes if is_x_0_0(tuple(n["semver"]))]
    patches = [
        n
        for n in gh_notes
        if is_patch_step(tuple(n["semver"]), tuple(n["previous_semver"]) if n.get("previous_semver") else None)
        and not is_x_0_0(tuple(n["semver"]))
    ]
    rest = [
        n
        for n in gh_notes
        if n["id"] not in {x["id"] for x in majors} and n["id"] not in {x["id"] for x in patches}
    ]

    selected: list[dict] = []
    seen: set[str] = set()
    for bucket in (majors, patches, rest):
        for n in bucket:
            if n["id"] in seen:
                continue
            seen.add(n["id"])
            selected.append(n)
            if len(selected) >= N_NOTES:
                break
        if len(selected) >= N_NOTES:
            break

    n_major = sum(1 for n in selected if is_x_0_0(tuple(n["semver"])))
    n_patch = sum(
        1
        for n in selected
        if is_patch_step(
            tuple(n["semver"]),
            tuple(n["previous_semver"]) if n.get("previous_semver") else None,
        )
    )
    corpus = {
        "unit_id": "RES-0141",
        "n_requested": N_NOTES,
        "n_selected": len(selected),
        "n_candidates": len(gh_notes),
        "n_x_0_0_selected": n_major,
        "n_patch_step_selected": n_patch,
        "selection_rule": (
            "Main-package tags only (no @monorepo, no prerelease). Previous "
            "version is the greatest strictly-smaller semver in the same repo, "
            "not GitHub API adjacency. Prefer X.0.0 notes, then adjacent patch "
            "steps, then fill. Changelog sections from raw.githubusercontent.com "
            "are concatenated onto GitHub release bodies when the version heading "
            "matches. Extra X.0.0 sections absent from the 20-release API window "
            "are admitted as changelog-only notes."
        ),
        "notes": selected,
    }
    dump_json(CORPUS, corpus)
    print(
        f"wrote {CORPUS} n={len(selected)} candidates={len(gh_notes)} "
        f"x.0.0={n_major} patch_steps={n_patch}"
    )
    if len(selected) < N_NOTES:
        print(f"FAILED:rebuild need {N_NOTES}")
        return 1
    print("SUCCESS:RES-0141-rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
