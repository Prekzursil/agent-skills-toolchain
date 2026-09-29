#!/usr/bin/env python3
"""Backfill 2026-09-23..2026-09-29 knowledge from .remember day spools into the
basic-memory vault, idempotently, with three dedup gates and a two-signal verify.

DEFAULT IS --plan. Nothing is written without --apply.

Transport: the `basic-memory` CLI's `tool write-note`, content on STDIN.
  - tool.py: write-note reads stdin when --content is omitted, so the Windows
    32,767-char argv cap and shell quoting are both out of play.
  - tool.py: the CLI imports the MCP tool IN-PROCESS over an ASGI transport.
    It binds NO port, opens no connection to :18765 and spawns no MCP server,
    so it is not a stdio spawn and not a :18765 bind (memory-contract.md:11-13),
    and it writes THROUGH write_note so it satisfies the G-81 writer lock
    (memory-contract.md:67).
  - Precedent: the estate's own production flusher (harness/modules.py:500-525)
    already shells this exact CLI form from the hook path.
  - --local is passed on every invocation so routing cannot depend on config
    state (config.json carries cloud_client_id/cloud_host; mode is "local" and
    cloud_api_key is null today, but the flag removes the ambiguity).

Never overwrites: --overwrite is never passed, so write_note returns
NOTE_ALREADY_EXISTS / exit 1 on a collision, which this script maps to a SKIP,
never a FAILED and never a clobber (memory-contract.md:56-63, supersede-not-delete).

Exit contract (AGENTS-RUNTIME 4):
  plan : SUCCESS:backfill-plan ...            (non-zero only if preflight fails)
  apply: SUCCESS:backfill-remember-to-vault ... | FAILED:... with the reason counts.
         apply exits NON-ZERO on any FAILED, CONFLICT, BLOCKED-SECRET, or
         un-actioned SUPERSEDE-REQUIRED row, so a green run cannot hide
         knowledge fragmentation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KIT_ROOT = Path(__file__).resolve().parent
AGENTS_ROOT = KIT_ROOT.parents[1]  # .../.agents
DEFAULT_MANIFEST = KIT_ROOT / "manifest.json"
DEFAULT_NOTES_DIR = KIT_ROOT / "notes"

# Ledger default is PINNED and DECLARED: it lives under .agents/state/, which
# `.gitignore:17:state/` ignores, so a per-run runtime artifact never enters the
# orchestrator's end-of-run commit. G1 correctness therefore depends on a
# gitignored local file, NOT on a committed one - that is the deliberate choice:
# a re-run after a repo restore re-checks G2/G3 against the live vault instead of
# trusting a stale committed ledger.
DEFAULT_LEDGER = (
    AGENTS_ROOT / "state" / "harness" / "backfill-remember-to-vault" / "ledger.jsonl"
)
DEFAULT_SUPERSEDE_QUEUE = DEFAULT_LEDGER.parent / "supersede-queue.json"
DEFAULT_SUPERSEDE_ACK = DEFAULT_LEDGER.parent / "supersede-actioned.jsonl"

BM_CONFIG = Path.home() / ".basic-memory" / "config.json"
AUTO_MEMORY_DIR = (
    Path.home() / ".claude" / "projects" / "C--Users-prekzursil" / "memory"
)

MARKER_RE = re.compile(
    r"^<!--\s*backfill-id:\s*(?P<id>[A-Za-z0-9._-]+)\s+src:\s*(?P<src>.*?)"
    r"\s+sha256:\s*(?P<sha12>[0-9a-f]{12})\s*-->\s*$"
)
OBSERVATION_RE = re.compile(
    r"^- \[(?:decision|fact|requirement|preference|bug)\]", re.MULTILINE
)
WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
DAEMON_PORT = 18765
LOCK_HINT = "database is locked"

# Relations that create a supersede obligation. "extends" does not: two notes
# about adjacent subjects are fine, two status:active notes asserting the same
# subject are not.
SUPERSEDE_RELATIONS = {"restates", "corrects"}


# --------------------------------------------------------------------------- io


def read_text_lf(path: Path) -> str:
    """Read a file and normalise line endings to LF.

    Windows CRLF is the difference between a stable digest and a mismatch that
    looks like corruption (AGENTS-RUNTIME 11).
    """
    raw = path.read_bytes()
    return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def split_body_marker(text: str) -> tuple[str, str | None]:
    """Return (body_without_marker, marker_line or None).

    The marker is the LAST non-empty line when it matches MARKER_RE.
    """
    lines = text.split("\n")
    idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            idx = i
            break
    if idx is None:
        return text, None
    if MARKER_RE.match(lines[idx].strip()):
        return "\n".join(lines[:idx]), lines[idx].strip()
    return text, None


def body_sha256(body: str) -> str:
    """Digest span, stated explicitly so the design is not circular.

    Hash = sha256 over the UTF-8 bytes of the body with LF line endings and
    trailing whitespace stripped, EXCLUDING the trailing marker line. The marker
    embeds the first 12 hex of this digest, so the marker is never inside its own
    input.
    """
    return hashlib.sha256(body.rstrip().encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


# ------------------------------------------------------------------ resolution


def resolve_vault(project: str, override: str | None) -> tuple[Path | None, str]:
    """Resolve the vault root ONCE. Never hardcoded.

    RecallModule still defaults vault_root to the stale "D:/basic-memory" while
    config.json says C:\\drive-d\\basic-memory, so a hardcoded path here would be
    a second place to get it wrong.
    """
    if override:
        return Path(override), f"--vault {override}"
    cfg = load_json(BM_CONFIG, {}) or {}
    raw = ((cfg.get("projects") or {}).get(project) or {}).get("path")
    if not raw:
        return None, f"{BM_CONFIG} has no projects.{project}.path"
    return Path(raw), f"{BM_CONFIG} projects.{project}.path"


def resolve_cli(override: str | None) -> str | None:
    cand = override or os.environ.get("BASIC_MEMORY_CLI") or "basic-memory"
    if os.sep in cand or "/" in cand:
        return cand if Path(cand).exists() else None
    return shutil.which(cand)


def daemon_listening(port: int = DAEMON_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------- ledger


def ledger_records(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def ledger_append(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def ack_keys(path: Path) -> set[str]:
    return {
        f"{r.get('id')}|{r.get('prior_key')}"
        for r in ledger_records(path)
        if r.get("id") and r.get("prior_key")
    }


# ------------------------------------------------------------------------- cli


def run_cli(
    cli: str, argv: list[str], stdin_text: str | None, timeout: int
) -> tuple[int, str, str]:
    proc = subprocess.run(
        [cli, *argv],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def parse_json_blob(text: str) -> dict[str, Any] | None:
    """Pull the first JSON object out of CLI stdout.

    Exit codes are NOT usable as the verify signal: read-note's own source says a
    genuine not-found returns null fields with no `error` key and still exits 0.
    So every signal here is parsed from the payload, never inferred from status.
    """
    text = text.strip()
    if not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except Exception:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def cli_with_retry(
    cli: str, argv: list[str], stdin_text: str | None, timeout: int
) -> tuple[int, str, str, int]:
    """One retry, only on 'database is locked'. Never a second retry (AGENTS 4b)."""
    calls = 0
    rc, out, err = run_cli(cli, argv, stdin_text, timeout)
    calls += 1
    if LOCK_HINT in (out + err).lower():
        time.sleep(2.0)
        rc, out, err = run_cli(cli, argv, stdin_text, timeout)
        calls += 1
    return rc, out, err, calls


# ------------------------------------------------------------- marker probing


def marker_token(note_id: str) -> str:
    return f"backfill-id: {note_id} "


def glob_marker(folder_dir: Path, note_id: str) -> list[Path]:
    """PRIMARY on-disk probe: glob the target folder for the immutable marker.

    The predicted <vault>/<folder>/<title>.md path is only a HINT. A wrong
    prediction would otherwise produce a spurious FAILED on a note that WAS
    written, and the only remaining net would be G2 on a later re-run.
    """
    hits: list[Path] = []
    if not folder_dir.is_dir():
        return hits
    token = marker_token(note_id)
    for path in sorted(folder_dir.glob("*.md")):
        try:
            if token in path.read_text(encoding="utf-8", errors="replace"):
                hits.append(path)
        except OSError:
            continue
    return hits


def folder_md_files(folder_dir: Path) -> list[Path]:
    return sorted(folder_dir.glob("*.md")) if folder_dir.is_dir() else []


# ------------------------------------------------------------------ preflight


class Note:
    __slots__ = (
        "id",
        "title",
        "folder",
        "type",
        "tags",
        "path",
        "body",
        "marker",
        "sha256",
        "content",
        "source_slice",
        "restates",
        "blocked_secret",
    )

    def __init__(self, spec: dict[str, Any], notes_dir: Path):
        self.id = str(spec["id"])
        self.title = str(spec["title"])
        self.folder = str(spec["folder"])
        self.type = str(spec.get("type") or "note")
        self.tags = list(spec.get("tags") or [])
        self.path = notes_dir / Path(str(spec["content_file"])).name
        self.source_slice = str(spec.get("source_slice") or "")
        self.restates = list(spec.get("restates") or [])
        self.body = ""
        self.marker = ""
        self.sha256 = ""
        self.content = ""
        self.blocked_secret = False


def preflight(args: argparse.Namespace) -> tuple[list[Note], list[str], dict[str, Any]]:
    """Zero writes. Returns (notes, fatal_problems, info)."""
    fatal: list[str] = []
    info: dict[str, Any] = {}

    manifest = load_json(Path(args.manifest))
    if not isinstance(manifest, dict) or not manifest.get("notes"):
        return [], [f"manifest unreadable or empty: {args.manifest}"], info

    notes_dir = Path(args.notes_dir)
    selected = set(args.only or [])
    notes: list[Note] = []

    try:
        sys.path.insert(0, str(AGENTS_ROOT))
        from harness.redaction import contains_secret  # type: ignore
    except Exception as exc:  # pragma: no cover - import guard
        return [], [f"cannot import harness.redaction.contains_secret: {exc!r}"], info

    for spec in manifest["notes"]:
        note = Note(spec, notes_dir)
        if selected and note.id not in selected:
            continue
        if not note.path.exists():
            fatal.append(f"{note.id} content file missing: {note.path}")
            continue
        text = read_text_lf(note.path)
        body, marker = split_body_marker(text)
        if marker is None:
            fatal.append(f"{note.id} has no trailing backfill-id marker (run --seal)")
            continue
        m = MARKER_RE.match(marker)
        if not m or m.group("id") != note.id:
            fatal.append(f"{note.id} marker id mismatch: {marker}")
            continue
        digest = body_sha256(body)
        declared = spec.get("sha256")
        if not declared:
            fatal.append(f"{note.id} manifest sha256 is null (run --seal)")
            continue
        if digest != declared:
            fatal.append(
                f"{note.id} sha256-mismatch body={digest[:12]} manifest={str(declared)[:12]}"
            )
            continue
        if m.group("sha12") != digest[:12]:
            fatal.append(
                f"{note.id} sha256-mismatch marker={m.group('sha12')} body={digest[:12]}"
            )
            continue
        if not OBSERVATION_RE.search(body):
            fatal.append(f"{note.id} has no '- [decision]/[fact]' observation line")
            continue
        if not WIKILINK_RE.search(body):
            fatal.append(f"{note.id} has no [[wikilink]] (memory-contract.md:50)")
            continue
        note.body, note.marker, note.sha256 = body, marker, digest
        note.content = body.rstrip() + "\n" + marker + "\n"
        # Deliberately LOUDER than modules.py:498-499, which returns False
        # silently on a trip: a silently dropped note is indistinguishable from a
        # note nobody wrote.
        note.blocked_secret = bool(
            contains_secret(note.title) or contains_secret(note.content)
        )
        notes.append(note)

    if selected:
        missing = selected - {n.id for n in notes}
        for mid in sorted(missing):
            if not any(mid in f for f in fatal):
                fatal.append(f"--only {mid} not present in manifest")

    vault, vault_src = resolve_vault(args.project, args.vault)
    info["vault"] = vault
    info["vault_source"] = vault_src
    if vault is None:
        fatal.append(f"cannot resolve vault: {vault_src}")
    elif not vault.is_dir():
        fatal.append(f"vault path does not exist: {vault}")

    cli = resolve_cli(args.cli)
    info["cli"] = cli
    if cli is None:
        fatal.append("cli-not-found")

    info["daemon_up"] = daemon_listening()
    return notes, fatal, info


# ---------------------------------------------------------- supersede report


def tokenize(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9_.-]{3,}", text.lower())}


# Promotion bar for a DISCOVERED candidate, CALIBRATED on this corpus (746 priors,
# measured 2026-09-29) - not guessed. Absolute jaccard alone does not separate: a
# true match scored 0.079 (note 13) while a non-match scored 0.089 (note 07). What
# separates is a standout: a high score AND a clear gap to the runner-up. Measured
# declared-true-match scores 0.079-0.196 with ratios 1.06-2.31; measured no-real-prior
# notes sat at 0.070-0.137 with ratios 1.02-1.10.
#   An earlier 0.22 threshold could NEVER fire (corpus max was 0.196) - it was an
#   inert control that made the discovery half silent while looking diligent
#   (single-signal-verification.md 3c). Containment (|shared|/min) was tested and is
#   WORSE: it ranks long generic notes above the true match.
# This bar is a TRIAGE aid, not a classifier. Declared rows remain the authoritative
# set; candidates are always REPORTED regardless of the bar so nothing is dropped
# silently, and only a standout blocks.
DISCOVERY_MIN_JACCARD = 0.10
DISCOVERY_MIN_RATIO = 1.25
DISCOVERY_REPORT_TOP = 3

_CORPUS_CACHE: dict[str, list[tuple[str, str, set[str]]]] = {}


def prior_corpus(vault: Path | None) -> list[tuple[str, str, set[str]]]:
    """Tokenised prior-note corpus: EVERY directory under the vault plus EVERY *.md
    body in the auto-memory store - not just MEMORY.md summaries, because a pointer
    line is not the note it points at. Memoised: without this the scan re-reads the
    whole corpus once per planned note."""
    cache_key = str(vault)
    if cache_key in _CORPUS_CACHE:
        return _CORPUS_CACHE[cache_key]
    out: list[tuple[str, str, set[str]]] = []
    paths: list[tuple[str, str, Path]] = []
    if vault and vault.is_dir():
        for path in sorted(vault.rglob("*.md")):
            rel = path.relative_to(vault).as_posix()
            # Auto-capture receipts and compaction dumps are not knowledge; including
            # them would bury every real prior under 100 near-identical stubs.
            if rel.startswith(("compaction-checkpoints/", "sessions/")):
                continue
            if "/.hf/" in f"/{rel}":
                continue
            paths.append(("vault", rel, path))
    if AUTO_MEMORY_DIR.is_dir():
        for path in sorted(AUTO_MEMORY_DIR.glob("*.md")):
            paths.append(("auto-memory", path.name, path))
    for store, key, path in paths:
        try:
            toks = tokenize(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if toks:
            out.append((store, key, toks))
    _CORPUS_CACHE[cache_key] = out
    return out


def discover_overlaps(note: Note, vault: Path | None) -> list[dict[str, Any]]:
    """Rank UNDECLARED priors by token overlap and report the nearest few."""
    declared = {str(r.get("key") or "") for r in note.restates}
    mine = tokenize(note.body)
    if not mine:
        return []
    scored: list[tuple[float, str, str]] = []
    for store, key, other in prior_corpus(vault):
        if key in declared:
            continue
        scored.append((len(mine & other) / float(len(mine | other)), store, key))
    if not scored:
        return []
    scored.sort(reverse=True)
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    found: list[dict[str, Any]] = []
    for rank, (score, store, key) in enumerate(scored[:DISCOVERY_REPORT_TOP]):
        ratio = score / max(runner_up if rank == 0 else scored[0][0], 1e-9)
        standout = (
            rank == 0
            and score >= DISCOVERY_MIN_JACCARD
            and ratio >= DISCOVERY_MIN_RATIO
        )
        found.append(
            {
                "store": store,
                "key": key,
                "relation": "discovered-standout" if standout else "discovered-candidate",
                "jaccard": round(score, 3),
                "ratio_to_next": round(ratio, 2) if rank == 0 else None,
                "blocking": standout,
                "what": (
                    "UNDECLARED standout prior on the same subject - disposition it as "
                    "restates/extends before this run can go green"
                    if standout
                    else "nearest undeclared prior, reported for review; below the "
                    "measured standout bar so it does not block"
                ),
            }
        )
    return found


def supersede_rows(
    notes: list[Note], vault: Path | None, acked: set[str]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for note in notes:
        for rel in note.restates:
            if str(rel.get("relation")) not in SUPERSEDE_RELATIONS:
                continue
            key = str(rel.get("key") or "")
            rows.append(
                {
                    "id": note.id,
                    "new_title": note.title,
                    "prior_store": rel.get("store"),
                    "prior_key": key,
                    "prior_title": rel.get("title"),
                    "relation": rel.get("relation"),
                    "what": rel.get("what"),
                    "source": "declared",
                    "actioned": f"{note.id}|{key}" in acked,
                }
            )
        for rel in discover_overlaps(note, vault):
            key = str(rel.get("key") or "")
            rows.append(
                {
                    "id": note.id,
                    "new_title": note.title,
                    "prior_store": rel.get("store"),
                    "prior_key": key,
                    "prior_title": Path(key).stem,
                    "relation": rel.get("relation"),
                    "what": f"{rel.get('what')} (jaccard {rel.get('jaccard')}"
                    + (
                        f", {rel['ratio_to_next']}x next)"
                        if rel.get("ratio_to_next")
                        else ")"
                    ),
                    "source": "discovered",
                    "blocking": bool(rel.get("blocking")),
                    "actioned": f"{note.id}|{key}" in acked,
                }
            )
    for row in rows:
        # A DECLARED restates/corrects row always blocks until acked; a DISCOVERED row
        # blocks only when it cleared the measured standout bar.
        row.setdefault("blocking", True)
    return rows


def supersede_followups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Explicit, REVERSIBLE follow-ups for the orchestrator. Never silently omitted.

    `edit_note` operations are append / prepend / find_replace / replace_section /
    insert_before_section / insert_after_section, and prepend is frontmatter-aware
    (it inserts AFTER frontmatter). So edit_note CANNOT set a frontmatter key:
    the contract-literal `superseded_by:` frontmatter patch is a direct file edit
    the orchestrator performs, and the edit_note append is the CLI-native
    equivalent recorded as a body observation that hybrid recall can see.
    """
    out: list[dict[str, Any]] = []
    for row in rows:
        if row["actioned"] or not row.get("blocking"):
            continue
        new_title = row["new_title"]
        if row["prior_store"] == "vault":
            add = f"- superseded_by [[{new_title}]] (valid_as_of 2026-09-29)"
            out.append(
                {
                    "id": row["id"],
                    "prior_key": row["prior_key"],
                    "prior_store": "vault",
                    "primary": {
                        "kind": "frontmatter-patch",
                        "file": row["prior_key"],
                        "add_keys": {
                            "superseded_by": f"[[{new_title}]]",
                            "valid_as_of": "2026-09-29",
                        },
                        "revert": "remove exactly those two frontmatter keys",
                    },
                    "cli_fallback": {
                        "kind": "edit_note-append",
                        "argv": [
                            "tool",
                            "edit-note",
                            row["prior_key"].rsplit("/", 1)[-1].removesuffix(".md"),
                            "--operation",
                            "append",
                            "--content",
                            add,
                            "--local",
                        ],
                        "revert_argv": [
                            "tool",
                            "edit-note",
                            row["prior_key"].rsplit("/", 1)[-1].removesuffix(".md"),
                            "--operation",
                            "find_replace",
                            "--find-text",
                            add,
                            "--content",
                            "",
                            "--local",
                        ],
                    },
                    "ack": f"--record-supersede {row['id']}:{row['prior_key']}",
                }
            )
        else:
            out.append(
                {
                    "id": row["id"],
                    "prior_key": row["prior_key"],
                    "prior_store": "auto-memory",
                    "primary": {
                        "kind": "memory-pointer-update",
                        "file": str(AUTO_MEMORY_DIR / row["prior_key"]),
                        "action": (
                            "the auto-memory store is not basic-memory-managed and has no "
                            "frontmatter or permalink, so the supersede edge belongs in its "
                            f"MEMORY.md pointer line: note it is superseded by vault note "
                            f"'{new_title}'"
                        ),
                        "revert": "restore the prior pointer line verbatim",
                    },
                    "ack": f"--record-supersede {row['id']}:{row['prior_key']}",
                }
            )
    return out


