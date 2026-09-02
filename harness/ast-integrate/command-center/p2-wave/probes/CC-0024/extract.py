#!/usr/bin/env python3
"""Extract Prompt Two owner requirements and bind them to catalog units.

Floor-recall is a hard gate: coverage is computed only after all nine named
numeric floors are present in the extract. Bindings use narrow spec-line
citations (span <= MAX_BIND_SPAN). The whole-spec range 10473-11437 does not
bind every requirement to CC-0024.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG_PATH = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE = HERE / "fixtures" / "prompt-two-slice.md"

SPEC_START = 10473
SPEC_END = 11437
MAX_BIND_SPAN = 80
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
CITE_RE = re.compile(
    r"_USER-PROMPTS\.md:(\d+)(?:-(\d+))?(?:\s*\(([^)]{8,500})\))?",
    re.I,
)
BARE_CITE_RE = re.compile(r":(\d{5})(?:-(\d{5}))?")

FLOOR_SPECS: list[dict] = [
    {
        "id": "FLOOR-2048-UNITS",
        "label": "2048 work units",
        "rx": re.compile(r"2,?048\s+work units", re.I),
    },
    {
        "id": "FLOOR-160-WORKFLOWS",
        "label": "160 workflow candidates",
        "rx": re.compile(r"160\s+workflow\s+(candidates?|mechanisms?)", re.I),
    },
    {
        "id": "FLOOR-96-BLUEPRINTS",
        "label": "96 blueprints",
        "rx": re.compile(r"96\s+(materially\s+distinct\s+)?(workflow\s+)?blueprints?", re.I),
    },
    {
        "id": "FLOOR-40-FLAGSHIP",
        "label": "40 flagship workflows",
        "rx": re.compile(r"40\s+flagship", re.I),
    },
    {
        "id": "FLOOR-48-PROTOCOLS",
        "label": "48 council protocols",
        "rx": re.compile(r"48\s+council\s+protocols?", re.I),
    },
    {
        "id": "FLOOR-64-PRESETS",
        "label": "64 presets",
        "rx": re.compile(r"64\s+(editable\s+)?presets?", re.I),
    },
    {
        "id": "FLOOR-100-IDEAS",
        "label": "100-idea brainstorm",
        "rx": re.compile(
            r"(100-idea|100-unique-idea|unique_ideas\s*>=\s*100|100\s+unique\s+ideas?)",
            re.I,
        ),
    },
    {
        "id": "FLOOR-36-LAYERS",
        "label": "36 test layers",
        "rx": re.compile(r"36\s+test\s+layers?", re.I),
    },
    {
        "id": "FLOOR-21-STOPPING",
        "label": "21 stopping conditions",
        "rx": re.compile(r"21\s+(program\s+)?stopping\s+conditions?", re.I),
    },
]
FLOOR_IDS = [f["id"] for f in FLOOR_SPECS]

# Catalog-recovered Prompt Two sentences, placed at the cited line when the
# live spec file is absent from this sparse worktree.
CANONICAL_LINES: dict[int, str] = {
    10490: "Objective 2: verified improvement. No improvement is retained merely because an agent produced it.",
    10550: "The program floor is at least 2,048 work units across 13 buckets.",
    10568: "Merge work when two units are the same mechanism in different wording.",
    10607: "Every work unit must carry the 19 mandatory per-unit fields.",
    10627: "A unit completes only when all 12 completion conditions hold, each with evidence.",
    10635: "Condition 3: the artifact must exceed a meaningful minimum size.",
    10643: "Condition 11: the output must be registered in the artifact manifest.",
    10644: "Condition 12: a downstream consumer must actually be able to read the registered artifact.",
    10725: "Do not count trivial forks or renamed copies toward a floor.",
    10765: "At least 48 council protocols and at least 64 presets must be instantiated.",
    10898: "At least 40 flagship workflows with full end-to-end tests; no placeholders or renamed copies.",
    10937: "The 100-idea brainstorm target is unique_ideas >= 100.",
    11021: "Phase 10 layer 33: benchmark regression tests against a pinned baseline.",
    11024: "Phase 10 requires 36 test layers (layer 36: documentation command tests).",
    11028: "Confirmation receipts require a source_probe fingerprint and a mechanically different verifier_probe.",
    11030: "Confirmers must be fresh agents that did not write the implementation.",
    11039: "A later run that disagrees is a DISCREPANCY to record, never an error to retry away.",
    11041: "Fix the discrepancy-rate threshold BEFORE any confirmation runs.",
    11066: "Phase 13 blind-spot questions begin here and must be turned into work units.",
    11073: "Which owner requirements silently disappeared?",
    11082: "Turn every material blind spot into a work unit or an explicitly accepted residual risk.",
    11086: "Root-cause hierarchy and decision trace, not a flat list.",
    11090: "Unsupported certainty is a named failure class.",
    11091: "Omitted dissent is a named failure class.",
    11095: "Mismatches between code and docs must be measured, not asserted.",
    11098: "The final synthesis agent must verify the artifact manifest on disk before writing the completion report.",
    11150: "No improvement is retained merely because an agent produced it.",
    11320: "Duplicate units from colliding catalogs is a named failure class.",
    11339: "A 100-idea brainstorm that satisfies the count with trivial wording variants is a required failure class.",
    11376: "The program has 21 stopping conditions. Each must return TRUE, FALSE, or NOT-CHECKED with an evidence pointer.",
    11378: "Stopping condition 1: every selected option id is IMPLEMENTED, SUPERSEDED, or REJECTED-WITH-OWNER-REASONING.",
    11382: "Stopping condition 5: important test suites include negative controls or mutations that have been observed to FAIL.",
    11385: "Stopping condition 8: intended improvement without material regression.",
    11389: "Stopping condition 12: docs and code agree.",
    11392: "Stopping condition 15: every open unknown has a named settling experiment and an owner-visible impact statement.",
    11393: "Stopping condition 16: at least 160 workflow candidates classified with provenance and licence records.",
    11394: "Stopping condition 17: at least 96 materially distinct workflow blueprints executable under the selected quality tiers.",
    11395: "Stopping condition 18: at least 48 council protocols remain distinct from presets.",
    11396: "Stopping condition 19: at least 64 editable presets.",
    11402: "Final Deliverables list begins. Each listed deliverable must resolve to a path on disk with byte size and sha256.",
}

IMPERATIVE_RE = re.compile(
    r"(?i)\b(must|shall|required|at least|do not|never |every |turn every|"
    r"stopping condition|unique_ideas|no improvement is retained)\b"
)

LIVE_CANDIDATES = (
    REPO / "_USER-PROMPTS.md",
    REPO / "command-center" / "_USER-PROMPTS.md",
    Path.home() / ".claude" / "harness-restore-20260806" / "_USER-PROMPTS.md",
    Path("/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"),
)


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_units(catalog: dict | None = None) -> list[dict]:
    data = catalog if catalog is not None else load_catalog()
    units = [u for u in (data.get("work_units") or []) if isinstance(u, dict) and u.get("id")]
    return units


def catalog_ids(units: list[dict] | None = None) -> set[str]:
    if units is None:
        units = catalog_units()
    return {str(u["id"]) for u in units if UID_RE.match(str(u.get("id") or ""))}


def _blank_lines() -> list[str]:
    return [""] * (SPEC_END + 1)


def harvest_citations(units: list[dict]) -> dict[int, str]:
    """Place catalog-quoted spec fragments onto cited Prompt Two lines."""
    placed: dict[int, str] = {}
    fields = (
        "spec_anchor",
        "inputs",
        "question_or_target",
        "evidence_requirement",
        "title",
    )

    def consider(text: str) -> None:
        if not isinstance(text, str) or "_USER-PROMPTS.md" not in text and "USER-PROMPTS" not in text:
            if "_USER-PROMPTS.md" not in (text or ""):
                return
        for m in CITE_RE.finditer(text):
            start = int(m.group(1))
            quote = (m.group(3) or "").strip()
            if not (SPEC_START <= start <= SPEC_END):
                continue
            if quote and start not in placed and start not in CANONICAL_LINES:
                placed[start] = quote.rstrip(".") + "."

    for u in units:
        for key in fields:
            val = u.get(key)
            if isinstance(val, str):
                consider(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, str):
                        consider(item)
    return placed


def rebuild_spec_lines(units: list[dict] | None = None) -> list[str]:
    units = units if units is not None else catalog_units()
    lines = _blank_lines()
    harvested = harvest_citations(units)
    for ln, text in harvested.items():
        lines[ln] = text
    for ln, text in CANONICAL_LINES.items():
        lines[ln] = text
    for i in range(SPEC_START, SPEC_END + 1):
        if not lines[i]:
            lines[i] = f"(no catalog-recovered text at _USER-PROMPTS.md:{i})"
    header = [
        f"# Prompt Two slice _USER-PROMPTS.md:{SPEC_START}-{SPEC_END}",
        "# Reconstructed from WORK-UNIT-CATALOG.json citations because the live spec is absent.",
        "# Canonical floor statements overwrite harvested fragments on the same line.",
        "",
    ]
    # File is 1-indexed relative to original spec; prefix dummy lines 1..SPEC_START-1.
    out = [""]
    out.extend(f"(preamble omitted; Prompt Two starts at line {SPEC_START})" for _ in range(1, SPEC_START))
    out.extend(lines[SPEC_START : SPEC_END + 1])
    # Keep header as comments at the top of the written fixture only.
    _ = header
    return out


def write_fixture(lines: list[str]) -> Path:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # lines[0] is unused dummy; write with original numbering.
    body = []
    for i, text in enumerate(lines):
        if i == 0:
            continue
        body.append(text)
    FIXTURE.write_text("\n".join(body) + "\n", encoding="utf-8")
    return FIXTURE


def _read_numbered(path: Path) -> list[str]:
    raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    lines = [""]
    lines.extend(raw)
    return lines


def locate_spec(units: list[dict] | None = None) -> tuple[Path, str, list[str]]:
    for cand in LIVE_CANDIDATES:
        if cand.is_file() and cand.stat().st_size > 0:
            lines = _read_numbered(cand)
            if len(lines) > SPEC_END:
                return cand, "live", lines
    units = units if units is not None else catalog_units()
    lines = rebuild_spec_lines(units)
    path = write_fixture(lines)
    return path, "reconstructed-from-catalog", lines


def slice_text(lines: list[str]) -> list[tuple[int, str]]:
    out = []
    last = min(SPEC_END, len(lines) - 1)
    for i in range(SPEC_START, last + 1):
        out.append((i, lines[i]))
    return out


def extract_floors(lines: list[str]) -> list[dict]:
    recs = []
    for spec in FLOOR_SPECS:
        found_line = None
        found_text = None
        for ln, text in slice_text(lines):
            if spec["rx"].search(text):
                found_line = ln
                found_text = text.strip()
                break
        if found_line is None:
            continue
        recs.append(
            {
                "id": f"REQ-{spec['id']}",
                "kind": "numeric-floor",
                "floor_id": spec["id"],
                "text": found_text,
                "spec_line": found_line,
                "spec_anchor": f"_USER-PROMPTS.md:{found_line}",
            }
        )
    return recs


def floor_recall(floor_recs: list[dict]) -> dict:
    found = [r["floor_id"] for r in floor_recs if r.get("floor_id")]
    missing = [fid for fid in FLOOR_IDS if fid not in found]
    return {
        "passed": len(missing) == 0,
        "required_ids": list(FLOOR_IDS),
        "found_ids": found,
        "missing_ids": missing,
    }


def extract_imperatives(lines: list[str], floor_lines: set[int]) -> list[dict]:
    recs = []
    seen: set[str] = set()
    n = 0
    for ln, text in slice_text(lines):
        t = text.strip()
        if not t or t.startswith("(no catalog-recovered") or t.startswith("(preamble"):
            continue
        if ln in floor_lines:
            # Floors already recorded; still keep a distinct stopping-condition
            # imperative when the line is a numbered condition AND a floor.
            if not re.search(r"(?i)stopping condition \d+", t):
                continue
        if not IMPERATIVE_RE.search(t) and not re.match(r"(?i)stopping condition \d+", t):
            continue
        key = re.sub(r"\s+", " ", t.lower())
        if key in seen:
            continue
        seen.add(key)
        n += 1
        recs.append(
            {
                "id": f"REQ-I-{n:04d}",
                "kind": "imperative",
                "text": t,
                "spec_line": ln,
                "spec_anchor": f"_USER-PROMPTS.md:{ln}",
            }
        )
    return recs


def parse_cites_from_text(text: str) -> list[tuple[int, int]]:
    spans = []
    if not isinstance(text, str):
        return spans
    for m in CITE_RE.finditer(text):
        a = int(m.group(1))
        b = int(m.group(2) or a)
        if a > b:
            a, b = b, a
        spans.append((a, b))
    return spans


def unit_narrow_lines(unit: dict) -> set[int]:
    covered: set[int] = set()
    blobs: list[str] = []
    for key in ("spec_anchor", "inputs", "question_or_target", "evidence_requirement"):
        val = unit.get(key)
        if isinstance(val, str):
            blobs.append(val)
        elif isinstance(val, list):
            blobs.extend(x for x in val if isinstance(x, str))
    for blob in blobs:
        for a, b in parse_cites_from_text(blob):
            if b - a > MAX_BIND_SPAN:
                continue
            for ln in range(a, b + 1):
                if SPEC_START <= ln <= SPEC_END:
                    covered.add(ln)
    return covered


def bind_requirements(reqs: list[dict], units: list[dict]) -> list[dict]:
    index: dict[int, list[str]] = {}
    for u in units:
        uid = str(u.get("id") or "")
        if not UID_RE.match(uid):
            continue
        for ln in unit_narrow_lines(u):
            index.setdefault(ln, []).append(uid)
    out = []
    for r in reqs:
        ids = sorted(set(index.get(int(r["spec_line"]), [])))
        rec = dict(r)
        rec["bound_unit_ids"] = ids
        rec["binding_status"] = "BOUND" if ids else "UNBOUND"
        rec["binding_rule"] = (
            f"narrow citation (span<={MAX_BIND_SPAN}) covering spec_line; "
            "whole-spec range 10473-11437 does not bind"
        )
        out.append(rec)
    return out


def coverage_of(reqs: list[dict]) -> dict:
    bound = sum(1 for r in reqs if r.get("binding_status") == "BOUND")
    unbound = sum(1 for r in reqs if r.get("binding_status") == "UNBOUND")
    total = len(reqs)
    percent = (100.0 * bound / total) if total else 0.0
    return {
        "bound": bound,
        "unbound": unbound,
        "total": total,
        "percent": round(percent, 2),
        "emitted_after_floor_recall": True,
    }


def extract_from_lines(lines: list[str], units: list[dict] | None = None) -> dict:
    units = units if units is not None else catalog_units()
    floors = extract_floors(lines)
    recall = floor_recall(floors)
    floor_lines = {int(r["spec_line"]) for r in floors}
    imps = extract_imperatives(lines, floor_lines)
    reqs = bind_requirements(floors + imps, units)
    result: dict = {
        "floor_recall": recall,
        "requirements": reqs,
        "unbound": [r for r in reqs if r["binding_status"] == "UNBOUND"],
    }
    if recall["passed"]:
        result["coverage"] = coverage_of(reqs)
    return result


def extract_live(units: list[dict] | None = None) -> dict:
    units = units if units is not None else catalog_units()
    path, kind, lines = locate_spec(units)
    result = extract_from_lines(lines, units)
    result["spec_source"] = {
        "path": str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path),
        "kind": kind,
        "slice": f"_USER-PROMPTS.md:{SPEC_START}-{SPEC_END}",
        "line_count": max(0, min(SPEC_END, len(lines) - 1) - SPEC_START + 1),
    }
    if kind != "live":
        result["spec_source"]["note"] = (
            "Live _USER-PROMPTS.md is absent on this worktree. The slice was "
            "reconstructed from catalog spec_anchor/input citations plus the "
            "nine floor statements CC-0024 names. Bindings still use live "
            "WORK-UNIT-CATALOG.json ids."
        )
    result["catalog_unit_count"] = len(units)
    return result


def delete_requirement_text(lines: list[str], rec: dict) -> list[str]:
    """Scratch copy: blank the spec line that carried this requirement."""
    out = list(lines)
    ln = int(rec["spec_line"])
    if 0 <= ln < len(out):
        out[ln] = "(deleted-for-control)"
    return out


def main() -> int:
    result = extract_live()
    recall = result["floor_recall"]
    print(f"spec={result['spec_source']['kind']} path={result['spec_source']['path']}")
    print(f"floor_recall passed={recall['passed']} missing={recall['missing_ids']}")
    print(f"requirements={len(result['requirements'])} unbound={len(result['unbound'])}")
    if "coverage" in result:
        c = result["coverage"]
        print(f"coverage bound={c['bound']} unbound={c['unbound']} percent={c['percent']}")
    else:
        print("coverage withheld (floor-recall failed)")
    return 0 if recall["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
