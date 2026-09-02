#!/usr/bin/env python3
"""detection_coverage - the MECHANICAL half of the purple-emulation skill.

The skill (``SKILL.md``) carries the judgement half: pick a technique, run its
atomic on an owner-owned range, and choose a *mechanically different* instrument
to confirm the detection fired (``claim-verify-gate``). This module carries the
half a model must not be trusted with, because it is answerable by an exact
algorithm - tallying whether the detections you EXPECTED to fire actually did.

Input:
  --manifest  an expected-hit manifest: atomics keyed to MITRE ATT&CK, each with
              the detection ids you assert must fire (schema in
              references/detection-assertion.md).
  --results   the detection ids your OWN lab tooling reports as fired - a file
              you export. This module never touches the network.

Output:
  - a per-atomic verdict table: DETECTED / PARTIAL / MISSED / UNVERIFIED;
  - --navigator  an ATT&CK Navigator v4.5 layer coloured by coverage;
  - --ledger     a claim-verify-gate ledger, built to pass claim_gate.py.

It never runs an atomic and contains no attack code. It only counts firings.

Exit codes: 0 no coverage gap - 1 a MISSED/PARTIAL gap exists - 2 unusable input.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

# Verdicts, worst coverage first. A technique that appears in several atomics
# rolls up to its WORST atomic: one MISSED variant means the technique has a gap,
# even if another variant was DETECTED. UNVERIFIED (no expectation declared)
# ranks below DETECTED because an un-assertable variant leaves coverage unknown.
VERDICT_ORDER = ("MISSED", "PARTIAL", "UNVERIFIED", "DETECTED")

# Coverage gaps - the detection-engineering backlog - are these two. They drive
# the non-zero exit. UNVERIFIED is surfaced but, like a claim-verify-gate
# residual, does not itself fail the gate.
GAP_VERDICTS = ("MISSED", "PARTIAL")

# ATT&CK Navigator v4.5 score/colour per verdict.
NAV_STYLE = {
    "DETECTED": (100, "#4caf50"),
    "PARTIAL": (50, "#ffb300"),
    "MISSED": (1, "#e53935"),
    "UNVERIFIED": (0, "#bdbdbd"),
}


def _norm(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _expected_detections(atomic: dict) -> list[dict]:
    """Normalise expected_detections to a list of {id, evidence} dicts.

    An entry is either a bare id string or an object {"id", "evidence"}. The
    evidence anchor (file:line or URL) is what lets the emitted ledger satisfy
    claim_gate.py's no-evidence-anchor rule.
    """
    normalised: list[dict] = []
    for entry in atomic.get("expected_detections") or []:
        if isinstance(entry, str):
            det_id = entry.strip()
            evidence = ""
        elif isinstance(entry, dict):
            det_id = _norm(entry.get("id"))
            evidence = _norm(entry.get("evidence"))
        else:
            continue
        if det_id:
            normalised.append({"id": det_id, "evidence": evidence})
    return normalised


def _validate(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("manifest must be a JSON object")
    atomics = payload.get("atomics")
    if not isinstance(atomics, list) or not atomics:
        raise ValueError("manifest must carry a non-empty 'atomics' list")
    seen: set[str] = set()
    for index, atomic in enumerate(atomics):
        if not isinstance(atomic, dict):
            raise ValueError(f"atomic #{index} is not an object")
        atomic_id = _norm(atomic.get("id"))
        if not atomic_id:
            raise ValueError(f"atomic #{index} has no 'id'")
        if atomic_id in seen:
            raise ValueError(f"duplicate atomic id {atomic_id!r}")
        seen.add(atomic_id)
        if not _norm(atomic.get("technique")):
            raise ValueError(f"atomic {atomic_id!r} has no 'technique' (ATT&CK id)")
    return atomics


def load_results(payload: object) -> set[str]:
    """Accept a JSON array, a {"fired": [...]} object, or newline text."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = payload.get("fired", [])
    else:
        raise ValueError("results must be a JSON array or an object with 'fired'")
    if not isinstance(items, list):
        raise ValueError("results 'fired' must be a list")
    return {_norm(item) for item in items if _norm(item)}


