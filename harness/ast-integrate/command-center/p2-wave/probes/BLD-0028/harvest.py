"""Harvest published zeros and grade detector-control on the producing receipt.

A reported zero is a published empty / clean / no-findings / not-found result.
Control evidence must already sit on the PRODUCING document: a known-present
or known-broken fire AND a known-good silence. This module does not backfill
controls onto other receipts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "BLD-0028"
FIXTURES = HERE / "fixtures"

ZERO_ARRAY_KEYS = frozenset({"findings", "violations", "issues", "defects"})
ZERO_COUNT_KEYS = frozenset(
    {
        "finding_count",
        "findings_count",
        "violation_count",
        "issue_count",
        "defect_count",
        "n_findings",
    }
)
RESULT_KEYS = frozenset(
    {
        "result",
        "verdict",
        "status",
        "classification",
        "answer",
        "outcome",
        "conclusion",
        "finding",
    }
)
ZERO_STRINGS = frozenset(
    {
        "no findings",
        "no-findings",
        "not found",
        "not-found",
        "no issues",
        "no-issues",
        "clean",
        "empty",
        "none",
        "0 findings",
        "zero findings",
    }
)
MENTION_PATH_PARTS = frozenset(
    {
        "example",
        "examples",
        "quote",
        "quoted",
        "mention",
        "question",
        "question_or_target",
        "tests_required",
        "description",
        "notes",
        "raw_output",
        "schema",
        "prompt",
    }
)
EMPTY_NOT_PASS_TRUE = frozenset(
    {
        "empty_live_is_not_a_pass",
        "empty_set_is_not_pass",
        "empty_is_not_a_pass",
        "empty_set_is_not_a_pass",
        "empty_corpus_is_not_green",
        "empty_set_is_not_a_pass",
    }
)
UNIT_ID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")
QUOTED_PHRASE_RE = re.compile(
    r"""['\"][^'\"]*(no findings|not found|no issues|clean)[^'\"]*['\"]""",
    re.I,
)
PHRASE_RE = re.compile(
    r"\b(no findings|not found|no issues|zero findings)\b",
    re.I,
)


