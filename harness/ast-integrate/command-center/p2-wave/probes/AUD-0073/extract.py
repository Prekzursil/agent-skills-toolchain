#!/usr/bin/env python3
"""Live UNVERIFIED / residual-claim extraction for AUD-0073.

AUD-0068 is absent on this worktree. The scanner walks the live program
corpus instead of inventing Prompt-One records. WORK-UNIT-CATALOG.json is
excluded: those hits are unit specifications, not tagged claims.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "AUD-0073"
OUTPUT_REL = "command-center/audit/AUD-0073-settling-probe-extraction.json"
AUD68_REL = "command-center/audit/AUD-0068-claim-extraction-canonical.json"
REGISTRY_REL = "command-center/CLAIM-REGISTRY.json"
CONTROL_INLINE = "command-center/p2-wave/probes/AUD-0073/fixtures/control-inline.md"
CONTROL_TRAILING = "command-center/p2-wave/probes/AUD-0073/fixtures/control-trailing.md"

STATUS_KEYS = ("verification_status", "verification_status", "claim_status")
RESIDUAL_KEYS = ("residual_unknowns", "residual_unknowns", "residuals")
CLAIM_KEYS = ("claim", "text", "statement", "unknown", "question", "title")
EXPERIMENT_KEYS = (
    "settling_probe",
    "settling_experiment",
    "settling_experiment",
    "named_experiment",
    "named_probe",
    "source_probe",
    "verifier_probe",
)
TRAILING_HEADING = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(limitations|residuals?|caveats?|unknowns|"
    r"not-checked|not checked|residual unknowns)\b"
)
UNVERIFIED_TAG = re.compile(r"(?<![A-Za-z])UNVERIFIED(?![A-Za-z])")
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "agent-transcripts"}
SKIP_FILES = {
    "WORK-UNIT-CATALOG.json",
    "UNIT-ARTIFACT-MANIFEST.json",
    "SUBAGENT-RETURN.json",
}
MAX_FILE_BYTES = 4_000_000
CORPUS: tuple[tuple[str, bool], ...] = (
    (REGISTRY_REL, False),
    ("command-center/receipts", True),
    ("command-center/research", True),
    ("command-center/confirmation", True),
    ("command-center/audit", True),
    ("command-center/p2-wave/P2-BUILD-ROUND1.md", False),
    ("command-center/p2-wave/P2-BUILD-ROUND3.md", False),
    ("command-center/p2-wave/probes/IMP-0259/fixtures", True),
    (CONTROL_INLINE, False),
    (CONTROL_TRAILING, False),
)


def relpath(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def load_text(path: Path) -> str:
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8", "replace")


def frac(offset: int, n: int) -> float:
    if n <= 1:
        return 0.0
    return round(min(1.0, max(0.0, offset / (n - 1))), 6)


def heading_before(text: str, offset: int) -> str:
    heading = ""
    for line in text[: max(0, offset)].splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or TRAILING_HEADING.match(stripped):
            heading = stripped
    return heading


def is_trailing(heading: str) -> bool:
    if not heading:
        return False
    body = heading.lstrip("#").strip()
    return bool(TRAILING_HEADING.match(heading) or TRAILING_HEADING.match(body))


def nearby_sentence(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset)
    start = 0 if start < 0 else start + 1
    end = text.find("\n", offset)
    if end < 0:
        end = min(len(text), offset + 400)
    line = text[start:end].strip()
    if line:
        return line[:500]
    lo = max(0, offset - 160)
    hi = min(len(text), offset + 170)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()[:500]


def claim_text(obj: Any) -> str:
    if isinstance(obj, str):
        return obj.strip()
    if not isinstance(obj, dict):
        return json.dumps(obj, sort_keys=True)[:400]
    for key in CLAIM_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return json.dumps({k: obj.get(k) for k in list(obj)[:6]}, sort_keys=True)[:400]


def named_experiment(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in EXPERIMENT_KEYS:
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def snippet_offset(text: str, snippet: str) -> int:
    needle = snippet.strip()[:120]
    if not needle:
        return 0
    idx = text.find(needle)
    return idx if idx >= 0 else 0


def position_of(
    *,
    text: str,
    offset: int,
    inline_to_claim: bool,
    json_residual: bool,
) -> dict[str, Any]:
    n = len(text)
    ratio = frac(offset, n)
    heading = heading_before(text, offset)
    trailing = is_trailing(heading)
    in_final_15 = ratio >= 0.85
    if json_residual or trailing:
        verdict = "BURIED-TRAILING-SECTION"
    elif inline_to_claim:
        verdict = "INLINE"
    elif in_final_15:
        verdict = "LATE-DOCUMENT"
    else:
        verdict = "MID-DOCUMENT"
    return {
        "char_offset": offset,
        "doc_bytes": n,
        "position_frac": ratio,
        "in_final_15_percent": in_final_15,
        "last_heading": heading[:120],
        "trailing_heading": trailing,
        "json_residual_array": json_residual,
        "inline_to_claim": inline_to_claim,
        "position_verdict": verdict,
    }


def is_runnable(experiment: str) -> bool:
    if not experiment:
        return False
    low = experiment.lower().strip()
    if low in {"not-a-decision-input", "n/a", "none", "unknown"}:
        return False
    if "investigate further" in low or low == "investigate":
        return False
    return True


def minimal_experiment(flag: dict[str, Any]) -> dict[str, str]:
    named = str(flag.get("named_experiment") or "").strip()
    if is_runnable(named):
        command = named
        if named.endswith(".py") and not named.startswith("python"):
            command = f"PYTHONDONTWRITEBYTECODE=1 python3 -B {named}"
        return {
            "kind": "named-in-source",
            "command": command,
            "expected_observation": (
                "The named command produces a discriminating pass/fail "
                "against the adjacent claim."
            ),
            "discriminating_outcome": (
                "CONFIRMED if the observation matches the claim; REFUTED otherwise."
            ),
        }
    rel = flag["path"]
    claim = str(flag.get("claim_text") or "")
    if "pretty-print" in claim.lower() or "two-space indent" in claim.lower():
        return {
            "kind": "minimal-generated",
            "command": (
                "python3 -B -c \"from pathlib import Path; "
                "p=Path('command-center/CLAIM-REGISTRY.json'); "
                "t=p.read_text(encoding='utf-8'); "
                "print('indent2', t.splitlines()[1].startswith('  ') if t else False)\""
            ),
            "expected_observation": (
                "Line 2 of CLAIM-REGISTRY.json begins with exactly two spaces."
            ),
            "discriminating_outcome": (
                "CONFIRMED if indent is two spaces; REFUTED otherwise."
            ),
        }
    snippet = claim.replace("'", "")[:80]
    return {
        "kind": "minimal-generated",
        "command": (
            f"python3 -B -c \"from pathlib import Path; "
            f"t=Path({rel!r}).read_text(encoding='utf-8'); "
            f"print({snippet!r} in t, len(t))\""
        ),
        "expected_observation": (
            f"The claim snippet still occurs in {rel} and the file is non-empty."
        ),
        "discriminating_outcome": (
            "CONFIRMED if the snippet is present; REFUTED if the residual has "
            "been removed or rewritten without a replacement tag."
        ),
    }


def should_skip(path: Path) -> bool:
    rel = relpath(path)
    if rel == OUTPUT_REL:
        return True
    if (
        rel.startswith("command-center/p2-wave/probes/AUD-0073/")
        and "/fixtures/" not in rel
    ):
        return True
    if path.name in SKIP_FILES:
        return True
    if path.name.startswith("_") and path.suffix == ".json":
        return True
    if set(path.parts) & SKIP_DIRS:
        return True
    return False


def corpus_files() -> Iterable[Path]:
    seen: set[str] = set()
    for rel, is_dir in CORPUS:
        path = REPO / rel
        if is_dir:
            if not path.is_dir():
                continue
            for child in path.rglob("*"):
                if not child.is_file():
                    continue
                if child.suffix.lower() not in {".json", ".md", ".txt"}:
                    continue
                if should_skip(child):
                    continue
                key = relpath(child)
                if key in seen:
                    continue
                try:
                    if child.stat().st_size > MAX_FILE_BYTES:
                        continue
                except OSError:
                    continue
                seen.add(key)
                yield child
        else:
            if not path.is_file() or should_skip(path):
                continue
            key = relpath(path)
            if key in seen:
                continue
            seen.add(key)
            yield path


def walk_json(obj: Any, json_path: str = "$") -> Iterable[tuple[str, Any]]:
    if isinstance(obj, dict):
        yield json_path, obj
        for key, val in obj.items():
            child = f"{json_path}.{key}"
            if isinstance(val, (dict, list)):
                yield from walk_json(val, child)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            yield from walk_json(item, f"{json_path}[{i}]")


def json_flags(path: Path, text: str) -> list[dict[str, Any]]:
    try:
        doc = json.loads(text)
    except json.JSONDecodeError:
        return []
    flags: list[dict[str, Any]] = []
    seen: set[tuple[str, int, str]] = set()
    rel = relpath(path)

    def add(flag: dict[str, Any]) -> None:
        key = (flag["path"], flag["position"]["char_offset"], flag["kind"])
        if key in seen:
            return
        seen.add(key)
        flags.append(flag)

    for jpath, node in walk_json(doc):
        if not isinstance(node, dict):
            continue
        residual_here = any(part in jpath for part in RESIDUAL_KEYS)
        for skey in STATUS_KEYS:
            status = node.get(skey)
            if str(status or "").upper() != "UNVERIFIED":
                continue
            claim = claim_text(node)
            needle = f'"{skey}": "UNVERIFIED"'
            loc = -1
            if claim:
                cidx = snippet_offset(text, claim)
                window_start = max(0, cidx - 240)
                window = text[window_start : cidx + max(len(claim), 80) + 240]
                rel_loc = window.find(needle)
                if rel_loc >= 0:
                    loc = window_start + rel_loc
                elif cidx > 0:
                    loc = cidx
            if loc < 0:
                loc = text.find(needle)
            if loc < 0:
                loc = text.find(f'"{skey}"')
            off = loc if loc >= 0 else snippet_offset(text, str(status))
            add(
                {
                    "id": f"{rel}:{jpath}:{skey}",
                    "kind": "unverified-status",
                    "path": rel,
                    "json_path": jpath,
                    "claim_text": claim,
                    "adjacent_sentence": claim or nearby_sentence(text, off),
                    "named_experiment": named_experiment(node),
                    "named_runnable": is_runnable(named_experiment(node)),
                    "position": position_of(
                        text=text,
                        offset=off,
                        inline_to_claim=not residual_here,
                        json_residual=residual_here,
                    ),
                    "control": "/fixtures/" in rel,
                }
            )
        for rkey in RESIDUAL_KEYS:
            val = node.get(rkey)
            if not isinstance(val, list):
                continue
            key_off = text.find(f'"{rkey}"')
            for i, item in enumerate(val):
                claim = claim_text(item)
                named = named_experiment(item) if isinstance(item, dict) else ""
                snippet = claim[:80] if claim else f"{rkey}[{i}]"
                off = snippet_offset(text, snippet)
                if off == 0 and key_off >= 0:
                    off = key_off
                add(
                    {
                        "id": f"{rel}:{jpath}.{rkey}[{i}]",
                        "kind": "residual-statement",
                        "path": rel,
                        "json_path": f"{jpath}.{rkey}[{i}]",
                        "claim_text": claim,
                        "adjacent_sentence": claim or nearby_sentence(text, off),
                        "named_experiment": named,
                        "named_runnable": is_runnable(named),
                        "position": position_of(
                            text=text,
                            offset=off,
                            inline_to_claim=not residual_here,
                            json_residual=True,
                        ),
                        "control": False,
                    }
                )
    return flags


def text_flags(path: Path, text: str) -> list[dict[str, Any]]:
    rel = relpath(path)
    flags: list[dict[str, Any]] = []
    is_control = rel.startswith("command-center/p2-wave/probes/AUD-0073/fixtures/")
    if path.suffix == ".json" and not is_control:
        return flags
    for match in UNVERIFIED_TAG.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end].lower()
        if (
            any(token in line for token in ("vocabulary", "enum", "status_vocabulary"))
            and not is_control
        ):
            continue
        adj = nearby_sentence(text, match.start())
        heading = heading_before(text, match.start())
        named = ""
        window = text[max(0, match.start() - 80) : match.end() + 240]
        for key in ("settling experiment", "settling probe", "named experiment"):
            if key in window.lower():
                named = re.sub(r"\s+", " ", window).strip()[:240]
                break
        flags.append(
            {
                "id": f"{rel}:offset:{match.start()}",
                "kind": "unverified-tag",
                "path": rel,
                "json_path": None,
                "claim_text": adj,
                "adjacent_sentence": adj,
                "named_experiment": named,
                "named_runnable": is_runnable(named),
                "position": position_of(
                    text=text,
                    offset=match.start(),
                    inline_to_claim=not is_trailing(heading),
                    json_residual=False,
                ),
                "control": is_control,
            }
        )
    return flags


def with_experiments(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for flag in flags:
        exp = minimal_experiment(flag)
        row = dict(flag)
        row["experiment"] = exp
        row["has_named_runnable_experiment"] = bool(flag.get("named_runnable"))
        row["needs_human_framing"] = exp["kind"] == "needs-human-framing"
        out.append(row)
    return out


def scan() -> dict[str, Any]:
    aud68 = REPO / AUD68_REL
    files = list(corpus_files())
    flags: list[dict[str, Any]] = []
    scanned: list[dict[str, Any]] = []
    for path in files:
        text = load_text(path)
        rel = relpath(path)
        before = len(flags)
        if path.suffix.lower() == ".json":
            flags.extend(json_flags(path, text))
        flags.extend(text_flags(path, text))
        scanned.append(
            {
                "path": rel,
                "bytes": len(text.encode("utf-8")),
                "flags_added": len(flags) - before,
            }
        )
    flags = with_experiments(flags)
    n = len(flags)
    n_named = sum(1 for f in flags if f["has_named_runnable_experiment"])
    n_final15 = sum(1 for f in flags if f["position"]["in_final_15_percent"])
    verdicts: dict[str, int] = {}
    for f in flags:
        v = f["position"]["position_verdict"]
        verdicts[v] = verdicts.get(v, 0) + 1
    controls = [f for f in flags if f["control"]]
    inline_ctrl = [f for f in controls if "control-inline.md" in f["path"]]
    trail_ctrl = [f for f in controls if "control-trailing.md" in f["path"]]
    return {
        "unit_id": UNIT,
        "upstream_aud_0068": {
            "path": AUD68_REL,
            "present": aud68.is_file() and aud68.stat().st_size > 0,
            "note": (
                "Canonical Prompt-One claim records are absent; live corpus "
                "scan is the honest input. Retrying as if AUD-0068 existed "
                "would be a detector failure."
            ),
        },
        "catalog_excluded": "command-center/WORK-UNIT-CATALOG.json",
        "files_scanned": len(scanned),
        "file_rows": scanned,
        "n_flags": n,
        "n_with_named_runnable_experiment": n_named,
        "n_without_named_runnable_experiment": n - n_named,
        "n_in_final_15_percent": n_final15,
        "final_15_percent_rate": (n_final15 / n) if n else None,
        "recorded_estate_baseline": {
            "n_flags": 127,
            "final_15_percent_rate": 0.40,
            "note": (
                "Catalog input cites 40% of 127 flags in the final 15% of "
                "their document. That is a prior-estate figure, not a live "
                "count on this worktree."
            ),
        },
        "position_verdict_counts": verdicts,
        "flags": flags,
        "controls": {"inline": inline_ctrl, "trailing": trail_ctrl},
    }


def control_diff(result: dict[str, Any]) -> dict[str, Any]:
    inline = result["controls"]["inline"]
    trailing = result["controls"]["trailing"]
    iv = {f["position"]["position_verdict"] for f in inline}
    tv = {f["position"]["position_verdict"] for f in trailing}
    differ = bool(inline) and bool(trailing) and iv.isdisjoint(tv)
    return {
        "inline_count": len(inline),
        "trailing_count": len(trailing),
        "inline_verdicts": sorted(iv),
        "trailing_verdicts": sorted(tv),
        "differ": differ,
    }


if __name__ == "__main__":
    doc = scan()
    ctrl = control_diff(doc)
    summary = {k: doc[k] for k in doc if k not in {"flags", "file_rows", "controls"}}
    summary["control"] = ctrl
    print(json.dumps(summary, indent=1, sort_keys=True))
    print(
        f"n_flags={doc['n_flags']} named={doc['n_with_named_runnable_experiment']} "
        f"control_differ={ctrl['differ']}"
    )
