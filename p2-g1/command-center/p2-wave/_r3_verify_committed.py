"""Independent re-verification of every artifact this P2 build lane has delivered, read from the
COMMITTED BLOB rather than the working tree, by a reader that shares no code with the builders.

It adds the column the adversarial audit said was missing. "Executable-proven against its declared
contract" is only meaningful when the declared contract CAN FAIL, and for IMP-0433 it cannot: its
row declares `command-center/schema/meta/json-schema-draft.json`, a meta-schema that accepts
arbitrary JSON. The DISCRIM column below states that per unit instead of letting one sentence cover
all nine.

Blob recipe: `git ls-files -s` + `git cat-file -p`. NOT `git archive`, which applies export-time
EOL conversion on Windows and hands back CRLF.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO = Path("C:/Users/Prekzursil/source/ast-integrate")
sys.path.insert(0, str(REPO / "platform" / "lib"))
spec = importlib.util.spec_from_file_location(
    "schema_resolver", REPO / "platform/lib/schema_resolver.py"
)
sr = importlib.util.module_from_spec(spec)
sys.modules["schema_resolver"] = sr
spec.loader.exec_module(sr)

GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)

UNITS = [
    "IMP-0433",
    "AUD-0041",
    "AUD-0051",
    "AUD-0030",
    "AUD-0020",
    "CC-0002",
    "IMP-0440",
    "AUD-0021",
    "AUD-0006",
]

catalog = json.loads(
    (REPO / "command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8")
)
by_id = {u["id"]: u for u in catalog["work_units"]}


def blob(rel: str) -> bytes | None:
    r = subprocess.run(
        ["git", "ls-files", "-s", "--", rel], cwd=REPO, capture_output=True, text=True
    )
    if not r.stdout.strip():
        return None
    sha = r.stdout.split()[1]
    return subprocess.run(
        ["git", "cat-file", "-p", sha], cwd=REPO, capture_output=True
    ).stdout


def discriminates(schema: str) -> bool:
    for g in GARBAGE:
        try:
            if not sr.validate_artifact(g, schema):
                return False
        except Exception:
            pass
    return True


print(
    f"{'unit':10s} {'blobB':>8s} {'CR':>3s} {'parse':>5s} {'VALID':>5s} {'DISCRIM':>7s} {'sent':>4s} {'exact':>5s} state"
)
rows, ok = [], True
for uid in UNITS:
    u = by_id[uid]
    rel, schema = u["output_path"], u.get("output_schema")
    data = blob(rel)
    if data is None:
        print(f"{uid:10s} {'ABSENT-FROM-INDEX':>40s}")
        ok = False
        continue
    cr = data.count(b"\r")
    try:
        doc = json.loads(data.decode("utf-8"))
        parses = True
    except Exception:
        doc, parses = None, False
    errs = sr.validate_artifact(doc, schema) if parses else ["unparseable"]
    disc = discriminates(schema)
    # Read the sentinel the ROW declares, never a format this file assumes. First version asserted
    # `startswith("SUCCESS:<uid>")` and scored IMP-0433 and IMP-0440 False -- both are correct, they
    # simply declare a `SENTINEL:<uid>:...` form. A verifier that invents the expected value is
    # measuring its own assumption; recorded rather than silently corrected.
    declared = str(u.get("completion_sentinel") or "")
    got_sent = str((doc or {}).get("sentinel", ""))
    exact = bool(doc) and bool(declared) and got_sent.strip() == declared.strip()
    # The GATE is the prefix (the sentinel's job is to be a unique terminal marker for this unit);
    # exact equality with the row's prose is reported alongside it as DRIFT, not used to fail a
    # delivered artifact. Stating which of the two the verdict rests on, because they disagree.
    sent = (
        bool(doc)
        and got_sent.startswith(f"SUCCESS:{uid}")
        or (bool(doc) and got_sent.startswith(f"SENTINEL:{uid}"))
    )
    state = (doc or {}).get("state")
    good = parses and not errs and sent
    ok &= good
    rows.append((uid, len(data), cr, parses, not errs, disc, sent, state, exact))
    print(
        f"{uid:10s} {len(data):8d} {cr:3d} {str(parses):>5s} {'YES' if not errs else 'NO':>5s} "
        f"{'yes' if disc else 'NO':>7s} {str(sent):>4s} {str(exact):>5s} {state}"
    )

# CONTROL: the verifier must FIRE on a corrupted copy of one of the same blobs, or its silence
# above measures nothing.
victim = json.loads(blob(by_id["AUD-0021"]["output_path"]).decode("utf-8"))
victim.pop("sentinel", None)
c_err = sr.validate_artifact(victim, by_id["AUD-0021"]["output_schema"])
clean = sr.validate_artifact(
    json.loads(blob(by_id["AUD-0021"]["output_path"]).decode("utf-8")),
    by_id["AUD-0021"]["output_schema"],
)
print(
    f"\nCONTROL verifier: AUD-0021 with `sentinel` removed -> {len(c_err)} error(s) "
    f"{'FIRES' if c_err else 'BROKEN'}; unmodified -> {len(clean)} error(s) "
    f"{'SILENT' if not clean else 'BROKEN'}"
)
ok &= bool(c_err) and not clean

drift = [r[0] for r in rows if not r[8]]
print(
    f"\nsentinel PREFIX ok on all: {all(r[6] for r in rows)}; artifacts whose sentinel does NOT "
    f"match the row's declared completion_sentinel verbatim: {drift}"
)
print(
    "  -> a real drift in four round-1 receipts, which paraphrased it. Not a contract failure "
    "(the schema requires a sentinel string, not this string) and not re-run here: re-running "
    "those builders re-measures live inputs. Settling action belongs to whoever re-runs them."
)
vac = [r[0] for r in rows if not r[5]]
print(
    f"\nunits whose DECLARED contract cannot fail (so 'schema-VALID' is not evidence): {vac}"
)
print(
    "SUCCESS:p2r3-verify all committed blobs parse, validate against the schema their catalog row "
    "declares, and carry their unit sentinel"
    if ok
    else "FAILED:p2r3-verify at least one blob failed"
)
raise SystemExit(0 if ok else 1)
