"""Generator for catalog slice TST-2 (bucket B08, units 129-256).

Bucket B08 = "testing, benchmark, mutation, fuzz, chaos, and deliberation-calibration"
(_USER-PROMPTS.md:10561, 352 units). This slice is part 2 of 3.

DECLARED SCOPE OF THIS SLICE (so parts 1 and 3 can be deduped mechanically):
Phase-10 test layers 19 THROUGH 36 as enumerated verbatim at _USER-PROMPTS.md:11007-11024,
i.e. the second half of the spec's own 36-layer list, plus the subset of the
"known failure classes that must be in the regression suite" (_USER-PROMPTS.md:11298-11347)
that those layers own.

Layers 1-18 (unit / integration / contract / schema / clean-install / upgrade / rollback /
uninstall / cross-platform / cross-client / differential-replay / mutation / property /
fuzz / concurrency / load / soak / chaos) are NOT in this slice.
Deliberation-calibration and the benchmark PLATFORM build are also not in this slice except
where a phase-10 layer names them (layers 33, 34).

Fields emitted per unit: the 19 mandatory fields contracted at
_USER-PROMPTS.md:10607-10625 (the spawn brief said "20"; the spec list and
command-center/WORK-UNIT-CATALOG.json:contract.work_unit_fields both enumerate 19).
Field NAMES follow the spawn brief (question_or_target, assigned_model_vendor_role),
not the repo catalog's shorter aliases (target, assignment).
"""

import io
import json
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TST-2.json")

SPEC = "_USER-PROMPTS.md"
GATES = "command-center/COMPLETION-GATES.json"
PRED = SPEC + ":10627-10648 (shared completion predicate, 12 conditions)"
FAILCLASSES = SPEC + ":11298-11347 (known failure classes that must be in the regression suite)"
NEGCTL = SPEC + ":11026 (every important suite must carry negative controls or mutations)"
STOP = SPEC + ":11376-11398 (program stopping rule, conditions 4 and 5)"

OPUS = {"vendor": "anthropic", "model": "opus", "role": None}
CODEX = {"vendor": "openai", "model": "codex-cli-default", "role": None}

BASE_RETRY = (
    "two strikes then pivot (AGENTS.md 4b): after the second failure on the same "
    "hypothesis, enumerate >=2 alternative approaches before a third attempt"
)
FLAKE_RETRY = (
    "up to 3 attempts with full-jitter backoff; a flake rate above 1-in-20 reruns is "
    "filed as a DEFECT against the test, never absorbed as a retry"
)
NO_RETRY = (
    "no automatic retry: a failure here is a finding, not a transient; re-run only after "
    "a named change to the harness or the fixture"
)

REV_1 = ("one independent adversarial reviewer in a fresh context who did not author the "
         "harness under test")
REV_SEC = ("two reviewers: a cross-vendor (Codex) security reviewer plus one correctness "
           "reviewer in a fresh context; both must reproduce the both-states control")
REV_WIN = ("one independent reviewer who re-runs the probe on a SECOND Windows shell "
           "(pwsh7 and Git Bash) and reports any divergence as a finding")
REV_XV = ("one cross-vendor reviewer (Codex) plus one Claude reviewer; disagreement is "
          "resolved from the raw probe output, never by vote")

SCHEMA = "command-center/schema/receipt.schema.json"


def sch(frag=None):
    return SCHEMA if frag is None else SCHEMA + "#/$defs/" + frag


