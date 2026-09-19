#!/usr/bin/env python3
"""Fabric Session Distillery — autonomous session review/sort/distill pipeline.

Stage 1  HARVEST  : consume index-ai-sessions.state.json (incremental catalog of
                    every runtime's sessions) and pick sessions not yet distilled.
Stage 2  SORT     : classify each candidate from its catalog title+snippet
                    (keyword heuristic; categories: coding, research, ops,
                    security, chat, aborted). Only coding/research proceed.
Stage 3  DISTILL  : stream first+last 64 KB of the session file and run fabric's
                    PATTERNS (create_summary + extract_wisdom, read from
                    ~/.config/fabric/patterns/<name>/system.md) through a Sonnet
                    backend. DISTILLERY_BACKEND selects:
                      claude  (default) - Claude Max subscription via headless
                                          `claude -p --model sonnet` (no keys)
                      bedrock           - owner SSO via `aws bedrock-runtime
                                          converse` (needs `aws sso login`;
                                          AWS_PROFILE=bolt-datascience;
                                          per-token cost to the employer account)
Stage 4  PERSIST  : one markdown artifact per distilled session under
                    ~/.agents/distillery/YYYY-MM/ + a regenerated INDEX.md.
                    NOTHING goes into the basic-memory vault (vault-bloat
                    lesson, BASIC-MEMORY-RELIABILITY_2026-08-27); the INDEX is
                    the searchable surface, agents promote findings manually.

Credentials policy: no literals anywhere. Backends ride existing authenticated
sessions (claude CLI login / AWS SSO chain) exactly as-is.

Usage:
  python fabric_session_distillery.py [--limit N] [--dry-run] [--no-llm]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
INDEXER_STATE = HOME / ".agents" / "scripts" / "index-ai-sessions.state.json"
STATE_PATH = HOME / ".agents" / "scripts" / "fabric-distillery.state.json"
OUT_ROOT = HOME / ".agents" / "distillery"
INDEX_PATH = OUT_ROOT / "INDEX.md"
PATTERNS_DIR = HOME / ".config" / "fabric" / "patterns"
BACKEND = os.environ.get("DISTILLERY_BACKEND", "claude").strip().lower()
BEDROCK_MODEL = os.environ.get(
    "DISTILLERY_BEDROCK_MODEL", "eu.anthropic.claude-sonnet-4-5-20250929-v1-0"
)
CLAUDE_MODEL = os.environ.get("DISTILLERY_CLAUDE_MODEL", "sonnet")
HEAD_BYTES = 64 * 1024
TAIL_BYTES = 64 * 1024
MAX_CONTENT = 24_000
LLM_TIMEOUT = 240
CATEGORIES = ("coding", "research", "ops", "security", "chat", "aborted")
DISTILL_CATEGORIES = ("coding", "research")

SECRET_RE = re.compile(
    r"(?i)(sk-[A-Za-z0-9]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|"
    r"AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}|xox[bap]-[A-Za-z0-9-]{10,}|"
    r"Bearer\s+[A-Za-z0-9._-]{24,})"
)


def redact(text: str) -> str:
    return SECRET_RE.sub("[REDACTED]", text)


def _pattern_system(pattern: str) -> str:
    try:
        return (PATTERNS_DIR / pattern / "system.md").read_text(
            encoding="utf-8", errors="replace"
        )[:16_000]
    except OSError:
        return ""


def _run_claude(system: str, content: str) -> str:
    proc = subprocess.run(
        ["claude", "-p", content[:MAX_CONTENT], "--model", CLAUDE_MODEL,
         "--system-prompt", system],
        capture_output=True, text=True, timeout=LLM_TIMEOUT,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def _run_bedrock(system: str, content: str) -> str:
    payload = json.dumps({
        "modelId": BEDROCK_MODEL,
        "system": [{"text": system}],
        "messages": [{"role": "user", "content": [
            {"text": content[:MAX_CONTENT]}
        ]}],
        "inferenceConfig": {"maxTokens": 2048, "temperature": 0.3},
    })
    proc = subprocess.run(
        ["aws", "bedrock-runtime", "converse", "--cli-binary-format", "raw-in-base64-out",
         "--payload", payload],
        capture_output=True, text=True, timeout=LLM_TIMEOUT,
        encoding="utf-8", errors="replace",
        env={**os.environ, "AWS_PROFILE": os.environ.get("AWS_PROFILE", "bolt-datascience")},
    )
    if proc.returncode != 0:
        return ""
    try:
        data = json.loads(proc.stdout)
        return (data.get("output", {}).get("message", {}).get("content", [{}])[0]
                .get("text", "")).strip()
    except (KeyError, IndexError, ValueError):
        return ""


def run_llm(pattern: str, content: str) -> str:
    system = _pattern_system(pattern)
    if not system or not content:
        return ""
    if BACKEND == "bedrock":
        return _run_bedrock(system, content)
    return _run_claude(system, content)


def classify(record: dict) -> str:
    title = (record.get("title") or "").lower()
    snippet = ((record.get("first") or "") + " " + (record.get("last") or ""))[:300].lower()
    blob = f"{title} {snippet}"
    if any(k in blob for k in ("compacted", "conversation compacted")):
        return "chat"
    if any(k in blob for k in ("failed:", "error", "aborted", "crash")):
        return "aborted"
    if any(k in blob for k in ("mcp", "config", "registry", "sync", "deploy", "harness", "setup", "wiring")):
        return "ops"
    if any(k in blob for k in ("exploit", "cve", "payload", "recon", "pentest", "phish", "malware", "reverse")):
        return "security"
    if any(k in blob for k in ("research", "paper", "review", "study", "literature", "doi")):
        return "research"
    if any(k in blob for k in ("code", "coding", "refactor", "bug", "fix", "test", "build", "implement", "python", "typescript", "repo", "api", "skill", "script")):
        return "coding"
    return "chat"


def stream_head_tail(path: Path) -> str:
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            head = fh.read(HEAD_BYTES)
            fh.seek(max(0, size - TAIL_BYTES))
            tail = fh.read(TAIL_BYTES)
        return redact((head + b"\n...\n" + tail).decode("utf-8", "replace"))
    except OSError:
        return ""


def slugify(value: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug[:limit] or "session"


def regenerate_index() -> None:
    rows = []
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        for path, info in state.items():
            if info.get("artifact"):
                rows.append((info["artifact"], path, info.get("category", "?")))
    lines = [
        "# Fabric Session Distillery — index",
        "",
        f"_regenerated {datetime.now().isoformat(timespec='seconds')}; backend={BACKEND}_",
        "",
        "| artifact | category | source |",
        "|---|---|---|",
    ]
    for artifact, src, cat in sorted(rows, reverse=True):
        lines.append(
            f"| [{Path(artifact).name}]({Path(artifact).as_posix()}) | {cat} | `{src}` |"
        )
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    if not INDEXER_STATE.exists():
        print("FAILED:fabric-distillery indexer state missing - run index-ai-sessions.py first")
        return 1
    catalog = json.loads(INDEXER_STATE.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8")) if STATE_PATH.exists() else {}

    month_dir = OUT_ROOT / datetime.now().strftime("%Y-%m")
    counts = {c: 0 for c in CATEGORIES}
    distilled, skipped_gone, errors = 0, 0, 0

    candidates = []
    for path, info in catalog.items():
        rec = info.get("record", {})
        if not rec.get("title"):
            continue
        sig = str(info.get("mtime"))
        if state.get(path, {}).get("mtime") == sig and state.get(path, {}).get("stage") == "done":
            continue
        path_obj = Path(path)
        if not path_obj.exists():
            skipped_gone += 1
            state[path] = {"mtime": sig, "stage": "gone"}
            continue
        cat = classify(rec)
        counts[cat] += 1
        state[path] = {"mtime": sig, "stage": "classified", "category": cat}
        if cat in DISTILL_CATEGORIES:
            candidates.append((path_obj, rec, cat))

    candidates.sort(key=lambda c: c[1].get("date") or "", reverse=True)
    if args.limit > 0:
        candidates = candidates[: args.limit]

    for path_obj, rec, cat in candidates:
        if args.dry_run:
            print(f"would-distill [{cat}] {rec.get('date')} {rec.get('title')}")
            continue
        content = stream_head_tail(path_obj)
        if not content:
            state[str(path_obj)]["stage"] = "empty"
            errors += 1
            continue
        if args.no_llm:
            summary = wisdom = "(skipped: --no-llm)"
        else:
            summary = run_llm("create_summary", content)
            wisdom = run_llm("extract_wisdom", content)
        date = rec.get("date") or datetime.now().strftime("%Y-%m-%d %H:%M")
        runtime = rec.get("runtime") or "unknown"
        title = rec.get("title") or "untitled"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        artifact = month_dir / f"{stamp}-{runtime}-{slugify(title)}.md"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(
            f"# {title}\n\n"
            f"- runtime: {runtime}\n- session date: {date}\n- category: {cat}\n"
            f"- source: `{path_obj}`\n- distilled: {datetime.now().isoformat(timespec='seconds')}\n"
            f"- backend: {BACKEND}\n\n"
            f"## create_summary\n\n{summary or '(backend returned nothing - fail-open)'}\n\n"
            f"## extract_wisdom\n\n{wisdom or '(backend returned nothing - fail-open)'}\n",
            encoding="utf-8",
        )
        state[str(path_obj)].update(
            stage="done", artifact=str(artifact),
            summary_len=len(summary), wisdom_len=len(wisdom),
        )
        distilled += 1

    if not args.dry_run:
        tmp = STATE_PATH.with_suffix(".json.tmp-distillery")
        tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
        tmp.replace(STATE_PATH)
        regenerate_index()

    print(
        f"SUCCESS:fabric-distillery backend={BACKEND} "
        f"classified_new={sum(counts.values())} "
        f"by_cat={ {k: v for k, v in counts.items() if v} } distilled={distilled} "
        f"gone={skipped_gone} errors={errors} dry_run={str(args.dry_run).lower()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