# ------------------------------------------------------------------- the gates


def g2_existing(vault: Path, note: Note) -> tuple[str | None, Path | None]:
    """G2: on-disk existence, marker-glob PRIMARY, predicted path only a hint."""
    folder_dir = vault / note.folder
    hits = glob_marker(folder_dir, note.id)
    if hits:
        return "already-backfilled", hits[0]
    predicted = folder_dir / f"{note.title}.md"
    if predicted.exists():
        return "CONFLICT-foreign-note", predicted
    for path in folder_md_files(folder_dir):
        if path.stem.strip().lower() == note.title.strip().lower():
            return "CONFLICT-foreign-note", path
    return None, None


def verify_signal_a(
    cli: str, permalink: str | None, note: Note, project: str, timeout: int
) -> tuple[bool, str, int]:
    """Signal A: read the note back THROUGH the tool, by the permalink the write
    result returned - never a permalink predicted from folder+slug."""
    if not permalink:
        return False, "no permalink in write result", 0
    rc, out, err, calls = cli_with_retry(
        cli,
        [
            "tool",
            "read-note",
            permalink,
            "--include-frontmatter",
            "--project",
            project,
            "--local",
        ],
        None,
        timeout,
    )
    blob = parse_json_blob(out)
    if blob is None:
        return False, f"read-note returned no JSON (rc={rc}) {err.strip()[:120]}", calls
    content = ""
    for key in ("content", "text", "body", "markdown"):
        val = blob.get(key)
        if isinstance(val, str) and val.strip():
            content = val
            break
    if not content:
        return False, "read-note JSON has empty content (null-field not-found)", calls
    if marker_token(note.id) not in content:
        return False, "read-note content missing marker", calls
    if not OBSERVATION_RE.search(content):
        return False, "read-note content has no observation line", calls
    return True, "ok", calls


