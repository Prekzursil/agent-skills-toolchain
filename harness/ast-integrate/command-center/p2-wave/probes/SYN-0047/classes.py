"""Extract the spec's seeded failure classes for SYN-0047.

Cited range is _USER-PROMPTS.md:11298-11347. That file is not on this worktree.
SYN-0047's title requires 48 classes; ARC-0005 reconstructed 11301-11347 (47).
Inclusive 11300-11347 is 48 lines. Lines 11298-11299 are treated as unread
preamble (no per-line gloss). Extraction count is asserted, not eyeballed.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PROMPT_CANDIDATES = (
    REPO / "_USER-PROMPTS.md",
    REPO / "command-center/_USER-PROMPTS.md",
    REPO / "docs/_USER-PROMPTS.md",
)
CITED_RANGE = (11298, 11347)
CLASS_LINES = tuple(range(11300, 11348))  # 48 inclusive
EXPECTED_COUNT = 48

# Reconstruct 11301-11347 from ARC-0005 (catalog glosses). 11300 has no gloss.
_NAMED = {
    11301: "dual-writable config trees (live tree and repo tree both treated as source)",
    11302: "strict parser rejects unknown fields",
    11303: "plugin appears installed but hooks are unloaded",
    11304: "bare .sh invocation on Windows",
    11305: "repository copy differs from live deployed copy",
    11306: "stale cache masks a fixed package",
    11307: "package accidentally includes .git or huge unrelated files",
    11308: "path-casing mismatch across filesystems",
    11309: "PowerShell/Git Bash path rewriting",
    11310: "case-insensitive parser collision",
    11311: "command-line length overflow",
    11312: "exit-zero with missing artifact",
    11313: "partial artifact without sentinel",
    11314: "two completion predicates disagree",
    11315: "stall detection from mtimes alone is impossible / orchestrator death",
    11316: "long-path / mtime stall coupling",
    11317: "one hung unit blocks a large batch",
    11318: "429 arrival-rate storm / self-throttling",
    11319: "remote harvest silently does nothing",
    11320: "permission-boundary / colliding catalog merge",
    11321: "worktree points to the wrong repository",
    11322: "stale branch would revert newer work",
    11323: "false-positive prose and fixture detectors",
    11324: "detector silent in both broken and fixed states",
    11325: "mutation survives the test suite",
    11326: "eager per-session MCP process multiplication",
    11327: "commit exhaustion freezes process creation",
    11328: "kill-based memory guard terminates a live shared service",
    11329: "skill exists in repo but not in live skill directory",
    11330: "router fails to select an installed skill",
    11331: "ignoring an existing superior workflow",
    11332: "workflow fusion loses a source capability",
    11333: "fused workflow performs worse than every source",
    11334: "fusion accepted because it has more stages (catalog gloss thin)",
    11335: "council/self-improvement loop class (catalog gloss thin)",
    11336: "trigger mandated, threshold unspecified",
    11337: "council deliberation under-specified stop (catalog gloss thin)",
    11338: "council stops before minimum deliberation conditions",
    11339: "100-idea brainstorm satisfies the count with trivial wording variants",
    11340: "dissent/minority report is dropped",
    11341: "minority report unattributed in final synthesis",
    11342: "corruption threshold unspecified",
    11343: "nested councils disagree on completion",
    11344: "transcript injects instructions into later stages",
    11345: "credentials or decrypted secrets enter an artifact bundle",
    11346: "marketplace package has malicious or excessive permissions",
    11347: "rollback destroys user-owned files/commands/settings",
}

_GLOSS = {
    11300: "ABSENT",
    11301: "RECONSTRUCTED-LINE",
    11334: "PARTIAL-GLOSS",
    11335: "PARTIAL-GLOSS",
    11337: "PARTIAL-GLOSS",
}
for _line in range(11302, 11348):
    _GLOSS.setdefault(_line, "CATALOG")


def _parse_prompt_lines(text: str) -> list[dict] | None:
    lines = text.splitlines()
    if len(lines) < CITED_RANGE[1]:
        return None
    chunk = lines[CITED_RANGE[0] - 1 : CITED_RANGE[1]]
    items: list[dict] = []
    for offset, raw in enumerate(chunk):
        spec = CITED_RANGE[0] + offset
        stripped = raw.strip()
        if spec < CLASS_LINES[0]:
            continue
        if spec > CLASS_LINES[-1]:
            break
        name = stripped.lstrip("-*0123456789.) ").strip()
        if not name:
            name = f"unnamed-spec-class-{spec}"
        items.append(
            {
                "id": f"FC-{spec}",
                "spec_line": spec,
                "name": name,
                "gloss_status": "SOURCE-FILE",
                "needles": _needles(f"FC-{spec}", name, spec),
            }
        )
    return items if len(items) == EXPECTED_COUNT else None


def _needles(cid: str, name: str, spec: int) -> list[str]:
    out = [cid.lower(), cid.replace("FC-", "fc-"), f":{spec}", f"spec:{spec}", name.lower()]
    if len(name) > 24:
        out.append(name.lower()[:40])
    return list(dict.fromkeys(out))


def reconstructed_classes() -> list[dict]:
    rows: list[dict] = []
    for spec in CLASS_LINES:
        name = _NAMED.get(spec, f"unnamed-spec-class-{spec}")
        cid = f"FC-{spec}"
        rows.append(
            {
                "id": cid,
                "spec_line": spec,
                "name": name,
                "gloss_status": _GLOSS.get(spec, "ABSENT"),
                "needles": _needles(cid, name, spec),
            }
        )
    return rows


def extract_classes(repo: Path | None = None) -> dict:
    repo = repo or REPO
    source_status = "ABSENT"
    source_path = None
    parsed = None
    for cand in (
        repo / "_USER-PROMPTS.md",
        repo / "command-center/_USER-PROMPTS.md",
        repo / "docs/_USER-PROMPTS.md",
    ):
        if cand.is_file() and cand.stat().st_size > 0:
            source_path = str(cand.relative_to(repo)).replace("\\", "/")
            parsed = _parse_prompt_lines(cand.read_text(encoding="utf-8", errors="replace"))
            if parsed:
                source_status = "PRESENT"
                classes = parsed
                break
            source_status = "PRESENT-UNPARSEABLE"
    else:
        classes = reconstructed_classes()

    if len(classes) != EXPECTED_COUNT:
        raise AssertionError(
            f"extraction count {len(classes)} != {EXPECTED_COUNT} (must be asserted)"
        )
    ids = [c["id"] for c in classes]
    if len(set(ids)) != EXPECTED_COUNT:
        raise AssertionError(f"duplicate class ids: {ids}")
    specs = [c["spec_line"] for c in classes]
    if specs != list(CLASS_LINES):
        raise AssertionError(f"spec lines {specs[0]}..{specs[-1]} n={len(specs)}")
    return {
        "cited_range": {"start": CITED_RANGE[0], "end": CITED_RANGE[1]},
        "class_line_range": {"start": CLASS_LINES[0], "end": CLASS_LINES[-1]},
        "expected_count": EXPECTED_COUNT,
        "extracted_count": len(classes),
        "count_asserted": True,
        "source_status": source_status,
        "source_path": source_path,
        "reconstruction": (
            "Inclusive 11300-11347 = 48 (unit title). ARC-0005 reconstructed "
            "11301-11347. 11298-11299 treated as unread preamble. 11300 has no "
            "catalog gloss on this worktree."
        ),
        "catalog_title_count": 48,
        "arc0005_count": 47,
        "classes": classes,
    }
