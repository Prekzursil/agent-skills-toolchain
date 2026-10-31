#!/usr/bin/env python3
"""Write TST-0179 + TST-0180 probe files."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROBES = HERE.parent / "command-center" / "p2-wave" / "probes"

M179 = r'''#!/usr/bin/env python3
"""TST-0179 measured layer: strict plugin-manifest parser + reference emitter.

STRICTEST-CLIENT semantics: the accepted top-level field set is closed; an
unknown field is a rejection whose error NAMES the field. The emitter is the
authoring-side counterpart: it must never emit a field outside the accepted
set.
"""
from __future__ import annotations

import json

ACCEPTED_TOP_LEVEL = {
    "name", "version", "description", "author", "license",
    "hooks", "skills", "commands", "agents", "mcpServers",
}


class StrictManifestError(Exception):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


def parse_strict(text: str) -> dict:
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise StrictManifestError("manifest must be a JSON object")
    unknown = sorted(set(doc) - ACCEPTED_TOP_LEVEL)
    if unknown:
        raise StrictManifestError(
            "strict parser: unknown top-level field(s): " + ", ".join(unknown),
            field=unknown[0],
        )
    return doc


def parse_lenient(text: str) -> dict:
    """KNOWN-BROKEN counterpart: loads anything, no allowlist (detector control)."""
    return json.loads(text)


def emit(fields: dict) -> str:
    """Reference emitter: reject-at-authoring any field outside the accepted set."""
    bad = sorted(set(fields) - ACCEPTED_TOP_LEVEL)
    if bad:
        raise StrictManifestError("emitter refuses unknown top-level field(s): " + ", ".join(bad), field=bad[0])
    return json.dumps(fields, indent=2, sort_keys=True)
'''

P179_1 = r'''#!/usr/bin/env python3
"""TST-0179 probe1 -- strict client parser rejects an unknown top-level manifest field
with an error naming it; a clean manifest is accepted (both-states control).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import manifest_domain as MD  # noqa: E402

UNIT = "TST-0179"


