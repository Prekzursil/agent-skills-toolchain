"""Build the finished ADV-0021 threat-model receipt from the DEAD AGENT'S surviving
probe outputs plus this round's independent AST/exec verifier.

No measurement is invented here: every raw_output is read verbatim off disk from
command-center/casualty/probe-output/.
"""

from __future__ import annotations

import hashlib
import io
import json
import os

ROOT = r"C:/Users/Prekzursil/source/ast-integrate"
CAS = os.path.join(ROOT, "command-center/casualty")
PO = os.path.join(CAS, "probe-output")
OUT = os.path.join(CAS, "ADV-0021-install-path-stride-threat-model.json")
CANON = "command-center/adversarial/ADV-0021-install-path-stride-threat-model.json"
SELF_REL = "command-center/casualty/ADV-0021-install-path-stride-threat-model.json"


def rd(name: str) -> str:
    return io.open(os.path.join(PO, name), encoding="utf-8").read()


def fp(method: str, command: str) -> str:
    return hashlib.md5(
        f"{method}|{command}".encode("utf-8"), usedforsecurity=False
    ).hexdigest()


P1_RAW = rd("adv0021_probe1_out.ORIGINAL.json")
P2_RAW = rd("adv0021_results_b.ORIGINAL.json")
V_RAW = rd("adv0021_verifier_out.txt")
P1 = json.loads(P1_RAW)
P2 = {r["case"]: r for r in json.loads(P2_RAW)["results"]}
VER = json.loads(V_RAW.split("ADV0021_V_BEGIN")[1].split("ADV0021_V_END")[0])

P1_CMD = (
    "python command-center/casualty/probes/adv0021_probe1.py "
    "command-center/casualty/probe-output/adv0021_probe1_out.json"
)
P2_CMD = (
    "python command-center/casualty/probes/adv0021_probe2b.py "
    "command-center/casualty/probe-output/adv0021_results_b.json"
)
V_CMD = "python command-center/casualty/probes/adv0021_verifier.py"


def probe(role, method, command, raw, exit_code=0):
    return {
        "role": role,
        "method": method,
        "command": command,
        "raw_output": raw[:65000],
        "fingerprint": fp(method, command),
        "exit_code": exit_code,
    }


def p2ex(*cases) -> str:
    """VERBATIM excerpt of the named result rows from the probe-2b capture."""
    rows = [P2[c] for c in cases if c in P2]
    return (
        "VERBATIM EXCERPT of command-center/casualty/probe-output/"
        "adv0021_results_b.ORIGINAL.json (full capture on disk, sha256 "
        + hashlib.sha256(P2_RAW.encode()).hexdigest()
        + "):\n"
        + json.dumps(rows, indent=2)
    )


def p1ex(*keys) -> str:
    sub = {k: P1[k] for k in keys if k in P1}
    return (
        "VERBATIM EXCERPT of command-center/casualty/probe-output/"
        "adv0021_probe1_out.ORIGINAL.json (full capture on disk, sha256 "
        + hashlib.sha256(P1_RAW.encode()).hexdigest()
        + "):\n"
        + json.dumps(sub, indent=2)[:60000]
    )


def vex(*keys) -> str:
    sub = {k: VER["checks"][k] for k in keys if k in VER["checks"]}
    return (
        "VERBATIM EXCERPT of command-center/casualty/probe-output/"
        "adv0021_verifier_out.txt:\n" + json.dumps(sub, indent=2)
    )


# ===================================================================== EVIDENCE
E = []

E.append(
    {
        "claim": "journal.version_dir builds a filesystem path directly from a manifest-supplied "
        "version string with no containment control, so a crafted version escapes the "
        "prefix and its manifest is then parsed as trusted state.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/journal.py:81-82",
        "probes": [
            probe(
                "source", "static-analysis", P1_CMD, p1ex("unguarded_external_joins")
            ),
            probe(
                "verifier",
                "test-run",
                P2_CMD,
                p2ex("D1b.arbitrary-read", "D1b.terminal-state", "D1b.control-good"),
            ),
            probe("verifier", "other", V_CMD, vex("V3_version_dir_containment_ast")),
        ],
    }
)

E.append(
    {
        "claim": "The semver gate at manifest.py:31 accepts a path-traversal payload: its "
        "'(?:[-+].*)?' tail matches ANY characters including '/', '\\\\' and tabs, so "
        "version-string validation is not a containment control.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/manifest.py:31",
        "probes": [
            probe("source", "static-analysis", P1_CMD, p1ex("semver_gate")),
            probe("verifier", "test-run", V_CMD, vex("V1_semver_regex_executed")),
        ],
    }
)

E.append(
    {
        "claim": "No decompression-ratio or uncompressed-size cap exists on the install path; an "
        "archive of 521,945 B expanded to 536,870,912 B (1029x), exceeding the preflight "
        "budget of 33,554,432 B by 503,316,480 B.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/lifecycle.py preflight (budget) vs packager unpack (no cap)",
        "probes": [
            probe("source", "test-run", P2_CMD, p2ex("A2b.archive", "A2b.unpack")),
            probe("verifier", "static-analysis", V_CMD, vex("V4_expansion_bound_ast")),
            probe(
                "verifier",
                "command",
                P2_CMD + "  # token-absence lane with positive control",
                p2ex("A2c.absence", "A2c.detector-control"),
            ),
        ],
    }
)

E.append(
    {
        "claim": "The install path performs NO publisher-signature or trust-anchor verification. "
        "Scoped precisely: an AST walk finds exactly one callsite of a signature-shaped "
        "verb, cli.py:287, and that is Cache.verify (cache.py:98) - a content re-hash that "
        "quarantines corrupted CACHE entries. It authenticates integrity of bytes already "
        "accepted; it authenticates nothing about who produced them.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/cli.py:287 -> platform/plugin/cache.py:98",
        "probes": [
            probe(
                "source", "command", P2_CMD, p2ex("A3c.absence", "A3c.detector-control")
            ),
            probe("verifier", "static-analysis", V_CMD, vex("V2_signature_calls_ast")),
        ],
    }
)

E.append(
    {
        "claim": "No live-target allowlist or denylist policy governs deploy targets: the set of "
        "paths the installer may write into the live tree is manifest-declared and "
        "unconstrained by policy.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/deploy.py, policy.py, manifest.py (token absence, controlled)",
        "probes": [
            probe(
                "source", "command", P2_CMD, p2ex("C1c.absence", "C1c.detector-control")
            ),
            probe("verifier", "static-analysis", P1_CMD, p1ex("control_sites")),
        ],
    }
)

E.append(
    {
        "claim": "No install-time content scan runs over package contents: neither scan_secrets, "
        "classify_forbidden nor validate_package is called from the install path, so a "
        "package carrying a credential or forbidden payload is staged without inspection.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/lifecycle.py, packager.py (token absence, controlled)",
        "probes": [
            probe(
                "source", "command", P2_CMD, p2ex("A4c.absence", "A4c.detector-control")
            ),
            probe("verifier", "static-analysis", P1_CMD, p1ex("verb_call_graph")),
        ],
    }
)