def _read_results_file(path: pathlib.Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return load_results(json.loads(text))
    return {line.strip() for line in text.splitlines() if line.strip()}


def score_atomic(atomic: dict, fired: set[str]) -> dict:
    expected = _expected_detections(atomic)
    matched = [det for det in expected if det["id"] in fired]
    missing = [det["id"] for det in expected if det["id"] not in fired]
    if not expected:
        verdict = "UNVERIFIED"
    elif not matched:
        verdict = "MISSED"
    elif missing:
        verdict = "PARTIAL"
    else:
        verdict = "DETECTED"
    return {
        "id": _norm(atomic.get("id")),
        "technique": _norm(atomic.get("technique")),
        "tactic": _norm(atomic.get("tactic")),
        "name": _norm(atomic.get("name")),
        "runner": _norm(atomic.get("runner")) or "invoke-atomic",
        "verdict": verdict,
        "matched": [det["id"] for det in matched],
        "missing": missing,
        "evidence": [det["evidence"] for det in matched if det["evidence"]],
    }


def _rollup(rows: list[dict]) -> dict[str, str]:
    """Worst verdict per ATT&CK technique."""
    by_technique: dict[str, str] = {}
    for row in rows:
        technique = row["technique"]
        current = by_technique.get(technique)
        candidate = row["verdict"]
        if current is None or VERDICT_ORDER.index(candidate) < VERDICT_ORDER.index(
            current
        ):
            by_technique[technique] = candidate
    return by_technique


def evaluate(manifest: object, fired: set[str], results_ref: str) -> dict:
    atomics = _validate(manifest)
    rows = [score_atomic(atomic, fired) for atomic in atomics]
    counts = {verdict: 0 for verdict in VERDICT_ORDER}
    for row in rows:
        counts[row["verdict"]] += 1
    gap_count = sum(counts[v] for v in GAP_VERDICTS)
    manifest_dict = manifest if isinstance(manifest, dict) else {}
    return {
        "engagement": _norm(manifest_dict.get("engagement")),
        "scope": _norm(manifest_dict.get("scope")),
        "results_ref": results_ref,
        "atomics": rows,
        "technique_rollup": _rollup(rows),
        "counts": counts,
        "gap_count": gap_count,
        "ok": gap_count == 0,
    }


def render_markdown(report: dict) -> str:
    lines = ["| atomic | technique | verdict | detail |", "|---|---|---|---|"]
    for row in report["atomics"]:
        if row["verdict"] == "MISSED":
            detail = "no expected detection fired"
        elif row["verdict"] == "PARTIAL":
            detail = "missing: " + ", ".join(row["missing"])
        elif row["verdict"] == "UNVERIFIED":
            detail = "no expected detection declared"
        else:
            detail = "fired: " + ", ".join(row["matched"])
        label = row["name"] or row["id"]
        lines.append(
            f"| {row['id']} {label} | {row['technique']} | {row['verdict']} "
            f"| {detail} |"
        )
    lines.append("")
    counts = report["counts"]
    lines.append(
        "coverage: "
        + " ".join(f"{verdict}={counts[verdict]}" for verdict in VERDICT_ORDER)
        + f" gaps={report['gap_count']} "
        + f"gate={'PASS' if report['ok'] else 'GAP'}"
    )
    gaps = [r for r in report["atomics"] if r["verdict"] in GAP_VERDICTS]
    if gaps:
        lines.append("")
        lines.append("gap backlog (route to detection-as-code):")
        for row in gaps:
            lines.append(f"- {row['technique']} ({row['id']}): {row['verdict']}")
    return "\n".join(lines)


def build_navigator(report: dict, name: str | None = None) -> dict:
    techniques = []
    for technique, verdict in sorted(report["technique_rollup"].items()):
        score, colour = NAV_STYLE[verdict]
        techniques.append(
            {
                "techniqueID": technique,
                "score": score,
                "color": colour,
                "comment": verdict,
                "enabled": True,
                "metadata": [{"name": "verdict", "value": verdict}],
            }
        )
    layer_name = name or (
        f"purple-emulation coverage - {report['engagement'] or 'range'}"
    )
    return {
        "name": layer_name,
        "versions": {"attack": "15", "navigator": "4.9.1", "layer": "4.5"},
        "domain": "enterprise-attack",
        "description": (
            "Detection coverage measured by owner-range emulation. "
            "Only emulated techniques are scored."
        ),
        "techniques": techniques,
        "gradient": {
            "colors": ["#e53935", "#ffb300", "#4caf50"],
            "minValue": 0,
            "maxValue": 100,
        },
        "legendItems": [
            {"label": "DETECTED", "color": "#4caf50"},
            {"label": "PARTIAL", "color": "#ffb300"},
            {"label": "MISSED", "color": "#e53935"},
            {"label": "UNVERIFIED", "color": "#bdbdbd"},
        ],
    }


def build_ledger(report: dict) -> dict:
    """Emit a claim-verify-gate ledger: one detection claim per atomic.

    source_probe = the emulation (the atomic runner); verify_probe = the SIEM/EDR
    query. They differ on tool/engine/field, so the "did it fire?" signal is
    mechanically independent of the tool that produced the action.
    """
    scope = report["scope"] or report["engagement"] or "owner range"
    results_ref = report["results_ref"] or "results.json"
    claims = []
    for row in report["atomics"]:
        technique = row["technique"]
        label = row["name"] or technique
        text = (
            f"Expected detections for {technique} ({label}) fired during the "
            f"{report['engagement'] or 'range'} emulation window."
        )
        claim: dict = {
            "id": row["id"],
            "text": text,
            "scope": scope,
        }
        if row["verdict"] == "DETECTED":
            anchors = list(row["evidence"]) or [f"{results_ref}:1"]
            claim.update(
                {
                    "verdict": "CONFIRMED",
                    "source_probe": {
                        "tool": row["runner"],
                        "engine": "atomic-red-team",
                        "field": "atomic_guid",
                    },
                    "verify_probe": {
                        "tool": "siem",
                        "engine": "detection-rule",
                        "field": "alert_id",
                        "command": "documentation only",
                    },
                    "evidence": anchors,
                }
            )
        elif row["verdict"] in ("MISSED", "PARTIAL"):
            if row["verdict"] == "MISSED":
                revised = (
                    f"No expected detection for {technique} fired; visibility gap "
                    "to close in detection-as-code."
                )
            else:
                revised = (
                    f"Only some expected detections for {technique} fired "
                    f"(missing: {', '.join(row['missing'])}); tune the rule."
                )
            claim.update(
                {
                    "verdict": "REFUTED",
                    "source_probe": {
                        "tool": row["runner"],
                        "engine": "atomic-red-team",
                        "field": "atomic_guid",
                    },
                    "verify_probe": {
                        "tool": "siem",
                        "engine": "detection-rule",
                        "field": "alert_id",
                        "command": "documentation only",
                    },
                    "revised_text": revised,
                }
            )
        else:
            claim.update(
                {
                    "verdict": "UNVERIFIED",
                    "settling_experiment": (
                        f"Declare an expected detection for {technique} and "
                        "re-run the atomic on the range."
                    ),
                }
            )
        claims.append(claim)
    return {
        "subject": (
            f"purple-emulation detection coverage - {report['engagement'] or 'range'}"
        ),
        "claims": claims,
    }


def self_test() -> bool:
    """Both-states probe: prove the checker distinguishes fired from silent.

    A checker that returns the same verdict whether or not the detection fired
    measures nothing (single-signal-verification.md:40). This is that check.
    """
    manifest = {
        "engagement": "self-test",
        "scope": "self-test range",
        "atomics": [
            {
                "id": "T1059-1",
                "technique": "T1059",
                "name": "self-test atomic",
                "expected_detections": ["d1"],
            }
        ],
    }
    fired_report = evaluate(manifest, {"d1"}, "results.json")
    silent_report = evaluate(manifest, set(), "results.json")
    fired_verdict = fired_report["atomics"][0]["verdict"]
    silent_verdict = silent_report["atomics"][0]["verdict"]

    checks = [
        ("fired -> DETECTED", fired_verdict == "DETECTED"),
        ("fired gate PASS", fired_report["ok"] is True),
        ("silent -> MISSED", silent_verdict == "MISSED"),
        ("silent gate GAP", silent_report["ok"] is False),
        ("verdicts differ", fired_verdict != silent_verdict),
    ]
    unverified = evaluate(
        {"atomics": [{"id": "x", "technique": "T1"}]}, set(), "r.json"
    )
    checks.append(
        (
            "no-expectation -> UNVERIFIED",
            unverified["atomics"][0]["verdict"] == "UNVERIFIED",
        )
    )
    checks.append(("no-expectation not a gap", unverified["ok"] is True))

    all_ok = True
    for label, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")
        all_ok = all_ok and passed
    return all_ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tally detection coverage from an owner-range emulation run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--manifest", type=pathlib.Path, help="expected-hit manifest JSON"
    )
    parser.add_argument(
        "--results",
        type=pathlib.Path,
        help="fired detection ids (JSON or newline text)",
    )
    parser.add_argument(
        "--navigator", type=pathlib.Path, help="write ATT&CK Navigator layer"
    )
    parser.add_argument(
        "--ledger", type=pathlib.Path, help="write claim-verify-gate ledger"
    )
    parser.add_argument("--name", help="Navigator layer name override")
    parser.add_argument("--format", choices=("md", "json"), default="md")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="prove the checker distinguishes a fired detection from a silent one",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        ok = self_test()
        print(
            "OK: checker discriminates."
            if ok
            else "FAILED: checker does not discriminate."
        )
        return 0 if ok else 1

    if args.manifest is None or args.results is None:
        parser.error(
            "--manifest and --results are required unless --self-test is given"
        )

    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        fired = _read_results_file(args.results)
        report = evaluate(manifest, fired, args.results.name)
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"FAILED: unusable input: {exc}", file=sys.stderr)
        return 2

    if args.navigator:
        args.navigator.write_text(
            json.dumps(build_navigator(report, args.name), indent=2), encoding="utf-8"
        )
    if args.ledger:
        args.ledger.write_text(
            json.dumps(build_ledger(report), indent=2), encoding="utf-8"
        )

    print(
        json.dumps(report, indent=2)
        if args.format == "json"
        else render_markdown(report)
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
