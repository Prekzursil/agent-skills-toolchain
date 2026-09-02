#!/usr/bin/env python3
"""Option-ID binding: defining-heading index vs title-token similarity.

Probe 1 indexes DEFINING headings only and flags tokens with more than one
candidate definition. Probe 2 never uses heading cardinality as a bind
rule: it binds only when a reference context carries a title token unique
to one candidate; otherwise it records UNRESOLVED.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "ADV-0007"
OUT_REL = "command-center/adversarial/ADV-0007-option-id-binding-refutation.json"
SCHEMA_REL = "command-center/schema/refutation-record.schema.json"
FIXTURES = HERE / "fixtures"

TOKEN_RE = re.compile(r"\b(FX-\d+|MECH-\d+|M-\d+|A-\d+)\b")
HEADING_RE = re.compile(
    r"^(#{1,6})\s+`?(FX-\d+|MECH-\d+|M-\d+|A-\d+)`?"
    r"(?:\s*[—:\-–]\s*|\s+)(.*)$"
)
STOP = frozenset(
    {
        "a",
        "an",
        "and",
        "around",
        "card",
        "family",
        "for",
        "from",
        "in",
        "is",
        "not",
        "of",
        "on",
        "option",
        "or",
        "the",
        "this",
        "to",
        "with",
    }
)
SKIP_DIR = frozenset(
    {
        ".git",
        ".venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "ADV-0007",
    }
)
TEXT_SUFFIX = {".md", ".txt", ".json", ".jsonl", ".yml", ".yaml"}
MAX_BYTES = 2_000_000

INPUT_CANDIDATES = {
    "OPTION-ID-RESOLUTION.json": (
        "command-center/OPTION-ID-RESOLUTION.json",
        "OPTION-ID-RESOLUTION.json",
    ),
    "07-OPTION-UNIVERSE.md": (
        "07-OPTION-UNIVERSE.md",
        "command-center/07-OPTION-UNIVERSE.md",
    ),
    "07-OPTION-UNIVERSE.json": (
        "07-OPTION-UNIVERSE.json",
        "command-center/07-OPTION-UNIVERSE.json",
    ),
    "13-ARCHITECTURE-CANDIDATES.md": (
        "13-ARCHITECTURE-CANDIDATES.md",
        "command-center/13-ARCHITECTURE-CANDIDATES.md",
    ),
    "17-DECISION-LOG.md": (
        "17-DECISION-LOG.md",
        "command-center/17-DECISION-LOG.md",
    ),
    "wave3-deep-research-SKILL.md": (
        "wave3/ast-cc/skills/deep-research/SKILL.md",
        "skills/deep-research/SKILL.md",
    ),
    "wave1-REGISTER.md": ("wave1/REGISTER.md",),
}

CATALOG_NAMED_SAMPLE = ("A-01", "A-03", "A-12", "A-13", "A-17", "A-18")
PLANTED_IDS = ("FX-16", "FX-40", "MECH-99")
AMBIGUOUS_ID = "FX-16"
UNAMBIGUOUS_ID = "FX-40"

PROBE1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0007/probe1_defining_index.py"
)
PROBE2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0007/probe2_title_similarity.py"
)

SENTINEL = (
    "SUCCESS:ADV-0007 emitted ONLY when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, records BOTH named probes "
    "verbatim with their raw output, carries exactly one verdict from "
    "{CONFIRMED|REFUTED|PARTIAL|NOT-CHECKED|BLOCKED} per enumerated target, "
    "and records the result of every listed control/negative test. Any missing "
    "control downgrades the unit's verdicts to NOT-CHECKED. Otherwise "
    "FAILED:ADV-0007 <reason>."
)

QUESTION = (
    "For every option ID in the Prompt Two selection list, does the ID "
    "resolve to exactly one option card across ALL artifacts that mention it "
    "- and for any ID that appears in more than one namespace, which binding "
    "did each consuming document actually use?"
)

ALLOWED = frozenset(
    {"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"}
)


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in STOP}


def input_presence(repo: Path) -> dict[str, Any]:
    rows = []
    for label, candidates in INPUT_CANDIDATES.items():
        found = None
        for cand in candidates:
            if (repo / cand).is_file():
                found = cand.replace("\\", "/")
                break
        rows.append(
            {
                "label": label,
                "present": found is not None,
                "path": found,
                "candidates": list(candidates),
            }
        )
    return {
        "any_present": any(r["present"] for r in rows),
        "rows": rows,
        "missing": [r["label"] for r in rows if not r["present"]],
    }


def load_selected_meta() -> dict[str, Any]:
    path = FIXTURES / "selected-ids.json"
    return json.loads(path.read_text(encoding="utf-8"))


def iter_text_files(root: Path) -> list[Path]:
    out: list[Path] = []
    if not root.is_dir():
        return out
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIX:
            continue
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        out.append(path)
    return out


def defining_headings(path: Path, namespace: str) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    found: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines(), 1):
        m = HEADING_RE.match(line.strip())
        if not m:
            continue
        found.append(
            {
                "id": m.group(2),
                "title": (m.group(3) or "").strip(),
                "path": rel(path),
                "line": i,
                "namespace": namespace,
                "heading": line.strip(),
            }
        )
    return found


def reference_sites(path: Path, defining_lines: set[int]) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    found: list[dict[str, Any]] = []
    for i, line in enumerate(lines, 1):
        if i in defining_lines:
            continue
        for m in TOKEN_RE.finditer(line):
            start = max(0, i - 2)
            end = min(len(lines), i + 1)
            context = " ".join(lines[start:end])
            found.append(
                {
                    "id": m.group(1),
                    "path": rel(path),
                    "line": i,
                    "excerpt": line.strip()[:240],
                    "context": context.strip()[:400],
                }
            )
    return found


def fixture_corpus() -> dict[str, Any]:
    defining_dir = FIXTURES / "defining"
    ref_dir = FIXTURES / "references"
    defs: list[dict[str, Any]] = []
    for path in sorted(defining_dir.glob("*.md")):
        defs.extend(defining_headings(path, namespace=f"fixture:{path.stem}"))
    def_lines: dict[str, set[int]] = defaultdict(set)
    for d in defs:
        def_lines[d["path"]].add(d["line"])
    refs: list[dict[str, Any]] = []
    for path in sorted(list(defining_dir.glob("*.md")) + list(ref_dir.glob("*.md"))):
        refs.extend(reference_sites(path, def_lines[rel(path)]))
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in defs:
        by_id[d["id"]].append(d)
    return {
        "definitions": defs,
        "references": refs,
        "index": {k: v for k, v in sorted(by_id.items())},
    }


def live_corpus(repo: Path) -> dict[str, Any]:
    roots = [
        repo / "07-OPTION-UNIVERSE.md",
        repo / "07-OPTION-UNIVERSE.json",
        repo / "13-ARCHITECTURE-CANDIDATES.md",
        repo / "17-DECISION-LOG.md",
        repo / "OPTION-ID-RESOLUTION.json",
        repo / "command-center" / "OPTION-ID-RESOLUTION.json",
        repo / "wave3",
        repo / "wave1",
        repo / "skills",
    ]
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(iter_text_files(root))
    defs: list[dict[str, Any]] = []
    for path in files:
        defs.extend(defining_headings(path, namespace="live"))
    def_lines: dict[str, set[int]] = defaultdict(set)
    for d in defs:
        def_lines[d["path"]].add(d["line"])
    refs: list[dict[str, Any]] = []
    for path in files:
        refs.extend(reference_sites(path, def_lines[rel(path)]))
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in defs:
        by_id[d["id"]].append(d)
    return {
        "file_count": len(files),
        "definitions": defs,
        "references": refs,
        "index": {k: v for k, v in sorted(by_id.items())},
    }


def probe1_index(corpus: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for token, defs in corpus["index"].items():
        refs = [r for r in corpus["references"] if r["id"] == token]
        n = len(defs)
        if n == 0:
            flag = "ABSENT"
        elif n == 1:
            flag = "UNIQUE"
        else:
            flag = "MULTI-DEF"
        rows.append(
            {
                "id": token,
                "definition_count": n,
                "reference_count": len(refs),
                "flag": flag,
                "definitions": [
                    {
                        "path": d["path"],
                        "line": d["line"],
                        "title": d["title"],
                        "namespace": d["namespace"],
                    }
                    for d in defs
                ],
            }
        )
    rows.sort(key=lambda r: r["id"])
    return {
        "instrument": "defining-heading-index",
        "rows": rows,
        "multi_def_ids": [r["id"] for r in rows if r["flag"] == "MULTI-DEF"],
        "unique_ids": [r["id"] for r in rows if r["flag"] == "UNIQUE"],
    }


def discriminating_title_tokens(
    candidates: list[dict[str, Any]],
) -> dict[int, set[str]]:
    per = {id(c): tokens(c.get("title") or "") for c in candidates}
    counts: dict[str, int] = defaultdict(int)
    for tokset in per.values():
        for t in tokset:
            counts[t] += 1
    unique = {t for t, n in counts.items() if n == 1}
    return {id(c): (per[id(c)] & unique) for c in candidates}


def resolve_by_title(
    context: str, candidates: list[dict[str, Any]]
) -> dict[str, Any]:
    if not candidates:
        return {
            "status": "ABSENT",
            "bound_to": None,
            "reason": "no defining heading for this token",
        }
    ctx = tokens(context)
    if len(candidates) == 1:
        title_toks = tokens(candidates[0].get("title") or "")
        if title_toks and not (ctx & title_toks):
            return {
                "status": "UNRESOLVED",
                "bound_to": None,
                "reason": (
                    "sole candidate title tokens do not appear in the "
                    "reference context; refusing to guess"
                ),
            }
        bound = {
            "path": candidates[0]["path"],
            "line": candidates[0]["line"],
            "title": candidates[0]["title"],
            "namespace": candidates[0]["namespace"],
        }
        return {
            "status": "BOUND",
            "bound_to": bound,
            "reason": (
                "single candidate and context carries its title tokens"
                if title_toks
                else "single candidate with empty title"
            ),
        }
    disc = discriminating_title_tokens(candidates)
    hits = []
    for c in candidates:
        overlap = ctx & disc[id(c)]
        if overlap:
            hits.append((c, sorted(overlap)))
    if len(hits) == 1:
        c, overlap = hits[0]
        return {
            "status": "BOUND",
            "bound_to": {
                "path": c["path"],
                "line": c["line"],
                "title": c["title"],
                "namespace": c["namespace"],
            },
            "discriminating_tokens": overlap,
            "reason": "context carries title tokens unique to one candidate",
        }
    return {
        "status": "UNRESOLVED",
        "bound_to": None,
        "reason": (
            "multiple defining headings and no unique title token in "
            "the reference context; UNRESOLVED rather than guess"
        ),
        "candidate_count": len(candidates),
    }


def probe2_similarity(corpus: dict[str, Any]) -> dict[str, Any]:
    index = corpus["index"]
    resolutions = []
    for ref in corpus["references"]:
        resolved = resolve_by_title(ref["context"], index.get(ref["id"]) or [])
        resolutions.append(
            {
                "id": ref["id"],
                "path": ref["path"],
                "line": ref["line"],
                "excerpt": ref["excerpt"],
                "status": resolved["status"],
                "bound_to": resolved.get("bound_to"),
                "reason": resolved["reason"],
            }
        )
    unresolved = [r for r in resolutions if r["status"] == "UNRESOLVED"]
    bound = [r for r in resolutions if r["status"] == "BOUND"]
    return {
        "instrument": "title-token-similarity",
        "resolutions": resolutions,
        "unresolved_count": len(unresolved),
        "bound_count": len(bound),
        "unresolved": unresolved,
        "bound": bound,
    }


def control_probe1(p1: dict[str, Any]) -> dict[str, Any]:
    by = {r["id"]: r for r in p1["rows"]}
    amb = by.get(AMBIGUOUS_ID)
    uni = by.get(UNAMBIGUOUS_ID)
    amb_ok = bool(amb and amb["flag"] == "MULTI-DEF" and amb["definition_count"] >= 2)
    uni_ok = bool(uni and uni["flag"] == "UNIQUE" and uni["definition_count"] == 1)
    return {
        "id": "C-P1-HEADING-CARDINALITY",
        "ambiguous_id": AMBIGUOUS_ID,
        "unambiguous_id": UNAMBIGUOUS_ID,
        "ambiguous_flagged_multi_def": amb_ok,
        "unambiguous_unique": uni_ok,
        "pass": amb_ok and uni_ok,
        "ambiguous_row": amb,
        "unambiguous_row": uni,
    }


def control_probe2(p2: dict[str, Any]) -> dict[str, Any]:
    amb_refs = [
        r
        for r in p2["resolutions"]
        if r["id"] == AMBIGUOUS_ID and "ambiguous.md" in r["path"]
    ]
    uni_refs = [
        r
        for r in p2["resolutions"]
        if r["id"] == UNAMBIGUOUS_ID and "unambiguous.md" in r["path"]
    ]
    amb_unresolved = bool(amb_refs) and all(
        r["status"] == "UNRESOLVED" for r in amb_refs
    )
    uni_bound = (
        bool(uni_refs)
        and all(r["status"] == "BOUND" for r in uni_refs)
        and len({(r["bound_to"] or {}).get("path") for r in uni_refs}) == 1
    )
    disc_refs = [
        r
        for r in p2["resolutions"]
        if r["id"] == AMBIGUOUS_ID and "discriminating-fx16.md" in r["path"]
    ]
    disc_bound = bool(disc_refs) and all(r["status"] == "BOUND" for r in disc_refs)
    return {
        "id": "C-P2-UNRESOLVED-VS-UNIQUE",
        "planted_ambiguous_unresolved": amb_unresolved,
        "planted_unambiguous_one_binding": uni_bound,
        "discriminating_fx16_bound": disc_bound,
        "pass": amb_unresolved and uni_bound,
        "ambiguous_refs": amb_refs,
        "unambiguous_refs": uni_refs,
        "discriminating_refs": disc_refs,
    }


def target_verdict(
    token: str,
    kind: str,
    p1: dict[str, Any],
    p2: dict[str, Any],
    live: dict[str, Any],
    controls_ok: bool,
) -> dict[str, Any]:
    if not controls_ok:
        return {
            "id": token,
            "kind": kind,
            "verdict": "NOT-CHECKED",
            "basis": "Required detector control missing; catalog downgrades all verdicts.",
        }
    p1_row = next((r for r in p1["rows"] if r["id"] == token), None)
    live_defs = (live.get("index") or {}).get(token) or []
    p2_refs = [r for r in p2["resolutions"] if r["id"] == token]
    if kind.startswith("live-selected") or kind == "live-collision":
        if not live_defs:
            return {
                "id": token,
                "kind": kind,
                "verdict": "NOT-CHECKED",
                "basis": (
                    "No DEFINING heading for this token on the live worktree. "
                    "07-OPTION-UNIVERSE / 13-ARCHITECTURE-CANDIDATES / "
                    "OPTION-ID-RESOLUTION.json are absent, so a silent wrong "
                    "binding cannot be proven or disproven."
                ),
                "live_definition_count": 0,
            }
        if len(live_defs) == 1:
            return {
                "id": token,
                "kind": kind,
                "verdict": "CONFIRMED",
                "basis": "Live tree has exactly one defining heading for this token.",
                "live_definition_count": 1,
            }
        return {
            "id": token,
            "kind": kind,
            "verdict": "REFUTED",
            "basis": (
                f"Live tree has {len(live_defs)} defining headings; unique "
                "binding is false."
            ),
            "live_definition_count": len(live_defs),
        }
    if not p1_row:
        return {
            "id": token,
            "kind": kind,
            "verdict": "NOT-CHECKED",
            "basis": "Token was not present in the fixture defining index.",
        }
    flag = p1_row["flag"]
    unresolved = [r for r in p2_refs if r["status"] == "UNRESOLVED"]
    bound = [r for r in p2_refs if r["status"] == "BOUND"]
    if flag == "UNIQUE" and not unresolved:
        return {
            "id": token,
            "kind": kind,
            "verdict": "CONFIRMED",
            "basis": (
                "Exactly one defining heading. Title-similarity bound every "
                "reference that existed; zero references is still a unique card."
            ),
            "definition_count": p1_row["definition_count"],
            "bound_references": len(bound),
        }
    if flag == "MULTI-DEF":
        if unresolved:
            return {
                "id": token,
                "kind": kind,
                "verdict": "REFUTED",
                "basis": (
                    f"{p1_row['definition_count']} defining headings across "
                    "namespaces; at least one reference is UNRESOLVED "
                    "(no discriminating title token). Unique-card binding is false."
                ),
                "definition_count": p1_row["definition_count"],
                "unresolved_references": len(unresolved),
                "bound_references": len(bound),
            }
        return {
            "id": token,
            "kind": kind,
            "verdict": "PARTIAL",
            "basis": (
                "Multiple defining headings, but every planted reference "
                "carried a discriminating title token so probe 2 bound each one."
            ),
            "definition_count": p1_row["definition_count"],
        }
    if flag == "UNIQUE" and unresolved:
        return {
            "id": token,
            "kind": kind,
            "verdict": "PARTIAL",
            "basis": "One defining heading, but probe 2 left a reference UNRESOLVED.",
        }
    return {
        "id": token,
        "kind": kind,
        "verdict": "NOT-CHECKED",
        "basis": f"Unexpected flag={flag}",
    }


def build_report(repo: Path) -> dict[str, Any]:
    planted = fixture_corpus()
    live = live_corpus(repo)
    p1 = probe1_index(planted)
    p2 = probe2_similarity(planted)
    c1 = control_probe1(p1)
    c2 = control_probe2(p2)
    controls_ok = bool(c1["pass"] and c2["pass"])
    inputs = input_presence(repo)
    meta = load_selected_meta()
    targets: list[dict[str, Any]] = []
    for token in PLANTED_IDS:
        targets.append(
            target_verdict(token, "planted-control", p1, p2, live, controls_ok)
        )
    for token in CATALOG_NAMED_SAMPLE:
        targets.append(
            target_verdict(token, "live-selected-sample", p1, p2, live, controls_ok)
        )
    targets.append(
        target_verdict("M-16", "live-collision", p1, p2, live, controls_ok)
    )
    if any(t["verdict"] not in ALLOWED for t in targets):
        raise RuntimeError("illegal verdict")
    if len({t["id"] + ":" + t["kind"] for t in targets}) != len(targets):
        raise RuntimeError("duplicate targets")
    counts = {
        v: sum(1 for t in targets if t["verdict"] == v)
        for v in ["CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"]
    }
    return {
        "ok": controls_ok,
        "controls_ok": controls_ok,
        "inputs": inputs,
        "selected_meta": meta,
        "planted": {
            "definition_count": len(planted["definitions"]),
            "reference_count": len(planted["references"]),
        },
        "live": {
            "file_count": live["file_count"],
            "definition_count": len(live["definitions"]),
            "reference_count": len(live["references"]),
            "index_ids": sorted((live.get("index") or {}).keys()),
        },
        "probe1": p1,
        "probe2": {
            "instrument": p2["instrument"],
            "unresolved_count": p2["unresolved_count"],
            "bound_count": p2["bound_count"],
            "resolutions": p2["resolutions"],
        },
        "controls": [c1, c2],
        "targets": targets,
        "target_verdict_counts": counts,
    }
