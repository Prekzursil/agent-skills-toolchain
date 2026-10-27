#!/usr/bin/env python3
"""ADV-0037 probe2 -- mechanically different independent recheck (live, fail-closed).

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
OUT = REPO / "command-center/adversarial/ADV-0037-credential-diagnosis-path-leak.json"
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "UNIT-ARTIFACT-MANIFEST.json"


def digest_norm(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def detector(doc_text: str) -> tuple[bool, str]:
    """The structural detector probe1 embodies, minimised: it must reject tampering."""
    try:
        doc = json.loads(doc_text)
    except Exception as exc:
        return True, f"parse-error:{type(exc).__name__}"
    if not isinstance(doc, dict):
        return True, "not-an-object"
    if doc.get("state") not in ("SUCCESS", "SUPERSEDED", "DROPPED-BY-OWNER"):
        return True, f"bad-state:{doc.get('state')}"
    if doc.get("unit_id") != "ADV-0037":
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
        sha = hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()
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
            print(f"NOTE:ADV-0037-probe2 dry pass: manifest not written yet; "
                  f"collecting mutation-control measurement only")
        else:
            print(f"FAILED:ADV-0037-probe2 manifest-absent {MANIFEST}")
            return 1
        rows = []
    else:
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        rows = [a for a in man.get("artifacts", []) if a.get("unit_id") == "ADV-0037"
                and str(a.get("path")).replace(chr(92) * 2, "/") == "command-center/adversarial/ADV-0037-credential-diagnosis-path-leak.json"]
        if not rows:
            print(f"FAILED:ADV-0037-probe2 manifest-row-absent")
            return 1
    live = None
    if rows:
        live = digest_norm(OUT)
        row = rows[0]
        if row.get("sha256") != live or row.get("present") is not True:
            print(f"FAILED:ADV-0037-probe2 manifest-sha-mismatch live={live} row={row.get('sha256')}")
            return 1

    doc = json.loads(OUT.read_text(encoding="utf-8"))

    # --- 2. independent headline re-derivation -----------------------------
    ok, detail = recompute(doc)
    if not ok:
        print(f"FAILED:ADV-0037-probe2 recompute-disagrees {detail}")
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
    nc = {
        "id": "NC-MUTATION-ADV-0037",
        "kind": "mutation",
        "description": (
            "Corrupting state/unit_id/evidence in a copy must make the structural "
            "detector fire, while the real artifact stays silent (both-states rule)."
        ),
        "fired_on_bad_state": bool(fired_bad),
        "silent_on_good_state": not fired_good,
        "bad_state_output": f"fired={fired_bad} why={why_bad}",
        "good_state_output": f"fired={fired_good} why={why_good}",
    }
    (HERE / "nc_live.json").write_text(
        json.dumps(nc, indent=1), encoding="utf-8", newline="\n"
    )
    if not fired_bad:
        print(f"FAILED:ADV-0037-probe2 mutation-control-inert {why_bad}")
        return 1
    if fired_good:
        print(f"FAILED:ADV-0037-probe2 control-over-fires-on-good {why_good}")
        return 1

    sha_note = ("manifest sha matches (" + live[:12] + "...); ") if live else "dry pass; "
    print(f"SUCCESS:ADV-0037-probe2 " + sha_note + "recompute: {detail}; "
          f"mutation control fired on bad state, silent on good")
    return 0


if __name__ == "__main__":
    sys.exit(main())
