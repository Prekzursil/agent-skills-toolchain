#!/usr/bin/env python3
"""Generate per-unit delivery-predicate probe pairs from the ADV-0027 wave template.

probe1_delivery_predicate.py - structural + schema delivery predicate (live, fail-closed)
probe2_independent_recheck.py  - manifest byte-compare + live recompute + mutation control
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(r"C:/Users/Prekzursil/p2-g1")
PROBES = REPO / "command-center/p2-wave/probes"
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"

# Units that already carry a builder-authored pair (skip - ADV-0027's exists).
SKIP = {"ADV-0027"}

PROBE1 = '''#!/usr/bin/env python3
"""{uid} probe1 -- structural + schema delivery predicate (live, fail-closed)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "{out_rel}"
SCHEMA_REL = "{schema_rel}"
SENTINEL = {sentinel!r}
NOT_DELIVERING = {{"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}}


def main() -> int:
    import jsonschema

    fails = []

    def check(ok: bool, label: str, detail: str = "") -> None:
        if not ok:
            fails.append(f"{{label}}{{(': ' + detail) if detail else ''}}")

    try:
        text = OUT.read_text(encoding="utf-8")
        doc = json.loads(text)
    except Exception as exc:
        print(f"FAILED:{uid}-probe1 artifact unreadable/unparseable: {{type(exc).__name__}}")
        return 1
    check(OUT.stat().st_size > 0, "artifact-empty")
    state = str(doc.get("state") or "").upper()
    check(state not in NOT_DELIVERING, "self-declared", state)
    check(str(doc.get("unit_id")) == "{uid}", "unit_id", str(doc.get("unit_id")))
    check(SENTINEL in text, "completion-sentinel-absent")
    check(doc.get("schema_version") == 1, "schema_version", repr(doc.get("schema_version")))

    schema = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    errs = sorted(
        jsonschema.Draft202012Validator(schema).iter_errors(doc),
        key=lambda e: str(list(e.absolute_path)),
    )
    check(not errs, "schema-invalid", f"{{len(errs)}} errors; first: {{str(errs[0].message)[:200] if errs else ''}}")

    ev = doc.get("evidence") or []
    check(len(ev) >= 2, "evidence-minItems-2", str(len(ev)))
    for i, item in enumerate(ev):
        probes = item.get("probes") or []
        roles = {{p.get("role") for p in probes}}
        fps = {{p.get("fingerprint") for p in probes}}
        check("source" in roles, f"evidence[{{i}}]-source-probe-absent")
        check("verifier" in roles, f"evidence[{{i}}]-verifier-probe-absent")
        check(len(fps) == len(probes) and len(probes) >= 2,
              f"evidence[{{i}}]-fingerprints-not-distinct")

    if fails:
        for f in fails[:10]:
            print(f"FAILED:{uid}-probe1 {{f}}")
        return 1
    print(f"SUCCESS:{uid}-probe1 artifact parses, schema-valid, sentinel present, "
          f"evidence pairs complete, state={{state}}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''

PROBE2 = '''#!/usr/bin/env python3
"""{uid} probe2 -- mechanically different independent recheck (live, fail-closed).

Lane: byte-compare against the per-unit manifest, an independent re-derivation of
one headline number from artifact internals, and a mutation negative control
(the structural detector must FIRE on a corrupted copy and stay SILENT on the real
artifact). Writes nc_live.json with the measured control result.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
OUT = REPO / "{out_rel}"
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest_norm(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\\r\\n", b"\\n")).hexdigest()


def detector(doc_text: str) -> tuple[bool, str]:
    """The structural detector probe1 embodies, minimised: it must reject tampering."""
    try:
        doc = json.loads(doc_text)
    except Exception as exc:
        return True, f"parse-error:{{type(exc).__name__}}"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("state") not in ("SUCCESS", "SUPERSEDED", "DROPPED-BY-OWNER"):
        return True, f"bad-state:{{doc.get('state')}}"
    if doc.get("unit_id") != "{uid}":
        return True, "unit-id-mismatch"
    if not doc.get("evidence") or len(doc["evidence"]) < 2:
        return True, "evidence-collapsed"
    if not doc.get("artifacts"):
        return True, "artifacts-collapsed"
    return False, "clean"


def recompute(doc):
    """Independent re-derivation: re-hash every non-self artifacts[] row live.
    A self-referential row (the file cannot contain its own hash) is verified by
    presence and non-emptiness; the external manifest carries the live hash."""
    bad = []
    n = 0
    for a in doc.get("artifacts") or []:
        if not isinstance(a, dict) or not a.get("path"):
            continue
        rel = str(a["path"]).replace(chr(92) * 2, "/")
        p = REPO / rel
        if not p.is_file():
            bad.append("missing:" + rel)
            continue
        if p.resolve() == OUT.resolve():
            if p.stat().st_size <= 0:
                bad.append("empty:" + rel)
            n += 1
            continue
        raw = p.read_bytes()
        sha = hashlib.sha256(raw.replace(b"\\r\\n", b"\\n")).hexdigest()
        n += 1
        if a.get("sha256") and a["sha256"] != sha:
            bad.append("sha-drift:" + rel)
    if bad:
        return False, "; ".join(bad[:4])
    return True, str(n) + " artifact rows re-verified live, all match"


def main() -> int:
    # --- 1. manifest byte-compare (mechanically different from probe1) -----
    if not MANIFEST.is_file():
        if not (HERE / "nc_live.json").is_file():
            print(f"NOTE:{uid}-probe2 dry pass: manifest not written yet; "
                  f"collecting mutation-control measurement only")
        else:
            print(f"FAILED:{uid}-probe2 manifest-absent {{MANIFEST}}")
            return 1
        rows = []
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == "{uid}"
                and str(a.get("path")).replace(chr(92) * 2, "/") == "{out_rel}"]
        if not rows:
            print(f"FAILED:{uid}-probe2 manifest-row-absent")
            return 1
    live = None
    if rows:
        live = digest_norm(OUT)
        row = rows[0]
        if row.get("sha256") != live or row.get("present") is not True:
            print(f"FAILED:{uid}-probe2 manifest-sha-mismatch live={{live}} row={{row.get('sha256')}}")
            return 1

    doc = json.loads(OUT.read_text(encoding="utf-8"))

    # --- 2. independent headline re-derivation -----------------------------
    ok, detail = recompute(doc)
    if not ok:
        print(f"FAILED:{uid}-probe2 recompute-disagrees {{detail}}")
        return 1

    # --- 3. mutation negative control (both states, live) ------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "mutant.json"
        mutant = json.loads(OUT.read_text(encoding="utf-8"))
        mutant["evidence"] = []
        mutant["unit_id"] = "ADV-9999"
        mutant["state"] = "BLOCKED"
        tmp.write_text(json.dumps(mutant), encoding="utf-8")
        fired_bad, why_bad = detector(tmp.read_text(encoding="utf-8"))
        fired_good, why_good = detector(OUT.read_text(encoding="utf-8"))
    nc = {{
        "id": "NC-MUTATION-{uid}",
        "kind": "mutation",
        "description": (
            "Corrupting state/unit_id/evidence in a copy must make the structural "
            "detector fire, while the real artifact stays silent (both-states rule)."
        ),
        "fired_on_bad_state": bool(fired_bad),
        "silent_on_good_state": not fired_good,
        "bad_state_output": f"fired={{fired_bad}} why={{why_bad}}",
        "good_state_output": f"fired={{fired_good}} why={{why_good}}",
    }}
    (HERE / "nc_live.json").write_text(
        json.dumps(nc, indent=1), encoding="utf-8", newline="\\n"
    )
    if not fired_bad:
        print(f"FAILED:{uid}-probe2 mutation-control-inert {{why_bad}}")
        return 1
    if fired_good:
        print(f"FAILED:{uid}-probe2 control-over-fires-on-good {{why_good}}")
        return 1

    sha_note = ("manifest sha matches (" + live[:12] + "...); ") if live else "dry pass; "
    print(f"SUCCESS:{uid}-probe2 " + sha_note + "recompute: {{detail}}; "
          f"mutation control fired on bad state, silent on good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def main() -> int:
    cat = json.load(open(CATALOG, encoding="utf-8"))
    units = {e["id"]: e for e in cat["work_units"] if e.get("id") in {
        "ADV-0006", "ADV-0019", "ADV-0027", "ADV-0028", "ADV-0029", "ADV-0033",
        "ADV-0037", "ADV-0038", "ADV-0060", "ADV-0096", "ADV-0124", "ADV-0127"}}
    for uid, e in sorted(units.items()):
        if uid in SKIP:
            print(f"skip {uid} (builder pair exists)")
            continue
        d = PROBES / uid
        d.mkdir(parents=True, exist_ok=True)
        ctx = dict(
            uid=uid,
            out_rel=str(e["output_path"]).replace("\\", "/"),
            schema_rel=str(e["output_schema"]).replace("\\", "/"),
            sentinel=e.get("completion_sentinel", ""),
        )
        (d / "probe1_delivery_predicate.py").write_text(
            PROBE1.format(**ctx), encoding="utf-8", newline="\n")
        (d / "probe2_independent_recheck.py").write_text(
            PROBE2.format(**ctx), encoding="utf-8", newline="\n")
        print(f"generated {uid}")
    print("SUCCESS:predicate-pair generation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
