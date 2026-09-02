#!/usr/bin/env python3
"""Cross-vendor meta-review reconciliation protocol for SYN-0026.

Agreement is recorded as AGREE. Disagreement is CONTEST and must cite a
raw source anchor. Neither side may close the other's finding unilaterally.
A same-vendor reviewer is rejected. Reviewers who authored a synthesis
candidate under review are disqualified.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
UNIT_ID = "SYN-0026"
SCHEMA_REL = "command-center/schema/meta-review-finding.schema.json"
OUT_REL = "command-center/synthesis/SYN-0026.cross-vendor-meta-review.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0026/probe1_vendor_differs.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/SYN-0026/probe2_unilateral_and_severed.py"
)

AGREE = "AGREE"
CONTEST = "CONTEST"
PLANTED_CONTEST_REL = (
    "command-center/p2-wave/probes/SYN-0026/fixtures/planted-contest.json"
)


class SameVendorReviewError(ValueError):
    pass


class UnilateralCloseError(ValueError):
    pass


class ReviewerAuthoredError(ValueError):
    pass


class ContestAnchorError(ValueError):
    pass


@dataclass
class Verdict:
    vendor: str
    label: str
    model: str = ""
    role: str = ""
    path: str = ""
    present: bool = False
    bytes: int = 0
    sha256: str | None = None
    parsed: bool = False
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Reconciliation:
    status: str
    first: Verdict
    second: Verdict
    raw_anchor: str | None
    open: bool

    def close_unilaterally(self, side: str) -> None:
        if self.status == CONTEST:
            raise UnilateralCloseError(
                f"{side} may not close a CONTEST; escalate to raw source "
                f"({self.raw_anchor or 'anchor-missing'})"
            )
        raise UnilateralCloseError(
            f"{side} cannot unilaterally close even an AGREE; both sides remain on the record"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "first": self.first.to_dict(),
            "second": self.second.to_dict(),
            "raw_anchor": self.raw_anchor,
            "open": self.open,
        }


def load_catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def index_units(doc: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    data = doc if doc is not None else load_catalog()
    out: dict[str, dict[str, Any]] = {}
    for unit in data.get("work_units") or []:
        if isinstance(unit, dict) and isinstance(unit.get("id"), str):
            out[unit["id"]] = unit
    return out


def amvr(unit: dict[str, Any]) -> dict[str, str]:
    raw = unit.get("assigned_model_vendor_role") or {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "vendor": str(raw.get("vendor") or ""),
        "model": str(raw.get("model") or ""),
        "role": str(raw.get("role") or ""),
    }


def other_vendor(author_vendor: str) -> str:
    a = (author_vendor or "").strip().lower()
    if a == "openai":
        return "anthropic"
    if a == "anthropic":
        return "openai"
    if not a:
        raise SameVendorReviewError("author vendor missing; cannot assign other vendor")
    return "openai" if a != "openai" else "anthropic"


def assign_reviewer(
    author_vendor: str,
    reviewer_vendor: str,
    reviewer_id: str,
    author_ids: set[str],
) -> str:
    if not (author_vendor or "").strip() or not (reviewer_vendor or "").strip():
        raise SameVendorReviewError("author and reviewer vendors are required")
    if author_vendor.strip().lower() == reviewer_vendor.strip().lower():
        raise SameVendorReviewError(
            f"reviewer vendor {reviewer_vendor!r} equals author vendor {author_vendor!r}"
        )
    if reviewer_id in author_ids:
        raise ReviewerAuthoredError(
            f"reviewer {reviewer_id!r} authored a synthesis candidate under review"
        )
    return reviewer_vendor.strip().lower()


def reconcile(first: Verdict, second: Verdict, raw_anchor: str | None = None) -> Reconciliation:
    if first.label == second.label:
        return Reconciliation(
            status=AGREE,
            first=first,
            second=second,
            raw_anchor=None,
            open=False,
        )
    if not raw_anchor or len(raw_anchor) < 8:
        raise ContestAnchorError(
            "CONTEST requires a raw source anchor; neither side may settle it by vote"
        )
    return Reconciliation(
        status=CONTEST,
        first=first,
        second=second,
        raw_anchor=raw_anchor,
        open=True,
    )


def planted_contest() -> Reconciliation:
    dest = REPO / PLANTED_CONTEST_REL
    first = Verdict(
        vendor="anthropic",
        label="SUCCESS",
        role="first-vendor-lens",
        path=PLANTED_CONTEST_REL,
        present=True,
        excerpt="first_label=SUCCESS",
    )
    second = Verdict(
        vendor="openai",
        label="FAILED",
        role="second-vendor-reviewer",
        path=PLANTED_CONTEST_REL,
        present=True,
        excerpt="second_label=FAILED",
    )
    lines = dest.read_text(encoding="utf-8").splitlines()
    line_no = 1
    for i, line in enumerate(lines, 1):
        if "first_label" in line or "second_label" in line:
            line_no = i
            break
    return reconcile(first, second, raw_anchor=f"{PLANTED_CONTEST_REL}:{line_no}")


def lens_ids_for_unit(units: dict[str, dict[str, Any]]) -> list[str]:
    deps = units[UNIT_ID].get("dependencies") or []
    return [d for d in deps if isinstance(d, str) and d.startswith("SYN-")]


def first_vendor_from_disk(unit: dict[str, Any]) -> Verdict:
    info = amvr(unit)
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    from dispatch import observe_output  # local import: dispatch must not import protocol

    obs = observe_output(rel)
    return Verdict(
        vendor=info["vendor"],
        label=str(obs["label"]),
        model=info["model"],
        role=info["role"] or "lens-author",
        path=rel,
        present=bool(obs["present"]),
        bytes=int(obs["bytes"] or 0),
        sha256=obs.get("sha256"),
        parsed=bool(obs.get("parsed")),
        excerpt=str(obs.get("excerpt") or ""),
    )


def second_vendor_from_dispatch(unit: dict[str, Any], rec: dict[str, Any], parsed: dict[str, Any] | None) -> Verdict:
    info = amvr(unit)
    reviewer = rec.get("reviewer_vendor") or other_vendor(info["vendor"])
    label = "DISPATCH-FAILED"
    excerpt = rec.get("diagnostic_tail") or rec.get("classification") or ""
    present = False
    sha = None
    parsed_ok = False
    nbytes = int(rec.get("output_bytes") or 0)
    if parsed and rec.get("counts_as_result"):
        label = str(parsed.get("verdict") or label)
        excerpt = str(parsed.get("excerpt") or excerpt)
        present = bool(parsed.get("output_present"))
        sha = parsed.get("sha256")
        parsed_ok = True
        nbytes = int(parsed.get("output_bytes") or nbytes)
    return Verdict(
        vendor=str(reviewer),
        label=label,
        model="mechanical-confirmer",
        role="second-vendor-reviewer",
        path=str(unit.get("output_path") or ""),
        present=present,
        bytes=nbytes,
        sha256=sha,
        parsed=parsed_ok,
        excerpt=str(excerpt),
    )


def contest_anchor(first: Verdict, second: Verdict) -> str:
    return (
        f"{first.path}:disk first.label={first.label} "
        f"first.sha={first.sha256 or 'none'} second.label={second.label} "
        f"second.sha={second.sha256 or 'none'}"
    )


def review_one_lens(
    unit: dict[str, Any],
    author_ids: set[str],
    dispatch_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from dispatch import run_confirmer, write_prompt

    info = amvr(unit)
    lens_id = str(unit["id"])
    reviewer_vendor = other_vendor(info["vendor"])
    reviewer_id = f"{UNIT_ID}-second-{reviewer_vendor}-{lens_id}"
    assign_reviewer(info["vendor"], reviewer_vendor, reviewer_id, author_ids)
    rel = str(unit.get("output_path") or "").replace("\\", "/")
    prompt = write_prompt(
        dispatch_dir / f"{lens_id}.prompt.txt",
        lens_id,
        rel,
        info["vendor"],
        reviewer_vendor,
    )
    rec = run_confirmer(
        reviewer_vendor,
        prompt,
        dispatch_dir / f"{lens_id}.json",
        mode="complete",
        lens_id=lens_id,
    )
    parsed = None
    outp = REPO / rec["output_path"] if rec.get("output_path") else None
    if rec.get("parsed") and outp and outp.is_file():
        parsed = json.loads(outp.read_text(encoding="utf-8"))
    first = first_vendor_from_disk(unit)
    second = second_vendor_from_dispatch(unit, rec, parsed)
    if first.label != second.label:
        recon = reconcile(first, second, contest_anchor(first, second))
    else:
        recon = reconcile(first, second, None)
    row = {
        "lens_id": lens_id,
        "title": str(unit.get("title") or ""),
        "output_path": rel,
        "author_vendor": info["vendor"],
        "author_model": info["model"],
        "author_role": info["role"],
        "reviewer_vendor": reviewer_vendor,
        "reviewer_id": reviewer_id,
        "first_vendor_verdict": first.to_dict(),
        "second_vendor_verdict": second.to_dict(),
        "reconciliation": recon.status,
        "raw_anchor": recon.raw_anchor,
        "open": recon.open,
        "unilateral_close": "forbidden-on-CONTEST",
    }
    return row, rec


def run_severed_control(dispatch_dir: Path) -> dict[str, Any]:
    from dispatch import run_confirmer, write_prompt, terminal_state

    prompt = write_prompt(
        dispatch_dir / "PLANT-SEVERED.prompt.txt",
        "SYN-0014",
        "command-center/receipts/SYN-0014.json",
        "anthropic",
        "openai",
    )
    rec = run_confirmer(
        "openai",
        prompt,
        dispatch_dir / "PLANT-SEVERED.json",
        mode="severed",
        lens_id="PLANT-SEVERED",
    )
    rec["terminal_state"] = terminal_state(rec)
    rec["id"] = "planted-severed-stream"
    return rec


def build_rosters(
    units: dict[str, dict[str, Any]], lens_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    authors: list[dict[str, str]] = []
    seen_a: set[str] = set()
    syn8 = units.get("SYN-0008")
    if syn8:
        info = amvr(syn8)
        rid = "SYN-0008"
        authors.append(
            {
                "id": rid,
                "vendor": info["vendor"],
                "role": "synthesis-candidate-author",
                "model": info["model"],
            }
        )
        seen_a.add(rid)
    for row in lens_rows:
        aid = row["lens_id"]
        if aid not in seen_a:
            authors.append(
                {
                    "id": aid,
                    "vendor": row["author_vendor"],
                    "role": "lens-author",
                    "model": row.get("author_model") or "",
                }
            )
            seen_a.add(aid)
    reviewers: list[dict[str, str]] = []
    seen_r: set[str] = set()
    for row in lens_rows:
        rid = row["reviewer_id"]
        if rid not in seen_r:
            reviewers.append(
                {
                    "id": rid,
                    "vendor": row["reviewer_vendor"],
                    "role": "second-vendor-reviewer",
                }
            )
            seen_r.add(rid)
    author_ids = {a["id"] for a in authors}
    reviewer_ids = {r["id"] for r in reviewers}
    intersection = sorted(author_ids & reviewer_ids)
    return authors, reviewers, intersection


def assert_vendor_differs(lens_rows: list[dict[str, Any]]) -> None:
    for row in lens_rows:
        a = str(row.get("author_vendor") or "").strip().lower()
        r = str(row.get("reviewer_vendor") or "").strip().lower()
        if not a or not r or a == r:
            raise SameVendorReviewError(
                f"{row.get('lens_id')} reviewer_vendor={r!r} author_vendor={a!r}"
            )
        second = (row.get("second_vendor_verdict") or {}).get("vendor") or ""
        if str(second).strip().lower() != r:
            raise SameVendorReviewError(
                f"{row.get('lens_id')} second-vendor verdict vendor {second!r} "
                f"!= reviewer {r!r}"
            )


def assert_contests_anchored_and_open(lens_rows: list[dict[str, Any]]) -> None:
    for row in lens_rows:
        if row.get("reconciliation") != CONTEST:
            continue
        anchor = row.get("raw_anchor")
        if not isinstance(anchor, str) or len(anchor) < 8:
            raise ContestAnchorError(f"{row.get('lens_id')} CONTEST missing raw_anchor")
        if row.get("open") is False:
            raise UnilateralCloseError(
                f"{row.get('lens_id')} CONTEST was closed; unilateral close is forbidden"
            )


def source_anchor(rel: str, needle: str) -> str:
    lines = (REPO / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return f"{rel}:{i}"
    raise RuntimeError(f"missing anchor {needle!r} in {rel}")


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Merge report/extensions over top-level so probes read receipt_core docs.

    receipt_core sets additionalProperties=false, so lenses, rosters and
    dispatch_control live under report (and optionally extensions).
    """
    merged: dict[str, Any] = {}
    if not isinstance(doc, dict):
        return merged
    merged.update(doc)
    ext = doc.get("extensions")
    if isinstance(ext, dict):
        merged.update(ext)
    report = doc.get("report")
    if isinstance(report, dict):
        merged.update(report)
    return merged
