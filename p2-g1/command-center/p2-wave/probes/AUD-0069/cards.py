"""Load option-card bodies from 07-OPTION-UNIVERSE (md or json) if present."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CANDIDATE_RELATIVE = (
    "07-OPTION-UNIVERSE.json",
    "07-OPTION-UNIVERSE.md",
    "command-center/07-OPTION-UNIVERSE.json",
    "command-center/07-OPTION-UNIVERSE.md",
    "docs/07-OPTION-UNIVERSE.json",
    "docs/07-OPTION-UNIVERSE.md",
    "corpus/07-OPTION-UNIVERSE.json",
    "corpus/07-OPTION-UNIVERSE.md",
    "artifacts/07-OPTION-UNIVERSE.json",
    "command-center/audit/07-OPTION-UNIVERSE.json",
    "command-center/p2-wave/fixtures/07-OPTION-UNIVERSE.json",
    # Derived extraction of the 283 option-universe records. Original
    # 07-OPTION-UNIVERSE.md is not mounted on this Linux worktree.
    "platform/corpus/CANONICAL-CLAIMS.json",
)
CANONICAL_CLAIMS_REL = "platform/corpus/CANONICAL-CLAIMS.json"

BODY_KEYS = (
    "body",
    "full_body",
    "mechanism",
    "mechanism_body",
    "description",
    "text",
    "content",
    "rationale",
    "detail",
    "details",
    "prompt",
)
ID_KEYS = ("id", "option_id", "card_id", "uid")
TITLE_KEYS = ("title", "name", "heading")
HEADING_RE = re.compile(
    r"^(#{1,4})\s+((?:[A-Z]{1,6}-?\d+[A-Z]?)|(?:M-\d+)|(?:MECH-\d+)|(?:O[A-Z]-?\d+))\s*[:.—-]?\s*(.*)$"
)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=True)
    return str(value).strip()


def _card_from_obj(obj: dict, source: str, index: int) -> dict | None:
    cid = ""
    for key in ID_KEYS:
        if obj.get(key):
            cid = str(obj[key]).strip()
            break
    title = ""
    for key in TITLE_KEYS:
        if obj.get(key):
            title = str(obj[key]).strip()
            break
    body_parts = [_as_text(obj.get(k)) for k in BODY_KEYS if obj.get(k)]
    body = "\n".join(p for p in body_parts if p).strip()
    if not cid and not title and not body:
        return None
    if not cid:
        cid = f"ANON-{index:04d}"
    if not body:
        # Title-only cards are the residual this unit exists to refuse.
        body = ""
    return {
        "id": cid,
        "title": title,
        "body": body,
        "source": source,
        "body_chars": len(body),
        "title_only": (not body) and bool(title or cid),
    }


def _walk_json(node: Any, source: str, out: list[dict], index: list[int]) -> None:
    if isinstance(node, dict):
        card = _card_from_obj(node, source, index[0])
        looks_card = any(k in node for k in ID_KEYS) and (
            any(k in node for k in BODY_KEYS) or any(k in node for k in TITLE_KEYS)
        )
        if looks_card and card is not None:
            index[0] += 1
            out.append(card)
            return
        for key in ("option_cards", "cards", "options", "universe", "items"):
            if key in node:
                _walk_json(node[key], source, out, index)
                return
        for value in node.values():
            _walk_json(value, source, out, index)
    elif isinstance(node, list):
        for item in node:
            _walk_json(item, source, out, index)


def parse_json_cards(path: Path, rel: str) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[dict] = []
    _walk_json(data, rel, out, [1])
    return out


def parse_canonical_claims_option_universe(path: Path, rel: str) -> list[dict]:
    """Load option-universe mechanism texts from CANONICAL-CLAIMS.json.

    The original 07-OPTION-UNIVERSE.md bodies are absent. This file keeps one
    canonical_mechanism per option-universe representative plus 283
    07-OPTION-UNIVERSE.md# member ids. Titles are not used as bodies.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    cards: list[dict] = []
    for claim in data.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        rep = claim.get("representative") or {}
        if not isinstance(rep, dict):
            continue
        if rep.get("record_class") != "option_universe":
            continue
        body = str(claim.get("canonical_mechanism") or "").strip()
        if body.endswith("\n-"):
            body = body[:-2].strip()
        if not body:
            continue
        cid = str(rep.get("local_id") or "").strip()
        if not cid:
            raw = str(rep.get("raw_id") or "")
            cid = raw.rsplit("#", 1)[-1] if "#" in raw else raw
        if not cid:
            continue
        cards.append(
            {
                "id": cid,
                "title": str(claim.get("title") or "").strip(),
                "body": body,
                "source": rel,
                "body_chars": len(body),
                "title_only": False,
                "raw_id": str(rep.get("raw_id") or ""),
                "derived": True,
            }
        )
    return cards