E.append(
    {
        "claim": "safe_join exists and is genuinely applied on the DEPLOY boundary (4 functions) but "
        "is NOT applied on the VERSION-DIRECTORY boundary - the containment control and the "
        "traversal sink are in different modules, which is why the mitigation reads as "
        "present while the boundary is open.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/deploy.py:140,167,336,412 vs platform/plugin/journal.py:81",
        "probes": [
            probe(
                "source", "command", P2_CMD, p2ex("B1c.absence", "B1c.detector-control")
            ),
            probe(
                "verifier",
                "static-analysis",
                V_CMD,
                vex("V3_version_dir_containment_ast"),
            ),
        ],
    }
)

E.append(
    {
        "claim": "The PrefixLock concurrency control is bypassable at the application layer: "
        "--clear-stale-lock removed a FRESH orphaned lock whose mtime was NOW, even though "
        "stale_after=3600 would not classify it as stale.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/lifecycle.py PrefixLock (5 callsites) / CLI --clear-stale-lock",
        "probes": [
            probe("source", "test-run", P2_CMD, p2ex("E1b.orphan-clear")),
            probe(
                "verifier",
                "process-table",
                P2_CMD + "  # live-holder race lane",
                p2ex("E1b.holder", "E1b.steal-live"),
            ),
        ],
    }
)

E.append(
    {
        "claim": "Against a LIVE lock holder the steal was refused - but by the operating system "
        "(WinError 32 mandatory file locking), not by an application check. On a platform "
        "without mandatory locking the same code path has no proven guard.",
        "verdict": "PARTIAL",
        "confidence": "likely",
        "anchor": "PermissionError WinError 32 in E1b.steal-live stderr",
        "unverified": True,
        "settling_experiment": "Re-run adv0021_probe2b.py case E1b on Linux/WSL2, where advisory "
        "flock does not block an unrelated writer, and record whether the "
        "live lock is stolen.",
        "probes": [
            probe("source", "test-run", P2_CMD, p2ex("E1b.steal-live", "E1b.holder")),
        ],
    }
)

E.append(
    {
        "claim": "A crash on the install path is UNCLASSIFIED: cli.main catches only SystemExit, "
        "PluginError and KeyboardInterrupt, so an unexpected exception exits with a raw "
        "traceback and no taxonomy code - measured traceback_in_stderr=True, "
        "taxonomy_code_present=False.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/cli.py:377,390,393",
        "probes": [
            probe("source", "static-analysis", P1_CMD, p1ex("cli_exception_handlers")),
            probe("verifier", "test-run", P2_CMD, p2ex("E1b.classification")),
            probe("verifier", "other", V_CMD, vex("V5_cli_exception_handlers_ast")),
        ],
    }
)

E.append(
    {
        "claim": "Four install-path security behaviours have NO test AT THEIR OWN BOUNDARY across all "
        "161 test functions in the six plugin test modules: version-string traversal, "
        "provenance/live_path escape, zip decompression bomb, and package signature. Scoped "
        "deliberately: traversal IS tested elsewhere in the suite "
        "(test_recovery_never_deletes_outside_the_prefix, "
        "test_unpack_refuses_a_zip_slip_entry), so the correct claim is a BOUNDARY gap, not "
        "an absence of traversal testing in general.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/test_{cli,foundation,health,lifecycle,package,schemas}.py",
        "probes": [
            probe(
                "source",
                "command",
                P2_CMD,
                p2ex(
                    "T1.version-string-traversal",
                    "T1.provenance-live_path-escape",
                    "T1.zip-decompression-bomb",
                    "T1.package-signature",
                    "T1.detector-control",
                ),
            ),
            probe("verifier", "static-analysis", V_CMD, vex("V6_test_gap_ast")),
        ],
    }
)

E.append(
    {
        "claim": "The code-derived surface of the five lifecycle verbs is 100 sink sites against 48 "
        "control sites across 10 modules, with 24 path joins of which 12 are external and "
        "unguarded by safe_join.",
        "verdict": "CONFIRMED",
        "confidence": "almost-certain",
        "anchor": "platform/plugin/{cli,lifecycle,packager,fsops,journal,deploy,manifest,proc,"
        "payload,cache}.py",
        "probes": [
            probe("source", "static-analysis", P1_CMD, P1_RAW),
            probe(
                "verifier",
                "byte-compare",
                "python command-center/casualty/_r1_rerun_diff.py",
                io.open(
                    os.path.join(CAS, "RERUN-EQUIVALENCE.json"), encoding="utf-8"
                ).read()[:20000],
            ),
        ],
    }
)


# ================================================================ STRIDE MATRIX
def cell(b, cat, status, control, bypass, disposition):
    return {
        "boundary": b,
        "stride": cat,
        "status": status,
        "control_anchor": control,
        "bypass_result": bypass,
        "disposition": disposition,
    }


