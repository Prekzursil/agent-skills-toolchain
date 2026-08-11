"""F1 refuter: mechanical enumeration of codex-* skill stubs.

Mechanically DIFFERENT probe from the claimed anchor (ls/du + git ls-files):
  - walks the whole repo tree with os.walk (not a glob/ls of one dir)
  - measures the GIT BLOB bytes via `git cat-file -s` (not on-disk du, which
    can differ by CRLF) AND the on-disk bytes, and compares them
  - classifies stub-vs-real by CONTENT STRUCTURE (line count, presence of a
    body beyond frontmatter) rather than by byte size alone, so the size band
    is a *derived* observation, not the detector.
"""

import hashlib
import json
import os
import subprocess

REPO = r"C:\Users\Prekzursil\source\ast-integrate"


def git(*args):
    return subprocess.run(
        ["git", "-C", REPO, *args], capture_output=True, text=True, check=False
    ).stdout


def blob_size(rev, path):
    out = subprocess.run(
        ["git", "-C", REPO, "cat-file", "-s", f"{rev}:{path}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return int(out.stdout.strip()) if out.returncode == 0 else None


# ---- 1. Walk the WHOLE repo for any SKILL.md (or any file) under a dir whose
#         name starts with "codex", plus any file whose path contains "codex".
hits = []
skipdirs = {".git", "node_modules", ".pytest_cache", ".ruff_cache"}
for dirpath, dirnames, filenames in os.walk(REPO):
    dirnames[:] = [d for d in dirnames if d not in skipdirs]
    for fn in filenames:
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, REPO).replace("\\", "/")
        if "codex" in rel.lower():
            hits.append(rel)

# ---- 2. Narrow to SKILL.md files whose immediate parent starts with 'codex'
skill_files = sorted(
    p for p in hits if p.endswith("/SKILL.md") and p.split("/")[-2].startswith("codex")
)

tracked = set(git("ls-files").splitlines())

rows = []
for rel in skill_files:
    full = os.path.join(REPO, rel.replace("/", os.sep))
    raw = open(full, "rb").read()
    disk = len(raw)
    bsz = blob_size("HEAD", rel) if rel in tracked else None
    txt = raw.decode("utf-8", "replace")
    lines = txt.splitlines()
    # structural stub test: frontmatter + <=3 non-empty body lines
    fm_end = None
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                fm_end = i
                break
    body = [
        line
        for line in lines[(fm_end + 1 if fm_end is not None else 0) :]
        if line.strip()
    ]
    rows.append(
        {
            "path": rel,
            "name": rel.split("/")[-2],
            "disk_bytes": disk,
            "blob_bytes": bsz,
            "tracked": rel in tracked,
            "total_lines": len(lines),
            "body_lines_after_frontmatter": len(body),
            "structural_stub": len(body) <= 3,
            "in_claimed_size_band_210_231": 210 <= disk <= 231,
            "blob_in_band": (bsz is not None and 210 <= bsz <= 231),
            "sha256_8": hashlib.sha256(raw).hexdigest()[:8],
        }
    )

claimed = {
    "codex-audit",
    "codex-brainstorm",
    "codex-coordinate",
    "codex-curate",
    "codex-discuss",
    "codex-fix",
    "codex-governance",
    "codex-review",
    "codex-triage",
}

structural = {r["name"] for r in rows if r["structural_stub"]}
band_disk = {r["name"] for r in rows if r["in_claimed_size_band_210_231"]}
band_blob = {r["name"] for r in rows if r["blob_in_band"]}

out = {
    "total_codex_star_SKILL_md": len(rows),
    "rows": rows,
    "claimed_set": sorted(claimed),
    "structural_stub_set": sorted(structural),
    "disk_band_set": sorted(band_disk),
    "blob_band_set": sorted(band_blob),
    "structural_minus_claimed": sorted(structural - claimed),
    "claimed_minus_structural": sorted(claimed - structural),
    "diskband_minus_claimed": sorted(band_disk - claimed),
    "claimed_minus_diskband": sorted(claimed - band_disk),
    "blobband_minus_claimed": sorted(band_blob - claimed),
    "claimed_minus_blobband": sorted(claimed - band_blob),
    "other_codex_paths_outside_agents_skills": sorted(
        p for p in hits if not p.startswith(".agents/skills/")
    )[:200],
}
print(json.dumps(out, indent=2))
