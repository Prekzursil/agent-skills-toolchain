#!/usr/bin/env python3
"""IMP-0007 probe1: fixture strict-parser accept/reject pair (signal 1)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "plugin"))
import manifest_schema as M  # noqa: E402
import strict_parser_policy as P  # noqa: E402

PROBE = Path(__file__).resolve().parent
EVIDENCE = (
    "TWO independent signals: (1) a strict-mode parser fixture rejects a manifest "
    "carrying a bare unknown key and accepts the same key under `x-`; (2) the real "
    "client's own loader (invoked out of process) reproduces the same accept/reject "
    "pair — a fixture parser alone is one signal."
)


def main() -> int:
    schema = M.load_schema(REPO)
    P.assert_frozen_matches_schema(schema)
    base = P.fixture_base_manifest()
    pair = P.accept_reject_pair(base)

    bare = P.mutate_bare_unknown(base)
    under_x = P.mutate_under_extension(base)
    v_bad1, v_bad2 = M.validate_manifest(bare, schema)
    v_good1, v_good2 = M.validate_manifest(under_x, schema)

    schema_pair_ok = (
        (not v_bad1.ok)
        and (not v_bad2.ok)
        and v_bad1.error_code == M.ERR_UNKNOWN_TOP_LEVEL
        and v_good1.ok
        and v_good2.ok
    )
    confirmed = bool(pair.get("pair_confirmed") and schema_pair_ok)

    meas = {
        "probe": "probe1-fixture-accept-reject",
        "probe_1_confirmed": confirmed,
        "ok": confirmed,
        "policy_pair": pair,
        "schema_reject_bare": {
            "jsonschema_ok": v_bad1.ok,
            "jsonschema_code": v_bad1.error_code,
            "fastjsonschema_ok": v_bad2.ok,
            "fastjsonschema_code": v_bad2.error_code,
        },
        "schema_accept_x": {
            "jsonschema_ok": v_good1.ok,
            "fastjsonschema_ok": v_good2.ok,
        },
        "extension_prefix": P.EXTENSION_PREFIX,
        "frozen_top_level_keys": sorted(P.FROZEN_TOP_LEVEL_KEYS),
    }
    (PROBE / "probe1-measurement.json").write_text(
        json.dumps(meas, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "NAMED PROBE 1: FIXTURE STRICT-PARSER ACCEPT/REJECT",
        "PROBE-1-BEGIN:IMP-0007",
        "stage=p2-deliver",
        f"evidence_requirement_verbatim={EVIDENCE}",
        f"extension_prefix={P.EXTENSION_PREFIX}",
        f"policy_pair_confirmed={pair.get('pair_confirmed')}",
        f"reject_bare_unknown={pair.get('reject_bare_unknown')}",
        f"accept_under_x={pair.get('accept_under_x')}",
        f"schema_pair_ok={schema_pair_ok}",
        f"probe_1_confirmed={confirmed}",
        "PROBE-1-COMPLETE:IMP-0007",
        "SUCCESS:IMP-0007-probe1" if confirmed else "FAILED:IMP-0007-probe1",
    ]
    raw = "\n".join(lines) + "\n"
    (PROBE / "probe1-fixture-accept-reject.raw.txt").write_text(raw, encoding="utf-8")
    print(raw, end="")
    return 0 if confirmed else 1


if __name__ == "__main__":
    raise SystemExit(main())