M = []
# TB1 archive -> staging
M += [
    cell(
        "TB1 untrusted archive -> staging tree",
        "Spoofing",
        "unmitigated",
        "none (no publisher signature; cli.py:287 verify is Cache.verify content re-hash)",
        "A3c.absence=ABSENT with A3c.detector-control=PROVEN; V2 AST 0 signature callsites vs 16 hash callsites",
        "AIM: ADV-0028 (signature and provenance verification bypass on install)",
    ),
    cell(
        "TB1 untrusted archive -> staging tree",
        "Tampering",
        "partial",
        "archive_sha256 + _verify_staged (lifecycle.py:314,403,317,406)",
        "integrity of the bytes received is checked; nothing binds those bytes to a trusted publisher, and the hash is self-declared by the same archive",
        "AIM: ADV-0030 (TOCTOU between validation and install)",
    ),
    cell(
        "TB1 untrusted archive -> staging tree",
        "Repudiation",
        "partial",
        "journal/installed.json records the install",
        "no signature means the record attributes the package to nobody",
        "ACCEPTED RESIDUAL: provenance is unattributable until ADV-0028 lands. Owner impact: after a bad install there is no way to prove which publisher supplied the bytes.",
    ),
    cell(
        "TB1 untrusted archive -> staging tree",
        "InformationDisclosure",
        "unmitigated",
        "none (no install-time content scan)",
        "A4c.absence=ABSENT with A4c.detector-control=PROVEN",
        "AIM: ADV-0024 (packager refusal for credential-bearing bundles), ADV-0023 (canary secret sweep)",
    ),
    cell(
        "TB1 untrusted archive -> staging tree",
        "DenialOfService",
        "unmitigated",
        "preflight free-space budget only (lifecycle.py:103,129 'usage.free < required')",
        "A2b.unpack=BYPASSED - 521,945 B archive wrote 536,870,912 B, 1029x, exceeding the 33,554,432 B budget by 503,316,480 B; V4 AST finds 0 uncompressed-size comparisons vs 2 free-space comparisons",
        "AIM: ADV-0034 (resource-exhaustion DoS, decompression bomb), ADV-0027 (archive extraction attacks)",
    ),
    cell(
        "TB1 untrusted archive -> staging tree",
        "ElevationOfPrivilege",
        "unmitigated",
        "check_relpath exists (fsops.py:73, packager.py:108) but no bypass was executed against it",
        "NOT EXECUTED - per the unit's own rule a mitigation with no executable check is downgraded to unmitigated",
        "AIM: ADV-0027 (traversal/absolute/symlink/device-name entries in an archive)",
    ),
]
# TB2 version string -> path
M += [
    cell(
        "TB2 manifest version string -> filesystem path",
        "Tampering",
        "unmitigated",
        "parse_semver (8 callsites) is the only gate; manifest.py:31 regex tail accepts any characters",
        "V1 executed: traversal_dash/traversal_plus/backslash/nul_adjacent all ACCEPTED; control garbage REJECTED",
        "AIM: ADV-0027 (path traversal on install)",
    ),
    cell(
        "TB2 manifest version string -> filesystem path",
        "InformationDisclosure",
        "unmitigated",
        "none - version_dir (journal.py:81) has zero callees, so no containment runs",
        "D1b.arbitrary-read=BYPASSED - version_dir('../../OUTSIDE_TREE2') resolved outside the prefix and its manifest parsed as name='attacker-controlled-name' version='9.9.9'",
        "AIM: ADV-0027; corroborates ADV-0041 (local path disclosure)",
    ),
    cell(
        "TB2 manifest version string -> filesystem path",
        "ElevationOfPrivilege",
        "unmitigated",
        "none",
        "same bypass as above: state read from outside the prefix is then trusted as installed state",
        "AIM: ADV-0027",
    ),
    cell(
        "TB2 manifest version string -> filesystem path",
        "Spoofing",
        "unmitigated",
        "none",
        "the escaped manifest supplied an attacker-chosen package identity that the CLI accepted",
        "AIM: ADV-0029 (dependency confusion / index poisoning)",
    ),
    cell(
        "TB2 manifest version string -> filesystem path",
        "Repudiation",
        "partial",
        "installed.json journal",
        "the journal records the tampered identity as if genuine",
        "ACCEPTED RESIDUAL: the audit record inherits the spoofed identity. Owner impact: post-incident forensics on installed.json cannot be trusted for package identity until TB2 is closed.",
    ),
    cell(
        "TB2 manifest version string -> filesystem path",
        "DenialOfService",
        "not-applicable",
        "n/a",
        "no DoS vector distinct from TB1 was measured at this boundary",
        "NONE - no unmitigated exposure asserted",
    ),
]
# TB3 staged -> live
M += [
    cell(
        "TB3 staged tree -> live deploy targets",
        "Tampering",
        "mitigated",
        "safe_join at deploy.py:140,167,336,412 (V3 control confirms 4 functions call it)",
        "B1c probed the adjacent version-dir boundary and found safe_join ABSENT there; the deploy boundary itself was NOT bypassed in this unit",
        "ACCEPTED RESIDUAL (scope): the deploy-side safe_join is confirmed PRESENT by two mechanisms but its bypass was not executed here. Owner impact: this cell is 'mitigated-by-inspection', not 'mitigated-by-bypass-attempt'. Settling experiment named in residual_unknowns.",
    ),
    cell(
        "TB3 staged tree -> live deploy targets",
        "ElevationOfPrivilege",
        "unmitigated",
        "none - no allowlist/denylist of live targets",
        "C1c.absence=ABSENT with C1c.detector-control=PROVEN (deploy_targets and safe_join found by the same matcher)",
        "AIM: ADV-0025 (package that writes outside its own root), ADV-0036 (Windows ACLs on deployed files that influence execution)",
    ),
    cell(
        "TB3 staged tree -> live deploy targets",
        "Spoofing",
        "partial",
        "content_hash (9 callsites)",
        "detects drift of a deployed file; does not authenticate the source of a replacement",
        "AIM: ADV-0036",
    ),
    cell(
        "TB3 staged tree -> live deploy targets",
        "InformationDisclosure",
        "unmitigated",
        "none",
        "projection_map joins version_root / ep.path (deploy.py:484) unguarded per Probe-1 unguarded_external_joins",
        "AIM: ADV-0025",
    ),
    cell(
        "TB3 staged tree -> live deploy targets",
        "Repudiation",
        "mitigated",
        "divergence_decisions + drift_document emit an operator-visible decision record",
        "D1b.terminal-state=CLASSIFIED - projection on a tampered installed.json exited 0 with no traceback, i.e. the outcome was classified rather than crashing",
        "NONE - no unmitigated exposure asserted",
    ),
    cell(
        "TB3 staged tree -> live deploy targets",
        "DenialOfService",
        "not-applicable",
        "n/a",
        "no distinct DoS vector measured at this boundary",
        "NONE",
    ),
]
# TB4 cache
M += [
    cell(
        "TB4 shared content cache",
        "Tampering",
        "partial",
        "Cache.verify (cache.py:98) re-hashes and quarantines",
        "not bypass-tested in this unit; cache._path and _quarantine join on a key (cache.py:59,83) and appear in Probe-1 unguarded_external_joins",
        "AIM: ADV-0038 (revocation propagation to already-cached packages)",
    ),
    cell(
        "TB4 shared content cache",
        "Spoofing",
        "unmitigated",
        "none - cache keys are content-derived, not publisher-bound",
        "inherits TB1 Spoofing: an unsigned artifact cached once is served thereafter",
        "AIM: ADV-0029, ADV-0038",
    ),
    cell(
        "TB4 shared content cache",
        "DenialOfService",
        "unmitigated",
        "none - no cache size or entry-count bound was found among the 48 control sites",
        "NOT EXECUTED against the cache specifically; the 1029x expansion in A2b lands in the same filesystem",
        "AIM: ADV-0034",
    ),
    cell(
        "TB4 shared content cache",
        "InformationDisclosure",
        "partial",
        "quarantine directory isolates bad entries",
        "not bypass-tested",
        "AIM: ADV-0038",
    ),
    cell(
        "TB4 shared content cache",
        "Repudiation",
        "not-applicable",
        "n/a",
        "no separate audit obligation at this boundary",
        "NONE",
    ),
    cell(
        "TB4 shared content cache",
        "ElevationOfPrivilege",
        "not-applicable",
        "n/a",
        "cache writes stay under the prefix cache root in all 24 measured joins",
        "NONE",
    ),
]
# TB5 concurrency
M += [
    cell(
        "TB5 concurrent operators -> prefix lock",
        "DenialOfService",
        "unmitigated",
        "PrefixLock (lifecycle.py:315,404,448,495,602) + stale_after=3600",
        "E1b.orphan-clear=BYPASSED - --clear-stale-lock removed a lock whose mtime was NOW",
        "AIM: ADV-0030 (TOCTOU). ACCEPTED RESIDUAL if ADV-0030 does not cover the CLI flag: owner impact is that one operator can clear another's fresh lock and both then mutate the prefix.",
    ),
    cell(
        "TB5 concurrent operators -> prefix lock",
        "Tampering",
        "partial",
        "OS mandatory file lock (Windows)",
        "E1b.steal-live=BLOCKED-BY-OS (WinError 32) - refused by the OS, not by the application",
        "ACCEPTED RESIDUAL, platform-scoped: the guard that actually held is the Windows filesystem, not this code. Owner impact: on a platform with advisory-only locking the same path is unproven. Settling experiment in residual_unknowns.",
    ),
    cell(
        "TB5 concurrent operators -> prefix lock",
        "Repudiation",
        "unmitigated",
        "none",
        "E1b.classification=UNCLASSIFIED-CRASH - exit=1 with a raw traceback and no taxonomy code",
        "ACCEPTED RESIDUAL: a lock-contention failure is indistinguishable from a crash in logs. Owner impact: operators cannot tell 'someone else is installing' from 'the installer is broken'.",
    ),
    cell(
        "TB5 concurrent operators -> prefix lock",
        "Spoofing",
        "not-applicable",
        "n/a",
        "the lock carries no identity claim to spoof",
        "NONE",
    ),
    cell(
        "TB5 concurrent operators -> prefix lock",
        "InformationDisclosure",
        "not-applicable",
        "n/a",
        "no data crosses this boundary",
        "NONE",
    ),
    cell(
        "TB5 concurrent operators -> prefix lock",
        "ElevationOfPrivilege",
        "not-applicable",
        "n/a",
        "no privilege change at this boundary",
        "NONE",
    ),
]
# TB6 subprocess
M += [
    cell(
        "TB6 install path -> subprocess / interpreter",
        "ElevationOfPrivilege",
        "unmitigated",
        "negotiate / check_interpreters (4 callsites) constrain WHICH interpreter, not what it runs",
        "NOT EXECUTED - downgraded to unmitigated per the unit's own rule; 7 proc-exec sinks measured (proc.py:146,179; lifecycle.py:165,319,408; deploy.py:483)",
        "AIM: ADV-0031 (command injection through parameters into shell and process adapters)",
    ),
    cell(
        "TB6 install path -> subprocess / interpreter",
        "Tampering",
        "unmitigated",
        "none proven",
        "NOT EXECUTED",
        "AIM: ADV-0031",
    ),
    cell(
        "TB6 install path -> subprocess / interpreter",
        "Spoofing",
        "partial",
        "check_interpreters resolves an expected interpreter",
        "NOT EXECUTED",
        "AIM: ADV-0031",
    ),
    cell(
        "TB6 install path -> subprocess / interpreter",
        "InformationDisclosure",
        "unmitigated",
        "none proven",
        "NOT EXECUTED - a spawned process inherits the parent environment",
        "AIM: ADV-0037 (credential-diagnosis path), ADV-0039 (telemetry egress)",
    ),
    cell(
        "TB6 install path -> subprocess / interpreter",
        "DenialOfService",
        "unmitigated",
        "none proven",
        "NOT EXECUTED",
        "AIM: ADV-0034",
    ),
    cell(
        "TB6 install path -> subprocess / interpreter",
        "Repudiation",
        "unmitigated",
        "none proven",
        "NOT EXECUTED - inherits the unclassified-crash finding of TB7",
        "ACCEPTED RESIDUAL: subprocess failures are not separately classified. Owner impact: a failed interpreter negotiation is logged the same as any crash.",
    ),
]
# TB7 operator CLI
M += [
    cell(
        "TB7 operator -> CLI process boundary",
        "Repudiation",
        "unmitigated",
        "cli.py:377 SystemExit, :390 PluginError, :393 KeyboardInterrupt - three handlers, none broad",
        "E1b.classification=UNCLASSIFIED-CRASH executed; V5 AST confirms catches_broad_exception=false",
        "ACCEPTED RESIDUAL: any exception outside PluginError exits with a raw traceback and no taxonomy code. Owner impact: the fan-in barrier cannot classify an install failure, so a crash may be read as an ordinary non-zero exit.",
    ),
    cell(
        "TB7 operator -> CLI process boundary",
        "InformationDisclosure",
        "partial",
        "none specific",
        "the raw traceback printed on an unclassified crash carries absolute local paths (observed in E1b.steal-live stderr: C:\\\\Users\\\\Prekzursil\\\\...)",
        "AIM: ADV-0041 (local path and identity disclosure in user-facing errors)",
    ),
    cell(
        "TB7 operator -> CLI process boundary",
        "Tampering",
        "not-applicable",
        "n/a",
        "no attacker-controlled data crosses at this boundary beyond TB1/TB2",
        "NONE",
    ),
    cell(
        "TB7 operator -> CLI process boundary",
        "Spoofing",
        "not-applicable",
        "n/a",
        "the CLI performs no authentication to spoof",
        "NONE",
    ),
    cell(
        "TB7 operator -> CLI process boundary",
        "DenialOfService",
        "not-applicable",
        "n/a",
        "covered by TB5",
        "NONE",
    ),
    cell(
        "TB7 operator -> CLI process boundary",
        "ElevationOfPrivilege",
        "not-applicable",
        "n/a",
        "the CLI runs at operator privilege; no elevation path measured",
        "NONE",
    ),
]

