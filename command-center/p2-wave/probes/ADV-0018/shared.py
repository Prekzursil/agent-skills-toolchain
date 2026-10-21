"""Shared helpers for ADV-0018 probes (2026-10-21 Windows re-run).

Unit contract (command-center/WORK-UNIT-CATALOG.json ADV-0018):
  Probe 1: retrieve notes by topic and diff each load-bearing assertion against the
           corresponding current measurement.
  Probe 2 (mechanically different): frontmatter audit for superseded_by/valid_as_of on
           every contradicted note, computed from the file rather than from the search
           snippet.

The prior run (2026-08-19, Linux P2 subset) was BLOCKED: the vault was not mounted there.
This re-run executes on the live Windows vault at D:/basic-memory.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

VAULT = Path("D:/basic-memory")
REPO = Path(__file__).resolve().parents[4]  # .../ast-pr325
ARTIFACT = REPO / "command-center/adversarial/ADV-0018-memory-vault-contradiction-sweep.json"
PROBE_DIR = Path(__file__).resolve().parent

# Topic terms for "this program's subject matter" retrieval: the vault's own layout
# (ast-integrate/, p2-wave/, notes/p2-*) plus subject tokens. Filename-first, like the
# basic-memory recall path, with a content fallback.
TOPIC_TERMS = (
    "ast-integrate",
    "ast-pr325",
    "p2-wave",
    "p2-loop",
    "p2-deliver",
    "p2-r2e",
    "adv-00",
    "work-unit",
    "agent-skills-toolchain",
    "unit-artifact-manifest",
)

CATALOG_UNIT_RE = re.compile(r"\b([A-Z]{2,4}-\d{3,4})\b")
ARTIFACT_DIR = REPO / "command-center/adversarial"


def repo_head() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return out.stdout.strip()
    except Exception:  # noqa: BLE001
        return "UNAVAILABLE"


def census_counts() -> dict:
    """Run the census live (import census.census) for today's ground numbers."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "census", REPO / "command-center/p2-loop/census.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.census()


def sha256_of(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def unit_artifact_for(uid: str) -> Path | None:
    """Map a catalog unit id to its declared output_path artifact, if committed."""
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in cat["work_units"]:
        if u.get("id") == uid:
            p = REPO / u["output_path"]
            return p if p.is_file() else None
    return None


def retrieve_topic_notes() -> list[Path]:
    """Topic retrieval over the vault: filename match first, content match as fallback."""
    if not VAULT.is_dir():
        return []
    hits: list[Path] = []
    for md in sorted(VAULT.rglob("*.md")):
        name = md.name.lower()
        if any(t in name for t in TOPIC_TERMS):
            hits.append(md)
    if hits:
        return hits
    for md in sorted(VAULT.rglob("*.md")):
        try:
            head = md.read_text(encoding="utf-8", errors="replace")[:4000].lower()
        except OSError:
            continue
        if any(t in head for t in TOPIC_TERMS):
            hits.append(md)
    return hits


def parse_state_claims(text: str) -> list[tuple[str, str]]:
    """Extract (unit_id, claimed_state) pairs from a note's body.

    Matches the estate's note idiom: '- status: BLOCKED' / '- state: SUCCESS' /
    'status: DELIVERED' lines, plus '<UNIT-ID> ... BLOCKED/SUCCESS/DELIVERED' inside
    the first 200 chars of a line. Only terminal states, not prose words.
    """
    states = {"SUCCESS", "BLOCKED", "FAILED", "DELIVERED", "TIMEOUT", "SEVERED"}
    claims: list[tuple[str, str]] = []
    for line in text.splitlines():
        m = re.match(r"^-\s*(?:status|state):\s*([A-Z]+)\s*$", line.strip())
        if m and m.group(1) in states:
            uids = sorted(set(CATALOG_UNIT_RE.findall(text[:2000])))
            for uid in uids:
                claims.append((uid, m.group(1)))
            continue
        m2 = re.match(r"^.*\b([A-Z]{2,4}-\d{3,4})\b.*?\b(SUCCESS|BLOCKED|FAILED|DELIVERED)\b",
                      line.strip())
        if m2:
            claims.append((m2.group(1), m2.group(2)))
    # de-dup, keep order
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for c in claims:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def artifact_hash_claims(text: str) -> list[tuple[str, str]]:
    """Extract (repo_path, sha256) claims: a sha256 hex on a line that also names a
    repo path under command-center/."""
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        hm = re.search(r"\b([0-9a-f]{64})\b", line)
        pm = re.search(r"(command-center/[A-Za-z0-9_./-]+)", line)
        if hm and pm:
            out.append((pm.group(1), hm.group(1)))
    return out


def parse_frontmatter(text: str) -> dict:
    """Frontmatter from the FILE text (not a search snippet). Simple YAML head parser."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    head = text[3:end].strip("\n")
    fm: dict = {}
    for line in head.splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip("'\"")
    return fm


def write_raw(name: str, payload: dict, stdout_text: str) -> None:
    (PROBE_DIR / f"{name}.json").write_text(
        json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    (PROBE_DIR / f"{name}.raw.txt").write_text(stdout_text, encoding="utf-8")
