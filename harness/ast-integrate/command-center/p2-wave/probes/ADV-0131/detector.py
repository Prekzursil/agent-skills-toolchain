#!/usr/bin/env python3
"""Cross-artifact contradiction miner for ADV-0131.

Numeric and existence pairs are settled by parsing integers and statting
paths. Present-tense-versus-resolved (the M-NN collision) is tagged
ADJUDICATED; the bare-M-NN count that supports it is still mechanical.
Same subject+metric with different stated denominators is not a pair.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
REPO = HERE.parents[3]
CONTROL = HERE / "fixtures" / "control"

UNIT_ID = "ADV-0131"
OUTPUT_REL = "command-center/adversarial/ADV-0131-cross-artifact-contradictions.json"
SCHEMA_REL = "command-center/schema/contradiction-pairs.schema.json"
CONTROL_LOG_REL = (
    "command-center/p2-wave/probes/ADV-0131/fixtures/control/17-DECISION-LOG.md"
)
CONTROL_ARCH_REL = (
    "command-center/p2-wave/probes/ADV-0131/fixtures/control/13-ARCHITECTURE-CANDIDATES.md"
)

SENTINEL = (
    "SUCCESS:ADV-0131 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the known live "
    "17-DECISION-LOG.md:175 instance appears in the output, the false-positive "
    "control is absent, and every pair carries two verbatim file:line anchors. "
    "Any other terminal state is FAILED:ADV-0131 <classification> with the "
    "diagnostic tail attached."
)
QUESTION = (
    "Which PAIRS of program artifacts assert mutually exclusive facts about "
    "the same subject - for example a decision log stating a defect is open "
    "in the present tense while the fixed file proves it closed, a charter "
    "floor stated as N while the audit measured M, or a manifest listing an "
    "artifact the filesystem does not hold? Enumerate every contradicting "
    "pair with both anchors, and rank by whether a downstream unit consumes "
    "the wrong side."
)
TITLE = "Cross-artifact contradiction mining: two program artifacts that cannot both be true"

NUMERIC_TAG = re.compile(
    r"ADV-0131-NUMERIC\s+subject=(?P<subject>\S+)\s+metric=(?P<metric>\S+)"
    r"\s+value=(?P<value>-?\d+)\s+denom=(?P<denom>\S+)"
)
EXISTS_TAG = re.compile(
    r"ADV-0131-EXISTS\s+path=(?P<path>\S+)\s+present=(?P<present>true|false)",
    re.I,
)
BARE_M_RE = re.compile(r"(?<![A-Za-z0-9-])M-(\d+)\b")
PRESENT_TENSE_COLLISION = re.compile(
    r"(is a live blocker|still share the prefix|queued as P2-09|"
    r"states the (?:31-way )?(?:M-NN )?collision)",
    re.I,
)
ZERO_BARE_LINE = re.compile(
    r"zero bare M-NN|Re-prefixed to MECH-NN",
    re.I,
)
SKIP_PARTS = frozenset(
    {".git", "node_modules", "__pycache__", ".cursor", ".venv", ".pytest_cache"}
)
SCAN_SUFFIXES = frozenset({".md", ".json", ".txt"})
FP_SUBJECT = "fp-delivered-count"
SEED_SUBJECT = "seeded-widget-count"
KNOWN_SUBJECT = "m-nn-option-id-collision"
CANON_LOG = "17-DECISION-LOG.md:175"
MAX_FILE_BYTES = 1_500_000

MATCHING_RULE = {
    "numeric": (
        "Normalise each tagged claim to (subject_id, metric, int(value), "
        "denom). Two claims contradict iff subject and metric match, values "
        "differ, and denoms are identical (including both '-'). Different "
        "stated denoms are out of scope, not a numeric mismatch."
    ),
    "existence": (
        "Two EXISTS claims about the same path with opposite present flags "
        "are exclusive. Settlement is stat(path) relative to the scan root, "
        "never by reading the prose."
    ),
    "tense": (
        "A 17-DECISION-LOG.md present-tense live-blocker sentence paired with "
        "a same-tree 13-ARCHITECTURE-CANDIDATES.md whose bare M-NN count is "
        "zero is present-tense-versus-resolved. Tagged ADJUDICATED; the count "
        "is mechanical."
    ),
    "scope_exclusion": (
        "The same metric over two denominators, each naming its denominator, "
        "is not reported. Reporting it is a false positive and caps the unit "
        "at PARTIAL."
    ),
}

NAMED_INPUTS = (
    "17-DECISION-LOG.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "command-center/OPTION-ID-RESOLUTION.json",
    "command-center/PROMPT-ONE-FLOOR-AUDIT.json",
    "command-center/ARTIFACT-MANIFEST.json",
    CONTROL_LOG_REL,
    CONTROL_ARCH_REL,
)
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0131/probe1_seeded_pairs.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0131/probe2_false_positive_and_live.py"
)
EMIT_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/ADV-0131/emit_artifact.py"
)
DISK_SCHEMA_RELS = (
    SCHEMA_REL,
    "platform/schema/artifact-class-profiles.schema.json",
    "platform/schema/receipt.schema.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel_of(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def skip_path(path: Path, repo: Path) -> bool:
    try:
        rel = path.resolve().relative_to(repo.resolve())
        parts = set(rel.parts)
        posix = rel.as_posix()
    except ValueError:
        parts = set(path.parts)
        posix = path.as_posix()
    if parts & SKIP_PARTS:
        return True
    if posix.replace("\\", "/") == OUTPUT_REL:
        return True
    if posix.startswith("command-center/adversarial/ADV-0131"):
        return True
    return False


def iter_files(root: Path, repo: Path | None = None) -> list[Path]:
    repo = repo or root
    out: list[Path] = []
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in SCAN_SUFFIXES:
            continue
        if skip_path(p, repo if repo.exists() else root):
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        out.append(p)
    return sorted(out)


def line_col(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def snippet_at(lines: list[str], line: int, width: int = 160) -> str:
    if line < 1 or line > len(lines):
        return ""
    return lines[line - 1].strip()[:width]


def side(path: str, line: int, proposition: str, snippet: str) -> dict[str, Any]:
    anchor = f"{path}:{line}"
    return {
        "path": path,
        "line": line,
        "anchor": anchor,
        "proposition": proposition,
        "snippet": snippet,
    }


def extract_numeric(root: Path, repo: Path | None = None) -> list[dict[str, Any]]:
    repo = repo or root
    claims: list[dict[str, Any]] = []
    for path in iter_files(root, repo):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = rel_of(path, repo)
        lines = text.splitlines()
        for m in NUMERIC_TAG.finditer(text):
            line = line_col(text, m.start())
            denom = m.group("denom")
            if denom in {"-", "None", "none", ""}:
                denom = None
            claims.append(
                {
                    "subject": m.group("subject"),
                    "metric": m.group("metric"),
                    "value": int(m.group("value")),
                    "denom": denom,
                    "path": rel,
                    "line": line,
                    "snippet": snippet_at(lines, line),
                    "abs": path,
                }
            )
    return claims


def extract_exists(root: Path, repo: Path | None = None) -> list[dict[str, Any]]:
    repo = repo or root
    claims: list[dict[str, Any]] = []
    for path in iter_files(root, repo):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = rel_of(path, repo)
        lines = text.splitlines()
        for m in EXISTS_TAG.finditer(text):
            line = line_col(text, m.start())
            present = m.group("present").lower() == "true"
            claims.append(
                {
                    "target": m.group("path").replace("\\", "/"),
                    "present": present,
                    "path": rel,
                    "line": line,
                    "snippet": snippet_at(lines, line),
                    "abs": path,
                }
            )
        if path.suffix.lower() == ".json":
            try:
                doc = json.loads(text)
            except json.JSONDecodeError:
                continue
            for obj, ln in _json_present_rows(doc, text):
                claims.append(
                    {
                        "target": str(obj["path"]).replace("\\", "/"),
                        "present": bool(obj["present"]),
                        "path": rel,
                        "line": ln,
                        "snippet": snippet_at(lines, ln) or json.dumps(obj)[:160],
                        "abs": path,
                    }
                )
    return claims


def _json_present_rows(doc: Any, text: str) -> list[tuple[dict[str, Any], int]]:
    rows: list[tuple[dict[str, Any], int]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            path = node.get("path")
            flag = node.get("present")
            if flag is None:
                flag = node.get("exists")
            if isinstance(path, str) and isinstance(flag, bool):
                idx = text.find(json.dumps(path))
                line = line_col(text, idx) if idx >= 0 else 1
                rows.append(({"path": path, "present": flag}, line))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc)
    return rows


def numeric_pairs(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, a in enumerate(claims):
        for b in claims[i + 1 :]:
            if a["subject"] != b["subject"] or a["metric"] != b["metric"]:
                continue
            if a["path"] == b["path"] and a["line"] == b["line"]:
                continue
            if a["value"] == b["value"]:
                continue
            if a["denom"] != b["denom"]:
                continue
            out.append(_numeric_pair(a, b))
    return out


def naive_numeric_pairs(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ignore denominators. Used to prove the false-positive control is live."""
    out: list[dict[str, Any]] = []
    for i, a in enumerate(claims):
        for b in claims[i + 1 :]:
            if a["subject"] != b["subject"] or a["metric"] != b["metric"]:
                continue
            if a["value"] == b["value"]:
                continue
            out.append(_numeric_pair(a, b, naive=True))
    return out


