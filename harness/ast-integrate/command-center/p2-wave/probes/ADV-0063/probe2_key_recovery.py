#!/usr/bin/env python3
"""Probe 2: documented recovery on the fixture; consumer refuses post-revocation signatures.

Mechanically different from probe 1: this is a consumer-side acceptance check
after a revocation-point recovery, not a publisher authorisation check.
A consumer who already trusted the compromised key must stop accepting
artifacts signed after the revocation point, while still accepting
pre-revocation signatures and replacement-key signatures.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from fixture_registry import (  # noqa: E402
    Consumer,
    FixtureRegistry,
    mint_synthetic_key,
    sign_artifact,
)

T_FROM = "2026-08-24T00:00:00Z"
T_UNTIL = "2026-12-31T00:00:00Z"
T_PRE = "2026-08-24T10:00:00Z"
T_REV = "2026-08-24T12:00:00Z"
T_POST = "2026-08-24T13:00:00Z"
T_NEW = "2026-08-24T14:00:00Z"


def main() -> int:
    key_old = mint_synthetic_key("syn-A-compromised")
    key_new = mint_synthetic_key("syn-A-replacement")
    registry = FixtureRegistry(enforce_owner=True)
    registry.register_publisher("pub-A", "Identity A (fixture)", key_old, T_FROM, T_UNTIL)

    d_v1, art_v1 = registry.publish(
        authenticated_as="pub-A",
        key=key_old,
        package="pkg.owned",
        version="1.0.0",
        payload=b"payload-pre",
        signed_at=T_PRE,
    )
    consumer = Consumer(honor_revocation_point=True)
    consumer.trust_from_registry(registry, "pub-A")
    before = consumer.accept(art_v1) if art_v1 is not None else None

    steps = registry.documented_recovery_procedure(
        publisher_id="pub-A",
        compromised_key_id=key_old.key_id,
        replacement=key_new,
        revoked_at=T_REV,
        replacement_valid_until=T_UNTIL,
    )
    consumer.refresh_identity(registry, "pub-A")

    forged_post = sign_artifact(
        key=key_old,
        package="pkg.owned",
        version="1.2.0",
        owner_id="pub-A",
        signed_as="pub-A",
        signed_at=T_POST,
        payload=b"payload-post-compromise",
    )
    after_forged = consumer.accept(forged_post)
    pre_after_refresh = consumer.accept(art_v1) if art_v1 is not None else None

    d_new, art_new = registry.publish(
        authenticated_as="pub-A",
        key=key_new,
        package="pkg.owned",
        version="1.3.0",
        payload=b"payload-replacement",
        signed_at=T_NEW,
    )
    after_new = consumer.accept(art_new) if art_new is not None else None

    registry_refuses_old = registry.publish(
        authenticated_as="pub-A",
        key=key_old,
        package="pkg.owned",
        version="1.4.0",
        payload=b"payload-old-key-after-revocation",
        signed_at=T_POST,
    )[0]

    naive = Consumer(honor_revocation_point=False)
    naive.trust_from_registry(registry, "pub-A")
    naive_post = naive.accept(forged_post)

    report = {
        "probe": "probe2-key-recovery",
        "unit_id": "ADV-0063",
        "synthetic_keys_only": True,
        "secrets_serialized": False,
        "revocation_point": T_REV,
        "key_old": key_old.public_record(),
        "key_new": key_new.public_record(),
        "recovery_steps": [
            {k: v for k, v in step.items() if k != "publisher"} for step in steps
        ],
        "pre_revocation": {
            "publish": d_v1.action,
            "consumer": None if before is None else before.action,
            "reason": None if before is None else before.reason,
        },
        "post_revocation_compromised_key": {
            "signed_at": T_POST,
            "consumer": after_forged.action,
            "reason": after_forged.reason,
            "registry_publish": registry_refuses_old.action,
        },
        "pre_revocation_after_refresh": None
        if pre_after_refresh is None
        else {
            "consumer": pre_after_refresh.action,
            "reason": pre_after_refresh.reason,
        },
        "replacement_key": {
            "publish": d_new.action,
            "consumer": None if after_new is None else after_new.action,
            "reason": None if after_new is None else after_new.reason,
        },
        "naive_consumer": {
            "honor_revocation_point": False,
            "post_revocation_action": naive_post.action,
            "fired_on_bad_state": naive_post.accepted,
        },
        "pass": False,
    }
    ok = (
        d_v1.accepted
        and before is not None
        and before.accepted
        and not after_forged.accepted
        and pre_after_refresh is not None
        and pre_after_refresh.accepted
        and d_new.accepted
        and after_new is not None
        and after_new.accepted
        and not registry_refuses_old.accepted
        and naive_post.accepted
        and len(steps) == 3
    )
    report["pass"] = bool(ok)
    print(json.dumps(report, sort_keys=True))
    if not ok:
        print("FAILED:ADV-0063-probe2 recovery drill did not hold")
        return 1
    print(
        "pre_accepted=True post_compromised_refused=True "
        "replacement_accepted=True naive_mutant_accepted=True"
    )
    print(
        "SUCCESS:ADV-0063-probe2 consumer who trusted the compromised key "
        "refuses signatures after the revocation point"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