def parse_md_cards(path: Path, rel: str) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    cards: list[dict] = []
    current: dict | None = None
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current, body_lines
        if current is None:
            return
        body = "\n".join(body_lines).strip()
        current["body"] = body
        current["body_chars"] = len(body)
        current["title_only"] = not body
        cards.append(current)
        current = None
        body_lines = []

    for line in lines:
        m = HEADING_RE.match(line.strip())
        if m:
            flush()
            current = {
                "id": m.group(2).strip(),
                "title": (m.group(3) or "").strip(),
                "source": rel,
            }
            body_lines = []
            continue
        if current is not None:
            body_lines.append(line)
    flush()
    return cards


def candidate_hits(repo: Path | None = None) -> list[dict]:
    root = repo or REPO
    hits = []
    seen: set[str] = set()
    for rel in CANDIDATE_RELATIVE:
        path = root / rel
        rec = {
            "path": rel,
            "present": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        }
        hits.append(rec)
        if rec["present"]:
            seen.add(rel)
    extra_roots = [
        root,
        root / "command-center",
        root / "docs",
        root / "corpus",
        root / "artifacts",
        root / "command-center" / "audit",
        root / "command-center" / "p2-wave",
    ]
    for base in extra_roots:
        if not base.is_dir():
            continue
        try:
            paths = list(base.glob("*OPTION-UNIVERSE*"))
            paths += list(base.glob("07-OPTION-UNIVERSE.*"))
        except OSError:
            continue
        for path in paths:
            if not path.is_file():
                continue
            try:
                rel = path.resolve().relative_to(root).as_posix()
            except ValueError:
                continue
            if rel in seen:
                continue
            hits.append({"path": rel, "present": True, "bytes": path.stat().st_size})
            seen.add(rel)
    return hits


def load_live_cards(repo: Path | None = None) -> dict:
    root = repo or REPO
    hits = candidate_hits(root)
    cards: list[dict] = []
    sources_used: list[str] = []
    parse_errors: list[str] = []
    for hit in hits:
        if not hit["present"]:
            continue
        path = root / hit["path"]
        try:
            rel = str(hit["path"]).replace("\\", "/")
            if rel == CANONICAL_CLAIMS_REL:
                parsed = parse_canonical_claims_option_universe(path, rel)
            elif path.suffix.lower() == ".json":
                parsed = parse_json_cards(path, rel)
            else:
                parsed = parse_md_cards(path, rel)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            parse_errors.append(f"{hit['path']}: {type(exc).__name__}: {exc}")
            continue
        if parsed:
            cards.extend(parsed)
            sources_used.append(hit["path"])
    # Dedup by id, first source wins. Original 07-OPTION-UNIVERSE paths are
    # listed before CANONICAL-CLAIMS so a mounted original file wins.
    by_id: dict[str, dict] = {}
    for card in cards:
        by_id.setdefault(card["id"], card)
    unique = list(by_id.values())
    with_bodies = [c for c in unique if c["body"].strip()]
    derived = any(
        str(s).replace("\\", "/") == CANONICAL_CLAIMS_REL for s in sources_used
    )
    return {
        "contracted_cards": 283,
        "candidate_paths": hits,
        "sources_used": sources_used,
        "parse_errors": parse_errors,
        "cards_found": len(unique),
        "cards_with_bodies": len(with_bodies),
        "title_only": len(unique) - len(with_bodies),
        "cards": with_bodies,
        "all_cards": unique,
        "corpus_present": bool(with_bodies),
        "source_kind": (
            "derived-canonical-claims"
            if derived and not any("07-OPTION-UNIVERSE" in str(s) for s in sources_used)
            else ("original-option-universe" if with_bodies else "absent")
        ),
    }