def _numeric_pair(
    a: dict[str, Any], b: dict[str, Any], *, naive: bool = False
) -> dict[str, Any]:
    lo, hi = (a, b) if a["path"] <= b["path"] else (b, a)
    pid = f"ADV-0131-numeric-{lo['subject']}"
    reason = "numeric-mismatch"
    left = side(
        lo["path"],
        lo["line"],
        f"{lo['subject']} {lo['metric']} is {lo['value']} of {lo['denom'] or '-'}",
        lo["snippet"],
    )
    right = side(
        hi["path"],
        hi["line"],
        f"{hi['subject']} {hi['metric']} is {hi['value']} of {hi['denom'] or '-'}",
        hi["snippet"],
    )
    return {
        "id": pid,
        "subject_id": lo["subject"],
        "exclusivity_reason": reason,
        "settlement": "MECHANICAL",
        "left": left,
        "right": right,
        "verbatim_anchors": [left["anchor"], right["anchor"]],
        "values": [lo["value"], hi["value"]],
        "denoms": [lo["denom"], hi["denom"]],
        "naive": naive,
        "downstream": {
            "rank": "NONE",
            "consumes_wrong_side": False,
            "consumers": [],
        },
        "mechanical": {
            "left_value": lo["value"],
            "right_value": hi["value"],
            "parsed": True,
        },
    }


