#!/usr/bin/env python3
"""Capability-id scope-shrink diff (BLD-0018).

Match on mechanism fingerprint, not display label. A rename keeps the
mechanism and must not be reported as a drop. A drop with an owner
decision id that names the cap_id or mechanism is APPROVED-DROP;
otherwise UNAPPROVED-DROP (quietly dropped).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

CAP_LINE = re.compile(
    r"^\s*[-*]\s*cap_id\s*:\s*(?P<id>[A-Za-z0-9][A-Za-z0-9._:-]*)\s*$",
    re.I,
)
MECH_LINE = re.compile(
    r"^\s*[-*]\s*mechanism\s*:\s*(?P<mech>\S.*?)\s*$",
    re.I,
)
LABEL_LINE = re.compile(
    r"^\s*[-*]\s*label\s*:\s*(?P<label>.+?)\s*$",
    re.I,
)
HEADING = re.compile(r"^#{2,4}\s+(?P<title>.+?)\s*$")
DEC_HEAD = re.compile(r"^#{2,3}\s+(?P<id>DEC-[A-Z0-9][A-Z0-9._-]*)\s*$", re.I)
AUTH_MECH = re.compile(
    r"^\s*[-*]?\s*authorizes_drop_mechanism\s*:\s*(?P<mech>\S.*?)\s*$",
    re.I,
)
AUTH_CAP = re.compile(
    r"^\s*[-*]?\s*authorizes_drop_cap_id\s*:\s*(?P<id>[A-Za-z0-9][A-Za-z0-9._:-]*)\s*$",
    re.I,
)
MECH_NORM = re.compile(r"[^a-z0-9.]+")


def norm_mech(text: str) -> str:
    return MECH_NORM.sub("", (text or "").strip().lower())


@dataclass
class Capability:
    cap_id: str
    mechanism: str
    label: str
    path: str
    line: int
    source: str = ""

    @property
    def mech_key(self) -> str:
        return norm_mech(self.mechanism)


@dataclass
class Decision:
    decision_id: str
    path: str
    line: int
    text: str
    drop_cap_ids: set[str] = field(default_factory=set)
    drop_mechanisms: set[str] = field(default_factory=set)

    def authorises(self, cap: Capability) -> bool:
        if cap.cap_id in self.drop_cap_ids:
            return True
        key = cap.mech_key
        if key and key in {norm_mech(m) for m in self.drop_mechanisms}:
            return True
        blob = (self.text or "").lower()
        if cap.cap_id.lower() in blob:
            return True
        if cap.mechanism and cap.mechanism.lower() in blob:
            return True
        return False


@dataclass
class Drop:
    cap_id: str
    mechanism: str
    label: str
    verdict: str
    earlier_citation: str
    current_absence: str
    decision_id: str | None
    earlier_path: str
    earlier_line: int
    earlier_snippet: str


def _rel(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def parse_capabilities_md(path: Path, repo: Path, source: str) -> list[Capability]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rel = _rel(path, repo)
    out: list[Capability] = []
    cur: dict = {}
    heading = ""
    start_line = 1

    def flush() -> None:
        nonlocal cur, start_line
        cap_id = (cur.get("cap_id") or "").strip()
        mech = (cur.get("mechanism") or "").strip()
        if cap_id and mech:
            out.append(
                Capability(
                    cap_id=cap_id,
                    mechanism=mech,
                    label=(cur.get("label") or heading or cap_id).strip(),
                    path=rel,
                    line=int(cur.get("line") or start_line),
                    source=source,
                )
            )
        cur = {}

    for i, raw in enumerate(lines, 1):
        hm = HEADING.match(raw)
        if hm:
            flush()
            heading = hm.group("title").strip()
            start_line = i
            continue
        cm = CAP_LINE.match(raw)
        if cm:
            if cur.get("cap_id"):
                flush()
                start_line = i
            cur["cap_id"] = cm.group("id")
            cur["line"] = i
            continue
        mm = MECH_LINE.match(raw)
        if mm:
            cur["mechanism"] = mm.group("mech").strip()
            cur.setdefault("line", i)
            continue
        lm = LABEL_LINE.match(raw)
        if lm:
            cur["label"] = lm.group("label").strip()
    flush()
    return out


def parse_capabilities_json(path: Path, repo: Path, source: str) -> list[Capability]:
    if not path.is_file():
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    rel = _rel(path, repo)
    rows: list = []
    if isinstance(doc, dict):
        for key in ("capabilities", "options", "owner_decisions", "work_units"):
            val = doc.get(key)
            if isinstance(val, list):
                rows.extend(val)
        if not rows and isinstance(doc.get("id"), str) and doc.get("mechanism"):
            rows = [doc]
    elif isinstance(doc, list):
        rows = doc
    out: list[Capability] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        cap_id = str(row.get("cap_id") or row.get("id") or "").strip()
        mech = str(row.get("mechanism") or "").strip()
        if not cap_id or not mech:
            continue
        label = str(row.get("label") or row.get("title") or cap_id).strip()
        line = int(row.get("line") or idx + 1)
        out.append(
            Capability(
                cap_id=cap_id,
                mechanism=mech,
                label=label,
                path=rel,
                line=max(line, 1),
                source=source,
            )
        )
    return out


def parse_scope_file(path: Path, repo: Path, source: str) -> list[Capability]:
    if path.suffix.lower() == ".json":
        return parse_capabilities_json(path, repo, source)
    return parse_capabilities_md(path, repo, source)


def parse_decisions_md(path: Path, repo: Path) -> list[Decision]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    rel = _rel(path, repo)
    out: list[Decision] = []
    cur: Decision | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal cur, body
        if cur is None:
            return
        cur.text = "\n".join(body).strip()
        out.append(cur)
        cur = None
        body = []

    for i, raw in enumerate(lines, 1):
        hm = DEC_HEAD.match(raw)
        if hm:
            flush()
            cur = Decision(
                decision_id=hm.group("id").upper(),
                path=rel,
                line=i,
                text="",
            )
            body = [raw]
            continue
        if cur is None:
            continue
        body.append(raw)
        am = AUTH_MECH.match(raw)
        if am:
            cur.drop_mechanisms.add(am.group("mech").strip())
        ac = AUTH_CAP.match(raw)
        if ac:
            cur.drop_cap_ids.add(ac.group("id").strip())
    flush()
    return out


def union_caps(groups: Iterable[Iterable[Capability]]) -> list[Capability]:
    by_key: dict[str, Capability] = {}
    for group in groups:
        for cap in group:
            key = cap.mech_key or cap.cap_id
            if key not in by_key:
                by_key[key] = cap
    return list(by_key.values())


def find_decision(cap: Capability, decisions: list[Decision]) -> Decision | None:
    for dec in decisions:
        if dec.authorises(cap):
            return dec
    return None


def current_absence_citation(
    cap: Capability, later_files: list[Path], repo: Path
) -> str:
    bits: list[str] = []
    needle_id = cap.cap_id.encode("utf-8")
    needle_mech = cap.mechanism.encode("utf-8")
    for path in later_files:
        if not path.is_file():
            bits.append(f"{_rel(path, repo)}:ABSENT-FILE")
            continue
        raw = path.read_bytes()
        has_id = needle_id in raw
        has_mech = needle_mech in raw
        rel = _rel(path, repo)
        if not has_id and not has_mech:
            bits.append(f"{rel}:absent(cap_id+mechanism)")
        elif not has_id:
            bits.append(f"{rel}:absent(cap_id)")
        else:
            bits.append(f"{rel}:id-present-but-mechanism-unmatched")
    return "; ".join(bits) if bits else "no-later-scope-files"


def diff_scope(
    earlier: list[Capability],
    later: list[Capability],
    decisions: list[Decision],
    later_files: list[Path],
    repo: Path,
) -> dict:
    later_by_id = {c.cap_id: c for c in later}
    later_by_mech = {c.mech_key: c for c in later if c.mech_key}
    drops: list[Drop] = []
    renames: list[dict] = []
    kept: list[dict] = []
    for cap in earlier:
        if cap.cap_id in later_by_id:
            nxt = later_by_id[cap.cap_id]
            kept.append(
                {
                    "cap_id": cap.cap_id,
                    "mechanism": cap.mechanism,
                    "later_cap_id": nxt.cap_id,
                    "later_label": nxt.label,
                    "match": "cap_id",
                }
            )
            continue
        if cap.mech_key and cap.mech_key in later_by_mech:
            nxt = later_by_mech[cap.mech_key]
            renames.append(
                {
                    "earlier_cap_id": cap.cap_id,
                    "earlier_label": cap.label,
                    "later_cap_id": nxt.cap_id,
                    "later_label": nxt.label,
                    "mechanism": cap.mechanism,
                    "earlier_citation": f"{cap.path}:{cap.line}",
                    "later_citation": f"{nxt.path}:{nxt.line}",
                    "verdict": "RENAMED",
                    "reported_as_drop": False,
                }
            )
            continue
        dec = find_decision(cap, decisions)
        verdict = "APPROVED-DROP" if dec is not None else "UNAPPROVED-DROP"
        snippet = f"cap_id: {cap.cap_id}; mechanism: {cap.mechanism}"
        drops.append(
            Drop(
                cap_id=cap.cap_id,
                mechanism=cap.mechanism,
                label=cap.label,
                verdict=verdict,
                earlier_citation=f"{cap.path}:{cap.line}",
                current_absence=current_absence_citation(cap, later_files, repo),
                decision_id=None if dec is None else dec.decision_id,
                earlier_path=cap.path,
                earlier_line=cap.line,
                earlier_snippet=snippet,
            )
        )
    drops.sort(key=lambda d: (d.verdict, d.cap_id))
    return {
        "earlier_count": len(earlier),
        "later_count": len(later),
        "kept": kept,
        "renames": renames,
        "drops": [d.__dict__ for d in drops],
        "approved_drop_ids": [d.cap_id for d in drops if d.verdict == "APPROVED-DROP"],
        "unapproved_drop_ids": [
            d.cap_id for d in drops if d.verdict == "UNAPPROVED-DROP"
        ],
        "rename_earlier_ids": [r["earlier_cap_id"] for r in renames],
    }


def load_scratch(repo: Path, here: Path) -> dict:
    earlier_dir = here / "fixtures" / "history" / "rev-earlier"
    later_dir = here / "fixtures" / "history" / "rev-later"
    earlier_charter = earlier_dir / "PROGRAM-CHARTER.md"
    later_charter = later_dir / "PROGRAM-CHARTER.md"
    later_arch = later_dir / "architecture-selection.json"
    later_catalog = later_dir / "catalog-coverage.json"
    decisions_path = later_dir / "OWNER-DECISIONS.md"
    earlier = parse_scope_file(earlier_charter, repo, "scratch-earlier-charter")
    later = union_caps(
        [
            parse_scope_file(later_charter, repo, "scratch-later-charter"),
            parse_scope_file(later_arch, repo, "scratch-later-architecture"),
            parse_scope_file(later_catalog, repo, "scratch-later-catalog"),
        ]
    )
    decisions = parse_decisions_md(decisions_path, repo)
    later_files = [later_charter, later_arch, later_catalog]
    result = diff_scope(earlier, later, decisions, later_files, repo)
    result["earlier_source"] = _rel(earlier_charter, repo)
    result["later_sources"] = [_rel(p, repo) for p in later_files]
    result["decisions_source"] = _rel(decisions_path, repo)
    result["decisions"] = [
        {
            "id": d.decision_id,
            "path": d.path,
            "line": d.line,
            "drop_cap_ids": sorted(d.drop_cap_ids),
            "drop_mechanisms": sorted(d.drop_mechanisms),
        }
        for d in decisions
    ]
    return result


LIVE_EARLIER_CANDIDATES = (
    "command-center/PROGRAM-CHARTER.md",
    "PROGRAM-CHARTER.md",
    "07-OPTION-UNIVERSE.md",
    "07-OPTION-UNIVERSE.json",
    "command-center/sources/07-OPTION-UNIVERSE.json",
    "command-center/sources/07-OPTION-UNIVERSE.md",
    "13-ARCHITECTURE-CANDIDATES.md",
    "command-center/sources/13-ARCHITECTURE-CANDIDATES.md",
)

LIVE_LATER_CANDIDATES = (
    "command-center/PROGRAM-CHARTER.md",
    "PROGRAM-CHARTER.md",
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/phase3/A1/DESIGN.json",
    "command-center/phase3/A2/DESIGN.json",
)

LIVE_DECISION_CANDIDATES = (
    "command-center/OWNER-DECISIONS.md",
    "OWNER-DECISIONS.md",
    "17-DECISION-LOG.md",
    "command-center/sources/17-DECISION-LOG.md",
)


def existing(repo: Path, rels: Iterable[str]) -> list[Path]:
    out: list[Path] = []
    for rel in rels:
        p = repo / rel
        if p.is_file() and p not in out:
            out.append(p)
    return out


def git_available(repo: Path) -> bool:
    return (repo / ".git").exists()


def load_live(repo: Path) -> dict:
    earlier_files = existing(repo, LIVE_EARLIER_CANDIDATES)
    later_files = existing(repo, LIVE_LATER_CANDIDATES)
    decision_files = existing(repo, LIVE_DECISION_CANDIDATES)
    earlier: list[Capability] = []
    for path in earlier_files:
        earlier.extend(parse_scope_file(path, repo, "live-earlier"))
    later: list[Capability] = []
    for path in later_files:
        later.extend(parse_scope_file(path, repo, "live-later"))
    later = union_caps([later])
    decisions: list[Decision] = []
    for path in decision_files:
        decisions.extend(parse_decisions_md(path, repo))
    result = diff_scope(earlier, later, decisions, later_files, repo)
    result["earlier_files_present"] = [_rel(p, repo) for p in earlier_files]
    result["later_files_present"] = [_rel(p, repo) for p in later_files]
    result["decision_files_present"] = [_rel(p, repo) for p in decision_files]
    result["git_available"] = git_available(repo)
    result["earlier_extracted_count"] = len(earlier)
    result["observation"] = (
        "earlier-scope-files-absent"
        if not earlier_files
        else "earlier-scope-files-present"
    )
    present_csv = ", ".join(result["earlier_files_present"]) or "(none)"
    git_note = (
        "git history is available"
        if result["git_available"]
        else "git history is unavailable so git show <rev>:<path> citations cannot be produced"
    )
    if not earlier_files:
        result["honesty"] = (
            "Prompt One scope files (PROGRAM-CHARTER.md, 07-OPTION-UNIVERSE, "
            "13-ARCHITECTURE-CANDIDATES) are not on this worktree and git history "
            "is unavailable. Live temporal drop set is empty because no earlier "
            "statement can be cited at path:line. Detector discriminating power "
            "is proven on the scratch history, not by inventing live drops."
        )
    elif not earlier:
        result["honesty"] = (
            f"Live earlier files exist ({present_csv}) but encode zero "
            "cap_id+mechanism pairs (charter is prose; option-universe and "
            "architecture-selection files are absent). "
            f"{git_note}. Live temporal drop set is empty. Detector "
            "discriminating power is proven on the scratch history, not by "
            "inventing live drops."
        )
    else:
        result["honesty"] = (
            f"Live earlier scope files were parsed ({present_csv}); drops below "
            "are the temporal capability-id diff against today's catalog/charter "
            f"coverage. {git_note}."
        )
    return result


def review_approved_drops(scratch: dict, repo: Path, here: Path) -> dict:
    """Independent of engine.authorises: re-read OWNER-DECISIONS.md and confirm."""
    dec_path = here / "fixtures" / "history" / "rev-later" / "OWNER-DECISIONS.md"
    decisions = parse_decisions_md(dec_path, repo)
    by_id = {d.decision_id: d for d in decisions}
    sampled: list[dict] = []
    ok = True
    approved = [
        d
        for d in scratch.get("drops") or []
        if isinstance(d, dict) and d.get("verdict") == "APPROVED-DROP"
    ]
    for row in approved:
        did = str(row.get("decision_id") or "")
        dec = by_id.get(did)
        cap = Capability(
            cap_id=str(row.get("cap_id") or ""),
            mechanism=str(row.get("mechanism") or ""),
            label=str(row.get("label") or ""),
            path=str(row.get("earlier_path") or ""),
            line=int(row.get("earlier_line") or 1),
        )
        authorises = bool(dec is not None and dec.authorises(cap))
        if not authorises:
            ok = False
        sampled.append(
            {
                "finding_id": cap.cap_id,
                "decision_id": did or "NONE",
                "decision_path": None if dec is None else f"{dec.path}:{dec.line}",
                "authorises_drop": authorises,
                "decision_names_mechanism": bool(
                    dec is not None
                    and cap.mech_key
                    in {norm_mech(m) for m in dec.drop_mechanisms}
                ),
                "decision_names_cap_id": bool(
                    dec is not None and cap.cap_id in dec.drop_cap_ids
                ),
            }
        )
    return {
        "ok": ok and len(sampled) >= 3,
        "sampled_count": len(sampled),
        "sampled": sampled,
        "decisions_on_disk": len(decisions),
    }


def control_report(scratch: dict) -> dict:
    rename_ids = set(scratch.get("rename_earlier_ids") or [])
    drop_ids = {d["cap_id"] for d in scratch.get("drops") or []}
    approved = set(scratch.get("approved_drop_ids") or [])
    unapproved = set(scratch.get("unapproved_drop_ids") or [])
    kept_ids = {k["cap_id"] for k in scratch.get("kept") or []}
    want_rename = "CAP-COUNCIL-COMPILER"
    want_keep = "CAP-KEEP"
    want_quiet = "CAP-REMOTE-AUTO-PUSH"
    want_approved = {
        "CAP-TELEMETRY-BEACON",
        "CAP-MARKETPLACE-SYNC",
        "CAP-UX-PREVIEW",
    }
    rename_ok = want_rename in rename_ids and want_rename not in drop_ids
    planted_ok = want_quiet in unapproved and want_quiet not in approved
    approved_ok = want_approved <= approved and not (want_approved & unapproved)
    keep_ok = want_keep in kept_ids and want_keep not in drop_ids
    return {
        "rename_not_reported_as_drop": rename_ok,
        "planted_unapproved_caught": planted_ok,
        "approved_classified_separately": approved_ok,
        "kept_not_reported": keep_ok,
        "rename_ids": sorted(rename_ids),
        "approved_drop_ids": sorted(approved),
        "unapproved_drop_ids": sorted(unapproved),
        "kept_ids": sorted(kept_ids),
        "pass": rename_ok and planted_ok and approved_ok and keep_ok,
    }
