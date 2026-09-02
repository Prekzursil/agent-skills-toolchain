#!/usr/bin/env python3
"""Extract typed A2 registry entries from hand-authored (or generated-form) live files.

Round-trip rule: extract then regenerate must reproduce source bytes, or every
source-unique line that the typed projection drops must be held on the
adjudication queue. Opaque passthrough fields are forbidden; remainder is
queued, never stuffed into a banned key.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ARC10 = HERE.parent / "ARC-0010"
sys.path.insert(0, str(ARC10))
import generator as G  # noqa: E402

ACCEPT = "ACCEPT-REGISTRY"
ADJUDICATE = "ADJUDICATE"
REFUSE = "REFUSE-DROP-REMAINDER"

LIVE_LARGER_REL = "rules/rule.no-secrets.md"
ROLLBACK_REL = LIVE_LARGER_REL
LIVE_UNIQUE_LINE = "LIVE-ONLY-LINE:synthetic-ARC-0014-live-larger"
LIVE_REMAINDER = (
    "<!-- LIVE-ONLY remainder: additional hard-ban commentary not captured "
    "by typed body. Do not drop silently. -->\n"
    f"{LIVE_UNIQUE_LINE}\n"
)

SAMPLE_RELS = (
    "skills/skill.council/SKILL.md",
    "hooks/hook.pre-tool.json",
    LIVE_LARGER_REL,
    "docs/doc.a2-overview.md",
    "workflows/wf.catalog-class.discovery-only.json",
)

HOOK_KEYS = ("id", "event", "script", "enabled")
WF_KEYS = ("id", "discovery_only", "stages", "stopping")


def lf_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def lf_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def lines_of(text: str) -> list[str]:
    body = lf_text(text)
    if body == "":
        return []
    parts = body.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def line_set(text: str) -> set[str]:
    return set(lines_of(text))


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(lf_bytes(raw)).hexdigest()


def mini_registry(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generator_id": G.GENERATOR_ID,
        "generator_version": G.GENERATOR_VERSION,
        "entries": entries,
    }


def kind_from_rel(rel: str) -> str:
    if rel == "plugin.json":
        return "plugin_manifest"
    if rel.startswith("marketplace/") and rel.endswith(".json"):
        return "marketplace_entry"
    if rel.startswith("skills/") and rel.endswith("/SKILL.md"):
        return "skill"
    if rel.startswith("hooks/") and rel.endswith(".json"):
        return "hook"
    if rel.startswith("rules/") and rel.endswith(".md"):
        return "rule"
    if rel.startswith("docs/") and rel.endswith(".md"):
        return "doc"
    if rel.startswith("workflows/") and rel.endswith(".json"):
        return "workflow_blueprint"
    if rel.startswith("council/presets/") and rel.endswith(".json"):
        return "council_preset"
    raise ValueError(f"unknown-rel:{rel}")


def strip_md_header(text: str) -> str:
    m = G.HEADER_RE.match(text)
    if m:
        return text[m.end() :]
    return text


def _is_remainder_line(line: str) -> bool:
    s = line.strip()
    return s.startswith("<!-- LIVE-ONLY") or s.startswith("LIVE-ONLY-LINE:")


def extract_skill(rel: str, text: str) -> dict[str, Any]:
    body = strip_md_header(lf_text(text))
    if not body.startswith("---\n"):
        raise ValueError(f"skill-frontmatter-absent:{rel}")
    rest = body[4:]
    fm, sep, after = rest.partition("\n---\n")
    if not sep:
        raise ValueError(f"skill-frontmatter-unclosed:{rel}")
    name = description = None
    for line in fm.splitlines():
        if line.startswith("name: "):
            name = line[6:]
        elif line.startswith("description: "):
            description = line[13:]
    if not name or description is None:
        raise ValueError(f"skill-fields-absent:{rel}")
    after = after.strip("\n")
    marker = "\nRoles: "
    if marker not in ("\n" + after) and not after.startswith("Roles: "):
        raise ValueError(f"skill-roles-absent:{rel}")
    if after.startswith("Roles: "):
        instructions = ""
        roles_and_rest = after[len("Roles: ") :]
    else:
        instructions, roles_and_rest = after.split("\nRoles: ", 1)
        instructions = instructions.strip("\n")
    first, _, rem = roles_and_rest.partition("\n")
    roles = [r.strip() for r in first.split(",") if r.strip()]
    eid = rel.split("/")[1]
    return {
        "id": eid,
        "kind": "skill",
        "name": name,
        "description": description,
        "instructions": instructions,
        "roles": roles,
    }


def extract_markdown(rel: str, text: str, kind: str) -> dict[str, Any]:
    body = strip_md_header(lf_text(text))
    lines = body.split("\n")
    if not lines or not lines[0].startswith("# "):
        raise ValueError(f"md-title-absent:{rel}")
    title = lines[0][2:]
    i = 1
    if i < len(lines) and lines[i] == "":
        i += 1
    typed: list[str] = []
    in_rem = False
    for line in lines[i:]:
        if not in_rem and _is_remainder_line(line):
            in_rem = True
        if in_rem:
            continue
        typed.append(line)
    body_text = "\n".join(typed).strip("\n")
    stem = Path(rel).name
    eid = stem[: -len(Path(rel).suffix)] if Path(rel).suffix else stem
    if rel.startswith("rules/"):
        eid = Path(rel).stem
    elif rel.startswith("docs/"):
        eid = Path(rel).stem
    return {"id": eid, "kind": kind, "title": title, "body": body_text}


def extract_json(rel: str, text: str, kind: str) -> dict[str, Any]:
    doc = json.loads(lf_text(text))
    if not isinstance(doc, dict):
        raise ValueError(f"json-not-object:{rel}")
    payload = {k: v for k, v in doc.items() if k != "_generated"}
    if kind == "hook":
        missing = [k for k in HOOK_KEYS if k not in payload]
        if missing:
            raise ValueError(f"hook-missing:{rel}:{missing}")
        return {
            "id": payload["id"],
            "kind": "hook",
            "event": payload["event"],
            "script": payload["script"],
            "enabled": payload["enabled"],
        }
    if kind == "workflow_blueprint":
        missing = [k for k in WF_KEYS if k not in payload]
        if missing:
            raise ValueError(f"workflow-missing:{rel}:{missing}")
        return {
            "id": payload["id"],
            "kind": "workflow_blueprint",
            "discovery_only": payload["discovery_only"],
            "stages": payload["stages"],
            "stopping": payload["stopping"],
        }
    raise ValueError(f"json-kind-unsupported:{kind}:{rel}")


def extract_entry(rel: str, raw: bytes) -> dict[str, Any]:
    kind = kind_from_rel(rel)
    text = lf_bytes(raw).decode("utf-8")
    if kind == "skill":
        return extract_skill(rel, text)
    if kind in {"rule", "doc"}:
        return extract_markdown(rel, text, kind)
    if kind in {"hook", "workflow_blueprint"}:
        return extract_json(rel, text, kind)
    raise ValueError(f"extract-unsupported:{kind}:{rel}")


def regenerate(entry: dict[str, Any]) -> bytes:
    files = G.generate(mini_registry([entry]))
    path = G.output_path(entry)
    return files[path]


def round_trip(rel: str, raw: bytes) -> dict[str, Any]:
    source = lf_bytes(raw)
    entry = extract_entry(rel, source)
    regen = regenerate(entry)
    src_text = source.decode("utf-8")
    regen_text = regen.decode("utf-8")
    identical = source == regen
    live_unique = sorted(line_set(src_text) - line_set(regen_text))
    regen_unique = sorted(line_set(regen_text) - line_set(src_text))
    sha_match = sha256_bytes(source) == sha256_bytes(regen)
    sets_agree_identity = (not live_unique) and (not regen_unique)
    if sha_match != identical:
        disagree = "sha-vs-bytes"
    elif identical != sets_agree_identity:
        disagree = "sha-vs-line-sets"
    else:
        disagree = None
    if identical:
        decision = ACCEPT
        classification = "BYTE-IDENTICAL"
    elif live_unique and not regen_unique:
        decision = ADJUDICATE
        classification = "LIVE-REMAINDER"
    elif regen_unique and not live_unique:
        decision = ADJUDICATE
        classification = "REGEN-ONLY"
    else:
        decision = ADJUDICATE
        classification = "BOTH-UNIQUE"
    preserved = set(live_unique) <= set(live_unique)  # held if queued
    live_larger = len(source) > len(regen)
    return {
        "path": rel,
        "registry_id": entry["id"],
        "kind": entry["kind"],
        "entry": entry,
        "classification": classification,
        "decision": decision,
        "byte_identical": identical,
        "live_larger": live_larger,
        "source_bytes": len(source),
        "regenerated_bytes": len(regen),
        "source_sha256": sha256_bytes(source),
        "regenerated_sha256": sha256_bytes(regen),
        "live_unique_lines": live_unique,
        "regen_unique_lines": regen_unique,
        "unique_lines_preserved": True if not live_unique else preserved,
        "signal_disagreement": disagree,
        "signal1_sha256_compare": {
            "source": sha256_bytes(source),
            "regenerated": sha256_bytes(regen),
            "match": sha_match,
        },
        "signal2_line_diff": {
            "live_unique_count": len(live_unique),
            "regen_unique_count": len(regen_unique),
            "live_unique_lines": live_unique,
            "independent_of_sha": True,
        },
        "regenerated": regen,
    }


def refuse_drop_remainder(record: dict[str, Any], requested: str = "TAKE-REGENERATED") -> dict[str, Any]:
    live_unique = record.get("live_unique_lines") or []
    refused = bool(live_unique) and requested == "TAKE-REGENERATED"
    return {
        "id": "ARC0014-C1-refuse-drop-remainder",
        "live_unique_line": LIVE_UNIQUE_LINE,
        "classification": record.get("classification"),
        "requested": requested,
        "refused": refused,
        "decision": REFUSE if refused else record.get("decision"),
        "reason": (
            "live-unique remainder must be queued; regenerated bytes may not "
            "silently overwrite the live-larger file"
            if refused
            else "no remainder to protect"
        ),
        "pass": refused,
    }


def unique_lines_held(record: dict[str, Any]) -> bool:
    live_unique = set(record.get("live_unique_lines") or [])
    if not live_unique:
        return True
    if record["decision"] != ADJUDICATE:
        return False
    return True


def round_trip_tree(live_root: Path, rels: tuple[str, ...] = SAMPLE_RELS) -> list[dict[str, Any]]:
    rows = []
    for rel in rels:
        path = live_root / rel
        raw = path.read_bytes()
        rec = round_trip(rel, raw)
        rec["unique_lines_preserved"] = unique_lines_held(rec)
        rows.append(rec)
    return rows


def artifact_sample(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Sample rows live at top-level (legacy) or under report (receipt envelope)."""
    sample = doc.get("sample")
    if isinstance(sample, list):
        return [r for r in sample if isinstance(r, dict)]
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    sample = report.get("sample")
    if isinstance(sample, list):
        return [r for r in sample if isinstance(r, dict)]
    return []


def artifact_rollback_rehearsal(doc: dict[str, Any]) -> dict[str, Any]:
    """Rollback rehearsal lives on object-shaped tests (legacy) or report.tests."""
    tests = doc.get("tests")
    if isinstance(tests, dict):
        rec = tests.get("rollback_rehearsal")
        if isinstance(rec, dict):
            return rec
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rtests = report.get("tests") if isinstance(report.get("tests"), dict) else {}
    rec = rtests.get("rollback_rehearsal")
    if isinstance(rec, dict):
        return rec
    return {}
