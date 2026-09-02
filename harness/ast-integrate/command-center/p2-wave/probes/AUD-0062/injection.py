"""Turn-0 injection-set enumerator and tokenizer for AUD-0062.

Probe 1 tokenizes each injected item and sums. Probe 2 measures occupancy of
the packed session blob (a different instrument: one concatenated payload,
not a per-file sum). The catalog's control is that those two numbers must
agree within a stated tolerance; withholding a known injected file must
open a gap larger than that tolerance.

Skill payloads are the frontmatter description (what a session injects in
the skill inventory), not the full SKILL.md body. Rules without a `paths:`
key are always-on (full file). Rules with `paths:` are lazy and excluded.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
HOME = Path.home()
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from router.tokenizer import (  # noqa: E402
    TOKENIZER_ID,
    TOKENIZER_VERSION,
    char_quarter_estimate,
    count_tokens,
)

UNIT = "AUD-0062"
JOIN = "\n\n"
SKIP_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    "agent-transcripts",
    "chats",
    "projects",
    ".venv",
    "venv",
}
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
DESC_RE = re.compile(
    r"^description\s*:\s*(?:>-?\s*\n((?:[ \t]+.+\n?)+)|(.+))$",
    re.MULTILINE,
)
PATHS_RE = re.compile(r"^paths\s*:", re.MULTILINE)
NAME_RE = re.compile(r"^name\s*:\s*(.+)$", re.MULTILINE)


def ensure_control_fixtures() -> dict[str, Path]:
    """Deterministic planted rules: always-on (no frontmatter) vs lazy (paths)."""
    rules = HERE / "fixtures" / "rules"
    rules.mkdir(parents=True, exist_ok=True)
    always = rules / "always-on-control.md"
    lazy = rules / "lazy-control.md"
    always_body = "\n".join(
        f"Always-on injected rule paragraph {i:03d} with distinct tokens."
        for i in range(20)
    ) + "\n"
    lazy_body = (
        "---\n"
        "paths:\n"
        "  - \"**/*.py\"\n"
        "---\n"
        + "\n".join(
            f"Lazy path-scoped rule paragraph {i:03d} must not enter turn 0."
            for i in range(500)
        )
        + "\n"
    )
    always.write_text(always_body, encoding="utf-8", newline="\n")
    lazy.write_text(lazy_body, encoding="utf-8", newline="\n")
    tools = HERE / "fixtures" / "live-cursor-tools.json"
    if not tools.is_file():
        tools.write_text("{}\n", encoding="utf-8", newline="\n")
    return {"always_on": always, "lazy": lazy, "cursor_tools": tools}


def _skipped(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    return m.group(1), text[m.end() :]


def has_paths_key(frontmatter: str | None) -> bool:
    if not frontmatter:
        return False
    return bool(PATHS_RE.search(frontmatter))


def skill_description(frontmatter: str | None, fallback: str) -> str:
    if not frontmatter:
        return fallback.strip()[:2000]
    m = DESC_RE.search(frontmatter)
    if not m:
        name = NAME_RE.search(frontmatter)
        return (name.group(1).strip() if name else fallback.strip())[:2000]
    folded = m.group(1)
    if folded:
        lines = [ln.strip() for ln in folded.splitlines() if ln.strip()]
        return " ".join(lines)
    return (m.group(2) or "").strip().strip("\"'")


def relabel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        try:
            return "~/" + path.resolve().relative_to(HOME.resolve()).as_posix()
        except ValueError:
            return path.as_posix()


def _item(
    path: Path, klass: str, payload: str, *, injected: bool = True
) -> dict[str, Any]:
    tokens = count_tokens(payload) if injected else 0
    estimate = char_quarter_estimate(payload)
    return {
        "path": relabel(path),
        "class": klass,
        "injected": injected,
        "bytes": len(payload.encode("utf-8")),
        "tokens": tokens,
        "char_quarter_estimate": estimate,
        "tokenizer_ne_estimate": tokens != estimate,
        "payload_sha256_prefix": __import__("hashlib")
        .sha256(payload.encode("utf-8"))
        .hexdigest()[:16],
    }


def _iter_files(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file() or _skipped(p):
            continue
        if p.suffix.lower() in suffixes:
            out.append(p)
    return sorted(out)


def discover_named_docs() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    candidates = [
        (REPO / "CLAUDE.md", "claude_md"),
        (REPO / "AGENTS.md", "agents_md"),
        (HOME / "CLAUDE.md", "claude_md"),
        (HOME / "AGENTS.md", "agents_md"),
        (HOME / ".claude" / "CLAUDE.md", "claude_md"),
        (HOME / ".claude" / "AGENTS.md", "agents_md"),
    ]
    seen: set[str] = set()
    for path, klass in candidates:
        if not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        items.append(_item(path, klass, _read_text(path)))
    return items


def discover_unfrontmattered_rules() -> list[dict[str, Any]]:
    ensure_control_fixtures()
    roots = [
        HERE / "fixtures" / "rules",
        REPO / ".cursor" / "rules",
        HOME / ".cursor" / "rules",
        HOME / ".claude" / "rules",
        REPO / "rules",
    ]
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        for path in _iter_files(root, (".md", ".mdc")):
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            text = _read_text(path)
            fm, body = split_frontmatter(text)
            injected = not has_paths_key(fm)
            payload = text if injected else body
            items.append(_item(path, "unfrontmattered_rules", payload, injected=injected))
    return items


def discover_skill_descriptions() -> list[dict[str, Any]]:
    # Canonical repo skill root is .agents/skills/. skills/ is a compatibility
    # copy of the same documents; counting both would double the budget.
    roots = [
        HOME / ".cursor" / "skills-cursor",
        HOME / ".cursor" / "skills",
        HOME / ".claude" / "skills",
        REPO / ".cursor" / "skills",
        REPO / ".agents" / "skills",
    ]
    if not (REPO / ".agents" / "skills").is_dir():
        roots.append(REPO / "skills")
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("SKILL.md")):
            if _skipped(path):
                continue
            key = str(path.resolve())
            if key in seen:
                continue
            seen.add(key)
            text = _read_text(path)
            fm, body = split_frontmatter(text)
            payload = skill_description(fm, body)
            items.append(_item(path, "skill_descriptions", payload))
    return items


def discover_tool_schemas() -> list[dict[str, Any]]:
    ensure_control_fixtures()
    paths = [HERE / "fixtures" / "live-cursor-tools.json"]
    schema_root = REPO / "tools" / "plugin" / "schema"
    if schema_root.is_dir():
        paths.extend(sorted(schema_root.glob("*.json")))
    mcp = HOME / ".mcp.json"
    if mcp.is_file():
        paths.append(mcp)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        items.append(_item(path, "tool_schemas", _read_text(path)))
    return items


def injection_set() -> list[dict[str, Any]]:
    items = (
        discover_named_docs()
        + discover_unfrontmattered_rules()
        + discover_skill_descriptions()
        + discover_tool_schemas()
    )
    items.sort(key=lambda r: (-int(r["tokens"]), r["path"]))
    return items


def injected_only(items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rows = items if items is not None else injection_set()
    return [r for r in rows if r.get("injected") is True]


def payloads_for(items: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for row in items:
        path = row["path"]
        resolved = _resolve(path)
        text = _read_text(resolved)
        klass = row["class"]
        if klass == "skill_descriptions":
            fm, body = split_frontmatter(text)
            out.append(skill_description(fm, body))
        elif klass == "unfrontmattered_rules":
            fm, body = split_frontmatter(text)
            out.append(text if not has_paths_key(fm) else body)
        else:
            out.append(text)
    return out


def _resolve(label: str) -> Path:
    if label.startswith("~/"):
        return (HOME / label[2:]).resolve()
    p = REPO / label
    if p.is_file():
        return p
    return Path(label)


def file_token_sum(items: list[dict[str, Any]]) -> int:
    return int(sum(int(r["tokens"]) for r in items))


def session_occupancy_tokens(items: list[dict[str, Any]]) -> tuple[int, str]:
    """Different instrument: tokenize the packed session blob once."""
    blob = JOIN.join(payloads_for(items))
    return count_tokens(blob), blob


def tolerance_tokens(n_items: int, file_sum: int) -> int:
    """Joiner overhead plus 2% of the file sum, floor 32 tokens."""
    joiners = max(0, n_items - 1) * 2
    return max(32, joiners + int(0.02 * file_sum))


def dominant_item(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    inj = injected_only(items)
    return inj[0] if inj else None


def class_totals(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for row in injected_only(items):
        slot = totals.setdefault(
            row["class"], {"items": 0, "tokens": 0, "bytes": 0}
        )
        slot["items"] += 1
        slot["tokens"] += int(row["tokens"])
        slot["bytes"] += int(row["bytes"])
    return totals


def aud0058_present() -> bool:
    return (REPO / "command-center/audit/AUD-0058-skill-load-trigger-audit.json").is_file()


def control_paths() -> dict[str, str]:
    fx = ensure_control_fixtures()
    return {k: relabel(v) for k, v in fx.items()}


def snapshot() -> dict[str, Any]:
    items = injection_set()
    inj = injected_only(items)
    file_sum = file_token_sum(inj)
    occ, blob = session_occupancy_tokens(inj)
    gap = abs(file_sum - occ)
    tol = tolerance_tokens(len(inj), file_sum)
    dom = dominant_item(items)
    return {
        "unit_id": UNIT,
        "tokenizer_id": TOKENIZER_ID,
        "tokenizer_version": TOKENIZER_VERSION,
        "join": JOIN.encode("unicode_escape").decode("ascii"),
        "items": items,
        "injected_count": len(inj),
        "enumerated_count": len(items),
        "file_token_sum": file_sum,
        "session_occupancy_tokens": occ,
        "gap_tokens": gap,
        "tolerance_tokens": tol,
        "within_tolerance": gap <= tol,
        "qualifies_as_budget": gap <= tol and file_sum > 0,
        "dominant": (
            {k: dom[k] for k in ("path", "class", "tokens", "bytes")} if dom else None
        ),
        "class_totals": class_totals(items),
        "occupancy_bytes": len(blob.encode("utf-8")),
        "aud0058_artifact_present": aud0058_present(),
        "control_paths": control_paths(),
        "claude_md_present": any(r["class"] == "claude_md" for r in inj),
        "agents_md_present": any(r["class"] == "agents_md" for r in inj),
    }
