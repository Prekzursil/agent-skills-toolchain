r"""SUPERSEDED 2026-08-12 by `_r2_verify_committed.py`. DO NOT cite this file's SUCCESS line.

An adversarial verifier REFUTED it and I reproduced both holes: (1) it validates against the
CATALOG-DECLARED contract, and IMP-0433's declared contract is the draft-2020-12 meta-schema,
which returns 0 errors for `{"totally":"unrelated","passing_tests":999999}` -- so its
`schema-VALID YES` for that unit is a green from a gate that cannot fail; (2) its corruption
control runs on AUD-0020 only while its SUCCESS line speaks for all five. Kept unmodified as the
record of what round 1 actually ran.

Independent re-verification of the five delivered units, from the COMMITTED BLOB.

Mechanically different from every build script: those validated an in-memory document and then
wrote it. This reads back what git actually stored (`git show HEAD:<path>`, which the corrected
floor confirms returns the blob with no CRLF conversion -- unlike `git archive`) and re-validates
it against the schema the CATALOG declares, not the schema the build script happened to pass.

A build script that validates its own variable is one signal. This is the second.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
UNITS = ["IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020"]


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    sr = load_resolver()
    cat = json.loads(
        (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
    )
    by_id = {u["id"]: u for u in cat["work_units"]}
    bad = 0
    print(
        f"{'unit':<9} {'blob B':>8} {'CRLF':>5}  parses  schema-VALID  sentinel-matches  state"
    )
    print("-" * 92)
    for uid in UNITS:
        u = by_id[uid]
        path = u["output_path"]
        r = subprocess.run(
            ["git", "show", f"HEAD:{path}"], cwd=str(REPO), capture_output=True
        )
        if r.returncode != 0:
            print(f"{uid:<9} NOT COMMITTED: {r.stderr.decode(errors='replace')[:70]}")
            bad += 1
            continue
        raw = r.stdout
        crlf = raw.count(b"\r\n")
        try:
            doc = json.loads(raw.decode("utf-8"))
            parses = True
        except Exception as e:  # noqa: BLE001
            print(f"{uid:<9} {len(raw):>8} {crlf:>5}  UNPARSEABLE {type(e).__name__}")
            bad += 1
            continue
        errs = sr.validate_artifact(doc, u["output_schema"])
        want_sentinel = (u.get("completion_sentinel") or "").strip()
        got_sentinel = doc.get("sentinel", "")
        # the catalog sentinel is sometimes a prose sentence; match on the leading token
        token = want_sentinel.split()[0] if want_sentinel else ""
        sent_ok = bool(token) and got_sentinel.startswith(token.rstrip(":").split()[0])
        ok = parses and not errs and len(raw) > 0
        print(
            f"{uid:<9} {len(raw):>8} {crlf:>5}  {str(parses):<6}  "
            f"{('YES' if not errs else 'NO(' + str(len(errs)) + ')'):<12}  "
            f"{str(sent_ok):<16}  {doc.get('state')}"
        )
        if not ok:
            bad += 1
            for e in errs[:5]:
                print("      ", e)

    # CONTROL: the verifier must REJECT a deliberately corrupted copy of a real artifact.
    print("-" * 92)
    victim = by_id["AUD-0020"]
    raw = subprocess.run(
        ["git", "show", f"HEAD:{victim['output_path']}"],
        cwd=str(REPO),
        capture_output=True,
    ).stdout
    doc = json.loads(raw.decode("utf-8"))
    doc.pop("sentinel", None)  # break completion condition 5
    mutant_errs = sr.validate_artifact(doc, victim["output_schema"])
    good_errs = sr.validate_artifact(
        json.loads(raw.decode("utf-8")), victim["output_schema"]
    )
    fires, silent = bool(mutant_errs), not good_errs
    print(
        f"CONTROL verifier: AUD-0020 with `sentinel` removed -> {len(mutant_errs)} error(s) "
        f"{'FIRES' if fires else '** INERT **'}; unmodified -> {len(good_errs)} error(s) "
        f"{'SILENT' if silent else 'OVER-FIRES'}"
    )
    if not (fires and silent):
        print(
            "FAILED:p2-verify the verifier does not discriminate; its PASSes mean nothing"
        )
        return 1
    if bad:
        print(
            f"FAILED:p2-verify {bad}/{len(UNITS)} committed artifacts do not satisfy their contract"
        )
        return 1
    print(
        f"SUCCESS:p2-verify {len(UNITS)}/{len(UNITS)} committed blobs are non-empty, parse, and "
        f"validate against the schema their CATALOG ROW declares"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