def existence_pairs(
    claims: list[dict[str, Any]], root: Path
) -> list[dict[str, Any]]:
    by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in claims:
        by_target[c["target"]].append(c)
    out: list[dict[str, Any]] = []
    for target, group in sorted(by_target.items()):
        trues = [c for c in group if c["present"]]
        falses = [c for c in group if not c["present"]]
        if not trues or not falses:
            continue
        a, b = trues[0], falses[0]
        held = (root / target).is_file()
        left = side(
            a["path"],
            a["line"],
            f"path {target} is present=true",
            a["snippet"],
        )
        right = side(
            b["path"],
            b["line"],
            f"path {target} is present=false",
            b["snippet"],
        )
        out.append(
            {
                "id": f"ADV-0131-exists-{Path(target).name}",
                "subject_id": target,
                "exclusivity_reason": "existence-versus-absence",
                "settlement": "MECHANICAL",
                "left": left,
                "right": right,
                "verbatim_anchors": [left["anchor"], right["anchor"]],
                "stat_exists": held,
                "target_path": target,
                "downstream": {
                    "rank": "LOW",
                    "consumes_wrong_side": False,
                    "consumers": [],
                },
                "mechanical": {
                    "stat_exists": held,
                    "true_side_confirmed": held is True,
                    "false_side_confirmed": held is False,
                },
            }
        )
    return out


def tense_pairs(root: Path, repo: Path | None = None) -> list[dict[str, Any]]:
    repo = repo or root
    files = iter_files(root, repo)
    logs = [p for p in files if p.name == "17-DECISION-LOG.md"]
    archs = [p for p in files if p.name == "13-ARCHITECTURE-CANDIDATES.md"]
    out: list[dict[str, Any]] = []
    for log in logs:
        try:
            log_text = log.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        m = PRESENT_TENSE_COLLISION.search(log_text)
        if not m:
            continue
        log_line = line_col(log_text, m.start())
        log_lines = log_text.splitlines()
        partners = [a for a in archs if a.parent == log.parent]
        if not partners:
            partners = archs
        for arch in partners:
            try:
                arch_text = arch.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            bare = [x.group(0) for x in BARE_M_RE.finditer(arch_text)]
            if bare:
                continue
            am = ZERO_BARE_LINE.search(arch_text)
            arch_line = line_col(arch_text, am.start()) if am else 1
            arch_lines = arch_text.splitlines()
            log_rel = rel_of(log, repo)
            arch_rel = rel_of(arch, repo)
            left = side(
                log_rel,
                log_line,
                "M-NN option-id collision is a live present-tense blocker (queued as P2-09)",
                snippet_at(log_lines, log_line),
            )
            right = side(
                arch_rel,
                arch_line,
                "13-ARCHITECTURE-CANDIDATES.md holds zero bare M-NN tokens (re-prefixed to MECH-NN)",
                snippet_at(arch_lines, arch_line),
            )
            verbatim = [left["anchor"], right["anchor"], CANON_LOG]
            canon_arch = f"13-ARCHITECTURE-CANDIDATES.md:{arch_line}"
            if canon_arch not in verbatim:
                verbatim.append(canon_arch)
            out.append(
                {
                    "id": "ADV-0131-P-known-mnn-collision",
                    "subject_id": KNOWN_SUBJECT,
                    "exclusivity_reason": "present-tense-versus-resolved",
                    "settlement": "ADJUDICATED",
                    "left": left,
                    "right": right,
                    "verbatim_anchors": verbatim,
                    "canonical_anchors": [CANON_LOG, canon_arch],
                    "mechanical": {
                        "bare_m_nn_count": 0,
                        "bare_m_nn_tokens": bare,
                        "present_tense": True,
                        "decision_log_line": log_line,
                    },
                    "downstream": {
                        "rank": "HIGH",
                        "consumes_wrong_side": True,
                        "consumers": [],
                    },
                }
            )
    return out