def verify_signal_b(
    vault: Path, note: Note, t0: float, file_path_hint: str | None
) -> tuple[bool, str]:
    """Signal B: the bytes on disk. Marker glob over the folder is PRIMARY; the
    file_path the write result returned and the predicted <title>.md are hints."""
    folder_dir = vault / note.folder
    hits = glob_marker(folder_dir, note.id)
    if not hits:
        hint_paths = []
        if file_path_hint:
            hint_paths.append(vault / file_path_hint)
        hint_paths.append(folder_dir / f"{note.title}.md")
        for cand in hint_paths:
            try:
                if cand.is_file() and marker_token(note.id) in cand.read_text(
                    encoding="utf-8", errors="replace"
                ):
                    hits = [cand]
                    break
            except OSError:
                continue
    if not hits:
        return False, f"no file under {folder_dir} carries the marker"
    path = hits[0]
    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        return False, f"stat failed: {exc!r}"
    if mtime + 1.0 < t0:
        return False, f"marker file older than run t0 ({path.name})"
    return True, path.name


# --------------------------------------------------------------------- phases


def do_seal(args: argparse.Namespace) -> int:
    """Recompute every marker + manifest sha256. Idempotent; rerun after editing
    a body. This is what makes the marker-embeds-its-own-hash design
    implementable: the hash span excludes the marker line."""
    manifest_path = Path(args.manifest)
    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        print(f"FAILED:seal manifest unreadable {manifest_path}")
        return 1
    notes_dir = Path(args.notes_dir)
    changed = 0
    for spec in manifest.get("notes", []):
        path = notes_dir / Path(str(spec["content_file"])).name
        if not path.exists():
            print(f"FAILED:seal missing {path}")
            return 1
        body, _old = split_body_marker(read_text_lf(path))
        digest = body_sha256(body)
        marker = (
            f"<!-- backfill-id: {spec['id']} src: {spec.get('source_slice','')[:80]} "
            f"sha256: {digest[:12]} -->"
        )
        new_text = body.rstrip() + "\n" + marker + "\n"
        if read_text_lf(path) != new_text or spec.get("sha256") != digest:
            changed += 1
        write_text_lf(path, new_text)
        spec["sha256"] = digest
    write_text_lf(
        manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"SUCCESS:seal notes={len(manifest.get('notes', []))} changed={changed}")
    return 0


