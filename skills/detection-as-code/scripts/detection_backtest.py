#!/usr/bin/env python3
"""detection_backtest.py — the expected-hit gate for detection-as-code.

A Sigma rule that compiles is not a rule that WORKS. This helper closes the loop:
you run a detection oracle (Zircolite or Hayabusa) over labelled sample logs, then
reconcile what fired against an *expected-hit manifest* — the rules that MUST fire on
each sample and the rules that must NOT. It fails closed (exit 1) on a missed expected
hit or a forbidden hit, so it can gate a detection-as-code CI job the same way the
repo's other quality gates work.

Everything here is stdlib-only and offline. It never runs an oracle, never touches the
network, and never parses raw EVTX; it only reconciles JSON that an oracle already
produced. That keeps it safe to run anywhere and testable with fakes.

Subcommands
-----------
  reconcile   Compare an expected-hit manifest against a normalized results ledger.
  normalize   Convert one oracle's JSON output into a normalized fired-rule record
              (optionally appending it to a results ledger).
  navigator   Emit a minimal ATT&CK Navigator layer for a set of technique IDs.

Manifests may be JSON or (if PyYAML is installed) YAML. Results ledgers are JSON.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

_TECHNIQUE_RE = re.compile(r"T\d{4}(?:\.\d{3})?", re.IGNORECASE)


# --- small helpers -----------------------------------------------------------


def _match_key(value: Any) -> str:
    """Normalize a rule identifier for comparison (case- and whitespace-insensitive)."""
    return str(value).strip().lower()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = _match_key(value)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out


def _unique_sorted(values: list[str]) -> list[str]:
    return sorted(set(values))


def _collect_techniques(value: Any, acc: list[str]) -> None:
    """Pull ATT&CK technique IDs (T1003, T1003.001) out of a string/list/dict."""
    if isinstance(value, str):
        acc.extend(match.upper() for match in _TECHNIQUE_RE.findall(value))
    elif isinstance(value, dict):
        for inner in value.values():
            _collect_techniques(inner, acc)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            _collect_techniques(inner, acc)


def _load(path: str) -> Any:
    text = Path(path).read_text(encoding="utf-8")
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise SystemExit(
                f"{path}: reading YAML needs PyYAML. Convert the manifest to JSON "
                "or `pip install pyyaml`."
            ) from exc
        return yaml.safe_load(text)
    return json.loads(text)


# --- oracle normalizers ------------------------------------------------------


def normalize_zircolite(data: Any) -> dict[str, list[str]]:
    """Normalize Zircolite JSON (an array of detection objects) to a fired-rule record.

    Accepts either the bare array Zircolite writes or a ``{"results": [...]}`` wrapper.
    """
    items = data.get("results", []) if isinstance(data, dict) else data
    fired: list[str] = []
    techniques: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("id")
        if title:
            fired.append(str(title))
        _collect_techniques(item.get("tags"), techniques)
    return {"fired": _unique_preserve(fired), "attack": _unique_sorted(techniques)}


def normalize_hayabusa(data: Any) -> dict[str, list[str]]:
    """Normalize Hayabusa json-timeline output (an array of detected events)."""
    items = data.get("results", []) if isinstance(data, dict) else data
    fired: list[str] = []
    techniques: list[str] = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        title = item.get("RuleTitle") or item.get("RuleFile")
        if title:
            fired.append(str(title))
        for field in ("MitreTags", "MitreAttack", "MitreTactics"):
            for value in _as_list(item.get(field)):
                _collect_techniques(value, techniques)
    return {"fired": _unique_preserve(fired), "attack": _unique_sorted(techniques)}


NORMALIZERS = {
    "zircolite": normalize_zircolite,
    "hayabusa": normalize_hayabusa,
}


# --- reconcile ---------------------------------------------------------------


def reconcile(
    manifest: dict[str, Any],
    results: dict[str, Any],
    strict: bool = False,
) -> dict[str, Any]:
    """Reconcile an expected-hit manifest against a normalized results ledger.

    A sample PASSES when every ``expect_fire`` rule fired and no ``expect_no_fire``
    rule fired. With ``strict=True`` an unexpected hit (a fired rule that is neither
    expected nor explicitly forbidden) also fails the sample. A technique in a
    sample's ``attack`` list is only credited as covered when that sample passes.
    """
    index: dict[str, dict[str, Any]] = {}
    for record in results.get("results", []) or []:
        if isinstance(record, dict) and record.get("sample") is not None:
            index[str(record["sample"])] = record

    sample_reports: list[dict[str, Any]] = []
    techniques_expected: list[str] = []
    techniques_covered: list[str] = []

    for sample in manifest.get("samples", []) or []:
        name = str(sample.get("name", ""))
        expected = _unique_preserve(
            [str(x) for x in sample.get("expect_fire", []) or []]
        )
        forbidden = _unique_preserve(
            [str(x) for x in sample.get("expect_no_fire", []) or []]
        )
        attack = [str(x) for x in sample.get("attack", []) or []]
        techniques_expected.extend(attack)

        record = index.get(name)
        fired = [str(x) for x in (record.get("fired", []) if record else [])]
        fired_keys = {_match_key(f) for f in fired}
        expected_keys = {_match_key(e) for e in expected}
        forbidden_keys = {_match_key(f) for f in forbidden}

        matched = [e for e in expected if _match_key(e) in fired_keys]
        missed = [e for e in expected if _match_key(e) not in fired_keys]
        forbidden_fired = [f for f in forbidden if _match_key(f) in fired_keys]
        unexpected = _unique_preserve(
            [f for f in fired if _match_key(f) not in expected_keys | forbidden_keys]
        )

        ok = not missed and not forbidden_fired and not (strict and unexpected)
        if ok:
            techniques_covered.extend(attack)

        sample_reports.append(
            {
                "name": name,
                "status": "pass" if ok else "fail",
                "matched": matched,
                "missed": missed,
                "forbidden_fired": forbidden_fired,
                "unexpected": unexpected,
                "observed": record is not None,
            }
        )

    passed = sum(1 for s in sample_reports if s["status"] == "pass")
    return {
        "name": manifest.get("name", "detection-as-code backtest"),
        "strict": strict,
        "total_samples": len(sample_reports),
        "passed_samples": passed,
        "failed_samples": len(sample_reports) - passed,
        "samples": sample_reports,
        "coverage": {
            "techniques_expected": _unique_sorted(techniques_expected),
            "techniques_covered": _unique_sorted(techniques_covered),
        },
        "ok": all(s["status"] == "pass" for s in sample_reports),
    }


# --- ATT&CK Navigator layer --------------------------------------------------


def build_navigator_layer(
    techniques: list[str],
    name: str = "detection coverage",
    score: int = 100,
) -> dict[str, Any]:
    """Build a minimal, valid ATT&CK Navigator layer for the given technique IDs."""
    unique = _unique_preserve([t for t in techniques if t])
    return {
        "name": name,
        "versions": {"layer": "4.5", "navigator": "4.9.1", "attack": "15"},
        "domain": "enterprise-attack",
        "description": "Coverage ledger from detection-as-code expected-hit backtest.",
        "techniques": [
            {
                "techniqueID": tech,
                "score": score,
                "color": "#31a354",
                "enabled": True,
                "comment": "covered by an expected-hit backtest",
            }
            for tech in unique
        ],
        "gradient": {
            "colors": ["#ffffff", "#31a354"],
            "minValue": 0,
            "maxValue": 100,
        },
        "legendItems": [
            {"label": "covered by expected-hit backtest", "color": "#31a354"}
        ],
        "hideDisabled": False,
    }


# --- CLI ---------------------------------------------------------------------


def _cmd_reconcile(args: argparse.Namespace) -> int:
    manifest = _load(args.manifest)
    results = _load(args.results)
    report = reconcile(manifest, results, strict=args.strict)

    if args.layer_out:
        layer = build_navigator_layer(
            report["coverage"]["techniques_covered"],
            name=f"{report['name']} coverage",
        )
        Path(args.layer_out).write_text(
            json.dumps(layer, indent=2) + "\n", encoding="utf-8"
        )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for sample in report["samples"]:
            marker = "PASS" if sample["status"] == "pass" else "FAIL"
            print(
                f"[{marker}] {sample['name']}  "
                f"missed={len(sample['missed'])} "
                f"forbidden={len(sample['forbidden_fired'])} "
                f"unexpected={len(sample['unexpected'])}"
            )
        cov = report["coverage"]
        print(
            f"summary: {report['passed_samples']}/{report['total_samples']} samples pass; "
            f"ATT&CK covered {len(cov['techniques_covered'])}/"
            f"{len(cov['techniques_expected'])}"
        )
    return 0 if report["ok"] else 1


def _cmd_normalize(args: argparse.Namespace) -> int:
    data = _load(args.input)
    record = NORMALIZERS[args.oracle](data)
    record = {"sample": args.sample, **record}

    if args.append_to:
        ledger_path = Path(args.append_to)
        if ledger_path.exists():
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        else:
            ledger = {"results": []}
        ledger.setdefault("results", [])
        ledger["results"] = [
            r for r in ledger["results"] if r.get("sample") != args.sample
        ]
        ledger["results"].append(record)
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(record, indent=2))
    return 0


def _cmd_navigator(args: argparse.Namespace) -> int:
    techniques = list(args.technique or [])
    if args.from_reconcile:
        report = _load(args.from_reconcile)
        techniques.extend(report.get("coverage", {}).get("techniques_covered", []))
    layer = build_navigator_layer(techniques, name=args.name, score=args.score)
    payload = json.dumps(layer, indent=2)
    if args.out:
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detection_backtest",
        description="Expected-hit backtest gate + ATT&CK coverage for detection-as-code.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser(
        "reconcile", help="compare an expected-hit manifest against a results ledger"
    )
    rec.add_argument(
        "--manifest", required=True, help="expected-hit manifest (JSON/YAML)"
    )
    rec.add_argument(
        "--results", required=True, help="normalized results ledger (JSON)"
    )
    rec.add_argument(
        "--strict",
        action="store_true",
        help="also fail a sample on an unexpected (untracked) hit",
    )
    rec.add_argument("--json", action="store_true", help="emit the full report as JSON")
    rec.add_argument(
        "--layer-out", help="also write an ATT&CK Navigator layer of covered techniques"
    )
    rec.set_defaults(func=_cmd_reconcile)

    norm = sub.add_parser(
        "normalize", help="convert one oracle's JSON output into a fired-rule record"
    )
    norm.add_argument("input", help="oracle JSON output file")
    norm.add_argument("--oracle", required=True, choices=sorted(NORMALIZERS))
    norm.add_argument("--sample", required=True, help="the sample name this run covers")
    norm.add_argument(
        "--append-to", help="results ledger JSON to upsert this record into"
    )
    norm.set_defaults(func=_cmd_normalize)

    nav = sub.add_parser(
        "navigator", help="emit an ATT&CK Navigator layer for a set of techniques"
    )
    nav.add_argument("--name", default="detection coverage", help="layer name")
    nav.add_argument(
        "--technique", action="append", help="technique ID (repeatable), e.g. T1003.001"
    )
    nav.add_argument(
        "--from-reconcile",
        help="a reconcile --json report to read covered techniques from",
    )
    nav.add_argument("--score", type=int, default=100, help="score for each technique")
    nav.add_argument("--out", help="write the layer here instead of stdout")
    nav.set_defaults(func=_cmd_navigator)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
