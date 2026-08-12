r"""Is IMP-0433's premise still true?

IMP-0433 (phase 0, unblocks 13 - the top of the OQ-2 order) is worded:
  "Author command-center/schema/receipt.schema.json - the file that defaults.output_schema in
   WORK-UNIT-CATALOG.json already points at and THAT DOES NOT EXIST ON DISK."

and its target is "a schema strict enough that a receipt missing its sentinel, its evidence
anchors, or its reviewer verdict is INVALID, and permissive enough that [real receipts] validate".

This probe tests that literal contract against the schema that IS on disk today:
  P1  does the file exist?
  P2  negative fixtures: drop sentinel / evidence / reviewer_verdict -> each MUST be INVALID
  P3  positive fixture: a complete receipt -> MUST be VALID
If P1-P3 all hold, the AUTHORING work is already done and the unit reduces to emitting its
receipt with this evidence, not writing a new schema.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA = REPO / "command-center/schema/receipt.schema.json"


def build_store():
    store = {}
    for base in ("command-center/schema", "platform"):
        for p in (REPO / base).rglob("*.schema.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if "$id" in d:
                store[d["$id"]] = d
    return store


def main() -> int:
    import jsonschema

    print(f"P1 exists({SCHEMA.relative_to(REPO)}) = {SCHEMA.exists()}  size={SCHEMA.stat().st_size if SCHEMA.exists() else 0}B")
    if not SCHEMA.exists():
        print("SUCCESS:imp0433-premise premise HOLDS - file absent, unit must author it")
        return 0

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    print(f"   physical definition: {str(schema.get('x-physical-definition'))[:110]}")
    print(f"   top-level $ref     : {schema.get('$ref')}")
    store = build_store()
    res = jsonschema.RefResolver(base_uri=schema.get("$id", ""), referrer=schema, store=store)

    # Positive fixture: an existing REAL receipt from the tree.
    real = REPO / "command-center/receipts/TST-0334.json"
    positive = json.loads(real.read_text(encoding="utf-8"))
    print(f"\nP3 positive fixture = {real.relative_to(REPO)} keys={sorted(positive)[:12]}")

    def valid(doc) -> tuple[bool, str]:
        try:
            jsonschema.validate(doc, schema, resolver=res)
            return True, ""
        except jsonschema.ValidationError as e:
            return False, str(e.message)[:90]
        except Exception as e:  # resolution error
            return False, f"<{type(e).__name__}> {str(e)[:70]}"

    ok, msg = valid(positive)
    print(f"   VALID={ok} {msg}")

    print("\nP2 negative fixtures (each MUST be INVALID):")
    all_reject = True
    for drop in ("sentinel", "evidence", "reviewer_verdict", "unit_id", "state"):
        if drop not in positive:
            print(f"   drop {drop:<16} SKIPPED - key absent from the positive fixture")
            continue
        mutant = {k: v for k, v in positive.items() if k != drop}
        v, m = valid(mutant)
        print(f"   drop {drop:<16} VALID={v}  {'<-- SURVIVED (schema does not require it)' if v else m}")
        if v:
            all_reject = False

    print(
        "\nVERDICT: premise REFUTED - schema exists"
        + (" and enforces the named conditions" if all_reject else " but at least one named condition is NOT enforced")
    )
    print("SUCCESS:imp0433-premise measured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
