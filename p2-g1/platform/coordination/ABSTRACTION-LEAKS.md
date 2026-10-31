# Abstraction leaks in the cross-vendor coordination layer

**Spec requirement:** `_USER-PROMPTS.md:10981` — *"explicit documentation of abstraction leaks"*, and
`:10983` — *"Do not pretend full interchangeability where tools, context, or permissions differ.
Degrade loudly and preserve the work artifact."*

A leak here means: **a detail of one layer that the layer above cannot hide, so the abstraction
lies unless the detail is written down and enforced.** Each entry names the leak, the mechanism
that makes it LOUD instead of silent, the test that proves the mechanism works, and — where the
leak is not closed — the experiment that would settle it.

`test_docs.py` asserts that every `L-nn` id referenced anywhere in the package source appears here
and vice versa, so this file cannot drift away from the code.

---

## L-01 — Transport detachment leaks into prompt delivery

**The leak.** `longrun` (and any `run_in_background` transport) **detaches the child process**, and a
detached child does not inherit stdin. So `codex exec … - < prompt.txt` written at the wrapper's
call site never receives the prompt and dies with *"No prompt provided via stdin."*
(`C:/Users/Prekzursil/.claude/agents/codex.md:52-55`.)

An adapter API that exposes "send the prompt on stdin" as a capability is therefore lying whenever
the transport detaches. The capability is real; its availability is a property of the TRANSPORT, not
of the vendor.

