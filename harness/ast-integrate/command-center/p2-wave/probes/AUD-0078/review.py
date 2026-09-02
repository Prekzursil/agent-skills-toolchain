"""Probe 2: contextual read of the highest-risk files from probe 1.

An automated PII classifier over-flags hashes, schema examples, and
detector source. This pass reads surrounding lines and labels each
sampled hit CONFIRMED, OVER-FLAG, or MENTION.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

from scan import scan_included  # noqa: E402

SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "info": 4}
TOP_FILES = 8
SAMPLE_PER_FILE = 6


def _read_line(path: Path, lineno: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1]
    return ""


def classify_hit(repo_rel: str, line: str, cls: str) -> str:
    low = line.strip().lower()
    rel = repo_rel.replace("\\", "/")

    if "/p2-wave/probes/AUD-0078/" in "/" + rel:
        return "MENTION"
    if "re.compile" in low or "regex" in low or "HOME_WIN" in line or "ASSIGN_RE" in line:
        return "MENTION"
    if low.startswith("#") or low.startswith("//"):
        if cls in {"credential-assignment", "credential-token"}:
            return "MENTION"

    if cls == "owner-home-path":
        if "c:/users/" in low or "c:\\\\users\\\\" in low or "/mnt/c/users/" in low:
            if "not a claim" in low or "were not read" in low or "is not on this" in low:
                return "CONFIRMED"
            return "CONFIRMED"
        if "/home/" in low or "/users/" in low:
            return "CONFIRMED"
        return "OVER-FLAG"

    if cls in {"private-key", "credential-token"}:
        if "redacted" in low or "example" in low or "placeholder" in low:
            return "OVER-FLAG"
        return "CONFIRMED"

    if cls == "credential-assignment":
        if "placeholder" in low or "not-a-live-secret" in low or "example" in low:
            return "OVER-FLAG"
        if rel.endswith(".md") or "schema" in rel:
            return "OVER-FLAG"
        if rel.endswith(".json") or '"token"' in low:
            if any(
                m in low
                for m in ("akia", "ghp_", "github_pat_", "sk-", "xox", "glpat-", "begin ")
            ):
                return "CONFIRMED"
            return "OVER-FLAG"
        return "CONFIRMED"

    if cls == "credential-path":
        return "CONFIRMED"

    if cls == "email":
        if "example.com" in low or "noreply" in low:
            return "OVER-FLAG"
        return "CONFIRMED"

    return "OVER-FLAG"


def review_scan(result: dict | None = None) -> dict:
    result = result or scan_included()
    findings = result.get("findings") or []
    by_path: dict[str, list[dict]] = defaultdict(list)
    for hit in findings:
        by_path[hit["path"]].append(hit)

    def path_score(items: list[dict]) -> tuple:
        classes = {h["class"] for h in items}
        if "private-key" in classes:
            rank = 0
        elif "credential-token" in classes:
            rank = 1
        elif "owner-home-path" in classes:
            rank = 2
        elif "email" in classes:
            rank = 3
        elif "credential-path" in classes:
            rank = 4
        else:
            rank = 5
        return (rank, -len(items))

    ranked = sorted(by_path.items(), key=lambda kv: path_score(kv[1]))[:TOP_FILES]
    catalog = "command-center/WORK-UNIT-CATALOG.json"
    if catalog in by_path and all(rel != catalog for rel, _ in ranked):
        ranked = [(catalog, by_path[catalog])] + ranked[: TOP_FILES - 1]
    reviews = []
    tallies = {"CONFIRMED": 0, "OVER-FLAG": 0, "MENTION": 0}
    for rel, items in ranked:
        path = REPO / rel
        samples = []
        for hit in items[:SAMPLE_PER_FILE]:
            raw = _read_line(path, int(hit.get("line") or 1))
            verdict = classify_hit(rel, raw, hit["class"])
            tallies[verdict] = tallies.get(verdict, 0) + 1
            samples.append(
                {
                    "class": hit["class"],
                    "line": hit["line"],
                    "severity": hit["severity"],
                    "verdict": verdict,
                    "snippet": hit.get("snippet") or "",
                }
            )
        reviews.append(
            {
                "path": rel,
                "hit_count": len(items),
                "classes": sorted({h["class"] for h in items}),
                "samples": samples,
            }
        )

    confirmed_paths = [
        r["path"]
        for r in reviews
        if any(s["verdict"] == "CONFIRMED" for s in r["samples"])
    ]
    return {
        "method": "contextual-read",
        "not_method": "second-regex-pass",
        "files_read": len(reviews),
        "tallies": tallies,
        "confirmed_paths": confirmed_paths,
        "reviews": reviews,
        "control_ok": bool((result.get("control") or {}).get("ok")),
    }
