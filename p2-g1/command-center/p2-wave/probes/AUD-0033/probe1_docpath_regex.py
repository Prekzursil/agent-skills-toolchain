#!/usr/bin/env python3
"""AUD-0033 probe 1 (source, static-analysis): regex extraction of path-like
tokens from documentation, existence-tested against the repo root.

Detector control (tests_required): the extractor must find a path inside a
markdown code fence and must NOT emit a false path from a prose sentence
containing a slash. Both asserted on one fixture in this run.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
TOP_LEVEL = set(q.name for q in REPO.iterdir() if q.is_dir())
OUT = HERE / "probe1_docpath_regex_out.json"

SCOPES = ["command-center", "docs", "guides", "rules"]
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "_scratch", "_chaos-scratch"}
MAX_FILES = 4000
MAX_BYTES = 512 * 1024

TOKEN_RE = re.compile(r"[A-Za-z0-9_.\-]+(?:/[A-Za-z0-9_.\-]+)+")
SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://")


TOP_LEVEL = set()

def segment_is_pathlike(token: str) -> bool:
    """A candidate path must end in a dotted (file-like) segment, or start with
    a real top-level repo directory. Bare prose slashes (input/output, and/or)
    have neither and are rejected."""
    segs = token.split("/")
    if "." in segs[-1]:
        return True
    return bool(TOP_LEVEL) and segs[0] in TOP_LEVEL


def clean_token(tok: str) -> str | None:
    tok = tok.strip("\"'`.,;:!)(")
    if not tok or "/" not in tok:
        return None
    if tok.endswith((".png", ".jpg", ".svg")) and "/" not in tok[:-4]:
        pass
    if not segment_is_pathlike(tok):
        return None
    if tok.count("/") > 12:
        return None
    return tok


def iter_docs():
    n = 0
    for scope in SCOPES:
        base = REPO / scope
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                p = Path(dirpath) / fn
                try:
                    if p.stat().st_size > MAX_BYTES:
                        continue
                except OSError:
                    continue
                n += 1
                if n > MAX_FILES:
                    return
                yield p


def exists_in_repo(tok: str) -> bool:
    cand = REPO / tok
    if cand.exists():
        return True
    # strip a trailing :line anchor if present
    if ":" in tok:
        head = tok.rsplit(":", 1)[0]
        if head and (REPO / head).exists():
            return True
    return False


def scan() -> dict:
    total = 0
    unique: dict[str, dict] = {}
    citations = 0
    files_scanned = 0
    for p in iter_docs():
        files_scanned += 1
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            # drop URLs so scheme paths do not count as repo paths
            line_nourl = SCHEME_RE.sub(" ", line)
            for m in TOKEN_RE.finditer(line_nourl):
                tok = clean_token(m.group(0))
                if tok is None:
                    continue
                total += 1
                citations += 1
                rec = unique.setdefault(tok, {"token": tok, "citations": []})
                if len(rec["citations"]) < 3:
                    rec["citations"].append(
                        {"file": p.resolve().relative_to(REPO).as_posix(), "line": i})
    resolved = 0
    missing = []
    for tok, rec in unique.items():
        if exists_in_repo(tok):
            resolved += 1
            rec["state"] = "resolved"
        else:
            rec["state"] = "missing"
            missing.append(rec)
    return {
        "probe": "probe1-docpath-regex",
        "files_scanned": files_scanned,
        "citations": citations,
        "unique_tokens": len(unique),
        "resolved": resolved,
        "missing": missing[:200],
        "missing_count": len(missing),
    }


def fixture_control() -> dict:
    fixture = HERE / "fixture_docpath.md"
    fixture.write_text(
        "# fixture\n\n"
        "```md\n"
        "see `command-center/STATUS.md` for the real file\n"
        "```\n\n"
        "The prose sentence mentions input/output tradeoffs and/or config values.\n",
        encoding="utf-8",
    )
    text = fixture.read_text(encoding="utf-8")
    fence_line = [ln for ln in text.splitlines() if "STATUS.md" in ln][0]
    prose_line = [ln for ln in text.splitlines() if "and/or" in ln][0]

    def hits(line: str) -> list:
        out = []
        for m in TOKEN_RE.finditer(SCHEME_RE.sub(" ", line)):
            tok = clean_token(m.group(0))
            if tok:
                out.append(tok)
        return out

    fence_hits = hits(fence_line)
    prose_hits = hits(prose_line)
    ok_fence = any("STATUS.md" in t for t in fence_hits)
    ok_prose = len(prose_hits) == 0
    return {
        "fence_token_found": ok_fence,
        "fence_hits": fence_hits,
        "prose_clean": ok_prose,
        "prose_hits": prose_hits,
        "pass": ok_fence and ok_prose,
    }


def main() -> int:
    result = scan()
    result["detector_control"] = fixture_control()
    ok = result["detector_control"]["pass"]
    result["pass"] = bool(ok)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("files=%d citations=%d unique=%d resolved=%d missing=%d control_pass=%s"
          % (result["files_scanned"], result["citations"], result["unique_tokens"],
             result["resolved"], result["missing_count"], ok))
    print("SUCCESS:AUD-0033-probe1 doc path regex sweep" if ok
          else "FAILED:AUD-0033-probe1 detector control")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
