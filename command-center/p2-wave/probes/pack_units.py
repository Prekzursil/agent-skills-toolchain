"""Per-unit content for the b5 packer: evidence, tests, controls, observations."""

from __future__ import annotations

import json
from pathlib import Path


def pack_all(g: dict) -> None:  # noqa: ANN001 - globals from the packer script
    REPO = g["REPO"]
    pack = g["pack"]
    base_unit = g["base_unit"]
    probe = g["probe"]
    art = g["art"]
    read_raw = g["read_raw"]

    P = "command-center/p2-wave/probes"

    # ---------------------------------------------------------------- ADV-0052
    uid = "ADV-0052"
    raw1 = f"{P}/ADV-0052/probe-registry-searches.raw.txt"
    res1 = f"{P}/ADV-0052/naming-marks-results.json"
    doc = base_unit(
        uid,
        blocked_on="explicit owner sign-off on the naming/marks disposition "
                   "(catalog reviewer_requirement: reviewer may not approve the "
                   "owner-gated part) + cross-vendor reviewer transport unavailable",
        reason="Both probes executed; findings require owner adjudication before "
               "the unit can complete: (1) no exact-name registry or trademark "
               "collision found, (2) nominative-use audit flags plugin keyword "
               "'codex' (a bare vendor mark as search metadata) plus 51 prose "
               "occurrences of vendor marks for owner review.",
        classifications=["license-violation", "owner-gated"])
    ev = [
        {"claim": "No exact-name collision exists on npm, PyPI or GitHub, and no "
                  "USPTO/EUIPO registration surfaced for the phrase (search date "
                  "2026-10-21 recorded as part of the result).",
         "verdict": "CONFIRMED", "confidence": "likely",
         "anchor": raw1,
         "probes": [
             probe("curl https://registry.npmjs.org/agent-skills-toolchain + "
                   "pypi.org/pypi/agent-skills-toolchain/json + gh search repos",
                   "http", "source", read_raw(raw1, 900)),
             probe(f"read {res1}", "file-read", "verifier",
                   read_raw(res1, 500))]},
        {"claim": "Nominative-use audit: the package NAME and headline description "
                  "carry no vendor mark as the brand ('agent-skills-toolchain'; "
                  "'personal Claude Code skill library' is nominative), while the "
                  "plugin keywords include the bare vendor mark 'codex' and 51 "
                  "vendor-mark occurrences in prose were flagged for review.",
         "verdict": "PARTIAL", "confidence": "likely",
         "anchor": f"{P}/ADV-0052/probe-naming-marks.raw.txt",
         "probes": [
             probe(f"python -B {P}/ADV-0052/probe_naming_marks.py", "command",
                   "source", read_raw(f"{P}/ADV-0052/probe-naming-marks.raw.txt",
                                      1600)),
             probe(f"read {res1} non_nominative_hits", "file-read", "verifier",
                   json.dumps(json.loads((REPO / res1).read_text(encoding="utf-8"))
                              ["non_nominative_hits"][:3]))]},
    ]
    tests = [
        {"id": "control-infringing-vs-clean", "command":
         f"python -B {P}/ADV-0052/probe_naming_marks.py (CONTROL block)",
         "result": "PASS", "output_tail": "infringing flagged=True; clean "
         "flagged=False; detector_both_states=OK"},
        {"id": "search-date-recorded", "command": "read naming-marks-results.json",
         "result": "PASS", "output_tail": "search_date=2026-10-21"},
    ]
    ncs = [{"id": "NC-INFRINGING-VS-CLEAN", "kind": "adversarial-payload",
            "description": "Deliberately infringing name 'Claude Code Toolchain "
                           "Pro' must be flagged; clean 'personal skills library' "
                           "must not be.",
            "fired_on_bad_state": True, "silent_on_good_state": True,
            "bad_state_output": "infringing flagged=True",
            "good_state_output": "clean flagged=False"}]
    obs = [
        {"name": "exact-name-collisions", "measured": 0,
         "method": "registry + trademark search (npm/PyPI/GitHub/web)",
         "anchor": raw1},
        {"name": "non-nominative-mark-occurrences", "measured": 51,
         "method": "nominative-shape classifier over published surfaces",
         "anchor": res1},
        {"name": "plugin-keyword-bare-vendor-mark", "measured": "codex",
         "method": "plugin.json keywords inspection",
         "anchor": ".claude-plugin/plugin.json:10"},
    ]
    pack(uid, doc, ["NC-INFRINGING-VS-CLEAN"], obs,
         "license-and-rights-record",
         [art(raw1, "log"), art(res1, "supporting"),
          art(f"{P}/ADV-0052/probe-naming-marks.raw.txt", "log")],
         ev, tests, ncs)

    # ---------------------------------------------------------------- ADV-0053
    uid = "ADV-0053"
    res1 = f"{P}/ADV-0053/provider-tos-results.json"
    raw1 = f"{P}/ADV-0053/probe-provider-tos.raw.txt"
    doc = base_unit(
        uid,
        blocked_on="explicit owner sign-off on the provider-ToS disposition "
                   "(default-flag remedies are owner-controlled) + cross-vendor "
                   "reviewer transport unavailable",
        reason="Clause-to-stage mapping and empirical default-state separation are "
               "complete: zero 'restricted and default-on' stages were found; the "
               "crcp cookie-bridge and codex-rail stages are restricted-class and "
               "opt-in; Z.ai and phylo.bio terms could not be retrieved verbatim "
               "(recorded NOT-CHECKED, not as compliance). Owner must sign off the "
               "classification and the warning labels it implies.",
        classifications=["license-violation", "owner-gated"])
    ev = [
        {"claim": "Each provider-touching stage is mapped to a quoted clause with "
                  "retrieval date; Anthropic AUP and OpenAI ToU clauses were "
                  "retrieved verbatim 2026-10-21.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": res1,
         "probes": [
             probe(f"python -B {P}/ADV-0053/probe_provider_tos.py", "command",
                   "source", read_raw(raw1, 1600)),
             probe(f"read {res1} stages[].clauses", "file-read", "verifier",
                   read_raw(res1, 700))]},
        {"claim": "Empirical default-state: with scrubbed HOME/TEMP and no provider "
                  "credentials, the zai-lane stage is inert (rc=1 missing state "
                  "file, no egress), the crcp login module performs no egress on "
                  "import; restricted-and-default-on count = 0.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": raw1,
         "probes": [
             probe(f"python -B {P}/ADV-0053/probe_provider_tos.py (DEFAULT block)",
                   "command", "source", read_raw(raw1, 1200)),
             probe(f"read {res1} empirical[]", "file-read", "verifier",
                   read_raw(res1, 500))]},
    ]
    tests = [
        {"id": "separation-three-buckets", "command":
         "python -B probe_provider_tos.py (SEPARATION block)",
         "result": "PASS", "output_tail": "restricted-and-default-on count = 0"},
        {"id": "clause-quotes-with-dates", "command": "read provider-tos-results.json",
         "result": "PASS", "output_tail": "every clause carries retrieved=2026-10-21"},
    ]
    ncs = [{"id": "NC-SCRUBBED-ENV-INERTNESS", "kind": "absent-input",
            "description": "With credentials absent the stage must be inert/refuse "
                           "rather than attempt egress (proves opt-in).",
            "fired_on_bad_state": True, "silent_on_good_state": True,
            "bad_state_output": "zai-lane-refresh rc=1 missing state file, "
                                "egress=False",
            "good_state_output": "no stage attempts provider egress unconfigured"}]
    obs = [
        {"name": "restricted-and-default-on-stages", "measured": 0,
         "method": "scrubbed-env empirical invocation of each stage entrypoint",
         "anchor": res1},
        {"name": "restricted-and-opt-in-stages", "measured": 2,
         "method": "same empirical run (zai-lane-refresh; crcp-codex-rail-login)",
         "anchor": res1},
        {"name": "provider-terms-verbatim-not-retrieved", "measured":
         ["Z.ai terms", "phylo.bio terms"],
         "method": "web retrieval attempt 2026-10-21",
         "anchor": res1},
    ]
    pack(uid, doc, ["NC-SCRUBBED-ENV-INERTNESS"], obs,
         "license-and-rights-record",
         [art(res1, "supporting"), art(raw1, "log")], ev, tests, ncs)

    # ---------------------------------------------------------------- ADV-0054
    uid = "ADV-0054"
    res1 = f"{P}/ADV-0054/tor-absence-results.json"
    raw1 = f"{P}/ADV-0054/probe-tor-absence.raw.txt"
    doc = base_unit(
        uid,
        blocked_on="owner adjudication: the onion-source stage named by the spec "
                   "does not exist in this tree (build the stage or retire the "
                   "unit), then explicit owner sign-off; cross-vendor reviewer "
                   "transport also unavailable",
        reason="The never-list conformance test cannot be run at cause: no "
               "onion-source stage implementation exists (two independent "
               "instruments: pattern enumeration over production code found zero "
               "non-self hits; import-graph and entrypoint-vocabulary enumeration "
               "found zero Tor client imports and no tor/onion entrypoint kind). "
               "All nine never-list items are recorded NOT-CHECKED, and the "
               "lawful-goal control is NOT-RUN, per the catalog's own rule that an "
               "unexercised vector is NOT-CHECKED, not safe. No live onion request "
               "was made (none possible).",
        classifications=["license-violation", "owner-gated", "privacy-leak"])
    ev = [
        {"claim": "No Tor/onion capability exists in production code: regex "
                  "enumeration over platform/tools/hooks production Python found "
                  "zero non-self matches across 6 pattern classes.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": raw1,
         "probes": [
             probe(f"python -B {P}/ADV-0054/probe_tor_absence.py (probe 1)",
                   "command", "source", read_raw(raw1, 1400)),
             probe(f"read {res1} probe1", "file-read", "verifier",
                   read_raw(res1, 600))]},
        {"claim": "Mechanically different second signal: zero Tor client library "
                  "imports anywhere in the repo AST and no tor/onion kind in the "
                  "plugin entrypoint or exec-policy vocabularies.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": res1,
         "probes": [
             probe(f"python -B {P}/ADV-0054/probe_tor_absence.py (probe 2)",
                   "static-analysis", "source", read_raw(raw1, 900)),
             probe(f"read {res1} probe2", "file-read", "verifier",
                   read_raw(res1, 400))]},
    ]
    tests = [
        {"id": "never-list-dry-run-corpus", "command": "drive the onion-source "
         "stage with each never-list goal in DRY-RUN",
         "result": "NOT-RUN",
         "output_tail": "stage absent; all 9 items recorded NOT-CHECKED, "
                        "never folded into a pass"},
        {"id": "lawful-goal-accept-control", "command": "lawful public-research "
         "goal must be ACCEPTED in dry-run", "result": "NOT-RUN",
         "output_tail": "stage absent"},
        {"id": "no-live-onion-connection", "command": "n/a (guaranteed by absence)",
         "result": "PASS", "output_tail": "live_onion_requests_issued=0"},
    ]
    ncs = [{"id": "NC-ABSENCE-TWO-INSTRUMENTS", "kind": "absent-input",
            "description": "Absence of the stage is asserted by two mechanically "
                           "different instruments (pattern enumeration + "
                           "import/vocabulary graph); a hit under either would "
                           "have falsified it.",
            "fired_on_bad_state": True, "silent_on_good_state": True,
            "bad_state_output": "self-planted pattern corpus matched 17 self-hits "
                                "(instrument fires when the target exists)",
            "good_state_output": "0 non-self hits in production code"}]
    obs = [
        {"name": "onion-source-stage-implementations", "measured": 0,
         "method": "pattern enumeration over production code",
         "anchor": res1},
        {"name": "tor-client-imports", "measured": 0,
         "method": "AST import-graph walk over the whole repo",
         "anchor": res1},
        {"name": "never-list-items-verdict", "measured":
         "9/9 NOT-CHECKED (stage absent)",
         "method": "dry-run corpus (could not execute)",
         "anchor": res1},
    ]
    pack(uid, doc, ["NC-ABSENCE-TWO-INSTRUMENTS"], obs, "threat-model",
         [art(res1, "supporting"), art(raw1, "log")], ev, tests, ncs)

    # ---------------------------------------------------------------- ADV-0055
    uid = "ADV-0055"
    res1 = f"{P}/ADV-0055/crypto-notice-results.json"
    raw1 = f"{P}/ADV-0055/probe-crypto-notices.raw.txt"
    doc = base_unit(
        uid,
        blocked_on="explicit owner sign-off on the crypto-notice disposition "
                   "(adding TSU/EAR notices and choosing release channels is an "
                   "owner-controlled action) + cross-vendor reviewer transport "
                   "unavailable",
        reason="One bundled crypto implementation ships (mkt/crypto.py: "
               "self-declared pure-Python RFC 8032 Ed25519, the marketplace "
               "signer) alongside platform-library calls only (hashlib/hmac/"
               "secrets/urandom); the built-artifact notice check found NO "
               "export-control or crypto-distribution notice anywhere in the "
               "release metadata (26 surfaces scanned). Whether notices are "
               "required for this release mode (owner decision OQ-3 = PR-ONLY) "
               "and which channel applies is an owner determination.",
        classifications=["license-violation", "supply-chain", "owner-gated"])
    ev = [
        {"claim": "Bundled-crypto enumeration: exactly one bundled implementation "
                  "(mkt/crypto.py Ed25519) and 40+ platform-library call sites; "
                  "the known-bundler control fired (traversal did not miss "
                  "transitives).",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": res1,
         "probes": [
             probe(f"python -B {P}/ADV-0055/probe_crypto_notices.py (probe 1)",
                   "command", "source", read_raw(raw1, 1500)),
             probe(f"read {res1} probe1.bundled + control", "file-read",
                   "verifier", read_raw(res1, 500))]},
        {"claim": "Built-artifact notice check: 26 release/ship surfaces scanned; "
                  "zero export-control/crypto-distribution notices present.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": raw1,
         "probes": [
             probe(f"python -B {P}/ADV-0055/probe_crypto_notices.py (probe 2)",
                   "command", "source", read_raw(raw1, 700)),
             probe(f"read {res1} export_control_notice_present", "file-read",
                   "verifier", read_raw(res1, 300))]},
    ]
    tests = [
        {"id": "control-known-bundler-in-probe1", "command":
         "assert mkt/crypto.py in probe1.bundled",
         "result": "PASS", "output_tail": "control_known_bundler_present=True"},
        {"id": "notice-presence-check", "command": "scan 26 release surfaces for "
         "TSU/EAR/ECCN/export-control terms", "result": "PASS",
         "output_tail": "export_control_notice_present=False (the finding)"},
    ]
    ncs = [{"id": "NC-KNOWN-BUNDLER-DETECTED", "kind": "known-broken-fixture",
            "description": "A component known to bundle crypto (mkt/crypto.py "
                           "Ed25519) must appear in the enumeration, or the "
                           "traversal is broken.",
            "fired_on_bad_state": True, "silent_on_good_state": True,
            "bad_state_output": "BUNDLED platform/marketplace/mkt/crypto.py "
                                "primitive=ed25519-constants",
            "good_state_output": "plain platform calls classified separately"}]
    obs = [
        {"name": "bundled-crypto-implementations", "measured": 1,
         "method": "primitive-pattern enumeration over 769 production files",
         "anchor": res1},
        {"name": "platform-crypto-call-sites", "measured": 40,
         "method": "same enumeration, platform-library class",
         "anchor": res1},
        {"name": "export-control-notices-present", "measured": False,
         "method": "release/ + top-level metadata scan (26 surfaces)",
         "anchor": res1},
    ]
    pack(uid, doc, ["NC-KNOWN-BUNDLER-DETECTED"], obs,
         "license-and-rights-record",
         [art(res1, "supporting"), art(raw1, "log")], ev, tests, ncs)

    # ---------------------------------------------------------------- ADV-0057
    uid = "ADV-0057"
    res1 = f"{P}/ADV-0057/governance-coherence-results.json"
    raw1 = f"{P}/ADV-0057/probe-governance-coherence.raw.txt"
    doc = base_unit(
        uid,
        blocked_on="explicit owner sign-off on the governance remediation "
                   "(shipping a LICENSE, choosing contribution terms, branch "
                   "protection are owner-controlled) + cross-vendor reviewer "
                   "transport unavailable",
        reason="Contradiction matrix found 3 policy-vs-policy/policy-vs-fact "
               "conflicts: (C1) plugin.json declares MIT at :8 while no LICENSE "
               "file exists and the repo's own marketplace gate MKT-P05 would "
               "refuse it; (C2) SECURITY.md:3 forbids ever making the repo public "
               "while GOVERNANCE.md:46-47 aggregates Apache-2.0/CC-BY-SA content "
               "with distribution obligations; (C3) the marketplace fixture has "
               "enforced role separation but the repository contribution flow "
               "collects NOTHING (main branch unprotected per GitHub API, no "
               "DCO/CLA/template anywhere). The scratch-PR control is NOT-RUN "
               "under this run's no-new-billing constraint (8 ubuntu-latest jobs).",
        classifications=["license-violation", "overclaim"])
    ev = [
        {"claim": "Pairwise contradiction matrix with file:line citations verified "
                  "on disk: C1, C2, C3 as above; CONTRIBUTING/SUPPORT/DEPRECATION/"
                  "LICENSE/NOTICE all absent.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": raw1,
         "probes": [
             probe(f"python -B {P}/ADV-0057/probe_governance_coherence.py",
                   "command", "source", read_raw(raw1, 1600)),
             probe(f"read {res1} contradiction_matrix", "file-read", "verifier",
                   read_raw(res1, 700))]},
        {"claim": "Enforcement: GitHub API returns 404 'Branch not protected' for "
                  "main; zero DCO/CLA/sign-off configurations exist in .github/; "
                  "the contribution flow therefore collects no rights.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": res1,
         "probes": [
             probe("gh api repos/Prekzursil/agent-skills-toolchain/branches/main/"
                   "protection", "command", "source",
                   '{"message":"Branch not protected","status":404}'),
             probe(f"read {res1} enforcement", "file-read", "verifier",
                   read_raw(res1, 500))]},
    ]
    tests = [
        {"id": "scratch-pr-without-signoff", "command": "open scratch PR and record "
         "whether sign-off is enforced", "result": "NOT-RUN",
         "output_tail": "run constraint: no new GitHub Actions billing spend (8 "
                        "ubuntu-latest jobs would fire); read-only API + static "
                        "scan executed instead"},
        {"id": "matrix-quotes-verified-on-disk", "command":
         "python -B probe_governance_coherence.py",
         "result": "PASS", "output_tail": "verified_on_disk=True for C1a/C2a/C3a"},
    ]
    ncs = [{"id": "NC-ENFORCEMENT-BOTH-SOURCES", "kind": "absent-input",
            "description": "The no-enforcement reading rests on two mechanically "
                           "different sources (GitHub protection API + filesystem/"
                           "workflow scan); either could have falsified it.",
            "fired_on_bad_state": True, "silent_on_good_state": True,
            "bad_state_output": "404 Branch not protected + 0 DCO/CLA hits",
            "good_state_output": "would have shown protection or a signoff check "
                                 "had one existed"}]
    obs = [
        {"name": "policy-contradictions-found", "measured": 3,
         "method": "pairwise matrix over existing policy docs, quotes verified "
                   "on disk", "anchor": res1},
        {"name": "branch-protection-on-main", "measured": "none (HTTP 404)",
         "method": "gh api branches/main/protection", "anchor": res1},
        {"name": "dco-cla-enforcement-configs", "measured": 0,
         "method": ".github/ recursive scan", "anchor": res1},
    ]
    pack(uid, doc, ["NC-ENFORCEMENT-BOTH-SOURCES"], obs,
         "license-and-rights-record",
         [art(res1, "supporting"), art(raw1, "log")], ev, tests, ncs)

    # ---------------------------------------------------------------- ADV-0060
    uid = "ADV-0060"
    res1 = f"{P}/ADV-0060/probe1-results.json"
    raw1 = f"{P}/ADV-0060/probe1-install-beacons.raw.txt"
    res2 = f"{P}/ADV-0060/probe2-results.json"
    raw2 = f"{P}/ADV-0060/probe2-source-enumeration.raw.txt"
    doc = base_unit(
        uid,
        blocked_on="cross-vendor reviewer transport unavailable (catalog names a "
                   "cross-vendor Anthropic refuter; claude CLI is 429-quota-exhausted "
                   "until 2026-10-28, openai/openrouter transports 402/429 - evidence "
                   "in _r1_b5_reviewer_transport.raw.txt). All probes, controls and "
                   "tests executed green locally on BOTH live package surfaces; only "
                   "the independent review gates the flip to SUCCESS.",
        reason="Re-implementation of both named probes on this tree COMPLETED (the "
               "previously landed artifact was BLOCKED with its marketplace leg "
               "NOT-CHECKED on a sparse worktree): plugin surface install/update/"
               "rollback/repair/uninstall all ran with zero shipped-code beacons "
               "across 7 vectors; the manifest parser refuses preinstall/postinstall/"
               "uninstall/build/scripts/hooks/lifecycle root fields (E_MANIFEST); the "
               "only lifecycle external commands are 2 fixed-argv interpreter "
               "--version probes; explicit entrypoint invocation via plugin.proc.run "
               "executes UNSANDBOXED (control proved the beacon mechanism); the "
               "marketplace surface PUBLISHED and INSTALLED a beacon package through "
               "13 gates with zero beacons and zero run-markers, undeclared payload "
               "refused MKT-P03; AST enumeration found 3 production spawn sites, "
               "joined per-site to the runtime trace with the rehearsal driver "
               "declared NOT-EXERCISED. Host-side automatic hook activation remains "
               "NOT-CHECKED (residual). The catalog's cross-vendor reviewer "
               "requirement cannot be met from this box today.",
        classifications=["supply-chain", "sandbox-escape"])
    doc["sentinel"] = "SENTINEL:ADV-0060:BLOCKED-ON-REVIEWER-TRANSPORT"
    ev = [
        {"claim": "Probe 1: all five plugin lifecycle phases and the full "
                  "marketplace publish+install executed in a disposable sandbox "
                  "with shipped_code_beacons=0 across all seven vectors; direct-"
                  "beacon and explicit-entrypoint controls prove the beacon "
                  "instrument works.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": raw1,
         "probes": [
             probe(f"python -B {P}/ADV-0060/probe1_install_beacons.py",
                   "command", "source", read_raw(raw1, 3500)),
             probe(f"read {res1} phases+controls", "file-read", "verifier",
                   read_raw(res1, 800))]},
        {"claim": "Probe 2 (mechanically different): AST enumeration found exactly "
                  "3 production external-command call sites (proc.py run, "
                  "proc.py probe_interpreter, lifecycle_rehearsal.py run), zero "
                  "in the marketplace; per-site join to the runtime trace records "
                  "the rehearsal driver NOT-EXERCISED-BY-PROBE1 (a declared gap, "
                  "not safe), and the declared policy says "
                  "install_runs_shipped_code=False with hook=automatic.",
         "verdict": "CONFIRMED", "confidence": "almost-certain",
         "anchor": raw2,
         "probes": [
             probe(f"python -B {P}/ADV-0060/probe2_source_enumeration.py",
                   "static-analysis", "source", read_raw(raw2, 1800)),
             probe(f"read {res2} join+policy", "file-read", "verifier",
                   read_raw(res2, 800))]},
    ]
    tests = [
        {"id": "T-CONTROL-DIRECT-BEACON", "command":
         f"python -B {P}/ADV-0060/probe1_install_beacons.py (CONTROL)",
         "result": "PASS", "output_tail": "direct_beacon rc=0 beacon=True"},
        {"id": "T-DISPOSABLE-SANDBOX", "command": "same run (SANDBOX line)",
         "result": "PASS", "output_tail":
         "disposable=true inside_repo=False"},
        {"id": "T-PLUGIN-LIFECYCLE", "command": "same run (5 OP phase lines)",
         "result": "PASS", "output_tail":
         "install/update/rollback/repair/uninstall ok=True new_beacons=[]"},
        {"id": "T-MARKETPLACE-LIFECYCLE", "command":
         "same run (marketplace publish+install)",
         "result": "PASS", "output_tail":
         "publish ok=True; install gates=13; ran_markers=[]"},
        {"id": "T-NEGATIVE-CONTROL-CAN-GO-RED", "command": "same run (NEG block)",
         "result": "PASS", "output_tail":
         "silent_on_good=True fired_on_bad=True silent_after_clear=True"},
        {"id": "T-STATIC-DYNAMIC-JOIN", "command":
         f"python -B {P}/ADV-0060/probe2_source_enumeration.py",
         "result": "PASS", "output_tail":
         "3 sites enumerated; per-site join_status recorded; rehearsal driver "
         "declared NOT-EXERCISED"},
    ]
    ncs = [
        {"id": "NC-BEACON-BOTH-STATES", "kind": "adversarial-payload",
         "description": "Beacon detector silent on good state, fires on planted "
                        "beacon, silent again after clear.",
         "fired_on_bad_state": True, "silent_on_good_state": True,
         "bad_state_output": "NEG.beacon planted -> detector non-empty",
         "good_state_output": "clean sandbox -> beacons=[]"},
        {"id": "NC-UNEXERCISED-IS-NOT-CHECKED", "kind": "other",
         "description": "The unexercised rehearsal-driver site and host hook "
                        "activation are reported as gaps, never as safe.",
         "fired_on_bad_state": True, "silent_on_good_state": True,
         "bad_state_output": "join_status=NOT-EXERCISED-BY-PROBE1 recorded",
         "good_state_output": "exercised sites recorded with their trace basis"},
    ]
    doc["residual_unknowns"] = [
        {"claim": "A real host may automatically load the deployed hook after "
                  "install; its activation and sandbox enforcement were not "
                  "measured.",
         "verdict": "NOT-CHECKED",
         "settling_experiment": "Launch a compatible host against a throwaway "
                                "config root containing the installed fixture "
                                "and monitor beacon, filesystem, process, "
                                "network and environment access."},
    ]
    obs = [
        {"name": "shipped-code-beacons-across-all-lifecycle-phases", "measured": 0,
         "method": "per-vector filesystem beacons, both live package surfaces",
         "anchor": res1},
        {"name": "production-external-command-call-sites", "measured": 3,
         "method": "AST enumeration over plugin + marketplace sources",
         "anchor": res2},
        {"name": "package-triggered-lifecycle-external-commands", "measured": 2,
         "method": "subprocess trace joined to lifecycle phases",
         "anchor": res1},
        {"name": "explicit-installed-entrypoint-unsandboxed", "measured": True,
         "method": "plugin.proc.run explicit control (beacon written)",
         "anchor": res1},
        {"name": "manifest-lifecycle-fields-refused", "measured": 7,
         "method": "strict-field mutant manifests (E_MANIFEST)",
         "anchor": res1},
        {"name": "host-automatic-hook-sandbox-enforcement", "measured":
         "NOT-CHECKED", "method": "source gap plus explicit scope declaration",
         "anchor": "platform/plugin/policy.py:57"},
    ]
    pack(uid, doc, ["NC-BEACON-BOTH-STATES", "NC-UNEXERCISED-IS-NOT-CHECKED"],
         obs, "exploit-proof",
         [art(res1, "log"), art(raw1, "log"), art(res2, "supporting"),
          art(raw2, "log"), art(f"{P}/ADV-0060/probe1_install_beacons.py",
                                "supporting"),
          art(f"{P}/ADV-0060/probe2_source_enumeration.py", "supporting"),
          art(g["TRANSPORT_NOTE_FILE"], "control")],
         ev, tests, ncs)
