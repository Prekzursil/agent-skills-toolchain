#!/usr/bin/env python3
"""Project changelog and release notes from a claim registry.

A sentence may appear in the verified section only when the backing claim is
VERIFIED and its evidence anchor resolves on disk. A VERIFIED claim whose
anchor file is missing causes the generator to refuse rather than emit.
INFERRED, UNVERIFIED, REJECTED and DEFERRED claims are withheld from the
verified section and rendered in a separately labelled section with the
status tag inline. Every claim line carries its source claim id.

# REL-0016-REFUSE: missing VERIFIED evidence file refuses the projection
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

VERIFIED = "VERIFIED"
TAGGED_STATUSES = ("INFERRED", "UNVERIFIED", "REJECTED", "DEFERRED")
STATUS_VOCABULARY = (VERIFIED,) + TAGGED_STATUSES

VERDICT_TO_STATUS = {
    "CONFIRMED": VERIFIED,
    "VERIFIED": VERIFIED,
    "REFUTED": "REJECTED",
    "REJECTED": "REJECTED",
    "PARTIAL": "INFERRED",
    "INFERRED": "INFERRED",
    "NOT-CHECKED": "UNVERIFIED",
    "UNVERIFIED": "UNVERIFIED",
    "BLOCKED": "DEFERRED",
    "DEFERRED": "DEFERRED",
    "DESIGN-ONLY": "DEFERRED",
}

VERIFIED_HEADER = "## Verified"
TAGGED_HEADER = "## Not verified"
CLAIM_LINE_RE = re.compile(
    r"^- (?:\[(INFERRED|UNVERIFIED|REJECTED|DEFERRED)\] )?\[([^\]]+)\] (.+)$"
)


class ProjectionRefused(Exception):
    """Generator must not emit notes when a VERIFIED anchor does not resolve."""

    def __init__(self, claim_id: str, anchor: str, reason: str) -> None:
        self.claim_id = claim_id
        self.anchor = anchor
        self.reason = reason
        super().__init__(
            f"REFUSE: VERIFIED claim {claim_id} evidence {anchor!r} {reason}"
        )


def claim_status(claim: dict[str, Any]) -> str:
    raw = (
        claim.get("verification_status")
        or claim.get("status")
        or claim.get("verdict")
        or ""
    )
    key = str(raw).strip().upper()
    return VERDICT_TO_STATUS.get(key, key or "UNVERIFIED")


def claim_text(claim: dict[str, Any]) -> str:
    text = (
        claim.get("changelog_sentence")
        or claim.get("text")
        or claim.get("claim")
        or ""
    )
    return " ".join(str(text).split())


_REL_PATH_RE = re.compile(
    r"(?:^|[\s;,'\"()=`])("
    r"(?:command-center|tools|agent-self|platform|scripts|docs|skills|\.agents)"
    r"/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)"
)
_ALT_TEST_PREFIXES = (
    "tools/command-center/",
    "command-center/tools/command-center/",
)


def _safe_is_file(repo: Path, rel: str) -> bool:
    text = str(rel or "").replace("\\", "/").strip().strip("'\"")
    if not text or len(text) > 240 or "\n" in text:
        return False
    parts = Path(text).parts
    if ".." in parts:
        return False
    try:
        return (repo / text).is_file()
    except OSError:
        return False


def infer_existing_anchor(repo: Path, text: str) -> str:
    """Return a repo-relative path that exists, or empty.

    Free-text evidence (the live CLAIM-REGISTRY `evidence` strings) is not an
    explicit evidence_anchor. Missing files here withhold a VERIFIED row;
    they do not refuse the whole projection. Explicit evidence_anchor pointing
    at a missing file still refuses (probe1).
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    candidates: list[str] = []
    head = text.split(";")[0].strip()
    head = head.split("::")[0].strip()
    if "," in head:
        candidates.append(head.split(",")[0].strip())
    candidates.append(head)
    for match in _REL_PATH_RE.finditer(text):
        candidates.append(match.group(1))
    seen: set[str] = set()
    for cand in candidates:
        cand = cand.replace("\\", "/").strip().strip("'\"")
        if not cand or cand in seen:
            continue
        seen.add(cand)
        if _safe_is_file(repo, cand):
            return cand
        if cand.startswith("tests/"):
            for prefix in _ALT_TEST_PREFIXES:
                alt = prefix + cand
                if alt not in seen and _safe_is_file(repo, alt):
                    return alt
    return ""


