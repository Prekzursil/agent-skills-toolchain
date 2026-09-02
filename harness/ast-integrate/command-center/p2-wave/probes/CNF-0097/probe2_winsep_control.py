#!/usr/bin/env python3
"""Probe 2: schema/sentinel + Windows-separator detector control + listing proof."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import schema_local as SL  # noqa: E402
import winsep as W  # noqa: E402

ART_REL = "command-center/confirmation/CNF-0097-clean-install-linux.json"
SCHEMA_REL = "command-center/schema/install-report.schema.json"
SENTINEL = (
    "SUCCESS:CNF-0097 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the container listing "
    "proves no repository checkout was present during the install. Any other "
    "terminal state is FAILED:CNF-0097 <classification> with the diagnostic "
    "tail attached."
)
MUTANT = '''
def dest(prefix, name):
    return "\\\\".join([prefix, "plugin", name])
'''


def main() -> int:
    art = REPO / ART_REL
    schema_path = REPO / SCHEMA_REL
    if not art.is_file():
        print("FAILED:CNF-0097-probe2 confirmation artifact missing")
        return 1
    text = art.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        print("FAILED:CNF-0097-probe2 sentinel-absent")
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0097-probe2 self-declared {doc.get('state')}")
        return 1
    if not schema_path.is_file() or schema_path.stat().st_size <= 0:
        print("FAILED:CNF-0097-probe2 catalog output_schema missing")
        return 1
    if not SL.contract_rejects_garbage():
        print("FAILED:CNF-0097-probe2 local contract accepted garbage")
        return 1
    schema_errs = SL.validate_doc(doc)
    if schema_errs:
        print("FAILED:CNF-0097-probe2 schema errors")
        for err in schema_errs[:12]:
            print(f"  {err}")
        return 1
    print("schema_ok=True")

    container = doc.get("container") or {}
    listing = container.get("root_listing") or []
    markers = container.get("repo_markers_found") or []
    print(f"listing={listing} markers={markers} repo={container.get('repo_checkout_present')}")
    if container.get("repo_checkout_present") is not False:
        print("FAILED:CNF-0097-probe2 repo_checkout_present is not false")
        return 1
    if markers:
        print("FAILED:CNF-0097-probe2 repo markers recorded")
        return 1
    if "opt" in listing or ".git" in listing or "command-center" in listing:
        print("FAILED:CNF-0097-probe2 listing contains a repository checkout name")
        return 1
    if "artifact" not in listing:
        print("FAILED:CNF-0097-probe2 listing is not a container root listing")
        return 1

    clean = W.scan_tree(HERE / "payload")
    print(f"clean_winsep={clean}")
    if clean:
        print("FAILED:CNF-0097-probe2 published payload has Windows path separators")
        return 1
    with tempfile.TemporaryDirectory(prefix="cnf0097-mutant-") as tmp:
        mutant_path = Path(tmp) / "install_mutant.py"
        mutant_path.write_text(MUTANT, encoding="utf-8")
        mutant_hits = W.scan_python(mutant_path.read_text(encoding="utf-8"), "install_mutant.py")
    print(f"mutant_winsep={mutant_hits}")
    kinds = {h.get("kind") for h in mutant_hits}
    if "backslash-join" not in kinds:
        print("FAILED:CNF-0097-probe2 detector silent on known-broken backslash-join fixture")
        return 1

    answers = doc.get("answers") or {}
    if answers.get("windows_separator_assumed") is not False:
        print("FAILED:CNF-0097-probe2 artifact overclaims or misses windows_separator_assumed=false")
        return 1
    if answers.get("install_succeeded") is not True:
        print("FAILED:CNF-0097-probe2 install_succeeded is not true")
        return 1
    if not (doc.get("install") or {}).get("success"):
        print("FAILED:CNF-0097-probe2 install.success is not true")
        return 1
    if not (doc.get("health_check") or {}).get("healthy"):
        print("FAILED:CNF-0097-probe2 health_check.healthy is not true")
        return 1
    digest = container.get("image_digest") or ""
    if not str(digest).startswith("sha256:") or len(digest) < 70:
        print("FAILED:CNF-0097-probe2 image_digest missing")
        return 1
    print("SUCCESS:CNF-0097-probe2 schema sentinel winsep-control listing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
