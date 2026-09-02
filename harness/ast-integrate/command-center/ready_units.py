r"""Compute which of the 2,007 work units are STARTABLE right now, and emit a build worklist.

A unit is READY when every dependency it declares is satisfiable:
  * a unit-id dependency is satisfied when that unit's artifact is DELIVERED -- see `delivered()`
    below. Until 2026-08-12 this was bare `Path.exists()`, which is the textbook Goodhart failure:
    the check rewards a file being present, so the program produced 44 present files of which 43
    SELF-DECLARE `state: BLOCKED` or `FAILED`. Measured with
    `command-center/p2-wave/_b1r2_scope_measure.py`: existence counted 44 delivered; the honest
    predicate counts 1, returns 36 wrongly-excluded units to the READY set, and removes 1
    phantom-ready unit (ADV-0002) that was queued on a BLOCKED foundation;
  * a `B\d+` bucket dependency is treated per the owner ruling recorded in OWNER-DECISIONS.md --
    "a bucket-level gate artifact exists" -- which makes a zero-member bucket SATISFIED rather than
    permanently unsatisfiable. That reading is recorded here explicitly because 876 edges turn on
    it and a silent choice would be indefensible;
  * an unknown-form token (ARC, WFA, CC, IMP -- 41 of them) cannot be resolved and BLOCKS, because
    guessing at it would manufacture readiness.

Owner-gated units (`owner_approval_required`) are excluded from the build list no matter how ready
they look: an executor cannot supply an owner ruling.

Emits command-center/READY-UNITS.json for the build fan-out to consume.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "command-center/WORK-UNIT-CATALOG.json"
BUCKET = re.compile(r"B\d+")

#: Owner ruling of record, 2026-08-11: a B-token dependency means "a bucket-level gate artifact
#: exists", which is the only reading that does not leave 876 edges permanently unsatisfiable.
BUCKET_SATISFIED = True

#: A receipt that classifies itself as one of these is NOT a delivered dependency. Reading the
#: FIELD rather than the document is deliberate: an earlier stub-word regex over the same 44
#: artifacts produced 22 false positives by matching prose that merely discussed placeholders.
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})

#: Both-states control fixtures for `--self-test`. The OLD existence predicate accepts BOTH of
#: these, so a control that only checked the good one would have been silent in both states.
CONTROL_GOOD = (
    "WFA-0001"  # exists, non-empty, parses, schema-VALID, no self-declared failure
)
CONTROL_BAD = (
    # exists, non-empty, parses, schema-VALID, but state == BLOCKED. Repointed
    # 2026-08-20: the previous control (ADV-0031) was legitimately delivered by the
    # P2/adversarial wave (state BLOCKED -> SUCCESS in e760762c), which is the one
    # state transition this live-artifact control cannot survive. When ADV-0026 is
    # delivered in its turn, re-elect a new self-declared-BLOCKED unit here.
    "ADV-0026"
)

#: A third control, added 2026-08-12 after an adversarial verifier REFUTED the round-1 claim that
#: "a `state` field is forgeable by a one-word edit; schema validation is not". For the 23 units
#: whose declared contract resolves to a JSON-Schema meta-schema, schema validation is ALSO one
#: word away: `command-center/receipts/IMP-0433.json` with `state` flipped to SUCCESS was accepted
#: as DELIVERED by the predicate shipped that day. This fixture IS that known-broken state, so the
#: vacuity guard below has a state in which it must FIRE.
CONTROL_VACUOUS = (
    "command-center/p2-wave/fixtures/ready-units/IMP-0433-state-SUCCESS-mutant.json"
)

#: Garbage probes for the contract-vacuity guard. A declared contract that accepts ALL of these
#: cannot fail, so "schema-VALID against it" carries no information. The first two are the exact
#: shapes that fooled an earlier verifier in this program (a doc asserting 999999 passing tests,
#: and a 2,000-repeated-character blob); the third is the empty object.
_GARBAGE_PROBES = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)

#: The type-appropriate fallback for an artifact under command-center/receipts/. Measured
#: discriminating: it rejects all three garbage probes (11/11/10 errors) and rejects a receipt
#: whose `state` says SUCCESS without a passing independent reviewer (3 errors).
RECEIPT_FALLBACK_CONTRACT = "command-center/schema/receipt.schema.json"

#: A text artifact is degenerate when it carries almost no information -- the 2,000-repeated-
#: character shape that fooled an earlier verifier in this program. Measured on the real corpus:
#: the smallest genuine report on disk has 60+ distinct characters, the blob has 1.
_TEXT_MIN_DISTINCT_CHARS = 12
_TEXT_MAX_SINGLE_CHAR_RUN = 200
#: A floor, disclosed as a heuristic and not as a contract: an artifact whose whole body is its own
#: completion sentinel is not a report. 200 non-space characters is roughly two sentences.
_TEXT_MIN_BODY_CHARS = 200

_DISCRIMINATES: dict[str, bool] = {}
_REGISTRY_CACHE: list = []  # [] = not attempted, [None] = attempted and unavailable, [reg] = live


def contract_discriminates(resolver, schema: str) -> bool:
    """Can this declared contract ever FAIL? Measured against garbage, never assumed.

    Census over the catalog's 367 distinct declarations (2026-08-12): 364 reject all three
    probes, 3 reject none -- `https://json-schema.org/draft/2020-12/schema` (21 units),
    `command-center/schema/meta/json-schema-draft.json` (1) and
    `command-center/schema/_meta/json-schema-2020-12.json` (1). The split is clean, so the
    all-three threshold is not a judgement call: nothing sits in between.
    """
    if resolver is None or not schema:
        return False
    cached = _DISCRIMINATES.get(schema)
    if cached is not None:
        return cached
    verdict = True
    for probe in _GARBAGE_PROBES:
        try:
            rejected = bool(resolver.validate_artifact(probe, schema))
        except Exception:  # a contract that raises on garbage has still refused it
            rejected = True
        if not rejected:
            verdict = False
            break
    _DISCRIMINATES[schema] = verdict
    return verdict


def _registry(resolver):
    """The platform schema registry, or None. Cached because building it walks the schema tree.

    Load-bearing for `schema_doc_verdict`: WITHOUT it the real WFA-0001 pack raises
    `_WrappedReferencingError` on every probe (its `$ref` is unresolvable in a bare validator) and
    would be admitted by the raise-means-refused convention -- i.e. for the wrong reason. WITH it
    the same pack returns 12/12/11 real errors on the three garbage probes, so it passes on merit.
    Measured by `command-center/p2-wave/_r3_probe_registry.py`.
    """
    if _REGISTRY_CACHE:
        return _REGISTRY_CACHE[0]
    reg = None
    if resolver is not None:
        try:
            reg = resolver.build_registry()
        except Exception:  # pragma: no cover - environment-dependent
            reg = None
    _REGISTRY_CACHE.append(reg)
    return reg


def schema_doc_verdict(doc, resolver=None) -> tuple[bool, str]:
    """Is this document a usable, NON-VACUOUS JSON Schema? Returns (verdict, stage).

    The type-appropriate fallback for the 23 units whose declared contract resolves to a
    JSON-Schema meta-schema: for an artifact that really IS a schema the meta-schema is the right
    KIND of contract and merely cannot reject unrelated JSON.

    The returned stage names WHICH gate rejected, so a control can assert the stage rather than
    only the boolean -- see the refutation below for why that matters.

    REFUTED WORDING, recorded rather than deleted. Until 2026-08-12 this function was
    `looks_like_schema_doc` and its docstring claimed: "Two-sided by construction: it accepts the
    real WFA-0001 schema pack, and rejects all three garbage probes AND a structurally-broken
    schema". Both halves were false, and an adversarial verifier proved it by execution
    (`command-center/p2-wave/_av2_tmp/probe_bypass.py`, `probe_merit.py`):

      * the three garbage probes were rejected by the ONE-LINE `$schema`/`$id` key check, not on
        merit. Adding a single `"$schema"` key to the SAME garbage flipped the end-to-end
        predicate to `delivered=True`  -- `BYPASS_PROVEN = True`, including for a bare
        `{"$schema": ...}` of 59 bytes and for the 2,000-x blob;
      * the structurally-broken example `{"type": 123, "required": "not-an-array"}` carries
        neither key, so it too was rejected by the key check and `check_schema` was never
        exercised by that control at all -- a control silent in both states.

    The fix is the third stage below: the document, USED AS A CONTRACT, must reject the same
    garbage probes the declared contract could not. That is the property the fallback was always
    claiming, now measured instead of assumed.
    """
    if not isinstance(doc, dict) or not ("$schema" in doc or "$id" in doc):
        return False, "not-a-schema-document"
    try:
        import jsonschema
    except (
        Exception
    ):  # pragma: no cover - jsonschema is a hard dependency of the resolver
        return False, "schema-document-uncheckable:jsonschema-missing"
    try:
        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception as e:
        return False, f"schema-document-invalid:{type(e).__name__}"
    reg = _registry(resolver)
    try:
        v = (
            jsonschema.Draft202012Validator(doc, registry=reg)
            if reg is not None
            else jsonschema.Draft202012Validator(doc)
        )
    except Exception as e:
        return False, f"schema-document-unusable:{type(e).__name__}"
    raised = None
    for probe in _GARBAGE_PROBES:
        try:
            if not list(v.iter_errors(probe)):
                return False, "schema-document-vacuous"
        except Exception as e:  # a contract that raises on garbage has still refused it
            raised = type(e).__name__
    if raised:
        # Disclosed, not hidden: refusal by exception is weaker evidence than refusal by
        # validation, because an unresolvable $ref refuses EVERYTHING including a good instance.
        return True, f"schema-document-discriminates(refused-by-raise:{raised})"
    return True, "schema-document-discriminates"


def looks_like_schema_doc(doc, resolver=None) -> bool:
    """Boolean face of `schema_doc_verdict`, kept so the round-2 probes still run unchanged."""
    return schema_doc_verdict(doc, resolver)[0]


def text_artifact_verdict(unit: dict, text: str) -> tuple[bool, str]:
    """The gate for a NON-JSON artifact. Returns (verdict, reason).

    D2, confirmed by execution (`command-center/p2-wave/_av2_tmp/probe_nonjson.py`): until
    2026-08-12 `artifact_delivered` returned `(True, "non-json-present")` for ANY non-.json path
    that merely existed and was non-empty, so a 2,000-x blob named `.md` was DELIVERED while the
    identical bytes named `.json` were rejected -- `SUFFIX_BYPASS_PROVEN = True`. 120 units (all
    `.md`) sit behind that branch; 0 of their artifacts exist yet, so the hole was latent, not
    already-exploited.

    What this gate can and cannot do, stated plainly because the reason string is quoted:
      * it CANNOT contract-prove the artifact. All 6 contracts those 120 rows declare reject a
        markdown string outright (1 error each: they are object schemas), so the declared
        contract is unenforceable against the declared output_path. That is a catalog-internal
        inconsistency; this module reports it and does not silently paper over it;
      * it CAN require the row's own `completion_sentinel` (declared by 2007/2007 rows) to appear
        in the document, and the content not to be degenerate.
    """
    sentinel = unit.get("completion_sentinel")
    if not isinstance(sentinel, str) or not sentinel.strip():
        return False, "text-artifact:no-completion-sentinel-declared"
    if sentinel.strip() not in text:
        return False, "text-artifact:completion-sentinel-absent"
    # Everything below is measured on the BODY -- the text with the sentinel removed -- so that an
    # artifact consisting only of its own sentinel cannot pass on the sentinel's own characters.
    body = text.replace(sentinel.strip(), "")
    solid = "".join(body.split())
    if len(solid) < _TEXT_MIN_BODY_CHARS:
        return False, f"text-artifact:body-too-thin(non-space-chars={len(solid)})"
    if len(set(solid)) < _TEXT_MIN_DISTINCT_CHARS:
        return False, f"text-artifact:degenerate(distinct-chars={len(set(solid))})"
    run = longest = 1
    for a, b in zip(body, body[1:]):
        run = run + 1 if a == b else 1
        longest = max(longest, run)
    if longest >= _TEXT_MAX_SINGLE_CHAR_RUN:
        return False, f"text-artifact:degenerate(longest-run={longest})"
    return (
        True,
        "delivered(text artifact; sentinel present, non-degenerate; declared contract is NOT machine-checkable against a .md path)",
    )


def _fallback_contract(doc, resolver) -> tuple[bool, str]:
    """The declared contract cannot fail. Find one for this artifact CLASS that can.

    Keyed on the DOCUMENT, never on the output path: a path-keyed fallback would give the
    `--self-test` mutant a different verdict than the real receipt it is a copy of, which is a
    control that measures its own location instead of the defect.
    """
    ok, stage = schema_doc_verdict(doc, resolver)
    if ok:
        return (
            True,
            f"delivered(schema-document fallback; declared contract is vacuous; {stage})",
        )
    try:
        errs = resolver.validate_artifact(doc, RECEIPT_FALLBACK_CONTRACT)
    except Exception as e:
        return (
            False,
            f"contract-vacuous;receipt-fallback-unresolvable:{type(e).__name__}",
        )
    if not errs:
        return True, "delivered(receipt fallback; declared contract is vacuous)"
    return (
        False,
        f"contract-vacuous:no-type-appropriate-fallback(receipt-errors={len(errs)})",
    )


_TOOLS_COMMAND_CENTER = Path(__file__).resolve().parents[1] / "tools" / "command-center"
_RESOLVER_REL = "platform/lib/schema_resolver.py"


def _degradation_surface():
    """The shared user-visible degradation surface (tools/command-center/degradation_events.py).

    Reuses the already-imported module object when a caller loaded it first, so every listener
    sees one ``USER_EVENTS`` list; returns None only when the surface module itself is absent.
    """
    mod = sys.modules.get("degradation_events")
    if mod is not None:
        return mod
    if str(_TOOLS_COMMAND_CENTER) not in sys.path:
        sys.path.insert(0, str(_TOOLS_COMMAND_CENTER))
    try:
        import degradation_events
    except ImportError:
        return None
    return degradation_events


def _resolver_unavailable(reason: str) -> None:
    """Report the lost contract-validation capability LOUDLY, then hand back None.

    The work artifact (the catalog) is untouched by this fallback, and the event names it so.
    When even the degradation surface is missing, a plain stderr DEGRADATION-EVENT line is
    written: the degradation is never silent.
    """
    fields = {
        "capability_lost": "jsonschema-contract-validation",
        "fallback_kind": "capability-missing-shim",
        "source": "command-center/ready_units.py:_load_resolver",
        "artifact_preserved": "command-center/WORK-UNIT-CATALOG.json",
        "reason": reason,
        "resolver": _RESOLVER_REL,
    }
    surface = _degradation_surface()
    if surface is not None:
        surface.emit_loud(**fields)
        return None
    event = {"type": "DEGRADATION-EVENT", "user_visible": True, **fields}
    print("DEGRADATION-EVENT " + json.dumps(event, sort_keys=True), file=sys.stderr)
    return None


def _load_resolver():
    """Load platform/lib/schema_resolver for contract validation.

    Returns None when unavailable. The caller DEGRADES LOUDLY rather than silently: a predicate
    that quietly stops validating is exactly the no-op gate this module is being fixed to stop
    manufacturing. Every None path first emits a user-visible DEGRADATION-EVENT naming the lost
    capability and the preserved artifact.
    """
    p = REPO / "platform" / "lib" / "schema_resolver.py"
    if not p.is_file():
        return _resolver_unavailable("schema_resolver.py absent")  # loud, then return None
    try:
        sys.path.insert(0, str(p.parent))
        spec = importlib.util.spec_from_file_location("schema_resolver", p)
        if spec is None or spec.loader is None:
            return _resolver_unavailable("schema_resolver.py yields no import spec")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["schema_resolver"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as exc:  # pragma: no cover - environment-dependent
        return _resolver_unavailable(f"{type(exc).__name__}: {exc}"[:200])


def artifact_delivered(unit: dict, resolver=None) -> tuple[bool, str]:
    """Is this unit's artifact actually DELIVERED? Returns (verdict, reason).

    Conditions, in order, each of which a bare `exists()` skips:
      1. output_path declared and the file exists;
      2. it is non-empty (a 0-byte file is the MSYS redirect-truncation signature);
      3. if NOT JSON, `text_artifact_verdict` decides -- this branch used to be a bare
         `return True, "non-json-present"`, which an adversarial verifier proved admits a
         2,000-x blob named `.md` (`SUFFIX_BYPASS_PROVEN = True`, 120 units behind it);
      3b. if JSON, it parses;
      4. if it validates against a declared output_schema, it must actually validate;
      4b. that declared contract must be ABLE TO FAIL -- see `contract_discriminates`. When it
          cannot, condition 4 is not evidence and a type-appropriate contract is applied instead;
      4c. when that substitute is "the artifact is itself a schema", the artifact must be a
          NON-VACUOUS schema -- see `schema_doc_verdict`. Until 2026-08-12 this stage checked
          only for a `$schema`/`$id` key, and one added key flipped garbage to DELIVERED;
      5. if it carries a `state` field, that state must not be a self-declared failure.

    Condition 5 alone is forgeable by a one-word edit, which is why 4 is also enforced; condition
    4 alone passes a perfectly-formed receipt that says BLOCKED, which is why 5 is also enforced.

    REFUTED WORDING, recorded rather than deleted: until 2026-08-12 this docstring's companion
    report claimed schema validation is NOT one word away. For the 23 meta-declaring units it was
    -- `command-center/receipts/IMP-0433.json` with `state` flipped to SUCCESS was accepted as
    DELIVERED, because its declared contract is the draft-2020-12 meta-schema, which accepts any
    object. Condition 4b closes that; `--self-test` keeps the mutant as a live control.
    """
    p = unit.get("output_path")
    if not p:
        return False, "no-output-path"
    fp = REPO / p
    if not fp.exists():
        return False, "absent"
    try:
        size = fp.stat().st_size
    except OSError as e:
        return False, f"stat-error:{type(e).__name__}"
    if size <= 0:
        return False, "empty"
    if fp.suffix.lower() != ".json":
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return False, f"read-error:{type(e).__name__}"
        return text_artifact_verdict(unit, text)
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"unparseable:{type(e).__name__}"
    schema = unit.get("output_schema")
    why_ok = "delivered"
    if resolver is not None and isinstance(schema, str) and schema:
        try:
            errs = resolver.validate_artifact(doc, schema)
        except Exception as e:
            # FAIL CLOSED. This was `pass` until 2026-08-12, which silently skipped condition 4
            # for any unit whose contract raised. Census that day: 0 of 367 distinct declarations
            # raise, so closing the hole moves nothing -- it removes a latent silent-pass.
            return False, f"contract-unresolvable:{type(e).__name__}"
        if errs:
            return False, f"schema-invalid:{len(errs)}"
        if not contract_discriminates(resolver, schema):
            ok, why = _fallback_contract(doc, resolver)
            if not ok:
                return False, why
            why_ok = why
    if isinstance(doc, dict):
        st = doc.get("state")
        if isinstance(st, str) and st.upper() in NOT_DELIVERING:
            return False, f"self-declared:{st.upper()}"
    return True, why_ok


def _prefix_predicate(unit: dict, resolver) -> bool:
    """The predicate as it stood BEFORE condition 4b, reproduced so every control can print the
    column that matters: did the OLD instrument agree? A control whose two states score the same
    under the old and the new predicate has measured nothing."""
    p = unit.get("output_path")
    fp = REPO / p if p else None
    if not p or not fp.exists() or fp.stat().st_size <= 0:
        return False
    if fp.suffix.lower() != ".json":
        return True
    try:
        doc = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return False
    schema = unit.get("output_schema")
    if resolver is not None and isinstance(schema, str) and schema:
        try:
            if resolver.validate_artifact(doc, schema):
                return False
        except Exception:
            pass  # the old silent skip, reproduced deliberately
    if isinstance(doc, dict):
        st = doc.get("state")
        if isinstance(st, str) and st.upper() in NOT_DELIVERING:
            return False
    return True


def _pre_r3_schema_doc(doc) -> bool:
    """`looks_like_schema_doc` as it stood BEFORE 2026-08-12 (key check + `check_schema`, no merit
    stage), reproduced so every schema-document control can print the column that matters: did the
    OLD instrument accept this? A fixture the old instrument also rejected is not a control for
    this defect."""
    if not isinstance(doc, dict) or not ("$schema" in doc or "$id" in doc):
        return False
    try:
        import jsonschema

        jsonschema.Draft202012Validator.check_schema(doc)
    except Exception:
        return False
    return True


_META = "https://json-schema.org/draft/2020-12/schema"

#: One fixture per STAGE of `schema_doc_verdict`, because the defect being fixed was a control
#: that never reached the stage it claimed to test. `want_stage` is a prefix, asserted so a
#: document rejected by the WRONG stage still fails the control.
_SCHEMA_DOC_CONTROLS = (
    (
        "unkeyed garbage",
        {"totally": "unrelated", "passing_tests": 999999},
        False,
        "not-a-schema-document",
    ),
    (
        "KEYED garbage (the proven bypass)",
        {"$schema": _META, "totally": "unrelated", "passing_tests": 999999},
        False,
        "schema-document-vacuous",
    ),
    ("bare {$schema}", {"$schema": _META}, False, "schema-document-vacuous"),
    (
        "$id-only garbage",
        {"$id": "urn:x", "totally": "unrelated"},
        False,
        "schema-document-vacuous",
    ),
    (
        "KEYED broken schema",
        {"$schema": _META, "type": 123, "required": "not-an-array"},
        False,
        "schema-document-invalid",
    ),
)

#: One fixture per STAGE of `text_artifact_verdict`, same reasoning. All five are `.md`, so the
#: PRE-fix predicate accepted every one of them -- that column is the proof the control bites.
_TEXT_CONTROLS = (
    ("good note", "text-good.md", True, "delivered(text artifact"),
    (
        "sentinel absent",
        "text-no-sentinel.md",
        False,
        "text-artifact:completion-sentinel-absent",
    ),
    ("body is only the sentinel", "text-thin.md", False, "text-artifact:body-too-thin"),
    (
        "2,000-x blob body",
        "text-degenerate-run.md",
        False,
        "text-artifact:degenerate(longest-run",
    ),
    (
        "two-character body",
        "text-degenerate-distinct.md",
        False,
        "text-artifact:degenerate(distinct-chars",
    ),
)

_TEXT_FIXTURE_DIR = "command-center/p2-wave/fixtures/ready-units"
#: The catalog row the text controls borrow: a real unit, so the sentinel under test is the one
#: the catalog actually declares rather than one this file invented.
_TEXT_CONTROL_UNIT = "CNL-0002"


def self_test() -> int:
    """Both-states control over THREE fixtures, each with the old predicate's column beside it.

    CONTROL_GOOD    a real delivered artifact          -> must be ACCEPTED
    CONTROL_BAD     a real self-declared-BLOCKED one   -> must be REJECTED
    CONTROL_VACUOUS the one-word `state: SUCCESS` mutant of a receipt whose declared contract
                    cannot fail -> must be REJECTED, and the OLD predicate must have ACCEPTED
                    it. If the old column ever reads False the fixture has stopped being a
                    known-broken state and this control no longer proves anything.
    """
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    by_id = {u["id"]: u for u in doc["work_units"]}
    resolver = _load_resolver()
    print(
        f"  resolver: {'loaded' if resolver else 'UNAVAILABLE (contract check degraded)'}"
    )
    ok = True

    # --- control the vacuity detector itself, before trusting any verdict that uses it. ---
    vac = "https://json-schema.org/draft/2020-12/schema"
    disc = RECEIPT_FALLBACK_CONTRACT
    for label, sch, want in (
        ("known-VACUOUS", vac, False),
        ("known-DISCRIMINATING", disc, True),
    ):
        got = contract_discriminates(resolver, sch)
        state = "OK" if got is want else "BROKEN"
        if got is not want:
            ok = False
        print(
            f"  CONTROL contract_discriminates({label}): want={want} got={got} -> {state}"
        )

    for uid, want in ((CONTROL_GOOD, True), (CONTROL_BAD, False)):
        u = by_id.get(uid)
        if u is None:
            print(f"  CONTROL {uid}: NOT IN CATALOG -- control cannot run")
            ok = False
            continue
        got, why = artifact_delivered(u, resolver)
        legacy = bool(u.get("output_path")) and (REPO / u["output_path"]).exists()
        verdict = "OK" if got is want else "BROKEN"
        if got is not want:
            ok = False
        print(
            f"  CONTROL {uid}: want={want} got={got} ({why}) "
            f"| legacy-exists-predicate={legacy} | pre-4b-predicate={_prefix_predicate(u, resolver)}"
            f" -> {verdict}"
        )

    # --- the vacuity control: a known-broken state the guard must FIRE on. ---
    mutant_unit = dict(by_id.get("IMP-0433") or {})
    if not mutant_unit or not (REPO / CONTROL_VACUOUS).is_file():
        print(
            f"  CONTROL VACUOUS: fixture {CONTROL_VACUOUS} MISSING -- control cannot run"
        )
        ok = False
    else:
        mutant_unit["output_path"] = CONTROL_VACUOUS
        got, why = artifact_delivered(mutant_unit, resolver)
        before = _prefix_predicate(mutant_unit, resolver)
        fires = (got is False) and (before is True)
        if not fires:
            ok = False
        print(
            f"  CONTROL VACUOUS (state:=SUCCESS mutant): want=False got={got} ({why}) "
            f"| pre-4b-predicate={before} -> {'OK (guard fires on the broken state)' if fires else 'BROKEN'}"
        )

    # --- D1: the schema-document fallback, one control per STAGE, with the old column. ---
    wfa = by_id.get("WFA-0001")
    cases = list(_SCHEMA_DOC_CONTROLS)
    if wfa and (REPO / wfa["output_path"]).is_file():
        cases.append(
            (
                "REAL WFA-0001 pack",
                json.loads((REPO / wfa["output_path"]).read_text(encoding="utf-8")),
                True,
                "schema-document-discriminates",
            )
        )
    else:
        print(
            "  CONTROL schema-doc: WFA-0001 artifact MISSING -- the known-GOOD state cannot run"
        )
        ok = False
    for label, doc, want, want_stage in cases:
        got, stage = schema_doc_verdict(doc, resolver)
        good = got is want and stage.startswith(want_stage)
        if not good:
            ok = False
        print(
            f"  CONTROL schema-doc {label:34s}: want={want!s:5s} got={got!s:5s} "
            f"stage={stage:46s} | pre-r3-instrument={_pre_r3_schema_doc(doc)!s:5s} "
            f"-> {'OK' if good else 'BROKEN'}"
        )

    # --- D2: the text-artifact gate, one control per STAGE, with the old column. ---
    tunit = by_id.get(_TEXT_CONTROL_UNIT)
    if tunit is None:
        print(
            f"  CONTROL text: {_TEXT_CONTROL_UNIT} not in catalog -- controls cannot run"
        )
        ok = False
    else:
        for label, fname, want, want_reason in _TEXT_CONTROLS:
            rel = f"{_TEXT_FIXTURE_DIR}/{fname}"
            if not (REPO / rel).is_file():
                print(
                    f"  CONTROL text {label}: fixture {rel} MISSING -- control cannot run"
                )
                ok = False
                continue
            u = dict(tunit)
            u["output_path"] = rel
            got, why = artifact_delivered(u, resolver)
            before = _prefix_predicate(u, resolver)
            good = got is want and why.startswith(want_reason)
            if not good:
                ok = False
            print(
                f"  CONTROL text {label:26s}: want={want!s:5s} got={got!s:5s} "
                f"reason={why[:52]:52s} | pre-r3-predicate={before!s:5s} "
                f"-> {'OK' if good else 'BROKEN'}"
            )

    if not ok:
        print(
            "FAILED:ready-units self-test the delivered() control does not discriminate"
        )
        return 1
    print(
        "SUCCESS:ready-units self-test delivered() fires on every known-broken state "
        "(self-declared failure, vacuous-contract false green, one-key $schema bypass, "
        "and non-.json suffix bypass) and is silent on the good ones"
    )
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    doc = json.loads(CATALOG.read_text(encoding="utf-8"))
    units = doc["work_units"]
    by_id = {u["id"]: u for u in units}
    resolver = _load_resolver()
    _cache: dict[str, bool] = {}

    def delivered(uid: str) -> bool:
        if uid in _cache:
            return _cache[uid]
        u = by_id.get(uid)
        verdict = False if u is None else artifact_delivered(u, resolver)[0]
        _cache[uid] = verdict
        return verdict

    ready, blocked, gated = [], [], []
    block_reason: Counter = Counter()
    for u in units:
        if delivered(u["id"]):
            continue  # already delivered
        if u.get("owner_approval_required"):
            gated.append(u["id"])
            continue
        reasons = []
        for dep in u.get("dependencies") or []:
            if BUCKET.fullmatch(dep):
                if not BUCKET_SATISFIED:
                    reasons.append(f"bucket:{dep}")
            elif dep in by_id:
                if not delivered(dep):
                    reasons.append(f"unbuilt:{dep}")
            else:
                reasons.append(f"unknown-token:{dep}")
        if reasons:
            blocked.append(u["id"])
            block_reason[reasons[0].split(":")[0]] += 1
        else:
            ready.append(u["id"])

    # Contract-vacuity census. Published because "schema-VALID" is only evidence when the schema
    # can fail, and 23 units declare one that cannot. Reported, never used to block a unit: the
    # catalog's schema choice is not the unit's fault, so the fallback in condition 4b decides.
    vac_decls = sorted(
        {
            s
            for s in (u.get("output_schema") for u in units)
            if isinstance(s, str) and s and not contract_discriminates(resolver, s)
        }
    )
    vac_units = [u["id"] for u in units if u.get("output_schema") in vac_decls]

    out = {
        "bucket_reading": "a bucket-level gate artifact exists (owner ruling 2026-08-11)",
        "contract_vacuity": {
            "probe": "a declared contract must reject all 3 garbage probes to count as evidence",
            "vacuous_declarations": vac_decls,
            "units_declaring_a_vacuous_contract": len(vac_units),
            "vacuous_unit_ids": vac_units,
            "checker": "unavailable" if resolver is None else "live",
        },
        "totals": {
            "units": len(units),
            "already_delivered": sum(1 for u in units if delivered(u["id"])),
            "artifacts_present_but_not_delivered": sum(
                1
                for u in units
                if u.get("output_path")
                and (REPO / u["output_path"]).exists()
                and not delivered(u["id"])
            ),
            "ready": len(ready),
            "blocked": len(blocked),
            "owner_gated": len(gated),
        },
        "block_reasons": dict(block_reason),
        "ready_units": ready,
        "owner_gated_units": gated,
    }
    (REPO / "command-center/READY-UNITS.json").write_text(
        json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )

    t = out["totals"]
    print(
        f"  units {t['units']} | delivered {t['already_delivered']} | READY {t['ready']} "
        f"| blocked {t['blocked']} | owner-gated {t['owner_gated']}"
    )
    print(
        f"  artifacts present but NOT delivered (self-declared failure / invalid): "
        f"{t['artifacts_present_but_not_delivered']}"
    )
    print(f"  block reasons: {out['block_reasons']}")
    cv = out["contract_vacuity"]
    print(
        f"  contract-vacuity: {len(cv['vacuous_declarations'])} declarations cannot fail, "
        f"declared by {cv['units_declaring_a_vacuous_contract']} units (checker={cv['checker']})"
    )
    print(f"  first ready: {ready[:8]}")
    if (
        t["ready"] + t["blocked"] + t["owner_gated"] + t["already_delivered"]
        != t["units"]
    ):
        print("FAILED:ready-units partition does not sum to the unit count")
        return 1
    # FAIL CLOSED on a dark contract checker. `--self-test` already refused to report a verdict
    # without a resolver; this path did not, and printed `SUCCESS:ready-units partition sums
    # correctly` while every one of the 367 declarations went unchecked. Measured 2026-08-12 by
    # `command-center/p2-wave/_i1_dark_probe2.py` (monkeypatched `_load_resolver`) with the LIT
    # state as its control:
    #     main/LIT   exit=0  contract-vacuity: 3 declarations ... (checker=live)
    #     main/DARK  exit=0  contract-vacuity: 367 declarations ... (checker=unavailable)
    # The sum still added up, so the only assertion this function made was arithmetic over a
    # partition computed from an unenforced predicate. A partition is not trustworthy because it
    # sums; it is trustworthy because the predicate that produced it actually ran. That distinction
    # is the whole reason this file was rewritten, and it was missing from its own exit code.
    if cv["checker"] != "live":
        print(
            f"FAILED:ready-units the contract checker is {cv['checker']} -- "
            f"{len(cv['vacuous_declarations'])} declarations went unchecked, so this partition "
            "is not evidence of anything"
        )
        return 1
    print("\nSUCCESS:ready-units partition sums correctly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
