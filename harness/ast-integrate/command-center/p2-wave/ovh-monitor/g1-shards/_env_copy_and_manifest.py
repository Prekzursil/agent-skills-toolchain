#!/usr/bin/env python3
"""Copy writable harness fixtures and refresh per-unit manifests for class-env."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROBES = REPO / "command-center" / "p2-wave" / "probes"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
HARNESS = Path("C:/Users/Prekzursil/.claude/harness-restore-20260806")
IDS = [
    "ADV-0139",
    "ARC-0005",
    "ARC-0004",
    "ARC-0049",
    "ARC-0089",
    "AUD-0074",
    "BLD-0036",
    "CNF-0045",
    "CNF-0101",
    "IMP-0025",
    "IMP-0036",
    "RES-0010",
    "RES-0015",
    "RES-0102",
    "RES-0177",
    "TST-0072",
    "WFA-0018",
    "WFA-0039",
    "WFA-0044",
    "WFA-0045",
    "WFA-0133",
    "WFA-0141",
]


def lf_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes().replace(b"\r\n", b"\n")
    dest.write_bytes(data)


def sha(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def copy_named(dest_dir: Path, names: list[str]) -> int:
    n = 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = HARNESS / name
        if src.is_file():
            lf_copy(src, dest_dir / name)
            n += 1
        else:
            print("MISSING harness", name)
    return n


def refresh_manifest(uid: str, rel: str) -> None:
    out = REPO / rel
    man_path = PROBES / uid / "UNIT-ARTIFACT-MANIFEST.json"
    if not out.is_file() or not man_path.is_file():
        print("skip manifest", uid, "out", out.is_file(), "man", man_path.is_file())
        return
    digest, nbytes = sha(out)
    man = json.loads(man_path.read_text(encoding="utf-8"))
    rows = list(man.get("artifacts") or [])
    hit = False
    for a in rows:
        if not isinstance(a, dict):
            continue
        if str(a.get("path") or "").replace("\\", "/") != rel:
            continue
        a["sha256"] = digest
        a["bytes"] = nbytes
        a["present"] = True
        a["unit_id"] = uid
        hit = True
    if not hit:
        rows.append(
            {
                "path": rel,
                "sha256": digest,
                "bytes": nbytes,
                "present": True,
                "unit_id": uid,
            }
        )
    man["artifacts"] = rows
    man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("manifest", uid, "bytes", nbytes, "sha", digest[:16])


def main() -> int:
    names = [
        "08-WORKFLOW-CANDIDATE-REGISTRY.json",
        "_USER-PROMPTS.md",
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    ]
    print("copied WFA-0039", copy_named(PROBES / "WFA-0039" / "fixtures" / "harness-restore-20260806", names))
    print("copied AUD-0074", copy_named(PROBES / "AUD-0074" / "fixtures" / "harness-restore-20260806", names))
    print("copied WFA-0133", copy_named(PROBES / "WFA-0133" / "fixtures", ["10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json"]))
    print("copied WFA-0141", copy_named(PROBES / "WFA-0141" / "fixtures" / "live", names))

    agent = PROBES / "RES-0015" / "fixtures" / "bin" / "agent"
    if agent.is_file():
        data = agent.read_bytes().replace(b"\r\n", b"\n")
        if not data.startswith(b"#!/usr/bin/env python3\n"):
            data = b"#!/usr/bin/env python3\n" + data
        agent.write_bytes(data)
        print("agent bytes", len(data), "crlf", b"\r\n" in agent.read_bytes())

    index_js = (
        b"// cursor-agent index.js fixture for G-1 (not /root).\n"
        b"AGENTS.md CLAUDE.md CLAUDE.local.md\n"
        b".cursor/rules/**/*.mdc mcp.json .mcp.json\n"
        b"n.data?.paths??n.data?.globs\n"
        b"function as(e){return!0===e.data?.alwaysApply}\n"
        b"e.frontmatter.globs\n"
    )
    for rel in (
        PROBES / "ADV-0139" / "fixtures" / "cursor-agent" / "versions" / "2026.08.11-e8db854" / "index.js",
        PROBES / "RES-0010" / "fixtures" / "cursor-agent" / "index.js",
    ):
        rel.parent.mkdir(parents=True, exist_ok=True)
        rel.write_bytes(index_js)
        print("wrote", rel.relative_to(REPO), "bytes", len(index_js))

    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    by = {u["id"]: u for u in cat.get("work_units") or []}
    for uid in IDS:
        rel = str((by.get(uid) or {}).get("output_path") or "").replace("\\", "/")
        refresh_manifest(uid, rel)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
