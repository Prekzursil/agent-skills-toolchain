#!/usr/bin/env python3
"""WFA-0019 corpus sweep: DEFINE-vs-mention extraction and inverse-join of 08/09/10.

Anchor verification reads the cited line and compares content. A file-exists
check is not sufficient (see verify_anchor mode="exists-only").
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_CORPUS = HERE / "fixtures" / "corpus"

DEFINE_HEADING = re.compile(
    r"^(#{1,6})\s+DEFINE\s+`([^`]+)`\s*$",
    re.MULTILINE,
)
HTML_DEFINE = re.compile(
    r"<!--\s*DEFINE:([A-Za-z0-9._-]+)\s*-->\s*(.*?)\s*<!--\s*/DEFINE\s*-->",
    re.DOTALL,
)
SRC_LINE = re.compile(
    r"^(?P<file>[^:\n]+):(?P<line>\d+)\s*$",
)
OUTPUT_PREFIXES = ("08-", "09-", "10-")
NUMBERED_FILE = re.compile(r"^\d{2}-.+\.(md|json|schema\.json)$", re.I)

# Catalog-attested Prompt One numbered names (not an exhaustive 60+ listing).
CATALOG_NUMBERED = [
    "00-CURRENT-STATE-INVENTORY.md",
    "01-BLOCKER-REPRODUCTION.md",
    "02-BLOCKER-ROOT-CAUSE.md",
    "03-PLUGIN-LIFECYCLE-MAP.md",
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    "05-ECO-frontier-orchestration.md",
    "05-ECO-marketplace-teardown.md",
    "05-ECO-plugin-specs.md",
    "05-ECO-workflow-sources.md",
    "06-PROGRAM-B-SCOPE-DOSSIER.json",
    "06-PROGRAM-B-SCOPE-DOSSIER.md",
    "07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.md",
    "08-WORKFLOW-ARCHAEOLOGY-AND-SOURCE-CATALOG.md",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-PROVENANCE-AND-LICENSE-GRAPH.json",
    "09-RECONCILED-BACKLOG.json",
    "09-RECONCILED-BACKLOG.md",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "09-WORKFLOW-BLUEPRINT-LIBRARY.md",
    "10-WORKFLOW-FORGE-SPEC.md",
    "10-WORKFLOW-FUSION-AND-CERTIFICATION-MAPS.json",
    "10-WORKFLOW-FUSION-AND-CERTIFICATION-PLAN.md",
    "10-WORKFLOW-MERGE-AND-COMPOSITION-MAPS.json",
    "11-CAPABILITY-PRESERVATION-GRAPH.json",
    "11-COUNCIL-OPTION-CARDS.md",
    "11-COUNCIL-SPECIFICATION.md",
    "11-COUNCIL-SPECIFICATION.schema.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.md",
    "12-COUNCIL-TEST-MATRIX.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "14-NO-REGRESSION-CONTRACT.md",
    "14-OWNER-DECISION-PACKET.md",
    "15-IMPLEMENTATION-PRECONDITIONS.md",
    "15-OWNER-DECISION-RECEIPT.json",
    "15-PROMPT-TWO-SPEC.md",
    "16-GRILL-QUEUE.md",
    "17-DECISION-LOG.md",
    "18-OPEN-UNKNOWNS-AND-PROBES.md",
    "19-SUBSTANCE-AUDIT-BLUEPRINTS.md",
    "24-REPO-RECONCILE.md",
    "31-LANE-foundry.md",
    "32-OWNER-DECISIONS.md",
    "33-INTEGRATION.md",
    "_USER-PROMPTS.md",
]

LIVE_ROOT_CANDIDATES = [
    Path.home() / ".claude" / "harness-restore-20260806",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/opt/p2/harness-restore-20260806"),
    REPO / "harness-restore-20260806",
    REPO / "command-center" / "sources" / "harness-restore-20260806",
]


def read_lines(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    return raw.replace("\r\n", "\n").split("\n")


def line_at(path: Path, n: int) -> str | None:
    if n < 1:
        return None
    lines = read_lines(path)
    # trailing split may add an empty last element; tolerate files without final NL
    if n > len(lines):
        return None
    return lines[n - 1]


def parse_src(src: str) -> tuple[str, int] | None:
    if not isinstance(src, str):
        return None
    m = SRC_LINE.match(src.strip().replace("\\", "/"))
    if not m:
        return None
    return m.group("file").split("/")[-1], int(m.group("line"))


def verify_anchor(
    root: Path,
    src: str,
    claimed: str,
    mode: str = "content",
) -> dict:
    """Dereference src. mode=content compares line text; exists-only does not."""
    parsed = parse_src(src)
    out = {
        "src": src,
        "claimed": claimed,
        "mode": mode,
        "ok": False,
        "reason": "unparsed",
        "file_exists": False,
        "line_content": None,
    }
    if parsed is None:
        out["reason"] = "src-unparsed"
        return out
    filename, lineno = parsed
    path = root / filename
    out["file"] = filename
    out["line"] = lineno
    out["file_exists"] = path.is_file()
    if mode == "exists-only":
        out["ok"] = bool(out["file_exists"])
        out["reason"] = "exists-only"
        return out
    if not path.is_file():
        out["reason"] = "file-missing"
        return out
    content = line_at(path, lineno)
    out["line_content"] = content
    if content is None:
        out["reason"] = "line-out-of-range"
        return out
    token = str(claimed or "")
    if token and token in content:
        out["ok"] = True
        out["reason"] = "line-contains-claimed"
        return out
    out["reason"] = "line-does-not-contain-claimed"
    return out


def extract_definitions(text: str, filename: str) -> list[dict]:
    """Workflow-shaped DEFINITIONS only. Backtick mentions are not definitions."""
    found: list[dict] = []
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines, 1):
        m = DEFINE_HEADING.match(line)
        if not m:
            continue
        mech_id = m.group(2).strip()
        body_parts: list[str] = []
        for later in lines[i:]:
            if later.startswith("#"):
                break
            if later.strip() == "" and body_parts:
                break
            if later.strip():
                body_parts.append(later.strip())
        body = " ".join(body_parts)
        found.append(
            {
                "id": mech_id,
                "kind": "definition",
                "file": filename,
                "line": i,
                "anchor": f"{filename}:{i}",
                "snippet": line,
                "body": body,
            }
        )
    for m in HTML_DEFINE.finditer(text.replace("\r\n", "\n")):
        mech_id = m.group(1).strip()
        prefix = text.replace("\r\n", "\n")[: m.start()]
        line = prefix.count("\n") + 1
        found.append(
            {
                "id": mech_id,
                "kind": "definition",
                "file": filename,
                "line": line,
                "anchor": f"{filename}:{line}",
                "snippet": m.group(0).splitlines()[0][:200],
                "body": m.group(2).strip(),
            }
        )
    return found


def extract_mentions(text: str, filename: str, defined_ids: set[str]) -> list[dict]:
    mentions = []
    for i, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        if DEFINE_HEADING.match(line):
            continue
        for tok in re.findall(r"`([A-Za-z0-9._-]+)`", line):
            if tok in defined_ids and DEFINE_HEADING.match(line):
                continue
            mentions.append(
                {
                    "id": tok,
                    "kind": "mention",
                    "file": filename,
                    "line": i,
                    "anchor": f"{filename}:{i}",
                    "snippet": line[:240],
                }
            )
    return mentions


def naive_backtick_as_definition(text: str, filename: str) -> list[dict]:
    """Mutant extractor: every backtick token is a definition (use-vs-mention fail)."""
    found = []
    for i, line in enumerate(text.replace("\r\n", "\n").split("\n"), 1):
        for tok in re.findall(r"`([A-Za-z0-9._-]+)`", line):
            found.append(
                {
                    "id": tok,
                    "kind": "definition",
                    "file": filename,
                    "line": i,
                    "anchor": f"{filename}:{i}",
                    "snippet": line[:240],
                    "body": "",
                }
            )
    return found


def iter_numbered_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.iterdir()):
        if p.is_file() and (NUMBERED_FILE.match(p.name) or p.name.startswith("_USER")):
            out.append(p)
    return out


def is_output_file(name: str) -> bool:
    return name.startswith(OUTPUT_PREFIXES)


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def walk_records(doc, source_name: str) -> list[dict]:
    rows: list[dict] = []

    def consider(obj, loc: str) -> None:
        if not isinstance(obj, dict):
            return
        rid = obj.get("id") or obj.get("name")
        mechs = obj.get("mechanisms")
        prov = obj.get("provenance") if isinstance(obj.get("provenance"), dict) else {}
        src = (
            (prov.get("src") if isinstance(prov, dict) else None)
            or obj.get("src")
            or obj.get("prov")
        )
        claimed = (
            (prov.get("prov") if isinstance(prov, dict) else None)
            or (mechs[0] if isinstance(mechs, list) and mechs else None)
            or obj.get("prov")
        )
        if rid or mechs or src:
            rows.append(
                {
                    "record_id": rid,
                    "source_file": source_name,
                    "mechanisms": list(mechs) if isinstance(mechs, list) else [],
                    "src": src,
                    "claimed": claimed,
                    "loc": loc,
                }
            )

    if isinstance(doc, list):
        for i, item in enumerate(doc):
            consider(item, f"[{i}]")
        return rows
    if not isinstance(doc, dict):
        return rows
    for key, val in doc.items():
        if isinstance(val, list):
            for i, item in enumerate(val):
                consider(item, f"{key}[{i}]")
        elif isinstance(val, dict) and (
            val.get("mechanisms") or val.get("provenance") or val.get("src")
        ):
            consider(val, key)
    if not rows:
        consider(doc, "$")
    return rows


def output_inventory(root: Path) -> tuple[list[dict], set[str]]:
    records: list[dict] = []
    ids: set[str] = set()
    for path in iter_numbered_files(root):
        if not is_output_file(path.name):
            continue
        if path.suffix.lower() != ".json":
            continue
        doc = load_json(path)
        for rec in walk_records(doc, path.name):
            records.append(rec)
            if rec.get("record_id"):
                ids.add(str(rec["record_id"]))
            for m in rec.get("mechanisms") or []:
                ids.add(str(m))
    return records, ids


def sweep_root(root: Path, *, naive: bool = False) -> dict:
    files = iter_numbered_files(root)
    extracted: list[dict] = []
    mentions: list[dict] = []
    read: list[dict] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        read.append(
            {
                "file": path.name,
                "bytes": len(text.encode("utf-8")),
                "output_side": is_output_file(path.name),
            }
        )
        if naive:
            defs = naive_backtick_as_definition(text, path.name)
        else:
            defs = extract_definitions(text, path.name)
        extracted.extend(defs)
        def_ids = {d["id"] for d in defs}
        mentions.extend(extract_mentions(text, path.name, def_ids))

    records, reached = output_inventory(root)
    fabricated = []
    confirmed_anchors = []
    for rec in records:
        src = rec.get("src")
        claimed = rec.get("claimed") or ""
        if not src:
            fabricated.append(
                {
                    "kind": "fabricated-anchor",
                    "record_id": rec.get("record_id"),
                    "source_file": rec.get("source_file"),
                    "src": None,
                    "claimed": claimed,
                    "reason": "missing-src",
                    "line_content": None,
                }
            )
            continue
        verdict = verify_anchor(root, str(src), str(claimed), mode="content")
        row = {
            "kind": "fabricated-anchor" if not verdict["ok"] else "confirmed-anchor",
            "record_id": rec.get("record_id"),
            "source_file": rec.get("source_file"),
            "src": src,
            "claimed": claimed,
            "reason": verdict["reason"],
            "line_content": verdict.get("line_content"),
            "file_exists": verdict.get("file_exists"),
        }
        if verdict["ok"]:
            confirmed_anchors.append(row)
        else:
            fabricated.append(row)

    defined_not_output = []
    for d in extracted:
        if is_output_file(d["file"]):
            continue
        if d["id"] in reached:
            continue
        defined_not_output.append(
            {
                "kind": "dropped-mechanism",
                "id": d["id"],
                "defined_at": {
                    "file": d["file"],
                    "line": d["line"],
                    "anchor": d["anchor"],
                    "snippet": d["snippet"],
                },
                "absent_from": ["08", "09", "10"],
            }
        )

    mention_only = []
    defined_ids = {d["id"] for d in extracted if not is_output_file(d["file"])}
    for m in mentions:
        if m["id"] in defined_ids:
            continue
        if m["id"] in reached:
            continue
        mention_only.append(m)

    return {
        "root": str(root),
        "files_read": read,
        "extracted_constructs": extracted,
        "mentions": mentions,
        "mention_only_not_defined": mention_only,
        "output_records": records,
        "reached_ids": sorted(reached),
        "dropped_mechanisms": defined_not_output,
        "fabricated_anchors": fabricated,
        "confirmed_anchors": confirmed_anchors,
    }


def live_roots() -> list[Path]:
    env = os.environ.get("WFA0019_CORPUS_ROOT")
    found: list[Path] = []
    if env:
        p = Path(env)
        if p.is_dir():
            found.append(p)
    for c in LIVE_ROOT_CANDIDATES:
        if c.is_dir() and c not in found:
            found.append(c)
    return found


def recall_limit(live: list[Path], live_sweep: dict | None) -> dict:
    live_read = []
    if live_sweep:
        live_read = [r["file"] for r in live_sweep.get("files_read") or []]
    unread = []
    for name in CATALOG_NUMBERED:
        if name not in live_read:
            unread.append(name)
    return {
        "implied_exhaustiveness": False,
        "catalog_named_count": len(CATALOG_NUMBERED),
        "live_roots_present": [str(p) for p in live],
        "live_artifacts_read": live_read,
        "live_artifacts_unread": unread,
        "unread_reason": (
            "live harness-restore-20260806 numbered tree is absent on this Linux "
            "worktree; names below are catalog-attested, not a claim that the "
            "host tree contained only these files"
            if not live
            else "catalog-attested names not present among files actually opened"
        ),
        "method_limit": (
            "definitions are DEFINE headings and HTML DEFINE comments only; a "
            "backtick mention is not a definition. Live files without that "
            "syntax contribute zero definitions and are reported, not treated "
            "as empty archaeology."
        ),
    }


def run_both_sweeps(*, naive: bool = False) -> dict:
    fixture = sweep_root(FIXTURE_CORPUS, naive=naive)
    live = live_roots()
    live_sweep = sweep_root(live[0], naive=naive) if live else None
    return {
        "fixture": fixture,
        "live_roots": [str(p) for p in live],
        "live": live_sweep,
        "recall_limit": recall_limit(live, live_sweep),
    }
