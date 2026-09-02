"""Load a sample of real SKILL.md files from this estate and split components."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

CURSOR_SKILLS = HERE / "fixtures" / "skills-cursor"
COUNCIL_REL = (
    "command-center/p2-wave/probes/ARC-0016/fixtures/"
    "hatch-run/typed/skills/skill.council/SKILL.md"
)

SAMPLE_IDS = (
    "create-skill",
    "create-hook",
    "review-security",
    "sdk",
    "share",
    "origin",
    "split-to-prs",
    "babysit",
    "create-rule",
    "statusline",
    "shell",
    "loop",
    "new-repo",
)

COMPONENTS = (
    "trigger_phrases",
    "negative_scope",
    "examples",
    "length_body",
    "irrelevant_meta",
)
CONTROL_COMPONENT = "irrelevant_meta"

NEG_RE = re.compile(
    r"\b(never |do not |don't |do not |must not |not the place |"
    r"is not the place |not a |use only when |use this skill only |"
    r"do not create |never create |without using this skill |"
    r"do not rewrite |do not inspect )\b",
    re.I,
)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    # Estate SKILL.md files may start with an HTML comment before YAML.
    stripped = re.sub(r"^\s*(<!--.*?-->\s*)+", "", text, count=1, flags=re.S)
    if not stripped.startswith("---"):
        return {}, text
    rest = stripped[3:]
    end = rest.find("\n---")
    if end < 0:
        return {}, text
    return _simple_yaml(rest[:end]), rest[end + 4 :]


def _simple_yaml(block: str) -> dict:
    out: dict = {}
    key = None
    mode = None
    acc: list[str] = []

    def flush() -> None:
        nonlocal key, mode, acc
        if key is None:
            return
        if mode == "fold":
            out[key] = " ".join(x for x in acc if x)
        elif mode == "list":
            out[key] = list(acc)
        key, mode, acc = None, None, []

    for line in block.splitlines():
        if key and mode == "fold":
            if line.startswith(" ") or line.strip() == "":
                acc.append(line.strip())
                continue
            flush()
        if key and mode == "list":
            s = line.strip()
            if s.startswith("- "):
                acc.append(s[2:].strip())
                continue
            flush()
        if not line.strip():
            continue
        if ":" in line and not line.startswith(" "):
            k, _, r = line.partition(":")
            k, r = k.strip(), r.strip()
            if r in {">-", ">", "|", "|-"}:
                key, mode, acc = k, "fold", []
            elif r == "":
                key, mode, acc = k, "list", []
            else:
                out[k] = r.strip('"').strip("'")
    flush()
    return out


def _negative_spans(text: str) -> str:
    parts: list[str] = []
    for chunk in re.split(r"(?<=[.!?\n])\s+", text or ""):
        c = chunk.strip().strip("-").strip()
        if c and NEG_RE.search(c):
            parts.append(c)
    return "\n".join(parts)


def split_components(fm: dict, body: str, raw: str, skill_id: str) -> dict[str, str]:
    triggers = str(fm.get("description") or "")
    fences = re.findall(r"```[\w+-]*\n(.*?)```", body, flags=re.S)
    examples = "\n".join(fences)
    body_wo = re.sub(r"```[\w+-]*\n.*?```", " ", body, flags=re.S)
    negative = "\n".join(
        p for p in (_negative_spans(triggers), _negative_spans(body_wo)) if p
    )
    meta_bits = [skill_id]
    for k in ("disable-model-invocation", "disabled-environments"):
        if k in fm:
            meta_bits.append(f"{k} {fm[k]}")
    comments = re.findall(r"<!--.*?-->", raw, flags=re.S)
    return {
        "trigger_phrases": triggers,
        "negative_scope": negative,
        "examples": examples,
        "length_body": body_wo,
        "irrelevant_meta": " ".join(meta_bits + comments),
    }


def _read_skill(path: Path, fallback_id: str, source: str) -> dict:
    raw = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)
    skill_id = str(fm.get("name") or fallback_id)
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    comps = split_components(fm, body, raw, skill_id)
    return {
        "id": skill_id,
        "path": str(path),
        "source": source,
        "sha256": sha,
        "bytes": len(raw.encode("utf-8")),
        "components": comps,
        "component_chars": {k: len(v) for k, v in comps.items()},
    }


def load_catalog() -> list[dict]:
    skills: list[dict] = []
    missing: list[str] = []
    for sid in SAMPLE_IDS:
        path = CURSOR_SKILLS / sid / "SKILL.md"
        if not path.is_file():
            missing.append(str(path))
            continue
        skills.append(_read_skill(path, sid, "cursor-builtin-live"))
    council = REPO / COUNCIL_REL
    if council.is_file():
        skills.append(_read_skill(council, "council", "estate-worktree"))
    else:
        missing.append(str(council))
    if len(skills) < 8:
        raise FileNotFoundError(
            "RES-0102 estate skill sample too small "
            f"n={len(skills)} missing={missing[:6]}"
        )
    ids = [s["id"] for s in skills]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate skill ids {ids}")
    return skills


def ablate(skills: list[dict], component: str | None) -> list[dict]:
    if component is None:
        return skills
    if component not in COMPONENTS:
        raise ValueError(component)
    out: list[dict] = []
    for s in skills:
        comps = dict(s["components"])
        comps[component] = ""
        cloned = dict(s)
        cloned["components"] = comps
        cloned["ablated"] = component
        out.append(cloned)
    return out