def print_supersede(rows: list[dict[str, Any]], followups: list[dict[str, Any]]) -> None:
    blocking = [r for r in rows if r.get("blocking")]
    unactioned = [r for r in blocking if not r["actioned"]]
    print("")
    print(
        f"-- SUPERSEDE-REQUIRED: {len(rows)} row(s) total, {len(blocking)} blocking, "
        f"{len(unactioned)} un-actioned --"
    )
    if not rows:
        print("   (none: no planned note restates or corrects a prior note)")
        return
    for row in rows:
        if not row.get("blocking"):
            flag = "review"
        elif row["actioned"]:
            flag = "ACTIONED"
        else:
            flag = "OPEN"
        print(
            f"   [{flag}] {row['id']} {row['relation']}/{row['source']} "
            f"{row['prior_store']}:{row['prior_key']}"
        )
        print(f"            why: {row['what']}")
    if followups:
        print("")
        print("   Queued reversible follow-ups (orchestrator runs these, not this script):")
        for f in followups:
            print(f"   - {f['id']} -> {f['prior_store']}:{f['prior_key']}")
            print(f"     primary: {f['primary']['kind']}")
            if "cli_fallback" in f:
                print(
                    "     cli    : basic-memory "
                    + " ".join(
                        x if x else '""' for x in f["cli_fallback"]["argv"]
                    )
                )
            print(f"     ack    : {f['ack']}")


