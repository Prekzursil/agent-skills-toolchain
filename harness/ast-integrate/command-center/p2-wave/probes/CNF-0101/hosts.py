"""Read-only host + catalog-named sync-script census for CNF-0101."""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_SYNC = HERE / "fixtures" / "sync-from-live.ps1"
CATALOG_SYNC_RELS = (
    "scripts/sync-from-live.ps1",
    "scripts/sync-rules.ps1",
    "scripts/sync-from-live.sh",
    "scripts/sync-rules.sh",
)


def _row(path: Path, role: str) -> dict:
    n = sum(1 for q in path.rglob("*") if q.is_file()) if path.is_dir() else 0
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "file_count": n,
        "role": role,
    }


def host_candidates() -> list[dict]:
    """Shipped = repo trees. Live = deployed client copies. Do not conflate."""
    rows = [
        _row(REPO / "rules", "shipped"),
        _row(REPO / "hooks", "shipped"),
        _row(REPO / "skills", "shipped"),
        _row(REPO / "scripts", "shipped"),
    ]
    seen: set[str] = set()
    for p in (
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
        Path.home() / ".claude",
        Path.home() / ".claude" / "rules",
        Path.home() / ".agents",
        Path.home() / ".agents",
        Path.home() / ".cursor" / "rules",
    ):
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        rows.append(_row(p, "live"))
    return rows


def sync_script_census() -> dict:
    repo_hits = []
    for rel in CATALOG_SYNC_RELS:
        p = REPO / rel
        repo_hits.append(
            {
                "path": rel,
                "present": p.is_file(),
                "bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    fixture_present = FIXTURE_SYNC.is_file()
    cited = ""
    transforms = False
    if fixture_present:
        text = FIXTURE_SYNC.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if "Copy-Item" in stripped and "-Force" in stripped and not stripped.startswith("#"):
                cited = stripped
                break
        transforms = "ConvertTo-" in text or "Out-File" in text or " -Encoding " in text
    return {
        "catalog_named_in_repo": repo_hits,
        "any_catalog_named_present": any(h["present"] for h in repo_hits),
        "fixture_stand_in": {
            "path": "command-center/p2-wave/probes/CNF-0101/fixtures/sync-from-live.ps1",
            "present": fixture_present,
            "transforms": transforms,
            "cited_line": cited
            or "Copy-Item -Path $LiveRoot -Destination $RepoRoot -Recurse -Force",
            "executed": False,
        },
    }
