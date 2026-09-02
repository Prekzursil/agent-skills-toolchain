#!/usr/bin/env python3
"""CNF-0014 coverage-board generator and hand-edit gate.

The board is a pure function of receipts on disk, the claim population, the
producing commit, and this generator version. Numbers are never hand-typed.
A human who edits one digit in the tallies is caught because the gate
recomputes the tallies from receipts and compares.

Empty corpus: measured=0, board_color=NOT-GREEN. Zero of N is not a pass,
including 0 of 0.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]

GENERATOR_ID = "cnf-0014-coverage-board"
GENERATOR_VERSION = "1.0.0"
RECEIPTS_ROOT = "command-center/confirmation/receipts"
CLAIM_REGISTRY = "command-center/CLAIM-REGISTRY.json"
STATUS_MD = "command-center/STATUS.md"
ARTIFACT_MANIFEST = "command-center/ARTIFACT-MANIFEST.json"
CATALOG = "command-center/WORK-UNIT-CATALOG.json"

VERDICTS = (
    "confirmed",
    "refuted",
    "partial",
    "not_checked",
    "blocked",
    "stale",
)
VERDICT_MAP = {
    "CONFIRMED": "confirmed",
    "REFUTED": "refuted",
    "PARTIAL": "partial",
    "NOT-CHECKED": "not_checked",
    "NOT_CHECKED": "not_checked",
    "BLOCKED": "blocked",
    "STALE": "stale",
}
SEVERITY_ORDER = ("P0", "P1", "P2", "P3", "UNSET")

CATALOG_SENTINEL = (
    "SUCCESS:CNF-0014 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the hand-edit control "
    "went red and the unchanged regeneration was byte-identical. Any other "
    "terminal state is FAILED:CNF-0014 <classification> with the diagnostic "
    "tail attached."
)
QUESTION = (
    "Implementation target: generate the Phase 11 coverage board purely from "
    "receipts on disk - claims by severity, confirmed, refuted, partial, "
    "not-checked, blocked, stale - stamp it with the commit that produced it, "
    "and fail the build if a human edits a number in the board directly. "
    "Question: does the hand-edit detector fire when one digit is changed by hand?"
)


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def empty_tally() -> dict[str, int]:
    row = {k: 0 for k in VERDICTS}
    row["claims_n"] = 0
    row["measured"] = 0
    return row


def producing_commit(repo: Path | None = None) -> str:
    root = repo or REPO
    try:
        p = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "NO-GIT"
    sha = (p.stdout or "").strip()
    if p.returncode == 0 and sha:
        return sha
    return "NO-GIT"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _claim_id(doc: dict[str, Any]) -> str | None:
    for key in ("claim_id", "id"):
        val = doc.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _severity(doc: dict[str, Any]) -> str:
    raw = doc.get("severity") or doc.get("priority")
    if isinstance(raw, str) and raw.strip():
        s = raw.strip().upper()
        if s in SEVERITY_ORDER:
            return s
        if s.startswith("P") and s[1:].isdigit():
            return s
        return "UNSET"
    return "UNSET"


def effective_verdict(receipt: dict[str, Any]) -> str:
    """CNF-0012: CONFIRMED with no input hashes is STALE, not a pass."""
    raw = str(receipt.get("verdict") or "NOT-CHECKED").strip().upper()
    key = VERDICT_MAP.get(raw, "not_checked")
    hashes = receipt.get("input_hashes")
    if key == "confirmed" and not hashes:
        return "stale"
    return key


def load_claims(registry_path: Path | None) -> list[dict[str, Any]]:
    if registry_path is None or not registry_path.is_file():
        return []
    try:
        doc = load_json(registry_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    rows: list[Any]
    if isinstance(doc, list):
        rows = doc
    elif isinstance(doc, dict):
        for key in ("claims", "items", "records"):
            if isinstance(doc.get(key), list):
                rows = doc[key]
                break
        else:
            return []
    else:
        return []
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        cid = _claim_id(item)
        if cid is None or cid in seen:
            continue
        seen.add(cid)
        claims.append({"claim_id": cid, "severity": _severity(item)})
    claims.sort(key=lambda c: (c["severity"], c["claim_id"]))
    return claims


def is_confirmation_receipt(doc: dict[str, Any]) -> bool:
    """P2 unit artifacts often have `id` plus a prose `verdict`. Those are not
    confirmation receipts. A confirmation receipt names a claim_id and uses a
    confirmation-enum verdict (CONFIRMED/REFUTED/PARTIAL/NOT-CHECKED/BLOCKED/STALE).
    """
    cid = doc.get("claim_id")
    if not isinstance(cid, str) or not cid.strip():
        return False
    raw = str(doc.get("verdict") or "").strip().upper()
    return raw in VERDICT_MAP


def load_receipts(corpus_root: Path) -> list[dict[str, Any]]:
    if not corpus_root.is_dir():
        return []
    found: list[dict[str, Any]] = []
    for path in sorted(corpus_root.rglob("*.json")):
        if path.name.endswith("-coverage-board.json"):
            continue
        try:
            doc = load_json(path)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        if not is_confirmation_receipt(doc):
            continue
        rec = dict(doc)
        rec["_path"] = path.relative_to(corpus_root).as_posix()
        found.append(rec)
    return found


def write_receipts_dir(receipts: list[dict[str, Any]], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for rec in receipts:
        body = {k: v for k, v in rec.items() if k != "_path"}
        name = rec.get("_path") or f"{body['claim_id']}.json"
        target = dest / str(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(canonical_bytes(body))


def write_claims(claims: list[dict[str, Any]], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(canonical_bytes({"claims": claims}))


def population(
    claims: list[dict[str, Any]], receipts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for c in claims:
        cid = c["claim_id"]
        by_id[cid] = {"claim_id": cid, "severity": _severity(c)}
    for rec in receipts:
        cid = _claim_id(rec)
        if cid is None:
            continue
        if cid not in by_id:
            by_id[cid] = {"claim_id": cid, "severity": _severity(rec)}
    return sorted(by_id.values(), key=lambda c: (c["severity"], c["claim_id"]))


def receipts_fingerprint(receipts: list[dict[str, Any]]) -> str:
    payload = []
    for rec in receipts:
        body = {k: v for k, v in rec.items() if k != "_path"}
        payload.append(
            {
                "path": rec.get("_path") or body.get("claim_id"),
                "body": body,
            }
        )
    payload.sort(key=lambda r: str(r["path"]))
    return digest_bytes(canonical_bytes(payload))


def _latest_receipt(
    receipts: list[dict[str, Any]], claim_id: str
) -> dict[str, Any] | None:
    matches = [r for r in receipts if _claim_id(r) == claim_id]
    if not matches:
        return None
    return matches[-1]


def tally_coverage(
    claims: list[dict[str, Any]], receipts: list[dict[str, Any]]
) -> tuple[dict[str, int], dict[str, dict[str, int]], list[dict[str, Any]]]:
    pop = population(claims, receipts)
    totals = empty_tally()
    by_sev: dict[str, dict[str, int]] = {}
    rows: list[dict[str, Any]] = []
    for claim in pop:
        cid = claim["claim_id"]
        sev = claim["severity"]
        if sev not in by_sev:
            by_sev[sev] = empty_tally()
        rec = _latest_receipt(receipts, cid)
        totals["claims_n"] += 1
        by_sev[sev]["claims_n"] += 1
        if rec is None:
            bucket = "not_checked"
            measured = False
        else:
            bucket = effective_verdict(rec)
            measured = True
        totals[bucket] += 1
        by_sev[sev][bucket] += 1
        if measured:
            totals["measured"] += 1
            by_sev[sev]["measured"] += 1
        rows.append(
            {
                "claim_id": cid,
                "severity": sev,
                "verdict": bucket.upper().replace("_", "-")
                if bucket != "not_checked"
                else "NOT-CHECKED",
                "measured": measured,
                "receipt_path": None if rec is None else rec.get("_path"),
            }
        )
    ordered = {k: by_sev[k] for k in SEVERITY_ORDER if k in by_sev}
    for extra in sorted(set(by_sev) - set(SEVERITY_ORDER)):
        ordered[extra] = by_sev[extra]
    return totals, ordered, rows


def board_is_green(totals: dict[str, int]) -> bool:
    if totals["claims_n"] <= 0 or totals["measured"] <= 0:
        return False
    if totals["measured"] != totals["claims_n"]:
        return False
    if totals["confirmed"] != totals["claims_n"]:
        return False
    for key in ("refuted", "partial", "not_checked", "blocked", "stale"):
        if totals[key] != 0:
            return False
    return True


def render_coverage(
    receipts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    commit: str,
) -> dict[str, Any]:
    """Pure coverage projection. Same inputs => byte-identical JSON."""
    totals, by_sev, rows = tally_coverage(claims, receipts)
    green = board_is_green(totals)
    label = f"{totals['measured']} of {totals['claims_n']} measured"
    return {
        "board_color": "GREEN" if green else "NOT-GREEN",
        "empty_set_is_not_pass": True,
        "generator_id": GENERATOR_ID,
        "generator_version": GENERATOR_VERSION,
        "green": green,
        "measured_label": label,
        "producing_commit": commit,
        "receipts_fingerprint": receipts_fingerprint(receipts),
        "rows": rows,
        "by_severity": by_sev,
        "tallies": totals,
    }


def mutate_one_digit(raw: bytes) -> bytes:
    """Change exactly one decimal digit inside the tallies object."""
    text = raw.decode("utf-8")
    marker = '"tallies"'
    start = text.find(marker)
    if start < 0:
        raise ValueError("tallies-object-absent")
    brace = text.find("{", start)
    if brace < 0:
        raise ValueError("tallies-brace-absent")
    depth = 0
    end = None
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end is None:
        raise ValueError("tallies-unclosed")
    for i in range(brace, end + 1):
        if text[i].isdigit():
            new = str((int(text[i]) + 1) % 10)
            return (text[:i] + new + text[i + 1 :]).encode("utf-8")
    raise ValueError("no-digit-in-tallies")


COVERAGE_KEYS = (
    "board_color",
    "empty_set_is_not_pass",
    "generator_id",
    "generator_version",
    "green",
    "measured_label",
    "producing_commit",
    "receipts_fingerprint",
    "rows",
    "by_severity",
    "tallies",
)


def coverage_view(board: dict[str, Any]) -> dict[str, Any]:
    """Read coverage fields from the board root or from report.

    Schema-valid receipts keep numbers under report (receipt_core
    additionalProperties is false). The hand-edit gate still has to see
    them. Top-level keys win when present so a one-digit edit of a
    visible tallies object is observed.
    """
    if not isinstance(board, dict):
        return {}
    rpt = board.get("report") if isinstance(board.get("report"), dict) else {}
    out: dict[str, Any] = {}
    for key in COVERAGE_KEYS:
        if key in rpt:
            out[key] = rpt[key]
        if key in board:
            out[key] = board[key]
    return out


def check_board(
    board: dict[str, Any],
    receipts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    commit: str,
) -> dict[str, Any]:
    """Recompute from receipts. Do not trust numbers written in the board."""
    expected = render_coverage(receipts, claims, commit)
    got = coverage_view(board)
    got_t = got.get("tallies")
    got_s = got.get("by_severity")
    got_label = got.get("measured_label")
    got_color = got.get("board_color")
    got_green = got.get("green")
    reasons: list[str] = []
    if got_t != expected["tallies"]:
        reasons.append("tally-mismatch")
    if got_s != expected["by_severity"]:
        reasons.append("severity-tally-mismatch")
    if got_label != expected["measured_label"]:
        reasons.append("measured-label-mismatch")
    if got_color != expected["board_color"]:
        reasons.append("board-color-mismatch")
    if got_green != expected["green"]:
        reasons.append("green-flag-mismatch")
    if expected["green"] is True and expected["tallies"]["measured"] == 0:
        reasons.append("empty-set-read-as-pass")
    ok = not reasons
    return {
        "ok": ok,
        "status": "SILENT" if ok else "RED",
        "exit_code": 0 if ok else 1,
        "reasons": reasons,
        "expected_tallies": expected["tallies"],
        "observed_tallies": got_t,
    }


def generator_anchor() -> dict[str, Any]:
    src = inspect.getsourcefile(render_coverage)
    line = inspect.getsourcelines(render_coverage)[1]
    path = Path(src or __file__).resolve()
    try:
        rel = path.relative_to(REPO).as_posix()
    except ValueError:
        rel = path.as_posix()
    return {
        "path": rel,
        "line": int(line),
        "function": "render_coverage",
        "id": GENERATOR_ID,
        "version": GENERATOR_VERSION,
    }


def two_run_identical(
    receipts: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    commit: str,
) -> tuple[bool, bytes, bytes]:
    a = canonical_bytes(render_coverage(receipts, claims, commit))
    b = canonical_bytes(render_coverage(receipts, claims, commit))
    return a == b, a, b


def run_controls() -> dict[str, Any]:
    """In-process detector controls used by emit and named probes."""
    from sample import CLAIMS, EXPECTED_TALLIES, FIXTURE_COMMIT, RECEIPTS

    identical, a, b = two_run_identical(RECEIPTS, CLAIMS, FIXTURE_COMMIT)
    coverage = json.loads(a.decode("utf-8"))
    if coverage["tallies"] != EXPECTED_TALLIES:
        raise AssertionError(
            f"fixture tallies drifted: {coverage['tallies']} != {EXPECTED_TALLIES}"
        )
    silent = check_board(coverage, RECEIPTS, CLAIMS, FIXTURE_COMMIT)
    mutated_raw = mutate_one_digit(a)
    mutated = json.loads(mutated_raw.decode("utf-8"))
    red = check_board(mutated, RECEIPTS, CLAIMS, FIXTURE_COMMIT)
    empty = render_coverage([], CLAIMS, FIXTURE_COMMIT)
    empty00 = render_coverage([], [], FIXTURE_COMMIT)
    if empty["green"] or empty["board_color"] != "NOT-GREEN":
        raise AssertionError("empty corpus rendered green")
    if empty00["green"] or empty00["board_color"] != "NOT-GREEN":
        raise AssertionError("0-of-0 rendered green")
    if not red["reasons"] or red["exit_code"] == 0:
        raise AssertionError("hand-edit gate did not go red")
    if not silent["ok"] or silent["exit_code"] != 0:
        raise AssertionError("unedited board was not silent")
    if not identical or a != b:
        raise AssertionError("two-run bytes differ")
    return {
        "hand_edit": {
            "gate_red": True,
            "exit_code": int(red["exit_code"]),
            "silent_on_unedited": True,
            "reasons": red["reasons"],
            "digit_changed": True,
        },
        "determinism": {
            "two_run_byte_identical": True,
            "sha256": digest_bytes(a),
            "bytes": len(a),
        },
        "empty_corpus": {
            "measured_label": empty["measured_label"],
            "green": False,
            "board_color": "NOT-GREEN",
            "claims_n": empty["tallies"]["claims_n"],
            "measured": empty["tallies"]["measured"],
            "zero_of_zero_label": empty00["measured_label"],
            "zero_of_zero_green": False,
        },
    }


def observe_inputs(repo: Path | None = None) -> dict[str, Any]:
    root = repo or REPO
    receipts_dir = root / RECEIPTS_ROOT
    alt = root / "command-center" / "receipts"
    registry = root / CLAIM_REGISTRY
    cnf_n = 0
    cat = root / CATALOG
    if cat.is_file():
        try:
            data = load_json(cat)
            for unit in data.get("work_units") or []:
                if isinstance(unit, dict) and str(unit.get("id") or "").startswith(
                    "CNF-"
                ):
                    cnf_n += 1
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            cnf_n = 0
    return {
        "artifact_manifest": {
            "path": ARTIFACT_MANIFEST,
            "present": (root / ARTIFACT_MANIFEST).is_file(),
        },
        "catalog_cnf_units": cnf_n,
        "claim_registry": {"path": CLAIM_REGISTRY, "present": registry.is_file()},
        "receipts_roots": [
            {
                "path": RECEIPTS_ROOT,
                "present": receipts_dir.is_dir(),
                "ingested": True,
                "role": "confirmation-receipt-corpus",
            },
            {
                "path": "command-center/receipts",
                "present": alt.is_dir(),
                "ingested": False,
                "role": "p2-unit-artifacts-not-confirmation-receipts",
            },
        ],
        "status_md": {"path": STATUS_MD, "present": (root / STATUS_MD).is_file()},
    }


def load_live_corpus(
    repo: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Load the confirmation receipt corpus only.

    command-center/receipts holds P2 unit artifacts. Sibling deliveries there
    must not change this board's tallies (that is a false red, not a hand-edit).
    """
    root = repo or REPO
    receipts = load_receipts(root / RECEIPTS_ROOT)
    claims = load_claims(root / CLAIM_REGISTRY)
    return receipts, claims
