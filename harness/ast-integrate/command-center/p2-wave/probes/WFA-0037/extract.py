#!/usr/bin/env python3
"""WFA-0037 role extractor.

Candidate-native roles (declared or implicit) are the source. Council
artifacts 11/12 are a cross-check: a role that only they define goes
into the council bucket, never onto a candidate. Implicit roles stay
IMPLICIT with the inference quoted. Role collapse is a property of
the extracted behaviour fingerprints, not a prose judgement.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE_CORPUS = HERE / "fixtures" / "corpus"
ENFORCEMENT_DIR = HERE / "fixtures" / "enforcement"

REGISTRY_NAMES = (
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
    "08-WORKFLOW-CANDIDATE-REGISTRY.json",
)
COUNCIL_SPEC_NAMES = (
    "11-COUNCIL-SPECIFICATION.md",
    "11-COUNCIL-SPECIFICATION.md",
)
COUNCIL_PRESET_NAMES = (
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)

LIVE_ROOTS = [
    Path.home() / ".claude" / "harness-restore-20260806",
    Path("/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/c/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/Users/Prekzursil/.claude/harness-restore-20260806"),
    Path("/opt/p2/harness-restore-20260806"),
    REPO / "harness-restore-20260806",
    REPO / "command-center" / "sources" / "harness-restore-20260806",
    REPO / "command-center" / "sources",
]

IMPLICIT_RE = re.compile(
    r"\b(?:the\s+)?(?P<role>reviewer|critic|judge|scribe|chair|"
    r"moderator|operator|agent|owner|voter|approver)\b"
    r".{0,80}\b(?P<act>votes?|speaks?|decides?|approves?|records?|vets?|vetoes?)\b",
    re.IGNORECASE | re.DOTALL,
)
ROLE_HEADING_RE = re.compile(
    r"^##\s+Role\s+`([^`]+)`\s*$",
    re.MULTILINE | re.IGNORECASE,
)
KV_RE = re.compile(r"^([a-z_]+)\s*:\s*(.+?)\s*$", re.IGNORECASE)
DENY_RE = re.compile(
    r"PermissionError|speaking_rights denied|vote_rights denied|"
    r"refuse|forbidden|raise Permission",
    re.IGNORECASE,
)

ATTRS = ("mandate", "tool_access", "speaking_rights", "vote_rights")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def first_existing(root: Path, names: tuple[str, ...]) -> Path | None:
    for name in names:
        path = root / name
        if path.is_file():
            return path
    return None


def live_roots() -> list[Path]:
    found: list[Path] = []
    env = os.environ.get("WFA0037_CORPUS_ROOT")
    if env:
        path = Path(env)
        if path.is_dir():
            found.append(path)
    for cand in LIVE_ROOTS:
        if cand.is_dir() and cand not in found:
            found.append(cand)
    return found


def candidates_from_doc(doc: Any) -> list[dict[str, Any]]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if isinstance(doc, dict):
        for key in ("candidates", "records", "items"):
            val = doc.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        if doc.get("id") or doc.get("name"):
            return [doc]
    return []


def as_bool(val: Any) -> bool | None:
    if val is True or val is False:
        return val
    if val is None:
        return None
    if isinstance(val, (int, float)) and val in (0, 1):
        return bool(val)
    text = str(val).strip().lower()
    if text in {"yes", "true", "allowed", "1"}:
        return True
    if text in {"no", "false", "denied", "none", "0"}:
        return False
    return None


def as_tools(val: Any) -> list[str] | None:
    if val is None:
        return None
    if isinstance(val, list):
        return [str(x) for x in val]
    text = str(val).strip()
    if not text or text.lower() in {"none", "null", "n/a"}:
        return []
    if "," in text:
        return [part.strip() for part in text.split(",") if part.strip()]
    return [text]


def norm_text(val: Any) -> str:
    if val is None:
        return ""
    return re.sub(r"\s+", " ", str(val).strip().lower())


def fingerprint(role: dict[str, Any]) -> str:
    tools = role.get("tool_access")
    if tools is None:
        tools_s = "NULL"
    else:
        tools_s = ",".join(sorted(str(t) for t in tools))
    speak = role.get("speaking_rights")
    vote = role.get("vote_rights")
    return "|".join(
        [
            norm_text(role.get("mandate")) or "NULL",
            tools_s,
            "NULL" if speak is None else ("1" if speak else "0"),
            "NULL" if vote is None else ("1" if vote else "0"),
        ]
    )


def parse_council_md(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    roles: list[dict[str, Any]] = []
    matches = list(ROLE_HEADING_RE.finditer(text))
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]
        row: dict[str, Any] = {
            "id": match.group(1).strip(),
            "source_file": path.name,
            "source_quote": match.group(0).strip(),
        }
        for line in body.split("\n"):
            kv = KV_RE.match(line.strip())
            if not kv:
                continue
            key = kv.group(1).strip().lower()
            val = kv.group(2).strip()
            if key == "mandate":
                row["mandate"] = val
            elif key == "tool_access":
                row["tool_access"] = as_tools(val)
            elif key == "speaking_rights":
                row["speaking_rights"] = as_bool(val)
            elif key == "vote_rights":
                row["vote_rights"] = as_bool(val)
            elif key == "veto_rights":
                row["veto_rights"] = as_bool(val)
        roles.append(row)
    return roles


def parse_council_json(path: Path) -> list[dict[str, Any]]:
    doc = load_json(path)
    rows: list[Any] = []
    if isinstance(doc, dict) and isinstance(doc.get("roles"), list):
        rows = doc["roles"]
    elif isinstance(doc, list):
        rows = doc
    out: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, str):
            out.append({"id": item, "source_file": path.name, "source_quote": item})
            continue
        if not isinstance(item, dict):
            continue
        rid = item.get("id") or item.get("name")
        if not rid:
            continue
        out.append(
            {
                "id": str(rid),
                "mandate": item.get("mandate"),
                "tool_access": as_tools(item.get("tool_access")),
                "speaking_rights": as_bool(item.get("speaking_rights")),
                "vote_rights": as_bool(item.get("vote_rights")),
                "veto_rights": as_bool(item.get("veto_rights")),
                "source_file": path.name,
                "source_quote": json.dumps(
                    {k: item.get(k) for k in ("id", "mandate") if k in item},
                    sort_keys=True,
                ),
            }
        )
    return out


def load_council(root: Path) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    md = first_existing(root, COUNCIL_SPEC_NAMES)
    js = first_existing(root, COUNCIL_PRESET_NAMES)
    rows: list[dict[str, Any]] = []
    if md:
        rows.extend(parse_council_md(md))
    if js:
        rows.extend(parse_council_json(js))
    for row in rows:
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        prev = by_id.get(rid)
        if prev is None:
            by_id[rid] = dict(row)
            by_id[rid]["sources"] = [row.get("source_file")]
        else:
            srcs = list(prev.get("sources") or [])
            if row.get("source_file") not in srcs:
                srcs.append(row.get("source_file"))
            prev["sources"] = srcs
            for key in ATTRS + ("veto_rights",):
                if prev.get(key) in (None, "", []) and row.get(key) not in (None, "", []):
                    prev[key] = row.get(key)
    return list(by_id.values())


def declared_roles(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    raw = candidate.get("roles")
    if raw is None:
        raw = candidate.get("participants") or candidate.get("seats")
    if not isinstance(raw, list) or not raw:
        return []
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str):
            out.append(
                {
                    "id": item,
                    "origin": "DECLARED",
                    "mandate": None,
                    "mandate_quote": None,
                    "tool_access": None,
                    "tool_access_quote": None,
                    "speaking_rights": None,
                    "speaking_rights_quote": None,
                    "vote_rights": None,
                    "vote_rights_quote": None,
                    "inference": None,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        rid = item.get("id") or item.get("name")
        if not rid:
            continue
        speak_src = (
            item.get("speaking_rights") if "speaking_rights" in item else item.get("speak")
        )
        vote_src = item.get("vote_rights") if "vote_rights" in item else item.get("vote")
        out.append(
            {
                "id": str(rid),
                "origin": "DECLARED",
                "mandate": item.get("mandate"),
                "mandate_quote": item.get("mandate_quote") or item.get("mandate"),
                "tool_access": as_tools(item.get("tool_access") or item.get("tools")),
                "tool_access_quote": item.get("tool_access_quote"),
                "speaking_rights": as_bool(speak_src),
                "speaking_rights_quote": item.get("speaking_rights_quote"),
                "vote_rights": as_bool(vote_src),
                "vote_rights_quote": item.get("vote_rights_quote"),
                "inference": None,
            }
        )
    return out


def implicit_roles(candidate: dict[str, Any], declared_ids: set[str]) -> list[dict[str, Any]]:
    blobs: list[tuple[str, str]] = []
    for key in ("does", "notes", "description", "body"):
        val = candidate.get(key)
        if isinstance(val, str) and val.strip():
            blobs.append((key, val))
    found: dict[str, dict[str, Any]] = {}
    for key, text in blobs:
        for match in IMPLICIT_RE.finditer(text):
            rid = match.group("role").strip().lower()
            if rid in declared_ids or rid in found:
                continue
            act = match.group("act").lower()
            snippet = re.sub(r"\s+", " ", match.group(0)).strip()
            speaking = act.startswith("speak") or act.startswith("record")
            voting = (
                act.startswith("vote") or act.startswith("approv") or act.startswith("veto")
            )
            found[rid] = {
                "id": rid,
                "origin": "IMPLICIT",
                "mandate": None,
                "mandate_quote": None,
                "tool_access": None,
                "tool_access_quote": None,
                "speaking_rights": True if speaking else None,
                "speaking_rights_quote": snippet if speaking else None,
                "vote_rights": True if voting else None,
                "vote_rights_quote": snippet if voting else None,
                "inference": (
                    f"field {key!r} describes participant {rid!r} performing {act!r}; "
                    f"no roles array names that participant. snippet={snippet!r}"
                ),
            }
    return list(found.values())


def index_enforcement(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    hits: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".py", ".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if not DENY_RE.search(text):
            continue
        rel = (
            str(path.relative_to(REPO)).replace("\\", "/")
            if REPO in path.parents or path == REPO
            else str(path)
        )
        hits.append({"path": rel, "text": text, "name": path.name.lower()})
    return hits


def role_is_constrained(text: str, name: str, role_id: str) -> bool:
    """True only when this file names the role as the constrained identity.

    A docstring mention of another participant must not count as enforcement.
    """
    rid = re.escape(role_id)
    named = re.search(
        rf"(?:['\"]{rid}['\"]|{rid}_gate\b|{rid}\.py\b)",
        text + " " + name,
        re.IGNORECASE,
    )
    return bool(named) and bool(DENY_RE.search(text))


def enforce_status(role_id: str, hits: list[dict[str, Any]]) -> dict[str, Any]:
    for hit in hits:
        if role_is_constrained(hit["text"], hit["name"], role_id):
            return {
                "enforcement": "ENFORCED",
                "enforcement_surface": hit["path"],
                "enforcement_note": f"constraint for role {role_id!r} located at {hit['path']}",
            }
    return {
        "enforcement": "DECLARED-ONLY",
        "enforcement_surface": None,
        "enforcement_note": f"no refuse/PermissionError surface constrains role {role_id!r}",
    }


def attach_enforcement(roles: list[dict[str, Any]], hits: list[dict[str, Any]]) -> None:
    for role in roles:
        role.update(enforce_status(str(role["id"]), hits))
        role["behavior_fingerprint"] = fingerprint(role)


def collapse_from_roles(roles: list[dict[str, Any]]) -> dict[str, Any]:
    fps = [r.get("behavior_fingerprint") or fingerprint(r) for r in roles]
    unique = sorted(set(fps))
    n = len(roles)
    return {
        "role_count": n,
        "distinct_fingerprints": len(unique),
        "fingerprints": fps,
        "collapse": n >= 2 and len(unique) == 1,
        "detectable_from_table": True,
        "rule": "collapse iff role_count>=2 and all behavior_fingerprint values are identical",
    }


def extract_candidate(
    candidate: dict[str, Any],
    *,
    hits: list[dict[str, Any]],
    mode: str = "honest",
    council_roles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    declared = declared_roles(candidate)
    decl_ids = {r["id"].lower() for r in declared}
    implicit = implicit_roles(candidate, decl_ids)
    if mode == "promote_implicit":
        for row in implicit:
            row["origin"] = "DECLARED"
            row["inference"] = None
    roles = list(declared) + list(implicit)
    if mode == "bleed_council":
        have = {r["id"].lower() for r in roles}
        for cr in council_roles or []:
            cid = str(cr.get("id") or "").lower()
            if not cid or cid in have:
                continue
            roles.append(
                {
                    "id": cid,
                    "origin": "DECLARED",
                    "mandate": cr.get("mandate"),
                    "mandate_quote": cr.get("source_quote"),
                    "tool_access": cr.get("tool_access"),
                    "tool_access_quote": None,
                    "speaking_rights": cr.get("speaking_rights"),
                    "speaking_rights_quote": None,
                    "vote_rights": cr.get("vote_rights"),
                    "vote_rights_quote": None,
                    "inference": None,
                }
            )
    attach_enforcement(roles, hits)
    if mode == "flatten_collapse":
        for i, role in enumerate(roles):
            role["behavior_fingerprint"] = f"unique:{role.get('id')}:{i}"
    collapse = collapse_from_roles(roles)
    if not roles:
        fill = "HONEST-NULL"
    elif all(r.get("origin") == "IMPLICIT" for r in roles):
        fill = "IMPLICIT"
    else:
        fill = "EVIDENCED"
    return {
        "candidate_id": str(candidate.get("id") or candidate.get("name") or ""),
        "family": candidate.get("family"),
        "name": candidate.get("name"),
        "fill": fill,
        "roles": roles,
        "collapse": collapse,
    }


def extract_root(
    root: Path,
    *,
    enforcement_root: Path | None = None,
    mode: str = "honest",
) -> dict[str, Any]:
    reg = first_existing(root, REGISTRY_NAMES)
    council = load_council(root)
    hits = index_enforcement(enforcement_root or ENFORCEMENT_DIR)
    per: list[dict[str, Any]] = []
    if reg:
        per = [
            extract_candidate(c, hits=hits, mode=mode, council_roles=council)
            for c in candidates_from_doc(load_json(reg))
        ]
    candidate_role_ids = {
        str(role["id"]).lower() for row in per for role in (row.get("roles") or [])
    }
    council_bucket = []
    for cr in council:
        cid = str(cr.get("id") or "").lower()
        if not cid:
            continue
        if cid in candidate_role_ids:
            continue
        council_bucket.append(
            {
                "id": cid,
                "bucket": "council",
                "reason": (
                    "defined in 11/12 and in no candidate native form; "
                    "council artifacts are a cross-check, not the source"
                ),
                "sources": cr.get("sources") or [cr.get("source_file")],
                "mandate": cr.get("mandate"),
            }
        )
    return {
        "root": str(root),
        "registry_path": None if reg is None else str(reg),
        "registry_present": reg is not None,
        "candidates": per,
        "council_bucket": council_bucket,
        "council_defined": [str(c.get("id")) for c in council],
        "mode": mode,
    }


def recall_limit(live: list[Path], live_extract: dict[str, Any] | None) -> dict[str, Any]:
    live_read: list[str] = []
    if live_extract and live_extract.get("registry_path"):
        live_read.append(Path(str(live_extract["registry_path"])).name)
    unread = [
        name
        for name in (
            "08-WORKFLOW-CANDIDATE-REGISTRY.json",
            "11-COUNCIL-SPECIFICATION.md",
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        )
        if name not in live_read
    ]
    return {
        "implied_exhaustiveness": False,
        "live_roots_present": [str(p) for p in live],
        "live_artifacts_read": live_read,
        "live_artifacts_unread": unread,
        "catalog_named": [
            REGISTRY_NAMES[0],
            COUNCIL_SPEC_NAMES[0],
            COUNCIL_PRESET_NAMES[0],
        ],
        "unread_reason": (
            "live harness-restore-20260806 tree is absent on this Linux worktree; "
            "fixture corpus proves the three named tests; 284-row fill is UNMEASURED, "
            "not empty-by-exhaustion"
            if not live
            else "catalog-named files not among files actually opened"
        ),
    }


def run_extract(*, mode: str = "honest", enforcement_root: Path | None = None) -> dict[str, Any]:
    fixture = extract_root(FIXTURE_CORPUS, enforcement_root=enforcement_root, mode=mode)
    live = live_roots()
    live_extract = (
        extract_root(live[0], enforcement_root=enforcement_root, mode=mode) if live else None
    )
    return {
        "fixture": fixture,
        "live_roots": [str(p) for p in live],
        "live": live_extract,
        "recall_limit": recall_limit(live, live_extract),
    }