def do_record_supersede(args: argparse.Namespace) -> int:
    ack_path = Path(args.supersede_ack)
    ok = 0
    for spec in args.record_supersede:
        if ":" not in spec:
            print(f"FAILED:record-supersede bad spec {spec!r} (want <id>:<prior_key>)")
            return 1
        note_id, prior_key = spec.split(":", 1)
        ledger_append(
            ack_path,
            {
                "ts": now_iso(),
                "kind": "supersede-actioned",
                "id": note_id.strip(),
                "prior_key": prior_key.strip(),
            },
        )
        ok += 1
    print(f"SUCCESS:record-supersede rows={ok} ledger={ack_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Idempotent .remember -> basic-memory vault backfill. --plan is the default."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="print the plan, write nothing (DEFAULT)")
    mode.add_argument("--apply", action="store_true", help="required to write anything")
    mode.add_argument("--seal", action="store_true", help="recompute markers + manifest hashes")
    parser.add_argument("--only", action="append", metavar="ID", help="restrict to one note id (repeatable)")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--notes-dir", default=str(DEFAULT_NOTES_DIR))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--supersede-queue", default=str(DEFAULT_SUPERSEDE_QUEUE))
    parser.add_argument("--supersede-ack", default=str(DEFAULT_SUPERSEDE_ACK))
    parser.add_argument("--record-supersede", action="append", metavar="ID:PRIOR_KEY")
    parser.add_argument("--project", default="main")
    parser.add_argument("--vault", default=None, help="override; default reads ~/.basic-memory/config.json")
    parser.add_argument("--cli", default=None, help="default: $BASIC_MEMORY_CLI else which(basic-memory)")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--migrations-verified",
        action="store_true",
        help="ORDERING GATE, required for --apply: attests the orchestrator has brought "
        "basic-memory up cleanly once and confirmed the DB is at head, so this batch is "
        "not the invocation that triggers an alembic migration plus a semantic-embedding "
        "backfill against the just-repointed vault.",
    )
    parser.add_argument(
        "--allow-daemon-up",
        action="store_true",
        help="SERIALIZATION GATE override: without it, --apply refuses while :18765 is "
        "listening, so this cannot become a second in-process SQLite writer during a "
        "daemon restart window.",
    )
    args = parser.parse_args(argv)

    if args.record_supersede:
        return do_record_supersede(args)
    if args.seal:
        return do_seal(args)
    apply_mode = bool(args.apply)

    t0 = time.time()
    print(f"== backfill-remember-to-vault  mode={'APPLY' if apply_mode else 'PLAN'}  {now_iso()} ==")
    notes, fatal, info = preflight(args)

    print("-- PHASE 0 preflight --")
    print(f"   manifest      : {args.manifest}")
    print(f"   notes-dir     : {args.notes_dir}")
    print(f"   ledger        : {args.ledger}")
    print(f"   vault         : {info.get('vault')}   (from {info.get('vault_source')})")
    print(f"   cli           : {info.get('cli')}")
    print(f"   :{DAEMON_PORT} listening: {info.get('daemon_up')}  (reported; gates below)")
    print(f"   notes parsed  : {len(notes)}")

    blocked = [n for n in notes if n.blocked_secret]
    for note in blocked:
        print(f"   !! BLOCKED-SECRET {note.id} {note.title!r} - will NOT be written")

    if fatal:
        for problem in fatal:
            print(f"   !! {problem}")
        reason = "sha256-mismatch" if any("sha256-mismatch" in f for f in fatal) else (
            "cli-not-found" if any("cli-not-found" in f for f in fatal) else "manifest"
        )
        print(f"FAILED:preflight {reason} (zero writes)")
        return 2

    if apply_mode and not args.migrations_verified:
        print(
            "   !! ordering gate: --apply needs --migrations-verified. The FIRST "
            "write-note can trigger an alembic migration plus a semantic-embedding "
            "backfill; a 14-note batch must not be that invocation."
        )
        print("FAILED:preflight migrations-not-verified (zero writes)")
        return 2
    if apply_mode and info.get("daemon_up") and not args.allow_daemon_up:
        print(
            f"   !! serialization gate: :{DAEMON_PORT} is listening and --allow-daemon-up "
            "was not passed. Daemon lifecycle belongs to the orchestrator, serially."
        )
        print("FAILED:preflight daemon-up (zero writes)")
        return 2

    vault: Path = info["vault"]
    cli: str = info["cli"]
    ledger_path = Path(args.ledger)
    done: dict[str, str] = {}
    for rec in ledger_records(ledger_path):
        if rec.get("verdict") in {"SUCCESS", "already-exists", "already-backfilled"} and rec.get("id"):
            done[str(rec["id"])] = str(rec.get("sha256") or "")

    rows = supersede_rows(notes, vault, ack_keys(Path(args.supersede_ack)))
    followups = supersede_followups(rows)

    written = skipped = failed = partial = conflicts = would_write = 0
    print("")
    print(f"-- PHASE 1/2 {'write + verify' if apply_mode else 'dry plan'} (sequential) --")

    for note in notes:
        if note.blocked_secret:
            skipped += 1
            print(f"   BLOCKED-SECRET {note.id}  {note.title}")
            continue

        # G1: cheapest gate, no CLI call at all.
        if done.get(note.id) == note.sha256:
            skipped += 1
            print(f"   SKIP(ledger)   {note.id}  {note.title}")
            continue

        # G2: on-disk, marker-glob primary.
        verdict, path = g2_existing(vault, note)
        if verdict == "already-backfilled":
            skipped += 1
            print(f"   SKIP(already-backfilled) {note.id}  <- {path.name if path else '?'}")
            if apply_mode:
                ledger_append(ledger_path, {
                    "ts": now_iso(), "id": note.id, "sha256": note.sha256,
                    "verdict": "already-backfilled", "gate": "G2",
                    "path": str(path) if path else None, "cli_calls": 0,
                })
            continue
        if verdict == "CONFLICT-foreign-note":
            conflicts += 1
            skipped += 1
            print(
                f"   SKIP(CONFLICT-foreign-note) {note.id}  {path}  "
                "-- NOT overwritten, NOT modified"
            )
            if apply_mode:
                ledger_append(ledger_path, {
                    "ts": now_iso(), "id": note.id, "sha256": note.sha256,
                    "verdict": "CONFLICT-foreign-note", "gate": "G2",
                    "path": str(path) if path else None, "cli_calls": 0,
                })
            continue

        if not apply_mode:
            would_write += 1
            print(f"   WOULD-WRITE    {note.id}  {note.folder}/{note.title}  ({len(note.content)} B)")
            continue

        argv = [
            "tool", "write-note",
            "--title", note.title,
            "--folder", note.folder,
            "--type", note.type,
            "--project", args.project,
            "--local",
        ]
        for tag in note.tags:
            argv += ["--tags", tag]
        try:
            rc, out, err, calls = cli_with_retry(cli, argv, note.content, args.timeout)
        except subprocess.TimeoutExpired:
            failed += 1
            print(f"   FAILED:{note.id} cli-timeout after {args.timeout}s")
            ledger_append(ledger_path, {
                "ts": now_iso(), "id": note.id, "sha256": note.sha256,
                "verdict": "FAILED", "reason": "cli-timeout", "cli_calls": 1,
            })
            continue

        blob = parse_json_blob(out) or {}
        combined = (out + err)
        # G3: server-side conflict. Same semantics as modules.py:528-531 -
        # ALREADY_EXISTS is a delivered note, not a failure.
        if "ALREADY_EXISTS" in combined or blob.get("error") == "NOTE_ALREADY_EXISTS":
            skipped += 1
            print(f"   SKIP(already-exists) {note.id}  (G3 server-side, rc={rc})")
            ledger_append(ledger_path, {
                "ts": now_iso(), "id": note.id, "sha256": note.sha256,
                "verdict": "already-exists", "gate": "G3", "cli_calls": calls,
            })
            continue
        if rc != 0:
            failed += 1
            tail = (err or out).strip().splitlines()
            print(f"   FAILED:{note.id} write rc={rc} {tail[-1][:160] if tail else 'no output'}")
            ledger_append(ledger_path, {
                "ts": now_iso(), "id": note.id, "sha256": note.sha256,
                "verdict": "FAILED", "reason": f"write rc={rc}", "cli_calls": calls,
            })
            continue

        permalink = blob.get("permalink")
        ok_a, why_a, calls_a = verify_signal_a(cli, permalink, note, args.project, args.timeout)
        ok_b, why_b = verify_signal_b(vault, note, t0, blob.get("file_path"))
        total_calls = calls + calls_a
        if ok_a and ok_b:
            written += 1
            print(f"   SUCCESS:{note.id}  A=tool-read-back  B={why_b}")
            verdict = "SUCCESS"
        elif ok_a or ok_b:
            partial += 1
            which = "A-only (tool sees it, no file carries the marker)" if ok_a else "B-only (file on disk, tool read-back failed)"
            print(f"   PARTIAL:{note.id} {which}  A={why_a}  B={why_b}")
            verdict = "PARTIAL"
        else:
            failed += 1
            print(f"   FAILED:{note.id} unverified  A={why_a}  B={why_b}")
            verdict = "FAILED"
        ledger_append(ledger_path, {
            "ts": now_iso(), "id": note.id, "sha256": note.sha256,
            "verdict": verdict, "gate": "G3-pass", "permalink": permalink,
            "file_path": blob.get("file_path"), "signal_a": ok_a, "signal_b": ok_b,
            "reason_a": why_a, "reason_b": why_b, "cli_calls": total_calls,
        })

    print_supersede(rows, followups)
    queue_path = Path(args.supersede_queue)
    try:
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        write_text_lf(queue_path, json.dumps(
            {"generated": now_iso(), "rows": rows, "followups": followups},
            ensure_ascii=False, indent=2) + "\n")
        print(f"\n   supersede queue written: {queue_path}")
    except OSError as exc:
        print(f"\n   !! could not write supersede queue: {exc!r}")

    unactioned = sum(1 for r in rows if r.get("blocking") and not r["actioned"])
    print("")
    if not apply_mode:
        print(
            f"SUCCESS:backfill-plan notes={len(notes)} would_write={would_write}"
            f" skipped={skipped} blocked={len(blocked)} conflicts={conflicts}"
            f" supersede_rows={len(rows)} supersede_unactioned={unactioned}"
            "  (nothing written; --apply is required)"
        )
        return 0

    bad = failed + partial + conflicts + len(blocked) + unactioned
    tag = "FAILED" if bad else "SUCCESS"
    print(
        f"{tag}:backfill-remember-to-vault written={written} skipped={skipped} "
        f"blocked={len(blocked)} failed={failed} partial={partial} "
        f"conflicts={conflicts} supersede_unactioned={unactioned}"
    )
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("FAILED:backfill-remember-to-vault interrupted")
        sys.exit(130)