**Why it cannot be hidden.** The layer that chooses detachment (dispatch policy, driven by
AGENTS.md §4a's 60-second rule) is above the layer that delivers the prompt. Any wrapper that both
backgrounds and redirects has already lost stdin by the time the redirect is evaluated.

**Made loud by.** `dispatch.audit_plan` violation `V-04-stdin-under-detach`, and
`CAPABILITY-REGISTRY.json` marks `stdin.prompt` DEGRADABLE with the fallback named
(`prompt.file_argument` / a runner script that owns the redirect).

**Proven by.** `test_dispatch.py::test_stdin_redirect_under_a_detached_transport_is_rejected`, plus
`::test_stdin_redirect_in_the_foreground_is_allowed` — the leak is scoped to detachment, not to
stdin, and a rule that fired in both cases would be wrong in the second.

---

## L-02 — The wrapper's exit-code plumbing leaks into the runner script's last line

**The leak.** Because the prompt must move into a runner script (L-01), the adapter contract now
constrains **shell script text**, not just an argv. And a runner script's last statement is
load-bearing: a trailing bare `echo` overwrites `$?`, which once masked a codex **exit 1** as
`SUCCESS` in 7 s with no output file — the exact severed-stream signature the AND-gate exists to
catch (`codex.md:56-58`).

**Why it cannot be hidden.** `$?` is a shell global. No wrapper API can protect a script from its
own final command.

**Made loud by.** `V-10-runner-trailing-echo`. The contract is `rc=$?; …; exit "$rc"`.

**Proven by.** `test_dispatch.py::test_runner_ending_in_a_bare_echo_is_rejected`,
`::test_runner_without_an_explicit_exit_is_rejected`,
`::test_runner_with_rc_capture_and_exit_passes` (the negative control — an `echo` BEFORE the `exit`
is fine), and `::test_comments_after_the_exit_do_not_defeat_the_check`.

---

## L-03 — Two individually-available capabilities are mutually exclusive in practice

**The leak.** On `codex-cli`, an active MCP inventory **voids** `--output-schema` (codex issue
#15451), and the inventory is also what blows the 32,767-char Windows command-line limit. So
`--ignore-user-config` is mandatory for the typed-output path — and it removes the MCP tools.

A capability model that answers "is `schema.typed_output` available?" and "is `mcp.tools`
available?" independently returns **yes** to both and is wrong about the conjunction.

**Why it cannot be hidden.** The interaction lives in the vendor's runtime, not in the model.

**Made loud by.** `capability.MUTUALLY_EXCLUSIVE` — a data table, not branches — and a negotiation
verdict of `REFUSED` with the conflict named when a unit asks for both. Not a silent pick-one.

**Proven by.** `test_capability.py::test_mutually_exclusive_pair_is_refused_not_silently_resolved`.

---

## L-04 — A permission flag exists, is accepted, and does nothing

**The leak.** `--sandbox workspace-write` is **INERT** on codex-cli 0.144.5 / Windows: `-s`,
`-c sandbox_mode` and `--full-auto` all still print `sandbox: read-only` and the write is
auto-rejected "blocked by policy" (`codex.md:44-50`). The invocation that actually works is
`--dangerously-bypass-approvals-and-sandbox`.

Consequence stated plainly: **containment is verified post-hoc by the caller, not enforced by the
runtime.** The API surface suggests otherwise.

**Why it cannot be hidden.** A confinement guarantee cannot be synthesised by the layer above the
thing that fails to confine. Scoping the WORKDIR tightly and auditing what was written afterwards is
a mitigation, not the guarantee.

**Made loud by.** `ADAPTER-REGISTRY.json` puts `sandbox.enforced` in `refuses` for BOTH real
adapters (Windows has no native OS-level process sandbox for `claude-code` either), the capability
is DEGRADABLE with the post-hoc-verification note, and `V-12-inert-sandbox-flag` rejects a plan that
relies on the flag.

**Proven by.** `test_adapters.py::test_both_real_adapters_refuse_enforced_sandbox_and_that_only_degrades`
and `test_dispatch.py::test_inert_sandbox_flag_is_rejected_for_codex`.

---

## L-05 — File leases are ADVISORY, and the API reads like a lock

**The leak.** A lease coordinates **cooperating** agents that use this store. It does not stop a
non-participating writer: the owner's editor, a sibling agent that does not consult the store, a
`git checkout`, or a formatter can all write a leased path.

**Why it cannot be hidden.** Enforcement would need a mandatory OS lock on every leased file for the
lease's whole duration, which would break every non-participating tool including git.

**Made loud by.** Named in `leases.py`'s module docstring and here. The word "advisory" is in the
API documentation, not implied.

**Not closed.** The experiment that would settle whether it matters: instrument the working tree
during a multi-agent wave and count writes to leased paths by non-participants. **NOT-CHECKED** by
this unit.

---

## L-06 — The OS liveness lock is a fact about the LOCAL kernel only

**The leak.** Signal B (the advisory lock) is released by the operating system of the machine that
ran the holder. If a coordination store lives on a network share and a session was registered on
another host, this host's kernel never saw that lock — so acquiring it would wrongly read as
`FREE` (= DEAD) and reap a live remote session.

**Why it cannot be hidden.** A cross-host liveness signal needs a different mechanism entirely
(a lease server, a heartbeat with a quorum). The filesystem does not provide one.

**Closed, by refusing to answer.** `session.classify` compares `record.host` to
`socket.gethostname()` and returns `UNVERIFIED` — *"signal B is inadmissible and no second signal
exists"* — for any foreign-host record. Recovery then refuses to reap it without an explicit force.

**Proven by.** `test_session.py::test_a_session_from_another_host_is_unverified_never_reaped`.

---

## L-07 — Case sensitivity is a filesystem property, not a path property

**The leak.** `normalize_lease_path` case-folds on win32 and darwin so `a/B.py` and `A\b.py`
collide (they are the same file there), and does NOT fold on Linux (they are different files
there). A store written on one platform and read on another would fold differently, so one file
could acquire two distinct lease keys.

**Made loud by.** Every lease records its `root`, and the folding rule is documented at the
function.

**Not closed.** Single-host, single-platform stores are the only measured configuration. The
experiment that would settle it: create a store on Windows, read it from WSL, and check whether any
two lease keys normalise to the same path. **NOT-CHECKED** by this unit.

---

## L-08 — Claim takeover is read-then-write, not compare-and-swap

**The leak.** `create_exclusive` (`O_CREAT | O_EXCL`) makes the FIRST claim on a unit atomic. Taking
over an already-existing (vacant) claim cannot use it, so two sessions could in principle both take
over the same abandoned claim.

**Bounded, not eliminated.** Takeover requires `takeover=True` (never implicit), both takeovers
appear in the journal, and the cost is duplicated EFFORT rather than corruption — file leases, not
claims, are the mutual exclusion for bytes on disk.

**Not closed.** Closing it needs a compare-and-swap primitive the filesystem does not offer for an
existing file. The experiment: a concurrency harness with N sessions racing one abandoned claim.
**NOT-CHECKED** by this unit.

---

## L-09 — A handoff can invalidate a cross-vendor review that was already valid

**The leak.** Predicate condition 9 requires an independent reviewer of a **different** vendor. A
unit reviewed cross-vendor and then handed to a session of the REVIEWER's vendor is now
same-vendor, and the earlier review no longer satisfies the condition — but nothing about the
handoff itself is invalid.

**Made loud by.** `accept_handoff` records `vendor_comparison` (canonical, three-valued, from
`vendor_identity.compare`) on the handoff record and in the journal, so the reducer's later verdict
is explainable rather than surprising. The reducer is deliberately NOT re-run automatically: that
is the caller's decision, and silently re-running it would be a second control plane.

**Proven by.** `test_handoff.py::test_accept_records_the_vendor_change_canonically` and
`::test_same_vendor_handoff_is_recorded_as_same_vendor`.

---

## L-10 — `COMPLETED` on a claim is not a completion verdict

**The leak.** `complete_claim` records that a session **asserts** it finished, and stores the
receipt path. Whether the unit is COMPLETE is decided only by the shared reducer
(`platform/lib/completion_predicate.py`, twelve conditions). Two vocabularies use the same English
word for different things, which is exactly how a self-certifying receipt gets believed.

**Made loud by.** `complete_claim`'s docstring says the verdict belongs to the reducer;
`reduce_claim` is the only path to a verdict; and `reducer.assert_single_reducer` fails if anything
in this package grows its own.

**Proven by.** `test_reducer.py::test_the_reducer_is_the_delegate_by_object_identity`,
`::test_not_checked_stays_not_checked_and_blocks`, and the both-states detector tests.

---

## L-11 — A BLOCKED unit has no legal catalog disposition (OWNER DECISION)

**The leak.** `platform/schema/receipt.schema.json` defines `terminal_state` with seven values
including `BLOCKED`, but `disposition` (the CATALOG row outcome) has exactly three:
`DONE-VERIFIED`, `DROPPED-BY-OWNER`, `SUPERSEDED`. The degrade-loudly path produces
`terminal_state = BLOCKED` — and there is **no disposition that means "this adapter cannot do
this"**.

So a loudly-degraded unit is representable on the receipt plane and NOT representable on the
catalog plane. The available choices are all wrong: `DROPPED-BY-OWNER` attributes the decision to
the owner, and `SUPERSEDED` implies a replacement that may not exist.

**Not closed, and not closeable here.** Adding a disposition value is a change to the catalog
contract, which is not this unit's surface. Surfaced as an owner decision rather than silently
mapped to the least-wrong value. The mapping this unit uses instead: `DegradedOutcome` carries no
`disposition` field at all, so nothing is fabricated.

---

## L-12 — The POSIX branch of the liveness lock is unmeasured

**The leak.** `oslock` uses `msvcrt.locking` on win32 and `fcntl.flock` on POSIX. Only the win32
branch is exercised: the both-states control and `test_oslock.py` run on this box, which is
Windows 11 / CPython 3.14.

**Stated, not assumed.** `oslock`'s docstring marks the POSIX branch **NOT-CHECKED** and names the
settling experiment: run `liveness_control.py` under WSL or a Linux CI runner and require
`all_discriminate: true` there too.

There is a real semantic difference to watch for, which is why an assumption would be unsafe:
`flock` locks are associated with the open FILE DESCRIPTION and are released when the last
descriptor closes, whereas `msvcrt.locking` locks byte ranges of the file for the process. Both
release on process exit, which is the property this design depends on — but only one of them has
been observed doing so here.