status_counts: dict[str, int] = {}
for c in M:
    status_counts[c["status"]] = status_counts.get(c["status"], 0) + 1
undisposed = [
    c
    for c in M
    if c["status"] in ("unmitigated", "partial")
    and c["disposition"] in ("NONE", "", None)
]

# ======================================================================= TESTS
TESTS = [
    {
        "id": "T-0021-1",
        "name": "Probe 1 re-executes and reproduces the code-derived surface",
        "command": P1_CMD,
        "result": "PASS",
        "assertions": 4,
        "output_tail": "sink_site_count=100 control_site_count=48 path_join_count=24 "
        "unguarded_external_joins=12; sha256 of rerun == sha256 of the dead agent's "
        "capture (b99e0b726c4c3786bb2c79f8bfd90e1339c6b4c6e71494bbbdf19601585e001a)",
    },
    {
        "id": "T-0021-2",
        "name": "Probe 2b re-executes and every outcome is unchanged",
        "command": P2_CMD,
        "result": "PASS",
        "assertions": 24,
        "output_tail": "24/24 case outcomes identical between the dead agent's capture and the "
        "re-run; the only 3 leaf diffs are a subprocess pid and two %TEMP% "
        "directory names (see RERUN-EQUIVALENCE.json)",
    },
    {
        "id": "T-0021-3",
        "name": "Independent AST/exec verifier agrees with every absence claim",
        "command": V_CMD,
        "result": "PASS",
        "assertions": 5,
        "output_tail": "V1 regex accepts 4/4 traversal payloads and rejects the control; "
        "V2 0 signature callsites vs 16 hash-verb control; V3 safe_join absent in "
        "version_dir vs 4 control functions; V4 0 size comparisons vs 2 free-space "
        "control; V5 3 handlers, no broad except",
    },
    {
        "id": "T-0021-4",
        "name": "tests_required: every unmitigated/partial cell carries a follow-up unit or an "
        "accepted residual with an owner-visible impact statement",
        "command": "python command-center/casualty/_build_adv0021.py  # assertion is executed at build time",
        "result": "PASS" if not undisposed else "FAIL",
        "assertions": len(M),
        "output_tail": f"{len(M)} STRIDE cells; status counts {json.dumps(status_counts)}; "
        f"cells needing a disposition and lacking one: {len(undisposed)}",
    },
]

