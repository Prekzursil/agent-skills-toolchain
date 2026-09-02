#!/usr/bin/env python3
"""IMP-0108 probe 2: independent closure + omit-dep negative + secret gate.

The independent BFS in independent_closure.py does not import the
exporter's resolver. A bundle whose blobs do not cover that walk fails.
Deliberately omitting leaf's blob must fail export. The IMP-0004-shaped
gate must be silent on the clean bundle and fire on a planted private-key
PEM without echoing the secret body.
"""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import independent_closure as IC  # noqa: E402
from marketplace.offline_export import (  # noqa: E402
    extract_offline_bundle,
    extracted_blob_paths,
    export_offline_bundle,
)
from marketplace.resolver import IncompleteClosure  # noqa: E402
from marketplace.secret_gate import (  # noqa: E402
    SecretInBundle,
    assert_clean,
    report_contains_secret_body,
    scan_bytes,
)
from marketplace.signatures import private_pem, verify_signature  # noqa: E402
from marketplace.testkit import diamond_registry  # noqa: E402

PLANTED_BODY = "SYNTHETIC-NOT-A-REAL-KEY-BODY-IMP0108"


def main() -> int:
    fx = diamond_registry()
    walk = IC.independent_required_closure(fx.index, [("app", "1.0.0")])
    extra_in_walk = "extra@1.0.0" in walk
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        dest = tmp / "bundle.zip"
        man = export_offline_bundle(
            index=fx.index,
            blobs=fx.blobs,
            private_keys=fx.private_keys,
            package_key_id=fx.package_key_id,
            selection=[("app", "1.0.0")],
            dest=dest,
            created_at="2026-08-24T18:00:00+00:00",
            signed_at="2026-08-24T18:00:00+00:00",
        )
        extract = tmp / "out"
        extract_offline_bundle(dest, extract)
        packed = sorted(f"{e['name']}@{e['version']}" for e in man["entries"])
        disk = extracted_blob_paths(extract)
        far_side_ok = True
        for entry in man["entries"]:
            try:
                verify_signature(entry["signature"], entry["digest"])
            except Exception:
                far_side_ok = False
        with zipfile.ZipFile(dest, "r") as zf:
            packed_files = {n: zf.read(n) for n in zf.namelist()}
        clean_ok = True
        try:
            assert_clean(packed_files)
        except SecretInBundle:
            clean_ok = False
        priv = private_pem(next(iter(fx.private_keys.values())))
        private_absent = priv not in b"".join(packed_files.values())
        planted = (
            b"-----BEGIN PRIVATE KEY-----\n"
            + PLANTED_BODY.encode("ascii")
            + b"\n-----END PRIVATE KEY-----\n"
        )
        planted_findings = scan_bytes(planted, "planted.pem")
        planted_report = str(SecretInBundle(planted_findings))
        planted_fires = len(planted_findings) == 1
        no_leak = not report_contains_secret_body(planted_report, PLANTED_BODY)

        omit_fired = False
        omit_named_leaf = False
        blobs = dict(fx.blobs)
        del blobs["leaf@1.0.0"]
        omit_dest = tmp / "omit.zip"
        try:
            export_offline_bundle(
                index=fx.index,
                blobs=blobs,
                private_keys=fx.private_keys,
                package_key_id=fx.package_key_id,
                selection=[("app", "1.0.0")],
                dest=omit_dest,
            )
        except IncompleteClosure as exc:
            omit_fired = True
            omit_named_leaf = "leaf@1.0.0" in str(exc)
            omit_wrote = omit_dest.exists()
        else:
            omit_wrote = omit_dest.exists()

        closure_ok = packed == walk and not extra_in_walk and len(disk) == len(walk)
        payload = {
            "probe": "probe2-closure-omit-secret",
            "unit_id": "IMP-0108",
            "independent_closure": walk,
            "packed": packed,
            "extracted_blobs": disk,
            "closure_contained": closure_ok,
            "optional_extra_excluded": not extra_in_walk,
            "far_side_signatures_verify": far_side_ok,
            "secret_gate_silent_on_clean": clean_ok,
            "private_pem_absent_from_bundle": private_absent,
            "planted_control_fired": planted_fires,
            "planted_report_leaks_body": not no_leak,
            "omit_dep_fired": omit_fired,
            "omit_named_leaf": omit_named_leaf,
            "omit_wrote_bundle": omit_wrote,
            "pass": (
                closure_ok
                and far_side_ok
                and clean_ok
                and private_absent
                and planted_fires
                and no_leak
                and omit_fired
                and omit_named_leaf
                and not omit_wrote
            ),
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"closure_ok={closure_ok} omit_fired={omit_fired} "
            f"clean_gate={clean_ok} planted={planted_fires} leak={not no_leak}"
        )
        if not payload["pass"]:
            print("FAILED:IMP-0108-probe2 closure/omit/secret gate")
            return 1
        print(
            "SUCCESS:IMP-0108-probe2 independent closure contained; "
            "omit-dep fails; secret gate both-states"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
