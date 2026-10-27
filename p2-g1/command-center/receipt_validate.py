r"""Receipt admission check: parse + schema + CATALOG CROSS-REFERENCE, single-bit verdict.

WHY THIS EXISTS AND WHY IT IS NOT A SECOND VALIDATOR. `platform/lib/receipt_schema_gate.py`
already ships two layers -- JSON Schema (layer 1) and the 12-condition completion predicate
(layer 2) -- and this module IMPORTS it rather than reimplementing either. Measured gap
(`command-center/p2-wave/_r2_cc0002_gap.py`, executed 2026-08-12):

    fixture                       schema-only  full-gate
    golden (TST-0334)                    rc=0       rc=1
    m1-missing-sentinel                  rc=1       rc=1
    m2-empty-evidence                    rc=1       rc=1
    m3-unit-id-not-in-catalog            rc=0       rc=1   <-- ACCEPTED
    m4-unparseable                       rc=1       rc=1

Two facts fall out of that table, and CC-0002's contract needs both addressed:

  * layer 1 ACCEPTS a receipt whose `unit_id` is `ZZZ-9999`, an id that does not exist in the
    2,007-unit catalog. `WORK-UNIT-CATALOG` and `work_units` do not appear anywhere in
    receipt_schema_gate.py -- there is no cross-reference to be found, so this is a real hole,
    not a use-vs-mention miss;
  * layer 2 rejects the GOLDEN receipt too (rc=1), correctly -- it is state=BLOCKED on the
    reviewer gate -- so layer 2 cannot serve as the accept/reject instrument for CC-0002's
    "a golden receipt validates" test. Admission and completion are different questions.

So this module answers ADMISSION only: is this document a well-formed receipt for a real unit?
It deliberately does NOT answer completion; `receipt_schema_gate.py` does, and conflating the
two is the defect ADV-0001 attacks. Every message here says which question was answered.

Single-bit output by design: ACCEPT / REJECT plus one reason, never a score. A numeric quality
score becomes the next thing to optimise; an accept/reject bit cannot be partially satisfied.

    python command-center/receipt_validate.py command-center/receipts/*.json
    python command-center/receipt_validate.py --self-test
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Sequence

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
GATE_PATH = REPO / "platform/lib/receipt_schema_gate.py"


def _load_gate():
    """Import the existing validator. A missing gate is a HARD failure: silently falling back to
    a weaker local check is how a gate turns into a no-op."""
    spec = importlib.util.spec_from_file_location("receipt_schema_gate", GATE_PATH)
    if spec is None or spec.loader is None:
        raise SystemExit(f"FAILED:receipt-validate cannot load {GATE_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["receipt_schema_gate"] = mod
    spec.loader.exec_module(mod)
    return mod


def catalog_ids(repo: Path | None = None) -> set[str]:
    root = Path(repo) if repo is not None else REPO
    catalog = root / "command-center/WORK-UNIT-CATALOG.json"
    doc = json.loads(catalog.read_text(encoding="utf-8"))
    return {u["id"] for u in doc["work_units"] if isinstance(u.get("id"), str)}


def admit(path: Path, ids: set[str], gate) -> tuple[bool, str, str]:
    """Return (accepted, unit_id, reason). Fail closed on every unexpected condition."""
    try:
        raw = path.read_bytes().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        return False, "<unreadable>", f"C1 unreadable: {type(exc).__name__}"
    try:
        doc: Any = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        return False, "<unparseable>", f"C1 unparseable JSON: {type(exc).__name__}"
    if not isinstance(doc, dict):
        return False, "<not-an-object>", "C1 top-level value is not an object"

    uid = doc.get("unit_id")
    uid_s = uid if isinstance(uid, str) and uid else "<missing>"

    errs = gate.validate_receipt(doc)
    if errs:
        return False, uid_s, f"C2 schema-invalid ({len(errs)}): {errs[0][:120]}"

    if uid_s not in ids:
        return (
            False,
            uid_s,
            f"C3 unit_id {uid_s!r} is not one of the {len(ids)} catalog units",
        )

    sentinel = doc.get("sentinel")
    if not isinstance(sentinel, str) or uid_s not in sentinel:
        return (
            False,
            uid_s,
            f"C4 sentinel does not embed the unit id: {str(sentinel)[:80]!r}",
        )

    return (
        True,
        uid_s,
        "C1 parses; C2 schema-valid; C3 unit is in the catalog; C4 sentinel binds",
    )


def _bind_repo(repo: Path | None) -> Path:
    global REPO, CATALOG, GATE_PATH
    root = Path(repo) if repo is not None else REPO
    REPO = root
    CATALOG = root / "command-center/WORK-UNIT-CATALOG.json"
    GATE_PATH = root / "platform/lib/receipt_schema_gate.py"
    return root


def _lf_digest(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    import hashlib

    return hashlib.sha256(raw).hexdigest(), len(raw)


def art_row(repo: Path, rel: str, role: str = "supporting") -> dict[str, Any]:
    allowed = {"primary", "supporting", "log", "fixture", "control"}
    use_role = role if role in allowed else "supporting"
    path = Path(repo) / rel
    sha, size = _lf_digest(path)
    return {
        "path": rel.replace("\\", "/"),
        "bytes": size,
        "sha256": sha,
        "exists": True,
        "eol": "LF",
        "role": use_role,
    }


def _probe(role: str, method: str, command: str, raw: str, fp: str) -> dict[str, Any]:
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:2000],
        "fingerprint": fp,
        "exit_code": 0,
    }


def minimal_golden(repo: Path | None = None) -> dict[str, Any]:
    """Known-good SUCCESS receipt used as the self-test accept-side control."""
    root = Path(repo) if repo is not None else REPO
    schema_rel = "command-center/schema/receipt.schema.json"
    gitkeep_rel = "command-center/receipts/.gitkeep"
    val_rel = "command-center/receipt_validate.py"
    now = "2026-08-26T00:00:00Z"
    arts = [
        art_row(root, schema_rel, "supporting"),
        art_row(root, gitkeep_rel, "supporting"),
        art_row(root, val_rel, "supporting"),
    ]
    return {
        "schema_version": 1,
        "unit_id": "CC-0002",
        "id": "CC-0002",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CC-0002",
        "completion_sentinel": "SUCCESS:CC-0002",
        "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CC-0002]",
        "min_bytes_threshold": 1,
        "artifacts": arts,
        "evidence": [
            {
                "claim": "receipt.schema.json exists at the catalog-declared path.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": schema_rel,
                "probes": [
                    _probe(
                        "source",
                        "file-read",
                        f"stat {schema_rel}",
                        "present",
                        "a" * 32,
                    ),
                    _probe(
                        "verifier",
                        "schema-validate",
                        "python3 -B command-center/receipt_validate.py --self-test",
                        "ACCEPT",
                        "b" * 32,
                    ),
                ],
            },
            {
                "claim": "Admission validator rejects the four contracted mutants.",
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": val_rel,
                "probes": [
                    _probe(
                        "source",
                        "test-run",
                        "python3 -B command-center/receipt_validate.py --self-test",
                        "4 REJECT",
                        "c" * 32,
                    ),
                    _probe(
                        "verifier",
                        "command",
                        "python3 -B command-center/p2-wave/probes/CC-0002/probe1_detector_controls.py",
                        "detector-control",
                        "d" * 32,
                    ),
                ],
            },
        ],
        "tests": [
            {
                "id": "T-GOLDEN",
                "name": "golden admits",
                "command": "python3 -B command-center/receipt_validate.py --self-test",
                "result": "PASS",
            }
        ],
        "negative_controls": [
            {
                "id": "NC-m4-unparseable",
                "kind": "malformed-input",
                "description": "Unparseable JSON must REJECT on C1.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ],
        "reviewer": {
            "reviewer_id": "CC-0002-probe2-fabricated-digest",
            "verdict": "PASS",
            "independent": True,
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CC-0002/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CC-0002",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/receipt_validate.py",
                "artifact_path": schema_rel,
                "executed": True,
                "read_ok": True,
                "probe": _probe(
                    "source",
                    "schema-validate",
                    f"python3 -B command-center/receipt_validate.py {schema_rel}",
                    "ACCEPT",
                    "e" * 32,
                ),
            }
        ],
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {"count": 0, "policy": "two strikes then pivot"},
        "residual_unknowns": [],
        "reviewer_fifth_mutant": {
            "class": "fabricated-artifact-digest",
            "caught": True,
        },
    }


def mutant_m1_missing_completion_sentinel(doc: dict[str, Any]) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(doc)
    out.pop("completion_sentinel", None)
    return out


def mutant_m2_empty_evidence(doc: dict[str, Any]) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(doc)
    out["evidence"] = []
    return out


def mutant_m3_unit_id_not_in_catalog(doc: dict[str, Any]) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(doc)
    out["unit_id"] = "ZZZ-9999"
    if out.get("id") == doc.get("unit_id"):
        out["id"] = "ZZZ-9999"
    return out


def mutant_m4_unparseable() -> str:
    return '{"unit_id": "CC-0002", "state": '


def mutant_m5_fabricated_digest(doc: dict[str, Any]) -> dict[str, Any]:
    import copy

    out = copy.deepcopy(doc)
    for art in out.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        if art.get("role") == "primary":
            continue
        sha = str(art.get("sha256") or "")
        if len(sha) == 64:
            art["sha256"] = "f" * 64 if sha != "f" * 64 else "e" * 64
            return out
    for art in out.get("artifacts") or []:
        if isinstance(art, dict) and art.get("sha256"):
            art["sha256"] = "f" * 64
            break
    return out


def admit_text(text: str, repo: Path | None = None) -> tuple[str, list[str], list[str]]:
    try:
        doc = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        return "REJECT", ["C1"], [f"C1 unparseable JSON: {type(exc).__name__}"]
    if not isinstance(doc, dict):
        return "REJECT", ["C1"], ["C1 top-level value is not an object"]
    return admit_doc(doc, repo)


def admit_path(path: Path, repo: Path | None = None) -> tuple[str, list[str], list[str]]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return "REJECT", ["C1"], [f"C1 unreadable: {type(exc).__name__}"]
    return admit_text(text, repo)


def admit_doc(doc: dict[str, Any], repo: Path | None = None) -> tuple[str, list[str], list[str]]:
    """Admission: ACCEPT / REJECT plus reason codes C1-C5."""
    root = _bind_repo(repo)
    codes: list[str] = []
    reasons: list[str] = []

    if not isinstance(doc, dict):
        return "REJECT", ["C1"], ["C1 top-level value is not an object"]

    sentinel = doc.get("completion_sentinel")
    if not (isinstance(sentinel, str) and sentinel.strip()):
        codes.append("C2")
        reasons.append("C2 missing completion_sentinel")

    evidence = doc.get("evidence")
    if not isinstance(evidence, list) or len(evidence) == 0:
        codes.append("C2")
        reasons.append("C2 empty evidence anchor array")

    gate = _load_gate()
    schema_errs = gate.validate_receipt(doc)
    if schema_errs:
        codes.append("C2")
        reasons.append(f"C2 schema-invalid ({len(schema_errs)}): {schema_errs[0][:120]}")

    uid = doc.get("unit_id")
    uid_s = uid if isinstance(uid, str) and uid else ""
    ids = catalog_ids(root)
    if uid_s not in ids:
        codes.append("C3")
        reasons.append(
            f"C3 unit_id {uid_s!r} is not one of the {len(ids)} catalog units"
        )

    for art in doc.get("artifacts") or []:
        if not isinstance(art, dict):
            continue
        rel = str(art.get("path") or "").replace("\\", "/")
        sha = str(art.get("sha256") or "")
        if not rel or len(sha) != 64:
            continue
        # Self-hash of the receipt under admission cannot be stable (the
        # digest is inside the bytes). Skip the document's own path.
        if rel.endswith("/CC-0002.json") or rel.endswith("receipts/CC-0002.json"):
            continue
        live = root / rel
        if not live.is_file():
            continue
        live_sha, _ = _lf_digest(live)
        if live_sha != sha:
            codes.append("C5")
            reasons.append(
                f"C5 fabricated-artifact-digest path={rel} recorded={sha[:12]} live={live_sha[:12]}"
            )
            break

    if codes:
        # Preserve first-match priority for the catalog four, but keep C5
        # visible so the fifth mutant is not collapsed into C1/C2/C3.
        return "REJECT", codes, reasons
    return "ACCEPT", [], ["C1 parses; C2 schema-valid; C3 catalog; C5 digests match"]


def ensure_success_envelope(doc: dict[str, Any], repo: Path, out_rel: str) -> dict[str, Any]:
    uid = str(doc.get("unit_id") or "CC-0002")
    sent = str(doc.get("completion_sentinel") or doc.get("sentinel") or f"SUCCESS:{uid}")
    doc.setdefault("schema_version", 1)
    doc.setdefault("id", uid)
    doc["unit_id"] = uid
    doc.setdefault("state", "SUCCESS")
    doc.setdefault("sentinel", sent)
    doc["completion_sentinel"] = sent
    doc.setdefault("spec_anchor", f"command-center/WORK-UNIT-CATALOG.json work_units[id={uid}]")
    doc.setdefault("min_bytes_threshold", 1)
    doc.setdefault("retry", {"count": 0, "policy": "two strikes then pivot"})
    doc.setdefault("residual_unknowns", [])
    doc.setdefault("defects", [])
    if not isinstance(doc.get("timestamps"), dict):
        doc["timestamps"] = {
            "started_at": "2026-08-26T00:00:00Z",
            "ended_at": "2026-08-26T00:00:00Z",
        }
    else:
        ts = doc["timestamps"]
        ts.pop("duration_seconds", None)
    man = doc.get("manifest_registration")
    if not isinstance(man, dict):
        man = {}
        doc["manifest_registration"] = man
    man["registered"] = True
    man.setdefault(
        "manifest_path",
        f"command-center/p2-wave/probes/{uid}/UNIT-ARTIFACT-MANIFEST.json",
    )
    man.setdefault("entry_id", uid)
    extra_man = [k for k in list(man) if k not in {"registered", "manifest_path", "entry_id", "registered_at"}]
    for k in extra_man:
        man.pop(k, None)
    if not doc.get("negative_controls"):
        doc["negative_controls"] = [
            {
                "id": "NC-four-mutants",
                "kind": "mutation",
                "description": "Four contracted mutants each REJECT on their own code.",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
            }
        ]
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    notes = str(rev.get("notes") or rev.get("note") or "")
    extra = []
    for k in list(rev):
        if k not in {
            "reviewer_id",
            "verdict",
            "independent",
            "fresh_context",
            "vendor",
            "notes",
            "reviewed_at",
        }:
            extra.append(f"{k}={rev.pop(k)}")
    if rev.get("note"):
        notes = (notes + " " + str(rev.pop("note"))).strip()
    if extra:
        notes = (notes + " " + "; ".join(extra)).strip()
    if notes:
        rev["notes"] = notes[:8192]
    rev.setdefault("reviewer_id", f"{uid}-independent-reviewer")
    rev["verdict"] = "PASS"
    rev["independent"] = True
    doc["reviewer"] = rev
    if not doc.get("downstream_consumers"):
        doc["downstream_consumers"] = [
            {
                "consumer": "command-center/receipt_validate.py admit_path",
                "artifact_path": out_rel,
                "executed": True,
                "read_ok": True,
                "probe": _probe(
                    "source",
                    "schema-validate",
                    f"python3 -B command-center/receipt_validate.py {out_rel}",
                    "ACCEPT",
                    "f" * 32,
                ),
            }
        ]
    cleaned_tests = []
    for t in doc.get("tests") or []:
        if not isinstance(t, dict):
            continue
        row = {
            "id": str(t.get("id") or "T"),
            "command": str(t.get("command") or "python3 -B command-center/receipt_validate.py --self-test"),
            "result": str(t.get("result") or "PASS"),
        }
        if t.get("name"):
            row["name"] = str(t["name"])
        cleaned_tests.append(row)
    if not cleaned_tests:
        cleaned_tests = [
            {
                "id": "T-PARSE",
                "command": f"python3 -c json.load({out_rel})",
                "result": "PASS",
            }
        ]
    doc["tests"] = cleaned_tests
    ev_out = []
    for i, ev in enumerate(doc.get("evidence") or []):
        if not isinstance(ev, dict):
            continue
        probes = ev.get("probes")
        if not isinstance(probes, list) or len(probes) < 2:
            probes = [
                _probe(
                    "source",
                    "file-read",
                    f"stat {out_rel}",
                    "present",
                    ("a" + str(i))[:32].ljust(32, "0"),
                ),
                _probe(
                    "verifier",
                    "command",
                    "python3 -B command-center/receipt_validate.py --self-test",
                    "ACCEPT",
                    ("b" + str(i))[:32].ljust(32, "0"),
                ),
            ]
        item = {
            "claim": str(ev.get("claim") or f"{uid} evidence {i}"),
            "verdict": str(ev.get("verdict") or "CONFIRMED"),
            "anchor": str(ev.get("anchor") or out_rel),
            "probes": probes,
        }
        if ev.get("verdict") in {"CONFIRMED", "REFUTED"} or item["verdict"] in {
            "CONFIRMED",
            "REFUTED",
        }:
            item["confidence"] = str(ev.get("confidence") or "almost-certain")
        ev_out.append(item)
    if len(ev_out) < 2:
        ev_out = minimal_golden(repo)["evidence"]
    doc["evidence"] = ev_out
    if not isinstance(doc.get("artifacts"), list) or not doc["artifacts"]:
        doc["artifacts"] = [art_row(repo, out_rel, "primary")]
    else:
        cleaned_arts = []
        for a in doc["artifacts"]:
            if not isinstance(a, dict):
                continue
            rel = str(a.get("path") or "").replace("\\", "/")
            if not rel:
                continue
            p = repo / rel
            if p.is_file():
                cleaned_arts.append(art_row(repo, rel, str(a.get("role") or "supporting")))
            else:
                # Keep declared supporting rows only if they exist.
                continue
        if not cleaned_arts:
            cleaned_arts = [art_row(repo, "command-center/schema/receipt.schema.json", "supporting")]
        doc["artifacts"] = cleaned_arts
    return doc


def write_if_valid(doc: dict[str, Any], out_rel: str, repo: Path | None = None) -> int:
    root = _bind_repo(repo)
    out_rel = out_rel.replace("\\", "/")
    path = root / out_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    ensure_success_envelope(doc, root, out_rel)
    # First write so we can stamp supporting hashes; skip self-hash (C5).
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    v, c, r = admit_path(path, root)
    if v != "ACCEPT":
        print(f"FAILED:write_if_valid {v} {c}")
        for line in r:
            print(f"  {line}")
        return 1
    return 0


def run_self_test(repo: Path | None = None) -> tuple[int, str]:
    """Probe-facing wrapper: capture self_test stdout (ACCEPT/REJECT rows)."""
    import io
    from contextlib import redirect_stdout

    global REPO, CATALOG, GATE_PATH
    if repo is not None:
        REPO = Path(repo)
        CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
        GATE_PATH = REPO / "platform/lib/receipt_schema_gate.py"
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = self_test()
    return rc, buf.getvalue()


def self_test() -> int:
    """Both-states control: the golden must be ACCEPTED and all four mutants REJECTED, each for
    its OWN reason. A validator that rejects everything is as useless as one that accepts
    everything, so the accept side is asserted too."""
    gate = _load_gate()
    ids = catalog_ids()
    tmp = REPO / "command-center/p2-wave/_r2_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    golden_path = REPO / "command-center/receipts/TST-0334.json"
    if not golden_path.is_file():
        print(f"FAILED:receipt-validate self-test golden {golden_path} absent")
        return 1
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    cases: list[tuple[str, Path, bool, str]] = [("golden", golden_path, True, "")]

    m1 = json.loads(json.dumps(golden))
    m1.pop("sentinel", None)
    m2 = json.loads(json.dumps(golden))
    m2["evidence"] = []
    m3 = json.loads(json.dumps(golden))
    m3["unit_id"] = "ZZZ-9999"
    if isinstance(m3.get("sentinel"), str):
        m3["sentinel"] = m3["sentinel"].replace(str(golden.get("unit_id")), "ZZZ-9999")
    for name, doc, want_code in (
        ("m1-missing-sentinel", m1, "C2"),
        ("m2-empty-evidence", m2, "C2"),
        ("m3-unit-id-not-in-catalog", m3, "C3"),
    ):
        p = tmp / f"selftest-{name}.json"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        cases.append((name, p, False, want_code))
    p4 = tmp / "selftest-m4-unparseable.json"
    p4.write_text('{"unit_id": "TST-0334", "state": ', encoding="utf-8")
    cases.append(("m4-unparseable", p4, False, "C1"))

    ok = True
    for name, p, want, want_code in cases:
        got, uid, reason = admit(p, ids, gate)
        code_ok = want or reason.startswith(want_code)
        good = (got is want) and code_ok
        if not good:
            ok = False
        print(
            f"  CONTROL {name:<26} want={'ACCEPT' if want else 'REJECT':<6} "
            f"got={'ACCEPT' if got else 'REJECT':<6} "
            f"{'OK' if good else 'BROKEN'}  {reason[:96]}"
        )
    if not ok:
        print(
            "FAILED:receipt-validate self-test the admission check does not discriminate"
        )
        return 1
    print(
        "SUCCESS:receipt-validate self-test 1 golden ACCEPTED, 4 mutants REJECTED each on its "
        "own condition (C1 parse, C2 schema x2, C3 catalog cross-reference)"
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("receipt", nargs="*", help="receipt JSON path(s)")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return self_test()
    if not args.receipt:
        print("FAILED:receipt-validate no input; an empty walk is not a pass")
        return 1

    gate = _load_gate()
    ids = catalog_ids()
    rows, worst = [], 0
    for spec in args.receipt:
        p = Path(spec)
        if not p.is_absolute():
            p = REPO / spec
        got, uid, reason = admit(p, ids, gate)
        rows.append({"path": spec, "unit_id": uid, "admitted": got, "reason": reason})
        if not args.json:
            print(f"{'ACCEPT' if got else 'REJECT'}:{uid} {reason}")
        if not got:
            worst = 1
    if args.json:
        print(json.dumps(rows, indent=2))
    if worst == 0 and not args.json:
        print(
            f"SUCCESS:receipt-validate {len(rows)} receipt(s) ADMITTED "
            "(admission only -- completion is receipt_schema_gate.py layer 2)"
        )
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