def explicit_anchor(claim: dict[str, Any]) -> str:
    if isinstance(claim.get("evidence_anchor"), str) and claim["evidence_anchor"]:
        return claim["evidence_anchor"]
    if isinstance(claim.get("anchor"), str) and claim["anchor"]:
        return claim["anchor"]
    evidence = claim.get("evidence")
    if isinstance(evidence, list) and evidence:
        first = evidence[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            path = str(first.get("path") or "")
            line = first.get("line")
            if path and isinstance(line, int):
                return f"{path}:{line}"
            return path
    return ""


def claim_anchor(claim: dict[str, Any]) -> str:
    return explicit_anchor(claim)


def parse_anchor(anchor: str) -> tuple[str, int | None]:
    text = str(anchor or "").strip().replace("\\", "/")
    if not text:
        return "", None
    if ":" in text:
        path, _, rest = text.rpartition(":")
        if rest.isdigit() and path:
            return path, int(rest)
    return text, None


def resolve_anchor(repo: Path, anchor: str) -> dict[str, Any]:
    rel, line = parse_anchor(anchor)
    if not rel:
        return {
            "resolved": False,
            "path": "",
            "line": line,
            "reason": "empty-anchor",
        }
    path = Path(rel)
    if not path.is_absolute():
        path = repo / rel
    if not path.is_file():
        return {
            "resolved": False,
            "path": rel,
            "line": line,
            "reason": "missing-file",
        }
    if line is not None:
        try:
            n = len(path.read_text(encoding="utf-8").splitlines())
        except OSError:
            return {
                "resolved": False,
                "path": rel,
                "line": line,
                "reason": "unreadable",
            }
        if line < 1 or line > n:
            return {
                "resolved": False,
                "path": rel,
                "line": line,
                "reason": "line-out-of-range",
            }
    return {
        "resolved": True,
        "path": rel,
        "line": line,
        "reason": "ok",
    }


def load_registry(path: Path) -> dict[str, Any]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(doc, list):
        return {"claims": doc}
    if not isinstance(doc, dict):
        raise ValueError(f"registry is not an object: {path}")
    claims = doc.get("claims")
    if not isinstance(claims, list):
        raise ValueError(f"registry.claims missing: {path}")
    return doc


def verified_line(claim_id: str, text: str) -> str:
    return f"- [{claim_id}] {text}"


def tagged_line(status: str, claim_id: str, text: str) -> str:
    return f"- [{status}] [{claim_id}] {text}"


def project(registry: dict[str, Any], repo: Path) -> dict[str, Any]:
    claims = [c for c in (registry.get("claims") or []) if isinstance(c, dict)]
    verified_rows: list[dict[str, Any]] = []
    tagged_rows: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    by_status: Counter[str] = Counter()

    for claim in claims:
        cid = str(claim.get("id") or "").strip()
        if not cid:
            raise ValueError("claim missing id")
        text = claim_text(claim)
        if not text:
            raise ValueError(f"{cid} missing text")
        status = claim_status(claim)
        by_status[status] += 1
        explicit = explicit_anchor(claim)
        inferred = ""
        if not explicit:
            evidence = claim.get("evidence")
            blob = evidence if isinstance(evidence, str) else ""
            inferred = infer_existing_anchor(repo, blob)
        anchor = explicit or inferred
        resolution = resolve_anchor(repo, anchor) if anchor else {
            "resolved": False,
            "path": "",
            "line": None,
            "reason": "empty-anchor",
        }
        row = {
            "id": cid,
            "status": status,
            "text": text,
            "anchor": anchor,
            "anchor_explicit": bool(explicit),
            "resolution": resolution,
        }
        if status == VERIFIED:
            if not resolution["resolved"]:
                if explicit:
                    # REL-0016-REFUSE: missing VERIFIED evidence file refuses the projection
                    raise ProjectionRefused(cid, anchor, resolution["reason"])
                row["withheld_reason"] = f"unresolvable-evidence:{resolution['reason']}"
                withheld.append(row)
                continue
            row["line"] = verified_line(cid, text)
            verified_rows.append(row)
            continue
        reason = f"status:{status}" if status in TAGGED_STATUSES else f"unknown-status:{status}"
        if status not in TAGGED_STATUSES:
            row["withheld_reason"] = reason
            withheld.append(row)
            continue
        row["withheld_reason"] = reason
        row["line"] = tagged_line(status, cid, text)
        tagged_rows.append(row)
        withheld.append(row)

    withheld_by_status = {
        status: {
            "count": sum(1 for r in withheld if r["status"] == status),
            "reason": (
                "status:VERIFIED — evidence string did not resolve to a file"
                if status == VERIFIED
                else f"status:{status} — excluded from verified section"
            ),
            "ids": [r["id"] for r in withheld if r["status"] == status],
        }
        for status in STATUS_VOCABULARY
        if any(r["status"] == status for r in withheld)
    }

    return {
        "claim_count": len(claims),
        "eligible": by_status[VERIFIED],
        "emitted_verified": len(verified_rows),
        "emitted_tagged": len(tagged_rows),
        "withheld_count": len(withheld),
        "by_status": dict(by_status),
        "verified": verified_rows,
        "tagged": tagged_rows,
        "withheld": withheld,
        "withheld_by_status": withheld_by_status,
    }


def _body(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_None._\n"
    return "\n".join(r["line"] for r in rows) + "\n"


def render_changelog(projection: dict[str, Any], *, version_line: str) -> str:
    return (
        "# Changelog\n"
        f"{version_line}\n"
        "\n"
        f"{VERIFIED_HEADER}\n"
        "\n"
        f"{_body(projection['verified'])}"
        "\n"
        f"{TAGGED_HEADER}\n"
        "\n"
        "Items below are withheld from the verified section. The status tag "
        "is inline beside each item.\n"
        "\n"
        f"{_body(projection['tagged'])}"
    )


def render_release_notes(projection: dict[str, Any], *, version_line: str) -> str:
    return (
        "# Release notes\n"
        f"{version_line}\n"
        "Projected from the claim registry. Verified sentences are those whose "
        "claim is VERIFIED and whose evidence anchor resolves on disk.\n"
        "\n"
        f"{VERIFIED_HEADER}\n"
        "\n"
        f"{_body(projection['verified'])}"
        "\n"
        f"{TAGGED_HEADER}\n"
        "\n"
        f"{_body(projection['tagged'])}"
    )


def section_lines(text: str, header: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == header:
            in_section = True
            continue
        if in_section and line.startswith("## ") and line.strip() != header:
            break
        if in_section:
            out.append(line)
    return out


def parse_claim_lines(text: str, header: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in section_lines(text, header):
        if not line.startswith("- "):
            continue
        match = CLAIM_LINE_RE.match(line)
        if not match:
            raise ValueError(f"claim line missing source id: {line}")
        rows.append(
            {
                "status_tag": match.group(1) or VERIFIED,
                "id": match.group(2),
                "text": match.group(3),
                "line": line,
            }
        )
    return rows


def verified_ids_in_notes(text: str) -> list[str]:
    return [row["id"] for row in parse_claim_lines(text, VERIFIED_HEADER)]


def freshness_ok(actual: str, expected: str) -> bool:
    return actual.replace("\r\n", "\n") == expected.replace("\r\n", "\n")


def version_line_for(repo: Path) -> tuple[str, dict[str, Any]]:
    rel = "command-center/receipts/REL-0001.json"
    path = repo / rel
    meta: dict[str, Any] = {
        "source_unit": "REL-0001",
        "path": rel,
        "status": "NOT-CHECKED",
        "reason": "REL-0001 receipt absent on this tree",
        "value": None,
    }
    if path.is_file() and path.stat().st_size > 0:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            meta["reason"] = f"unparseable:{type(exc).__name__}"
        else:
            value = (
                doc.get("version")
                or doc.get("derived_version")
                or (doc.get("gate") or {}).get("version")
            )
            if isinstance(value, dict):
                value = value.get("value") or value.get("version")
            if value:
                meta["status"] = "CHECKED"
                meta["reason"] = "read from REL-0001 receipt"
                meta["value"] = str(value)
    if meta["value"]:
        return f"Version: {meta['value']}", meta
    return f"Version: NOT-CHECKED ({meta['reason']})", meta


def project_files(
    registry: dict[str, Any],
    repo: Path,
    changelog_path: Path,
    notes_path: Path,
) -> dict[str, Any]:
    projection = project(registry, repo)
    version_line, version_meta = version_line_for(repo)
    changelog = render_changelog(projection, version_line=version_line)
    notes = render_release_notes(projection, version_line=version_line)
    changelog_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    changelog_path.write_text(changelog, encoding="utf-8", newline="\n")
    notes_path.write_text(notes, encoding="utf-8", newline="\n")
    projection["changelog"] = changelog
    projection["release_notes"] = notes
    projection["version"] = version_meta
    projection["version_line"] = version_line
    return projection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="REL-0016 claim-registry projector")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=REPO)
    parser.add_argument("--changelog", type=Path)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--check-fresh", action="store_true")
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry)
        projection = project(registry, args.repo)
    except ProjectionRefused as exc:
        print(str(exc))
        return 2
    version_line, _ = version_line_for(args.repo)
    expected_changelog = render_changelog(projection, version_line=version_line)
    expected_notes = render_release_notes(projection, version_line=version_line)
    if args.check_fresh:
        if args.changelog is None or args.notes is None:
            print("FAILED: --check-fresh requires --changelog and --notes")
            return 1
        actual_c = args.changelog.read_text(encoding="utf-8")
        actual_n = args.notes.read_text(encoding="utf-8")
        ok_c = freshness_ok(actual_c, expected_changelog)
        ok_n = freshness_ok(actual_n, expected_notes)
        if ok_c and ok_n:
            print("SUCCESS:fresh")
            return 0
        print("FAILED:fresh changelog_match=" + str(ok_c) + " notes_match=" + str(ok_n))
        return 1
    if args.changelog:
        args.changelog.parent.mkdir(parents=True, exist_ok=True)
        args.changelog.write_text(expected_changelog, encoding="utf-8", newline="\n")
    if args.notes:
        args.notes.parent.mkdir(parents=True, exist_ok=True)
        args.notes.write_text(expected_notes, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "eligible": projection["eligible"],
                "emitted_verified": projection["emitted_verified"],
                "withheld_count": projection["withheld_count"],
                "by_status": projection["by_status"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:project")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