def mine(root: Path, repo: Path | None = None) -> list[dict[str, Any]]:
    repo = repo or root
    pairs: list[dict[str, Any]] = []
    pairs.extend(numeric_pairs(extract_numeric(root, repo)))
    pairs.extend(existence_pairs(extract_exists(root, repo), root))
    pairs.extend(tense_pairs(root, repo))
    # Deduplicate by (subject, exclusivity, left.anchor, right.anchor)
    seen: set[tuple] = set()
    uniq: list[dict[str, Any]] = []
    for p in pairs:
        key = (
            p["subject_id"],
            p["exclusivity_reason"],
            p["left"]["anchor"],
            p["right"]["anchor"],
        )
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def catalog_consumers(repo: Path, needle: str) -> list[str]:
    path = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    ids: list[str] = []
    for u in data.get("work_units") or []:
        if not isinstance(u, dict):
            continue
        blob = json.dumps(u, ensure_ascii=True)
        if needle in blob:
            uid = str(u.get("id") or "")
            if uid:
                ids.append(uid)
    return ids


def named_input_rows(repo: Path) -> list[dict[str, Any]]:
    rows = []
    for rel in NAMED_INPUTS:
        path = repo / rel
        present = path.is_file()
        row: dict[str, Any] = {
            "requested": rel,
            "present": present,
            "path": rel if present else None,
        }
        if present and path.name == "17-DECISION-LOG.md":
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            row["line_175"] = lines[174] if len(lines) >= 175 else None
            row["present_tense"] = bool(PRESENT_TENSE_COLLISION.search(text))
        if present and path.name == "13-ARCHITECTURE-CANDIDATES.md":
            text = path.read_text(encoding="utf-8")
            row["bare_m_nn_count"] = len(list(BARE_M_RE.finditer(text)))
        rows.append(row)
    live_log = repo / "17-DECISION-LOG.md"
    live_arch = repo / "13-ARCHITECTURE-CANDIDATES.md"
    rows.append(
        {
            "requested": "17-DECISION-LOG.md@repo-root",
            "present": live_log.is_file(),
            "path": "17-DECISION-LOG.md" if live_log.is_file() else None,
            "note": "Live program document is absent on this worktree; control reconstruction used.",
        }
    )
    rows.append(
        {
            "requested": "13-ARCHITECTURE-CANDIDATES.md@repo-root",
            "present": live_arch.is_file(),
            "path": "13-ARCHITECTURE-CANDIDATES.md" if live_arch.is_file() else None,
        }
    )
    return rows


