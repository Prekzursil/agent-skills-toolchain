#!/usr/bin/env python3
"""Probe 1: identity B updates a package owned by identity A on a fixture registry.

Control: identity A publishes its own update in the same run.
Negative control: a naive registry that skips the owner check accepts B's update.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixture_registry import (  # noqa: E402
    FixtureRegistry,
    mint_synthetic_key,
    production_publisher_surface,
)

REPO = HERE.parents[3]
T_FROM = "2026-08-24T00:00:00Z"
T_UNTIL = "2026-12-31T00:00:00Z"
T_V1 = "2026-08-24T10:00:00Z"
T_SPOOF = "2026-08-24T11:00:00Z"
T_OWNER = "2026-08-24T11:05:00Z"


def main() -> int:
    key_a = mint_synthetic_key("syn-A-1")
    key_b = mint_synthetic_key("syn-B-1")
    honest = FixtureRegistry(enforce_owner=True)
    honest.register_publisher("pub-A", "Identity A (fixture)", key_a, T_FROM, T_UNTIL)
    honest.register_publisher("pub-B", "Identity B (fixture)", key_b, T_FROM, T_UNTIL)

    d_create, art_v1 = honest.publish(
        authenticated_as="pub-A",
        key=key_a,
        package="pkg.owned",
        version="1.0.0",
        payload=b"payload-v1",
        signed_at=T_V1,
    )
    d_spoof, art_spoof = honest.publish(
        authenticated_as="pub-B",
        key=key_b,
        package="pkg.owned",
        version="1.1.0",
        payload=b"payload-spoof",
        signed_at=T_SPOOF,
    )
    d_owner, art_owner = honest.publish(
        authenticated_as="pub-A",
        key=key_a,
        package="pkg.owned",
        version="1.1.0",
        payload=b"payload-owner-update",
        signed_at=T_OWNER,
    )

    naive = FixtureRegistry(enforce_owner=False)
    naive.register_publisher("pub-A", "Identity A (fixture)", key_a, T_FROM, T_UNTIL)
    naive.register_publisher("pub-B", "Identity B (fixture)", key_b, T_FROM, T_UNTIL)
    naive.publish(
        authenticated_as="pub-A",
        key=key_a,
        package="pkg.owned",
        version="1.0.0",
        payload=b"payload-v1",
        signed_at=T_V1,
    )
    d_naive, art_naive = naive.publish(
        authenticated_as="pub-B",
        key=key_b,
        package="pkg.owned",
        version="1.1.0",
        payload=b"payload-spoof",
        signed_at=T_SPOOF,
    )

    census = production_publisher_surface(REPO)
    versions = sorted((honest.packages.get("pkg.owned") or {}).get("versions") or {})
    report = {
        "probe": "probe1-cross-identity-publish",
        "unit_id": "ADV-0063",
        "synthetic_keys_only": True,
        "secrets_serialized": False,
        "key_a": key_a.public_record(),
        "key_b": key_b.public_record(),
        "create": {
            "action": d_create.action,
            "reason": d_create.reason,
            "artifact_present": art_v1 is not None,
        },
        "foreign_update": {
            "authenticated_as": "pub-B",
            "package": "pkg.owned",
            "owner": "pub-A",
            "action": d_spoof.action,
            "reason": d_spoof.reason,
            "artifact_present": art_spoof is not None,
        },
        "owner_update_control": {
            "authenticated_as": "pub-A",
            "action": d_owner.action,
            "reason": d_owner.reason,
            "artifact_present": art_owner is not None,
            "versions_after": versions,
        },
        "naive_mutant": {
            "enforce_owner": False,
            "action": d_naive.action,
            "artifact_present": art_naive is not None,
            "fired_on_bad_state": d_naive.accepted and art_naive is not None,
        },
        "production_census": census,
        "pass": False,
    }
    ok = (
        d_create.accepted
        and art_v1 is not None
        and not d_spoof.accepted
        and art_spoof is None
        and d_owner.accepted
        and art_owner is not None
        and d_naive.accepted
        and art_naive is not None
        and versions == ["1.0.0", "1.1.0"]
        and not census["any_present"]
    )
    report["pass"] = bool(ok)
    print(json.dumps(report, sort_keys=True))
    if not ok:
        print("FAILED:ADV-0063-probe1 cross-identity drill did not hold")
        return 1
    print(
        "foreign_refused=True owner_update_accepted=True "
        "naive_mutant_accepted=True synthetic_keys_only=True"
    )
    print("SUCCESS:ADV-0063-probe1 identity B refused; identity A published its own update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
