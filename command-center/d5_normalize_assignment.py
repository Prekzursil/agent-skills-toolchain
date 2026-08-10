"""D5: normalise every work unit's ``assigned_model_vendor_role`` to the canonical object form.

Two transforms, both non-lossy:

1. **slash-triple string -> object.** ``"<model>/<vendor>/<role>"`` splits on the two slashes.
   The base schema's ``assignment_triple_string`` pattern guarantees exactly two slashes and no
   empty segment, so the split is total; this tool re-verifies that per value rather than
   trusting the pattern.

2. **prose ``model`` -> structured multi-vendor.** A ``model`` carrying ``" + "`` encodes two
   vendors in one string with ``vendor: "mixed"``. It becomes a primary ``{model, vendor, role}``
   plus ``co_assignments[]`` and an enumerated ``multi_vendor_policy``. A ``model`` carrying a
   trailing parenthetical qualifier keeps the bare model token and moves the qualifier into
   ``basis``. In BOTH cases the original string is preserved verbatim in ``rationale``, so the
   transform can be audited and reversed.

Only ``work_units[]`` is touched. The separate ``items[]`` register (different schema, different
purpose) is not read or written, and no unit is renumbered, added or dropped - asserted, not
assumed.

Usage::

    python command-center/d5_normalize_assignment.py --check   # census + planned diff, no write
    python command-center/d5_normalize_assignment.py --apply   # rewrite the catalog in place
    python command-center/d5_normalize_assignment.py --self-test  # both-states detector control
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "WORK-UNIT-CATALOG.json"
FIELD = "assigned_model_vendor_role"

#: vendor for each known model token. Derived from the corpus' own object-form pairings,
#: not guessed: every ('anthropic', model) and ('openai', model) pair below is attested.
MODEL_VENDOR = {
    "opus": "anthropic",
    "gpt-5-codex": "openai",
    "gpt-5.x-codex": "openai",
    "gpt-5.1-codex": "openai",
    "codex-cli": "openai",
    "codex-cli-default": "openai",
}

#: prose fragment -> enumerated multi_vendor_policy token
POLICY_FROM_PROSE = (
    (
        "run independently, results compared not merged",
        "independent-compared-not-merged",
    ),
    ("model-diverse", "model-diverse-panel"),
)

_QUALIFIER = re.compile(r"^(?P<token>[^\s(]+)\s*\((?P<qual>.+)\)$")


#: the corpus writes these sub-objects with alphabetically ordered keys; newly built or
#: rewritten assignments follow suit so the diff stays minimal and visually consistent.
_KEY_ORDER = (
    "basis",
    "co_assignments",
    "model",
    "multi_vendor_policy",
    "rationale",
    "role",
    "vendor",
)


class NormalizeError(RuntimeError):
    """A value this tool refuses to guess at. Never silently passed through."""


def serialize(doc: dict[str, Any]) -> bytes:
    """Reproduce the catalog's EXACT on-disk serialisation.

    Measured off disk, not assumed: ``indent=1``, ``sort_keys=False``, CRLF line endings, and
    NO trailing newline. Writing bytes (not text) is deliberate - ``write_text`` on Windows
    would translate every ``\\n`` again and double the line endings.
    """
    text = json.dumps(doc, indent=1, ensure_ascii=False)
    return text.replace("\n", "\r\n").encode("utf-8")


def _ordered(assignment: dict[str, Any]) -> dict[str, Any]:
    known = {k: assignment[k] for k in _KEY_ORDER if k in assignment}
    extra = {k: v for k, v in assignment.items() if k not in known}
    return {**known, **extra}


def split_triple(value: str) -> dict[str, str]:
    """``'<model>/<vendor>/<role>'`` -> the canonical object. Refuses anything else."""
    parts = value.split("/")
    if len(parts) != 3 or not all(p.strip() for p in parts):
        raise NormalizeError(f"not a model/vendor/role triple: {value!r}")
    model, vendor, role = (p.strip() for p in parts)
    return _ordered({"model": model, "vendor": vendor, "role": role})


def _policy_for(prose: str) -> str:
    for fragment, token in POLICY_FROM_PROSE:
        if fragment in prose:
            return token
    raise NormalizeError(f"no multi_vendor_policy maps to prose: {prose!r}")


def normalize_multi_vendor(assignment: dict[str, Any]) -> dict[str, Any] | None:
    """Structure a prose ``model``. Returns None when the value is already clean."""
    model = assignment.get("model")
    if not isinstance(model, str):
        return None

    if " + " in model:
        head, _, tail = model.partition(" + ")
        primary_token = head.strip()
        # the tail is '<model> (<prose>)'
        m = _QUALIFIER.match(tail.strip())
        if not m:
            raise NormalizeError(
                f"multi-vendor tail has no '(...)' policy prose: {tail!r}"
            )
        co_token, prose = m.group("token"), m.group("qual")
        for token in (primary_token, co_token):
            if token not in MODEL_VENDOR:
                raise NormalizeError(f"unknown model token {token!r} in {model!r}")
        out = dict(assignment)
        out["model"] = primary_token
        out["vendor"] = MODEL_VENDOR[primary_token]
        out["co_assignments"] = [{"model": co_token, "vendor": MODEL_VENDOR[co_token]}]
        out["multi_vendor_policy"] = _policy_for(prose)
        out.setdefault("rationale", f"normalised from the single-string form {model!r}")
        return _ordered(out)

    m = _QUALIFIER.match(model)
    if m:
        token, qual = m.group("token"), m.group("qual")
        if token not in MODEL_VENDOR:
            raise NormalizeError(f"unknown model token {token!r} in {model!r}")
        out = dict(assignment)
        out["model"] = token
        if out.get("vendor") != MODEL_VENDOR[token]:
            raise NormalizeError(
                f"{token!r} maps to vendor {MODEL_VENDOR[token]!r} but unit says {out.get('vendor')!r}"
            )
        out.setdefault("basis", qual)
        out.setdefault("rationale", f"normalised from the single-string form {model!r}")
        return _ordered(out)

    return None


def normalize_unit(unit: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Return (possibly-new assignment, transform-name or None)."""
    val = unit.get(FIELD)
    if isinstance(val, str):
        return split_triple(val), "string-triple-to-object"
    if isinstance(val, dict):
        out = normalize_multi_vendor(val)
        if out is not None:
            kind = (
                "prose-model-to-co-assignments"
                if "co_assignments" in out
                else "prose-model-to-basis"
            )
            return out, kind
        return val, None
    raise NormalizeError(f"{unit.get('id')}: unexpected type {type(val).__name__}")