def rel_of(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def producer_of(doc: Any, path: Path) -> str:
    if isinstance(doc, dict):
        for key in ("unit_id", "id", "unit"):
            val = doc.get(key)
            if isinstance(val, str) and UNIT_ID_RE.match(val.strip()):
                return val.strip()
    if UNIT_ID_RE.match(path.stem):
        return path.stem
    return path.stem


def path_is_mention(parts: tuple[str, ...]) -> bool:
    return bool({p.lower() for p in parts} & MENTION_PATH_PARTS)


def empty_not_treated_as_pass(doc: Any) -> bool:
    def walk(node: Any) -> bool:
        if isinstance(node, dict):
            for key, val in node.items():
                leaf = str(key).lower()
                if leaf in EMPTY_NOT_PASS_TRUE and val is True:
                    return True
                if leaf == "empty_set_read_as_pass" and val is False:
                    return True
                if walk(val):
                    return True
        elif isinstance(node, list):
            return any(walk(item) for item in node)
        return False

    return walk(doc)


def _truthy_fire(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, str) and value.strip().upper() in {
        "PASS",
        "FIRED",
        "TRUE",
        "YES",
    }:
        return True
    return False


def recorded_both_states(doc: Any) -> dict:
    """Known-present/broken fire AND known-good silence, already on this document."""
    fired_bad = False
    silent_good = False

    def walk(node: Any) -> None:
        nonlocal fired_bad, silent_good
        if isinstance(node, dict):
            blob = " ".join(str(k) for k in node.keys())
            ident = str(node.get("id") or "")
            blob_l = (blob + " " + ident).lower()
            if "known" in blob_l and "present" in blob_l:
                if node.get("fired") is True or node.get("fired_on_bad") is True:
                    fired_bad = True
                elif any(
                    _truthy_fire(v)
                    for v in node.values()
                    if not isinstance(v, (dict, list))
                ):
                    fired_bad = True
            if "known" in blob_l and "broken" in blob_l:
                if node.get("fired") is True or node.get("fired_on_bad") is True:
                    fired_bad = True
                elif any(
                    _truthy_fire(v)
                    for v in node.values()
                    if not isinstance(v, (dict, list))
                ):
                    fired_bad = True
            if node.get("fired_on_bad") is True:
                fired_bad = True
            if node.get("silent_on_good") is True:
                silent_good = True
            if node.get("known_present_run_first") is True and (
                node.get("fired") is True
                or node.get("fired_before_absence_reported") is True
            ):
                fired_bad = True
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(doc)
    controlled = bool(fired_bad and silent_good)
    return {
        "fired_on_bad": fired_bad,
        "silent_on_good": silent_good,
        "known_present": fired_bad,
        "known_broken": fired_bad,
        "controlled": controlled,
    }


def _zero_string(value: str) -> bool:
    return value.strip().lower() in ZERO_STRINGS


def harvest_json_doc(doc: Any, source: Path) -> list[dict]:
    rows: list[dict] = []
    skip_empty_arrays = empty_not_treated_as_pass(doc)
    producer = producer_of(doc, source)
    controls = recorded_both_states(doc)

    def add(json_path: str, claim: str) -> None:
        verdict = "controlled" if controls["controlled"] else "uncontrolled"
        rows.append(
            {
                "id": f"{producer}:{json_path}",
                "kind": "reported-zero",
                "verdict": verdict,
                "source": rel_of(source),
                "producer": producer,
                "claim": claim,
                "json_path": json_path,
                "classification": (
                    "CONTROLLED-ZERO"
                    if verdict == "controlled"
                    else "UNCONTROLLED-ZERO"
                ),
                "control": {
                    "known_present": controls["known_present"],
                    "known_broken": controls["known_broken"],
                    "fired_on_bad": controls["fired_on_bad"],
                    "silent_on_good": controls["silent_on_good"],
                },
            }
        )

    def walk(node: Any, parts: tuple[str, ...]) -> None:
        if path_is_mention(parts):
            return
        if isinstance(node, dict):
            for key, val in node.items():
                walk(val, parts + (str(key),))
            return
        if isinstance(node, list):
            key = parts[-1].lower() if parts else ""
            if key in ZERO_ARRAY_KEYS and len(node) == 0 and not skip_empty_arrays:
                add(".".join(parts), f"{key}=[]")
                return
            for i, item in enumerate(node):
                walk(item, parts + (str(i),))
            return
        if isinstance(node, bool):
            key = parts[-1].lower() if parts else ""
            if key == "clean" and node is True:
                add(".".join(parts), "clean=true")
            return
        if isinstance(node, int):
            key = parts[-1].lower() if parts else ""
            if key in ZERO_COUNT_KEYS and node == 0:
                add(".".join(parts), f"{key}=0")
            return
        if isinstance(node, str):
            key = parts[-1].lower() if parts else ""
            if key in RESULT_KEYS and _zero_string(node):
                if QUOTED_PHRASE_RE.fullmatch(node.strip()):
                    return
                add(".".join(parts), f"{key}={node.strip()[:80]}")

    if isinstance(doc, dict):
        walk(doc, ())
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        if row["json_path"] in seen:
            continue
        seen.add(row["json_path"])
        out.append(row)
    return out


def harvest_markdown(text: str, source: Path) -> tuple[list[dict], int]:
    mentions = len(QUOTED_PHRASE_RE.findall(text))
    stripped = QUOTED_PHRASE_RE.sub(" ", text)
    rows: list[dict] = []
    producer = producer_of({}, source)
    for i, line in enumerate(stripped.splitlines(), 1):
        if not PHRASE_RE.search(line):
            continue
        low = line.strip().lower()
        if "absent" in low or "missing file" in low or "does not exist" in low:
            continue
        if not re.search(
            r"\b(result|verdict|finding|status|outcome|clean)\b", line, re.I
        ) and not re.search(
            r"^\s*(no findings|not found|no issues)\s*$", line, re.I
        ):
            continue
        rows.append(
            {
                "id": f"{producer}:md:{i}",
                "kind": "reported-zero",
                "verdict": "uncontrolled",
                "source": rel_of(source),
                "producer": producer,
                "claim": line.strip()[:160],
                "json_path": f"line:{i}",
                "classification": "UNCONTROLLED-ZERO",
                "control": {
                    "known_present": False,
                    "known_broken": False,
                    "fired_on_bad": False,
                    "silent_on_good": False,
                },
            }
        )
    return rows, mentions


def harvest_file(path: Path) -> tuple[list[dict], int]:
    if path.suffix.lower() == ".json":
        doc = load_json(path)
        if doc is None:
            return [], 0
        text = path.read_text(encoding="utf-8", errors="replace")
        mentions = len(QUOTED_PHRASE_RE.findall(text))
        rows = harvest_json_doc(doc, path)
        harvested = " ".join(r["claim"] for r in rows).lower()
        mention_only = 0
        if mentions and "no findings" not in harvested and "not found" not in harvested:
            mention_only = mentions
        return rows, mention_only
    if path.suffix.lower() in {".md", ".txt"}:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return [], 0
        return harvest_markdown(text, path)
    return [], 0


def iter_live_paths(repo: Path | None = None) -> list[Path]:
    root = repo if repo is not None else REPO
    paths: list[Path] = []
    receipts = root / "command-center" / "receipts"
    if receipts.is_dir():
        for path in sorted(receipts.rglob("*.json")):
            if path.name == "BLD-0028.json":
                continue
            if "BLD-0028" in path.parts:
                continue
            paths.append(path)
    wave = root / "command-center" / "p2-wave"
    if wave.is_dir():
        paths.extend(sorted(wave.glob("P2-*.md")))
        for path in sorted(wave.glob("P2-*.json")):
            name = path.name.upper()
            if name.startswith("P2-BLOCKED"):
                continue
            if "LEFTOVER" in name or "CLOUD-DONE" in name:
                continue
            paths.append(path)
    claim = root / "command-center" / "CLAIM-REGISTRY.json"
    if claim.is_file():
        paths.append(claim)
    return paths


def harvest_paths(paths: Iterable[Path]) -> dict:
    inventory: list[dict] = []
    mentions = 0
    scanned = 0
    for path in paths:
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        scanned += 1
        rows, extra = harvest_file(path)
        mentions += extra
        inventory.extend(rows)
    controlled = [r for r in inventory if r["verdict"] == "controlled"]
    uncontrolled = [r for r in inventory if r["verdict"] == "uncontrolled"]
    requeued: list[dict] = []
    seen_prod: set[str] = set()
    for row in uncontrolled:
        prod = row["producer"]
        if prod in seen_prod:
            continue
        seen_prod.add(prod)
        requeued.append(
            {
                "producer": prod,
                "classification": "UNCONTROLLED-ZERO",
                "reason": (
                    "Published zero has no recorded known-present and "
                    "known-broken (both-states) control on the producing receipt"
                ),
                "source": row["source"],
                "zero_id": row["id"],
            }
        )
    return {
        "inventory": inventory,
        "zeros_harvested": len(inventory),
        "controlled_count": len(controlled),
        "uncontrolled_count": len(uncontrolled),
        "mentioned_not_harvested": mentions,
        "live_files_scanned": scanned,
        "requeued": requeued,
        "uncontrolled_ids": [r["id"] for r in uncontrolled],
        "controlled_ids": [r["id"] for r in controlled],
    }


def harvest_fixture_dir(name: str) -> dict:
    root = FIXTURES / name
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return harvest_paths(files)


harvest_fixture_dir = harvest_fixture_dir


def live_harvest(repo: Path | None = None) -> dict:
    return harvest_paths(iter_live_paths(repo))


def claim_registry_status(repo: Path | None = None) -> str:
    root = repo if repo is not None else REPO
    path = root / "command-center" / "CLAIM-REGISTRY.json"
    if path.is_file() and path.stat().st_size > 0:
        return "present"
    return "ABSENT"


if __name__ == "__main__":
    result = live_harvest()
    print(
        json.dumps(
            {
                "zeros": result["zeros_harvested"],
                "controlled": result["controlled_count"],
                "uncontrolled": result["uncontrolled_count"],
                "mentions": result["mentioned_not_harvested"],
                "scanned": result["live_files_scanned"],
                "uncontrolled_head": result["uncontrolled_ids"][:25],
                "controlled_head": result["controlled_ids"][:25],
            },
            indent=2,
        )
    )