# =========================================================== NEGATIVE CONTROLS
NC = [
    {
        "id": "NC-ABSENCE-POSITIVE-CONTROL",
        "kind": "known-broken-fixture",
        "description": "Every token-absence claim re-runs the SAME matcher over the SAME files with "
        "a token known to be present. If the matcher were broken it would return "
        "nothing for the known-present token too.",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "A2c/A3c/C1c/A4c/B1c detector-control = PROVEN, e.g. "
        "['lifecycle.py:archive_sha256','lifecycle.py:sha256',"
        "'packager.py:archive_sha256','packager.py:sha256']",
        "good_state_output": "the absence queries themselves returned NO HITS",
    },
    {
        "id": "NC-AST-WALKER-NOT-INERT",
        "kind": "absent-input",
        "description": "The verifier's AST walkers are proven live by a positive control on the same "
        "walker: 16 hash-verb callsites (V2), 4 safe_join functions (V3), 2 "
        "free-space Compare nodes (V4).",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "V2 control=16, V3 control=4, V4 control=2 - all non-zero",
        "good_state_output": "signature callsites=0 (after excluding Cache.verify), "
        "safe_join in version_dir=false, size comparisons=0",
    },
    {
        "id": "NC-SEMVER-REJECTS-GARBAGE",
        "kind": "malformed-input",
        "description": "The executed semver regex must still REJECT a non-version string, otherwise "
        "'it accepts traversal' would be meaningless.",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "accepts['traversal_dash']=true, ['traversal_plus']=true, "
        "['backslash']=true, ['nul_adjacent']=true",
        "good_state_output": "accepts['control_must_reject']='not-a-version' -> false; "
        "accepts['benign']='1.2.3' -> true",
    },
    {
        "id": "NC-TEST-GAP-MATCHER-LIVE",
        "kind": "absent-input",
        "description": "The 'no test exists' claim is controlled by searching the same six test "
        "files for a token known to be present ('diverged').",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "T1.detector-control = PROVEN, 'diverged' found in test_cli.py, "
        "test_lifecycle.py, test_schemas.py",
        "good_state_output": "all four security tokens -> NO HITS across the same six files",
    },
    {
        "id": "NC-GOOD-STATE-PROJECTION-SILENT",
        "kind": "known-broken-fixture",
        "description": "The traversal exploit is paired with an untampered run, so the bypass is not "
        "an artefact of a broken CLI.",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "D1b.arbitrary-read=BYPASSED - manifest outside the prefix parsed",
        "good_state_output": "D1b.control-good=SILENT-AND-CORRECT - untampered projection exit=0 "
        "stdout='SUCCESS:projection'",
    },
    {
        "id": "NC-SUBSTRING-FALSE-POSITIVE",
        "kind": "other",
        "description": "A detector defect found and FIXED inside this build, recorded rather than "
        "deleted. The first AST test-gap pass matched bare substrings and reported "
        "three spurious zip-decompression-bomb tests because the token 'ratio' is a "
        "substring of 'migration'. Word-boundary plus conjunctive matching removed "
        "all three. This control is the before/after of that same instrument.",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "substring pass -> zip_decompression_bomb: "
        "['test_health.py:test_dry_run_migration_moves_nothing:277', "
        "'test_health.py:test_a_failing_step_rolls_the_migration_back:285', "
        "'test_health.py:test_migration_ledger_serialises:383'] (all FALSE)",
        "good_state_output": "word-boundary + conjunctive pass -> zip_decompression_bomb: [] ; "
        "positive control 'diverged' still returns 4 test functions, so the "
        "tightened matcher is not merely inert",
    },
    {
        "id": "NC-BOUNDARY-VS-ANYWHERE",
        "kind": "other",
        "description": "The test-gap claim is checked at two widths so it cannot be overstated: at "
        "the specific boundary (the unit's actual question) and anywhere in the suite "
        "(the weaker reading). A claim that held only at the narrow width and was "
        "reported at the wide width would be an overclaim.",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "narrow reading: 4 of 4 behaviours have ZERO tests at their boundary",
        "good_state_output": "wide reading: traversal IS covered by 2 adjacent tests "
        "(test_recovery_never_deletes_outside_the_prefix, "
        "test_unpack_refuses_a_zip_slip_entry) - reported inline, not suppressed",
    },
    {
        "id": "NC-RERUN-EQUIVALENCE",
        "kind": "other",
        "description": "Both dead-agent captures were re-executed by an independent later process; "
        "the detector here is the byte/semantic differ, which must show a real diff "
        "when one exists and none when it does not.",
        "fired_on_bad_state": True,
        "silent_on_good_state": True,
        "bad_state_output": "adv0021_results_b: 3 differing leaves surfaced (pid 31240 vs 12812, two "
        "%TEMP% dir names) - the differ is live",
        "good_state_output": "adv0021_probe1_out: 0 differing leaves of 1,299; sha256 identical",
    },
]

OBS = [
    {
        "name": "sink sites on the five lifecycle verbs",
        "measured": 100,
        "method": "static-analysis",
        "anchor": "adv0021_probe1_out.json:sink_site_count",
    },
    {
        "name": "control sites",
        "measured": 48,
        "method": "static-analysis",
        "anchor": "adv0021_probe1_out.json:control_site_count",
    },
    {
        "name": "path joins",
        "measured": 24,
        "method": "static-analysis",
        "anchor": "adv0021_probe1_out.json:path_join_count",
    },
    {
        "name": "external path joins unguarded by safe_join",
        "measured": 12,
        "method": "static-analysis",
        "anchor": "adv0021_probe1_out.json:unguarded_external_joins",
    },
    {
        "name": "archive expansion ratio achieved against the install path",
        "measured": "1029x (521,945 B -> 536,870,912 B)",
        "method": "test-run",
        "anchor": "adv0021_results_b.json:A2b.unpack",
    },
    {
        "name": "preflight budget exceeded by",
        "measured": "503,316,480 B",
        "method": "test-run",
        "anchor": "adv0021_results_b.json:A2b.archive",
    },
    {
        "name": "publisher-signature callsites on the install path",
        "measured": 0,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V2 (Cache.verify excluded)",
    },
    {
        "name": "hash-verb callsites (positive control for V2)",
        "measured": 16,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V2",
    },
    {
        "name": "semver traversal payloads accepted",
        "measured": "4 of 4",
        "method": "test-run",
        "anchor": "adv0021_verifier_out.txt:V1",
    },
    {
        "name": "safe_join present in journal.version_dir",
        "measured": False,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V3",
    },
    {
        "name": "deploy functions that DO call safe_join (positive control for V3)",
        "measured": 4,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V3",
    },
    {
        "name": "uncompressed-size comparisons anywhere on the install path",
        "measured": 0,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V4",
    },
    {
        "name": "CLI exception handlers",
        "measured": 3,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V5",
    },
    {
        "name": "security behaviours with zero test coverage AT THEIR OWN BOUNDARY",
        "measured": 4,
        "method": "command",
        "anchor": "adv0021_results_b.json:T1.*",
    },
    {
        "name": "test functions parsed by the independent AST test-gap verifier",
        "measured": 161,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V6",
    },
    {
        "name": "adjacent traversal tests that DO exist (scope-limiter on the test-gap claim)",
        "measured": 2,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V6.adjacent_coverage_weaker_reading",
    },
    {
        "name": "false positives produced by the first substring test-gap matcher, before fixing",
        "measured": 3,
        "method": "static-analysis",
        "anchor": "adv0021_verifier_out.txt:V6.detector_defect_found_and_fixed",
    },
    {
        "name": "STRIDE cells enumerated",
        "measured": len(M),
        "method": "manual-inspection",
        "anchor": "report.stride_matrix",
    },
    {
        "name": "STRIDE cells unmitigated",
        "measured": status_counts.get("unmitigated", 0),
        "method": "manual-inspection",
        "anchor": "report.stride_matrix",
    },
    {
        "name": "unmitigated/partial cells left without a follow-up unit or accepted residual",
        "measured": len(undisposed),
        "method": "manual-inspection",
        "anchor": "report.tests_required_closure",
    },
    {
        "name": "probe-1 re-run byte equivalence with the dead agent's capture",
        "measured": True,
        "method": "byte-compare",
        "anchor": "command-center/casualty/RERUN-EQUIVALENCE.json",
    },
]

