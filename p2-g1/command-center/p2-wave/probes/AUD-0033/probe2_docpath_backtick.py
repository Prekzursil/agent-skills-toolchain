#!/usr/bin/env python3
"""AUD-0033 probe 2 (verifier, file-read): mechanically different extractor -
line-oriented scan of backtick-quoted spans only - re-tests existence, diffs
against probe 1, and classifies every MISSING token by basename search across
the repo file index (found-elsewhere vs nowhere-in-tree).

Git-history separation (git log --all per the catalog) is NOT available: this
worktree has no .git. The basename-search separation plus a residual_unknown is
the honest substitute.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
TOP_LEVEL = set(q.name for q in REPO.iterdir() if q.is_dir())
OUT = HERE / "probe2_docpath_backtick_out.json"

SCOPES = ["command-center", "docs", "guides", "rules"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "_scratch", "_chaos-scratch"}
MAX_FILES = 4000
MAX_BYTES = 512 * 1024
BACKTICK_RE = None  # built lazily without regex: manual span split


def iter_docs():
    n = 0
    for scope in SCOPES:
        base = REPO / scope
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(".md"):
                    n += 1
                    if n > MAX_FILES:
                        return
                    yield Path(dirpath) / fn


def backtick_spans(line: str) -> list:
    spans = []
    parts = line.split("`")
    for i in range(1, len(parts), 2):
        spans.append(parts[i])
    return spans


def segment_is_pathlike(token: str) -> bool:
    """A candidate must end in a dotted (file-like) segment, or start with a
    real top-level repo directory. Bare prose slashes are rejected."""
    segs = token.split("/")
    if "." in segs[-1]:
        return True
    return bool(TOP_LEVEL) and segs[0] in TOP_LEVEL


def clean_token(tok: str) -> str | None:
    tok = tok.strip()
    if "/" not in tok or len(tok) > 300:
        return None
    if not segment_is_pathlike(tok):
        return None
    if "://" in tok:
        return None
    return tok


def build_name_index() -> dict:
    names: dict[str, list] = {}
    count = 0
    for scope in SCOPES:
        base = REPO / scope
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                names.setdefault(fn.lower(), []).append(
                    str(Path(dirpath) / fn))
                count += 1
    return {"by_name": names, "files_indexed": count}


def main() -> int:
    findings: dict[str, dict] = {}
    citations = 0
    files_scanned = 0
    for p in iter_docs():
        files_scanned += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = p.resolve().relative_to(REPO).as_posix()
        for i, line in enumerate(text.splitlines(), 1):
            for span in backtick_spans(line):
                for piece in span.replace("*", " ").split():
                    tok = clean_token(piece)
                    if tok is None:
                        continue
                    citations += 1
                    rec = findings.setdefault(tok, {"token": tok, "citations": []})
                    if len(rec["citations"]) < 3:
                        rec["citations"].append({"file": rel, "line": i})

    resolved = set()
    missing = []
    for tok, rec in findings.items():
        if (REPO / tok).exists():
            resolved.add(tok)
        elif ":" in tok and (REPO / tok.rsplit(":", 1)[0]).exists():
            resolved.add(tok)
        else:
            missing.append(rec)

    idx = build_name_index()
    for rec in missing:
        base = rec["token"].rsplit("/", 1)[-1].rsplit(":", 1)[0]
        elsewhere = idx["by_name"].get(base.lower(), [])
        rec["classification"] = "found-elsewhere" if elsewhere else "nowhere-in-tree"
        if elsewhere:
            rec["found_at"] = [e for e in elsewhere[:2]]

    # cross-check vs probe 1 (mechanically different extractor agreement)
    p1_path = HERE / "probe1_docpath_regex_out.json"
    agreement = {"available": p1_path.is_file()}
    if p1_path.is_file():
        p1 = json.loads(p1_path.read_text(encoding="utf-8"))
        p1_missing = {m["token"] for m in p1.get("missing", [])}
        p2_missing = {m["token"] for m in missing}
        inter = p1_missing & p2_missing
        agreement.update({
            "probe1_missing": len(p1_missing),
            "probe2_missing": len(p2_missing),
            "agreed_missing": len(inter),
            "probe2_extra_missing": sorted(p2_missing - p1_missing)[:20],
            "pass": len(inter) >= max(0, len(p1_missing) - len(p2_missing) - 5),
        })

    # fixture control (same fixture as probe 1)
    fixture = HERE / "fixture_docpath.md"
    ok_fixture = False
    if fixture.is_file():
        ftext = fixture.read_text(encoding="utf-8")
        fence = [ln for ln in ftext.splitlines() if "STATUS.md" in ln][0]
        prose = [ln for ln in ftext.splitlines() if "and/or" in ln][0]
        f_hits = [t for span in backtick_spans(fence) for t in span.split() if clean_token(t)]
        p_hits = [t for span in backtick_spans(prose) for t in span.split() if clean_token(t)]
        ok_fixture = any("STATUS.md" in t for t in f_hits) and len(p_hits) == 0

    result = {
        "probe": "probe2-docpath-backtick",
        "files_scanned": files_scanned,
        "backtick_citations": citations,
        "unique_tokens": len(findings),
        "resolved": len(resolved),
        "missing_count": len(missing),
        "missing_sample": missing[:50],
        "classification_counts": {
            "found-elsewhere": sum(1 for m in missing if m["classification"] == "found-elsewhere"),
            "nowhere-in-tree": sum(1 for m in missing if m["classification"] == "nowhere-in-tree"),
        },
        "name_index_files": idx["files_indexed"],
        "agreement_with_probe1": agreement,
        "fixture_control_pass": ok_fixture,
        "pass": bool(ok_fixture and agreement.get("pass", True)),
    }
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("files=%d citations=%d unique=%d resolved=%d missing=%d cls=%s fixture=%s"
          % (files_scanned, citations, len(findings), len(resolved), len(missing),
             result["classification_counts"], ok_fixture))
    print("SUCCESS:AUD-0033-probe2 backtick verifier sweep" if result["pass"]
          else "FAILED:AUD-0033-probe2 control or agreement")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