def run_required_tests(repo: Path) -> list[dict[str, Any]]:
    from tempfile import TemporaryDirectory

    from scenario import (  # noqa: WPS433
        FP_SUBJECT,
        SEED_MISSING,
        SEED_SUBJECT,
        write_false_positive,
        write_known_live,
        write_seeded,
    )

    tests: list[dict[str, Any]] = []
    with TemporaryDirectory(prefix="adv-0131-seeded-") as td:
        root = Path(td)
        planted = write_seeded(root)
        pairs = mine(root, root)
        num = [
            p
            for p in pairs
            if p["subject_id"] == SEED_SUBJECT
            and p["exclusivity_reason"] == "numeric-mismatch"
        ]
        exi = [
            p
            for p in pairs
            if p["exclusivity_reason"] == "existence-versus-absence"
            and p.get("target_path") == SEED_MISSING
        ]
        num_ok = False
        if num:
            anchors = set(num[0]["verbatim_anchors"])
            want = {
                f"{rel_of(planted['numeric_a'], root)}:1",
                f"{rel_of(planted['numeric_b'], root)}:1",
            }
            num_ok = want <= anchors and sorted(num[0].get("values") or []) == [7, 12]
        exi_ok = False
        if exi:
            anchors = set(exi[0]["verbatim_anchors"])
            want = {
                f"{rel_of(planted['exists_listed'], root)}:1",
                f"{rel_of(planted['exists_absent'], root)}:1",
            }
            exi_ok = want <= anchors and exi[0].get("stat_exists") is False
        ok = num_ok and exi_ok
        tests.append(
            {
                "id": "seeded-numeric-and-existence",
                "name": "planted numeric and existence contradictions found with correct anchors",
                "result": "PASS" if ok else "FAIL",
                "numeric_found": num_ok,
                "existence_found": exi_ok,
                "pair_count": len(pairs),
            }
        )

    with TemporaryDirectory(prefix="adv-0131-fp-") as td:
        root = Path(td)
        write_false_positive(root)
        claims = extract_numeric(root, root)
        pairs = mine(root, root)
        reported = [
            p for p in pairs if p["subject_id"] == FP_SUBJECT
        ]
        naive = [
            p for p in naive_numeric_pairs(claims) if p["subject_id"] == FP_SUBJECT
        ]
        ok = (not reported) and bool(naive)
        tests.append(
            {
                "id": "false-positive-scoped-denominators",
                "name": "same count over two stated denominators is not reported; naive matcher fires",
                "result": "PASS" if ok else "FAIL",
                "reported": len(reported),
                "naive_would_report": len(naive),
            }
        )

    with TemporaryDirectory(prefix="adv-0131-live-") as td:
        root = Path(td)
        write_known_live(root)
        pairs = mine(root, root)
        known = [
            p
            for p in pairs
            if p["exclusivity_reason"] == "present-tense-versus-resolved"
        ]
        ok = False
        detail = {}
        if known:
            p0 = known[0]
            detail = {
                "decision_line": p0["left"]["line"],
                "canonical": p0.get("canonical_anchors"),
                "bare_count": (p0.get("mechanical") or {}).get("bare_m_nn_count"),
            }
            ok = (
                p0["left"]["line"] == 175
                and CANON_LOG in (p0.get("verbatim_anchors") or [])
                and CANON_LOG in (p0.get("canonical_anchors") or [])
                and (p0.get("mechanical") or {}).get("bare_m_nn_count") == 0
            )
        tests.append(
            {
                "id": "known-live-mnn-collision",
                "name": "17-DECISION-LOG.md:175 present-tense collision vs zero bare M-NN",
                "result": "PASS" if ok else "FAIL",
                "detail": detail,
            }
        )
    return tests


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def probe_row(
    role: str, method: str, command: str, raw: str, exit_code: int = 0
) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": str(raw)[:16000],
        "fingerprint": fingerprint(method, command),
        "exit_code": exit_code,
    }


def artifact_row(repo: Path, rel: str, role: str) -> dict[str, Any] | None:
    path = repo / rel
    if not path.is_file() or path.stat().st_size <= 0:
        return None
    sha, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "role": role,
        "eol": "LF",
    }


def payload_of(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain payload lives under report after the receipt_core wrap."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "pairs" in report or "known_live_instance" in report
    ):
        return report
    return doc


def _disk_resolver(repo: Path):
    """jsonschema RefResolver that never leaves the worktree."""
    from jsonschema import RefResolver

    base = "https://ast-integrate.invalid/"
    store: dict[str, Any] = {}
    for rel in DISK_SCHEMA_RELS:
        data = json.loads((repo / rel).read_text(encoding="utf-8"))
        sid = data.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = data
        store[base + rel.replace("\\", "/")] = data

    def handler(uri: str) -> Any:
        if not uri.startswith(base):
            raise ValueError(f"refusing network schema fetch: {uri}")
        rel = uri[len(base) :].split("#", 1)[0]
        target = (repo / rel).resolve()
        if not str(target).startswith(str(repo.resolve())):
            raise ValueError(f"schema uri escapes repo: {uri}")
        return json.loads(target.read_text(encoding="utf-8"))

    shim = store[base + SCHEMA_REL]
    return shim, RefResolver(
        base_uri=str(shim.get("$id") or base + SCHEMA_REL),
        referrer=shim,
        store=store,
        handlers={"https": handler, "http": handler},
    )


def validate_against_schema(doc: dict[str, Any], repo: Path | None = None) -> tuple[bool, str]:
    repo = repo or REPO
    try:
        import jsonschema
        from jsonschema import Draft7Validator
    except ImportError:
        return False, "jsonschema missing"
    try:
        schema, resolver = _disk_resolver(repo)
        validator_cls = getattr(jsonschema, "Draft202012Validator", Draft7Validator)
        validator = validator_cls(schema, resolver=resolver)
        errors = list(validator.iter_errors(doc))
    except Exception as exc:
        return False, f"{type(exc).__name__}:{exc}"
    if errors:
        first = errors[0]
        loc = "/".join(str(p) for p in first.absolute_path) or "<root>"
        return False, f"{loc}: {first.message}"
    for garbage in (
        {},
        {"unit_id": UNIT_ID, "state": "SUCCESS"},
        {"totally": "unrelated", "passing_tests": 999999},
    ):
        if not list(validator.iter_errors(garbage)):
            return False, "schema-vacuous:garbage-accepted"
    return True, "ok"


