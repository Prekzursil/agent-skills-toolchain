#!/usr/bin/env python3
"""AUD-0048 Probe 1: syntactic classification of every uses: + permissions census.

Catalog evidence_requirement Probe 1:
  syntactic classification of each uses: reference as sha-pinned, tag-pinned,
  or branch-pinned.

Also inventories every permissions block (workflow-level and job-level) so the
unit can answer whether workflows declare least-privilege rather than inherit
the default GITHUB_TOKEN scope.

Required control (tests_required):
  a fixture with a branch-pinned action must be flagged at the highest severity,
  and a sha-pinned one must not be flagged.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBE = Path(__file__).resolve().parent
OUT_JSON = PROBE / "probe1-syntactic-classify.json"
OUT_RAW = PROBE / "probe1-syntactic-classify.raw.txt"

SHA_FULL = re.compile(r"^[0-9a-fA-F]{40}$")
SHA_SHORT = re.compile(r"^[0-9a-fA-F]{7,39}$")
# Semver-ish tags: v4, v4.1, v4.1.2, 3.0.0, etc.
TAG_RE = re.compile(r"^v?\d+(\.\d+){0,3}([+-][0-9A-Za-z.-]+)?$")
BRANCH_NAMES = {
    "main",
    "master",
    "head",
    "develop",
    "devel",
    "dev",
    "trunk",
    "latest",
    "canary",
    "nightly",
    "next",
    "beta",
    "alpha",
    "staging",
    "production",
    "release",
}

SEVERITY = {
    "branch-pinned": "critical",
    "tag-pinned": "high",
    "sha-short": "medium",
    "sha-pinned": "none",
    "local": "none",
    "docker": "high",
    "unknown": "high",
}

USES_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)(?:-\s*)?uses:\s*(?P<ref>[^\s#]+)")
# Top-level permissions: line that starts at column 0 (or after BOM) with permissions:
WF_PERM_RE = re.compile(r"(?m)^permissions\s*:")
# Job-level: indented under jobs.<id>
JOB_HEADER_RE = re.compile(r"(?m)^  ([A-Za-z0-9_-]+)\s*:\s*(?:#.*)?$")
JOB_PERM_RE = re.compile(r"(?m)^    permissions\s*:")


def rel(p: Path) -> str:
    try:
        return str(p.resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def classify_ref(uses_value: str) -> dict:
    """Return pin_class / severity / owner / action / ref for one uses: value."""
    raw = uses_value.strip().strip("'\"")
    out: dict = {
        "uses": raw,
        "pin_class": "unknown",
        "severity": "high",
        "flagged": True,
        "owner": None,
        "action": None,
        "ref": None,
        "third_party": True,
        "kind": "github-action",
    }
    if raw.startswith("./") or raw.startswith(".\\"):
        out.update(
            {
                "pin_class": "local",
                "severity": "none",
                "flagged": False,
                "third_party": False,
                "kind": "local-action",
                "action": raw.split("@", 1)[0],
                "ref": raw.split("@", 1)[1] if "@" in raw else "",
            }
        )
        return out
    if raw.startswith("docker://"):
        out.update(
            {
                "pin_class": "docker",
                "severity": "high",
                "flagged": True,
                "kind": "docker-action",
                "action": raw,
                "ref": raw.rsplit(":", 1)[-1] if ":" in raw[9:] else "",
            }
        )
        return out

    if "@" not in raw:
        out.update({"pin_class": "unknown", "action": raw, "ref": ""})
        return out

    left, ref = raw.rsplit("@", 1)
    out["ref"] = ref
    out["action"] = left
    parts = left.split("/")
    if len(parts) >= 2:
        out["owner"] = parts[0]
        # owner/repo or owner/repo/path
        out["repo"] = parts[1]
    else:
        out["owner"] = None
        out["repo"] = left

    if SHA_FULL.match(ref):
        out["pin_class"] = "sha-pinned"
        out["severity"] = "none"
        out["flagged"] = False
    elif SHA_SHORT.match(ref) and not TAG_RE.match(ref):
        # Short SHAs are not full-commit pins; still mutable/ambiguous.
        out["pin_class"] = "sha-short"
        out["severity"] = "medium"
        out["flagged"] = True
    elif ref.lower() in BRANCH_NAMES or "/" in ref or ref.startswith("refs/"):
        out["pin_class"] = "branch-pinned"
        out["severity"] = "critical"
        out["flagged"] = True
    elif TAG_RE.match(ref):
        out["pin_class"] = "tag-pinned"
        out["severity"] = "high"
        out["flagged"] = True
    else:
        # Non-semver symbolic refs (feature branches, release/x) → branch-pinned.
        out["pin_class"] = "branch-pinned"
        out["severity"] = "critical"
        out["flagged"] = True
    return out


def parse_permissions(text: str, path: str) -> list[dict]:
    """Collect workflow-level and job-level permissions blocks."""
    rows: list[dict] = []
    has_wf = bool(WF_PERM_RE.search(text))
    if has_wf:
        # Capture the immediate mapping under top-level permissions:
        m = WF_PERM_RE.search(text)
        assert m is not None
        start = m.end()
        block_lines = []
        for line in text[start:].splitlines()[1:]:
            if (
                line
                and not line.startswith((" ", "\t"))
                and not line.strip().startswith("#")
            ):
                break
            if line.strip():
                block_lines.append(line.rstrip())
        rows.append(
            {
                "path": path,
                "scope": "workflow",
                "job": None,
                "present": True,
                "snippet": "\n".join(block_lines[:12]),
            }
        )
    else:
        rows.append(
            {
                "path": path,
                "scope": "workflow",
                "job": None,
                "present": False,
                "snippet": "",
            }
        )

    # Job-level: find each job id then look for permissions under it until next job/top key.
    job_ids = [m.group(1) for m in JOB_HEADER_RE.finditer(text)]
    # Only consider headers that appear after a top-level `jobs:` key.
    jobs_m = re.search(r"(?m)^jobs\s*:", text)
    if not jobs_m:
        return rows
    jobs_region = text[jobs_m.end() :]
    # Split by job headers at 2-space indent.
    parts = re.split(r"(?m)^(  [A-Za-z0-9_-]+)\s*:(?:\s*#.*)?$", jobs_region)
    # parts: [preamble, jobname, body, jobname, body, ...]
    i = 1
    while i + 1 < len(parts):
        job_name = parts[i].strip()
        body = parts[i + 1]
        present = bool(re.search(r"(?m)^    permissions\s*:", body))
        snippet = ""
        if present:
            mm = re.search(r"(?m)^    permissions\s*:\s*(.*)$", body)
            if mm:
                lines = [mm.group(0).rstrip()]
                after = body[mm.end() :]
                for line in after.splitlines()[1:]:
                    if re.match(r"^    \S", line) and not line.startswith("      "):
                        break
                    if line.startswith("      ") or line.strip() == "":
                        if line.strip():
                            lines.append(line.rstrip())
                    else:
                        break
                snippet = "\n".join(lines[:12])
        rows.append(
            {
                "path": path,
                "scope": "job",
                "job": job_name,
                "present": present,
                "snippet": snippet,
            }
        )
        i += 2
    # Silence unused warning if jobs: present but no headers matched.
    _ = job_ids
    return rows


def workflow_paths() -> list[Path]:
    roots = [
        REPO / ".github" / "workflows",
        PROBE / "fixtures",
    ]
    out: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for p in sorted(root.rglob("*")):
            if p.suffix.lower() in {".yml", ".yaml"} and p.is_file():
                out.append(p)
    return out


def scan_file(path: Path) -> tuple[list[dict], list[dict]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    rpath = rel(path)
    uses_rows: list[dict] = []
    for m in USES_RE.finditer(text):
        # Skip commented-out uses:
        line_start = text.rfind("\n", 0, m.start()) + 1
        prefix = text[line_start : m.start()]
        if "#" in prefix:
            continue
        info = classify_ref(m.group("ref"))
        line_no = text.count("\n", 0, m.start()) + 1
        info.update(
            {
                "path": rpath,
                "line": line_no,
                "is_fixture": "/AUD-0048/fixtures/" in rpath.replace("\\", "/"),
                "fixture_kind": (
                    "branch-pinned"
                    if "branch-pinned" in rpath
                    else "sha-pinned"
                    if "sha-pinned" in rpath
                    else "tag-pinned"
                    if "tag-pinned" in rpath
                    else None
                ),
            }
        )
        uses_rows.append(info)
    perm_rows = parse_permissions(text, rpath)
    return uses_rows, perm_rows


def main() -> int:
    uses: list[dict] = []
    perms: list[dict] = []
    files = workflow_paths()
    for path in files:
        u, p = scan_file(path)
        uses.extend(u)
        perms.extend(p)

    by_class = Counter(r["pin_class"] for r in uses)
    by_sev = Counter(r["severity"] for r in uses if r["flagged"])
    production = [r for r in uses if not r["is_fixture"]]
    fixtures = [r for r in uses if r["is_fixture"]]

    # Permissions: workflows that inherit default token (no wf-level AND no job-level).
    by_path: dict[str, list[dict]] = {}
    for row in perms:
        by_path.setdefault(row["path"], []).append(row)
    inherit_default = []
    inherit_default_production = []
    for path, rows in sorted(by_path.items()):
        wf = [r for r in rows if r["scope"] == "workflow"]
        jobs = [r for r in rows if r["scope"] == "job"]
        wf_present = any(r["present"] for r in wf)
        any_job = any(r["present"] for r in jobs)
        if not wf_present and not any_job:
            inherit_default.append(path)
            if "/AUD-0048/fixtures/" not in path.replace("\\", "/"):
                inherit_default_production.append(path)

    # Required control
    branch_fix = [
        r
        for r in fixtures
        if r.get("fixture_kind") == "branch-pinned"
        and r["pin_class"] == "branch-pinned"
    ]
    sha_fix = [
        r
        for r in fixtures
        if r.get("fixture_kind") == "sha-pinned" and r["pin_class"] == "sha-pinned"
    ]
    branch_flagged_critical = (
        all(r["flagged"] and r["severity"] == "critical" for r in branch_fix)
        and len(branch_fix) >= 1
    )
    sha_not_flagged = all(not r["flagged"] for r in sha_fix) and len(sha_fix) >= 1
    control_ok = branch_flagged_critical and sha_not_flagged

    # Headline production counts (exclude fixtures)
    prod_by_class = Counter(r["pin_class"] for r in production)
    prod_flagged = [r for r in production if r["flagged"]]
    third_party_unpinned = [
        r
        for r in production
        if r["third_party"]
        and r["pin_class"]
        in {"branch-pinned", "tag-pinned", "sha-short", "docker", "unknown"}
    ]

    result = {
        "unit": "AUD-0048",
        "probe": 1,
        "ok": control_ok,
        "workflow_files_scanned": len(files),
        "uses_total": len(uses),
        "uses_production": len(production),
        "uses_fixture": len(fixtures),
        "by_pin_class": dict(by_class),
        "production_by_pin_class": dict(prod_by_class),
        "flagged_by_severity": dict(by_sev),
        "production_flagged_count": len(prod_flagged),
        "third_party_unpinned_count": len(third_party_unpinned),
        "permissions_blocks": perms,
        "workflows_inheriting_default_token": inherit_default,
        "workflows_inheriting_default_token_count": len(inherit_default),
        "production_workflows_inheriting_default_token": inherit_default_production,
        "production_workflows_inheriting_default_token_count": len(
            inherit_default_production
        ),
        "control": {
            "branch_pinned_fixture_rows": len(branch_fix),
            "branch_pinned_flagged_critical": branch_flagged_critical,
            "sha_pinned_fixture_rows": len(sha_fix),
            "sha_pinned_not_flagged": sha_not_flagged,
            "ok": control_ok,
        },
        "uses": uses,
        "third_party_unpinned": third_party_unpinned,
    }
    OUT_JSON.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    lines = [
        "PROBE 1: syntactic classification of uses: refs + permissions census",
        "unit=AUD-0048",
        f"workflow_files_scanned={len(files)}",
        f"uses_total={len(uses)} uses_production={len(production)} uses_fixture={len(fixtures)}",
        f"by_pin_class={dict(by_class)}",
        f"production_by_pin_class={dict(prod_by_class)}",
        f"production_flagged_count={len(prod_flagged)}",
        f"third_party_unpinned_count={len(third_party_unpinned)}",
        f"workflows_inheriting_default_token_count={len(inherit_default)}",
        f"production_workflows_inheriting_default_token_count={len(inherit_default_production)}",
        f"inherit_default={inherit_default}",
        f"inherit_default_production={inherit_default_production}",
        (
            f"CONTROL branch_rows={len(branch_fix)} "
            f"branch_critical={branch_flagged_critical} "
            f"sha_rows={len(sha_fix)} sha_clean={sha_not_flagged} ok={control_ok}"
        ),
    ]
    for r in uses:
        lines.append(
            "USES|"
            + json.dumps(
                {
                    "path": r["path"],
                    "line": r["line"],
                    "uses": r["uses"],
                    "pin_class": r["pin_class"],
                    "severity": r["severity"],
                    "flagged": r["flagged"],
                    "third_party": r["third_party"],
                    "fixture": r["is_fixture"],
                },
                sort_keys=True,
            )
        )
    for r in perms:
        lines.append(
            "PERM|"
            + json.dumps(
                {
                    "path": r["path"],
                    "scope": r["scope"],
                    "job": r["job"],
                    "present": r["present"],
                },
                sort_keys=True,
            )
        )
    lines.append(
        "SUCCESS:AUD-0048-probe1" if control_ok else "FAILED:AUD-0048-probe1-control"
    )
    raw = "\n".join(lines) + "\n"
    OUT_RAW.write_text(raw, encoding="utf-8")
    sys.stdout.write(raw)
    return 0 if control_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
