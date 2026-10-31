#!/usr/bin/env python3
"""Verify live facts that BLD-0040/0042 probes will assert."""
import json
from pathlib import Path

REPO = Path(r"C:\Users\Prekzursil\p2-g1")

tr = json.loads(
    (REPO / "command-center/TEST-REGISTRY.json").read_text(encoding="utf-8")
)
suites = tr.get("suites") or []
print("suites:", len(suites))
for s in suites:
    p = REPO / str(s.get("path") or "")
    print(f"  {s.get('path')}: exists={p.is_file()} tests={s.get('tests')}")

d = json.loads(
    (REPO / "command-center/receipts/BLD-0042.json").read_text(encoding="utf-8")
)
rep = d["report"]
print("\nBLD-0042 declaration sites (first 8 findings):")
ok = miss = 0
for f in rep["finding_register"][:8]:
    site = str(f.get("declaration_site") or "")
    if ":" not in site:
        print(f"  MALFORMED site: {site!r}")
        continue
    rel, line = site.rsplit(":", 1)
    q = REPO / rel
    present = q.is_file()
    if present:
        ok += 1
    else:
        miss += 1
    print(f"  {site}: exists={present} kind={f.get('kind')} "
          f"explicit={f.get('explicit_call_site_count')}")
print(f"sites ok={ok} missing={miss}")

c = rep["counts"]
total = (c["function_defaults_exercised"] + c["function_defaults_explicit_only"]
         + c["function_defaults_unreferenced"] + c["function_defaults_assertionless_only"]
         + c["function_defaults_dynamic_unknown"])
print("\ncounts identity: exercised+explicit+unref+assertionless+dynamic =",
      total, "vs public_default_parameters =", c["public_default_parameters"])
print("reported_findings:", c["reported_findings"],
      "len(finding_register):", len(rep["finding_register"]))
print("cli_defaults_reported_unexercised:", c["cli_defaults_reported_unexercised"])
krc = rep["known_require_complete"]
print("krc.cli[0]:", json.dumps(krc["cli"][0])[:300])
print("krc.function[0]:", json.dumps(krc["function"][0])[:220])

d40 = json.loads(
    (REPO / "command-center/receipts/BLD-0040.json").read_text(encoding="utf-8")
)
print("\nBLD-0040 artifacts rows:", len(d40.get("artifacts") or []))
print("BLD-0040 tests rows:", len(d40.get("tests") or []))