RECEIPT = {
    "schema_version": 1,
    "unit_id": "ADV-0021",
    "state": "BLOCKED",
    "sentinel": (
        "FAILED:ADV-0021 measurement is COMPLETE and no verdict below is downgraded; the terminal "
        "state is BLOCKED rather than SUCCESS because three schema-mandated SUCCESS conditions "
        "cannot be satisfied honestly by this agent - condition 9 (the unit requires a CROSS-VENDOR "
        "openai refuter who re-derives the counterexample from the raw artifact; none has run, and "
        "this artifact was produced by anthropic/opus so an Anthropic reviewer would be "
        "same-vendor), condition 11 (registering in the shared artifact manifest is an orchestrator "
        "action), and the artifact currently sits at command-center/casualty/ because this lane is "
        "forbidden from writing into command-center/adversarial/ while a sibling wave may be "
        "writing there. Every probe, control and verdict below may be cited."
    ),
    "spec_anchor": "_USER-PROMPTS.md:11049, 10824-10842",
    "min_bytes_threshold": 8192,
    "artifacts": [
        {
            "path": SELF_REL,
            "bytes": 0,
            "sha256": "0" * 64,
            "exists": True,
            "eol": "LF",
            "role": "primary",
        },
        {
            "path": "command-center/casualty/probe-output/adv0021_probe1_out.ORIGINAL.json",
            "bytes": len(P1_RAW.encode("utf-8")),
            "sha256": hashlib.sha256(P1_RAW.encode("utf-8")).hexdigest(),
            "exists": True,
            "eol": "LF",
            "role": "supporting",
        },
        {
            "path": "command-center/casualty/probe-output/adv0021_results_b.ORIGINAL.json",
            "bytes": len(P2_RAW.encode("utf-8")),
            "sha256": hashlib.sha256(P2_RAW.encode("utf-8")).hexdigest(),
            "exists": True,
            "eol": "LF",
            "role": "supporting",
        },
        {
            "path": "command-center/casualty/probe-output/adv0021_verifier_out.txt",
            "bytes": len(V_RAW.encode("utf-8")),
            "sha256": hashlib.sha256(V_RAW.encode("utf-8")).hexdigest(),
            "exists": True,
            "eol": "LF",
            "role": "control",
        },
    ],
    "evidence": E,
    "tests": TESTS,
    "negative_controls": NC,
    "reviewer": {
        "reviewer_id": "NOT-ASSIGNED",
        "verdict": "NOT-REVIEWED",
        "independent": False,
        "fresh_context": False,
        "notes": "reviewer_requirement: one cross-vendor Codex (openai) refuter who re-derives the "
        "counterexample from the RAW ARTIFACT and not from this report. None has run. "
        "NOTE THE INVERSION: the catalog assigns this unit to anthropic/opus and therefore "
        "names an openai refuter; this artifact was in fact assembled by anthropic/opus "
        "(a recovery lane), so the inversion does not apply and an openai refuter is still "
        "the correct one. The two highest-value counterexamples to re-derive independently "
        "are (a) version_dir('../../X') escaping the prefix with its manifest parsed, and "
        "(b) the 1029x archive expansion clearing the preflight budget.",
    },
    "defects": [
        {
            "id": "ADV-0021-D1",
            "severity": "P1",
            "status": "open",
            "summary": "journal.version_dir (journal.py:81) applies no containment to a "
            "manifest-supplied version string; a crafted version reads and trusts state "
            "outside the prefix. Executed: D1b.arbitrary-read=BYPASSED.",
        },
        {
            "id": "ADV-0021-D2",
            "severity": "P1",
            "status": "open",
            "summary": "No uncompressed-size or ratio cap on install: a 521,945 B archive wrote "
            "536,870,912 B, exceeding the preflight budget by 503,316,480 B.",
        },
        {
            "id": "ADV-0021-D3",
            "severity": "P1",
            "status": "open",
            "summary": "No publisher-signature or trust-anchor verification anywhere on the install "
            "path; the one signature-shaped callsite is Cache.verify, a content re-hash.",
        },
        {
            "id": "ADV-0021-D4",
            "severity": "P2",
            "status": "open",
            "summary": "SEMVER_RE (manifest.py:31) accepts path separators and control characters in "
            "its prerelease/build tail, so semver validation is not containment.",
        },
        {
            "id": "ADV-0021-D5",
            "severity": "P2",
            "status": "open",
            "summary": "--clear-stale-lock removes a lock whose mtime is NOW, defeating stale_after.",
        },
        {
            "id": "ADV-0021-D6",
            "severity": "P2",
            "status": "open",
            "summary": "cli.main classifies only PluginError/KeyboardInterrupt/SystemExit; any other "
            "exception exits with a raw traceback, no taxonomy code, and absolute local "
            "paths in stderr.",
        },
        {
            "id": "ADV-0021-D7",
            "severity": "P2",
            "status": "open",
            "summary": "Four install-path security behaviours have no test in any of the six plugin "
            "test modules (traversal, provenance escape, zip bomb, signature).",
        },
        {
            "id": "ADV-0021-D8",
            "severity": "INFO",
            "status": "resolved",
            "summary": "Run A of Probe 2 self-diagnosed three broken detectors (a non-compressing "
            "'bomb', a harness-held lock handle, absence greps with no positive control). "
            "Run B replaced all three and is the run cited here; run A is retained at "
            "probe-output/adv0021_results.ORIGINAL.json and is NOT cited.",
        },
    ],
    "manifest_registration": {
        "registered": False,
        "manifest_path": "command-center/ARTIFACT-MANIFEST.json",
        "entry_id": "ADV-0021",
    },
    "downstream_consumers": [
        {
            "consumer": "platform/lib/receipt_schema_gate.py -- the independent reducer that validates "
            "a receipt and evaluates the 12-condition completion predicate",
            "artifact_path": SELF_REL,
            "executed": True,
            "read_ok": True,
            "exit_code": 1,
            "probe": probe(
                "verifier",
                "schema-validate",
                f"python platform/lib/receipt_schema_gate.py {SELF_REL} --repo-root .",
                "__GATE_CAPTURE__",
            ),
        }
    ],
    "timestamps": {
        "started_at": "2026-08-12T08:34:26+03:00",
        "ended_at": "2026-08-12T09:05:00+03:00",
    },
    "retry": {
        "count": 0,
        "policy": "two strikes then pivot (AGENTS.md 4b). Not triggered in this recovery "
        "lane: no hypothesis failed twice. One PIVOT is inherited and recorded as "
        "ADV-0021-D8 - the original agent replaced three of its own broken "
        "detectors after run A self-diagnosed them.",
        "attempts": [
            {
                "attempt": 1,
                "outcome": "BLOCKED",
                "error_fingerprint": "reviewer-and-manifest-unsatisfiable-by-builder",
            }
        ],
    },
    "failure": {
        "classification": ["dependency-blocked", "overclaim-guard"],
        "reason": "Measurement is COMPLETE. The original ADV-0021 agent finished both probes and "
        "died at the artifact-assembly step ('All claims now have controls. Writing the "
        "artifact.' -> 'API Error: Connection closed mid-response.'). This receipt is "
        "assembled from that agent's surviving verbatim probe captures, both of which "
        "were independently RE-EXECUTED (probe 1 byte-identical, probe 2b identical on "
        "all 24 outcomes), plus a new mechanically-different AST/exec verifier. BLOCKED "
        "rather than SUCCESS only because condition 9 (cross-vendor refuter) and "
        "condition 11 (manifest registration) are not this agent's to satisfy, and "
        "because the artifact is parked outside its canonical output_path by lane scope.",
        "blocked_on": "a cross-vendor openai refuter (condition 9); orchestrator registration in "
        "command-center/ARTIFACT-MANIFEST.json (condition 11); orchestrator "
        "promotion of this file to command-center/adversarial/ (canonical path)",
    },
    "residual_unknowns": [
        {
            "claim": "The deploy-side safe_join mitigation (deploy.py:140,167,336,412) is confirmed "
            "PRESENT by two independent mechanisms but its BYPASS was never executed, so "
            "TB3/Tampering is mitigated-by-inspection rather than mitigated-by-attempt.",
            "verdict": "NOT-CHECKED",
            "settling_experiment": "Extend adv0021_probe2b.py with a case that drives deploy.sync "
            "with an entry path containing '../' and a Windows device name, "
            "and record whether safe_join raises.",
        },
        {
            "claim": "TB5/Tampering held only because Windows applies mandatory file locking "
            "(WinError 32). On a platform with advisory-only locking the live-lock steal is "
            "unproven.",
            "verdict": "NOT-CHECKED",
            "settling_experiment": "Re-run adv0021_probe2b.py case E1b under WSL2/Linux and record "
            "whether the live lock is stolen.",
        },
        {
            "claim": "The entire TB6 subprocess/interpreter boundary (6 cells) is enumerated from the "
            "AST only; no bypass was executed against any of its 7 proc-exec sinks, so all "
            "six cells are downgraded to unmitigated by rule rather than by measurement.",
            "verdict": "NOT-CHECKED",
            "settling_experiment": "This is precisely ADV-0031's scope (command injection through "
            "workflow parameters into shell and process adapters); run it and "
            "fold its result back into TB6.",
        },
        {
            "claim": "The unit's reviewer_requirement (one cross-vendor openai refuter) is unmet.",
            "verdict": "NOT-CHECKED",
            "settling_experiment": "Dispatch an openai/gpt-5-codex refuter with ONLY the raw probe "
            "captures in probe-output/ and this artifact, and require it to "
            "re-derive D1 and D2 without reading report.stride_matrix.",
        },
        {
            "claim": "spec_anchor cites _USER-PROMPTS.md:11049 and 10824-10842, but the original "
            "agent could not locate _USER-PROMPTS.md in the worktree (its rec 46/49 searches "
            "found no tracked file of that name), so the STRIDE matrix is derived from CODE "
            "only - which is what evidence_requirement demanded anyway.",
            "verdict": "PARTIAL",
            "settling_experiment": "Locate _USER-PROMPTS.md (it may live only in the originating "
            "session) and confirm the plugin requirements at 10824-10842 "
            "introduce no boundary absent from this matrix.",
        },
    ],
    "produced_by": {
        "vendor": "anthropic",
        "model": "claude-opus-4",
        "role": "casualty-recovery-assembler",
        "execution_substrate": "local-serialized",
    },
    "report": {
        "kind": "threat-model",
        "observations": OBS,
        "control_ids": [c["id"] for c in NC],
        "verdicts": {
            "question": "What are the trust boundaries crossed during install, update, repair, "
            "rollback and uninstall, and for each boundary which STRIDE category has "
            "no mitigating control?",
            "short_answer": f"Seven trust boundaries, {len(M)} STRIDE cells. "
            f"{status_counts.get('unmitigated', 0)} unmitigated, "
            f"{status_counts.get('partial', 0)} partial, "
            f"{status_counts.get('mitigated', 0)} mitigated, "
            f"{status_counts.get('not-applicable', 0)} not-applicable. The install path has NO "
            "publisher authentication, NO expansion bound, and NO containment on the "
            "version-string-to-path boundary; all three were proven by execution, not by "
            "reading. The two controls that DO hold at the boundaries tested are deploy-side "
            "safe_join and the Windows OS file lock - and the second is not this code's doing.",
            "per_target": {
                "TB1 untrusted archive -> staging": "3 unmitigated (S, I, D) + 1 unmitigated by "
                "downgrade (E), 2 partial",
                "TB2 version string -> path": "4 unmitigated, 1 partial, 1 n/a - the worst boundary",
                "TB3 staged -> live": "2 unmitigated, 1 partial, 2 mitigated, 1 n/a",
                "TB4 shared cache": "2 unmitigated, 2 partial, 2 n/a",
                "TB5 concurrency": "2 unmitigated, 1 partial, 3 n/a",
                "TB6 subprocess": "5 unmitigated by downgrade, 1 partial - NONE executed",
                "TB7 operator CLI": "1 unmitigated, 1 partial, 4 n/a",
            },
            "not_a_duplicate_of_siblings": "This unit does not execute the attacks; it tells the sibling units where to aim. "
            "Every unmitigated cell is routed to a named existing ADV unit below.",
        },
        "stride_matrix": M,
        "stride_status_counts": status_counts,
        "trust_boundaries": [
            {
                "id": "TB1",
                "name": "untrusted archive -> staging tree",
                "crossed_by": ["install", "update"],
                "anchor": "lifecycle.py:287-346 install, :355-427 update, _stage lifecycle.py:182",
            },
            {
                "id": "TB2",
                "name": "manifest version string -> filesystem path",
                "crossed_by": ["install", "update", "repair", "rollback", "uninstall"],
                "anchor": "journal.py:81-82 version_dir; manifest.py:31 SEMVER_RE",
            },
            {
                "id": "TB3",
                "name": "staged tree -> live deploy targets",
                "crossed_by": ["install", "update", "repair", "rollback"],
                "anchor": "deploy.py:484 projection_map, deploy.py:140/167/336/412 safe_join",
            },
            {
                "id": "TB4",
                "name": "shared content cache",
                "crossed_by": ["install", "update"],
                "anchor": "cache.py:59 _path, cache.py:83 _quarantine",
            },
            {
                "id": "TB5",
                "name": "concurrent operators -> prefix lock",
                "crossed_by": ["install", "update", "repair", "rollback", "uninstall"],
                "anchor": "lifecycle.py:315,404,448,495,602 PrefixLock",
            },
            {
                "id": "TB6",
                "name": "install path -> subprocess / interpreter",
                "crossed_by": ["install", "update"],
                "anchor": "proc.py:146,179; lifecycle.py:165,319,408; deploy.py:483",
            },
            {
                "id": "TB7",
                "name": "operator -> CLI process boundary",
                "crossed_by": ["install", "update", "repair", "rollback", "uninstall"],
                "anchor": "cli.py:377,390,393",
            },
        ],
        "tests_required_closure": {
            "requirement": "every unmitigated cell must be converted into either a named follow-up "
            "work unit or an explicitly accepted residual risk with an "
            "owner-visible impact statement - an unmitigated cell with neither is a "
            "unit failure",
            "cells_requiring_disposition": status_counts.get("unmitigated", 0)
            + status_counts.get("partial", 0),
            "cells_without_disposition": len(undisposed),
            "satisfied": len(undisposed) == 0,
            "routed_to_existing_catalog_units": {
                "ADV-0024": "install-time content scan absent (TB1/I)",
                "ADV-0025": "no live-target allowlist; writes outside own root (TB3/E, TB3/I)",
                "ADV-0027": "archive traversal, absolute paths, symlinks, device names; "
                "version-string traversal (TB1/E, TB2/T,I,E)",
                "ADV-0028": "no publisher signature or trust anchor (TB1/S)",
                "ADV-0029": "unsigned artifact cached and reserved; identity spoof (TB2/S, TB4/S)",
                "ADV-0030": "TOCTOU between validation and install; lock races (TB1/T, TB5/D)",
                "ADV-0031": "the entire TB6 subprocess boundary (6 cells, none executed here)",
                "ADV-0034": "decompression bomb and unbounded cache growth (TB1/D, TB4/D)",
                "ADV-0036": "ACLs on deployed files that influence execution (TB3/E, TB3/S)",
                "ADV-0037": "environment inheritance into spawned processes (TB6/I)",
                "ADV-0038": "revocation propagation to already-cached packages (TB4/T,S,I)",
                "ADV-0039": "telemetry/egress from spawned processes (TB6/I)",
                "ADV-0041": "absolute local paths in tracebacks and errors (TB7/I, TB2/I)",
            },
            "accepted_residual_risks_with_owner_impact": [
                c["disposition"]
                for c in M
                if c["disposition"].startswith("ACCEPTED RESIDUAL")
            ],
        },
        "provenance_of_this_receipt": {
            "original_agent": "agent-ae7e589262e107d7e.jsonl (124 records, 627,092 B)",
            "death_mode": "died at the artifact-assembly step after ALL measurement completed; "
            "last two assistant texts were 'All claims now have controls. Writing "
            "the artifact.' then 'API Error: Connection closed mid-response.'",
            "what_was_recovered": "both probe scripts and both probe captures, verbatim",
            "what_this_lane_added": "an independent re-execution of both probes (equivalence "
            "recorded in RERUN-EQUIVALENCE.json), a new mechanically "
            "different AST/exec verifier, the STRIDE projection, and the "
            "tests_required closure",
            "run_A_is_not_cited": "adv0021_results.ORIGINAL.json (run A) self-diagnosed three "
            "broken detectors and is superseded by run B",
        },
    },
    "extensions": {
        "self_digest_recipe": "A receipt cannot contain its own sha256 as a fixed point. artifacts[0].sha256 is "
        "therefore the ELIDED digest, defined exactly as: read this file's bytes, replace the "
        "64-character value of artifacts[0].sha256 with 64 ASCII '0' characters, then sha256 "
        "the result. artifacts[0].bytes is the true on-disk size and needs no elision.",
        "canonical_output_path": CANON,
        "canonical_path_note": "The catalog declares output_path="
        + CANON
        + ". This lane was explicitly forbidden "
        "from writing into command-center/adversarial/ because a sibling wave may still be "
        "writing there, so the artifact is delivered at "
        + SELF_REL
        + " and its promotion to "
        "the canonical path is an orchestrator action. Nothing else about the receipt changes.",
        "probe_scripts": [
            "command-center/casualty/probes/adv0021_probe1.py",
            "command-center/casualty/probes/adv0021_probe2b.py",
            "command-center/casualty/probes/adv0021_verifier.py",
        ],
    },
}

