"""Slash-command markdown → WorkflowIR adapter (WFA-0048).

Classifies each command as ALIAS (thin skill invoke, no extra stages) or
OWN-PROCEDURE (its own ordered stages). Aliases collapse to the target
skill id with an alias edge. Description frontmatter is mention, not a
stage list (use-versus-mention).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALIAS = "ALIAS"
OWN_PROCEDURE = "OWN-PROCEDURE"

SKILL_INVOKE_RE = re.compile(
    r"(?i)\b(?:use|run|invoke|launch|call|wraps?|delegates?\s+to)\s+"
    r"(?:the\s+)?[`'\"]?([a-z0-9._/-]+)[`'\"]?\s+skill\b"
)
SKILL_FIELD_RE = re.compile(r"(?i)\bskill:\s*([a-z0-9._/-]+)")
NUM_STAGE_RE = re.compile(r"^(\d+)\.\s+(.+)$")
HEAD_STAGE_RE = re.compile(
    r"^#{1,3}\s+((?:Step|Stage|Phase)\b.*)$", re.IGNORECASE
)
GATE_RE = re.compile(r"^(?:Gate|Barrier)\s*:\s+(.+)$", re.IGNORECASE)
INVOKE_STRIP_RE = re.compile(
    r"(?i)\b(?:use|run|invoke|launch|call|wraps?|delegates?\s+to)\s+"
    r"(?:the\s+)?[`'\"]?[a-z0-9._/-]+[`'\"]?\s+skill\b"
    r"|\bskill:\s*[a-z0-9._/-]+"
    r"|\$ARGUMENTS"
)


@dataclass
class ParsedCommand:
    path: str
    command_id: str
    frontmatter: dict[str, str]
    body: str
    body_start_line: int
    raw: str


@dataclass
class Stage:
    id: str
    title: str
    body: str
    source_anchor: dict[str, Any]
    kind: str = "stage"


@dataclass
class Classification:
    command_id: str
    path: str
    verdict: str
    skill_id: str | None
    stages: list[Stage]
    gates: list[Stage]
    deciding_quote: str
    deciding_line: int
    lossy_fields: list[dict[str, str]] = field(default_factory=list)


def command_id_from_path(path: Path) -> str:
    stem = path.stem
    if stem.startswith("cmd-"):
        return stem
    return f"cmd-{stem}"


def skill_id(name: str) -> str:
    name = name.strip().strip("`\"'").replace("\\", "/")
    if name.startswith("skill:"):
        return name
    if name.startswith("skill/"):
        return "skill:" + name.split("/", 1)[1]
    return "skill:" + name


def parse_markdown(text: str, path: str) -> ParsedCommand:
    lines = text.splitlines()
    fm: dict[str, str] = {}
    body_start = 1
    body = text
    if lines and lines[0].strip() == "---":
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            for line in lines[1:end]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    fm[key.strip().lower()] = val.strip().strip('"').strip("'")
            body_start = end + 2
            body = "\n".join(lines[end + 1 :])
    return ParsedCommand(
        path=path,
        command_id=command_id_from_path(Path(path)),
        frontmatter=fm,
        body=body,
        body_start_line=body_start,
        raw=text,
    )


def parse_file(path: Path, repo: Path | None = None) -> ParsedCommand:
    rel = path.as_posix()
    if repo is not None:
        try:
            rel = path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            rel = path.as_posix()
    return parse_markdown(path.read_text(encoding="utf-8"), rel)


def is_invoke_only(text: str) -> bool:
    stripped = INVOKE_STRIP_RE.sub(" ", text)
    stripped = re.sub(r"[`'\"]", " ", stripped)
    stripped = re.sub(r"[^a-zA-Z0-9]+", " ", stripped)
    tokens = [t.lower() for t in stripped.split() if t]
    boilerplate = {
        "the",
        "a",
        "an",
        "with",
        "and",
        "to",
        "for",
        "this",
        "command",
        "thin",
        "alias",
        "wrapper",
        "arguments",
        "args",
        "only",
        "just",
        "simply",
    }
    remain = [t for t in tokens if t not in boilerplate]
    return len(remain) == 0


def resolve_skill(parsed: ParsedCommand) -> tuple[str | None, str | None, int]:
    for key in ("skill", "invoke-skill", "delegate-to", "alias-of"):
        if parsed.frontmatter.get(key):
            raw = parsed.frontmatter[key]
            # Frontmatter occupies lines 2.. before closing ---; quote the field.
            return skill_id(raw), f"{key}: {raw}", 2
    for i, line in enumerate(parsed.body.splitlines()):
        lineno = parsed.body_start_line + i
        m = SKILL_INVOKE_RE.search(line) or SKILL_FIELD_RE.search(line)
        if m:
            name = next(g for g in m.groups() if g)
            return skill_id(name), line.strip(), lineno
    return None, None, parsed.body_start_line


def extract_stages(parsed: ParsedCommand) -> tuple[list[Stage], list[Stage]]:
    """Body-only stage extraction. Frontmatter description is never a stage."""
    stages: list[Stage] = []
    gates: list[Stage] = []
    for i, line in enumerate(parsed.body.splitlines()):
        stripped = line.strip()
        lineno = parsed.body_start_line + i
        anchor = {
            "path": parsed.path,
            "line": lineno,
            "quote": stripped[:240],
        }
        num = NUM_STAGE_RE.match(stripped)
        if num:
            title = num.group(2).strip()
            stages.append(
                Stage(
                    id=f"{parsed.command_id}-s{num.group(1)}",
                    title=title,
                    body=title,
                    source_anchor=anchor,
                )
            )
            continue
        head = HEAD_STAGE_RE.match(stripped)
        if head:
            title = head.group(1).strip()
            stages.append(
                Stage(
                    id=f"{parsed.command_id}-h{len(stages)+1}",
                    title=title,
                    body=title,
                    source_anchor=anchor,
                    kind="heading-stage",
                )
            )
            continue
        gate = GATE_RE.match(stripped)
        if gate:
            title = gate.group(1).strip()
            gates.append(
                Stage(
                    id=f"{parsed.command_id}-g{len(gates)+1}",
                    title=title,
                    body=title,
                    source_anchor=anchor,
                    kind="gate",
                )
            )
    return stages, gates


def lossy_fields(parsed: ParsedCommand) -> list[dict[str, str]]:
    rows = []
    if "$ARGUMENTS" in parsed.body or "$ARGUMENTS" in parsed.raw:
        rows.append(
            {
                "field": "$ARGUMENTS",
                "reason": "Claude Code argument interpolation is host-specific; IR records the mention, not an evaluator.",
            }
        )
    if parsed.frontmatter.get("argument-hint") or parsed.frontmatter.get(
        "argument_hint"
    ):
        rows.append(
            {
                "field": "argument-hint",
                "reason": "Slash-command argument hint has no WorkflowIR counterpart; recorded as lossy.",
            }
        )
    if parsed.frontmatter.get("allowed-tools") or parsed.frontmatter.get(
        "allowed_tools"
    ):
        rows.append(
            {
                "field": "allowed-tools",
                "reason": "Host tool-name strings are noted, not executed; not an IR runtime policy engine.",
            }
        )
    return rows


def classify(parsed: ParsedCommand, detect_alias: bool = True) -> Classification:
    skill, skill_quote, skill_line = resolve_skill(parsed)
    stages, gates = extract_stages(parsed)
    real_stages = [s for s in stages if not is_invoke_only(s.body)]
    lossy = lossy_fields(parsed)

    if detect_alias and skill and not real_stages and not gates:
        quote = skill_quote or parsed.body.strip().splitlines()[0] if parsed.body.strip() else skill
        return Classification(
            command_id=parsed.command_id,
            path=parsed.path,
            verdict=ALIAS,
            skill_id=skill,
            stages=[],
            gates=[],
            deciding_quote=str(quote)[:240],
            deciding_line=skill_line,
            lossy_fields=lossy,
        )

    if not real_stages:
        # Unstructured body: one stage citing the first non-empty body line,
        # never the frontmatter description (use-versus-mention).
        for i, line in enumerate(parsed.body.splitlines()):
            if line.strip():
                real_stages = [
                    Stage(
                        id=f"{parsed.command_id}-s1",
                        title=line.strip()[:120],
                        body=line.strip(),
                        source_anchor={
                            "path": parsed.path,
                            "line": parsed.body_start_line + i,
                            "quote": line.strip()[:240],
                        },
                    )
                ]
                break

    if real_stages:
        first = real_stages[0]
        return Classification(
            command_id=parsed.command_id,
            path=parsed.path,
            verdict=OWN_PROCEDURE,
            skill_id=skill if not detect_alias else (skill if skill else None),
            stages=real_stages,
            gates=gates,
            deciding_quote=first.source_anchor["quote"],
            deciding_line=int(first.source_anchor["line"]),
            lossy_fields=lossy,
        )

    # Empty command: still OWN-PROCEDURE with no stages rather than inventing.
    return Classification(
        command_id=parsed.command_id,
        path=parsed.path,
        verdict=OWN_PROCEDURE,
        skill_id=skill,
        stages=[],
        gates=gates,
        deciding_quote="(empty body; no ordered procedure extracted)",
        deciding_line=parsed.body_start_line,
        lossy_fields=lossy,
    )


def to_ir(cls: Classification) -> dict[str, Any]:
    """WorkflowIR record. No runtime entrypoint. Every node has source_anchor."""
    if cls.verdict == ALIAS:
        return {
            "id": cls.command_id,
            "kind": "WorkflowIR",
            "classification": ALIAS,
            "alias_of": cls.skill_id,
            "stages": [],
            "gates": [],
            "source_anchor": {
                "path": cls.path,
                "line": cls.deciding_line,
                "quote": cls.deciding_quote,
            },
            "runtime_entrypoint": None,
        }
    stages = []
    for st in cls.stages:
        if not st.source_anchor or "line" not in st.source_anchor:
            raise ValueError(f"IR node without source_anchor: {st.id}")
        stages.append(
            {
                "id": st.id,
                "kind": "stage",
                "title": st.title,
                "body": st.body,
                "source_anchor": st.source_anchor,
            }
        )
    gates = []
    for g in cls.gates:
        gates.append(
            {
                "id": g.id,
                "kind": "gate",
                "title": g.title,
                "body": g.body,
                "source_anchor": g.source_anchor,
            }
        )
    return {
        "id": cls.command_id,
        "kind": "WorkflowIR",
        "classification": OWN_PROCEDURE,
        "alias_of": None,
        "stages": stages,
        "gates": gates,
        "source_anchor": {
            "path": cls.path,
            "line": cls.deciding_line,
            "quote": cls.deciding_quote,
        },
        "runtime_entrypoint": None,
    }


def classify_dir(
    root: Path, repo: Path | None = None, detect_alias: bool = True
) -> list[Classification]:
    files = sorted(p for p in root.glob("*.md") if p.is_file())
    return [classify(parse_file(p, repo=repo), detect_alias=detect_alias) for p in files]


def live_command_roots() -> list[dict[str, Any]]:
    home = Path.home()
    repo = Path(__file__).resolve().parents[4]
    candidates = [
        home / ".claude" / "commands",
        home / ".config" / "claude" / "commands",
        Path("/root/.claude/commands"),
        Path("/mnt/c/Users/Prekzursil/.claude/commands"),
        Path("C:/Users/Prekzursil/.claude/commands"),
        repo / "platform/routing/fixtures/home/.claude/commands",
        repo / "tools/editor/metaswarm/.claude/commands",
        repo / "tools/editor/metaswarm/commands",
    ]
    rows = []
    for p in candidates:
        rows.append(
            {
                "path": str(p),
                "exists": p.is_dir(),
                "md_count": len(list(p.glob("*.md"))) if p.is_dir() else 0,
            }
        )
    return rows