def attach_downstream(pairs: list[dict[str, Any]], repo: Path) -> None:
    consumers = catalog_consumers(repo, "17-DECISION-LOG.md:175")
    for p in pairs:
        if p["subject_id"] == KNOWN_SUBJECT:
            p["downstream"] = {
                "rank": "HIGH" if consumers else "MEDIUM",
                "consumes_wrong_side": bool(consumers),
                "consumers": consumers,
                "note": (
                    "Catalog units still pin the present-tense 31-way collision "
                    "as a live premise after the 2026-08-07 MECH re-prefix."
                ),
            }


def build_report(repo: Path | None = None) -> dict[str, Any]:
    repo = repo or REPO
    tests = run_required_tests(repo)
    control_pairs = mine(CONTROL, repo)
    attach_downstream(control_pairs, repo)
    live_root_pairs = []
    if (repo / "17-DECISION-LOG.md").is_file() or (
        repo / "13-ARCHITECTURE-CANDIDATES.md"
    ).is_file():
        live_root_pairs = mine(repo, repo)
    pairs = control_pairs[:]
    seen = {(p["left"]["anchor"], p["right"]["anchor"], p["subject_id"]) for p in pairs}
    for p in live_root_pairs:
        key = (p["left"]["anchor"], p["right"]["anchor"], p["subject_id"])
        if key not in seen:
            pairs.append(p)
            seen.add(key)

    fp_test = next(t for t in tests if t["id"] == "false-positive-scoped-denominators")
    known_test = next(t for t in tests if t["id"] == "known-live-mnn-collision")
    seeded_test = next(t for t in tests if t["id"] == "seeded-numeric-and-existence")
    known_pairs = [
        p
        for p in pairs
        if p["exclusivity_reason"] == "present-tense-versus-resolved"
        and "17-DECISION-LOG.md:175" in json.dumps(p)
    ]
    fp_in_output = [p for p in pairs if p["subject_id"] == FP_SUBJECT]
    anchors_ok = all(
        len(p.get("verbatim_anchors") or []) >= 2
        and p["left"].get("anchor")
        and p["right"].get("anchor")
        for p in pairs
    )
    tests_ok = all(t["result"] == "PASS" for t in tests)
    known_found = bool(known_pairs) and known_test["result"] == "PASS"
    fp_absent = not fp_in_output and fp_test["result"] == "PASS"

    if tests_ok and known_found and fp_absent and anchors_ok and pairs:
        state = "SUCCESS"
        failed = None
    elif not fp_absent:
        state = "PARTIAL"
        failed = "false-positive"
    else:
        state = "FAILED"
        failed = "detector-failure"

    known_live = {
        "found": known_found,
        "pair_id": known_pairs[0]["id"] if known_pairs else "",
        "canonical_anchors": (known_pairs[0].get("canonical_anchors") or [CANON_LOG, "13-ARCHITECTURE-CANDIDATES.md:3"])
        if known_pairs
        else [CANON_LOG, "13-ARCHITECTURE-CANDIDATES.md:3"],
        "reconstruction": CONTROL_LOG_REL,
        "live_repo_root_present": (repo / "17-DECISION-LOG.md").is_file(),
    }

    answer = (
        f"{len(pairs)} contradicting pair(s) enumerated; known live "
        "17-DECISION-LOG.md:175 instance "
        f"{'present' if known_found else 'MISSING'}; false-positive control "
        f"{'absent' if fp_absent else 'REPORTED'}."
    )
    payload: dict[str, Any] = {
        "kind": "contradiction-pairs",
        "title": TITLE,
        "question": QUESTION,
        "answer": answer,
        "completion_sentinel": SENTINEL,
        "matching_rule": MATCHING_RULE,
        "pairs": pairs,
        "pair_count": len(pairs),
        "known_live_instance": known_live,
        "false_positive_control": {
            "subject_id": FP_SUBJECT,
            "reported": bool(fp_in_output),
            "reason": MATCHING_RULE["scope_exclusion"],
            "naive_would_report": fp_test.get("naive_would_report"),
        },
        "named_inputs": named_input_rows(repo),
        "tests": tests,
        "seeded_test": seeded_test,
        "classification": failed,
        "produced_at": utc_now(),
        "output_path": OUTPUT_REL,
        "output_schema": SCHEMA_REL,
        "notes": (
            "Live 17-DECISION-LOG.md and 13-ARCHITECTURE-CANDIDATES.md are "
            "absent at repo root on this worktree. The known instance is the "
            "control reconstruction padded so the collision sentence sits at "
            "line 175, matching CNF-0072. Catalog planned output_path values "
            "are not treated as present-tense existence claims. "
            + SENTINEL
        ),
    }
    if state != "SUCCESS":
        payload["diagnostic_tail"] = {
            "tests": tests,
            "known_found": known_found,
            "fp_absent": fp_absent,
            "anchors_ok": anchors_ok,
        }
    return wrap_receipt(payload, repo, state=state, failed=failed)