def run(apply: bool) -> int:
    # read BYTES, not text: read_text applies universal newlines and would turn the file's CRLF
    # into LF, making the byte-identity check below compare against the wrong bytes and always
    # fail. The whole point of that check is that it compares what is actually on disk.
    raw = CATALOG.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    units = doc["work_units"]
    ids_before = [u["id"] for u in units]

    changes: list[tuple[str, str, Any, Any]] = []
    for unit in units:
        before = unit.get(FIELD)
        after, kind = normalize_unit(unit)
        if kind:
            changes.append((unit["id"], kind, before, after))
            unit[FIELD] = after

    # invariants asserted, not assumed
    ids_after = [u["id"] for u in doc["work_units"]]
    assert ids_after == ids_before, "unit ids reordered or changed"
    assert len(ids_after) == len(set(ids_after)) == 2007, f"unit count {len(ids_after)}"
    assert len(doc.get("items", [])) == 103, "items[] register was disturbed"

    by_kind: dict[str, int] = {}
    for _, kind, _, _ in changes:
        by_kind[kind] = by_kind.get(kind, 0) + 1

    print(f"units={len(units)}  changed={len(changes)}")
    for kind, n in sorted(by_kind.items()):
        print(f"  {n:5d}  {kind}")
    print("\nsample of each transform:")
    seen: set[str] = set()
    for uid, kind, before, after in changes:
        if kind in seen:
            continue
        seen.add(kind)
        print(f"  [{kind}] {uid}")
        print(f"      before: {json.dumps(before)}")
        print(f"      after:  {json.dumps(after)}")

    residual = sum(1 for u in doc["work_units"] if not isinstance(u.get(FIELD), dict))
    print(f"\nnon-object residual after transform = {residual}")

    new_bytes = serialize(doc)
    if not changes:
        # Idempotence AND serialisation control in one: a no-op run must reproduce the file
        # byte-for-byte. Getting this wrong rewrites all 5.3 MB as a whitespace diff.
        assert new_bytes == raw, "serialisation does not round-trip; refusing to write"
        print("no changes; serialisation round-trips byte-for-byte")

    if apply:
        CATALOG.write_bytes(new_bytes)
        print(f"WROTE {CATALOG}  ({len(new_bytes)} bytes)")
    else:
        print("(--check: no write)")
    return 0