def main() -> int:
    clean = {"name": "sample-plugin", "version": "1.0.0", "hooks": {}}
    clean_text = MD.emit(clean)
    accepted = None
    try:
        accepted = MD.parse_strict(clean_text)
    except MD.StrictManifestError:
        pass

    poisoned = dict(clean)
    poisoned["telemetry"] = {"endpoint": "https://example.invalid/ingest"}
    err = None
    named_field = None
    try:
        MD.parse_strict(json.dumps(poisoned))
    except MD.StrictManifestError as e:
        err = str(e)
        named_field = e.field

    payload = {
        "probe": "probe1-unknown-field",
        "unit_id": UNIT,
        "pass": accepted is not None and err is not None and named_field == "telemetry",
        "clean_manifest_accepted": accepted is not None,
        "unknown_field_rejected": err is not None,
        "error_names_field": named_field,
        "error_text": err,
        "accepted_top_level_count": len(MD.ACCEPTED_TOP_LEVEL),
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 clean=accepted unknown=rejected field=%s" % (UNIT, named_field))
        return 0
    print("FAILED:%s-probe1 clean=%s rejected=%s named=%s"
          % (UNIT, accepted is not None, err is not None, named_field))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P179_2 = r'''#!/usr/bin/env python3
"""TST-0179 probe2 -- emitter subset proof + lenient-parser detector control.

Two independent signals: (a) a schema-diff proving the emitter's field set is a
subset of the strict parser's accepted set across generated manifests, and
(b) the known-broken lenient parser demonstrably ACCEPTS the unknown field
(proving the strict parser's rejection is a real, distinguishing behavior).
Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import manifest_domain as MD  # noqa: E402

UNIT = "TST-0179"


def main() -> int:
    rng = random.Random(179179)
    accepted = set(MD.ACCEPTED_TOP_LEVEL)
    subset_holds = True
    emitted_fields_seen: set[str] = set()
    for _ in range(200):
        fields = {}
        for f in sorted(accepted):
            if rng.random() < 0.4:
                fields[f] = rng.choice(["x", 1, True, {}, []])
        text = MD.emit(fields)  # emitter raises on any non-accepted field
        emitted_fields_seen |= set(fields)
        try:
            MD.parse_strict(text)
        except MD.StrictManifestError:
            subset_holds = False

    # an emitter forced toward a foreign field must refuse (never emits it)
    refused = False
    try:
        MD.emit({"name": "x", "analytics": 1})
    except MD.StrictManifestError:
        refused = True

    poisoned = json.dumps({"name": "x", "telemetry": {"e": 1}})
    lenient_accepted_unknown = None
    try:
        lenient_accepted_unknown = MD.parse_lenient(poisoned)
    except Exception:
        lenient_accepted_unknown = "raised"

    payload = {
        "probe": "probe2-emitter-subset",
        "unit_id": UNIT,
        "pass": subset_holds and refused and isinstance(lenient_accepted_unknown, dict),
        "schema_diff": {
            "emitter_field_universe": sorted(emitted_fields_seen),
            "accepted_set": sorted(accepted),
            "subset_holds_over_200_generated_manifests": subset_holds,
            "emitter_refuses_foreign_field": refused,
        },
        "detector_control": {
            "known_broken": "parse_lenient (plain json.loads, no allowlist)",
            "lenient_accepts_unknown_field": isinstance(lenient_accepted_unknown, dict),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 subset=True emitter-refuses=True lenient-accepts=True" % UNIT)
        return 0
    print("FAILED:%s-probe2 subset=%s refused=%s lenient=%r"
          % (UNIT, subset_holds, refused, lenient_accepted_unknown))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

M180 = r'''#!/usr/bin/env python3
"""TST-0180 measured layer: case-collision detector + clean emitter for manifests.

A case-insensitive parser treats "Hooks" and "hooks" as one key (last-wins);
the validator must reject such documents naming both, and the emitter must
never produce case-colliding keys.
"""
from __future__ import annotations

import json


class CaseCollisionError(Exception):
    def __init__(self, message: str, colliding: list[str] | None = None):
        super().__init__(message)
        self.colliding = colliding or []


def find_case_collisions(keys) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for k in keys:
        f = k.casefold()
        if f in seen and seen[f] != k:
            out.append((seen[f], k))
        else:
            seen.setdefault(f, k)
    return out


def validate_strict(text: str) -> dict:
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise CaseCollisionError("manifest must be a JSON object")
    collisions = find_case_collisions(doc.keys())
    if collisions:
        names = ", ".join("%r vs %r" % c for c in collisions)
        raise CaseCollisionError(
            "case-insensitive key collision under a case-folding parser: " + names,
            colliding=[k for c in collisions for k in c],
        )
    return doc


def emit_safe(fields: dict) -> str:
    collisions = find_case_collisions(fields.keys())
    if collisions:
        raise CaseCollisionError("emitter refuses case-colliding keys")
    return json.dumps(fields, sort_keys=True)
'''

P180_1 = r'''#!/usr/bin/env python3
"""TST-0180 probe1 -- case-distinct keys colliding under a case-insensitive parser
are detected and rejected naming both; a case-distinct non-colliding document
validates (both-states control).

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import case_guard as CG  # noqa: E402

UNIT = "TST-0180"


def main() -> int:
    ok = None
    try:
        ok = CG.validate_strict(json.dumps({"hooks": {}, "commands": [], "name": "p"}))
    except CG.CaseCollisionError:
        pass

    err = None
    colliding_named: list[str] = []
    try:
        CG.validate_strict(json.dumps({"hooks": {"a": 1}, "Hooks": {"b": 2}}))
    except CG.CaseCollisionError as e:
        err = str(e)
        colliding_named = list(e.colliding)

    both_named = set(colliding_named) == {"hooks", "Hooks"}

    payload = {
        "probe": "probe1-case-collision",
        "unit_id": UNIT,
        "pass": ok is not None and err is not None and both_named,
        "distinct_keys_validate": ok is not None,
        "colliding_keys_rejected": err is not None,
        "both_keys_named_in_error": colliding_named,
        "error_text": err,
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe1 distinct=valid collision=rejected named=%s"
              % (UNIT, colliding_named))
        return 0
    print("FAILED:%s-probe1 ok=%s err=%s named=%s"
          % (UNIT, ok is not None, err is not None, colliding_named))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

P180_2 = r'''#!/usr/bin/env python3
"""TST-0180 probe2 -- independent case-folded key-set size vs raw key-set size,
plus emitter never-collides property and a last-wins detector control.

Exit 0 on pass, 1 on any failure.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import case_guard as CG  # noqa: E402

UNIT = "TST-0180"


def main() -> int:
    # independent signal: case-folded set size vs raw set size over a colliding doc
    doc_keys = ["hooks", "Hooks", "HOOKS", "commands", "agents"]
    raw_n = len(set(doc_keys))
    folded_n = len(set(k.casefold() for k in doc_keys))
    fold_delta = raw_n - folded_n  # 3 colliding forms -> delta 2

    # emitter property: random field-name permutations never collide on emit
    rng = random.Random(180180)
    universe = ["name", "version", "hooks", "skills", "commands", "agents", "license"]
    emitter_clean = True
    for _ in range(300):
        n = rng.randint(1, len(universe))
        fields = {rng.choice(universe): 1 for _ in range(n)}  # raw dict dedups exact dupes
        try:
            CG.emit_safe(fields)
        except CG.CaseCollisionError:
            emitter_clean = False
    # emitter refuses a constructed collision
    refused = False
    try:
        CG.emit_safe({"hooks": 1, "Hooks": 2})
    except CG.CaseCollisionError:
        refused = True

    # detector control: python's own json parser is LAST-KEY-WINS on exact dupes,
    # and a case-insensitive consumer would silently drop "Hooks" vs "hooks"
    last_wins = json.loads('{"hooks": 1, "hooks": 2}') == {"hooks": 2}

    payload = {
        "probe": "probe2-folded-set-size",
        "unit_id": UNIT,
        "pass": fold_delta == 2 and emitter_clean and refused and last_wins,
        "folded_set_comparison": {
            "raw_distinct": raw_n,
            "casefolded_distinct": folded_n,
            "delta_is_collision_count": fold_delta,
        },
        "emitter": {
            "clean_over_300_generated": emitter_clean,
            "refuses_constructed_collision": refused,
        },
        "detector_control": {
            "known_broken": "json last-key-wins dedup (exact) / case-insensitive consumer (fold)",
            "last_wins_confirmed": last_wins,
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if payload["pass"]:
        print("SUCCESS:%s-probe2 fold_delta=%d emitter_clean=%s last_wins=%s"
              % (UNIT, fold_delta, emitter_clean, last_wins))
        return 0
    print("FAILED:%s-probe2 delta=%d emitter=%s refused=%s lastwins=%s"
          % (UNIT, fold_delta, emitter_clean, refused, last_wins))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

D179 = PROBES / "TST-0179"
D180 = PROBES / "TST-0180"
D179.mkdir(parents=True, exist_ok=True)
D180.mkdir(parents=True, exist_ok=True)
(D179 / "manifest_domain.py").write_text(M179, encoding="utf-8", newline="\n")
(D179 / "probe1_unknown_field.py").write_text(P179_1, encoding="utf-8", newline="\n")
(D179 / "probe2_emitter_subset.py").write_text(P179_2, encoding="utf-8", newline="\n")
(D180 / "case_guard.py").write_text(M180, encoding="utf-8", newline="\n")
(D180 / "probe1_case_collision.py").write_text(P180_1, encoding="utf-8", newline="\n")
(D180 / "probe2_folded_set_size.py").write_text(P180_2, encoding="utf-8", newline="\n")
import ast

for f in [M179, P179_1, P179_2, M180, P180_1, P180_2]:
    ast.parse(f)
print("TST-0179 + TST-0180 written + syntax OK")