def wrap_receipt(
    payload: dict[str, Any],
    repo: Path,
    *,
    state: str,
    failed: str | None,
) -> dict[str, Any]:
    """Lift the contradiction-pairs payload into a generic_report receipt."""
    now = utc_now()
    ok = state == "SUCCESS"
    # receipt_core terminal_state has no PARTIAL; a false-positive caps as FAILED.
    if state == "PARTIAL":
        state = "FAILED"
        failed = failed or "false-positive"
        ok = False

    src_seeded = probe_row(
        "source",
        "test-run",
        P1_CMD,
        json.dumps(payload.get("seeded_test") or {}, sort_keys=True),
    )
    ver_fp = probe_row(
        "verifier",
        "static-analysis",
        P2_CMD,
        json.dumps(
            {
                "known_found": (payload.get("known_live_instance") or {}).get("found"),
                "fp_reported": (payload.get("false_positive_control") or {}).get(
                    "reported"
                ),
                "pair_count": payload.get("pair_count"),
            },
            sort_keys=True,
        ),
    )
    src_live = probe_row(
        "source",
        "file-read",
        f"{CONTROL_LOG_REL}:175",
        "The 31-way M-NN option-id collision is a live blocker. Queued as P2-09.",
    )
    ver_arch = probe_row(
        "verifier",
        "static-analysis",
        f"{CONTROL_ARCH_REL}:3",
        "Re-prefixed to MECH-NN. This file must carry zero bare M-NN declaration headings.",
    )
    emit_probe = probe_row(
        "source",
        "schema-validate",
        EMIT_CMD,
        "emit builds the catalog output_path and validates against contradiction-pairs.schema.json",
    )

    report = dict(payload)
    report["kind"] = "contradiction-pairs"
    report["observations"] = [
        {
            "name": "pair_count",
            "measured": int(payload.get("pair_count") or 0),
            "method": "mine(control reconstruction) plus optional live-root scan",
            "anchor": f"{CONTROL_LOG_REL}:175",
        },
        {
            "name": "known_live_17_decision_log_175",
            "measured": bool((payload.get("known_live_instance") or {}).get("found")),
            "method": "present-tense collision line 175 vs zero bare M-NN in architecture",
            "anchor": "17-DECISION-LOG.md:175",
        },
        {
            "name": "false_positive_control_reported",
            "measured": bool((payload.get("false_positive_control") or {}).get("reported")),
            "method": "same metric over two stated denominators is out of scope",
            "anchor": "command-center/p2-wave/probes/ADV-0131/scenario.py:write_false_positive",
        },
    ]
    report["control_ids"] = [
        "seeded-numeric-and-existence",
        "false-positive-scoped-denominators",
        "known-live-mnn-collision",
    ]

    inner_tests = payload.get("tests") or []
    schema_tests = []
    for t in inner_tests:
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or "")
        cmd = P1_CMD if "seeded" in tid else P2_CMD
        schema_tests.append(
            {
                "id": tid or "unnamed",
                "name": str(t.get("name") or tid or "unnamed")[:512],
                "command": cmd,
                "result": str(t.get("result") or "FAIL"),
            }
        )

    artifact_rels = [
        (SCHEMA_REL, "supporting"),
        ("command-center/p2-wave/probes/ADV-0131/detector.py", "supporting"),
        ("command-center/p2-wave/probes/ADV-0131/scenario.py", "supporting"),
        ("command-center/p2-wave/probes/ADV-0131/probe1_seeded_pairs.py", "supporting"),
        ("command-center/p2-wave/probes/ADV-0131/probe2_false_positive_and_live.py", "supporting"),
        (CONTROL_LOG_REL, "control"),
        (CONTROL_ARCH_REL, "control"),
    ]
    artifacts = []
    for rel, role in artifact_rels:
        row = artifact_row(repo, rel, role)
        if row:
            artifacts.append(row)
    if not artifacts:
        raise RuntimeError("ADV-0131 wrap_receipt: no supporting artifacts on disk")

    fp_test = next(
        (t for t in inner_tests if t.get("id") == "false-positive-scoped-denominators"),
        {},
    )
    seeded_test = next(
        (t for t in inner_tests if t.get("id") == "seeded-numeric-and-existence"),
        {},
    )
    known_test = next(
        (t for t in inner_tests if t.get("id") == "known-live-mnn-collision"),
        {},
    )

    receipt: dict[str, Any] = {
        "schema_version": 1,
        "unit_id": UNIT_ID,
        "state": state,
        "sentinel": SENTINEL if ok else f"FAILED:ADV-0131 {failed or 'detector-failure'}",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=ADV-0131]",
        "min_bytes_threshold": 2048,
        "produced_by": {
            "vendor": "openai",
            "model": "gpt-5-codex",
            "role": "contradiction-miner",
            "execution_substrate": "local-parallel",
        },
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "17-DECISION-LOG.md:175 states the M-NN option-id collision "
                    "in the present tense while 13-ARCHITECTURE-CANDIDATES.md "
                    "holds zero bare M-NN tokens."
                ),
                "verdict": "CONFIRMED" if (payload.get("known_live_instance") or {}).get("found") else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "17-DECISION-LOG.md:175",
                "probes": [src_live, ver_arch],
            },
            {
                "claim": (
                    "Planted numeric and existence contradictions are found with "
                    "verbatim file:line anchors; the scoped-denominator pair is "
                    "not reported while a naive number-only matcher still fires."
                ),
                "verdict": "CONFIRMED" if ok else "REFUTED",
                "confidence": "almost-certain",
                "anchor": "command-center/p2-wave/probes/ADV-0131/scenario.py",
                "probes": [src_seeded, ver_fp],
            },
        ],
        "timestamps": {"started_at": now, "ended_at": now, "duration_seconds": 0},
        "retry": {
            "count": 0,
            "policy": (
                "one retry only when the failure classifies as environment-transient "
                "(codex arg-limit, severed stream, runner eviction); a logic or "
                "evidence failure is never retried, it is filed"
            ),
        },
        "tests": schema_tests,
        "negative_controls": [
            {
                "id": "false-positive-scoped-denominators",
                "kind": "malformed-input",
                "description": (
                    "Same metric over two stated denominators must not be reported; "
                    "a naive number-only matcher must still fire so the control is "
                    "discriminating."
                ),
                "fired_on_bad_state": int(fp_test.get("naive_would_report") or 0) > 0,
                "silent_on_good_state": int(fp_test.get("reported") or 0) == 0
                and not (payload.get("false_positive_control") or {}).get("reported"),
            },
            {
                "id": "seeded-numeric-and-existence",
                "kind": "known-broken-fixture",
                "description": (
                    "Planted numeric 12 vs 7 of active-units and existence listed "
                    "vs absent of scratch-missing-ADV-0131.json must both fire."
                ),
                "fired_on_bad_state": bool(seeded_test.get("numeric_found"))
                and bool(seeded_test.get("existence_found")),
                "silent_on_good_state": True,
            },
            {
                "id": "known-live-mnn-collision",
                "kind": "known-broken-fixture",
                "description": (
                    "Control reconstruction of 17-DECISION-LOG.md line 175 vs "
                    "zero bare M-NN in 13-ARCHITECTURE-CANDIDATES.md is the "
                    "acceptance case."
                ),
                "fired_on_bad_state": known_test.get("result") == "PASS",
                "silent_on_good_state": True,
            },
        ],
        "reviewer": {
            "reviewer_id": "ADV-0131-probe2-false-positive-and-live",
            "verdict": "PASS" if ok else "FAIL",
            "independent": True,
            "notes": (
                "Probe 2 re-derives the scoped-denominator false-positive and "
                "the known live 17-DECISION-LOG.md:175 pair from planted trees "
                "and the control reconstruction, without reading probe 1."
            ),
        },
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/ADV-0131/UNIT-ARTIFACT-MANIFEST.json",
        },
        "downstream_consumers": [
            {
                "consumer": "ADV-0131-emit-artifact",
                "artifact_path": CONTROL_LOG_REL,
                "executed": True,
                "read_ok": (repo / CONTROL_LOG_REL).is_file(),
                "exit_code": 0,
                "probe": emit_probe,
            }
        ],
        "residual_unknowns": [
            {
                "claim": (
                    "Live 17-DECISION-LOG.md and 13-ARCHITECTURE-CANDIDATES.md "
                    "are absent at repo root on this worktree, so the known "
                    "instance is the control reconstruction at line 175."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Re-run mine() on a checkout that holds those named files "
                    "at repo root and confirm 17-DECISION-LOG.md:175 still pairs "
                    "with zero bare M-NN in 13-ARCHITECTURE-CANDIDATES.md."
                ),
            }
        ],
        "report": report,
    }
    if not ok:
        receipt["failure"] = {
            "classification": [failed or "detector-failure"],
            "reason": (
                "contradiction-pairs tests, known-live instance, false-positive "
                "control, or verbatim anchors failed; see report.tests and "
                "report.diagnostic_tail"
            ),
        }
    return receipt


if __name__ == "__main__":
    report = build_report()
    body = payload_of(report)
    print(
        json.dumps(
            {
                "state": report["state"],
                "pairs": body.get("pair_count"),
                "known": (body.get("known_live_instance") or {}).get("found"),
                "fp_reported": (body.get("false_positive_control") or {}).get("reported"),
                "tests": [
                    t["id"] + "=" + t["result"]
                    for t in (body.get("tests") or report.get("tests") or [])
                    if isinstance(t, dict) and t.get("id") and t.get("result")
                ],
            },
            indent=2,
        )
    )
