"""documented-but-missing MCP audit -- additive companion to mcp_doctor.py.

Diffs the MCP servers DECLARED in CLAUDE.md (and AGENTS.md) against what is
actually mounted per `claude mcp list`, and flags any documented server that is
NOT mounted -- or is mounted but FAILED to connect. This is the exact drift that
silently hid `basic-memory` + `codex` this session: both were documented as live
rails in CLAUDE.md yet were not showing as mounted.

Purely additive: a NEW standalone tool. It does NOT import from or modify
mcp_doctor.py / lib.mcp_doctor_core, so it cannot change existing doctor
behavior. Deploy alongside the live doctor at
``~/.local/opt/re-harness/mcp_doc_drift.py`` and run it as its own gate, or wire
it as a new ``docdrift`` subcommand (a suggested, NON-applied patch is at the
bottom of this file's module docstring in the repo README note).

Usage:
    python mcp_doc_drift.py            # audit default CLAUDE.md/AGENTS.md set
    python mcp_doc_drift.py --json
    python mcp_doc_drift.py --docs path/to/CLAUDE.md [more ...]

Signal source (high-confidence): literal ``mcp__<server>__<tool>`` handles found
in the docs -- these MUST resolve to a mounted server or every tool call to them
404s. Prose-only mentions (e.g. "codex mcp-server", "basic-memory") are reported
as a SEPARATE lower-confidence list so they never cause a false FAILED on their
own.

Exit codes (fail-closed, per the ci-hygiene rule): 0 = clean; 1 = drift found
(documented server missing / failed); 2 = could not audit (no docs, or
`claude mcp list` unavailable) -- never "nothing found -> pass".
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

# ``mcp__<server>__<tool>`` -- server names keep hyphens (and remote display
# names fold spaces/dots to underscores, keeping case, e.g. claude_ai_Boltz_API);
# the tool segment follows the 2nd ``__``. normalize() lowercases downstream.
_HANDLE_RE = re.compile(r"mcp__([A-Za-z0-9][A-Za-z0-9_-]*?)__[A-Za-z0-9]")

# Prose forms that name a server without an ``mcp__`` handle. Lower confidence:
# reported, but never the sole cause of a FAILED marker.
_PROSE_ALIASES: dict[str, str] = {
    "codex mcp-server": "codex",
    "codex mcp server": "codex",
    "basic-memory mcp": "basic-memory",
    "mcp_agent_mail": "agent-mail",
    "agent-mail": "agent-mail",
}

# Documented-but-mounting-is-INTENTIONALLY-optional. Never flag these as drift
# (they are advertised as "start on demand" backends, not always-on rails).
_OPTIONAL_DEFAULT: frozenset[str] = frozenset()


def normalize(name: str) -> str:
    """Fold a server name/handle to a comparison key: lowercase, non-alnum -> '_'.

    Makes ``mcp__claude_ai_Boltz_API__`` (handle) match ``claude.ai Boltz API``
    (list display) and ``basic-memory`` match ``basic_memory``.
    """
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def extract_handles(text: str) -> set[str]:
    """Raw server names taken from literal ``mcp__<server>__`` handles."""
    return {m.group(1) for m in _HANDLE_RE.finditer(text)}


def extract_prose(text: str) -> set[str]:
    """Lower-confidence server names from known prose aliases."""
    low = text.lower()
    return {canon for phrase, canon in _PROSE_ALIASES.items() if phrase in low}


def parse_mcp_list(output: str) -> dict[str, dict]:
    """Parse `claude mcp list` text into {normalized_name: {raw, connected}}.

    Each server line looks like ``name: <cmd or url> - <status>``; the status
    carries a check (Connected) or a cross (Failed to connect). Diagnostic /
    header / blank lines are skipped.
    """
    servers: dict[str, dict] = {}
    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        if " - " not in line or ":" not in line:
            continue
        name_part = line.split(":", 1)[0].strip()
        if not name_part or name_part.lower().startswith(
            ("location", "checking", "mcp config", "for help", "[warning", "[contains")
        ):
            continue
        # Status is after the LAST " - "; check-mark / "connected" == up.
        tail = line.rsplit(" - ", 1)[1].lower()
        connected = ("✔" in tail or "connected" in tail) and "fail" not in tail
        servers[normalize(name_part)] = {"raw": name_part, "connected": connected}
    return servers


def audit(
    handles: set[str],
    prose: set[str],
    mounted: dict[str, dict],
    optional: frozenset[str] = _OPTIONAL_DEFAULT,
) -> dict:
    """Compute drift findings. High-confidence = handle-documented servers that
    are missing or failed. Prose-only mentions are reported separately."""
    opt_norm = {normalize(o) for o in optional}
    findings: list[dict] = []

    def _check(names: set[str], confidence: str) -> None:
        for raw in sorted(names):
            key = normalize(raw)
            if key in opt_norm:
                continue
            entry = mounted.get(key)
            if entry is None:
                findings.append(
                    {
                        "severity": "HIGH" if confidence == "handle" else "MEDIUM",
                        "kind": "documented-but-missing",
                        "server": raw,
                        "confidence": confidence,
                        "detail": f"{raw!r} is documented ({confidence}) but not mounted "
                        f"in `claude mcp list`",
                    }
                )
            elif not entry["connected"]:
                findings.append(
                    {
                        "severity": "HIGH" if confidence == "handle" else "MEDIUM",
                        "kind": "documented-but-failed",
                        "server": raw,
                        "confidence": confidence,
                        "detail": f"{raw!r} is documented ({confidence}) and mounted as "
                        f"{entry['raw']!r} but FAILED to connect",
                    }
                )

    # Prose names that also appear as handles are covered by the handle pass.
    prose_only = {
        p for p in prose if normalize(p) not in {normalize(h) for h in handles}
    }
    _check(handles, "handle")
    _check(prose_only, "prose")

    counts = {"HIGH": 0, "MEDIUM": 0}
    for f in findings:
        counts[f["severity"]] += 1
    return {
        "documented_handles": sorted(handles),
        "documented_prose": sorted(prose),
        "mounted": sorted(v["raw"] for v in mounted.values()),
        "findings": findings,
        "counts": counts,
    }


def default_doc_paths() -> list[Path]:
    """Best-effort default doc set: project + global CLAUDE.md / AGENTS.md."""
    home = Path.home()
    candidates = [
        Path.cwd() / "CLAUDE.md",
        Path.cwd() / "AGENTS.md",
        home / "CLAUDE.md",
        home / ".claude" / "CLAUDE.md",
        home / ".claude" / "AGENTS.md",
        home / "AGENTS.md",
    ]
    seen: set[Path] = set()
    out: list[Path] = []
    for c in candidates:
        try:
            rc = c.resolve()
        except OSError:
            continue
        if rc in seen:
            continue
        seen.add(rc)
        if c.is_file():
            out.append(c)
    return out


def read_docs(paths: list[Path]) -> tuple[set[str], set[str], list[str]]:
    """Read the given docs; return (handles, prose, read_paths)."""
    handles: set[str] = set()
    prose: set[str] = set()
    read: list[str] = []
    for p in paths:
        try:
            text = Path(p).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        handles |= extract_handles(text)
        prose |= extract_prose(text)
        read.append(str(p))
    return handles, prose, read


def run_claude_mcp_list(timeout: float = 60.0) -> str:
    """Injectable seam: shell out to `claude mcp list`. Raises on failure so the
    caller fails CLOSED (never treats an unavailable CLI as 'no drift')."""
    exe = shutil.which("claude") or "claude"
    proc = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [exe, "mcp", "list"],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(
            f"`claude mcp list` failed (rc={proc.returncode}): {proc.stderr.strip()[:400]}"
        )
    return proc.stdout


def build_report(
    doc_paths: list[Path] | None = None,
    list_output: str | None = None,
    optional: frozenset[str] = _OPTIONAL_DEFAULT,
) -> dict:
    """Pure orchestration around the injectable seams (docs + list output)."""
    paths = doc_paths if doc_paths is not None else default_doc_paths()
    handles, prose, read = read_docs(paths)
    if not read:
        return {
            "error": "no-docs",
            "read_paths": [],
            "findings": [],
            "counts": {"HIGH": 0, "MEDIUM": 0},
        }
    if list_output is None:
        list_output = run_claude_mcp_list()
    mounted = parse_mcp_list(list_output)
    rep = audit(handles, prose, mounted, optional=optional)
    rep["read_paths"] = read
    return rep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="documented-but-missing MCP audit (CLAUDE.md vs `claude mcp list`)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--docs",
        nargs="*",
        default=None,
        help="explicit doc paths (default: project + global CLAUDE.md/AGENTS.md)",
    )
    parser.add_argument(
        "--optional",
        nargs="*",
        default=(),
        help="server names that are intentionally on-demand (never flagged)",
    )
    args = parser.parse_args(argv)

    doc_paths = [Path(d) for d in args.docs] if args.docs is not None else None
    optional = frozenset(args.optional or ())

    try:
        rep = build_report(doc_paths=doc_paths, optional=optional)
    except (RuntimeError, subprocess.SubprocessError, OSError) as exc:
        marker = f"FAILED:docdrift could not run `claude mcp list`: {exc}"
        print(
            json.dumps({"error": str(exc), "marker": marker}, indent=2)
            if args.json
            else marker
        )
        return 2

    if rep.get("error") == "no-docs":
        marker = "FAILED:docdrift no CLAUDE.md/AGENTS.md found to audit"
        print(json.dumps({**rep, "marker": marker}, indent=2) if args.json else marker)
        return 2

    c = rep["counts"]
    if c["HIGH"]:
        marker = f"FAILED:docdrift {c['HIGH']} documented server(s) missing/failed"
        rc = 1
    elif c["MEDIUM"]:
        marker = f"FAILED:docdrift {c['MEDIUM']} prose-documented server(s) missing"
        rc = 1
    else:
        marker = (
            f"SUCCESS:docdrift all {len(rep['documented_handles'])} "
            f"documented server(s) mounted + connected"
        )
        rc = 0

    if args.json:
        print(json.dumps({**rep, "marker": marker}, indent=2))
    else:
        for f in rep["findings"]:
            print(f"[{f['severity']:6}] {f['kind']} ({f['confidence']}): {f['detail']}")
        print()
        print(
            f"docs={len(rep['read_paths'])} "
            f"handles={len(rep['documented_handles'])} "
            f"prose={len(rep['documented_prose'])} "
            f"mounted={len(rep['mounted'])} "
            f"HIGH={c['HIGH']} MEDIUM={c['MEDIUM']}"
        )
        print(marker)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
