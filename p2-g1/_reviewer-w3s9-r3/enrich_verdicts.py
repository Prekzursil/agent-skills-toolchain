#!/usr/bin/env python3
"""Enrich VERDICTS-w3s9-r3.json with per-unit grounds, continuity and closure statement."""
import json
from pathlib import Path

P = Path(__file__).parent / "VERDICTS-w3s9-r3.json"
v = json.loads(P.read_text(encoding="utf-8"))

grounds = {
    "IMP-0022": [
        "probes 6/8 irreproducible as recorded: 'python3 -B -m plugin' (and '--negative-control') exit 2 (requires subcommand; only 'install' exists); 4x tests[] recorded as 'python3 -B file.py::node' exit 2 (python cannot open a path containing '::')",
        "receipt.schema: 6 errors (downstream_consumers[0].probe required; evidence probes missing fingerprint; manifest_registration.derivation unexpected; reviewer.finding/requirement unexpected; timestamps.rerun_at unexpected)",
    ],
    "IMP-0031": [
        "probes 6/10 irreproducible: all 6 tests[] recorded as 'python3 -B file.py::node' exit 2",
        "receipt.schema: 8 errors (same family: downstream_consumers.probe, fingerprints, extra keys)",
    ],
    "IMP-0035": [
        "probes 4/7 irreproducible: two 'command' fields carry prose descriptions not shell ('sha256(lf) vs sha256(crlf)...', 'len(crlf)-len(lf) == ...') exit 2; PNG prose command exit 127",
        "receipt.schema: 15 errors (residual_unknowns required; artifacts[0] bytes+sha256 required; role 'test' not in enum; 3 probe method values not in enum; negative_controls kind 'both-states' not in enum; extra keys)",
    ],
    "IMP-0036": [
        "probes 2/10: two recorded test commands exit 0 with EMPTY stdout (NOOP per binding rule)",
        "receipt.schema: 29 errors (evidence blocks missing verdict/probes; artifacts bytes/sha; produced_by vendor 'cursor' not in enum; reviewer/manifest_registration/timestamps extra keys)",
    ],
    "IMP-0037": [
        "probes 1/1 pass",
        "receipt.schema: 17 errors (artifacts bytes/sha required, 'note' unexpected, etc.) - schema alone fails it",
    ],
    "IMP-0038": [
        "probes 7/8 irreproducible: scenario.py exit 2; two command fields are prose ('probe2 independent os.walk', 'probe2 four kind manifests (not plugin.json)'); one recorded probe exit 127",
        "receipt.schema: 13 errors (artifacts bytes/sha, role 'tests' not in enum, etc.)",
    ],
    "IMP-0041": [
        "probes 7/9 irreproducible: prose command fields ('PluginCache.refresh after in-place truncate...', 'hashlib.sha256(source_bytes)', etc.) exit 2/127; test_reap_mutations.py exit 1 as recorded",
        "receipt.schema: 5 errors (fingerprints required)",
    ],
    "IMP-0044": [
        "probes 3/5: two recorded test commands exit 0 with EMPTY stdout (NOOP)",
        "receipt.schema: 13 errors (downstream_consumers, retry, timestamps required at root; more)",
        "catalog declares compound schema (+ tools/plugin/schema/probe-control.schema.json) which the estate resolver cannot resolve: no registry entry (program-level gap)",
    ],
    "IMP-0051": [
        "probes 3/8 irreproducible: recorded as 'python -B ...' (no 'python' resolves on the pinned runtime) exit 2",
        "receipt.schema: 3 errors (downstream_consumers + residual_unknowns required at root; secondary schema resolver-unregistered)",
        "NOTE: secondary deliverable taxonomy-document.json validates 0 errors vs error-taxonomy.schema.json (raw instrument) - substance fine, envelope not",
    ],
    "IMP-0068": [
        "probes 3/9 irreproducible: 3x tests[] recorded as 'python3 -B file.py::node' exit 2",
        "receipt.schema: 6 errors (downstream_consumers[0] probe required / note unexpected etc.)",
    ],
    "IMP-0070": [
        "receipt is schema-clean (0 errors on BOTH instruments) and 6/11 probes pass",
        "probes 5/11 irreproducible: 3x tests[] command fields are prose ('recorded by prior builder (named probe re-run is the live check)') exit 2; extensions/prior_evidence commands point at probe1_range_matrix.py and a probe2 file that DO NOT EXIST on disk (probes/IMP-0070/ holds probe1_version_matrix.py + probe2_yank_prerelease.py)",
        "receipt already carries a wave-4 note claiming 'both named probes re-ran exit 0 on this host' - CONTRADICTED by this live re-run (the files it names are absent)",
    ],
    "IMP-0084": [
        "probes 9/10: test_lockfile.py -v exit 1 as recorded (missing PYTHONPATH=tools prefix; WITH it: 7/7 OK - substance fine, record sloppy)",
        "declared secondary schema tools/marketplace/schema/lockfile.schema.json has NO resolver registry entry (program-level gap); the receipt part itself is schema-clean (0 errors on both instruments)",
    ],
}

v["per_unit_failing_grounds"] = grounds
v["continuity"] = (
    "all 12 receipts byte-identical before and after this run (live sha == r2 recorded "
    "live_sha_lf == post-run sha); identical all-FAIL verdicts to r1 and r2 - no builder "
    "repairs landed between rounds"
)
v["receipts_modified"] = False
v["closure"] = "NONE - all 12 verdict FAIL; receipts left byte-identical (verified post-run)"
v["binding_rule_detail"] = (
    "command extraction: every dict anywhere in the receipt JSON with a non-empty string "
    "'command' field (broader than the r2 walker: also catches prose-in-command-field records "
    "and exit-0-empty-stdout NOOPs); PASS iff exit 0 + non-empty stdout, 180s timeout, pinned "
    "Git Bash + /c/Python314/python3 (RT-PROOF captured per command). Schema: instrument1 = "
    "estate platform/lib/schema_resolver.validate_artifact (fail-closed on unknown schemas), "
    "instrument2 = raw draft-2020-12 whole-doc against the shim $ref physical target; BOTH "
    "must be clean."
)
v["program_level_finding"] = (
    "registry gap: the catalog declares compound output_schema ('command-center/schema/"
    "receipt.schema.json + <second>') for IMP-0036/0044/0051/0084 but the platform schema "
    "registry has no entries for the + schemas - the resolver correctly refuses with "
    "UnknownSchemaError. Fix = register the + schemas in the registry (or drop them from the "
    "declarations). Until then no unit with a compound declaration can pass the schema gate."
)

P.write_text(json.dumps(v, indent=1), encoding="utf-8")
print("enriched OK; units:", v["units"])
print("verdicts:", json.dumps(v["verdict"]))
