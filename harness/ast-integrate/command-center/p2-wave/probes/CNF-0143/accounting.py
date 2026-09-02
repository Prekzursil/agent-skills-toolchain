#!/usr/bin/env python3
"""Non-response accounting: pass rates WITH and WITHOUT BLOCKED in the denominator.

Dropping BLOCKED from the denominator is how a program reports a pass rate it
did not earn. Each BLOCKED record must name the missing prerequisite and the
experiment that would unblock it.

Formulas (per stratum S, integers then exact ratio):
  n_confirmed(S) = |{r in S : verdict == CONFIRMED}|
  n_blocked(S)   = |{r in S : verdict == BLOCKED}|
  n_all(S)       = |records in S|
  rate_with(S)    = n_confirmed / n_all                         if n_all > 0 else None
  rate_without(S) = n_confirmed / (n_all - n_blocked)           if n_all > n_blocked else None

Invariant A (arithmetic): n_blocked > 0  =>  rate_with != rate_without
  (identical rates with a non-empty BLOCKED set is a wiring bug).
Invariant B (known-absent): n_blocked == 0  =>  rate_with == rate_without
  (including both-None when n_all == 0).
Invariant C (completeness): every BLOCKED record has a non-empty prerequisite
  after strip; whitespace-only is empty.
"""
from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})
PASS_VERDICT = "CONFIRMED"
BLOCKED = "BLOCKED"
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CONTROL_SET = HERE / "fixtures" / "control-set.json"
RECORD_SCHEMA = HERE / "confirmation-record.schema.json"
OVERLAY_SCHEMA = HERE / "program-gate-report.overlay.schema.json"
PREREQ_MARKER = "CNF-0143-PREREQUISITE"
CATALOG_OUTPUT_SCHEMA = "command-center/schema/program-gate-report.schema.json"


class AccountingError(ValueError):
    pass


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def stratum_key(claim: dict) -> str:
    return "|".join(
        [
            str(claim.get("severity") or ""),
            str(claim.get("subsystem") or ""),
            str(claim.get("author_vendor") or ""),
            str(claim.get("claim_type") or ""),
        ]
    )


def prerequisite_of(record: dict) -> str:
    return str(record.get("prerequisite") or "").strip()


def require_blocked_prerequisite(record: dict) -> str:
    if str(record.get("verdict") or "") != BLOCKED:
        return prerequisite_of(record)
    pre = prerequisite_of(record)
    if not pre:
        raise AccountingError(
            f"BLOCKED record {record.get('claim_id')!r} has empty prerequisite"
        )
    exp = str(record.get("unblock_experiment") or "").strip()
    if not exp:
        raise AccountingError(
            f"BLOCKED record {record.get('claim_id')!r} has empty unblock_experiment"
        )
    return pre


def load_control_set(path: Path | None = None) -> dict:
    p = path or CONTROL_SET
    return json.loads(p.read_text(encoding="utf-8"))


def freeze_frame(frame: dict) -> dict:
    claims = list(frame.get("claims") or [])
    body = canonical_json({"claims": claims}).encode("utf-8")
    return {
        "kind": "content-sha256",
        "sha256": sha256_bytes(body),
        "n_claims": len(claims),
        "git_available": False,
        "git_commit": None,
        "note": (
            "Worktree is not a git repo; the sampling frame is frozen at the "
            "canonical JSON sha256 of its claims list, not a commit."
        ),
    }


def rate_view(confirmed: int, denominator: int) -> dict:
    if denominator <= 0:
        return {
            "defined": False,
            "confirmed": None,
            "denominator": 0,
            "as_string": None,
            "as_float": None,
            "fraction": None,
        }
    frac = Fraction(confirmed, denominator)
    return {
        "defined": True,
        "confirmed": confirmed,
        "denominator": denominator,
        "as_string": f"{confirmed}/{denominator}",
        "as_float": float(frac),
        "fraction": f"{frac.numerator}/{frac.denominator}",
    }


