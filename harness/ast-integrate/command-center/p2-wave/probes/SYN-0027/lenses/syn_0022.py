"""SYN-0022 premise re-probe: source and verifier must be different fingerprints.

Fingerprint tuple matches CNF-0006 / CNF-0008: (tool, shell, data_field, measurement_kind).
A record whose source probe is empty is a VIOLATION, not a pass.
A verifier that repeats the source fingerprint is a rerun, not CONFIRMED.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from role import iter_json_strings, load_subject, path_role

LENS_ID = "SYN-0022"


def fingerprint(probe: Any) -> tuple[str, str, str, str]:
    if not isinstance(probe, dict):
        return ("", "", "", "")
    return (
        str(probe.get("tool") or ""),
        str(probe.get("shell") or ""),
        str(probe.get("data_field") or probe.get("field") or ""),
        str(probe.get("measurement_kind") or probe.get("kind") or ""),
    )


def empty_probe(fp: tuple[str, str, str, str]) -> bool:
    return not any(fp)


def extract_records(obj: Any, path: list[Any] | None = None) -> list[dict[str, Any]]:
    if path is None:
        path = []
    records: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        if "source_probe" in obj or "verifier_probe" in obj:
            records.append({"record": obj, "json_path": list(path)})
        for k, v in obj.items():
            records.extend(extract_records(v, path + [k]))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            records.extend(extract_records(v, path + [i]))
    return records


def classify_record(rec: dict[str, Any], *, mention: bool) -> dict[str, Any]:
    obj = rec["record"]
    src = fingerprint(obj.get("source_probe"))
    ver = fingerprint(obj.get("verifier_probe"))
    rid = str(obj.get("id") or obj.get("fact_id") or "/".join(str(p) for p in rec["json_path"]))
    if mention:
        verdict = "MENTION"
        reason = "probe record sits under a mention/example field; not counted as a defect"
        counted = False
        kind = "mention-only"
    elif empty_probe(src):
        verdict = "VIOLATION"
        reason = "empty source_probe is zero signals, not an independent pair"
        counted = True
        kind = "undeclared-source-probe"
    elif src == ver:
        verdict = "RERUN-REJECTED"
        reason = "verifier fingerprint equals source; a rerun is not CONFIRMED"
        counted = True
        kind = "same-probe-rerun"
    elif empty_probe(ver):
        verdict = "NOT-CHECKED"
        reason = "verifier probe missing; cannot complete the independent pair"
        counted = True
        kind = "undeclared-verifier-probe"
    else:
        verdict = "CONFIRMED"
        reason = "source and verifier fingerprints differ and both are declared"
        counted = False
        kind = "independent-pair"
    return {
        "id": f"SYN-0022-{rid}",
        "lens": LENS_ID,
        "kind": kind,
        "use_or_mention": "MENTION" if mention else "USE",
        "counted_as_defect": counted,
        "span": str(obj.get("text") or obj.get("fact") or rid)[:200],
        "source_path": "",
        "source_locator": "",
        "source_fingerprint": list(src),
        "verifier_fingerprint": list(ver),
        "verdict": verdict,
        "reason": reason,
        "record_id": rid,
    }


def scan_path(path: Path, *, ignore_wrappers: bool = False) -> list[dict[str, Any]]:
    del ignore_wrappers
    sub = load_subject(path)
    if sub["kind"] != "json":
        return []
    findings: list[dict[str, Any]] = []
    for rec in extract_records(sub["parsed"]):
        mention = path_role(rec["json_path"]) == "MENTION"
        row = classify_record(rec, mention=mention)
        row["source_path"] = path.as_posix()
        row["source_locator"] = f"{path.as_posix()}#{'/'.join(str(p) for p in rec['json_path'])}"
        findings.append(row)
    # Surface quoted 'CONFIRMED' theatre in mention fields as MENTION, never as a defect.
    for jpath, value in iter_json_strings(sub["parsed"]):
        if path_role(jpath) != "MENTION":
            continue
        if "CONFIRMED" in value and "source_probe" not in value:
            findings.append(
                {
                    "id": f"SYN-0022-MENTION-{'-'.join(str(p) for p in jpath)}",
                    "lens": LENS_ID,
                    "kind": "evidence-tag-theatre",
                    "use_or_mention": "MENTION",
                    "counted_as_defect": False,
                    "span": "CONFIRMED",
                    "source_path": path.as_posix(),
                    "source_locator": path.as_posix(),
                    "reason": "CONFIRMED appears inside a mention/example field",
                    "verdict": "MENTION",
                }
            )
    return findings