import re  # noqa: E402  (deliberate: the RECEIPT literal above must be the first thing
import subprocess  # noqa: E402  a reader sees; these are used only by the emit/gate tail)


def emit() -> str:
    """Serialize with a converged byte count and a correct elided self-digest."""
    RECEIPT["artifacts"][0]["sha256"] = "0" * 64
    for _ in range(4):
        blob = json.dumps(RECEIPT, indent=2, ensure_ascii=False)
        n = len(blob.encode("utf-8"))
        if RECEIPT["artifacts"][0]["bytes"] == n:
            break
        RECEIPT["artifacts"][0]["bytes"] = n
    blob = json.dumps(RECEIPT, indent=2, ensure_ascii=False)
    RECEIPT["artifacts"][0]["sha256"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    out = json.dumps(RECEIPT, indent=2, ensure_ascii=False)
    assert len(out.encode("utf-8")) == RECEIPT["artifacts"][0]["bytes"]
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    return out


def run_gate() -> str:
    r = subprocess.run(
        ["python", "platform/lib/receipt_schema_gate.py", SELF_REL, "--repo-root", "."],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return (r.stdout + r.stderr).replace("\r\n", "\n").strip()


def marker(text: str) -> str:
    return text.split("\n")[0]


# PHASE 1: write with the placeholder, then run the real gate against the real file.
emit()
g1 = run_gate()
# The on-disk digest quoted by condition 3 is volatile by construction (it changes
# the moment this capture is embedded). Normalise ONLY that token, and say so.
NORM = "<VOLATILE-ON-DISK-DIGEST>"
g1_norm = re.sub(r"on-disk [0-9a-f]{12}\.\.\.", f"on-disk {NORM}", g1)
capture = (
    "$ python platform/lib/receipt_schema_gate.py "
    + SELF_REL
    + " --repo-root .\n"
    + g1_norm
    + "\n\n[capture note] Exactly one token above is normalised: the 12-hex on-disk digest "
    "quoted by condition 3, rendered as "
    + NORM
    + ". It is volatile by construction because "
    "embedding this very capture changes the file it describes. Everything else is verbatim, "
    "and the build asserts the condition vector is byte-identical before and after embedding."
)
RECEIPT["downstream_consumers"][0]["probe"]["raw_output"] = capture

# PHASE 2: re-emit with the capture embedded, then prove the verdict vector did not move.
emit()
g2 = run_gate()
assert marker(g1) == marker(g2), (
    f"gate vector moved between phases:\n{marker(g1)}\n{marker(g2)}"
)
final = io.open(OUT, encoding="utf-8", newline="").read()
elided = RECEIPT["artifacts"][0]["sha256"]

print("WROTE", OUT)
print("bytes on disk:", os.path.getsize(OUT))
print("declared bytes:", RECEIPT["artifacts"][0]["bytes"])
print("elided sha256:", elided)
print("gate marker (stable across both phases):", marker(g2))
print("stride cells:", len(M), status_counts)
print("undisposed unmitigated/partial cells:", len(undisposed))
print(
    "evidence items:",
    len(E),
    "tests:",
    len(TESTS),
    "controls:",
    len(NC),
    "observations:",
    len(OBS),
    "defects:",
    len(RECEIPT["defects"]),
)
