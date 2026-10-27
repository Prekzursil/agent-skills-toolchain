# -*- coding: utf-8 -*-
"""BLD bucket (completeness and blind-spot, B11) - units 1..32.

Each entry is a dict consumed by _bld_build.py, which expands it into the
19 contract fields used by every existing catalog slice.

Spec anchor for the bucket: _USER-PROMPTS.md:10564 (64 completeness and
blind-spot units) and :11066-11082 (Phase 13, the eleven questions).
"""

SPEC = "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"

UNITS_1 = [
dict(
    n=1, q="files-never-read",
    title="Never-read file census derived from the transcript read-ledger",
    target=(
        "Question: which files inside the program's declared scope did NO agent ever open? "
        "Build a read-ledger by extracting every Read/Grep/Glob/Bash-cat tool_use input path from the "
        "session JSONL transcripts for the whole Prompt Two program, normalise each to a repo-relative "
        "path, and set-difference the ledger against `git ls-files` at the program HEAD. Emit an "
        "unread-file register carrying a criticality weight (executable > schema > CI config > doc > "
        "fixture) and a per-file reason code (out-of-scope | never-routed | oversized | unreadable-form)."
    ),
    inputs=[
        "~/.claude/projects/**/*.jsonl (session + subagent transcripts for this program)",
        "`git ls-files` at the program HEAD of C:/Users/Prekzursil/source/ast-integrate",
        "command-center/ARTIFACT-MANIFEST.json",
        "command-center/PROGRAM-CHARTER.md (the declared scope statement)",
    ],
    deps=["B01", "B02"],
    role="corpus-cartographer",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="local-serialized",
    to=7200,
    schema="blindspot-register",
    ev=(
        "Cite the exact transcript glob and the number of tool_use records parsed. The extractor script "
        "path and its sha256 go in the receipt so the ledger is reproducible. DETECTOR CONTROL IS "
        "MANDATORY: seed one KNOWN-READ file (any path cited file:line by an existing receipt) and prove "
        "it is absent from the unread set, and seed one KNOWN-UNREAD sentinel path and prove it appears. "
        "A low or zero unread count with no control is a detector failure, not a clean bill."
    ),
    tests=[
        "Control (known-present): a file cited file:line in an existing receipt must NOT appear in the unread set.",
        "Control (known-absent): a planted sentinel path present in git but touched by nobody must appear in the unread set.",
        "Path-form collapse: the same file reached as C:/..., /c/..., .\\rel\\path and repo-relative must produce exactly ONE ledger entry.",
        "Determinism: two runs over the same frozen transcript set must emit byte-identical registers.",
    ],
    rev=(
        "One independent reviewer who re-derives the unread count with a mechanically different extractor "
        "(jq over the JSONL rather than the Python parser) and must agree within 1% or the discrepancy blocks."
    ),
    retry=(
        "No blind retry: re-running the same extractor is not a second signal. A disagreeing second extractor "
        "is a detector defect - fix and re-run once; a second disagreement escalates with both outputs attached."
    ),
    fc=["detector-failure", "single-signal", "use-vs-mention", "non-portable"],
),
dict(
    n=2, q="files-never-read",
    title="Unreachable-code census by import-graph reachability from declared entry points",
    target=(
        "Question: which shipped modules and public functions are unreachable from ANY declared entry "
        "point? Build a static import/call graph over the shipped package, mark entry points from the "
        "plugin manifest commands, the hook manifest registrations, the MCP tool exports, the workflow "
        "stage registry and the CI invocation lines, compute reachability, and emit the unreachable set. "
        "This is orthogonal to line coverage: code can be imported and covered by a test yet be reachable "
        "from no user-facing entry point at all."
    ),
    inputs=[
        "the shipped package tree produced by B07",
        "plugin manifest + hook manifest + MCP tool registrations (entry-point declarations)",
        "the CI workflow files (the commands CI actually invokes)",
        "coverage.xml from the B08 suite run (for the covered-but-unreachable cross-check)",
    ],
    deps=["B02", "B07"],
    role="graph-engineer",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="reachability-report",
    ev=(
        "State the entry-point set explicitly and cite each source at file:line - an incomplete entry-point "
        "set manufactures false unreachability, which is the dangerous direction here (it invites deletion). "
        "Every unreachable verdict must survive a dynamic-import search (importlib, __import__, entry_points, "
        "plugin discovery by glob) before it is reported."
    ),
    tests=[
        "Control: a deliberately orphaned module planted in a scratch copy must be reported unreachable.",
        "Control (false-positive guard): a module reachable ONLY through a hook manifest entry must NOT be reported - this proves the entry-point set includes hooks.",
        "Control (dynamic import): a module loaded only via importlib.import_module(name_from_config) must NOT be reported unreachable.",
        "Cross-check: every file that is covered by tests but unreachable from an entry point must be individually explained in the register.",
    ],
    rev="One independent reviewer who attempts to reach three sampled 'unreachable' symbols from a real CLI invocation before sign-off.",
    retry="Two strikes then pivot: a second false-positive class means the graph builder is wrong; switch to a runtime import-trace before a third static attempt.",
    fc=["detector-failure", "data-loss-risk", "overclaim"],
),
dict(
    n=3, q="files-never-read",
    title="Structurally unreadable surface census: binary, encrypted, oversized and OS-hostile paths",
    target=(
        "Question: what part of the corpus is the text pipeline STRUCTURALLY blind to - content no agent "
        "could read even in principle? Enumerate by class: non-UTF8-decodable binaries, git-crypt/age "
        "encrypted blobs, single files above the read cap, paths containing a Windows reserved device name "
        "(NUL/CON/AUX/PRN/COM1/LPT1) that require the \\\\?\\ extended-length prefix, paths over 260 "
        "characters, and files present on disk but excluded by .gitignore. For each class, state what "
        "evidence would be needed to cover it and list every current program claim that depends on its content."
    ),
    inputs=[
        "the full repo working tree plus the deployed live trees in scope",
        ".gitattributes and .gitignore",
        "the git-crypt / encrypted-path list",
        "command-center/CLAIM-REGISTRY.json (to find claims resting on unreadable content)",
    ],
    deps=["B01", "B02"],
    role="corpus-cartographer",
    perms=["Read", "Grep", "Glob", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=5400,
    schema="blindspot-register",
    ev=(
        "The enumerator must survive the OS-hostile classes it is counting. Measured precedent: a Phase-0 "
        "enumerator CRASHED with `ValueError: path is on mount '\\\\.\\NUL'` because os.path.relpath cannot "
        "handle a file literally named NUL, and a swallowed crash would have reported every count as 0 and "
        "read as 'the trees are empty'. The receipt must show the enumerator completing over a fixture "
        "containing each hostile class."
    ),
    tests=[
        "Fixture: a scratch directory containing a reserved-device-name file, a >260-char path and a non-UTF8 blob must be enumerated without an exception.",
        "Classification: a git-crypt encrypted file must classify ENCRYPTED, not BINARY.",
        "Control: a plain UTF-8 markdown file planted in the fixture must NOT appear in any unreadable class.",
        "Crash-visibility: an induced enumerator exception must fail the unit loudly, never produce a zero count.",
    ],
    rev="One independent reviewer who re-runs the enumerator from PowerShell 7 rather than Git Bash and compares class counts.",
    retry="Retry once after a crash ONLY with the crash fixed and the fixture extended to cover the crashing class; never retry with the exception suppressed.",
    fc=["detector-failure", "non-portable", "data-loss-risk"],
),
dict(
    n=4, q="files-never-read",
    title="Docs-vs-code parity by bidirectional identifier set-difference",
    target=(
        "Question: which documented behaviour has no implementing code, and which shipped behaviour is "
        "undocumented? Extract the identifier space from every shipped document (command names, CLI flags, "
        "tool names, config keys, workflow ids, council preset ids, hook event names, schema field names) "
        "and independently from code definition sites, then emit BOTH set differences. Stopping condition 12 "
        "('docs and code agree') is not satisfiable without this measurement existing as a number."
    ),
    inputs=[
        "all shipped documentation (README, RUNBOOK.md, docs/**, skill SKILL.md files, marketplace listing copy)",
        "code definition sites (argparse/click declarations, command registries, hook manifests, schema files)",
        "command-center/RELEASE-CHECKLIST.md (which docs are release-blocking)",
    ],
    deps=["B05", "B07"],
    role="docs-conformance-tester",
    vendor="openai",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="cloud-batch",
    to=5400,
    schema="parity-matrix",
    ev=(
        "Both directions must be reported with counts, not just the doc-ahead direction. Every DOCUMENTED-BUT-"
        "ABSENT finding cites the doc line and the search that failed to find an implementation; every "
        "UNDOCUMENTED finding cites the definition site."
    ),
    tests=[
        "Use-vs-mention control: a flag documented inside a 'removed in v2' or 'example of what not to do' block must NOT count as a live documentation claim.",
        "Control: a flag planted in code with no doc mention must appear in the undocumented set.",
        "Control: a command documented but deleted from code must appear in the documented-but-absent set.",
        "Negative control: a command that is both documented and implemented must appear in neither set.",
    ],
    rev="Cross-vendor: the Claude corpus authored both the docs and the code, so the parity read is assigned to an independent OpenAI-vendor agent and reviewed by an Anthropic-vendor reviewer.",
    retry="Two strikes then pivot from regex extraction to an AST/manifest-parse extraction before a third attempt.",
    fc=["use-vs-mention", "overclaim", "detector-failure"],
),
dict(
    n=5, q="files-never-read",
    title="Orphan configuration keys and undeclared runtime knobs",
    target=(
        "Question: which configuration key does the product declare but never read, and which key does code "
        "read that no shipped config or schema declares? Cross the union of the declared key space (plugin "
        "manifest, marketplace manifest, settings schema, workflow presets, .coverage-thresholds.json where "
        "present) against every configuration read site (os.environ.get, cfg[...], settings.get, argparse "
        "dest, Get-ItemProperty) and emit both orphan sets."
    ),
    inputs=[
        "every shipped manifest and settings schema",
        "every configuration read call site in the shipped code",
        "the default values block of WORK-UNIT-CATALOG.json (a live example of a declared-but-unoverridden key space)",
    ],
    deps=["B04", "B07"],
    role="contract-author",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="local-parallel",
    to=3600,
    schema="parity-matrix",
    ev="Each finding cites the declaration site and the (absent) read site, or the read site and the (absent) declaration. A key read only from a test fixture is classified FIXTURE-ONLY and reported separately from a product orphan.",
    tests=[
        "Control: an unused key planted in the manifest must be reported as an orphan.",
        "Control: a getenv of an undeclared variable planted in code must be reported as an undeclared knob.",
        "Classification control: a key read only inside tests must classify FIXTURE-ONLY, not product-orphan.",
        "Negative control: a declared key with a real read site must appear in neither set.",
    ],
    rev="One independent reviewer who samples five orphan verdicts and greps the whole tree (including non-Python callers such as PowerShell and YAML) for a read site before sign-off.",
    retry="Two strikes then pivot: if the read-site grep misses non-Python consumers twice, switch to a whole-tree token scan.",
    fc=["detector-failure", "use-vs-mention", "overclaim"],
),
dict(
    n=6, q="clients-never-tested",
    title="Host-client coverage matrix with a version-stamped evidence anchor per cell",
    target=(
        "Question: which supported host client was never exercised end-to-end? Enumerate the declared client "
        "set (Claude Code, Codex CLI, Antigravity/agy, and any generic MCP host named in the compatibility "
        "matrix) crossed with the conformance suite, and mark every cell RUN / NEVER-RUN / NOT-APPLICABLE. A "
        "cell may be marked RUN only when a receipt exists that names the client VERSION under which it ran."
    ),
    inputs=[
        "the compatibility matrix produced in Phase 4",
        "the conformance suite from B08",
        "installed client versions on this box (read-only probe)",
        "command-center/receipts/** (the evidence anchors)",
    ],
    deps=["B07", "B08", "B09"],
    role="conformance-engineer",
    perms=["Read", "Grep", "Glob", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=7200,
    schema="coverage-matrix",
    ev=(
        "A RUN cell without a client version string is downgraded to NEVER-RUN. 'The plugin installed cleanly' "
        "is not evidence that the client loaded it - the named failure class is 'plugin appears installed but "
        "hooks are unloaded', so a RUN cell must cite an observation from INSIDE the client (a hook firing, a "
        "command resolving), not an installer exit code."
    ),
    tests=[
        "Both-states: deliberately corrupt the plugin manifest and prove every RUN cell's probe turns red on that client - a probe that passes against a broken manifest measures nothing.",
        "Control: a cell whose only evidence is an installer exit code must fail validation.",
        "Control: an absent client must classify NOT-CHECKED, never PASS and never NOT-APPLICABLE.",
    ],
    rev="One independent reviewer who re-runs one RUN cell on a client the original agent did not use.",
    retry="No retry on an absent client: report NOT-CHECKED with the exact install step that would enable the probe.",
    fc=["green-not-live", "overclaim", "detector-failure"],
),
dict(
    n=7, q="platforms-never-tested",
    title="Platform x shell matrix that emits a runnable probe for every empty cell",
    target=(
        "Implementation target: build the OS x shell coverage matrix - {Windows, macOS, Linux} x {PowerShell 7, "
        "cmd.exe, Git Bash/MSYS, WSL bash, macOS zsh, POSIX sh} - and for every empty cell EMIT A RUNNABLE PROBE "
        "SCRIPT rather than a prose gap statement. A gap that ships as a sentence gets re-argued; a gap that "
        "ships as a script gets run."
    ),
    inputs=[
        "the declared support contract from Phase 4",
        "every shipped launcher, hook script and CLI entry point",
        "rules/common/windows-shell.md (the five ledger-proven Windows footguns)",
    ],
    deps=["B07", "B08"],
    role="platform-cartographer",
    perms=["Read", "Grep", "Glob", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=7200,
    schema="coverage-matrix",
    ev=(
        "Every probe must be executed at least once on a platform this box actually has; cells for absent "
        "platforms are marked NOT-CHECKED with the probe attached, never PASS. Cite each probe file path in "
        "the receipt."
    ),
    tests=[
        "Discrimination control: the Git-Bash cell probe must FAIL on a CRLF-line-ending script under real WSL bash and PASS under Git Bash - a probe that passes in both measures nothing.",
        "Control: `bare .sh invocation on Windows` (a named spec failure class) must be caught by the cmd.exe cell probe.",
        "Control: a probe that emits no assertion must fail the matrix's own validator.",
    ],
    rev="One independent reviewer who runs two emitted probes on a shell the author did not use and reports any silent pass.",
    retry="Two strikes then pivot: after two probe-authoring failures on the same cell, escalate the cell as BLOCKED with the exact missing platform.",
    fc=["non-portable", "overclaim", "detector-failure"],
),
dict(
    n=8, q="platforms-never-tested",
    title="Byte-form matrix: CRLF, LF, BOM and UTF-16 against every shipped parser",
    target=(
        "Question: which shipped parser has only ever been fed the LF bytes its author happened to write? "
        "Enumerate every parser the product ships (JSON, JSONL, YAML, TOML, markdown front-matter, .env, "
        "manifest readers, the receipt reducer) crossed with byte form {LF, CRLF, UTF-8 BOM, CRLF+BOM, UTF-16LE, "
        "mixed within one file}, and record which cells were exercised. Anchor on the live defect: "
        "tools/command-center/validate.py REACH-6 hashes WORKING-TREE bytes and is unrunnable on any Windows "
        "checkout because core.autocrlf=true and .gitattributes carries no '*.md eol=lf' rule."
    ),
    inputs=[
        "tools/command-center/validate.py (REACH-6) and every other shipped parser",
        ".gitattributes and the repo core.autocrlf setting",
        "rules/common/windows-shell.md 8b (blob-vs-worktree verification recipe)",
    ],
    deps=["B01", "B07", "B08"],
    role="portability-tester",
    perms=["Read", "Grep", "Glob", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=7200,
    schema="coverage-matrix",
    ev=(
        "Any claim of 'verified against the bytes CI sees' must use `git cat-file -p <rev>:<path>` or "
        "`git show <rev>:<path>`. `git archive | tar -x` returns the CRLF worktree form on this box - measured "
        "3,837 bytes with 100 CRLF vs 3,737 bytes with 0 CRLF for the same blob - so a check routed through it "
        "verifies the wrong bytes and manufactures false confidence."
    ),
    tests=[
        "For each parser: the CRLF form must produce the same parse result as the LF form, or an explicit documented rejection.",
        "Control: the known REACH-6 divergence must reproduce (committed blob hashes to the recorded provenance; the CRLF working copy does not).",
        "Control: a BOM-prefixed JSON file must either parse or raise a named error, never silently yield a key with a BOM in it.",
        "Route control: prove on one file that git archive returns CRLF and git cat-file returns LF before any blob-verification claim is accepted.",
    ],
    rev="One independent reviewer who repeats two parser cells against the blob route rather than the worktree route.",
    retry="Retry once per parser after fixing the byte-form fixture; a second failure escalates the parser as non-portable rather than being re-attempted.",
    fc=["non-portable", "green-not-live", "detector-failure"],
),
dict(
    n=9, q="platforms-never-tested",
    title="Link, network-path and permission filesystem semantics the hostile-path matrix leaves uncovered",
    target=(
        "Question: which filesystem semantics is covered by NEITHER the shipped tests NOR the adversarial "
        "hostile-path matrix? SCOPE BOUNDARY: ADV-0117 owns reserved device names, MAX_PATH overflow, "
        "case-only collisions, spaces, non-ASCII and trailing dots. This unit consumes that receipt and covers "
        "the residue it does not touch: UNC \\\\server\\share and mapped network drives, symlink versus NTFS "
        "junction versus hardlink traversal, a read-only or ACL-denied directory, a path crossing a filesystem "
        "boundary mid-operation, and an open file held by another process. Report each as EXERCISED, "
        "COVERED-BY-ADV-0117 or NEVER-TESTED with the shipped code path that touches it."
    ),
    inputs=[
        "the ADV-0117 hostile-path matrix receipt (consumed, not re-derived)",
        "every filesystem write/read/glob/rename/delete site in shipped code",
        "rules/common/bash-hud-and-terminal-emit.md 6 (UNC rejection after normalisation)",
    ],
    deps=["B07", "B08"],
    role="platform-test-engineer",
    perms=["Read", "Grep", "Glob", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=7200,
    schema="coverage-matrix",
    ev="Each cell cites the code path under test and the fixture that exercised it. Fixture creation and teardown must be idempotent and must never touch a path outside the scratch root.",
    tests=[
        "UNC: any path or URI handler must REJECT a normalised UNC target - a synthesized \\\\server\\share coerces an outbound SMB/NTLM authentication.",
        "Link traversal: a junction pointing outside the scratch root must not be followed by any recursive walk or delete (containment proof).",
        "Permission: a write into an ACL-denied directory must fail with a named error, never be silently skipped.",
        "Locked file: an open file held by a second process must produce a named error rather than a partial write.",
        "Control: the fixture set must be proven to be created (a matrix that silently skipped fixture creation would report all-green).",
    ],
    rev="One independent reviewer who re-runs the reserved-name and long-path cells and confirms the scratch root was the only tree mutated.",
    retry="No retry on a cell that mutated anything outside the scratch root - that is a blocking defect in the harness, not a flake.",
    fc=["non-portable", "data-loss-risk", "detector-failure"],
),
dict(
    n=10, q="platforms-never-tested",
    title="Locale, codepage and timezone blind spots",
    target=(
        "Question: what breaks outside en-US / UTF-8 / UTC? Enumerate every site that formats or parses a date, "
        "sorts strings, prints to a console, or embeds a timestamp in a filename, then run the smoke set under a "
        "non-UTF8 codepage (cp1252), a non-English locale, and a non-UTC timezone that crosses a DST boundary."
    ),
    inputs=[
        "every datetime, sort, print/console-emit and timestamped-filename site in shipped code",
        "the smoke test set from B08",
        "the event ledger writer (timestamps are its primary key surface)",
    ],
    deps=["B07", "B08"],
    role="portability-tester",
    perms=["Read", "Grep", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=5400,
    schema="coverage-matrix",
    ev="Report the exact environment triple (codepage, locale, TZ) for every run, and the console encoding actually in effect - not the one requested.",
    tests=[
        "cp1252 console with PYTHONIOENCODING unset: no shipped CLI banner or error message may raise UnicodeEncodeError.",
        "DST fall-back: two ledger entries written at the repeated 01:30 local hour must remain deterministically ordered.",
        "Negative control: introducing a naive datetime.now() into a timestamp path must make the suite RED - if it stays green the suite does not test this.",
        "Locale sort: a list sorted for display must be stable under a non-English collation or must declare an explicit locale-independent key.",
    ],
    rev="One independent reviewer who repeats the DST case with the opposite (spring-forward) boundary.",
    retry="Two strikes then pivot: after two environment-setup failures, containerise the locale run rather than mutating the live session environment a third time.",
    fc=["non-portable", "detector-failure", "green-not-live"],
),
dict(
    n=11, q="platforms-never-tested",
    title="Interpreter floor and ceiling: which declared runtime versions were never run",
    target=(
        "Question: which declared interpreter version was never actually executed? Extract the declared support "
        "range from python_requires, engines.node, and the plugin manifest's explicit interpreter declarations; "
        "record which versions the suite has actually run; then execute the conformance subset on the declared "
        "MINIMUM and on the newest available version, and narrow any declaration that cannot be demonstrated."
    ),
    inputs=[
        "pyproject/setup metadata, package.json engines, plugin manifest interpreter declarations",
        "the CI matrix definition (which versions CI really runs)",
        "the conformance subset from B08",
    ],
    deps=["B07", "B08"],
    role="conformance-engineer",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="cloud-batch",
    to=5400,
    schema="coverage-matrix",
    ev="A declared version with no executed run is reported UNSUBSTANTIATED-DECLARATION; the remedy is either a run or a narrowed declaration, never an assumption of compatibility.",
    tests=[
        "Floor run: the conformance subset must pass on the declared minimum interpreter, or the declaration is narrowed in the same unit.",
        "Control: a syntax feature newer than the declared floor, introduced deliberately, must be caught by the floor run.",
        "Ceiling run: the newest available interpreter must be run and any deprecation warning recorded, not suppressed.",
    ],
    rev="One independent reviewer who checks that the CI matrix and the declared range are the same set, not merely overlapping.",
    retry="Two strikes then pivot to a container image pinned at the floor version rather than a third local interpreter install attempt.",
    fc=["overclaim", "green-not-live", "non-portable"],
),
dict(
    n=12, q="clients-never-tested",
    title="Host-client version drift: what breaks one release back and one release forward",
    target=(
        "Question: which behaviours depend on the exact host-client version we happened to test? Enumerate every "
        "integration surface whose contract is owned by the HOST rather than by us - hook event names and payload "
        "shape, settings.json key layout and scope semantics, skill/plugin manifest fields, MCP protocol revision, "
        "slash-command registration - and for each record the tested version plus the concrete breakage one "
        "release back and one release forward."
    ),
    inputs=[
        "the shipped hook, skill, plugin and MCP adapter surfaces",
        "recorded hook payloads from the tested client version",
        "host-client changelogs and release notes for the adjacent versions",
    ],
    deps=["B03", "B07"],
    role="adapter-engineer",
    vendor="openai",
    perms=["Read", "Grep", "Write", "Bash", "WebFetch"],
    sub="local-serialized",
    to=7200,
    schema="coverage-matrix",
    ev="Every drift claim cites the host's own changelog entry or a recorded payload diff. An inference from our code alone is INFERRED, not CONFIRMED, and must say so in the claim.",
    tests=[
        "Strict-parser: replay a recorded payload with an unknown extra field and with a missing optional field; the adapter must degrade loudly, never silently.",
        "Control: an unknown hook event name must produce a named error rather than a silent no-op.",
        "Control: a settings key written at the wrong scope must be detected - the estate has measured a root-scope write that was inert because the real key lives per-project.",
    ],
    rev="Cross-vendor reviewer from the other vendor re-reads the host changelog independently; a drift claim asserted by only one vendor's read stays INFERRED.",
    retry="Retry once with the adjacent client version actually installed; if it cannot be installed, report NOT-CHECKED with the install blocker named.",
    fc=["stale-premise", "non-portable", "green-not-live"],
),
dict(
    # MERGE NOTE: this slot originally held a spec-imperative -> work-unit traceability matrix.
    # CC-0024 already extracts every imperative and numeric floor into requirement records and BINDS
    # each to its satisfying units, explicitly to answer this Phase 13 question. Extraction and binding
    # were therefore MERGED AWAY; this slot now audits the FALSE-POSITIVE direction of that same join,
    # which CC-0024 does not check.
    n=13, q="owner-requirements-disappeared",
    title="Mis-binding audit: requirements marked covered by a unit that does not actually satisfy them",
    target=(
        "Question: which requirement is BOUND to a work unit that does not in fact satisfy it? CC-0024 "
        "surfaces UNBOUND requirements - the false-negative direction. This unit audits the opposite and more "
        "dangerous direction: a requirement that reads as covered because a binding exists, where the bound "
        "unit implements a substitute, a subset, or an adjacent mechanism. For each binding, compare the "
        "requirement's demanded mechanism against the unit's actual target and classify SATISFIES / "
        "SUBSTITUTES (different mechanism, needs owner approval) / SUBSET (partial, name the residue) / "
        "MIS-BOUND."
    ),
    inputs=[
        "the CC-0024 requirement records and their requirement-to-unit bindings",
        "the merged work-unit catalog (the bound units' actual targets)",
        SPEC + ":10473-11437 (the demanded mechanism, read from the source line, not from the record's summary)",
    ],
    deps=["B01", "B07"],
    role="requirements-analyst",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="cloud-batch",
    to=7200,
    schema="binding-quality-audit",
    ev=(
        "Every verdict quotes BOTH the requirement's demanded mechanism at its spec line AND the bound unit's "
        "target text. A SATISFIES verdict that cites only the binding record is not evidence - the binding "
        "record is the artifact under audit, so it cannot be its own proof."
    ),
    tests=[
        "Control: plant a binding from a requirement to an unrelated unit and prove it classifies MIS-BOUND.",
        "Control: a requirement demanding 'a visual OR structured builder' satisfied by a structured builder must classify SATISFIES, not SUBSTITUTES - the audit must honour disjunctive requirements.",
        "Control: a correctly bound requirement must not be flagged (no false positives).",
        "Direction control: prove the audit is measuring the false-positive direction by confirming an UNBOUND requirement is out of scope here and belongs to CC-0024.",
    ],
    rev="One independent reviewer who re-reads five SATISFIES verdicts from the spec line alone and confirms the bound unit really does the demanded thing.",
    retry="Two strikes then pivot from mechanism-token comparison to a per-requirement hand adjudication of the disputed bindings.",
    fc=["overclaim", "detector-failure", "use-vs-mention"],
),
dict(
    n=14, q="owner-requirements-disappeared",
    title="Silently reversed owner decisions: contradiction detection, not absence detection",
    target=(
        "Question: which binding owner decision is CONTRADICTED by a shipped artifact? This is distinct from a "
        "missing implementation. For each decision in OWNER-DECISIONS.md and 17-DECISION-LOG.md, extract its "
        "normative content (release mode = PR-ONLY; retirement scope = DELETE-ALL across five trees; salvage "
        "home = tools/lib/; no-remote repos = triage first, never create remotes) and search the tree for an "
        "artifact that asserts or performs the opposite."
    ),
    inputs=[
        "command-center/OWNER-DECISIONS.md",
        "17-DECISION-LOG.md",
        "every shipped doc, script, CI workflow and catalog slice",
    ],
    deps=["B01", "B07"],
    role="contradiction-hunter",
    vendor="openai",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="contradiction-register",
    ev="Every contradiction cites BOTH sides at path:line. A decision with no contradicting artifact is reported CONFIRMED-CONSISTENT with the search surface named - not merely 'no finding', which is unfalsifiable.",
    tests=[
        "Control: plant a line asserting a canary release channel while PR-ONLY is binding, and prove it is caught.",
        "Use-vs-mention control: a document QUOTING the decision, or describing the rejected alternative as rejected, must NOT be flagged.",
        "Control: a decision whose contradicting artifact is a CI workflow (not prose) must still be caught - the search surface includes executable config.",
    ],
    rev="An Anthropic-vendor reviewer re-reads the three highest-severity contradictions from the raw sources; the OpenAI author's summary is not the input.",
    retry="Two strikes then pivot: if keyword search misses a planted contradiction twice, switch to per-decision hand-written probes.",
    fc=["contradiction", "stale-premise", "use-vs-mention"],
),
dict(
    n=15, q="owner-requirements-disappeared",
    title="Numeric floor deficit audit with a published counting rule and a planted-duplicate control",
    target=(
        "Question: for every 'at least N' in the spec, what is the measured count and the deficit? The floors are "
        "2,048 work units; 160 workflow candidates/mechanisms; 96 blueprints of which 40 flagship; 48 council "
        "protocols; 64 editable presets; 9 architectures; and the 100-unique-idea brainstorm target. For each, "
        "publish the exact counting rule (regex or JSON path), the measured number, the deficit, and a detector "
        "control proving the counter finds a known-present item and is SILENT on a planted near-duplicate."
    ),
    inputs=[
        "07-OPTION-UNIVERSE (md + json), 08-WORKFLOW-ARCHAEOLOGY (md + json), the blueprint and council registries",
        "command-center/PROMPT-ONE-FLOOR-AUDIT.json (the prior measurement to reproduce independently)",
        SPEC + " (the floor statements themselves)",
    ],
    deps=["B04", "B05", "B06"],
    role="measurement-engineer",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="cloud-batch",
    to=7200,
    schema="floor-audit",
    ev=(
        "Report the markdown-derived count and the JSON-derived count SEPARATELY and require the two SETS to be "
        "identical, not merely equal in size. Taking the max of two lists is the known wrong answer for the two "
        "council floors: protocols (58) and presets (72) are two disjoint fields, and 58+72 equals the file's "
        "total h4 heading count of 130, which is what proves nothing is double-counted. SCOPE BOUNDARY: "
        "CC-0024 EXTRACTS the floor statements; this unit contributes the COUNTED deficit plus the "
        "anti-padding control that a renamed duplicate must not increment a floor."
    ),
    tests=[
        "Control: plant a renamed duplicate blueprint and prove the counter does NOT count it toward the floor.",
        "Control: remove one known entry and prove the count drops by exactly 1.",
        "Cross-extractor: every floor count must be reproduced by a second, mechanically different extractor before it is reported.",
        "Disjointness: protocol ids intersect preset ids must be the empty set, computed and printed.",
    ],
    rev="One independent reviewer who recomputes two floors with their own extractor and must match exactly; a mismatch blocks both numbers, not just one.",
    retry="No retry of the same extractor. A disagreement between extractors is resolved by reading the raw artifact, never by re-running either counter.",
    fc=["overclaim", "detector-failure", "single-signal"],
),
dict(
    n=16, q="owner-requirements-disappeared",
    title="Final-deliverable closure by on-disk existence probe",
    target=(
        "Question: which item on the spec's Final Deliverables list (_USER-PROMPTS.md:11402-11435) has no artifact "
        "on disk? Resolve each of the listed deliverables to a concrete path or path set, probe existence, record "
        "byte size and sha256 read off disk, and register the result in ARTIFACT-MANIFEST.json. A digest is a "
        "claim, not a receipt; a file path inside a report is not proof the file exists."
    ),
    inputs=[
        SPEC + ":11402-11435 (the deliverable list)",
        "command-center/ARTIFACT-MANIFEST.json",
        "the repo working tree at program HEAD",
    ],
    deps=["B07", "B12"],
    role="verification-engineer",
    perms=["Read", "Glob", "Write", "Bash", "PowerShell"],
    sub="local-parallel",
    to=5400,
    schema="traceability-matrix",
    ev=(
        "Every PRESENT verdict carries a byte size and sha256 read from the filesystem in this unit, not copied "
        "from a manifest entry. Measured precedent: three of three agents in one corpus returned plausible "
        "digests for files that do not exist."
    ),
    tests=[
        "Control: a manifest entry pointing at a nonexistent path must be reported ABSENT.",
        "Control: a zero-byte file must classify EMPTY, never PRESENT.",
        "Control: a deliverable satisfied by a directory must require a named minimum member file, not merely a directory that exists.",
    ],
    rev="One independent reviewer who re-probes five PRESENT verdicts with a different tool (PowerShell Get-Item vs Python os.stat).",
    retry="No retry: an ABSENT verdict is a finding, not a failure. Re-probing an absent path is not a second signal.",
    fc=["overclaim", "detector-failure", "single-signal"],
),
dict(
    # MERGE NOTE: this slot originally held a stopping-condition computability audit. That mechanism
    # is already owned three times over by sibling slices - CC-0015 (encode the 21 predicates),
    # IMP-0457 (release-mode-aware evaluation of condition 13) and SYN-0043 (execute and adjudicate) -
    # measured at Jaccard 0.344 against CC-0015. It was MERGED AWAY rather than shipped as a fourth
    # copy, and this slot was refilled with a mechanism no slice covers.
    n=17, q="owner-requirements-disappeared",
    title="Unanswered-owner-question closure: units executing on a default the owner never chose",
    target=(
        "Question: which owner question was raised and never answered, and which work units are silently "
        "executing on that question's assumed default? Join the 27 owner_questions carried in "
        "WORK-UNIT-CATALOG.json and every question in OWNER-QUESTION-PACKET.md to the recorded owner "
        "answers, then to the units whose inputs or targets depend on each question, and report every unit "
        "proceeding on an UNANSWERED question together with the default it assumed. A required-but-blank "
        "answer defaults to worst case under adverse inference, never to 'probably fine'."
    ),
    inputs=[
        "command-center/WORK-UNIT-CATALOG.json (owner_questions, 27 entries)",
        "command-center/OWNER-QUESTION-PACKET.md",
        "command-center/OWNER-DECISIONS.md and 17-DECISION-LOG.md (the recorded answers)",
        "the merged work-unit catalog (units whose targets rest on an open question)",
    ],
    deps=["B01"],
    role="governance-analyst",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="owner-question-closure",
    ev=(
        "Every ANSWERED verdict cites the owner's own answer at path:line. An answer recorded as an agent's "
        "summary of the owner counts as UNANSWERED for this audit. For every unit proceeding on an "
        "unanswered question the ASSUMED DEFAULT must be extracted and stated explicitly - an implicit "
        "default is the thing this unit exists to surface."
    ),
    tests=[
        "Control: a question with a recorded owner answer must classify ANSWERED (no false positives).",
        "Control: a question 'answered' only by an agent's inference must classify UNANSWERED.",
        "Control: plant a unit whose target depends on an unanswered question and prove it appears in the proceeding-on-default set.",
        "Coverage: all 27 catalog owner_questions plus every question in the packet must appear exactly once in the closure table - a question appearing zero times is a join failure, not an absence.",
    ],
    rev="One independent reviewer who samples five ANSWERED verdicts and confirms the cited text actually RESOLVES the question rather than merely acknowledging it.",
    retry="No retry: an UNANSWERED question is a finding routed to the owner, not a failure of this unit to re-attempt.",
    fc=["owner-blocked", "stale-premise", "overclaim"],
    owner=True,
),
dict(
    n=18, q="owner-requirements-disappeared",
    title="Scope-shrink diff between the Prompt One scope and today's program scope",
    target=(
        "Question: what capability was quietly dropped between the Prompt One option universe and architecture "
        "selection and the program's scope today? Diff the successive scope statements (PROGRAM-CHARTER.md, the "
        "selected architecture, the merged catalog's actual coverage) and list every capability present earlier "
        "and absent now, naming the commit or decision that dropped it and whether that drop was owner-approved."
    ),
    inputs=[
        "command-center/PROGRAM-CHARTER.md and its git history",
        "the Prompt One architecture selection and option universe",
        "the merged work-unit catalog (current coverage)",
        "git log over the command-center tree",
    ],
    deps=["B01", "B06"],
    role="changelog-archaeologist",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="blindspot-register",
    ev="Each dropped capability cites the earlier statement at path:line (via `git show <rev>:<path>`) and the current absence, plus the decision id that authorised the drop or the fact that none exists.",
    tests=[
        "Control: a capability RENAMED rather than dropped must NOT be reported - match on mechanism, not on label.",
        "Control: plant a real drop in a scratch history and prove it is caught.",
        "Control: a capability dropped WITH an owner decision id must classify APPROVED-DROP, separately from unapproved drops.",
    ],
    rev="One independent reviewer who samples three APPROVED-DROP verdicts and reads the cited decision to confirm it actually authorises that drop.",
    retry="Two strikes then pivot from prose diff to capability-id diff before a third attempt.",
    fc=["stale-premise", "overclaim", "owner-blocked"],
    owner=True,
),
dict(
    n=19, q="option-ids-dropped",
    title="Option-ID disposition closure against stopping condition 1",
    target=(
        "Question: which option id is neither implemented, explicitly superseded, nor explicitly rejected with "
        "owner-approved reasoning? Enumerate every id in the option universe (283 options) plus the 38 MECH-NN "
        "mechanism cards, join to the decision log and the merged work-unit catalog, and emit a disposition table "
        "with exactly ONE terminal disposition per id."
    ),
    inputs=[
        "the CC-0024 extracted numeric-floor records (the floor STATEMENTS are consumed, not re-extracted)",
        "07-OPTION-UNIVERSE.md and its JSON twin (283 ids)",
        "13-ARCHITECTURE-CANDIDATES.md (38 MECH-NN mechanism cards)",
        "17-DECISION-LOG.md and command-center/OPTION-ID-RESOLUTION.json",
        "the merged work-unit catalog",
    ],
    deps=["B01", "B06", "B07"],
    role="registry-analyst",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="cloud-batch",
    to=7200,
    schema="disposition-table",
    ev=(
        "Resolve ids through the POST-FIX namespace: 13-ARCHITECTURE-CANDIDATES has used MECH-NN since "
        "2026-08-07 and carries zero bare M-NN tokens, while 17-DECISION-LOG.md contains zero 'MECH' tokens and "
        "still states the collision in the present tense at line 175. Resolve against the artifacts, never "
        "against the decision log's stale prose, and say which source each resolution used."
    ),
    tests=[
        "Control: an id carrying two dispositions must be reported AMBIGUOUS, never silently deduplicated to one.",
        "Control: a planted id absent from every artifact must surface as MISSING.",
        "Control: the two universe-only ids (M-40, M-41) and the seven doc-13-only ids must land in the expected buckets, or the discrepancy must be explained.",
    ],
    rev="One independent reviewer who re-derives the disposition of ten sampled ids directly from the artifacts without reading this unit's table.",
    retry="No retry against the decision log. If a resolution is ambiguous, escalate it to the dangling-reference sweep rather than guessing.",
    fc=["id-collision", "stale-premise", "overclaim"],
),
dict(
    n=20, q="option-ids-dropped",
    title="Cross-artifact ID-namespace collision census",
    target=(
        "Question: how many ID namespaces exist across the estate, and which prefixes are declared by more than "
        "one registry? Generalise past the known case: extract every `<PREFIX>-<NUMBER>` DECLARATION site across "
        "program artifacts, deployed skill trees and registers, group by prefix, and report every prefix with more "
        "than one declaring registry. Four M-NN namespaces are already known - the option-universe family M, the "
        "doc-13 mechanism cards, the wave-3 deep-research 'Research Harness (M-16)' deliverable id, and the wave-1 "
        "single-digit M-1/M-3 mission grades."
    ),
    inputs=[
        "all program artifacts and registers",
        "the deployed skill trees (.agents/skills and skills) including the duplicated wave3 copies",
        "wave1/REGISTER.md and wave3/ast-cc/skills/deep-research/SKILL.md",
    ],
    deps=["B01", "B02"],
    role="registry-analyst",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="collision-census",
    ev="A prefix is DECLARED only where a card/entry defines it; a prefix that only ever appears as a reference is DANGLING and is reported by the reference sweep instead. State the declaration-site pattern used.",
    tests=[
        "Control: all four known M-NN namespaces must be found - a census that finds fewer has a broken detector.",
        "Control: a prefix used only in references must classify DANGLING, not as a namespace.",
        "Control: a planted second declaring registry for an unused prefix must be caught.",
    ],
    rev="One independent reviewer who greps two random prefixes across all trees and confirms the declaring-registry count.",
    retry="Two strikes then pivot: if the declaration-site pattern misses a known namespace twice, enumerate declaration sites per-registry by hand.",
    fc=["id-collision", "detector-failure", "use-vs-mention"],
),
dict(
    n=21, q="option-ids-dropped",
    title="Dangling and ambiguous cross-reference sweep with UNDECIDABLE as a first-class verdict",
    target=(
        "Question: which id REFERENCE in the corpus fails to resolve to exactly one declaration? Distinct from a "
        "namespace collision: resolve every id token occurring in prose against the declaring registries and "
        "classify RESOLVES-ONE / RESOLVES-MANY / RESOLVES-NONE / UNDECIDABLE. Fifty-eight M-NN references are "
        "already known to be undecidable by algorithm because both namespaces contain a card for that number and "
        "the surrounding prose carries no discriminating token."
    ),
    inputs=[
        "every artifact containing id references (docs 16, 18, 19 in particular)",
        "the declaring registries identified by the namespace census",
        "command-center/OPTION-ID-RESOLUTION.json",
    ],
    deps=["BLD-0020"],
    role="differ-engineer",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="cloud-batch",
    to=7200,
    schema="reference-resolution",
    ev=(
        "UNDECIDABLE is a first-class verdict and must NOT be guessed into a resolution. LLM classification of a "
        "mechanical comparison measured 86% accurate on this estate with 100% of the errors pointing at data "
        "loss, so every UNDECIDABLE reference is escalated to the authoring lane rather than inferred."
    ),
    tests=[
        "Use-vs-mention control: a reference inside a fenced code block or a quoted example must classify MENTION, not USE.",
        "Control: the known 58 undecidable M-NN references must reproduce, or every deviation must be individually explained.",
        "Control: a reference to a definitely-absent id must classify RESOLVES-NONE, proven with a planted token.",
    ],
    rev="One independent reviewer who takes ten UNDECIDABLE references and confirms that no discriminating token exists in their context - if one does, the resolver is under-powered.",
    retry="No auto-retry with a loosened threshold. Loosening a resolver to reduce UNDECIDABLE count is the data-loss direction and is forbidden.",
    fc=["use-vs-mention", "id-collision", "data-loss-risk"],
),
dict(
    n=22, q="option-ids-dropped",
    title="Selection provenance: owner-explicit versus agent-assumed option selection",
    target=(
        "Question: for every option treated as SELECTED, what is the evidence that the OWNER selected it rather "
        "than an agent inferring the selection? The Prompt Two placeholder `[PASTE SELECTED OPTION IDS HERE]` is "
        "empty, so every 'selected' id inherits its authority from the decision log. Classify each as "
        "OWNER-EXPLICIT (quoting the owner's own sentence with its source), OWNER-IMPLIED (an agent's reading of "
        "the owner), or AGENT-ASSUMED, and route the last class to the owner."
    ),
    inputs=[
        SPEC + ":10514-10526 (the empty placeholders and the read-the-decision-log fallback)",
        "the Prompt One prompt corpus (owner-authored messages only)",
        "17-DECISION-LOG.md and command-center/OWNER-DECISIONS.md",
    ],
    deps=["B01"],
    role="owner-liaison",
    perms=["Read", "Grep", "Write"],
    sub="local-serialized",
    to=5400,
    schema="provenance-audit",
    ev="An OWNER-EXPLICIT verdict must quote the owner's own sentence with its file:line in the corpus. An agent's summary of the owner is OWNER-IMPLIED at best, however confidently it is written.",
    tests=[
        "Speaker-attribution control: an agent-authored sentence inside the corpus must never be attributed to the owner.",
        "Control: a known OWNER-EXPLICIT decision (release mode = PR-ONLY) must classify correctly.",
        "Control: a decision recorded by an agent with no owner quotation must land in AGENT-ASSUMED.",
    ],
    rev="One independent reviewer who re-reads the owner quotations only (not the agent summaries) and re-scores five entries.",
    retry="No retry: an AGENT-ASSUMED verdict is a finding to hand back, not a failure to re-attempt.",
    fc=["owner-blocked", "stale-premise", "overclaim"],
    owner=True,
),
dict(
    n=23, q="failures-normalized-away",
    title="Suppressed-failure construct census across code, tests, CI and scripts",
    target=(
        "Question: where does the tree convert a failure into a pass? Enumerate every suppression construct - "
        "skip/xfail/skipif, `continue-on-error: true`, `|| true`, a redirect of stderr on a checked command, bare "
        "`except: pass`, `-ErrorAction SilentlyContinue`, warning filters, `--exit-zero`-style flags - and record "
        "for each whether it carries a documented reason and an expiry, or is unaccounted."
    ),
    inputs=[
        "all test files, CI workflow files, shell/PowerShell scripts and shipped code",
        "the CI run history (which suppressions are load-bearing today)",
    ],
    deps=["B07", "B08"],
    role="test-governance-auditor",
    vendor="openai",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="cloud-batch",
    to=5400,
    schema="blindspot-register",
    ev="Each suppression is cited at path:line with its surrounding construct, and classified JUSTIFIED (reason + expiry present) or UNACCOUNTED. A count with no per-item citation is not accepted.",
    tests=[
        "Control: plant a `|| true` in a scratch copy of a CI step and prove it is reported.",
        "Use-vs-mention control: the literal string `continue-on-error` inside documentation or inside THIS unit's own description must not be counted as a suppression.",
        "Control: a `-ErrorAction SilentlyContinue` in PowerShell must be caught - the census must cover non-Python surfaces.",
    ],
    rev="An Anthropic-vendor reviewer samples ten JUSTIFIED verdicts and checks the stated reason is falsifiable rather than decorative.",
    retry="Two strikes then pivot from regex to per-language AST scanning before a third attempt.",
    fc=["use-vs-mention", "green-not-live", "detector-failure"],
),
dict(
    n=24, q="failures-normalized-away",
    title="Re-verification of previously dismissed failures (a triage is a dated claim)",
    target=(
        "Question: does every past 'not a real regression' triage still hold? Each dismissal is a dated claim that "
        "decays. Re-run each previously dismissed failure and re-check its stated reason: the Phase 0 baseline's "
        "eight failures triage as three Windows-CRLF artifacts, four a sibling agent's transient TDD red phase, "
        "and one POSIX-only - and a triage that rests on a sibling's transient state is only valid while that "
        "state is unchanged."
    ),
    inputs=[
        "command-center/BASELINE-SNAPSHOT.json and _baseline_tests_out.json",
        "the current test suite at program HEAD",
        "the CI console-script entry point (the runner the baseline did NOT use)",
    ],
    deps=["B02", "B08"],
    role="defect-archaeologist",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="worktree-isolated",
    to=7200,
    schema="triage-revalidation",
    ev=(
        "Re-running the identical command is a valid re-probe only when the tree SHA differs; otherwise use a "
        "mechanically different runner. The baseline used `python -m pytest` rather than CI's console script, so "
        "it is a broken detector for packaging and import-path regressions BY CONSTRUCTION - the re-verification "
        "must close that gap explicitly."
    ),
    tests=[
        "Falsification: a 'Windows CRLF only' dismissal must be falsified by running the same test on LF-normalised bytes and observing green; if it stays red the dismissal was wrong.",
        "Control: a dismissal whose reason cannot be falsified by ANY experiment is downgraded to UNVERIFIED and re-queued.",
        "Runner control: at least one dismissed failure must be re-run through the CI console script to prove the runner difference is exercised.",
    ],
    rev="One independent reviewer who reproduces two dismissals from raw source without reading the original triage text.",
    retry="Two strikes then pivot: after two inconclusive re-runs on the same failure, isolate it in a clean clone rather than re-running in the shared tree.",
    fc=["stale-premise", "green-not-live", "single-signal"],
),
dict(
    n=25, q="failures-normalized-away",
    title="Retry-as-mask audit: operations that only ever succeed on attempt two",
    target=(
        "Question: where does a retry policy hide a deterministic defect? Instrument every retrying call site - "
        "per-unit retry_policy, HTTP backoff wrappers, flaky-test reruns, monitor re-polls, cache refresh loops - "
        "to record attempt counts and first-attempt errors, then report every operation that succeeded only on "
        "attempt two or later. An operation that always fails once and then passes is a defect, not flakiness."
    ),
    inputs=[
        "every retry/backoff wrapper in shipped code and in the runner",
        "the per-unit retry_policy fields in the merged catalog",
        "run logs from the B08 and B09 executions",
    ],
    deps=["B07", "B08", "B09"],
    role="reliability-engineer",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="blindspot-register",
    ev="Each finding reports the attempt count distribution and the verbatim first-attempt error. A retry site that records no attempt telemetry is itself a finding (unobservable retry).",
    tests=[
        "Fault injection: a fail-once-then-succeed fault must be reported by the audit rather than swallowed by the wrapper.",
        "Control: a genuinely transient vendor 429 must classify TRANSIENT with its rate-limit evidence, not as a masked defect.",
        "Control: a call site with zero retries must not appear in the register (no false positives from non-retrying code).",
    ],
    rev="One independent reviewer who re-reads the first-attempt errors and confirms at least one is a real defect rather than an environment condition.",
    retry="Self-referential caution: this unit must not retry its own instrumentation run silently - a failed instrumentation pass is reported, not retried into a pass.",
    fc=["green-not-live", "detector-failure", "overclaim"],
),
dict(
    n=26, q="failures-normalized-away",
    title="Silent-degradation census: every fallback must degrade loudly",
    target=(
        "Question: where does the product silently fall back instead of degrading loudly, which the spec requires "
        "for cross-vendor and capability gaps? Enumerate every fallback branch - default-on-exception, best-effort "
        "parse, capability-missing shim, cached-value-on-error, vendor-adapter substitution - and require each to "
        "emit a structured, user-visible degradation event that names the capability lost and preserves the work "
        "artifact."
    ),
    inputs=[
        "every except/catch branch that returns a default or a cached value in shipped code",
        "the cross-vendor adapter layer from Phase 9",
        SPEC + ":10983 ('Degrade loudly and preserve the work artifact')",
    ],
    deps=["B07"],
    role="reliability-engineer",
    perms=["Read", "Grep", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="blindspot-register",
    ev="A fallback whose only trace is a debug-level log the user never sees counts as SILENT. The evidence for LOUD is an emitted event observable in the user-facing surface, cited by path:line plus a captured sample event.",
    tests=[
        "For each fallback: force the error condition and assert a degradation event is emitted AND the input artifact still exists afterwards.",
        "Control: a fallback whose event goes only to a debug logger must be classified SILENT by the audit.",
        "Control: a code path with no fallback must not appear in the register.",
    ],
    rev="One independent reviewer who forces two fallbacks and confirms the event reaches the user-facing surface, not only the log file.",
    retry="Two strikes then pivot: if fault injection cannot reach a branch twice, mark it UNREACHABLE-BY-INJECTION and hand it to the reachability unit rather than attempting a third time.",
    fc=["detector-failure", "overclaim", "green-not-live"],
),
dict(
    n=27, q="failures-normalized-away",
    title="Timeout-and-stillness classification audit across monitors and reducers",
    target=(
        "Question: where is a timeout or an absence of change read as health? Audit every monitor, harvester and "
        "fan-in reducer for the two inverse errors: a timed-out unit classified as anything other than FAILED, and "
        "stillness misread in either direction (a live-but-quiet unit reported stalled, or a dead monitor reported "
        "healthy). Stall detection from file mtimes alone is impossible - the only honest mtime signal is 'N files "
        "written in the last T seconds equals currently active'."
    ),
    inputs=[
        "every monitor, harvester and fan-in reducer in the runner",
        "the shared completion predicate implementation",
        "rules/common/bash-hud-and-terminal-emit.md 3 (mtime stall detection is impossible)",
    ],
    deps=["B07", "B08"],
    role="observability-tester",
    perms=["Read", "Grep", "Write", "Bash", "PowerShell"],
    sub="local-serialized",
    to=7200,
    schema="blindspot-register",
    ev="Every classification claim is backed by an executed fault scenario, not by reading the classifier's source. Two independent signals are required before any liveness verdict (for example CPU delta AND byte growth), never mtime alone.",
    tests=[
        "Kill a monitor while its remote work continues: the reducer must report SEVERED, never SUCCESS.",
        "Freeze a healthy long-running unit's output for twice the stall window: it must NOT be reported stalled without orchestrator state.",
        "Control: an exit code of zero with a missing artifact must classify FAILED (a named spec failure class).",
        "Control: an 11-hour-old finished agent must not be reported as a live stall.",
    ],
    rev="One independent reviewer who repeats the severed-monitor scenario with a different kill mechanism (process kill vs network partition).",
    retry="Two strikes then pivot: after two inconclusive liveness scenarios, instrument the orchestrator state rather than attempting a third filesystem-only probe.",
    fc=["detector-failure", "single-signal", "overclaim"],
),
dict(
    n=28, q="failures-normalized-away",
    title="Uncontrolled-zero census: every empty result that was never detector-controlled",
    target=(
        "Question: which reported zero, empty, 'no findings', 'not found' or 'clean' result in the whole program "
        "was never detector-controlled? Harvest every such result from receipts and reports; for each, check "
        "whether the PRODUCING unit recorded a known-present control and a known-broken control. A probe that is "
        "silent in both states measures nothing, and the estate's single most expensive recurring defect is acting "
        "on an uncontrolled zero."
    ),
    inputs=[
        "command-center/receipts/** and every lane report",
        "command-center/CLAIM-REGISTRY.json",
        "rules/common/single-signal-verification.md (the both-states rule)",
    ],
    deps=["B09", "B10"],
    role="detector-auditor",
    vendor="openai",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="cloud-batch",
    to=7200,
    schema="detector-control-audit",
    ev=(
        "The control evidence must be present in the PRODUCING receipt; this unit does not supply it retroactively. "
        "A zero with no recorded control is reported UNCONTROLLED-ZERO and re-queued to its producer, never "
        "accepted as a clean result."
    ),
    tests=[
        "Control: an uncontrolled zero planted in a scratch receipt set must be caught.",
        "Control (false-positive guard): a properly controlled zero must NOT be flagged.",
        "Use-vs-mention control: the phrase 'no findings' appearing inside a quoted example must not be harvested as a result.",
    ],
    rev="An Anthropic-vendor reviewer re-derives the uncontrolled count from the receipts independently; the two counts must agree.",
    retry="No retry against the same receipts. If the harvester and the reviewer disagree, read the receipts directly rather than re-running either harvester.",
    fc=["detector-failure", "single-signal", "overclaim"],
),
dict(
    n=29, q="unknowns-remain",
    title="Unknowns-register closure: a named settling experiment and an owner-visible impact per unknown",
    target=(
        "Question: which open unknown lacks a NAMED settling experiment and an owner-visible impact statement, as "
        "stopping condition 15 requires? Reconcile UNKNOWNS-REGISTER.md against every residual, UNVERIFIED and "
        "NOT-CHECKED tag harvested program-wide, and emit the unknowns that fail either half of the two-part test."
    ),
    inputs=[
        "command-center/UNKNOWNS-REGISTER.md",
        "every lane artifact's residual and UNVERIFIED tags",
        SPEC + ":11392 (stopping condition 15)",
    ],
    deps=["B09", "B10", "B12"],
    role="methodologist",
    perms=["Read", "Grep", "Glob", "Write"],
    sub="local-parallel",
    to=5400,
    schema="unknowns-closure",
    ev="An experiment 'names a command, an input, and the observation that would settle it'. Anything short of that fails the named-experiment half regardless of how it is worded.",
    tests=[
        "Control: an unknown whose experiment reads 'investigate further' must FAIL the named-experiment test.",
        "Control: an unknown with an impact statement written only in agent jargon must FAIL owner-visibility.",
        "Control: a well-formed unknown must PASS both halves (no false positives).",
        "Coverage: every harvested UNVERIFIED tag must appear in the register or be reported as unregistered.",
    ],
    rev="One independent reviewer who attempts to EXECUTE two named experiments from their text alone; if the text is insufficient to run it, the experiment is not named.",
    retry="No retry: an unknown that fails the test is a finding routed to its owning lane, not a failure of this unit.",
    fc=["overclaim", "owner-blocked", "detector-failure"],
),
dict(
    n=30, q="unknowns-remain",
    title="Caveat-position audit: inline adjacency versus a buried limitations section",
    target=(
        "Question: which UNVERIFIED or NOT-CHECKED caveat is buried where a reader will never meet it? For every "
        "tag in the corpus, compute its position as a fraction of its document and whether it sits adjacent to the "
        "claim it qualifies. The measured estate baseline is 40% of 127 real flags sitting in the final 15% of "
        "their document, and one buried caveat let a Tier-0 recommendation ship on a premise that the same "
        "document later admitted was never checked."
    ),
    inputs=[
        "every program artifact carrying UNVERIFIED / NOT-CHECKED / residual tags",
        "rules/common/fan-out-contract.md A3 (the inline-adjacency requirement)",
    ],
    deps=["B09", "B10", "B12"],
    role="methodologist",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="cloud-batch",
    to=3600,
    schema="tag-position-audit",
    ev="Report the position distribution, not just a mean: the defect is concentration in the final decile. Every BURIED verdict cites the tag line and the line of the claim it should have been adjacent to.",
    tests=[
        "Control: a tag in the same sentence or the immediately following sentence must score INLINE.",
        "Control: a tag inside a trailing 'Limitations' or 'Residual' section must score BURIED even when the document is short.",
        "Control: a document with zero tags must classify NO-TAGS, distinct from ALL-INLINE.",
    ],
    rev="One independent reviewer who reads two BURIED findings in context and confirms a reader following the recommendation would not have met the caveat.",
    retry="Two strikes then pivot from character-offset position to section-structure position before a third attempt.",
    fc=["overclaim", "use-vs-mention"],
),
dict(
    n=31, q="unknowns-remain",
    title="Confidence-band and evidence-tag audit over every forward-looking claim",
    target=(
        "Question: which forward-looking claim ships with no calibrated confidence band, or carries a band with no "
        "paired evidence anchor? Extract claims in the predictive or uncertain register from all program reports, "
        "check each for a Sherman-Kent band (almost-certain / likely / roughly-even / unlikely / remote) and a "
        "paired evidence tag, and report bare hedges such as 'should work', 'looks fine' and 'likely fine'."
    ),
    inputs=[
        "every lane report and receipt narrative",
        "command-center/CLAIM-REGISTRY.json",
        "AGENTS.md 7 (the confidence lexicon)",
    ],
    deps=["B09", "B10", "B12"],
    role="calibration-analyst",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="cloud-batch",
    to=3600,
    schema="tag-position-audit",
    ev="Each finding quotes the hedged sentence. A band attached to a PAST measured fact is a category error and is reported in a separate class from a missing band.",
    tests=[
        "Control: 'should work' with no band must be caught.",
        "Control: 'likely (55-80%), measured at path:line' must pass unflagged.",
        "Control: a past-tense measured fact carrying a probability band must be reported as a category error, not as compliant.",
    ],
    rev="One independent reviewer who re-scores twenty sampled claims blind and must agree within two on the flagged count.",
    retry="Two strikes then pivot from lexicon matching to modality tagging before a third attempt.",
    fc=["overclaim", "use-vs-mention", "detector-failure"],
),
dict(
    n=32, q="unknowns-remain",
    title="UNVERIFIED premise inheritance: recommendations that drop their premise's tag",
    target=(
        "Question: which recommendation rests on an UNVERIFIED premise without inheriting the tag in its own "
        "heading? Build premise-to-recommendation edges (a recommendation cites a claim; that claim carries a "
        "verification tag), compute the transitive premise set for each recommendation, and report every "
        "recommendation whose premise set contains an UNVERIFIED or NOT-CHECKED item while the recommendation "
        "itself reads as unqualified."
    ),
    inputs=[
        "every recommendation in the program's reports and decision packets",
        "command-center/CLAIM-REGISTRY.json (claim ids and verification status)",
        "the citation edges between recommendations and claims",
    ],
    deps=["B09", "B10", "B12"],
    role="adjudicator",
    perms=["Read", "Grep", "Glob", "Write", "Bash"],
    sub="local-parallel",
    to=5400,
    schema="tag-position-audit",
    ev="Every finding cites the recommendation heading, the premise claim id, and the premise's tag location. A recommendation with no traceable premise is reported UNGROUNDED, which is a separate and more severe class.",
    tests=[
        "Control: a recommendation citing a tagged premise without inheriting the tag must be caught.",
        "Control (false-positive guard): a recommendation that DOES carry the inherited tag in its heading must not be flagged.",
        "Transitivity control: a two-hop premise chain (recommendation cites claim A, A rests on UNVERIFIED claim B) must be caught, not only the one-hop case.",
    ],
    rev="One independent reviewer who traces two flagged recommendations back to their premises by hand and confirms the chain.",
    retry="Two strikes then pivot from citation-token matching to explicit claim-id edges before a third attempt.",
    fc=["overclaim", "contradiction", "detector-failure"],
),
]