def self_test() -> int:
    """Both-states control: the transform must FIRE on known-bad and be IDENTITY on known-good."""
    ok = True

    # known-BAD 1: string triple -> must transform
    unit = {"id": "X-0001", FIELD: "opus/anthropic/implementer"}
    after, kind = normalize_unit(unit)
    fired = kind == "string-triple-to-object" and after == {
        "model": "opus",
        "vendor": "anthropic",
        "role": "implementer",
    }
    print(f"[{'PASS' if fired else 'FAIL'}] fires on string triple -> {after}")
    ok &= fired

    # known-BAD 2: multi-vendor prose -> must produce co_assignments + policy
    unit = {
        "id": "X-0002",
        FIELD: {
            "model": "opus + gpt-5-codex (>=2 vendors, run independently, results compared not merged)",
            "role": "paired-independent-refuter",
            "vendor": "mixed",
        },
    }
    after, kind = normalize_unit(unit)
    fired = (
        kind == "prose-model-to-co-assignments"
        and after["model"] == "opus"
        and after["vendor"] == "anthropic"
        and after["co_assignments"] == [{"model": "gpt-5-codex", "vendor": "openai"}]
        and after["multi_vendor_policy"] == "independent-compared-not-merged"
        and "opus + gpt-5-codex" in after["rationale"]
    )
    print(
        f"[{'PASS' if fired else 'FAIL'}] fires on multi-vendor prose -> {json.dumps(after)}"
    )
    ok &= fired

    # known-GOOD: already canonical -> must be IDENTITY (a transform that always fires
    # measures nothing)
    good = {"model": "opus", "vendor": "anthropic", "role": "implementer"}
    after, kind = normalize_unit({"id": "X-0003", FIELD: dict(good)})
    silent = kind is None and after == good
    print(
        f"[{'PASS' if silent else 'FAIL'}] SILENT on already-canonical -> kind={kind}"
    )
    ok &= silent

    good2 = {"model": "opus", "vendor": "anthropic", "role": "r", "basis": "b"}
    after, kind = normalize_unit({"id": "X-0004", FIELD: dict(good2)})
    silent = kind is None and after == good2
    print(f"[{'PASS' if silent else 'FAIL'}] SILENT on canonical+basis -> kind={kind}")
    ok &= silent

    # refuses to guess rather than passing an unknown value through
    try:
        normalize_unit(
            {
                "id": "X-0005",
                FIELD: {
                    "model": "llama-9 + opus (model-diverse)",
                    "vendor": "x",
                    "role": "r",
                },
            }
        )
        print("[FAIL] accepted an unknown model token")
        ok = False
    except NormalizeError as exc:
        print(f"[PASS] refuses unknown model token -> {exc}")

    try:
        normalize_unit({"id": "X-0006", FIELD: "only/two"})
        print("[FAIL] accepted a 2-segment string")
        ok = False
    except NormalizeError as exc:
        print(f"[PASS] refuses a 2-segment string -> {exc}")

    print("SUCCESS:d5-self-test" if ok else "FAILED:d5-self-test")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--check", action="store_true", help="census + planned diff, no write"
    )
    g.add_argument("--apply", action="store_true", help="rewrite the catalog in place")
    g.add_argument(
        "--self-test", action="store_true", help="both-states detector control"
    )
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return run(apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
