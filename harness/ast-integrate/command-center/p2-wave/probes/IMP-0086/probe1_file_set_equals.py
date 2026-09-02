#!/usr/bin/env python3
"""Named probe 1: marketplace install file set equals direct plugin install."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from marketplace.install import marketplace_install  # noqa: E402
from marketplace.tests.support import (  # noqa: E402
    PACKAGE_ID,
    generate_publisher,
    good_request,
    sign_digest,
    write_deterministic_tar,
)
from marketplace.verify import VERIFY_ORDER  # noqa: E402
from plugin.census import census  # noqa: E402
from plugin.installer import install_direct  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0086-p1-") as raw:
        tmp = Path(raw)
        blob = tmp / "demo.tar.gz"
        digest = write_deterministic_tar(blob)
        private, public_hex = generate_publisher()
        signature = sign_digest(private, digest)
        direct_home = tmp / "home-direct"
        mkt_home = tmp / "home-mkt"
        req = good_request(
            mkt_home,
            tmp / "cache-mkt",
            blob,
            digest,
            signature,
            public_hex,
            transaction_id="txn-mkt-probe1",
        )
        install_direct(
            blob,
            direct_home,
            package_id=PACKAGE_ID,
            projection_map=req.projection_map,
            transaction_id="txn-direct-probe1",
            digest=digest,
            declared_permissions=["fs:plugin-root"],
        )
        result = marketplace_install(req)
        left = census(direct_home)
        right = census(mkt_home)
        payload = {
            "probe": "probe1-file-set-equals",
            "unit_id": "IMP-0086",
            "direct": sorted(left),
            "marketplace": sorted(right),
            "equal": left == right,
            "trace": result.get("trace"),
            "expected_trace": ["fetch", *VERIFY_ORDER, "handoff"],
            "pass": bool(
                result.get("ok")
                and left == right
                and left
                and result.get("trace") == ["fetch", *VERIFY_ORDER, "handoff"]
            ),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if not payload["pass"]:
            print("FAILED:IMP-0086-probe1 file-set inequality or verify-before-handoff trace broken")
            return 1
        print("SUCCESS:IMP-0086-probe1 marketplace and direct plugin install file sets equal")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