def _index_frame(frame: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for claim in frame.get("claims") or []:
        cid = str(claim.get("claim_id") or "")
        if not cid:
            raise AccountingError("frame claim missing claim_id")
        if cid in out:
            raise AccountingError(f"duplicate frame claim_id {cid}")
        if not str(claim.get("severity") or "").strip():
            raise AccountingError(
                f"frame claim {cid} missing severity (null-field must fail loudly)"
            )
        out[cid] = claim
    return out


def compute_rates(records: list[dict], frame: dict) -> dict:
    """Compute per-stratum and overall rates with and without BLOCKED."""
    claims = _index_frame(frame)
    by_stratum: dict[str, list[dict]] = {}
    unframed: list[str] = []
    blocked_entries: list[dict] = []
    not_checked: list[dict] = []

    for rec in records:
        cid = str(rec.get("claim_id") or "")
        verdict = str(rec.get("verdict") or "")
        if cid not in claims:
            unframed.append(cid or "<missing-claim_id>")
            continue
        if verdict not in VERDICTS:
            raise AccountingError(f"record {cid} has invalid verdict {verdict!r}")
        if verdict == BLOCKED:
            pre = require_blocked_prerequisite(rec)
            blocked_entries.append(
                {
                    "claim_id": cid,
                    "stratum_id": stratum_key(claims[cid]),
                    "prerequisite": pre,
                    "unblock_experiment": str(rec.get("unblock_experiment") or "").strip(),
                    "reason": str(rec.get("reason") or rec.get("class") or "").strip(),
                    "class": str(rec.get("class") or rec.get("reason") or "").strip(),
                }
            )
        if verdict == "NOT-CHECKED":
            not_checked.append(
                {
                    "claim_id": cid,
                    "stratum_id": stratum_key(claims[cid]),
                    "note": (
                        "NOT-CHECKED stays in BOTH denominators until it is "
                        "upgraded to BLOCKED with a named prerequisite"
                    ),
                }
            )
        sid = stratum_key(claims[cid])
        by_stratum.setdefault(sid, []).append(rec)

    if unframed:
        raise AccountingError(
            "records not in sampling frame (sampling-invalid): " + ", ".join(unframed)
        )

    def summarize(sid: str, recs: list[dict]) -> dict:
        n_all = len(recs)
        n_confirmed = sum(1 for r in recs if r.get("verdict") == PASS_VERDICT)
        n_blocked = sum(1 for r in recs if r.get("verdict") == BLOCKED)
        n_refuted = sum(1 for r in recs if r.get("verdict") == "REFUTED")
        n_partial = sum(1 for r in recs if r.get("verdict") == "PARTIAL")
        n_not_checked = sum(1 for r in recs if r.get("verdict") == "NOT-CHECKED")
        n_without = n_all - n_blocked
        rate_with = rate_view(n_confirmed, n_all)
        rate_without = rate_view(n_confirmed, n_without)
        differ = rate_with["as_string"] != rate_without["as_string"]
        return {
            "stratum_id": sid,
            "n_all": n_all,
            "n_confirmed": n_confirmed,
            "n_blocked": n_blocked,
            "n_refuted": n_refuted,
            "n_partial": n_partial,
            "n_not_checked": n_not_checked,
            "n_without_blocked": n_without,
            "rate_with_blocked_in_denominator": rate_with,
            "rate_without_blocked": rate_without,
            "rates_differ": differ,
            "claim_ids": sorted(str(r.get("claim_id")) for r in recs),
        }

    strata = [summarize(sid, by_stratum[sid]) for sid in sorted(by_stratum)]
    overall_recs = [r for recs in by_stratum.values() for r in recs]
    overall = summarize("OVERALL", overall_recs)
    framed_ids = set(claims)
    recorded_ids = {str(r.get("claim_id")) for r in overall_recs}
    missing_records = sorted(framed_ids - recorded_ids)

    invariants = assert_invariants(strata, overall)
    return {
        "frame_freeze": freeze_frame(frame),
        "n_frame_claims": len(claims),
        "n_records": len(overall_recs),
        "frame_claims_without_record": missing_records,
        "strata": strata,
        "overall": overall,
        "blocked": blocked_entries,
        "not_checked": not_checked,
        "invariants": invariants,
        "formula": {
            "rate_with_blocked_in_denominator": "n_confirmed / n_all",
            "rate_without_blocked": "n_confirmed / (n_all - n_blocked)",
            "pass_verdict": PASS_VERDICT,
            "note": (
                "rate_without_blocked is the unearned pass rate obtained by "
                "dropping BLOCKED from the denominator"
            ),
        },
    }


def assert_invariants(strata: list[dict], overall: dict) -> dict:
    """Arithmetic + known-absent controls. Raises AccountingError on wiring bugs."""
    checks = []

    def check_one(row: dict, label: str) -> None:
        n_b = int(row["n_blocked"])
        differ = bool(row["rates_differ"])
        with_s = row["rate_with_blocked_in_denominator"]["as_string"]
        without_s = row["rate_without_blocked"]["as_string"]
        if n_b > 0 and not differ:
            raise AccountingError(
                f"wiring bug: {label} has n_blocked={n_b} but identical rates "
                f"{with_s} == {without_s}"
            )
        if n_b == 0 and differ:
            raise AccountingError(
                f"known-absent violated: {label} has empty BLOCKED set but "
                f"rates differ {with_s} vs {without_s}"
            )
        checks.append(
            {
                "label": label,
                "n_blocked": n_b,
                "rate_with": with_s,
                "rate_without": without_s,
                "ok": True,
            }
        )

    for row in strata:
        check_one(row, row["stratum_id"])
    check_one(overall, "OVERALL")
    return {"ok": True, "checks": checks}


def wiring_bug_clone(result: dict) -> dict:
    """Mutant: both rates use n_all. Must be caught by assert_invariants."""
    clone = json.loads(json.dumps(result))
    for row in list(clone["strata"]) + [clone["overall"]]:
        n_all = int(row["n_all"])
        n_conf = int(row["n_confirmed"])
        same = rate_view(n_conf, n_all)
        row["rate_with_blocked_in_denominator"] = same
        row["rate_without_blocked"] = same
        row["rates_differ"] = False
    return clone


def crosscheck_unknowns(blocked: list[dict], markdown: str) -> dict:
    missing = []
    present = []
    for entry in blocked:
        pre = str(entry.get("prerequisite") or "").strip()
        if not pre:
            missing.append({"claim_id": entry.get("claim_id"), "prerequisite": pre})
            continue
        if pre in markdown:
            present.append(pre)
        else:
            missing.append(
                {"claim_id": entry.get("claim_id"), "prerequisite": pre}
            )
    return {
        "ok": not missing,
        "present_count": len(present),
        "missing": missing,
        "marker": PREREQ_MARKER,
    }


def render_unknowns_section(blocked: list[dict]) -> str:
    lines = [
        "# UNKNOWNS-REGISTER",
        "",
        "This file was absent on the worktree. CNF-0143 created it so every",
        "BLOCKED confirmation prerequisite is named with a settling experiment",
        "(catalog test: appear here or be added). Other lanes may append.",
        "Do not delete a CNF-0143-PREREQUISITE marker without replacing the token.",
        "",
        "## 1. OUTSTANDING",
        "",
        "### CNF-0143 non-response (unconfirmable claims)",
        "",
        "| id | claim_id | prerequisite | settling_experiment | owner_impact |",
        "| --- | --- | --- | --- | --- |",
    ]
    for i, entry in enumerate(blocked, 1):
        uid = f"U-CNF-0143-{i:03d}"
        pre = entry["prerequisite"]
        exp = entry["unblock_experiment"].replace("|", "/")
        impact = (
            "Until this prerequisite exists, dropping the claim from the "
            "pass-rate denominator reports a pass rate the program did not earn."
        )
        lines.append(f"| {uid} | {entry['claim_id']} | `{pre}` | {exp} | {impact} |")
        lines.append("")
        lines.append(f"<!-- {PREREQ_MARKER}: {pre} -->")
        lines.append("")
        lines.append(f"- prerequisite: {pre}")
        lines.append(f"- settling_experiment: {entry['unblock_experiment']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def ensure_unknowns(path: Path, blocked: list[dict]) -> dict:
    """Create or append so every BLOCKED prerequisite appears in the register."""
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    added = []
    text = existing
    if not text.strip():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_unknowns_section(blocked), encoding="utf-8")
        return {
            "path": str(path.as_posix()),
            "created": True,
            "added": [e["prerequisite"] for e in blocked],
            "already_present": [],
        }
    for entry in blocked:
        pre = entry["prerequisite"]
        if pre in text:
            continue
        block = (
            f"\n### CNF-0143 added {entry['claim_id']}\n\n"
            f"<!-- {PREREQ_MARKER}: {pre} -->\n\n"
            f"- prerequisite: {pre}\n"
            f"- settling_experiment: {entry['unblock_experiment']}\n"
            f"- owner_impact: Until this exists, dropping {entry['claim_id']} "
            f"from the pass-rate denominator is an unearned pass rate.\n"
        )
        text = text.rstrip() + "\n" + block
        added.append(pre)
    if added:
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    already = [e["prerequisite"] for e in blocked if e["prerequisite"] not in added]
    return {
        "path": str(path.as_posix()),
        "created": False,
        "added": added,
        "already_present": already,
    }


def validate_record_schema(record: dict) -> list[str]:
    import jsonschema

    schema = json.loads(RECORD_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    return [e.message for e in validator.iter_errors(record)]


_PREREQ_WS = re.compile(r"\S")


def record_schema_rejects_empty_prerequisite(record: dict) -> bool:
    errs = validate_record_schema(record)
    return bool(errs)


def overlay_validator():
    import jsonschema

    schema = json.loads(OVERLAY_SCHEMA.read_text(encoding="utf-8"))
    return jsonschema.Draft7Validator(schema)


def overlay_errors(doc: dict) -> list[str]:
    return [e.message for e in overlay_validator().iter_errors(doc)]


def catalog_schema_errors(doc: dict) -> list[str]:
    """Disk-only validation against the physical program-gate-report profile.

    platform/lib/schema_resolver.py needs jsonschema>=4.18 (`registry=`). This
    worktree has 4.10, so resolve the generated $ref shim from disk via
    RefResolver and never fetch ast-integrate.invalid.
    """
    import jsonschema
    from jsonschema import RefResolver

    profiles_path = REPO / "platform/schema/artifact-class-profiles.schema.json"
    receipt_path = REPO / "platform/schema/receipt.schema.json"
    shim_path = REPO / CATALOG_OUTPUT_SCHEMA
    profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    shim = json.loads(shim_path.read_text(encoding="utf-8"))
    store = {
        "https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json": profiles,
        "https://ast-integrate.invalid/platform/schema/receipt.schema.json": receipt,
        "https://ast-integrate.invalid/command-center/schema/program-gate-report.schema.json": shim,
    }
    for blob in (profiles, receipt, shim):
        sid = blob.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = blob
    resolver = RefResolver(
        base_uri=str(shim.get("$id") or shim_path.as_uri()),
        referrer=shim,
        store=store,
    )
    validator = jsonschema.Draft202012Validator(shim, resolver=resolver)
    out: list[str] = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def _ext(doc: dict) -> dict:
    ext = doc.get("extensions")
    return ext if isinstance(ext, dict) else {}


def artifact_published_rates(doc: dict) -> dict:
    top = doc.get("published_rates")
    if isinstance(top, dict) and top:
        return top
    rates = _ext(doc).get("published_rates")
    return rates if isinstance(rates, dict) else {}


def artifact_blocked(doc: dict) -> list:
    top = doc.get("blocked")
    if isinstance(top, list) and top:
        return top
    blocked = _ext(doc).get("blocked")
    return blocked if isinstance(blocked, list) else []


def artifact_excluded_set(doc: dict) -> dict:
    top = doc.get("excluded_set")
    if isinstance(top, dict) and top:
        return top
    ex = _ext(doc).get("excluded_set")
    return ex if isinstance(ex, dict) else {}


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()
