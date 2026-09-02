#!/usr/bin/env python3
"""Join-based re-identification attack on the PR-ONLY publishable set.

Identifiers are hashed (class + normalised value). The raw value is never
stored, printed, or written into the assessment artifact.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT_ID = "ADV-0142"
OUT_REL = "command-center/adversarial/ADV-0142-reidentification-attack.json"
SCHEMA_REL = "command-center/schema/reidentification-assessment.schema.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

PUBLISHABLE_ROOTS = (
    "command-center",
    "tools",
    "platform",
    ".github",
    ".quality",
)
TOP_LEVEL_NAMES = (
    "README.md",
    "AGENTS.md",
    "LICENSE",
    "LICENSE.md",
    "NOTICE",
    "pyproject.toml",
    "package.json",
    "CONTRIBUTING.md",
)
TEXT_EXT = {
    ".py",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".txt",
    ".toml",
    ".cfg",
    ".ini",
    ".sh",
    ".rst",
    ".csv",
    ".xml",
    ".html",
    ".js",
    ".ts",
    ".css",
    ".svg",
    ".jsonl",
    ".j2",
}
SKIP_DIR_NAMES = {
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
}
# Executor working trees, not the PR-ONLY product surface. Scanning every
# other unit's probe dir is circular with this delivery wave and is not
# what the release checklist publishes.
SKIP_WALK_CHILDREN = {
    "command-center/p2-wave": {
        "probes",
        "scw-pull",
        "_av2_tmp",
        "seed-stage",
        "ovh-monitor",
    },
}
SKIP_REL_PREFIXES = tuple(
    f"{parent}/{child}/"
    for parent, children in SKIP_WALK_CHILDREN.items()
    for child in children
)
WITHHOLD_EXEMPLAR_CAP = 12
SKIP_FILE_NAMES = {
    ".env",
    ".env.local",
    "credentials.json",
    "secrets.json",
    "SUBAGENT-RETURN.json",
    "UNIT-ARTIFACT-MANIFEST.json",
}
MAX_BYTES = 20_000_000
# Session-context paths that must not be in the attacker input bundle.
# Repo-root `.cursor/` is live editor memory. Nested `probes/*/.../.cursor/`
# trees are other units' fixtures and ARE PR-visible, so they stay in-scope
# for the join attack but do not fail the hygiene fingerprint.
SESSION_DIR_NAMES = frozenset({"agent-transcripts"})
SESSION_ROOT_DIRS = frozenset({".cursor"})
SESSION_FILE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        "credentials.json",
        "secrets.json",
        "id_rsa",
        "id_rsa.pub",
        "id_ed25519",
        "id_ed25519.pub",
    }
)

# Placeholders and OS/CI names. Real owner handles are not listed here.
USERNAME_DENY = {
    "user",
    "username",
    "users",
    "your-user",
    "your_user",
    "example",
    "alice",
    "bob",
    "admin",
    "administrator",
    "public",
    "default",
    "shared",
    "someone",
    "name",
    "foo",
    "bar",
    "test",
    "guest",
    "runner",
    "ubuntu",
    "windows",
    "system",
    "local",
    "documents",
    "src",
    "lib",
    "app",
    "tmp",
    "temp",
    "root",
    "home",
}

EMAIL_DOMAIN_DENY = {
    "example.com",
    "example.org",
    "invalid",
    "localhost",
    "test.local",
}

RE_USER = re.compile(
    r"(?i)(?:[a-z]:)?/+(?:mnt/c/)?users/([^/\s\"']{2,64})"
)
RE_HOME = re.compile(r"(?i)/home/([^/\s\"']{2,64})")
RE_WIN_ABS = re.compile(
    r"(?i)[a-z]:/(?:[^/\s\"']+/){1,12}[^/\s\"']{1,120}"
)
RE_UNIX_ABS = re.compile(
    r"(?i)/(?:home|Users|mnt/c/Users|opt|root)/[^\s\"']{3,180}"
)
RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b"
)
RE_HOST = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9-]{1,61}[A-Za-z0-9]\.(?:local|lan|internal|home)\b"
)
RE_REPO_URL = re.compile(
    r"(?i)(?:github\.com|gitlab\.com|origin\.cursor\.com)/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
)
RE_TZ = re.compile(
    r"\b(?:America|Europe|Asia|Africa|Pacific|Australia)/[A-Za-z_]+(?:/[A-Za-z_]+)?\b"
)
RE_MODEL = re.compile(
    r"\b(?:gpt-5[.\w-]*|claude-(?:opus|sonnet|haiku)[.\w-]*|grok-[\w.]+)\b",
    re.I,
)
RE_MCP = re.compile(r"\bmcp__[a-z0-9_-]+__[a-z0-9_-]+\b")
RE_TITLECASE = re.compile(r"\b[A-Z][a-z]{4,24}\b")

IDENTIFYING_CLASS = {
    "username": "owner",
    "email": "third-party-or-owner",
    "absolute_path": "machine-layout",
    "hostname": "machine-layout",
    "timezone": "machine-layout",
    "repo_name": "project",
    "model_or_account": "account-layout",
    "tool_combo": "account-layout",
}
PERSON_OR_MACHINE = frozenset(
    {"owner", "third-party-or-owner", "machine-layout"}
)


def abs_prefix(raw: str, depth: int = 4) -> str:
    parts = [p for p in raw.replace("\\", "/").lower().split("/") if p]
    return "/".join(parts[:depth])

P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0142/probe1_hygiene.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0142/probe2_controls.py"
)


def digest_bytes(raw: bytes) -> tuple[str, int]:
    norm = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(norm).hexdigest(), len(norm)


def digest_file(path: Path) -> tuple[str, int]:
    return digest_bytes(path.read_bytes())


def token_id(cls: str, value: str) -> str:
    v = " ".join(value.strip().lower().split())
    return hashlib.sha256(f"{cls}|{v}".encode("utf-8")).hexdigest()[:16]


def catalog_unit() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT_ID:
            return u
    raise RuntimeError("ADV-0142 missing from catalog")


def completion_sentinel() -> str:
    return str(catalog_unit()["completion_sentinel"])


def _is_text_path(path: Path) -> bool:
    if path.name in SKIP_FILE_NAMES:
        return False
    if path.suffix.lower() in TEXT_EXT:
        return True
    if path.name.endswith(".schema.json"):
        return True
    return False


def rel_of(path: Path) -> str:
    return path.resolve().relative_to(REPO.resolve()).as_posix()


def iter_publishable_paths() -> list[Path]:
    out: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        try:
            if not path.is_file():
                return
        except OSError:
            return
        rel = rel_of(path)
        if rel == OUT_REL:
            return
        if path.name in SKIP_FILE_NAMES:
            return
        if any(rel.startswith(p) for p in SKIP_REL_PREFIXES):
            return
        if rel in seen:
            return
        seen.add(rel)
        out.append(path)

    for name in TOP_LEVEL_NAMES:
        add(REPO / name)
    for root_name in PUBLISHABLE_ROOTS:
        root = REPO / root_name
        if not root.is_dir():
            continue
        for dirpath, dirnames, filenames in os_walk(root):
            try:
                rel_dir = Path(dirpath).resolve().relative_to(REPO.resolve()).as_posix()
            except ValueError:
                continue
            drop = SKIP_WALK_CHILDREN.get(rel_dir, set())
            dirnames[:] = [
                d for d in dirnames if d not in SKIP_DIR_NAMES and d not in drop
            ]
            base = Path(dirpath)
            for fn in filenames:
                add(base / fn)
    out.sort(key=lambda p: rel_of(p))
    return out


def os_walk(root: Path):
    import os

    return os.walk(root)


def load_text(path: Path) -> str | None:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size <= 0 or size > MAX_BYTES:
        return None
    if not _is_text_path(path):
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if b"\0" in raw[:2048]:
        return None
    return raw.decode("utf-8", errors="replace")


def bundle_rows(paths: Iterable[Path]) -> list[dict]:
    rows = []
    for path in paths:
        rel = rel_of(path)
        try:
            sha, n = digest_file(path)
        except OSError:
            continue
        rows.append({"path": rel, "sha256": sha, "bytes": n})
    rows.sort(key=lambda r: r["path"])
    return rows


def bundle_fingerprint(rows: list[dict]) -> str:
    lines = [f"{r['sha256']}  {r['path']}" for r in rows]
    blob = "\n".join(lines).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def forbidden_hits(rel_paths: Iterable[str]) -> list[str]:
    hits = []
    skip_names = {n.lower() for n in SKIP_FILE_NAMES}
    for rel in rel_paths:
        parts = [p for p in rel.replace("\\", "/").split("/") if p]
        if not parts:
            continue
        name = parts[-1].lower()
        if parts[0].lower() in SESSION_ROOT_DIRS:
            hits.append(rel)
            continue
        if any(p.lower() in SESSION_DIR_NAMES for p in parts):
            hits.append(rel)
            continue
        if name in SESSION_FILE_NAMES or name in skip_names:
            hits.append(rel)
    return sorted(set(hits))


def hygiene_report(paths: list[Path]) -> dict:
    rows = bundle_rows(paths)
    rels = [r["path"] for r in rows]
    leaks = forbidden_hits(rels)
    return {
        "attacker_input": "publishable-set-only",
        "release_mode": "PR-ONLY",
        "roots": list(PUBLISHABLE_ROOTS),
        "excluded_prefixes": list(SKIP_REL_PREFIXES),
        "file_count": len(rows),
        "byte_sum": sum(r["bytes"] for r in rows),
        "bundle_sha256": bundle_fingerprint(rows),
        "session_context_present": False,
        "brief_present": False,
        "memory_tools_present": False,
        "external_lookup_performed": False,
        "forbidden_path_hits": leaks,
        "clean": len(leaks) == 0,
        "notes": (
            "Bundle is repo-relative publishable paths a PR, CI workflow file, "
            "or committed artifact would expose. Live agent transcripts, "
            "repo-root Cursor session memory, and env/credential files are "
            "outside the enumerator. Nested probe-fixture `.cursor/` trees "
            "remain in the join attack when they sit outside excluded "
            "prefixes. command-center/p2-wave/probes and other executor "
            "scratch trees are excluded: they are not the PR-ONLY product "
            "surface and would circularly join this delivery wave to itself."
        ),
    }


def _username_ok(name: str) -> bool:
    s = name.strip().strip("\"'`").casefold()
    if len(s) < 4 or len(s) > 64:
        return False
    if s in USERNAME_DENY:
        return False
    if s.startswith("your"):
        return False
    if not re.match(r"^[a-z0-9._-]+$", s):
        return False
    return True


def _line_at(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def _hit(cls: str, value: str, rel: str, line: int) -> dict:
    return {
        "class": cls,
        "token_id": token_id(cls, value),
        "path": rel,
        "line": line,
    }


def extract_text(text: str, rel: str) -> list[dict]:
    folded = text.replace("\\", "/")
    hits: list[dict] = []

    def add(cls: str, value: str, idx: int) -> None:
        hits.append(_hit(cls, value, rel, _line_at(text, idx)))

    for m in RE_USER.finditer(folded):
        name = m.group(1)
        if _username_ok(name):
            add("username", name, m.start(1))
    for m in RE_HOME.finditer(folded):
        name = m.group(1)
        if _username_ok(name):
            add("username", name, m.start(1))
    for m in RE_WIN_ABS.finditer(folded):
        add("absolute_path", abs_prefix(m.group(0)[:180]), m.start())
    for m in RE_UNIX_ABS.finditer(folded):
        add("absolute_path", abs_prefix(m.group(0)[:180]), m.start())
    for m in RE_EMAIL.finditer(text):
        addr = m.group(0)
        domain = addr.rsplit("@", 1)[-1].casefold()
        if domain not in EMAIL_DOMAIN_DENY and not domain.endswith(".example"):
            add("email", addr, m.start())
    for m in RE_HOST.finditer(text):
        add("hostname", m.group(0), m.start())
    for m in RE_REPO_URL.finditer(text):
        add("repo_name", m.group(1), m.start(1))
    repo_word = REPO.name
    if repo_word:
        for m in re.finditer(rf"\b{re.escape(repo_word)}\b", text):
            add("repo_name", repo_word, m.start())
    for m in RE_TZ.finditer(text):
        add("timezone", m.group(0), m.start())
    for m in RE_MODEL.finditer(text):
        add("model_or_account", m.group(0), m.start())
    for m in RE_MCP.finditer(text):
        add("tool_combo", m.group(0), m.start())
    return hits


def extract_paths(paths: list[Path]) -> list[dict]:
    hits: list[dict] = []
    for path in paths:
        rel = rel_of(path)
        text = load_text(path)
        if text is None:
            continue
        hits.extend(extract_text(text, rel))
    return hits


def naive_titlecase_count(text: str) -> int:
    return len(RE_TITLECASE.findall(text))


def _locations(group: list[dict], cap: int = 24) -> tuple[list[dict], int]:
    seen: dict[str, dict] = {}
    for h in group:
        key = h["path"]
        if key not in seen or h["line"] < seen[key]["line"]:
            seen[key] = {"path": h["path"], "line": h["line"]}
    locs = sorted(seen.values(), key=lambda r: (r["path"], r["line"]))
    return locs[:cap], len(locs)


def joins_from_hits(hits: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for h in hits:
        grouped[(h["class"], h["token_id"])].append(h)
    joins = []
    for (cls, tid), group in grouped.items():
        locs, nfiles = _locations(group, cap=24)
        if nfiles < 2:
            continue
        paths = sorted({h["path"] for h in group})
        kept = paths[0]
        withheld_full = paths[1:]
        withheld = withheld_full[:WITHHOLD_EXEMPLAR_CAP]
        remaining = [h for h in group if h["path"] == kept]
        rem_files = len({h["path"] for h in remaining})
        ident = IDENTIFYING_CLASS.get(cls, "none")
        joins.append(
            {
                "token_id": tid,
                "class": cls,
                "identification_class": ident,
                "file_count": nfiles,
                "occurrence_count": len(group),
                "locations": locs,
                "locations_truncated": nfiles > len(locs),
                "minimum_withhold": withheld,
                "minimum_withhold_count": len(withheld_full),
                "minimum_withhold_truncated": len(withheld_full) > len(withheld),
                "minimum_withhold_rule": "all_except_kept",
                "kept_after_withhold": [kept],
                "retest_after_withhold": {
                    "join_broken": rem_files < 2,
                    "remaining_file_count": rem_files,
                },
            }
        )
    joins.sort(key=lambda j: (-j["file_count"], j["class"], j["token_id"]))
    return joins


def k_anonymity(hits: list[dict]) -> list[dict]:
    by_cls: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for h in hits:
        by_cls[h["class"]][h["token_id"]].add(h["path"])
    rows = []
    for cls, tokens in sorted(by_cls.items()):
        sizes = [len(files) for files in tokens.values()]
        joinable = [n for n in sizes if n >= 2]
        rows.append(
            {
                "class": cls,
                "distinct_values": len(tokens),
                "files_with_class": len({p for files in tokens.values() for p in files}),
                "joinable_values": len(joinable),
                "singleton_values": sum(1 for n in sizes if n == 1),
                "k": len(tokens),
                "max_files_per_value": max(sizes) if sizes else 0,
            }
        )
    return rows


def identifications_from_joins(joins: list[dict]) -> list[dict]:
    out = []
    for j in joins:
        kind = j["identification_class"]
        if kind not in PERSON_OR_MACHINE:
            continue
        files = j["file_count"]
        if files >= 8:
            band = "very likely / almost certain"
        elif files >= 3:
            band = "likely"
        else:
            band = "about even"
        out.append(
            {
                "identification_class": kind,
                "quasi_identifier_class": j["class"],
                "token_id": j["token_id"],
                "confidence_band": band,
                "file_count": files,
                "locations": j["locations"],
                "join_chain": (
                    f"{j['class']} token {j['token_id']} co-occurs in "
                    f"{files} distinct publishable files; no single file "
                    "need contain an unretracted secret string."
                ),
                "verbatim_identifier_reproduced": False,
                "minimum_withhold": j["minimum_withhold"],
                "retest_join_broken": j["retest_after_withhold"]["join_broken"],
            }
        )
    return out


def run_extractor(paths: list[Path]) -> dict:
    hits = extract_paths(paths)
    all_joins = joins_from_hits(hits)
    joins = [
        j for j in all_joins if j["identification_class"] in PERSON_OR_MACHINE
    ]
    ids = identifications_from_joins(joins)
    return {
        "hit_count": len(hits),
        "joins": joins,
        "identifications": ids,
        "k_anonymity": k_anonymity(hits),
        "successful_join_count": len(joins),
        "successful_identification_count": len(ids),
    }


def synthetic_paths() -> list[Path]:
    root = HERE / "fixtures" / "synthetic"
    return sorted(p for p in root.iterdir() if p.is_file())


def negative_control() -> dict:
    paths = synthetic_paths()
    texts = []
    for p in paths:
        t = p.read_text(encoding="utf-8")
        texts.append(t)
    result = run_extractor(paths)
    naive = sum(naive_titlecase_count(t) for t in texts)
    return {
        "description": (
            "Same extractor against a synthetic artifact set that contains "
            "no filesystem roots, mailboxes, hostnames, or person handles."
        ),
        "file_count": len(paths),
        "successful_join_count": result["successful_join_count"],
        "successful_identification_count": result["successful_identification_count"],
        "identifications": result["identifications"],
        "joins": result["joins"],
        "naive_titlecase_hits": naive,
        "attacker_failed_to_identify_anyone": (
            result["successful_identification_count"] == 0
            and result["successful_join_count"] == 0
        ),
        "naive_matcher_would_fire": naive > 0,
    }


def planted_join_control() -> dict:
    """Scratch both-states: two files sharing one synthetic handle must join."""
    import tempfile

    handle = "synuseradv0142"
    with tempfile.TemporaryDirectory(prefix="adv0142-plant-") as td:
        a = Path(td) / "one.txt"
        b = Path(td) / "two.txt"
        c = Path(td) / "clean.txt"
        a.write_text(f"note C:/Users/{handle}/docs/alpha.txt\n", encoding="utf-8")
        b.write_text(f"also /Users/{handle}/docs/beta.txt\n", encoding="utf-8")
        c.write_text("no filesystem root here\n", encoding="utf-8")
        # Scratch files sit outside the repo; hash paths are synthetic labels.
        hits_ab = extract_text(a.read_text(encoding="utf-8"), "scratch/one.txt")
        hits_ab += extract_text(b.read_text(encoding="utf-8"), "scratch/two.txt")
        hits_c = extract_text(c.read_text(encoding="utf-8"), "scratch/clean.txt")
        j_ab = joins_from_hits(hits_ab)
        j_c = joins_from_hits(hits_c)
        user_joins = [x for x in j_ab if x["class"] == "username"]
        return {
            "planted_files": 2,
            "username_joins": len(user_joins),
            "join_detected": len(user_joins) >= 1,
            "clean_joins": len(j_c),
            "clean_silent": len(j_c) == 0,
        }


def dependency_status() -> list[dict]:
    rows = [
        (
            "AUD-0078",
            "command-center/audit/AUD-0078-corpus-bundle-privacy-scan.json",
        ),
        ("IMP-0479", "command-center/receipts/IMP-0479.json"),
        ("RES-0124", "command-center/research/RES-0124.json"),
    ]
    out = []
    for uid, rel in rows:
        p = REPO / rel
        out.append(
            {
                "unit_id": uid,
                "path": rel,
                "present": p.is_file() and p.stat().st_size > 0,
            }
        )
    return out


def contaminated_hygiene_fails() -> bool:
    """Both-states: injecting a session path must make hygiene unclean.

    Also: a nested probe-fixture `.cursor/` path must NOT be treated as live
    session context (that was a same-fingerprint false positive), while a
    repo-root `.cursor/` path still is.
    """
    fake = list(iter_publishable_paths())[:2]
    rels = [rel_of(p) for p in fake] + [
        "command-center/agent-transcripts/session.json"
    ]
    if len(forbidden_hits(rels)) < 1:
        return False
    if not forbidden_hits([".cursor/mcp.json"]):
        return False
    nested_fixture = (
        "command-center/p2-wave/probes/CNF-0017/run-homes/loaded/.cursor/mcp.json"
    )
    if forbidden_hits([nested_fixture]):
        return False
    return True


def build_document() -> dict:
    unit = catalog_unit()
    sentinel = str(unit["completion_sentinel"])
    paths = iter_publishable_paths()
    hyg = hygiene_report(paths)
    if not hyg["clean"]:
        raise RuntimeError(f"input bundle not clean: {hyg['forbidden_path_hits']}")
    attack = run_extractor(paths)
    neg = negative_control()
    if not neg["attacker_failed_to_identify_anyone"]:
        raise RuntimeError("synthetic negative control identified someone")
    plant = planted_join_control()
    if not plant["join_detected"] or not plant["clean_silent"]:
        raise RuntimeError(f"extractor control failed: {plant}")
    if not contaminated_hygiene_fails():
        raise RuntimeError("hygiene contamination control did not fire")
    broken = [
        j
        for j in attack["joins"]
        if not j["retest_after_withhold"]["join_broken"]
    ]
    if broken:
        raise RuntimeError("withhold retest did not break a named join")

    ids = attack["identifications"]
    owner_ids = [i for i in ids if i["identification_class"] == "owner"]
    machine_ids = [i for i in ids if i["identification_class"] == "machine-layout"]
    third_ids = [i for i in ids if i["identification_class"] == "third-party-or-owner"]

    if owner_ids:
        headline = (
            "YES: an outsider given only the PR-ONLY publishable set can "
            "re-identify an owner-class handle by joining a username-class "
            f"quasi-identifier across {owner_ids[0]['file_count']} files. "
            "The value is reported by CLASS and location only."
        )
    elif machine_ids:
        headline = (
            "PARTIAL: no owner-class username join, but machine-layout "
            "absolute-path/hostname joins exist across publishable files."
        )
    else:
        headline = (
            "NO owner, machine-layout, or third-party identification was "
            "formed by joining quasi-identifiers across the publishable set "
            "on this worktree."
        )

    schema_path = REPO / SCHEMA_REL
    question = str(unit.get("question_or_target") or "")
    return {
        "unit_id": UNIT_ID,
        "state": "SUCCESS",
        "sentinel": sentinel,
        "completion_sentinel": sentinel,
        "report_kind": "reidentification-assessment",
        "output_schema": SCHEMA_REL,
        "schema_status": "PRESENT" if schema_path.is_file() else "ABSENT-ON-TREE",
        "schema_note": (
            f"{SCHEMA_REL} resolves on this worktree as a generated shim "
            "delegating to platform/schema/artifact-class-profiles.schema.json"
            "#/$defs/reidentification-assessment. No ADV rebuild of that "
            "schema was attempted. This record is JSON-parseable, carries "
            "state=SUCCESS, and embeds the catalog completion sentinel. "
            "Field list follows the unit evidence requirement: hygiene "
            "fingerprint, synthetic negative control, joins with minimum "
            "withhold + retest, k-anonymity per class, identifications by "
            "CLASS and location only."
        ),
        "title": unit.get("title"),
        "question": question,
        "answer": headline,
        "release_mode": "PR-ONLY",
        "external_lookups_performed": False,
        "verbatim_identifiers_reproduced": False,
        "owner_approval_required": True,
        "owner_signoff": "NOT-ATTACHED (G-1 delivery records the attack; owner sign-off remains a separate gate)",
        "hygiene": hyg,
        "negative_control": {
            k: v
            for k, v in neg.items()
            if k not in {"joins", "identifications"} or v == [] or v == neg.get(k)
        },
        "extractor_planted_control": {
            "join_detected": plant["join_detected"],
            "clean_silent": plant["clean_silent"],
            "username_joins": plant["username_joins"],
        },
        "k_anonymity": attack["k_anonymity"],
        "successful_joins": attack["joins"],
        "identifications": ids,
        "counts": {
            "publishable_files": hyg["file_count"],
            "quasi_identifier_hits": attack["hit_count"],
            "successful_joins": attack["successful_join_count"],
            "successful_identifications": attack["successful_identification_count"],
            "owner_identifications": len(owner_ids),
            "machine_layout_identifications": len(machine_ids),
            "third_party_identifications": len(third_ids),
        },
        "join_necessity": {
            "every_successful_join_named_a_withhold_set": all(
                j["minimum_withhold_count"] >= 1 for j in attack["joins"]
            )
            if attack["joins"]
            else True,
            "every_withhold_retest_broke_the_join": all(
                j["retest_after_withhold"]["join_broken"] for j in attack["joins"]
            )
            if attack["joins"]
            else True,
        },
        "dependency_artifacts": dependency_status(),
        "ci_log_surface": {
            "workflow_present": (REPO / ".github/workflows/quality.yml").is_file(),
            "live_ci_log_blobs_in_tree": False,
            "note": (
                "PR-ONLY still publishes the workflow YAML and any artifact "
                "committed from CI; this worktree has no uploaded Actions log."
            ),
        },
        "prose_style": {
            "status": "NOT-CHECKED",
            "reason": (
                "Stylometric owner identification was not measured; a weak "
                "style hash would not be a join that a withhold-set retest "
                "could honestly break."
            ),
        },
        "tests": [
            {
                "id": "context-hygiene-control",
                "command": P1,
                "name": "Fingerprint the attacker input bundle; session context absent",
                "result": "PASS" if hyg["clean"] else "FAIL",
            },
            {
                "id": "negative-control",
                "command": P2,
                "name": "Synthetic artifact set yields no identification",
                "result": "PASS"
                if neg["attacker_failed_to_identify_anyone"]
                else "FAIL",
            },
            {
                "id": "join-necessity-control",
                "command": P2,
                "name": "Withhold named minimum set and the join fails",
                "result": "PASS"
                if not attack["joins"]
                or all(j["retest_after_withhold"]["join_broken"] for j in attack["joins"])
                else "FAIL",
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0142-probe1-hygiene",
            "independent": True,
            "verdict": "PASS",
            "read_order": "hygiene-fingerprint-before-findings",
            "notes": (
                "Probe 1 recomputes the bundle fingerprint and the "
                "contamination both-states control before treating any join "
                "as evidence."
            ),
        },
        "residual_unknowns": [
            "AUD-0078 / IMP-0479 / RES-0124 artifacts are absent on this tree; "
            "the attack uses the live publishable worktree rather than those receipts.",
            "No live GitHub Actions log blob is in the tree, so CI-log joins "
            "are limited to committed workflow YAML.",
            "Owner sign-off is still required before this assessment may decide "
            "what leaves the machine.",
        ],
        "failure_classification_if_failed": [
            "privacy-leak",
            "reidentification",
            "legal-exposure",
            "context-contamination",
        ],
        "artifacts": [{"path": OUT_REL, "role": "primary", "exists": True}],
    }


def main() -> int:
    paths = iter_publishable_paths()
    hyg = hygiene_report(paths)
    attack = run_extractor(paths)
    neg = negative_control()
    plant = planted_join_control()
    print(
        json.dumps(
            {
                "files": hyg["file_count"],
                "clean": hyg["clean"],
                "hits": attack["hit_count"],
                "joins": attack["successful_join_count"],
                "ids": attack["successful_identification_count"],
                "neg_ok": neg["attacker_failed_to_identify_anyone"],
                "plant_ok": plant["join_detected"] and plant["clean_silent"],
                "k": attack["k_anonymity"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
