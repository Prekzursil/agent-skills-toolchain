r"""ROUND-2 independent re-verification of the delivered units, from the COMMITTED BLOB.

SUPERSEDES `_b1r2_verify_committed.py`, which an adversarial verifier REFUTED. Two holes, both
reproduced by me before writing this file:

  1. it validated each artifact against the CATALOG-DECLARED contract and printed `schema-VALID
     YES` -- but for IMP-0433 that contract is the draft-2020-12 meta-schema, which returns 0
     errors for `{"totally":"unrelated","passing_tests":999999}`. A green from a contract that
     cannot fail is not evidence. This file measures whether each contract CAN fail and says so
     in its own column, then applies a type-appropriate contract where it cannot.
  2. its corruption control ran on ONE unit (AUD-0020) and was reported as if it covered all
     five. A control on one unit's schema says nothing about a different unit's schema. This
     file runs the control PER UNIT, against that unit's EFFECTIVE contract.

Reads the blob with `git show HEAD:<path>`. The program floor mis-stated that as CRLF-converting;
measured false -- only `git archive` converts. The CRLF column below is the standing check.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_UNITS = ["IMP-0433", "AUD-0041", "AUD-0051", "AUD-0030", "AUD-0020"]
RECEIPT_FALLBACK = "command-center/schema/receipt.schema.json"
GARBAGE = ({"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}, {})


def load_resolver():
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("schema_resolver", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["schema_resolver"] = mod
    spec.loader.exec_module(mod)
    return mod


def n_err(sr, doc, schema):
    try:
        return len(sr.validate_artifact(doc, schema))
    except Exception as e:  # noqa: BLE001
        return f"ERR:{type(e).__name__}"


def discriminates(sr, schema) -> bool:
    for g in GARBAGE:
        e = n_err(sr, g, schema)
        if e == 0:
            return False
    return True


def main() -> int:
    units = sys.argv[1:] or DEFAULT_UNITS
    sr = load_resolver()
    cat = json.loads((REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in cat["work_units"]}
    bad = 0
    rows = []
    print(f"{'unit':<9} {'blob B':>8} {'CRLF':>5} {'parses':>7} {'declared':>9} {'can-fail':>9} "
          f"{'effective contract':<44} {'VALID':>6} {'ctl':>10}  state")
    print("-" * 132)
    for uid in units:
        u = by_id.get(uid)
        if u is None:
            print(f"{uid:<9} NOT IN CATALOG")
            bad += 1
            continue
        path = u["output_path"]
        r = subprocess.run(["git", "show", f"HEAD:{path}"], cwd=str(REPO), capture_output=True)
        if r.returncode != 0:
            print(f"{uid:<9} NOT COMMITTED: {r.stderr.decode(errors='replace')[:70]}")
            bad += 1
            continue
        raw = r.stdout
        crlf = raw.count(b"\r\n")
        try:
            doc = json.loads(raw.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            print(f"{uid:<9} {len(raw):>8} {crlf:>5}  UNPARSEABLE {type(e).__name__}")
            bad += 1
            continue

        declared = u["output_schema"]
        d_err = n_err(sr, doc, declared)
        can_fail = discriminates(sr, declared)
        effective, e_err = declared, d_err
        if not can_fail:
            effective = RECEIPT_FALLBACK
            e_err = n_err(sr, doc, effective)

        # PER-UNIT two-sided control against the EFFECTIVE contract: strip `sentinel` and the
        # contract must FIRE; unmodified it must be SILENT. This is the coverage the round-1
        # verifier claimed from a single AUD-0020 control.
        mut = {k: v for k, v in doc.items() if k != "sentinel"}
        m_err = n_err(sr, mut, effective)
        ctl_fires = isinstance(m_err, str) or m_err > 0
        ctl_silent = e_err == 0
        ctl = "OK" if (ctl_fires and ctl_silent) else ("INERT" if not ctl_fires else "OVERFIRE")

        want = (u.get("completion_sentinel") or "").strip()
        token = want.split()[0].rstrip(":") if want else ""
        sent_ok = bool(token) and str(doc.get("sentinel", "")).startswith(token)

        ok = (e_err == 0) and ctl == "OK" and len(raw) > 0 and crlf == 0 and sent_ok
        if not ok:
            bad += 1
        rows.append((uid, ok, sent_ok))
        print(f"{uid:<9} {len(raw):>8} {crlf:>5} {'True':>7} {str(d_err):>9} {str(can_fail):>9} "
              f"{effective[-44:]:<44} {('YES' if e_err == 0 else 'NO(' + str(e_err) + ')'):>6} "
              f"{ctl:>10}  {doc.get('state')}")
        if not sent_ok:
            print(f"      sentinel MISMATCH: want prefix {token!r} got {str(doc.get('sentinel'))[:60]!r}")
        if isinstance(e_err, int) and e_err:
            for e in sr.validate_artifact(doc, effective)[:5]:
                print("      ", e)

    print("-" * 132)
    print("Column `can-fail` = does the CATALOG-DECLARED contract reject all 3 garbage probes.")
    print("Where it is False the declared green is worthless and the effective contract shown is")
    print("a type-appropriate substitute; `ctl` is that contract's per-unit two-sided control.")
    if bad:
        print(f"FAILED:r2-verify {bad}/{len(units)} artifacts fail the strengthened check")
        return 1
    print(f"SUCCESS:r2-verify {len(units)}/{len(units)} committed blobs validate against a contract "
          f"PROVEN able to fail, each with its own two-sided control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