# ---------------------------------------------------------------- layer defaults
L = {
    19: dict(
        name="network-fault", line=11007,
        substrate="cloud-batch", timeout=2700,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(OPUS, role="fault-injection-tester"),
        inputs=[SPEC + ":11007 (Phase 10 layer 19, network-fault tests)", PRED,
                "tools/lib/net-allowlist.mjs", "B07 registry + package-download clients"],
        deps=["B07", "B06"],
        retry=FLAKE_RETRY, rev=REV_1,
        fails=["detector-failure", "flaky-nondeterminism", "green-not-live", "dependency-blocked"],
        frag="fault_injection_report",
    ),
    20: dict(
        name="rate-limit", line=11008,
        substrate="cloud-batch", timeout=3600,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(OPUS, role="scheduler-tester"),
        inputs=[SPEC + ":11008 (Phase 10 layer 20, rate-limit tests)",
                SPEC + ":10570-10583 (separate logical count from simultaneous concurrency)",
                "tools/command-center/measure_rate.py", "B07 dispatcher + scheduler"],
        deps=["B07"],
        retry=FLAKE_RETRY, rev=REV_1,
        fails=["detector-failure", "flaky-nondeterminism", "green-not-live", "overclaim"],
        frag="scheduler_report",
    ),
    21: dict(
        name="partial-artifact", line=11009,
        substrate="local-parallel", timeout=1800,
        tools=["Read", "Grep", "Glob", "Bash", "Write"],
        who=dict(OPUS, role="completion-predicate-tester"),
        inputs=[SPEC + ":11009 (Phase 10 layer 21, partial-artifact tests)", PRED, GATES,
                "command-center/ARTIFACT-MANIFEST.json"],
        deps=["B06", "B07"],
        retry=BASE_RETRY, rev=REV_1,
        fails=["detector-failure", "uncontrolled-silence", "green-not-live", "fixture-invalid"],
        frag="predicate_report",
    ),
    22: dict(
        name="stale-monitor", line=11010,
        substrate="local-serialized", timeout=2700,
        tools=["Read", "Grep", "Bash", "PowerShell", "Write"],
        who=dict(OPUS, role="observability-tester"),
        inputs=[SPEC + ":11010 (Phase 10 layer 22, stale-monitor tests)",
                "rules/common/bash-hud-and-terminal-emit.md",
                "rules/common/single-signal-verification.md",
                "B07 cockpit / monitor surface"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_WIN,
        fails=["detector-failure", "uncontrolled-silence", "overclaim", "platform-gap"],
        frag="monitor_report",
    ),
    23: dict(
        name="duplicate-dispatch", line=11011,
        substrate="local-parallel", timeout=3600,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(OPUS, role="concurrency-tester"),
        inputs=[SPEC + ":11011 (Phase 10 layer 23, duplicate-dispatch tests)",
                SPEC + ":10965-10983 (Phase 9 work claims, file leases, duplicate suppression)",
                "tools/lib/handled-ledger.mjs"],
        deps=["B07"],
        retry=FLAKE_RETRY, rev=REV_1,
        fails=["detector-failure", "flaky-nondeterminism", "green-not-live", "dependency-blocked"],
        frag="concurrency_report",
    ),
    24: dict(
        name="resume", line=11012,
        substrate="worktree-isolated", timeout=3600,
        tools=["Read", "Grep", "Bash", "Write", "Edit"],
        who=dict(OPUS, role="resume-tester"),
        inputs=[SPEC + ":11012 (Phase 10 layer 24, resume tests)",
                SPEC + ":10874-10896 (Phase 7 resume, deterministic replay, artifact caching)",
                "tools/lib/handled-ledger.mjs"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_1,
        fails=["detector-failure", "green-not-live", "overclaim", "fixture-invalid"],
        frag="resume_report",
    ),
    25: dict(
        name="corrupted-cache", line=11013,
        substrate="local-parallel", timeout=2700,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(OPUS, role="cache-integrity-tester"),
        inputs=[SPEC + ":11013 (Phase 10 layer 25, corrupted-cache tests)",
                SPEC + ":11305 (stale cache masks a fixed package)",
                "B05/B07 cache refresh and invalidation implementation"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_1,
        fails=["detector-failure", "green-not-live", "uncontrolled-silence", "fixture-invalid"],
        frag="cache_report",
    ),
    26: dict(
        name="strict-parser", line=11014,
        substrate="cloud-batch", timeout=1800,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(CODEX, role="schema-conformance-tester"),
        inputs=[SPEC + ":11014 (Phase 10 layer 26, strict-parser tests)",
                SPEC + ":11302 (strict plugin parser rejects unknown fields)",
                SPEC + ":11309 (case-insensitive parser collision on case-distinct JSON keys)",
                "B06 plugin/marketplace manifest schemas"],
        deps=["B06"],
        retry=BASE_RETRY, rev=REV_1,
        fails=["detector-failure", "overclaim", "green-not-live", "fixture-invalid"],
        frag="parser_report",
    ),
    27: dict(
        name="shell-quoting", line=11015,
        substrate="local-serialized", timeout=2700,
        tools=["Read", "Grep", "Bash", "PowerShell", "Write"],
        who=dict(OPUS, role="shell-portability-tester"),
        inputs=[SPEC + ":11015 (Phase 10 layer 27, shell-quoting tests)",
                "rules/common/windows-shell.md",
                "rules/common/cross-vendor-dispatch.md",
                "tools/lib/codex-invocation.mjs"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_WIN,
        fails=["detector-failure", "platform-gap", "green-not-live", "uncontrolled-silence"],
        frag="shell_report",
    ),
    28: dict(
        name="path-casing", line=11016,
        substrate="local-serialized", timeout=2700,
        tools=["Read", "Grep", "Glob", "Bash", "PowerShell", "Write"],
        who=dict(OPUS, role="portability-tester"),
        inputs=[SPEC + ":11016 (Phase 10 layer 28, path-casing tests)",
                SPEC + ":11309 (case-insensitive parser collision)",
                "command-center/BASELINE-SNAPSHOT.json"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_WIN,
        fails=["detector-failure", "platform-gap", "green-not-live", "fixture-invalid"],
        frag="portability_report",
    ),
    29: dict(
        name="long-path", line=11017,
        substrate="local-serialized", timeout=2700,
        tools=["Read", "Bash", "PowerShell", "Write"],
        who=dict(OPUS, role="portability-tester"),
        inputs=[SPEC + ":11017 (Phase 10 layer 29, long-path tests)",
                "rules/common/windows-shell.md",
                "B07 artifact writer + package extractor"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_WIN,
        fails=["detector-failure", "platform-gap", "green-not-live", "owner-blocked"],
        frag="portability_report",
    ),
    30: dict(
        name="secret-leak", line=11018,
        substrate="cloud-batch", timeout=2700,
        tools=["Read", "Grep", "Glob", "Bash", "Write"],
        who=dict(CODEX, role="security-tester"),
        inputs=[SPEC + ":11018 (Phase 10 layer 30, secret-leak tests)",
                SPEC + ":11345 (credentials or decrypted secrets enter an artifact bundle)",
                "AGENTS.md:9 (security non-negotiables)", "tools/lib/security.mjs"],
        deps=["B07"],
        retry=NO_RETRY, rev=REV_SEC,
        fails=["detector-failure", "green-not-live", "overclaim", "owner-blocked"],
        frag="security_report",
    ),
    31: dict(
        name="malicious-plugin", line=11019,
        substrate="cloud-batch", timeout=3600,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(CODEX, role="supply-chain-auditor"),
        inputs=[SPEC + ":11019 (Phase 10 layer 31, malicious-plugin tests)",
                SPEC + ":11346 (marketplace package has malicious or excessive permissions)",
                SPEC + ":10844-10871 (Phase 6 marketplace trust surface)",
                "AGENTS.md:9 (a cloned repo can carry auto-loaded agent config)"],
        deps=["B07"],
        retry=NO_RETRY, rev=REV_SEC,
        fails=["detector-failure", "green-not-live", "overclaim", "owner-blocked"],
        frag="security_report",
    ),
    32: dict(
        name="permission-boundary", line=11020,
        substrate="worktree-isolated", timeout=2700,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(OPUS, role="security-tester"),
        inputs=[SPEC + ":11020 (Phase 10 layer 32, permission-boundary tests)",
                SPEC + ":10613-10614 (per-unit tool permissions and execution substrate)",
                "tools/lib/workspace.mjs", "tools/lib/net-allowlist.mjs"],
        deps=["B06", "B07"],
        retry=NO_RETRY, rev=REV_SEC,
        fails=["detector-failure", "green-not-live", "overclaim", "owner-blocked"],
        frag="security_report",
    ),
    33: dict(
        name="benchmark-regression", line=11021,
        substrate="cloud-batch", timeout=5400,
        tools=["Read", "Grep", "Bash", "Write"],
        who=dict(OPUS, role="benchmark-engineer"),
        inputs=[SPEC + ":11021 (Phase 10 layer 33, benchmark regression tests)",
                SPEC + ":10656-10657 (capture benchmark baselines before changing behavior)",
                SPEC + ":11385 (stopping condition 8: intended improvement without material regression)"],
        deps=["B07"],
        retry=FLAKE_RETRY, rev=REV_XV,
        fails=["detector-failure", "overclaim", "green-not-live", "flaky-nondeterminism"],
        frag="benchmark_result",
    ),
    34: dict(
        name="latency-overhead", line=11022,
        substrate="local-serialized", timeout=3600,
        tools=["Read", "Grep", "Bash", "PowerShell", "Write"],
        who=dict(OPUS, role="performance-tester"),
        inputs=[SPEC + ":11022 (Phase 10 layer 34, latency and overhead tests)",
                "rules/common/bash-hud-and-terminal-emit.md",
                "command-center/BASELINE-SNAPSHOT.json"],
        deps=["B07"],
        retry=FLAKE_RETRY, rev=REV_1,
        fails=["detector-failure", "flaky-nondeterminism", "overclaim", "platform-gap"],
        frag="benchmark_result",
    ),
    35: dict(
        name="accessibility-ux", line=11023,
        substrate="local-serialized", timeout=2700,
        tools=["Read", "Grep", "Bash", "PowerShell", "Write"],
        who=dict(OPUS, role="accessibility-tester"),
        inputs=[SPEC + ":11023 (Phase 10 layer 35, accessibility and UX tests)",
                SPEC + ":10840 (clear user-facing error messages)",
                "rules/common/bash-hud-and-terminal-emit.md"],
        deps=["B07"],
        retry=BASE_RETRY, rev=REV_1,
        fails=["detector-failure", "platform-gap", "overclaim", "green-not-live"],
        frag="ux_report",
    ),
    36: dict(
        name="documentation-command", line=11024,
        substrate="cloud-batch", timeout=3600,
        tools=["Read", "Grep", "Glob", "Bash", "Write"],
        who=dict(CODEX, role="docs-conformance-tester"),
        inputs=[SPEC + ":11024 (Phase 10 layer 36, documentation command tests)",
                SPEC + ":11389 (stopping condition 12: docs and code agree)",
                "command-center/RUNBOOK.md", "command-center/RELEASE-CHECKLIST.md"],
        deps=["B07", "B13"],
        retry=BASE_RETRY, rev=REV_1,
        fails=["detector-failure", "green-not-live", "overclaim", "fixture-invalid"],
        frag="docs_conformance_report",
    ),
}

# ------------------------------------------------------------------- unit table
# (index, layer, title, question_or_target, evidence_requirement, [tests], {overrides})
U = []


def add(n, layer, title, q, ev, tests, **ov):
    U.append((n, layer, title, q, ev, tests, ov))


# ---- L19 network-fault (129-135)
add(129, 19, "DNS failure during registry fetch fails closed",
    "When DNS resolution for the marketplace registry host fails, does `install` abort with an "
    "actionable error and leave ZERO bytes of index written, or does it fall back to a partial / "
    "previously cached index and report success? PASS requires: non-zero exit, an error naming the "
    "host and the resolver, and a byte-for-byte unchanged index file.",
    "two mechanically independent signals: (a) the process exit code plus stderr text, and "
    "(b) a pre/post sha256 of the on-disk index directory taken by a separate process; plus the "
    "both-states transcript showing the same assertion passing on a resolvable host",
    ["both-states control: assertion fires with the resolver blackholed and is silent on a "
     "reachable registry",
     "postcondition probe: index directory sha256 identical before and after the failed install"])

add(130, 19, "TLS handshake failure must not downgrade to plaintext",
    "With an expired / wrong-CN certificate presented by the registry endpoint, does the client "
    "refuse the connection outright? PASS requires: no plaintext HTTP retry on any port, no "
    "`--insecure` equivalent reachable from config, and no silent substitution of a cached index "
    "for the refused fetch.",
    "two independent signals: (a) client exit classification, and (b) a passive capture of the "
    "attempted connections proving no second connection to an http:// scheme or port 80 occurred",
    ["both-states control: a valid certificate on the same fixture endpoint must pass",
     "negative control: a config that attempts to set insecure-TLS must be rejected at parse time"],
    who=dict(CODEX, role="security-tester"), frag="security_report")

add(131, 19, "Mid-stream truncation of a package download is quarantined",
    "When a package download is reset after N of M bytes, is the partial file quarantined outside "
    "the cache and the integrity failure reported by digest mismatch? PASS requires: the cache "
    "contains no entry for that package afterward, and a later successful install is not poisoned "
    "by the truncated remnant.",
    "two independent signals: (a) digest-mismatch error emitted by the downloader, and (b) an "
    "independent directory listing of the cache showing zero entries for the package id",
    ["both-states control: a complete download of the same fixture installs cleanly",
     "follow-on probe: a second install attempt after truncation succeeds and produces the correct "
     "digest"])

add(132, 19, "Slow-loris response trips the READ timeout, not only the connect timeout",
    "When the registry accepts the connection then trickles bytes below the throughput floor, does "
    "a read/idle timeout fire and classify the unit `network-fault`? PASS requires: termination "
    "within the declared read-timeout plus a stated margin, and a classification that is NOT the "
    "generic unit timeout.",
    "two independent signals: (a) wall-clock delta measured by the harness against the configured "
    "read timeout, and (b) the emitted failure classification string in the receipt",
    ["both-states control: a normal-speed response on the same endpoint completes",
     "negative control: a client configured with connect-timeout only must FAIL this test, proving "
     "the test can distinguish the two timeout kinds"])

add(133, 19, "Hermetic audit: which tests silently reach the network",
    "Run the full suite with all egress blocked and enumerate every test that changes outcome. "
    "Target: produce the exact list of tests whose green depends on undeclared network access, and "
    "add an explicit `network` declaration to each. PASS requires: after remediation, the "
    "egress-blocked run and the egress-allowed run produce identical outcomes for every test not "
    "declaring network.",
    "two independent signals: (a) the pass/fail delta between the blocked and allowed runs, and "
    "(b) an egress log naming the destination host for every attempted connection during the "
    "blocked run",
    ["detector control: plant one test that deliberately fetches a URL and confirm the audit finds "
     "it before trusting any zero",
     "both-states control: the audit must report a non-empty list on the pre-remediation tree and "
     "an empty list after"],
    substrate="local-serialized", owner=True, timeout=5400,
    who=dict(OPUS, role="hermeticity-auditor"))

add(134, 19, "Captive-portal HTTP 200 interstitial is rejected by content, not status",
    "When a network interstitial returns HTTP 200 with an HTML body in place of the registry JSON, "
    "does the client reject it? PASS requires rejection driven by content-type plus schema "
    "validation, and an error that names the unexpected content-type rather than a JSON parse "
    "stack trace.",
    "two independent signals: (a) the emitted error string, and (b) proof the rejection path was "
    "taken before any index mutation (pre/post index mtime unchanged)",
    ["both-states control: the same client accepts the genuine JSON fixture",
     "negative control: a client that keys only on HTTP status must fail this test"])

add(135, 19, "Cancelled cross-vendor call leaves no orphan thread",
    "When a cross-vendor adapter call (Codex MCP thread) is cancelled mid-request by a network "
    "fault, does crash recovery either reclaim the thread by id or record an explicit ABANDONED "
    "receipt? PASS requires: no thread id is left in a running state with no owner, and the "
    "receipt names which of the two outcomes occurred.",
    "two independent signals: (a) the durable ledger entry for the thread id, and (b) an "
    "independent enumeration of live adapter threads after recovery showing no unowned entry",
    ["both-states control: an uncancelled call produces a normal receipt and no ABANDONED record",
     "negative control: deleting the ledger entry must make recovery report UNKNOWN, not SUCCESS"],
    substrate="local-serialized", timeout=3600,
    inputs_extra=["rules/common/cross-vendor-dispatch.md", "tools/lib/codex-invocation.mjs"])

# ---- L20 rate-limit (136-142)
add(136, 20, "Retry-After is honored in both wire formats",
    "Does the client honor `Retry-After` when expressed as delta-seconds AND as an HTTP-date? PASS "
    "requires the observed next-attempt time to fall inside the instructed window for both forms, "
    "including a date already in the past (immediate retry) and a malformed value (fall back to "
    "backoff, do not crash).",
    "two independent signals: (a) dispatch timestamps recorded by the harness, and (b) the server "
    "fixture's own arrival log; the two clocks must be reconciled and the reconciliation shown",
    ["both-states control: a client that ignores Retry-After must fail all four cases",
     "property test over 200 generated Retry-After values including negative, zero, huge and "
     "malformed"])

add(137, 20, "Arrival-rate ceiling holds under a 256-unit simultaneous release",
    "Release 256 units at t=0 and measure the observed arrival rate at the vendor boundary. Does "
    "the scheduler's stagger/jitter keep the measured rate under the configured ceiling? PASS "
    "requires the rate be measured from DISPATCH TIMESTAMPS at the boundary, never read back from "
    "the config value.",
    "two independent signals: (a) per-request dispatch timestamps binned into 1-second buckets, and "
    "(b) the fixture server's independently recorded arrival count; the two must agree within 1%",
    ["detector control: run with the stagger disabled and confirm the measurement reports a "
     "ceiling breach, proving the meter can see one",
     "both-states control: stagger enabled must be silent"],
    inputs_extra=["tools/command-center/measure_rate.py"])

add(138, 20, "Backoff is jittered, bounded, and cannot outlive the unit timeout",
    "Are retry intervals non-deterministic across runs (full jitter) while the SUM of the retry "
    "budget is provably less than the unit's `timeout_seconds`? PASS requires: interval sets from "
    "two runs differ, and no generated schedule exceeds the timeout for any configured "
    "max-attempts.",
    "two independent signals: (a) empirical interval samples across 50 runs, and (b) a symbolic or "
    "exhaustive check over the backoff function proving the bound for all attempt counts",
    ["property test: for all (base, cap, attempts) in the supported ranges, sum(schedule) < timeout",
     "negative control: a fixed-interval (unjittered) implementation must fail the "
     "non-determinism assertion"])

add(139, 20, "429 and 529 are different policies, and 529 must not shrink concurrency",
    "Does the harness distinguish a 429 (our arrival rate) from a 529 / vendor-overload (their "
    "capacity) and apply different policies? PASS requires: 429 reduces our arrival rate; 529 does "
    "NOT reduce program concurrency and instead retries the affected unit while siblings continue.",
    "two independent signals: (a) the concurrency counter sampled during the injected 529 storm, "
    "and (b) the per-unit classification recorded in the ledger",
    ["both-states control: an injected 429 storm MUST reduce arrival rate; an injected 529 storm "
     "must not - a harness that behaves identically for both fails",
     "negative control: mislabelling 529 as 429 must be detectable by this test"],
    substrate="local-serialized", timeout=3600)

add(140, 20, "Interactive lane keeps reserved headroom against a batch sweep",
    "With a batch sweep saturating the shared subscription, does an interactive request still get "
    "served within its latency budget? PASS requires: a measurable reservation (not a documented "
    "intention), and the reservation must be observable as a refused/deferred batch dispatch at "
    "the moment the interactive request arrives.",
    "two independent signals: (a) interactive request latency distribution with and without the "
    "sweep, and (b) the scheduler's deferral log showing batch units held back",
    ["both-states control: disabling the reservation must make interactive latency degrade "
     "measurably, proving the test is sensitive to it",
     "negative control: a reservation implemented only as a config comment must fail"],
    substrate="local-serialized")

add(141, 20, "Token-bucket accounting is race-free under N concurrent takers",
    "Under 64 concurrent takers, can the token bucket ever go negative or issue more permits than "
    "its capacity in any window? PASS requires zero violations across a randomized property run "
    "and a deterministic replay of any counterexample.",
    "two independent signals: (a) an invariant assertion inside the bucket, and (b) an external "
    "audit of the issued-permit log recomputing the window totals after the fact",
    ["property test with 10,000 randomized interleavings; any counterexample must shrink to a "
     "minimal reproducing schedule",
     "mutation control: remove the lock/CAS and confirm the property fails"])

add(142, 20, "Rate-limited partial fan-in returns typed PARTIAL, never a shrunken denominator",
    "When half a cohort is 429-blocked at the barrier, does fan-in return a typed PARTIAL naming "
    "every blocked unit id? PASS requires the denominator stay at the launched count; a result "
    "reporting 'N of N complete' after silently dropping blocked units is a FAIL.",
    "two independent signals: (a) the barrier's returned object compared against the launch "
    "manifest, and (b) an independent count of receipt files on disk",
    ["both-states control: an unblocked cohort returns COMPLETE with the same denominator",
     "negative control: a barrier that filters blocked units out of its own denominator must fail"],
    inputs_extra=["rules/common/fan-out-contract.md"])

# ---- L21 partial-artifact (143-149)
add(143, 21, "Zero-byte artifact fails the minimum-size condition",
    "Does completion-predicate condition 3 (non-empty and above a meaningful minimum) reject a "
    "0-byte artifact while accepting a legitimately small one at exactly the declared floor? PASS "
    "requires both directions.",
    "two independent signals: (a) the predicate's returned condition vector, and (b) an "
    "independent stat() of the file size",
    ["both-states control: 0 bytes fails, floor-sized passes",
     "boundary test at floor-1, floor, floor+1"])

add(144, 21, "Truncated JSON fails schema parse and is never cached as parsed",
    "When an artifact is non-empty but truncated mid-JSON, does condition 4 fail AND does no "
    "downstream consumer retain a partially-parsed object? PASS requires the parse cache to hold "
    "no entry for that artifact after the failure.",
    "two independent signals: (a) the parse error with byte offset, and (b) an inspection of the "
    "consumer's cache showing no entry for the artifact id",
    ["both-states control: the complete artifact parses and caches",
     "negative control: a lenient parser that repairs truncated JSON must fail this test"])

add(145, 21, "Sentinel absence is detected even when the artifact is otherwise valid",
    "Does condition 5 fire for a schema-valid, non-empty artifact whose completion sentinel is "
    "missing or belongs to a different unit id? PASS requires both the missing case and the "
    "wrong-id case to fail, with the wrong-id case naming the mismatch.",
    "two independent signals: (a) the predicate condition vector, and (b) a grep of the artifact "
    "showing the sentinel token absent or mismatched",
    ["both-states control: the correct sentinel passes",
     "use-vs-mention control: an artifact that MENTIONS the sentinel inside a quoted example must "
     "NOT satisfy the check"])

add(146, 21, "Every artifact writer publishes atomically (tmp + rename)",
    "Do all writers publish via a temporary file plus atomic rename, so a crash cannot expose a "
    "partial artifact? Target: prove it two ways - a static scan of all write paths AND a "
    "crash-injection run that SIGKILLs the writer mid-write. PASS requires zero readable partial "
    "artifacts across 100 injected crashes.",
    "two independent signals: (a) the static scan's enumeration of write call sites, and (b) the "
    "crash-injection run's observed reader outcomes",
    ["detector control: add one deliberately non-atomic writer and confirm both the scan and the "
     "crash run find it",
     "crash-injection: 100 SIGKILLs at randomized offsets"])

add(147, 21, "An evidence anchor that does not resolve counts as MISSING",
    "Does condition 6 treat a file:line anchor pointing at a nonexistent file, or a line beyond "
    "end-of-file, as missing evidence? PASS requires resolution of every anchor against the "
    "filesystem at the recorded revision; a syntactically valid but unresolvable anchor is a FAIL.",
    "two independent signals: (a) the anchor resolver's per-anchor verdict, and (b) an independent "
    "`git cat-file -p <rev>:<path>` confirming existence and line count",
    ["both-states control: a resolvable anchor passes, an off-by-1000 line number fails",
     "negative control: a checker that only regex-validates the anchor SHAPE must fail this test"],
    inputs_extra=["rules/common/single-signal-verification.md"])

add(148, 21, "Missing shard is named, not averaged away",
    "For a multi-shard artifact set where 3 of 4 shards exist, does the reducer report the missing "
    "shard BY ID rather than computing a result over what is present? PASS requires the returned "
    "status be INCOMPLETE with the missing id enumerated.",
    "two independent signals: (a) the reducer's returned status object, and (b) an independent "
    "directory listing diffed against the shard manifest",
    ["both-states control: all 4 shards present returns COMPLETE",
     "negative control: a reducer that computes over present shards only must fail"])

add(149, 21, "Unregistered artifact fails condition 11 even when it exists on disk",
    "Does the predicate fail a unit whose artifact exists, parses and carries the sentinel but was "
    "never registered in ARTIFACT-MANIFEST.json? PASS requires the manifest check read the manifest "
    "FROM DISK, not from the writer's in-memory claim.",
    "two independent signals: (a) the predicate condition vector, and (b) a fresh process re-reading "
    "the manifest and confirming the absence",
    ["both-states control: registering the artifact flips the verdict to PASS",
     "negative control: a check that trusts the writer's return value must fail"],
    inputs_extra=["command-center/ARTIFACT-MANIFEST.json"])

# ---- L22 stale-monitor (150-156)
add(150, 22, "Monitor death does not lose remote terminal state",
    "Kill the monitor while remote work continues: after restart, is every remote unit's terminal "
    "state recoverable from the durable ledger? PASS requires zero units in an UNKNOWN state that "
    "the remote side considers finished.",
    "two independent signals: (a) the post-restart ledger reconciliation report, and (b) the remote "
    "runtime's own job list queried directly",
    ["both-states control: an uninterrupted run reconciles to zero UNKNOWNs",
     "negative control: state held only in monitor memory must be detectable as lost by this test"])

add(151, 22, "Heartbeat separates idle-but-alive from hung",
    "Does the liveness signal distinguish a process that is alive and idle from one that is hung? "
    "PASS requires a heartbeat emitted independently of work output, and the detector must flip "
    "when the process is SIGSTOPped and again when it is killed.",
    "two independent signals: (a) heartbeat age, and (b) process CPU-time delta sampled over 20s",
    ["both-states control: detector silent while idle-alive, fires when SIGSTOPped",
     "detector control: confirm the probe reports ALIVE for a known-running process before trusting "
     "any DEAD verdict"])

add(152, 22, "mtime-only stall detection is banned and provably absent",
    "Target: prove no liveness or stall claim in the cockpit is derived from file mtimes alone. "
    "PASS requires: a static trace of each liveness signal to its source, plus a live case where an "
    "11-hour-finished agent is presented and the cockpit does NOT report it as a stall.",
    "two independent signals: (a) the source trace of each rendered liveness field, and (b) the "
    "rendered output for a synthetic long-finished agent fixture",
    ["both-states control: a genuinely active agent renders as active; a long-finished one renders "
     "as finished, not stalled",
     "regression seed: the measured statusline defect where an 11-hour-old finished agent read as a "
     "live stall"],
    inputs_extra=["rules/common/bash-hud-and-terminal-emit.md"])

add(153, 22, "Expired cache renders UNKNOWN, never the last good value",
    "When a cockpit panel's cached value exceeds its TTL, does the panel render UNKNOWN rather than "
    "a stale number? PASS requires the stale value never appear without an explicit age marker.",
    "two independent signals: (a) the rendered pane text at TTL+1, and (b) the cache file's mtime "
    "read by a separate process",
    ["both-states control: a fresh value renders normally",
     "negative control: a renderer that falls back to last-good silently must fail"])

add(154, 22, "Monotonic clock is used for elapsed time; wall-clock jumps cannot fake a timeout",
    "Does elapsed-time computation use a monotonic source, so that a backward wall-clock adjustment "
    "cannot mark a running unit as timed out (nor a stalled one as fresh)? PASS requires the unit "
    "survive a simulated backward and forward clock jump.",
    "two independent signals: (a) the unit's state across the injected clock jump, and (b) a static "
    "check that no elapsed computation reads a wall-clock source",
    ["both-states control: a real timeout must still fire during the jump test",
     "negative control: a wall-clock implementation must fail both directions"])

add(155, 22, "Log rotation under a live reader causes neither crash nor double-count",
    "While the monitor tails a log, rotate it: does the reader continue without crashing and "
    "without re-counting lines already consumed? PASS requires an exact line-count match against "
    "the concatenated pre- and post-rotation content.",
    "two independent signals: (a) the monitor's counted lines, and (b) an offline count over the "
    "rotated files concatenated in order",
    ["both-states control: no rotation yields the same count",
     "boundary test: rotation exactly between two writes, and mid-line"])

add(156, 22, "A cancelled render cannot leave a half-written cache",
    "Cancel the render mid-write repeatedly: can any subsequent read observe a truncated cache "
    "file? PASS requires atomic publish and zero observed partial reads across 200 cancellations.",
    "two independent signals: (a) reader-side parse outcomes across the cancellation run, and "
    "(b) a directory scan showing no orphan tmp files left behind",
    ["both-states control: an uncancelled render publishes normally",
     "mutation control: replace the atomic rename with a direct write and confirm partial reads "
     "appear"])

# ---- L23 duplicate-dispatch (157-163)
add(157, 23, "Concurrent dispatch of one unit id yields exactly one winner",
    "When the same unit id is dispatched twice concurrently, does the work-claim lease admit exactly "
    "one executor while the loser returns DUPLICATE-SUPPRESSED? PASS requires exactly one receipt "
    "and a typed suppression result for the loser - not a second receipt, and not silence.",
    "two independent signals: (a) receipt count on disk for the id, and (b) both callers' returned "
    "status objects",
    ["both-states control: two DIFFERENT ids both execute",
     "race amplification: 100 trials with randomized start skew"])

add(158, 23, "Catalog merge refuses colliding id namespaces",
    "When two catalog slices reuse the same id namespace with different meanings, does the merger "
    "refuse and enumerate the colliding ids? PASS requires refusal plus the full collision list; "
    "silently taking last-wins is a FAIL.",
    "two independent signals: (a) the merger's exit status and collision list, and (b) an "
    "independent set-intersection computed over the two slices' id fields",
    ["both-states control: two disjoint slices merge cleanly",
     "regression seed: the measured 31-way M-NN collision between the option universe and the "
     "architecture-candidates mechanism cards"],
    inputs_extra=["command-center/OPTION-ID-RESOLUTION.json",
                  "tools/command-center/catalog.py"])

add(159, 23, "Idempotent retry cannot overwrite a completed receipt",
    "After a false-negative timeout where the original unit actually completed, does a retry refuse "
    "to overwrite the existing terminal receipt? PASS requires write-once semantics with a version "
    "guard and a recorded DUPLICATE-COMPLETION event.",
    "two independent signals: (a) the receipt's content hash before and after the retry, and (b) the "
    "event log entry naming the suppressed write",
    ["both-states control: a retry of a genuinely failed unit DOES write a new receipt",
     "negative control: last-write-wins semantics must fail this test"])

add(160, 23, "Intentional cross-vendor replication is labelled, not double-counted",
    "When a unit is deliberately run on two vendors for independence, is the pair labelled as one "
    "logical unit with two observations? PASS requires coverage metrics count it once and the "
    "independence claim is only made when the two runs share no input artifact.",
    "two independent signals: (a) the coverage denominator computed from the catalog, and (b) an "
    "input-provenance diff proving the two runs did not read the same intermediate",
    ["both-states control: an accidental duplicate (same vendor, same inputs) must be flagged as "
     "duplication, not independence",
     "negative control: counting both runs toward coverage must fail"],
    inputs_extra=["rules/common/single-signal-verification.md"])

add(161, 23, "File-lease conflict surfaces and expiry cannot silently transfer a live write",
    "Do two sessions requesting the same file lease see an explicit conflict, and can a lease "
    "expiring mid-write transfer ownership without the original writer noticing? PASS requires the "
    "expiring writer to fail its next write rather than continue.",
    "two independent signals: (a) the second requester's returned conflict object, and (b) the "
    "first writer's post-expiry write outcome",
    ["both-states control: non-overlapping paths lease independently",
     "negative control: an advisory-only lease with no write-time recheck must fail the second case"])

add(162, 23, "Resume skips terminal units and re-dispatches corrupted claims",
    "On resume, are already-terminal units skipped and units with a corrupted claim record "
    "re-dispatched? PASS requires both behaviors; a corrupted claim that is silently skipped is the "
    "dangerous failure and must be detected.",
    "two independent signals: (a) the resume plan's skip/redispatch lists, and (b) an independent "
    "diff of receipts present before and after resume",
    ["both-states control: intact claims skip, corrupted claims re-dispatch",
     "mutation control: truncate one claim record and confirm the re-dispatch happens"])

add(163, 23, "Launcher edited mid-run is detected by a spec hash at fan-in",
    "If the fan-out launcher or unit spec is edited after launch, does fan-in detect that units ran "
    "under different contracts? PASS requires a spec hash recorded at dispatch and compared at "
    "fan-in, with a typed CONTRACT-DRIFT result naming the two hashes.",
    "two independent signals: (a) the recorded per-unit spec hash, and (b) the current spec file "
    "hash recomputed at fan-in by a separate process",
    ["both-states control: an unedited run reports no drift",
     "regression seed: the measured mid-run edit that left contradictory tool-call caps live"],
    inputs_extra=["rules/common/fan-out-contract.md"])

# ---- L24 resume (164-171)
add(164, 24, "Mid-phase resume reproduces the uninterrupted downstream artifacts",
    "Does resuming from a mid-phase checkpoint produce downstream artifacts byte-identical to an "
    "uninterrupted run, after excluding fields explicitly declared non-deterministic? PASS requires "
    "the non-deterministic field list be declared UP FRONT, not discovered by diffing.",
    "two independent signals: (a) a byte diff of the two artifact trees, and (b) a normalized diff "
    "after applying the declared non-determinism mask",
    ["both-states control: an undeclared non-deterministic field must make the byte diff fail, "
     "proving the mask is not a blanket",
     "negative control: masking everything must be rejected by a mask-coverage ceiling"])

add(165, 24, "Older checkpoint schema triggers migration or a loud refusal",
    "When the checkpoint on disk predates the current schema version, does resume run a versioned "
    "migration or refuse loudly? PASS forbids a partial read that silently drops unknown fields.",
    "two independent signals: (a) the resume exit status and message, and (b) a field-set diff "
    "between the old checkpoint and the migrated one showing zero silent drops",
    ["both-states control: a current-version checkpoint resumes without migration",
     "negative control: a lenient loader that ignores unknown fields must fail"])

add(166, 24, "Checkpoint pinned SHA mismatch is a decision, not an auto-accept",
    "If HEAD moved since the checkpoint, does resume surface the SHA mismatch and require an "
    "explicit choice? PASS requires the pinned SHA be validated and the divergence summarized "
    "(files changed) before any work continues.",
    "two independent signals: (a) the resume prompt/record naming both SHAs, and (b) an independent "
    "`git diff --name-only <pinned>..HEAD` listing",
    ["both-states control: an unchanged HEAD resumes without a prompt",
     "negative control: auto-accepting the new HEAD must fail"])

add(167, 24, "Council resume restores rounds, votes AND dissent",
    "Does resuming a council mid-deliberation restore round state, per-round votes, confidence "
    "trajectory and the minority report? PASS requires dissent survive the round trip; dissent loss "
    "on resume is a named failure class.",
    "two independent signals: (a) a structural diff of the pre-suspend and post-resume council "
    "state, and (b) the final transcript's minority-report section compared against the pre-suspend "
    "one",
    ["both-states control: an uninterrupted council produces the same dissent content",
     "regression seed: dissent/minority report is dropped (_USER-PROMPTS.md:11340)"],
    inputs_extra=[SPEC + ":11340 (dissent/minority report is dropped)", "B05 council runtime"],
    deps_extra=["B05"])

add(168, 24, "Resume of an in-flight dynamic fan-out orphans nothing and duplicates nothing",
    "When a workflow is suspended while a dynamic fan-out is in flight, does resume re-derive every "
    "child's state exactly once? PASS requires: children_after == children_before, with no child in "
    "an unowned state and no child executed twice.",
    "two independent signals: (a) child id set before and after, and (b) receipt count per child id",
    ["both-states control: suspending before the fan-out starts and after it completes both resume "
     "cleanly",
     "race amplification: suspend at 20 randomized points inside the fan-out"])

add(169, 24, "Cold resume after reboot depends on nothing in memory",
    "After a full machine reboot, does resume work with no reliance on process tables, environment "
    "variables set only by the previous session, or a temp directory that reboot clears? PASS "
    "requires a successful cold resume from a clean shell.",
    "two independent signals: (a) the cold-resume run's outcome, and (b) a static scan enumerating "
    "every state read at resume time and its durability class",
    ["both-states control: a warm resume in the same session also passes",
     "detector control: plant one temp-dir dependency and confirm the cold resume fails"],
    substrate="local-serialized", timeout=5400)

add(170, 24, "Resume cannot launder the retry, token or time budget",
    "Does a resumed run continue the original budgets rather than resetting them? PASS requires the "
    "post-resume budget equal the pre-suspend remainder for retries, tokens and wall-clock.",
    "two independent signals: (a) the budget ledger before and after, and (b) an end-to-end tally "
    "of consumed budget across both legs compared against the declared cap",
    ["both-states control: a fresh run starts with the full budget",
     "negative control: a resume that resets any of the three budgets must fail"],
    deps_extra=["TST-0164"])

add(171, 24, "Orphan artifact between write and manifest registration resolves deterministically",
    "SIGKILL the runner between artifact write and manifest registration: does resume deterministically "
    "either register the orphan or discard it? PASS requires the SAME outcome across 50 trials - a "
    "coin-flip outcome is a FAIL even if both branches are individually safe.",
    "two independent signals: (a) the per-trial outcome distribution, and (b) the manifest state "
    "after each trial verified by an independent reader",
    ["both-states control: a clean shutdown always registers",
     "determinism assertion: 50/50 trials must share one outcome"],
    deps_extra=["TST-0146"])

# ---- L25 corrupted-cache (172-178)
add(172, 25, "Cache key includes content hash so a fixed package cannot stay masked",
    "Does the cache key incorporate the package CONTENT hash rather than only name+version, so a "
    "republished fix is not masked by a stale entry? PASS requires a same-version republish to be "
    "fetched, not served from cache.",
    "two independent signals: (a) the resolved cache key string, and (b) an install run after a "
    "same-version republish showing the new content on disk",
    ["both-states control: an unchanged package IS served from cache (the cache must still work)",
     "regression seed: stale cache masks a fixed package (_USER-PROMPTS.md:11305)"])

add(173, 25, "Bit-flipped cache payload is caught on read and refetched",
    "When a cached payload is corrupted after write, is the corruption caught on read by checksum "
    "and the entry quarantined and refetched? PASS forbids both a crash and a silent use of the "
    "corrupt bytes.",
    "two independent signals: (a) the checksum mismatch event, and (b) the post-recovery file hash "
    "matching the authoritative digest",
    ["both-states control: an intact entry reads without a refetch",
     "fuzz: 500 single-bit and multi-byte corruptions at randomized offsets"])

add(174, 25, "Concurrent cache writers cannot expose a partial entry",
    "With two processes writing the same cache key concurrently, can any reader observe a partial "
    "entry? PASS requires atomic publish and a well-defined winner; readers must see either the old "
    "entry or a complete new one.",
    "two independent signals: (a) reader-side integrity checks across the concurrent run, and "
    "(b) an inspection for leftover temp files",
    ["property test: 1,000 interleavings with a reader thread asserting integrity on every read",
     "mutation control: remove the atomic publish and confirm partial reads appear"])

add(175, 25, "Upgrade clears derived caches and preserves user data",
    "Does `update` / `install --repair` invalidate exactly the caches it owns while leaving user "
    "data untouched? PASS requires an explicit ownership manifest for cache paths; anything not on "
    "it must survive the upgrade byte-identical.",
    "two independent signals: (a) a pre/post tree hash of the user-data directories, and (b) the "
    "cache directory's post-upgrade emptiness for owned paths only",
    ["both-states control: a planted user file survives; a planted derived-cache file is removed",
     "regression seed: rollback removes existing commands or user data "
     "(_USER-PROMPTS.md:11347)"],
    substrate="worktree-isolated")

add(176, 25, "A failed fetch is not cached as a permanent absence",
    "Is a transient fetch failure negatively cached with a SHORT ttl and clearly distinguished from "
    "a genuine absence? PASS requires a retry after the negative-ttl to hit the network again; an "
    "empty result that reports OK is the failure being tested.",
    "two independent signals: (a) the second attempt's observed network call, and (b) the cache "
    "entry's recorded type (negative vs positive) and ttl",
    ["both-states control: a genuine 404 stays negatively cached for its full ttl",
     "regression seed: an EMPTY cache reporting OK, measured on this estate"])

add(177, 25, "Clean-room profile sees an empty cache (no cross-profile leakage)",
    "Does a fresh user profile observe zero inherited cache entries, and are all cache paths "
    "profile-scoped? PASS requires an install in a new profile to perform full fetches and to write "
    "only inside that profile.",
    "two independent signals: (a) the new profile's cache directory contents after install, and "
    "(b) a filesystem audit showing no writes outside the profile root during the run",
    ["both-states control: the original profile still has its cache",
     "detector control: plant a machine-wide cache entry and confirm the audit sees it"],
    substrate="local-serialized", owner=True, timeout=5400)

add(178, 25, "Eviction never removes an entry a running unit holds",
    "Under cache-size pressure, can eviction remove an entry that a running unit is actively "
    "reading? PASS requires reference counting or pinning; zero evictions of pinned entries across "
    "a randomized pressure run.",
    "two independent signals: (a) the eviction log cross-referenced against the pin table, and "
    "(b) the running units' read outcomes",
    ["property test: randomized pressure with concurrent readers, asserting no pinned eviction",
     "mutation control: disable pinning and confirm the property fails"])

# ---- L26 strict-parser (179-185)
add(179, 26, "Unknown top-level manifest field is rejected by the strict client parser",
    "Does the strict parser reject a plugin manifest carrying an unknown top-level field, with an "
    "error naming the field? PASS requires rejection under the STRICTEST supported client, and the "
    "authoring toolchain must never emit such a field.",
    "two independent signals: (a) the strict parser's error output, and (b) a schema-diff proving "
    "our emitter's field set is a subset of the accepted set",
    ["both-states control: a clean manifest is accepted",
     "regression seed: strict plugin parser rejects unknown fields (_USER-PROMPTS.md:11302)"])

add(180, 26, "Case-distinct JSON keys colliding under a case-insensitive parser are detected",
    "Do two keys differing only in case produce a detected collision rather than last-key-wins? "
    "PASS requires our emitter to never produce case-colliding keys AND our validator to reject an "
    "incoming document that has them.",
    "two independent signals: (a) the validator verdict, and (b) an independent case-folded "
    "key-set size compared against the raw key-set size",
    ["both-states control: a document with distinct case-folded keys validates",
     "regression seed: case-insensitive parser collision (_USER-PROMPTS.md:11309)"])

add(181, 26, "A `$schema` key must not change which hooks load",
    "Does the presence or absence of a `$schema` key alter how many hooks/skills a client loads? "
    "PASS requires an identical loaded set across both forms, and a loud error if any hook fails to "
    "load rather than a silent zero.",
    "two independent signals: (a) the loaded-hook count reported by the client, and (b) an "
    "independent probe firing each hook and observing its side effect",
    ["both-states control: the counts must be equal with and without `$schema`",
     "detector control: remove one hook file and confirm the count probe drops, proving it can see "
     "a change (regression seed: hooks.json $schema made a client load ZERO hooks)"])

add(182, 26, "Duplicate keys in one JSON object are rejected, not last-wins",
    "Does the validator reject an object containing the same key twice? PASS requires rejection "
    "with both values reported, because last-wins silently discards owner intent.",
    "two independent signals: (a) the validator error, and (b) a raw token-level scan counting key "
    "occurrences",
    ["both-states control: a unique-key object validates",
     "negative control: a stdlib json.load-based checker (which silently takes last) must fail this "
     "test"])

add(183, 26, "BOM and UTF-16 manifests behave deterministically and never mojibake",
    "How does the loader treat a UTF-8-with-BOM and a UTF-16LE manifest? PASS requires a single "
    "declared behavior (accept-and-normalize OR reject with a precise message) applied consistently, "
    "and zero mojibake in any accepted field value.",
    "two independent signals: (a) the loader outcome per encoding, and (b) a byte-level comparison "
    "of a round-tripped non-ASCII field value",
    ["both-states control: plain UTF-8 is accepted with identical field values",
     "regression seed: mojibake repaired at the wrong pipeline stage, measured on this estate"])

add(184, 26, "Trailing commas and comments are rejected, and our emitter never produces them",
    "Does the strict context reject JSON5-isms with a line:column, and is our emit side provably "
    "free of them? PASS requires both the reject direction and an emitter property test.",
    "two independent signals: (a) parser error with position, and (b) a scan of every emitted JSON "
    "artifact through a strict parser",
    ["both-states control: strict-clean JSON parses",
     "emitter property test over 200 generated artifacts"])

add(185, 26, "64-bit ids and precise numbers survive round-trip without float rounding",
    "Do large integer ids and high-precision numbers round-trip through our parse/emit path without "
    "loss? PASS requires exact equality for values above 2^53 and for decimals with more digits "
    "than a double can hold.",
    "two independent signals: (a) string equality of the emitted token, and (b) a decimal-typed "
    "comparison after re-parse",
    ["property test over generated ids spanning 2^40..2^63 and decimals with 20 significant digits",
     "negative control: a float-based parser must fail above 2^53"])

# ---- L27 shell-quoting (186-193)
add(186, 27, "Prose containing an apostrophe never reaches a shell command line",
    "Does the runner route apostrophe-bearing content (commit messages, PR bodies, prompts) through "
    "a FILE rather than inlining it? PASS requires: a static scan finding zero inline prose call "
    "sites, and a live case with apostrophes succeeding.",
    "two independent signals: (a) the static scan of command construction sites, and (b) an "
    "end-to-end run with an apostrophe-heavy payload",
    ["both-states control: reproduce the `unexpected EOF while looking for matching quote` failure "
     "with a deliberately inlined payload, then show the file route succeeding",
     "property test over payloads containing ', \", `, $, newline and CRLF"],
    inputs_extra=["rules/common/windows-shell.md:10 (apostrophe breaks the tool's own quoting)"])

add(187, 27, "Command-line length guard fires at the real Windows ceiling",
    "Does the dispatcher route oversized payloads to a file before the 32,767-character "
    "CreateProcess limit? PASS requires the guard fire below the ceiling and the file route succeed "
    "at 10x the ceiling.",
    "two independent signals: (a) the measured argv byte length at dispatch, and (b) the child "
    "process's received payload size",
    ["boundary test at ceiling-1, ceiling, ceiling+1 characters",
     "regression seed: payload_len=34472 producing os error 206 (cross-vendor-dispatch.md:3)"],
    inputs_extra=["rules/common/cross-vendor-dispatch.md:3 (prompt by FILE, never inline)"])

add(188, 27, "No git helper emits a bare `^` under PowerShell",
    "Does any git invocation pass a caret-bearing revision (`tag^{commit}`, `HEAD^`) unquoted "
    "through PowerShell? PASS requires zero such call sites and a live check that tag-to-commit "
    "dereference returns the correct object under pwsh7.",
    "two independent signals: (a) a static scan for caret-bearing revision arguments, and (b) a "
    "live dereference compared against `git rev-list -n 1 <tag>`",
    ["both-states control: the caret form must be shown to produce a WRONG or errored object under "
     "pwsh7, proving the hazard is real on this box",
     "regression seed: windows-shell.md:2"])

add(189, 27, "File creation never routes through a here-string payload",
    "Does the toolchain create files via a write API rather than a shell here-string, so a document "
    "quoting a destructive command is not scanned as one, and `@'`/`'@` sequences round-trip? PASS "
    "requires a byte-exact round trip of a document containing both terminators.",
    "two independent signals: (a) sha256 of the written file vs the intended content, and (b) a "
    "static scan showing zero here-string file-creation sites",
    ["both-states control: attempt the here-string route with the same content and record the "
     "corruption or block",
     "regression seed: windows-shell.md:9 (a here-string PAYLOAD is scanned as a command)"])

add(190, 27, "MSYS path conversion is scoped to revisions, never suppressed globally",
    "Is `MSYS_NO_PATHCONV` applied ONLY around revision/pathspec arguments, leaving genuine "
    "`/c/Users/...` path arguments to convert normally? PASS requires both: a revision argument "
    "survives intact AND a POSIX path argument still resolves.",
    "two independent signals: (a) the child process's observed argv, and (b) the filesystem effect "
    "of the path-carrying command",
    ["both-states control: with the variable set globally, the path-carrying command must "
     "demonstrably FAIL - proving the test can see the inversion",
     "regression seed: windows-shell.md:11 (global suppression silently skipped a clone)"])

add(191, 27, "Adversarial argument values survive as exact bytes (argv arrays, not concatenation)",
    "Do launcher arguments containing spaces, quotes, `&`, `|`, `>`, newlines, `%VAR%` and unicode "
    "arrive at the child byte-identical? PASS requires argv-array passing everywhere; any "
    "string-concatenation launcher is a FAIL.",
    "two independent signals: (a) the child's echoed argv bytes, and (b) a static scan for string "
    "concatenation in process spawn sites",
    ["property test over 500 generated adversarial argument values",
     "mutation control: replace one spawn with string concatenation and confirm the property fails"])

add(192, 27, "Generated shell scripts are LF and verified with the REAL interpreter",
    "Are all emitted `.sh` files LF-terminated and syntax-checked by the interpreter that will "
    "actually run them? PASS requires verification under real bash (WSL), not Git Bash, and a "
    "`.gitattributes` rule pinning `*.sh eol=lf`.",
    "two independent signals: (a) a CRLF byte count over the committed BLOB via "
    "`git cat-file -p <rev>:<path>`, and (b) `wsl bash -n` exit status",
    ["both-states control: a deliberately CRLF script must FAIL the WSL check while PASSING a "
     "Git-Bash check, proving the two detectors differ",
     "regression seed: windows-shell.md:3"])

add(193, 27, "Workflow parameters are never re-parsed by a shell",
    "Can a workflow parameter containing `$(...)`, backticks or `%VAR%` cause command substitution "
    "anywhere in the pipeline? PASS requires zero substitution across every parameter sink, proven "
    "by a canary that would create a marker file if evaluated.",
    "two independent signals: (a) absence of the canary marker file, and (b) the recorded literal "
    "parameter value at each sink",
    ["detector control: deliberately eval one parameter and confirm the canary marker appears, "
     "proving the probe can detect substitution",
     "property test over 300 injection payloads"])

# ---- L28 path-casing (194-199)
add(194, 28, "Case-only duplicate manifest entries are caught at BUILD time",
    "Do two package entries differing only in case get rejected when the package is built, rather "
    "than colliding on the user's case-insensitive filesystem at install time? PASS requires the "
    "build to fail with both paths named.",
    "two independent signals: (a) the packer's exit status and message, and (b) a case-folded "
    "set-size comparison over the manifest paths",
    ["both-states control: a case-distinct-but-non-colliding manifest builds",
     "negative control: deferring the check to install time must fail this test"])

add(195, 28, "Loader lookup casing is exact on Linux and normalized-with-warning on Windows",
    "Does a `Skills/` vs `skills/` reference resolve consistently, and is the platform difference "
    "declared rather than accidental? PASS requires: exact-match failure on Linux, and on Windows "
    "either the same failure or a resolution accompanied by a warning naming the mismatch.",
    "two independent signals: (a) the Linux CI leg's resolution result, and (b) the Windows leg's "
    "result plus its warning stream",
    ["both-states control: correctly-cased references resolve silently on both",
     "cross-OS matrix: the same fixture executed on both legs of one run"],
    timeout=5400)

add(196, 28, "Case-only rename survives the deploy/sync path on Windows",
    "When a tracked file is renamed case-only, does the deploy/sync tool carry the rename without "
    "dropping either side on a case-insensitive filesystem? PASS requires the destination hold "
    "exactly one file with the new casing and the same content hash.",
    "two independent signals: (a) the destination listing with exact casing, and (b) a content "
    "hash comparison against the source blob",
    ["both-states control: a content-changing rename also carries correctly",
     "negative control: a copy loop keyed on lowercased names must fail"],
    substrate="worktree-isolated")

add(197, 28, "Reserved device names do not crash tree enumeration",
    "Does the enumerator survive files named NUL/CON/AUX/PRN/COM1/LPT1 in a scanned tree, using the "
    "extended-length prefix where required? PASS requires a complete count with the reserved entries "
    "reported, never an exception and never a silent zero.",
    "two independent signals: (a) the enumerator's returned count with reserved names present, and "
    "(b) an independent count from a different API (dir listing) over the same tree",
    ["detector control: confirm the enumerator finds a KNOWN-PRESENT ordinary file in the same "
     "tree before trusting any count",
     "regression seed: os.path.relpath raising ValueError on a file named NUL, which would have "
     "zeroed every count in a baseline enumeration"])

add(198, 28, "NFC vs NFD path names match the manifest",
    "Does a macOS-created NFD filename match its NFC manifest entry? PASS requires normalization at "
    "comparison time with the chosen normal form declared, and a cross-platform round trip that "
    "loses no file.",
    "two independent signals: (a) the manifest match result per file, and (b) a byte-level "
    "comparison of the two encodings' code point sequences",
    ["both-states control: pure-ASCII names match trivially",
     "negative control: byte-equality comparison must fail on the NFD fixture"],
    substrate="cloud-batch")

add(199, 28, "Unportable filenames are rejected at publish time",
    "Are trailing-dot, trailing-space, control-character and case-folding-hazard (Turkish dotless i) "
    "filenames rejected before publication? PASS requires rejection at publish with the offending "
    "name and rule quoted.",
    "two independent signals: (a) the publisher's rejection list, and (b) an independent "
    "portability linter over the same file set",
    ["both-states control: a portable name set publishes",
     "corpus test: 40 known-unportable names, each must be individually named in the rejection"])

# ---- L29 long-path (200-205)
add(200, 29, "Install to a >260 character path either works or fails clearly - never truncates",
    "On a Windows host WITHOUT LongPathsEnabled, does install to a deep target produce an actionable "
    "error naming the limit, and never a truncated or partially written tree? PASS forbids any "
    "partially populated destination.",
    "two independent signals: (a) the installer's exit status and message, and (b) a recursive "
    "listing of the destination proving it is either complete or empty",
    ["both-states control: the same install to a short path succeeds",
     "policy note: this unit reads and may require toggling a machine-wide long-path policy, which "
     "is why it is owner-gated"],
    owner=True)

add(201, 29, "Path-length budget is checked BEFORE the first byte is written",
    "Does the artifact writer validate the full resolved path length before opening the file, so a "
    "budget breach cannot leave a partial tree? PASS requires the pre-flight check and zero bytes "
    "written on breach.",
    "two independent signals: (a) the pre-flight check's rejection, and (b) a filesystem scan "
    "showing no created entries under the target root",
    ["both-states control: an in-budget path writes normally",
     "boundary test at limit-1, limit, limit+1 resolved characters"])

add(202, 29, "Length is measured on the RESOLVED path, through junctions and symlinks",
    "When the target is reached through a junction/symlink, is the length budget applied to the "
    "resolved path rather than the short alias? PASS requires the resolved measurement; measuring "
    "the alias is the defect being tested.",
    "two independent signals: (a) the measured length recorded by the writer, and (b) an "
    "independent resolution of the same path by a different API",
    ["both-states control: a direct (non-junction) path of equal resolved length behaves "
     "identically",
     "negative control: measuring the alias must be shown to admit an over-limit write"])

add(203, 29, "Archive extraction with long member names fails closed and cleans up",
    "Does extracting an archive containing over-limit member paths abort and remove the "
    "partially-extracted tree? PASS requires no residue and a message naming the first offending "
    "member.",
    "two independent signals: (a) the extractor's exit and message, and (b) a directory scan of the "
    "extraction root after the failure",
    ["both-states control: an in-limit archive extracts fully",
     "fixture: one archive whose first 40 members are fine and member 41 is over-limit, proving "
     "cleanup of already-written members"])

add(204, 29, "Worktree/id generators bound their own contribution to the path budget",
    "Do generated worktree roots and unit ids have a declared maximum length, so the harness cannot "
    "consume the user's path budget? PASS requires a hard cap enforced in code, not a convention.",
    "two independent signals: (a) the enforced cap in the generator plus a property test over "
    "10,000 generated ids, and (b) the longest observed real path in a full fan-out run",
    ["property test: every generated root length <= declared cap",
     "measurement: report the p100 observed path length from a 256-unit run"])

add(205, 29, "Long-path visibility is consistent across pwsh7, Git Bash and WSL",
    "Is a long path created in one shell visible and writable from the other two, or is the "
    "difference documented as an abstraction leak? PASS requires either parity or an explicit "
    "documented leak with the affected operations enumerated.",
    "two independent signals: (a) per-shell stat/write outcomes for the same path, and (b) the "
    "documented leak table compared against the measured matrix",
    ["both-states control: a short path is visible from all three",
     "matrix: 3 shells x {create, stat, read, write, delete}"],
    timeout=3600)

# ---- L30 secret-leak (206-213)
add(206, 30, "Canary-seeded scan proves no secret enters any produced artifact",
    "With canary tokens planted in the environment and in local config, does a scan of every "
    "produced artifact directory find zero occurrences? PASS requires the scan first PROVE it can "
    "find a planted canary inside an artifact before any zero is trusted.",
    "two independent signals: (a) a pattern scanner over the artifact tree, and (b) an entropy-based "
    "scanner run independently; both must agree",
    ["detector control: plant a canary INSIDE an artifact and confirm both scanners fire",
     "regression seed: credentials or decrypted secrets enter an artifact bundle "
     "(_USER-PROMPTS.md:11345)"])

add(207, 30, "The packer uses an allowlist and a size ceiling, so `.git` and caches cannot ship",
    "Can `.git`, caches, logs, transcripts or unrelated gigabytes enter the distributable? PASS "
    "requires an ALLOWLIST-based packer (a denylist is a FAIL by construction) plus a package size "
    "ceiling that fails the build.",
    "two independent signals: (a) the package member list compared against the allowlist, and "
    "(b) the packaged artifact's size against the declared ceiling",
    ["detector control: add a 200 MB junk file and a `.git` directory to the source tree and confirm "
     "the build fails",
     "regression seed: package accidentally includes `.git` or huge unrelated files "
     "(_USER-PROMPTS.md:11307)"])

add(208, 30, "Redaction operates on parsed structure as well as raw text",
    "Does a secret carried in a STRUCTURED field (`{\"password\": \"...\"}`, a nested token field, "
    "a base64 blob) get redacted, or only ones matching a raw-text regex? PASS requires both paths.",
    "two independent signals: (a) the redacted output for structured payloads, and (b) a "
    "field-by-field walk of the parsed object confirming no sensitive key retains its value",
    ["both-states control: the raw-text form is redacted too (the existing capability must not "
     "regress)",
     "regression seed: a JSON password field bypassing a regex redactor, measured on this estate"])

add(209, 30, "Scrubbing happens at the sink, not per call site",
    "Are secrets scrubbed from error messages, stack traces and telemetry by a single sink-level "
    "scrubber? PASS requires: adding a NEW logging call site with an unscrubbed secret must still "
    "be redacted in the output.",
    "two independent signals: (a) the sink output for a newly added unscrubbed call site, and "
    "(b) a static scan showing no call site performs its own redaction as the only defense",
    ["detector control: add an unscrubbed call site and confirm the sink still redacts",
     "property test over 200 synthetic secret shapes in exception messages"],
    deps_extra=["TST-0206"])

add(210, 30, "Child agent processes inherit only allowlisted environment variables",
    "Does a spawned agent/worker process receive an ALLOWLISTED env set? PASS requires a planted "
    "canary variable to be absent in the child, and the allowlist to be declared in code.",
    "two independent signals: (a) the child's dumped environment (canary absent), and (b) the "
    "static allowlist compared against the observed set",
    ["detector control: add the canary to the allowlist and confirm it DOES appear, proving the "
     "child dump is real",
     "negative control: full inheritance must fail this test"],
    substrate="local-serialized")

add(211, 30, "Secrets in workflow parameters never persist into a resumable checkpoint",
    "Is a credential passed as a workflow parameter excluded from (or encrypted in) the checkpoint, "
    "so resume must re-acquire it? PASS requires the checkpoint bytes contain no plaintext secret "
    "and resume to prompt or fail cleanly without it.",
    "two independent signals: (a) a scan of the checkpoint bytes, and (b) the resume behavior when "
    "the credential source is removed",
    ["both-states control: a non-secret parameter DOES persist and resume uses it",
     "canary: a planted fake credential must be absent from the checkpoint"],
    substrate="local-serialized", deps_extra=["TST-0164"])

add(212, 30, "Masking preserves the zero-entropy prefix and leaks no length information",
    "Does the redactor keep a diagnostic prefix (`sk-`, `ghp_`, `hf_`) while masking the remainder "
    "with a FIXED-WIDTH replacement, so the mask does not reveal the secret's length? PASS requires "
    "identical mask width for secrets of different lengths.",
    "two independent signals: (a) the rendered mask for 5 secrets of differing lengths, and (b) a "
    "byte-length equality assertion across those renders",
    ["both-states control: the prefix is still readable for diagnosis",
     "negative control: a per-character mask must fail the fixed-width assertion"],
    substrate="cloud-batch")

add(213, 30, "No code path in the toolchain can revoke, rotate or unset a credential",
    "Target: prove by static scan plus a runtime guard that the toolchain contains no credential "
    "MUTATION path (revoke/rotate/regenerate/unset/delete) for any provider. PASS requires a "
    "zero-hit scan whose detector is first proven on a planted mutation call, plus a runtime guard "
    "that refuses such a call if one is ever added.",
    "two independent signals: (a) the static scan across all languages in the tree, and (b) the "
    "runtime guard's refusal when a planted mutation is attempted in a test build",
    ["detector control: plant one `revoke_token()` call and confirm the scan fires",
     "policy anchor: AGENTS.md:9 - the owner handles credential lifecycle personally"],
    substrate="local-serialized", who=dict(OPUS, role="security-tester"))

# ---- L31 malicious-plugin (214-221)
add(214, 31, "Permission widening at install requires an explicit owner decision",
    "When an update widens a package's requested permissions, is the DIFF surfaced and the install "
    "halted pending approval? PASS requires the diff name each added permission and the install to "
    "block, not warn.",
    "two independent signals: (a) the installer's halt status and rendered diff, and (b) the "
    "installed package's effective permission set afterward (unchanged)",
    ["both-states control: an identical or narrower permission set installs without a prompt",
     "regression seed: marketplace package has malicious or excessive permissions "
     "(_USER-PROMPTS.md:11346)"])

add(215, 31, "Capability text is DATA: a planted instruction cannot steer the router",
    "Can an injected instruction inside a plugin description / SKILL.md alter capability selection "
    "or tool use? PASS requires identical routing decisions with and without the injected text, "
    "across a fixed task set.",
    "two independent signals: (a) the router's top-k selections for both corpora, and (b) the "
    "executed tool sequence for the same tasks",
    ["detector control: an injection that changes routing MUST be detectable - plant one that "
     "trivially renames a capability and confirm the comparison sees the change",
     "corpus: 30 injection payloads x 20 tasks"],
    deps_extra=["B07"])

add(216, 31, "A cloned repo carrying auto-load agent config is quarantined, not executed",
    "When a checkout contains `.claude/`, `.codex/`, `.mcp.json` or hooks, does the toolchain "
    "quarantine and report them before any agent runs inside it? PASS requires zero hook execution "
    "from the untrusted tree, proven by a canary hook that would write a marker.",
    "two independent signals: (a) absence of the canary marker file, and (b) the quarantine report "
    "enumerating every auto-load surface found",
    ["detector control: run the same canary with quarantine disabled and confirm the marker IS "
     "written, proving the probe can see execution",
     "threat anchor: CVE-2026-47751-class auto-load on clone (AGENTS.md:9)"],
    substrate="local-serialized", owner=True, timeout=3600)

add(217, 31, "Post-install scripts do not execute implicitly",
    "Does installing a package with a post-install script execute it? PASS requires either no "
    "implicit execution at all, or execution inside a sandbox behind an explicit owner gate. Proven "
    "with a benign canary that writes a marker.",
    "two independent signals: (a) the canary marker's absence on the host, and (b) the installer's "
    "declared handling of the script field in its output",
    ["detector control: the same canary must write its marker when run directly, proving the marker "
     "mechanism works",
     "both-states control: with the sandbox gate explicitly enabled, the marker appears only inside "
     "the sandbox"])

add(218, 31, "Typosquat and homoglyph package names are flagged against the installed set",
    "Does the linter flag a candidate name confusable with an installed package (edit distance, "
    "homoglyph folding, hyphen/underscore equivalence)? PASS requires flagging with the confused-with "
    "name reported.",
    "two independent signals: (a) the linter's flags on a crafted corpus, and (b) an independent "
    "confusable-mapping computation over the same names",
    ["both-states control: genuinely distinct names are not flagged (false-positive ceiling stated)",
     "corpus: 50 confusable pairs plus 50 distinct pairs, reporting precision and recall"])

add(219, 31, "Lockfile pins registry origin and integrity, defeating dependency confusion",
    "Can a private package name be satisfied from a public mirror? PASS requires the lockfile to pin "
    "both the registry origin and an integrity hash, and resolution to FAIL when the public mirror "
    "offers a same-named package.",
    "two independent signals: (a) the resolver's refusal and message, and (b) the installed tree "
    "hash proving the public artifact was not used",
    ["both-states control: the legitimate private origin resolves",
     "negative control: a lockfile without an origin pin must fail this test"])

add(220, 31, "Unsigned or wrongly-signed packages fail verification",
    "Does verification reject an unsigned package, a package signed by an untrusted key, and a "
    "package whose content changed after signing? PASS requires all three rejections plus acceptance "
    "of the correctly signed twin.",
    "two independent signals: (a) the verifier's per-case verdict, and (b) an independent "
    "signature check using a different implementation",
    ["both-states control: the valid twin verifies",
     "mutation control: flip one byte in a signed package and confirm rejection"])

add(221, 31, "Revocation is honored at the next health check and removal preserves user data",
    "After a package is revoked upstream, does the next health check flag it, and does removal leave "
    "user data intact? PASS requires the flag to appear without a manual refresh and the user-data "
    "tree to be byte-identical after removal.",
    "two independent signals: (a) the health-check output naming the revoked package, and (b) a "
    "pre/post hash of the user-data tree",
    ["both-states control: a non-revoked package is not flagged",
     "regression seed: rollback removes existing commands or user data "
     "(_USER-PROMPTS.md:11347)"],
    substrate="worktree-isolated")

# ---- L32 permission-boundary (222-228)
add(222, 32, "Declared tool permissions are ENFORCED at runtime, not merely documented",
    "Does a unit declaring `[Read, Grep]` actually fail when it attempts a Write? PASS requires a "
    "runtime denial with a typed permission error; a documented-only restriction is the defect being "
    "tested.",
    "two independent signals: (a) the denied call's error, and (b) a filesystem check proving no "
    "write occurred",
    ["both-states control: a unit declaring Write succeeds at the same call",
     "matrix: every tool in the permission vocabulary tested in both the granted and denied state"])

add(223, 32, "Subworkflow permissions narrow monotonically and can never widen",
    "Can a subworkflow obtain a permission its parent lacks, via nesting, re-entry or a preset? PASS "
    "requires a monotone-narrowing property proven over randomized nesting trees.",
    "two independent signals: (a) the effective permission set computed at each nesting depth, and "
    "(b) an attempted privileged call at the deepest level",
    ["property test: 5,000 randomized nesting trees, asserting child_perms subset of parent_perms",
     "mutation control: allow one widening path and confirm the property fails"])

add(224, 32, "File-scope containment resists prefix escape",
    "Does a unit scoped to `tools/lib/` get denied writes to `tools/libextra/`, `tools/lib/../x`, a "
    "symlink pointing outside, and a case-variant path? PASS requires a real containment check, not "
    "a string StartsWith.",
    "two independent signals: (a) per-case allow/deny verdicts, and (b) a filesystem check after "
    "each attempted write",
    ["both-states control: an in-scope write succeeds",
     "regression seed: the measured StartsWith prefix-escape sibling bug (`tools/libextra` passes a "
     "naive prefix check)"],
    inputs_extra=["tools/lib/workspace.mjs"])

add(225, 32, "A unit declared `network: none` is observably unable to egress",
    "Is the no-network declaration ENFORCED at the substrate (firewall/namespace), not merely "
    "asserted? PASS requires an attempted connection from inside the unit to fail at the network "
    "layer and be logged.",
    "two independent signals: (a) the unit's connection attempt result, and (b) an out-of-band "
    "egress log showing the blocked attempt",
    ["detector control: the same probe must SUCCEED for a unit declaring network access, proving "
     "the probe reaches the network at all",
     "policy note: owner-gated because it manipulates host firewall state"],
    substrate="local-serialized", owner=True, inputs_extra=["tools/lib/net-allowlist.mjs"])

add(226, 32, "An owner-approval gate cannot be satisfied by an agent",
    "Can an agent forge, replay or self-issue an owner approval token? PASS requires the approval "
    "provenance be a channel no agent can write, and replay of a previously valid token for a "
    "different unit must be rejected.",
    "two independent signals: (a) the gate's rejection of a forged and a replayed token, and (b) a "
    "provenance trace of the accepted token's origin channel",
    ["both-states control: a genuine owner approval passes",
     "negative control: a token stored anywhere an agent can write must fail this test"],
    who=dict(CODEX, role="security-tester"))

add(227, 32, "One session cannot write into another session's worktree or artifact root",
    "Is cross-session write containment enforced, given multiple concurrent agent sessions on this "
    "box? PASS requires a denied write plus an alert naming both session ids.",
    "two independent signals: (a) the denial and alert, and (b) a pre/post hash of the victim "
    "session's tree",
    ["both-states control: a write inside the agent's OWN session root succeeds",
     "concurrency: run the probe while a second session is genuinely active"],
    substrate="local-serialized")

add(228, 32, "Revoking a capability mid-run takes effect at the next tool call",
    "When a capability is revoked while a unit is running, does the next tool call fail rather than "
    "the permission being evaluated only at unit start? PASS requires denial within one call of the "
    "revocation.",
    "two independent signals: (a) the timestamped revocation event versus the timestamped denial, "
    "and (b) the unit's own observed error",
    ["both-states control: without revocation the same call succeeds",
     "negative control: start-time-only evaluation must fail this test"])

# ---- L33 benchmark-regression (229-236)
add(229, 33, "Benchmark baselines are content-addressed and cannot be silently rewritten",
    "Can a benchmark run overwrite its own baseline? PASS requires baselines be content-addressed "
    "and immutable, with any change requiring an explicit re-baseline record naming who, when and "
    "why.",
    "two independent signals: (a) the baseline store's hash before and after a full run, and (b) the "
    "re-baseline audit log",
    ["detector control: attempt a silent overwrite and confirm it is refused",
     "both-states control: an explicit re-baseline succeeds and is recorded"])

add(230, 33, "Every benchmark case has a proven non-empty input",
    "Does each benchmark case operate on a non-empty input above a declared floor, so a green cannot "
    "be produced by measuring nothing? PASS requires a per-case input-size assertion plus one "
    "control case with known non-zero work whose timing must be measurably above noise.",
    "two independent signals: (a) per-case input byte/item counts recorded in the result, and (b) the "
    "control case's timing separation from the empty case",
    ["detector control: an intentionally empty case must be FLAGGED, not scored",
     "regression seed: two benchmarks on this estate measured EMPTY inputs and returned a clean, "
     "meaningless green"])

add(231, 33, "The regression gate compares distributions, not single samples",
    "Does the gate require n>=k repetitions and compare median and p95 with a stated variance, "
    "rather than one sample? PASS requires the gate to refuse a verdict when n < k and to report the "
    "spread alongside the point estimate.",
    "two independent signals: (a) the gate's refusal at n<k, and (b) a synthetic dataset with known "
    "distribution where the gate's verdict is checked against the analytic answer",
    ["both-states control: a genuine 20% regression is caught; a 2% noise band is not flagged",
     "false-positive rate measured over 100 no-change runs"],
    deps_extra=["TST-0229"])

add(232, 33, "A holdout set the implementer never sees defeats benchmark gaming",
    "Can a candidate win by special-casing visible fixtures? PASS requires a holdout split never "
    "exposed to implementers, with the gate reporting BOTH scores and failing any candidate whose "
    "visible-vs-holdout gap exceeds a declared threshold.",
    "two independent signals: (a) the visible/holdout score pair, and (b) a provenance check "
    "proving the holdout inputs never appeared in any implementation unit's input list",
    ["detector control: submit a deliberately fixture-overfitted candidate and confirm the gap "
     "detector fires",
     "regression seed: benchmark gaming (_USER-PROMPTS.md:11059)"],
    deps_extra=["TST-0229"])

add(233, 33, "A fused workflow must beat or materially complement EVERY source",
    "Does the acceptance gate reject a fusion that merely has more stages? PASS requires the fused "
    "candidate to beat or materially complement each source on matched cases, with 'more stages' "
    "explicitly non-qualifying and the complementarity claim backed by a case where a source fails "
    "and the fusion succeeds.",
    "two independent signals: (a) per-source matched-case score matrices, and (b) the named "
    "complementarity case executed and shown to differ",
    ["detector control: submit a stage-padded fusion with identical behavior and confirm rejection",
     "regression seed: fused workflow performs worse than every source workflow "
     "(_USER-PROMPTS.md:11333)"],
    deps_extra=["TST-0231", "B04"])

add(234, 33, "Cross-vendor benchmarks are confound-checked before any vendor claim",
    "Are model tier, tool permissions, budgets and prompt transport identical across vendors before "
    "a comparative claim is made? PASS requires an automated confound report; any unequal axis "
    "blocks the comparative verdict.",
    "two independent signals: (a) the confound report's per-axis equality table, and (b) the raw "
    "invocation records for both vendors",
    ["detector control: deliberately downgrade one side's model tier and confirm the confound "
     "report blocks the verdict",
     "regression seed: a measured Claude-vs-Codex comparison was actually sonnet-driver vs "
     "opus-driver"],
    substrate="local-serialized", owner=True, timeout=5400,
    inputs_extra=["rules/common/cross-vendor-dispatch.md:5 (model floor)"])

add(235, 33, "A stored green decays: freshness is stamped and staleness forces a re-run",
    "For any gate whose result depends on a live external source (advisory DB, registry, vendor API), "
    "is the result stamped with its freshness and re-run when stale? PASS requires a stale stored "
    "green to be treated as NOT-CHECKED, never as a pass.",
    "two independent signals: (a) the freshness stamp compared against the staleness policy, and "
    "(b) an observed re-query when the stamp is aged past the threshold",
    ["both-states control: a fresh result is reused without a re-query",
     "regression seed: a stored green from an advisory-DB scan is not a control for today"])

add(236, 33, "The self-improvement loop keeps only measured wins and auto-reverts the rest",
    "Does the retention gate keep a change ONLY on a measured improvement, and automatically revert "
    "neutral or harmful ones? PASS requires all three outcomes exercised (win kept, neutral "
    "reverted, harmful reverted) and the revert proven by a post-revert tree hash.",
    "two independent signals: (a) the gate's decision per candidate, and (b) the working-tree hash "
    "after the decision compared against the pre-candidate hash",
    ["both-states control: a deliberately neutral change must be reverted, not kept",
     "spec anchor: _USER-PROMPTS.md:11135-11150 (no improvement is retained merely because an agent "
     "produced it)"],
    phase="16", deps_extra=["TST-0231", "TST-0235"],
    inputs_extra=[SPEC + ":11135-11150 (Phase 16 self-improvement loop)",
                  "command-center/PHASE-GRAPH.json (Phase 16 has NO allocation bucket; this unit is "
                  "drawn from B08 per the graph's own recommendation)"])

# ---- L34 latency-overhead (237-243)
add(237, 34, "Per-turn harness WALL-CLOCK overhead is attributed per component",
    "How many milliseconds does each harness component (hook dispatch, capability router, rule "
    "injection, ledger write) add to a turn, and is the total under the declared ceiling? PASS "
    "requires a per-component number so a future regression can be attributed to one component. "
    "SCOPE: wall-clock only - context-token cost of routing belongs to TST-0240 and must not be "
    "reported here.",
    "two independent signals: (a) instrumented per-component timings summing to within 5% of the "
    "measured total, and (b) an A/B of end-to-end turn latency with the harness disabled",
    ["both-states control: disabling one component must move BOTH its line item and the total",
     "attribution check: the per-component sum must reconcile with the A/B delta, otherwise the "
     "instrumentation is missing a component"])

add(238, 34, "Render budget is enforced by SPAWN COUNT, measured with a proven shim",
    "How many external process spawns does one cockpit/statusline render perform, and is it under "
    "the ceiling? PASS requires the count come from a PATH shim that is first PROVEN to catch a "
    "known spawn; a text grep of the script is not an acceptable detector.",
    "two independent signals: (a) the shim's spawn log, and (b) an OS-level process-creation trace "
    "over the same render",
    ["detector control: insert a known extra spawn and confirm the shim count increments",
     "regression seed: a slow render is CANCELLED, so spawn count is the real budget"],
    inputs_extra=["rules/common/bash-hud-and-terminal-emit.md:7"])

add(239, 34, "Cold-start versus warm-start latency are both measured and bounded",
    "What is the first-command-after-install latency versus warm, and does the cold path contain an "
    "unbounded index build? PASS requires cold-start under its ceiling on a representative install "
    "size and O(n) behavior characterized, not assumed.",
    "two independent signals: (a) timed cold and warm runs on a clean profile, and (b) a scaling "
    "curve across 3 install sizes",
    ["both-states control: warm start must be measurably faster, proving the measurement "
     "distinguishes them",
     "scaling check: 1x, 4x, 16x installed-capability counts"])

add(240, 34, "Capability routing stays under its context-token ceiling",
    "How many tokens does top-k capability injection add per turn, and does it stay under the "
    "ceiling as the installed capability count grows? PASS requires the injected token count be "
    "measured, not estimated, and be sub-linear in installed capabilities.",
    "two independent signals: (a) a token count of the actual injected block, and (b) the growth "
    "curve across installed-capability counts",
    ["both-states control: adding 50 capabilities must not proportionally grow the injection",
     "spec anchor: _USER-PROMPTS.md:10963 (selects relevant capabilities without flooding context)"],
    substrate="cloud-batch", deps_extra=["B07"])

add(241, 34, "Dispatch cost is amortized O(1) per unit and the ledger write is not O(n)",
    "Does per-unit dispatch cost stay flat as the cohort grows from 16 to 2,048 units, and is the "
    "ledger append O(1) rather than a rewrite? PASS requires a measured flat curve and an "
    "append-only ledger proven by write-size instrumentation.",
    "two independent signals: (a) per-unit dispatch time across cohort sizes, and (b) bytes written "
    "per ledger append at each size",
    ["scaling test: 16, 64, 256, 1024, 2048 units",
     "detector control: a deliberately O(n) ledger write must show the quadratic curve"],
    substrate="cloud-batch", timeout=5400)

add(242, 34, "Process and memory ceilings hold, and the guard never kills a shared service",
    "Does the harness bound per-session MCP/worker process multiplication, and can its memory guard "
    "ever terminate a live shared service? PASS requires the ceiling to hold under a 10x fan-out AND "
    "the guard to be proven incapable of selecting a shared-service PID.",
    "two independent signals: (a) peak process count and committed memory sampled by an external "
    "monitor, and (b) the guard's candidate-selection list audited against the shared-service PID "
    "set",
    ["detector control: present the guard with a shared-service PID and confirm it refuses",
     "regression seeds: eager per-session MCP process multiplication; commit exhaustion freezes "
     "process creation; kill-based memory guard terminates a live shared service "
     "(_USER-PROMPTS.md:11326-11328)"],
    owner=True, timeout=5400)

add(243, 34, "Declared timeouts exceed measured p99 by a stated margin",
    "For each unit class, is `timeout_seconds` greater than the measured p99 duration by the declared "
    "margin? PASS requires the comparison be computed per class; any class whose p99 exceeds its "
    "timeout is reported as a catalog defect with the proposed new value.",
    "two independent signals: (a) the measured duration distribution per class, and (b) the catalog's "
    "declared timeout per class, joined mechanically",
    ["mechanical join: computed by script over the catalog and the run ledger, never eyeballed",
     "both-states control: an artificially short timeout on one class must be reported"],
    deps_extra=["TST-0237"])

# ---- L35 accessibility-ux (244-249)
add(244, 35, "Every failure class emits an actionable message (what, why, next command)",
    "Does each entry in the failure taxonomy produce a message naming what failed, why, and the "
    "exact next command? PASS requires full taxonomy coverage; a bare stack trace or an error with "
    "no next action is a FAIL.",
    "two independent signals: (a) a taxonomy-to-message coverage matrix generated by triggering each "
    "class, and (b) a rubric score of each message against the three required parts",
    ["coverage: every failure class in the taxonomy must be triggered, not sampled",
     "negative control: a deliberately bare error must score zero"],
    substrate="cloud-batch")

add(245, 35, "Every colour-coded signal also carries a glyph or text token",
    "Under NO_COLOR, a monochrome terminal and a simulated colour-vision deficiency, is every "
    "coded signal still distinguishable? PASS requires each coloured element carry a non-colour "
    "token.",
    "two independent signals: (a) the NO_COLOR rendering compared against the coloured one after "
    "stripping SGR, and (b) an enumeration of coded elements to their non-colour token",
    ["both-states control: a threshold breach must remain visible in NO_COLOR",
     "regression seed: colour is a scarce channel and must be capped and paired with a glyph"])

add(246, 35, "No double-width or ambiguous glyph appears in fixed-width output",
    "Does any fixed-width output line contain an emoji-presentation or East-Asian-ambiguous glyph "
    "that breaks alignment? PASS requires a zero-hit scan whose detector is proven on a planted "
    "width-2 character, plus a rendered-width assertion.",
    "two independent signals: (a) a codepoint-class scan of the output, and (b) a measured rendered "
    "column count in a real terminal",
    ["detector control: plant a known width-2 glyph and confirm the scan fires",
     "regression seed: U+26A0 renders width-2 on Windows Terminal and overlapped its neighbour"])

add(247, 35, "A plain-text mode carries the same information as the TUI",
    "Does `--plain` (screen-reader friendly, no cursor addressing) expose the same information set "
    "as the interactive cockpit? PASS requires a field-level set comparison, not a visual "
    "impression.",
    "two independent signals: (a) the field set parsed from the plain output, and (b) the field set "
    "rendered by the TUI panes, compared mechanically",
    ["both-states control: hiding a field from the TUI must show up as a set difference",
     "assistive check: the plain output is line-oriented with no cursor-addressing escapes"])

add(248, 35, "Non-interactive mode never blocks on stdin",
    "Does every command complete or fail without stdin when run non-interactively? PASS requires no "
    "prompt, no hang, and a non-zero exit with an actionable message where input was required.",
    "two independent signals: (a) each command run with stdin attached to the null device, and "
    "(b) a wall-clock bound proving no command waited",
    ["coverage: every command in the CLI surface, enumerated from the parser, not from docs",
     "detector control: a deliberately prompting command must be caught by the hang bound"])

add(249, 35, "UTF-8 output survives a legacy code-page console",
    "Does user-facing output containing non-ASCII crash or mojibake on a cp1252 console? PASS "
    "requires no exception and a legible fallback, with the chosen fallback declared.",
    "two independent signals: (a) the process exit status on a cp1252 console, and (b) a byte-level "
    "capture of the emitted output",
    ["both-states control: the same output on a UTF-8 console is byte-exact",
     "regression seed: a UnicodeDecodeError from the default cp1252 codec, reproduced on this box "
     "while reading a UTF-8 catalog"])

# ---- L36 documentation-command (250-256)
add(250, 36, "Every documented command is executed verbatim in a clean room and must exit 0",
    "Are all commands in README and quick-start extracted and executed in a fresh environment with "
    "the published artifact? PASS requires 100% of extracted commands run, each exit code recorded, "
    "and any non-zero either fixed or documented as expected-failure with its reason.",
    "two independent signals: (a) the per-command exit codes from the clean-room run, and (b) an "
    "extraction audit proving the extractor found every fenced command (count matched against a "
    "manual count of one document)",
    ["detector control: plant a deliberately broken command and confirm the harness fails",
     "clean room: fresh container/profile with only the published artifact installed"],
    timeout=5400)

add(251, 36, "Documented flags and implemented flags are the same set, both directions",
    "Is every documented CLI flag implemented, and every implemented flag documented? PASS requires "
    "a bidirectional set difference computed from the parser definition and the docs, with both "
    "difference sets empty or explicitly waived.",
    "two independent signals: (a) the flag set extracted from the argument parser at runtime, and "
    "(b) the flag set extracted from the docs, diffed mechanically",
    ["mechanical diff: computed by script, never eyeballed",
     "detector control: remove one flag from the docs and confirm the diff reports it"],
    deps_extra=["TST-0250"])

add(252, 36, "A WRONG documented recipe is caught: the git-archive CRLF trap",
    "Does the docs-verification harness catch a recipe that RUNS successfully but returns the wrong "
    "bytes? Concretely: `git archive | tar -x` returns CRLF worktree bytes on Windows, not the LF "
    "blob, so any recipe telling a reader to verify formatting that way is wrong. PASS requires the "
    "harness to compare each recipe's OUTPUT against the authoritative source, not just its exit "
    "code.",
    "two independent signals: (a) byte and CRLF counts from the documented recipe, and (b) the same "
    "file obtained via `git cat-file -p <rev>:<path>`; a difference that is purely line endings must "
    "be shown by an LF-normalised control to be exactly that",
    ["both-states control: the `git cat-file` recipe must pass while the `git archive` recipe fails",
     "regression seed: command-center/RELEASE-CHECKLIST.md prescribes the git-archive route for the "
     "very CRLF trap that makes its own gates red"],
    inputs_extra=["command-center/RELEASE-CHECKLIST.md",
                  "rules/common/windows-shell.md:8b"])

add(253, 36, "Every runbook step has a machine-checkable postcondition and the rollback rehearses",
    "Does each RUNBOOK step declare a postcondition a script can verify, and does the rollback "
    "procedure run end to end? PASS requires zero steps whose only success criterion is prose, and a "
    "completed rollback rehearsal.",
    "two independent signals: (a) a per-step postcondition coverage table, and (b) the rollback "
    "rehearsal's own postcondition probes",
    ["coverage: every step in RUNBOOK.md and ROLLBACK-MANIFEST.md",
     "both-states control: a deliberately broken step must fail its postcondition"],
    substrate="local-serialized",
    inputs_extra=["command-center/RUNBOOK.md", "command-center/ROLLBACK-MANIFEST.md"])

add(254, 36, "Fenced workflow examples in docs are schema-valid and executable",
    "Does every workflow example embedded in documentation parse against the CURRENT workflow schema "
    "and execute in dry-run? PASS requires both; a doc example that no longer validates is a drift "
    "defect, not a cosmetic issue.",
    "two independent signals: (a) schema validation per example, and (b) a dry-run execution result "
    "per example",
    ["detector control: bump the schema in a scratch copy and confirm stale examples are reported",
     "coverage: every fenced block tagged as a workflow across the docs tree"],
    deps_extra=["B06"])

add(255, 36, "Internal anchors and external links resolve, with offline distinguished from wrong",
    "Do all internal `file:line` anchors and external URLs in the documentation resolve? PASS "
    "requires internal anchors verified against the repository at the documented revision, and "
    "external links to distinguish UNREACHABLE (offline/transient) from WRONG (404/410) - never "
    "folding the first into the second.",
    "two independent signals: (a) internal anchor resolution via `git cat-file -p <rev>:<path>` plus "
    "a line-count check, and (b) external status codes with a retry policy and an explicit "
    "offline classification",
    ["both-states control: a deliberately off-by-1000 line anchor must be reported",
     "detector control: run the external checker with egress blocked and confirm it reports "
     "UNREACHABLE, not 404"])

add(256, 36, "The migration guide actually converts a real old-layout fixture, idempotently",
    "Does the documented old-to-new migration, run verbatim against a genuine old-layout fixture, "
    "produce the expected new layout - and produce no further change on a second run? PASS requires "
    "both the conversion and the idempotence.",
    "two independent signals: (a) a tree diff of the migrated fixture against the expected layout, "
    "and (b) a byte-identical tree hash after a second migration run",
    ["both-states control: an already-migrated tree is a no-op",
     "fixture provenance: the old-layout fixture must be captured from a real prior release, not "
     "synthesized from the migration script"],
    substrate="worktree-isolated")


# ------------------------------------------------------------------- expansion
def build():
    out = []
    seen = set()
    for (n, layer, title, q, ev, tests, ov) in U:
        d = L[layer]
        uid = "TST-%04d" % n
        assert uid not in seen, "duplicate id " + uid
        seen.add(uid)
        who = ov.get("who", d["who"])
        inputs = list(d["inputs"]) + list(ov.get("inputs_extra", []))
        deps = list(d["deps"]) + list(ov.get("deps_extra", []))
        rec = {
            "id": uid,
            "title": title,
            "phase": ov.get("phase", "10"),
            "question_or_target": q,
            "inputs": inputs,
            "dependencies": deps,
            "assigned_model_vendor_role": {
                "vendor": who["vendor"],
                "model": who["model"],
                "role": who["role"],
            },
            "tool_permissions": ov.get("tools", list(d["tools"])),
            "execution_substrate": ov.get("substrate", d["substrate"]),
            "timeout_seconds": ov.get("timeout", d["timeout"]),
            "output_path": "command-center/receipts/%s.json" % uid,
            "output_schema": sch(ov.get("frag", d["frag"])),
            "evidence_requirement": ev,
            "tests_required": tests,
            "reviewer_requirement": ov.get("rev", d["rev"]),
            "completion_sentinel": "SUCCESS:" + uid,
            "retry_policy": ov.get("retry", d["retry"]),
            "failure_classification": ov.get("fails", list(d["fails"])),
            "owner_approval_required": bool(ov.get("owner", False)),
        }
        out.append(rec)
    return out


def main():
    units = build()
    ids = [u["id"] for u in units]
    assert len(ids) == len(set(ids))
    expected = ["TST-%04d" % i for i in range(129, 129 + len(units))]
    assert ids == expected, "ids not sequential from 129"
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(units, fh, indent=2, ensure_ascii=True, sort_keys=False)
        fh.write("\n")
    print("WROTE", OUT, len(units), ids[0], ids[-1])


if __name__ == "__main__":
    main()
