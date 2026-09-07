#!/usr/bin/env python3
"""AUD-0048 Probe 2: resolve each tag/branch ref to its current SHA.

Catalog evidence_requirement Probe 2:
  resolve each tag to its current SHA and record it, so a later silent retag
  is detectable — the syntax check alone cannot tell you what the tag points
  at today.

Uses `git ls-remote` (no GitHub API token required). Records both the peeled
annotated-tag object and the commit SHA when available.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
P1 = PROBE / "probe1-syntactic-classify.json"
OUT_JSON = PROBE / "probe2-tag-resolution.json"
OUT_RAW = PROBE / "probe2-tag-resolution.raw.txt"

RESOLVE_CLASSES = {"tag-pinned", "branch-pinned"}


def git_ls_remote(owner: str, repo: str, ref: str, timeout: int = 60) -> dict:
    """Resolve ref via git ls-remote. Returns structured result."""
    url = f"https://github.com/{owner}/{repo}.git"
    # Query both tags and heads for the symbolic name.
    candidates = [
        f"refs/tags/{ref}",
        f"refs/tags/{ref}^{{}}",  # peeled annotated tag → commit
        f"refs/heads/{ref}",
        ref,
    ]
    cmd = ["git", "ls-remote", url, *candidates]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"timeout after {timeout}s",
            "url": url,
            "ref": ref,
            "commit_sha": None,
            "raw_lines": [],
        }
    except OSError as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "url": url,
            "ref": ref,
            "commit_sha": None,
            "raw_lines": [],
        }

    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    mapping: dict[str, str] = {}
    for ln in lines:
        parts = ln.split()
        if len(parts) >= 2:
            mapping[parts[1]] = parts[0]

    commit_sha = None
    tag_object = None
    # Prefer peeled annotated tag commit.
    peeled = mapping.get(f"refs/tags/{ref}^{{}}")
    if peeled:
        commit_sha = peeled
        tag_object = mapping.get(f"refs/tags/{ref}")
    elif f"refs/tags/{ref}" in mapping:
        commit_sha = mapping[f"refs/tags/{ref}"]
        tag_object = commit_sha
    elif f"refs/heads/{ref}" in mapping:
        commit_sha = mapping[f"refs/heads/{ref}"]
    elif ref in mapping:
        commit_sha = mapping[ref]

    return {
        "ok": r.returncode == 0 and commit_sha is not None,
        "exit_code": r.returncode,
        "error": None
        if (r.returncode == 0 and commit_sha)
        else (r.stderr or "").strip()[:500],
        "url": url,
        "ref": ref,
        "commit_sha": commit_sha,
        "tag_object_sha": tag_object,
        "raw_lines": lines[:20],
        "queried_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def unique_resolve_targets(uses: list[dict]) -> list[dict]:
    """Deduplicate owner/repo@ref for tag/branch pins (include fixtures)."""
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for row in uses:
        if row.get("pin_class") not in RESOLVE_CLASSES:
            continue
        if row.get("kind") != "github-action":
            continue
        owner = row.get("owner")
        repo = row.get("repo")
        ref = row.get("ref")
        if not owner or not repo or not ref:
            continue
        key = (owner, repo, ref)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "owner": owner,
                "repo": repo,
                "ref": ref,
                "pin_class": row["pin_class"],
                "sample_uses": row["uses"],
                "sample_path": row["path"],
            }
        )
    return out


def main() -> int:
    if not P1.is_file():
        sys.stderr.write(f"MISSING probe1 output: {P1}\n")
        return 2
    p1 = json.loads(P1.read_text(encoding="utf-8"))
    targets = unique_resolve_targets(p1.get("uses", []))
    resolutions = []
    ok_count = 0
    fail_count = 0
    for t in targets:
        res = git_ls_remote(t["owner"], t["repo"], t["ref"])
        row = {**t, **res}
        resolutions.append(row)
        if res["ok"]:
            ok_count += 1
        else:
            fail_count += 1

    # Control: tag-pinned fixture must resolve to a 40-char SHA.
    tag_fixture = [
        r
        for r in resolutions
        if r.get("sample_path", "").endswith("fixtures/tag-pinned.yml")
        or "tag-pinned.yml" in r.get("sample_path", "")
    ]
    tag_resolved = (
        all(
            r.get("ok")
            and isinstance(r.get("commit_sha"), str)
            and len(r["commit_sha"]) == 40
            for r in tag_fixture
        )
        and len(tag_fixture) >= 1
    )

    result = {
        "unit": "AUD-0048",
        "probe": 2,
        "ok": tag_resolved,
        "targets": len(targets),
        "resolved_ok": ok_count,
        "resolved_fail": fail_count,
        "tag_fixture_resolved": tag_resolved,
        "tag_fixture_count": len(tag_fixture),
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "git ls-remote https://github.com/<owner>/<repo>.git refs/tags/<ref> refs/heads/<ref>",
        "resolutions": resolutions,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "PROBE 2: resolve tag/branch refs to current commit SHA via git ls-remote",
        "unit=AUD-0048",
        f"targets={len(targets)} resolved_ok={ok_count} resolved_fail={fail_count}",
        f"tag_fixture_count={len(tag_fixture)} tag_fixture_resolved={tag_resolved}",
        f"method={result['method']}",
        f"measured_at={result['measured_at']}",
    ]
    for r in resolutions:
        lines.append(
            "RESOLVE|"
            + json.dumps(
                {
                    "owner": r["owner"],
                    "repo": r["repo"],
                    "ref": r["ref"],
                    "pin_class": r["pin_class"],
                    "ok": r["ok"],
                    "commit_sha": r.get("commit_sha"),
                    "tag_object_sha": r.get("tag_object_sha"),
                    "sample_path": r.get("sample_path"),
                },
                sort_keys=True,
            )
        )
    lines.append(
        "SUCCESS:AUD-0048-probe2" if tag_resolved else "FAILED:AUD-0048-probe2"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if tag_resolved else 1


if __name__ == "__main__":
    raise SystemExit(main())
