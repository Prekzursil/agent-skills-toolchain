"""Generator for catalog slice AUD-1of1: bucket B02 (current-state and dependency audit, 96 units).

Spec anchors: _USER-PROMPTS.md:10555 (bucket), :10605-10625 (19 mandatory per-unit fields),
:10652-10660 (Phase 0), :10662-10679 (Phase 1), :10570-10584 (scaling/substrate doctrine).

Design decision (addresses the CONFIRMED P1 in ground/cc-reality): every field is written
PER UNIT. There is no global defaults block and no unit relies on one.
"""
import json
import os

SCHEMA = {
    "inv": "command-center/schema/audit-inventory.schema.json",
    "drift": "command-center/schema/audit-drift.schema.json",
    "graph": "command-center/schema/audit-graph.schema.json",
    "metric": "command-center/schema/audit-metric-baseline.schema.json",
    "detector": "command-center/schema/audit-detector-control.schema.json",
    "claim": "command-center/schema/claim-record.schema.json",
    "finding": "command-center/schema/audit-finding.schema.json",
    "failtest": "command-center/schema/failing-test-receipt.schema.json",
}

RO = ["Read", "Grep", "Glob"]
ROB = ["Read", "Grep", "Glob", "Bash"]
ROP = ["Read", "Grep", "Glob", "PowerShell"]
ROBP = ["Read", "Grep", "Glob", "Bash", "PowerShell"]
FULL = ["Read", "Grep", "Glob", "Bash", "PowerShell", "Write"]
FULLE = ["Read", "Grep", "Glob", "Bash", "PowerShell", "Write", "Edit"]
GH = ["Read", "Grep", "Glob", "Bash", "mcp__github__list_branches",
      "mcp__github__list_pull_requests", "mcp__github__pull_request_read"]

M_AUD = {"model": "opus", "vendor": "anthropic", "role": "auditor"}
M_TOOL = {"model": "opus", "vendor": "anthropic", "role": "tool-author"}
M_XV = {"model": "gpt-5-codex", "vendor": "openai", "role": "independent-verifier"}
M_NORM = {"model": "opus", "vendor": "anthropic", "role": "corpus-normalizer"}
M_SEC = {"model": "opus", "vendor": "anthropic", "role": "security-auditor"}
M_REF = {"model": "gpt-5-codex", "vendor": "openai", "role": "adversarial-refuter"}

R_FRESH = ("one fresh-context Claude reviewer who has not seen this unit's transcript; the reviewer "
           "must try to FALSIFY the headline count before PASS, not re-read the artifact")
R_XV = ("one cross-vendor Codex reviewer who re-runs ONLY the second probe; a same-vendor reviewer "
        "shares this unit's blind spots and does not satisfy the requirement")
R_TWO = ("two reviewers, one fresh-context Claude and one Codex; on disagreement escalate to the owner "
         "with both probes attached - do NOT resolve by vote")
R_OWNER = ("fresh-context Claude reviewer PLUS explicit owner sign-off before any action is taken on "
           "the finding; the audit itself is read-only")

RT_2S = ("two strikes then pivot (AGENTS.md 4b): after the second failure with the same detector, "
         "enumerate at least 2 mechanically different detectors before a third attempt")
RT_SHELL = ("at most 3 attempts, each in a DIFFERENT shell (pwsh7, git-bash, wsl bash); a repeat in the "
            "same shell is not a retry and must not be counted as one")
RT_NORETRY = ("no automatic retry - a failed run here may have mutated the tree; restore from the AUD-0092 "
              "backup, record the mutation, and escalate")
RT_UPSTREAM = ("retry only after the named upstream unit emits its SUCCESS sentinel; retrying against a "
               "missing input is a detector failure, not a transient")
RT_SCOPE = ("retry once with the sweep re-scoped to a single path to isolate a path-length or encoding "
            "failure from a logic failure, then pivot")
RT_DECAY = ("re-run rather than retry: this result decays, so a stored PASS older than 24h must be "
            "re-queried instead of reused")

# lane, slug, title, target(question/implementation target), inputs, deps, model, tools,
# substrate, timeout, schema, evidence, tests, reviewer, retry, failclass, owner_appr, phase
U = []


def u(slug, title, target, inputs, deps, model, tools, sub, to, sch,
      ev="", ts=None, rev="", rt="", fc=None, oa=False, ph="0"):
    U.append(dict(slug=slug, title=title, target=target, inputs=inputs, deps=deps, model=model,
                  tools=tools, sub=sub, to=to, sch=sch, ev=ev, ts=list(ts or []), rev=rev, rt=rt,
                  fc=list(fc or []), oa=oa, ph=ph))


# ------------------------------------------------------------------ Lane A: git / VCS current state
u("branch-merge-state",
  "Branch inventory with squash-merge-aware merge-state classification",
  "For every local and remote branch in every owner-controlled repo, is its content already on main - "
  "answered by PR-MERGED state or byte-level content comparison, NOT by commit ancestry?",
  ["git for-each-ref over every repo under ~/source and ~/Documents/GitHub",
   "GitHub PR state for each branch head",
   "rules/common/ci-hygiene.md section 4 (squash-merge makes a merged branch report as ahead)"],
  ["B01"], M_AUD, GH, "local-serialized", 2400, SCHEMA["inv"],
  "Probe 1: git rev-list --count main..<branch> plus git cherry -v main <branch>. Probe 2 (mechanically "
  "different): GitHub API pull_request state=MERGED for the branch head SHA, and for branches with no PR, "
  "a git diff main...<branch> --stat byte surface. A branch is CONTENT-ON-MAIN only when probe 2 agrees.",
  ["plant a branch that IS squash-merged and confirm the ancestry-only detector wrongly reports it as ahead "
   "while the content detector reports it as merged - if both agree, the detector is not discriminating"],
  R_XV, RT_2S, ["detector-failure", "single-signal", "stale-premise"], False)

u("worktree-inventory",
  "Worktree inventory: repo identity, dirty surface, and content-preservation proof",
  "For each of the 6 surviving worktrees, which repository does it actually point at, how many tracked and "
  "untracked files differ from its upstream, and is every byte of its unique content preserved elsewhere?",
  ["git worktree list --porcelain in every checkout",
   "git -C <wt> remote get-url origin for identity",
   "the 5 NEEDS-OWNER-DECISION gradings from the 2026-08-09 worktree cleanup"],
  ["B01", "AUD-0001"], M_AUD, ROBP, "local-serialized", 2400, SCHEMA["inv"],
  "Probe 1: git status --porcelain=v2 --untracked-files=all per worktree for the dirty surface. Probe 2: for "
  "every file the worktree holds uniquely, a sha256 search of the same blob in main and in every sibling "
  "worktree - a path-name match is NOT preservation proof.",
  ["control: seed a file that exists ONLY in one worktree and confirm the preservation prober reports it "
   "UNPRESERVED; then copy it to main and confirm the prober flips"],
  R_TWO, RT_NORETRY, ["detector-failure", "index-contention", "owner-blocked"], True)

u("pr-unique-content",
  "PR history census: content in merged or closed PRs that never reached main",
  "Which merged-or-closed pull requests contain file content that is absent from main today, and for each, "
  "was the loss deliberate (superseded) or accidental (revert, force-push, or a closed-without-merge)?",
  ["GitHub PR list for every owner repo, all states",
   "each PR head SHA and its files changed",
   "current main tree"],
  ["B01", "AUD-0001"], M_AUD, GH, "local-serialized", 3000, SCHEMA["finding"],
  "Probe 1: for each PR head SHA, git diff <head> main --name-only limited to files the PR touched. Probe 2: "
  "GitHub API merged_at plus merge_commit_sha reachability from main - the two must agree on merged-ness "
  "before any absence is called deliberate.",
  ["negative control: pick a PR known to be fully merged and confirm the detector reports zero missing files; "
   "then delete one of its files locally and confirm it reports exactly one"],
  R_FRESH, RT_2S, ["detector-failure", "stale-premise", "credential-absent"], False)

u("stash-reflog-salvage",
  "Stash, reflog, and dangling-object salvage census",
  "What recoverable work exists in git stashes, reflog entries beyond current branch tips, and dangling "
  "blobs/commits across owner repos - and specifically, did any 'git stash push -- <untracked path>' save nothing?",
  ["git stash list and git fsck --lost-found per repo",
   "git reflog --all with dates",
   "the recorded 2026-08-08 incident where a bare pop popped an unrelated stash"],
  ["B01"], M_AUD, ROB, "local-serialized", 1800, SCHEMA["inv"],
  "Probe 1: git fsck --unreachable --dangling enumerating unreachable commits and blobs. Probe 2: git stash "
  "list cross-checked against git stash show --include-untracked --stat per entry, because an empty stash "
  "entry and a populated one are indistinguishable from the list alone.",
  ["both-states control: create a stash of ONLY an untracked path and confirm the prober reports it as "
   "zero-content, then stash a tracked change and confirm it reports non-zero"],
  R_FRESH, RT_2S, ["detector-failure", "partial-artifact"], False)

u("tag-release-parity",
  "Tag and release inventory versus published artifacts and declared versions",
  "Does every git tag resolve to a release with the artifacts it claims, and does every in-tree version "
  "declaration (pyproject, package.json, plugin manifest) agree with the latest tag?",
  ["git tag -l with git rev-list -n 1 <tag> for deref (never the caret form)",
   "GitHub releases and their asset lists",
   "every version string in the repo"],
  ["B01"], M_AUD, GH, "local-serialized", 1500, SCHEMA["inv"],
  "Probe 1: git rev-list -n 1 <tag> for the commit (the caret form is mangled by PowerShell escaping). "
  "Probe 2: the GitHub releases API asset list plus a byte-size check, so a release row with zero assets "
  "cannot read as published.",
  ["control: assert the prober flags a deliberately created tag with no release, proving it is not "
   "silently treating absence as parity"],
  R_FRESH, RT_SHELL, ["shell-quoting", "detector-failure"], False)

u("uncommitted-work-census",
  "Uncommitted and untracked work census, classified real-work versus agent-scratch",
  "Across every owner-controlled repo, which uncommitted or untracked files are real authored work that "
  "must be preserved, and which are agent scratch, build output, or cache that may be ignored?",
  ["git status --porcelain=v2 -uall per repo",
   "file mtime, size, and authoring-tool fingerprints",
   "the hooks/git-hygiene Stop-hook exclusion list for vendored and scratch clones"],
  ["B01"], M_AUD, ROBP, "local-serialized", 2400, SCHEMA["inv"],
  "Probe 1: git status porcelain enumeration with per-path size and mtime. Probe 2: a content classifier "
  "run on the file BODY (does it import project modules, does it carry a test or a docstring) rather than "
  "on its path, because a scratch-looking path can hold real work and vice versa.",
  ["planted-mutant control: place a real authored module under a scratch-looking path and confirm the "
   "content classifier rescues it while a path-only classifier loses it"],
  R_FRESH, RT_2S, ["use-vs-mention", "detector-failure", "index-contention"], False)

u("no-remote-repo-triage",
  "No-remote repository triage - report only, create no remotes and push nothing",
  "Which local repositories have no configured remote, what unique content does each hold, and what is the "
  "recommended disposition for each - with the action itself left entirely to the owner?",
  ["git remote -v across every directory containing a .git",
   "per-repo commit count, last commit date, and unique-path surface",
   "the standing owner decision: TRIAGE FIRST, report, owner decides"],
  ["B01", "AUD-0006"], M_AUD, ROB, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: git remote -v emptiness per repo. Probe 2: git config --get-regexp remote to catch a remote "
  "configured without a fetch refspec, which prints nothing under probe 1 yet is not remote-less.",
  ["detector control: add a fetch-less remote to a scratch repo and confirm probe 2 sees it while probe 1 "
   "reports no-remote - if both report the same, the pair is not independent"],
  R_OWNER, RT_2S, ["detector-failure", "owner-blocked"], True)

u("commit-authorship-integrity",
  "Commit authorship and history-integrity census for the baseline-ancestor invariant",
  "Is the pinned baseline commit still an ancestor of every HEAD, and is every intervening commit "
  "owner-authored rather than agent-authored - and what is the changed-path surface that corroborates it?",
  ["git merge-base --is-ancestor 53c37c6c HEAD per repo",
   "git log --format for author, committer, and date since the baseline",
   "the changed-path list per intervening commit"],
  ["B01"], M_AUD, ROB, "local-serialized", 1500, SCHEMA["finding"],
  "Probe 1: git merge-base --is-ancestor for the no-history-rewrite half. Probe 2: the changed-path surface "
  "per commit checked against this program's unit names, because author identity is forgeable and must be "
  "corroborated by what the commit actually touched.",
  ["assert the invariant is NOT expressed as equality to a pinned SHA - a scratch commit by the owner must "
   "leave the invariant GREEN, and a history rewrite must turn it RED"],
  R_XV, RT_2S, ["stale-premise", "detector-failure", "single-signal"], False)

u("submodule-vendored-inventory",
  "Submodule, nested-repo, and vendored-tree inventory with upstream pin",
  "Which paths in the tree are submodules, nested git repos, or vendored copies of third-party code, and "
  "for each vendored tree what is the exact upstream URL, version, and license?",
  [".gitmodules and every nested .git directory",
   "vendored directory markers (vendor/, third_party/, _vendor/, pinned commit notes)",
   "upstream project metadata for each vendored tree"],
  ["B01"], M_AUD, ROB, "local-parallel", 1800, SCHEMA["inv"],
  "Probe 1: find every .git entry below the repo root (file or directory) - a submodule presents .git as a "
  "FILE. Probe 2: a content fingerprint of each candidate vendored tree against its upstream tarball hash, "
  "so an undeclared copy with no marker is still detected.",
  ["control: the finder must locate the known submodule-style .git FILE, not only .git directories; assert "
   "on a fixture containing both forms"],
  R_FRESH, RT_2S, ["detector-failure", "scope-mismatch"], False)

u("repo-weight-baseline",
  "Repository object-size and history-weight baseline",
  "What does a fresh clone of each owner repo cost in objects, packed bytes, and wall-clock, and which "
  "individual objects or paths dominate that weight?",
  ["git count-objects -vH per repo",
   "git rev-list --objects --all piped through cat-file for per-blob size",
   "a timed git clone --no-hardlinks into a scratch path"],
  ["B01"], M_TOOL, ROB, "local-serialized", 2400, SCHEMA["metric"],
  "Probe 1: git count-objects -vH for the packed size. Probe 2: an independently timed clone into a temp "
  "directory measuring bytes on disk, because count-objects reports the packed view and not what a clone "
  "materializes.",
  ["record the measurement twice on an unchanged repo and require the two runs agree within 2 percent, "
   "proving the metric is not contaminated by concurrent gc"],
  R_FRESH, RT_2S, ["concurrency-contention", "detector-failure"], False)

# ------------------------------------------------------------- Lane B: live-vs-repo deployment drift
u("rules-provenance-adjudication",
  "Per-file provenance adjudication for the 28 content-differing rules files",
  "For each of the 28 rules files whose repo and live copies differ in real content, which side is "
  "AUTHORITATIVE - decided by commit time versus live mtime plus a content read, not by size?",
  ["the 88-file repo rules/ tree and the ~/.claude/rules live tree",
   "git log -1 --format=%cI -- rules/<path> per file",
   "the 3 live-larger files (owner-ops-authorization +1001 B, performance +178 B, security +97 B)"],
  ["B01"], M_AUD, ROBP, "local-serialized", 3600, SCHEMA["drift"],
  "Probe 1: per-file git commit timestamp versus live filesystem mtime. Probe 2: a semantic read of the "
  "diff hunks for each of the 3 live-larger files and a sample of the 25 repo-larger ones - timestamps alone "
  "cannot tell a deploy artifact from authored content.",
  ["both-states control: normalize line endings before comparing and confirm the 55 EOL-only differences "
   "collapse to zero while the 28 content differences survive; a comparator that also collapses the 28 is broken"],
  R_TWO, RT_2S, ["eol-artifact", "detector-failure", "owner-blocked"], True)

u("skills-three-way-drift",
  "Three-way skills drift: repo skills/ versus ~/.agents/skills versus ~/.claude/skills",
  "Which skills exist in only one or two of the three trees, and for those in all three, which pairs differ "
  "in content after EOL normalization?",
  ["repo skills tree", "~/.agents/skills", "~/.claude/skills"],
  ["B01"], M_TOOL, ROBP, "local-serialized", 2400, SCHEMA["drift"],
  "Probe 1: a three-way set comparison of relative paths. Probe 2: sha256 of the LF-normalized bytes per "
  "path per tree, reported as a 3-way partition so a two-directional divergence cannot be read as a "
  "one-directional deploy lag.",
  ["planted control: introduce a one-byte content change in exactly one tree and confirm the comparator "
   "reports exactly one divergent path, not zero and not all"],
  R_FRESH, RT_2S, ["eol-artifact", "detector-failure"], False)

u("hooks-manifest-parity",
  "Hook registration parity: manifest entries versus on-disk hook files",
  "Does every entry in hooks/_dispatch/manifest.json resolve to an existing executable hook file, and does "
  "every on-disk hook file appear in the manifest?",
  ["repo hooks/_dispatch/manifest.json and the deployed copy",
   "every file under repo hooks/ and ~/.claude/hooks/",
   "the standing rule that the repo is source of truth and the deployed copy is overwritten on deploy"],
  ["B01"], M_TOOL, ROBP, "local-serialized", 1800, SCHEMA["drift"],
  "Probe 1: manifest-to-disk resolution in both directions. Probe 2: compare the REPO manifest against the "
  "DEPLOYED manifest, because a hand-edit to the deployed copy is invisible to git and reverts on next deploy.",
  ["control: remove one manifest entry in a scratch copy and confirm the orphan detector names exactly that "
   "hook; add a stray file and confirm the unregistered detector names exactly that file"],
  R_FRESH, RT_2S, ["green-not-live", "detector-failure"], False)

u("agents-commands-drift",
  "Agent-definition and slash-command drift between repo and live trees",
  "Which agent definitions and slash commands exist live but not in the repo, differ in content, or declare "
  "a model that violates the opus-for-substantive-subagents floor?",
  ["repo agents/ and commands/ trees", "~/.claude/agents and ~/.claude/commands",
   "each definition's frontmatter model field"],
  ["B01"], M_AUD, ROBP, "local-serialized", 1800, SCHEMA["drift"],
  "Probe 1: path-set and normalized-content comparison per tree. Probe 2: parse the frontmatter model FIELD "
  "rather than grepping the file body for the word sonnet, because a definition that merely mentions sonnet "
  "in prose is not assigned sonnet.",
  ["use-vs-mention control: a fixture whose body contains the string sonnet in a comment must NOT be flagged; "
   "a fixture whose frontmatter sets model: sonnet MUST be flagged"],
  R_FRESH, RT_2S, ["use-vs-mention", "detector-failure"], False)

u("mcp-scope-resolution",
  "MCP configuration scope resolution: which config file actually wins",
  "For every MCP server, which of ~/.mcp.json, the ~/.claude.json root block, the ~/.claude.json per-project "
  "block, and ~/.claude/settings.json holds its effective enabled state - and where do they disagree?",
  ["~/.mcp.json", "~/.claude.json root and per-project keys", "~/.claude/settings.json",
   "the measured precedent that a root-scope disabledMcpServers key was inert because the real key was per-project"],
  ["B01"], M_AUD, ROP, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: parse all four config surfaces and compute the declared effective state per server. Probe 2: the "
  "live process table (server processes actually spawned) - the declared state is a claim and the process "
  "table is the receipt.",
  ["both-states control: the resolver must produce a DIFFERENT answer for a server disabled at root versus "
   "the same server disabled per-project; a resolver that returns the same answer for both is not reading scope"],
  R_XV, RT_2S, ["scope-mismatch", "green-not-live", "single-signal"], False)

u("plugin-enablement-map",
  "Plugin enable/disable map audit across every scope",
  "For every installed plugin, what is its enabled state at user, project, and local scope, and which "
  "reported state is contradicted by whether its commands and skills are actually reachable this session?",
  ["claude plugin list output", "enabledPlugins in ~/.claude/settings.json and any project settings",
   "the live skill and command inventory"],
  ["B01"], M_AUD, ROP, "local-serialized", 1500, SCHEMA["finding"],
  "Probe 1: the enabledPlugins map read from each settings file. Probe 2: reachability - does the plugin's "
  "command or skill actually resolve; a plugin marked enabled whose skills do not resolve is green-not-live.",
  ["control: confirm the detector reports the known-disabled agentbridge plugin as disabled by BOTH probes; "
   "if the reachability probe cannot distinguish it, the probe measures nothing"],
  R_FRESH, RT_2S, ["green-not-live", "scope-mismatch"], False)

u("live-repo-orphan-census",
  "Bidirectional orphan census: live-only harness files and repo files never deployed",
  "Which harness artifacts exist in the live trees but in no repo (architecturally orphaned), and which repo "
  "artifacts have no deployed counterpart (deploy target missing)?",
  ["every live harness tree (~/.claude, ~/.agents)", "the repo tree", "the deploy map from AUD-0018"],
  ["B01", "AUD-0018"], M_TOOL, ROBP, "local-serialized", 3000, SCHEMA["drift"],
  "Probe 1: relative-path set difference in both directions after applying the deploy map. Probe 2: for each "
  "live-only file, a git log --all --diff-filter=D search proving it was never in history rather than deleted, "
  "which the set difference alone cannot distinguish.",
  ["control: the enumerator must not crash or silently zero on a file named NUL or a path over 260 chars - "
   "assert a non-zero count on a fixture containing both"],
  R_XV, RT_SCOPE, ["path-length", "detector-failure", "partial-artifact"], False)

u("deploy-script-semantics",
  "Deploy and sync script semantic audit: transform, directionality, and guards",
  "For each deploy or sync script, does it copy verbatim or transform content, which direction does it carry, "
  "and which guards (nested-repo, vendored-tree, repo-owned-file) does it actually apply?",
  ["scripts/sync-rules.ps1", "scripts/sync-from-live.ps1", "any other deploy entry point",
   "the measured fact that sync-rules.ps1:67 is a plain Copy-Item -Force with no transform"],
  ["B01"], M_AUD, RO, "local-parallel", 1500, SCHEMA["finding"],
  "Probe 1: a line-level read of each script naming the copy primitive and every guard clause. Probe 2: a "
  "DRY-RUN execution against a scratch fixture pair, recording which files the script would touch - the code "
  "read is the claim, the dry run is the receipt.",
  ["the dry run must be proven non-destructive first: run it against a fixture and assert byte-identical "
   "before and after; only then trust its file list"],
  R_TWO, RT_NORETRY, ["detector-failure", "index-contention"], False)

u("eol-contract-audit",
  "EOL contract audit: blob-versus-worktree divergence and .gitattributes rule coverage",
  "Which files differ between their committed blob and the Windows working tree purely by line ending, and "
  "which file types have no .gitattributes eol rule to pin them?",
  [".gitattributes", "git cat-file -p HEAD:<path> for every text file", "the working-tree bytes",
   "core.autocrlf setting"],
  ["B01"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["drift"],
  "Probe 1: byte-compare git cat-file -p output against the working-tree file for every text path. Probe 2: "
  "a .gitattributes rule-coverage map by extension. Explicitly do NOT use git archive - it applies export-time "
  "EOL conversion and returns CRLF on this box, the opposite of the blob.",
  ["three-route control on one known file: git archive, git cat-file -p, and git show must be compared, and "
   "the audit must record that archive disagrees - if all three agree, the probe is not running on Windows"],
  R_XV, RT_2S, ["eol-artifact", "detector-failure"], False)

# --------------------------------------------------- Lane C: external dependency and supply chain
u("python-dep-inventory",
  "Python dependency and lockfile inventory per package",
  "For every Python package in the repo, what are its declared direct dependencies, is there a lockfile, and "
  "does the lockfile resolve the declared constraints?",
  ["every pyproject.toml, setup.cfg, requirements*.txt", "every uv.lock / poetry.lock / pip freeze artifact"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["inv"],
  "Probe 1: parse each manifest into a normalized name/constraint table. Probe 2: resolve the same set with "
  "the lockfile and diff the two tables - a manifest read alone cannot detect a lockfile that pins a version "
  "outside the declared range.",
  ["control: inject an out-of-range pin into a fixture lockfile and confirm the differ flags it"],
  R_FRESH, RT_2S, ["detector-failure", "partial-artifact"], False)

u("node-dep-inventory",
  "Node dependency inventory and lockfile integrity",
  "For every package.json in the repo, what are its dependencies by class (prod, dev, peer, optional), and "
  "does package-lock.json or pnpm-lock.yaml pass an integrity check?",
  ["every package.json", "every lockfile", "npm ls / pnpm list output"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["inv"],
  "Probe 1: parse package.json dependency classes. Probe 2: npm ls --all exit status plus the lockfile "
  "integrity hashes, because a manifest can be well-formed while the lock is corrupt or out of sync.",
  ["control: corrupt one integrity hash in a fixture lock and confirm the checker exits non-zero and names "
   "that package"],
  R_FRESH, RT_2S, ["detector-failure"], False)

u("transitive-dep-graph",
  "Transitive dependency graph, depth, and duplicate-version census",
  "What is the full transitive dependency closure across ecosystems, what is its maximum depth, and which "
  "packages appear at two or more incompatible versions in the same closure?",
  ["the direct dependency tables from AUD-0020 and AUD-0021", "resolver output for the full closure"],
  ["B01", "AUD-0020", "AUD-0021"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["graph"],
  "Probe 1: the resolver's own tree output. Probe 2: an independently built graph from installed package "
  "metadata in a clean environment, so a resolver bug or a stale cache cannot define the answer alone.",
  ["control: the duplicate detector must find a deliberately introduced dual-version case and must NOT "
   "report duplicates on a fixture with a single clean resolution"],
  R_FRESH, RT_UPSTREAM, ["dependency-blocked", "detector-failure"], False)

u("vuln-posture-snapshot",
  "Vulnerability posture snapshot with an explicit decay timestamp",
  "Which dependencies in the closure carry a known advisory today, at what severity, and what is the exact "
  "query timestamp after which this result must be re-queried rather than reused?",
  ["the transitive closure from AUD-0022", "osv-scanner and the GitHub advisory database",
   "the standing rule that a stored green from last week is not a control for today"],
  ["B01", "AUD-0022"], M_AUD, ["Read", "Grep", "Bash", "WebFetch"], "cloud-batch", 2400, SCHEMA["finding"],
  "Probe 1: osv-scanner over the lockfiles. Probe 2: the GitHub Dependabot alert list for the same repos - "
  "two independent advisory sources, because one database's silence is not absence of a vulnerability.",
  ["detector control: seed a fixture with a package version carrying a known published advisory and confirm "
   "BOTH sources report it; a source that stays silent on the known-bad case measures nothing"],
  R_FRESH, RT_DECAY, ["decay", "detector-failure", "egress-blocked"], False)

u("license-inventory",
  "License inventory for every direct and transitive dependency",
  "What is the resolved SPDX license for every package in the closure, which are unresolved or ambiguous, "
  "and which are incompatible with a public marketplace distribution?",
  ["the transitive closure from AUD-0022", "each package's license metadata and LICENSE file",
   "the intended distribution license for the plugin"],
  ["B01", "AUD-0022"], M_AUD, ["Read", "Grep", "Bash", "WebFetch"], "local-parallel", 3000, SCHEMA["inv"],
  "Probe 1: the declared license field in package metadata. Probe 2: the actual LICENSE file text classified "
  "independently, because a declared MIT with a GPL LICENSE file on disk is a real and common divergence.",
  ["control: a fixture whose metadata says MIT and whose LICENSE file is AGPL must be flagged as a "
   "declared-versus-actual conflict, not silently resolved to either"],
  R_TWO, RT_2S, ["detector-failure", "owner-blocked"], True)

u("unpinned-version-census",
  "Unpinned and floating version census and its reproducibility impact",
  "Which dependencies are declared with a floating constraint that allows a different resolution tomorrow, "
  "and for each, what is the blast radius if it resolves to a new major?",
  ["all dependency manifests", "the resolved versions today", "each package's release cadence"],
  ["B01", "AUD-0020", "AUD-0021"], M_AUD, ROB, "local-parallel", 1500, SCHEMA["finding"],
  "Probe 1: constraint-syntax classification per declaration (exact, compatible, caret, tilde, wildcard, none). "
  "Probe 2: two resolutions taken at different times or with different resolver seeds, showing whether the "
  "constraint actually floats in practice rather than only in theory.",
  ["control: a fixture with an exact pin must produce identical resolutions across both runs; if it does not, "
   "the resolution probe is contaminated"],
  R_FRESH, RT_2S, ["detector-failure", "decay"], False)

u("runtime-vs-dev-split",
  "Runtime versus development dependency split: what a shipped package would actually require",
  "If the plugin were packaged today, exactly which dependencies would a consumer be forced to install, and "
  "which of those are only needed by tests, linters, or the development harness?",
  ["dependency class declarations", "the actual import graph of the shippable modules",
   "the packaging configuration include/exclude rules"],
  ["B01", "AUD-0020", "AUD-0030"], M_AUD, ROB, "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: the declared prod/dev split in the manifests. Probe 2: the IMPORT graph of shippable modules only - "
  "a declared dev dependency that a shipped module imports is a packaging defect that the declaration hides.",
  ["control: a shipped fixture module importing a dev-only package must be flagged; a test-only import of the "
   "same package must NOT be flagged"],
  R_XV, RT_UPSTREAM, ["detector-failure", "scope-mismatch"], False)

u("native-platform-dep-census",
  "Native, compiled, and platform-wheel dependency census",
  "Which dependencies require a compiler, a platform-specific wheel, or a native runtime, and on which of the "
  "declared support platforms would each fail to install?",
  ["the transitive closure from AUD-0022", "each package's wheel availability matrix",
   "the declared support contract"],
  ["B01", "AUD-0022"], M_AUD, ["Read", "Grep", "Bash", "WebFetch"], "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: the wheel tag matrix published for each package. Probe 2: an actual install attempt into a clean "
  "environment on at least one non-Windows target, because a published wheel tag is not proof the install "
  "resolves under the pinned Python.",
  ["control: attempt an install of a package known to be source-only and confirm the probe reports a "
   "compiler requirement rather than a clean pass"],
  R_FRESH, RT_2S, ["dependency-blocked", "detector-failure"], False)

u("external-cli-tool-census",
  "External CLI tool dependency census with cross-shell resolution divergence",
  "Which external command-line tools does the codebase invoke, is each present, at what version, and does "
  "PowerShell resolve it to a different binary than Git Bash does?",
  ["every subprocess or shell invocation in the codebase",
   "Get-Command output in pwsh7 and command -v output in git-bash for each tool",
   "the measured case where git-bash which missed a .cmd shim and where bash resolved to WSL"],
  ["B01"], M_AUD, ROBP, "local-serialized", 1800, SCHEMA["finding"],
  "Probe 1: Get-Command <tool> in PowerShell 7 reporting the resolved Source path. Probe 2: command -v <tool> "
  "in Git Bash reporting its path. A divergence between the two resolved PATHS is the finding, not the "
  "presence bit.",
  ["both-states control: the pair must report DIFFERENT paths for bash itself (WSL versus MSYS) - if the two "
   "probes agree on bash, one of them is not actually running in the shell it claims"],
  R_XV, RT_SHELL, ["shell-quoting", "detector-failure", "single-signal"], False)

u("language-floor-audit",
  "Declared versus actually-required language version floor",
  "What is the lowest Python and Node version the code actually runs on, measured by syntax and API usage, and "
  "does it match the declared requires-python and engines fields?",
  ["declared requires-python and engines fields",
   "AST-level syntax feature usage across the codebase",
   "stdlib API introduction versions for every symbol used"],
  ["B01"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: an AST scan mapping used syntax and stdlib symbols to their introduction version. Probe 2: an "
  "actual import and test run under the declared FLOOR interpreter, because a static scan misses runtime-only "
  "features and a passing run on the current interpreter proves nothing about the floor.",
  ["control: run the same scan against a file using a feature newer than the declared floor and confirm it is "
   "flagged; a scan that passes that file is not reading versions"],
  R_FRESH, RT_2S, ["detector-failure", "dependency-blocked"], False)

# ------------------------------------------- Lane D: internal artifact and code dependency graph
u("import-graph-cycles",
  "Python import graph of tools/ with cycle detection",
  "What is the module-level import graph across tools/ and tools/lib/, does it contain any import cycle, and "
  "which modules sit on the highest-fan-in paths?",
  ["every .py file under tools/", "AST import statements including deferred and conditional imports"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["graph"],
  "Probe 1: an AST-derived import graph with strongly-connected-component detection. Probe 2: a runtime "
  "import trace (import each module in a fresh interpreter and record sys.modules deltas), which catches "
  "dynamic imports the AST scan cannot see.",
  ["control: plant a two-module cycle in a fixture and require the SCC detector to report exactly one cycle "
   "of length 2"],
  R_FRESH, RT_2S, ["detector-failure"], False)

u("salvage-consumption-verify",
  "Verify the tools/lib salvage actually acquired consumers",
  "For each of the 6 modules salvaged into tools/lib/, which non-test callers import it today - and if a "
  "module has zero non-test consumers, did the salvage decision achieve anything measurable?",
  ["tools/lib/ modules and their 72 tests",
   "the owner decision that salvage home = tools/lib/ shared tree",
   "the full import graph from AUD-0030"],
  ["B01", "AUD-0030"], M_AUD, ROB, "local-parallel", 1500, SCHEMA["finding"],
  "Probe 1: reverse-reference search over the import graph, excluding test modules. Probe 2: a runtime "
  "coverage trace of the non-test entry points recording which tools/lib modules are actually executed - an "
  "import is not a use.",
  ["use-vs-mention control: a module named only inside a docstring or a comment must NOT count as a consumer; "
   "assert on a fixture containing exactly that"],
  R_XV, RT_2S, ["use-vs-mention", "overclaim", "detector-failure"], False)

u("dead-code-census",
  "Unreferenced-module and dead-code census with a use-versus-mention-safe detector",
  "Which modules, functions, and CLI entry points in the repo have no reference from any entry point, test, "
  "CI step, or documentation command - counting only real references, never textual mentions?",
  ["the import graph from AUD-0030", "CI workflow command lines",
   "documented commands in RUNBOOK and README files"],
  ["B01", "AUD-0030"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["inv"],
  "Probe 1: AST-level symbol reference resolution. Probe 2: a dynamic reachability trace from every declared "
  "entry point plus every CI step, because a module reached only through a string-named plugin registry is "
  "invisible to the AST pass.",
  ["planted control: a module referenced ONLY by a string in a registry must be reported as LIVE by probe 2 "
   "and DEAD by probe 1 - if both agree, the pair is not independent"],
  R_XV, RT_2S, ["use-vs-mention", "detector-failure", "overclaim"], False)

u("doc-path-reference-integrity",
  "Documentation-to-path reference integrity sweep",
  "Does every filesystem path cited in a command-center document, rule, skill, or README resolve to a file "
  "that exists at that path today?",
  ["every markdown and json artifact in the repo and the live harness trees",
   "extracted path-like tokens with their citing file and line"],
  ["B01"], M_TOOL, ROB, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: extract path tokens and test existence. Probe 2: for each MISSING path, a git log --all search "
  "for the path, which separates never-existed (a typo) from deleted (a real dangling reference) - the "
  "existence test alone conflates them.",
  ["detector control: the extractor must find a path inside a markdown code fence and must NOT emit a false "
   "path from a prose sentence containing a slash; assert both on one fixture"],
  R_FRESH, RT_SCOPE, ["use-vs-mention", "path-length", "detector-failure"], False)

u("option-id-crossref-resolution",
  "Option-ID cross-reference resolution across the whole corpus",
  "For each of the 58 unsettled bare M-NN references in docs 16, 18 and 19, and every M-NN token elsewhere on "
  "disk, which of the four known namespaces does it belong to - or is it genuinely undecidable from context?",
  ["07-OPTION-UNIVERSE family M (33 ids)", "13-ARCHITECTURE-CANDIDATES MECH-NN (38 cards, re-prefixed 2026-08-07)",
   "wave3 deep-research SKILL.md:16 Research Harness (M-16)", "wave1/REGISTER.md:304 single-digit M-1/M-3",
   "17-DECISION-LOG.md, which contains zero MECH tokens"],
  ["B01"], M_NORM, ROB, "local-parallel", 3600, SCHEMA["finding"], ph="1")
U[-1]["ev"] = ("Probe 1: a mechanical namespace resolver keyed on surrounding discriminating tokens (MECH, "
               "mechanism, option, harness, mission-grade). Probe 2: for every reference the resolver cannot "
               "decide, an explicit UNDECIDABLE verdict with the two candidate meanings printed side by side - "
               "guessing is banned, because LLM classification of a mechanical comparison measured 86 percent "
               "on this estate with 100 percent of errors pointing at data loss.")
U[-1]["ts"] = ["control: the resolver must correctly resolve the 31 historically colliding ids in their "
               "pre-fix form and must return UNDECIDABLE, not a guess, on a synthetic reference with no "
               "discriminating token"]
U[-1]["rev"] = R_TWO
U[-1]["rt"] = RT_2S
U[-1]["fc"] = ["detector-failure", "overclaim", "stale-premise"]
U[-1]["oa"] = True

u("blocker-as-failing-test",
  "Capture the option-ID resolution blocker as an executable failing test",
  "Write a test that FAILS today because 17-DECISION-LOG.md line 175 states the M-NN collision in present "
  "tense while carrying zero MECH tokens, and that PASSES only once the decision log is reconciled.",
  ["17-DECISION-LOG.md:175", "the AUD-0034 resolution map", "spec _USER-PROMPTS.md:10656"],
  ["B01", "AUD-0034"], M_TOOL, FULLE, "worktree-isolated", 1800, SCHEMA["failtest"],
  "Probe 1: run the new test on the current tree and record a RED result with its assertion message. Probe 2: "
  "run the same test against a scratch copy of the decision log with the reconciliation applied and record "
  "GREEN - a test that is red in both states, or green in both, measures nothing.",
  ["the both-states run IS the test of the test: RED on current HEAD and GREEN on the patched scratch copy, "
   "both recorded verbatim in the receipt"],
  R_XV, RT_NORETRY, ["detector-failure", "green-not-live"], False)

u("artifact-manifest-reconcile",
  "ARTIFACT-MANIFEST versus disk bidirectional reconciliation",
  "Which manifest entries name a file that does not exist, and which files under command-center/ are absent "
  "from the manifest - measured in both directions with hashes, not names?",
  ["command-center/ARTIFACT-MANIFEST.json", "every file under command-center/",
   "the recorded provenance hashes and the REACH-6 Windows CRLF portability defect"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["drift"],
  "Probe 1: manifest-to-disk existence plus sha256 of the COMMITTED BLOB via git cat-file -p. Probe 2: "
  "disk-to-manifest coverage. Hashing the working tree instead of the blob is the known REACH-6 defect and "
  "must be avoided, not reproduced.",
  ["control: hash one known file by both routes (worktree bytes and blob bytes) and assert the receipt "
   "records BOTH values plus which one the manifest matches"],
  R_FRESH, RT_2S, ["eol-artifact", "detector-failure", "partial-artifact"], False)

u("claim-evidence-anchor-resolution",
  "CLAIM-REGISTRY evidence-anchor resolution: does each file:line say what is claimed",
  "For every claim in CLAIM-REGISTRY.json, does its cited file:line exist today, and does the text at that "
  "line actually support the claim rather than merely mention its subject?",
  ["command-center/CLAIM-REGISTRY.json", "every cited file at the cited revision"],
  ["B01"], M_AUD, ROB, "local-parallel", 3000, SCHEMA["finding"], ph="1")
U[-1]["ev"] = ("Probe 1: mechanical resolution - the file exists and has at least that many lines. Probe 2: a "
               "semantic read of the cited span judging support versus mention, reported as SUPPORTS, "
               "MENTIONS-ONLY, or CONTRADICTS. Probe 1 passing while probe 2 says MENTIONS-ONLY is the "
               "high-value finding.")
U[-1]["ts"] = ["control: plant a claim citing a line that contains only the subject word and confirm it is "
               "classified MENTIONS-ONLY rather than resolved"]
U[-1]["rev"] = R_XV
U[-1]["rt"] = RT_2S
U[-1]["fc"] = ["use-vs-mention", "overclaim", "detector-failure"]
U[-1]["oa"] = False

u("test-registry-resolution",
  "TEST-REGISTRY entries resolved to real collectible test node IDs",
  "Does every entry in TEST-REGISTRY.json resolve to a test that pytest or the relevant runner can actually "
  "collect and execute today?",
  ["command-center/TEST-REGISTRY.json", "pytest --collect-only output for the whole tree",
   "any non-pytest runner registries"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["drift"],
  "Probe 1: string match of registry node IDs against the collector output. Probe 2: an actual single-node "
  "execution of a stratified sample, because a node can be collectible and still error at setup.",
  ["control: add a registry entry for a nonexistent node and confirm the resolver reports it missing rather "
   "than counting it as present"],
  R_FRESH, RT_2S, ["detector-failure", "partial-artifact"], False)

u("catalog-edge-integrity",
  "WORK-UNIT-CATALOG edge integrity: existence, acyclicity, and reachability",
  "Does every dependency edge in WORK-UNIT-CATALOG.json name an id that exists, is the edge set acyclic, and "
  "is every unit reachable from a terminal disposition?",
  ["command-center/WORK-UNIT-CATALOG.json items and their dependencies",
   "the contract reachability rule (every item reachable from a final disposition)"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1500, SCHEMA["graph"],
  "Probe 1: id-existence and topological sort over the declared edges. Probe 2: an independently recomputed "
  "reachability closure from the terminal dispositions, so a unit reachable only through a dangling id cannot "
  "be counted as reachable.",
  ["control: introduce a two-unit cycle and a dangling id in a scratch copy and require the checker to report "
   "exactly one cycle and exactly one dangling id"],
  R_FRESH, RT_2S, ["detector-failure"], False)

u("depgraph-catalog-parity",
  "DEPENDENCY-GRAPH.json versus catalog parity and the byte-parity gate's own correctness",
  "Is DEPENDENCY-GRAPH.json still byte-derivable from WORK-UNIT-CATALOG.json by its generator, and does the "
  "CI byte-parity gate actually fail when the two diverge?",
  ["command-center/DEPENDENCY-GRAPH.json", "command-center/WORK-UNIT-CATALOG.json",
   "the generator in tools/command-center/", "the CI gate that enforces byte parity"],
  ["B01", "AUD-0039"], M_TOOL, ROB, "worktree-isolated", 1800, SCHEMA["detector"],
  "Probe 1: re-run the generator and byte-compare its output to the committed file. Probe 2: mutate the "
  "catalog in a scratch worktree and confirm the CI gate turns RED - a parity gate that has never been seen "
  "to fail is an unproven gate.",
  ["both-states control: the gate must exit 0 on the unmodified pair and non-zero after a one-byte catalog "
   "change; record both exit codes verbatim"],
  R_XV, RT_NORETRY, ["detector-failure", "green-not-live"], False)

# ---------------------------------------------------------------- Lane E: CI and gate current state
u("ci-step-inventory",
  "CI workflow, job, and step inventory: what each step actually executes",
  "For every workflow file, what is the complete ordered list of jobs and steps, the exact command each step "
  "runs, and which steps are conditional on a matrix value or an event type?",
  ["every file under .github/workflows/", "reusable workflow and composite action definitions"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1500, SCHEMA["inv"],
  "Probe 1: a YAML parse producing the ordered job and step table with resolved run commands. Probe 2: the "
  "GitHub Actions API job list for a recent real run, which reveals matrix expansion and skipped steps that "
  "the static YAML does not show.",
  ["control: the parser must expand a matrix job into its concrete legs; assert the leg count matches the "
   "API-reported leg count for one known run"],
  R_FRESH, RT_2S, ["detector-failure", "credential-absent"], False)

u("close-baseline-ci-gap",
  "Execute the 32 never-executed CI test steps and close the baseline gap",
  "Run the 32 of 60 CI-declared test steps that the Phase-0 baseline never executed, and record each outcome "
  "verbatim so the baseline covers 60 of 60 rather than 28 of 60.",
  ["the 60-step list from AUD-0041", "the recorded 28 executed steps and their 5326 passed / 8 failed result",
   "each step's exact command line"],
  ["B01", "AUD-0041"], M_TOOL, FULL, "worktree-isolated", 7200, SCHEMA["metric"],
  "Probe 1: the runner exit code per step. Probe 2: the parsed result summary from each step's own output "
  "(counts of passed, failed, errored) - an exit code alone is never success, and a step that collects zero "
  "tests can exit 0.",
  ["control: assert that at least one step reports a NON-ZERO collected count; a run where every step "
   "collects zero is a harness failure being reported as a pass"],
  R_XV, RT_UPSTREAM, ["partial-artifact", "green-not-live", "detector-failure"], False)

u("ci-local-invocation-parity",
  "CI-versus-local invocation parity and packaging/import-path exposure",
  "Does running the suite the way CI does (installed console script, installed package) produce the same "
  "result as running it the way the baseline did (python -m pytest against the source tree)?",
  ["the CI step command lines", "the baseline runner command", "the package entry-point declarations"],
  ["B01", "AUD-0041"], M_XV, FULL, "worktree-isolated", 3600, SCHEMA["detector"],
  "Probe 1: run the suite via python -m pytest from the source tree. Probe 2: pip install the built artifact "
  "into a fresh virtual environment and run the installed console script - by construction the source-tree "
  "run cannot detect a packaging or import-path regression.",
  ["both-states control: remove one module from the package include list in a scratch build and confirm the "
   "installed-run turns RED while the source-tree run stays GREEN"],
  R_FRESH, RT_NORETRY, ["green-not-live", "dependency-blocked", "detector-failure"], False)

u("required-context-audit",
  "Branch-protection required-context set versus the checks that actually run",
  "Which check contexts are REQUIRED by the branch protection ruleset, which contexts do the workflows "
  "actually produce, and where do those two sets disagree?",
  ["the branch protection ruleset for main", "the context names emitted by each workflow job",
   "the standing rule to gate merges on REQUIRED contexts only"],
  ["B01", "AUD-0041"], M_AUD, GH, "local-serialized", 1500, SCHEMA["drift"],
  "Probe 1: the ruleset required_status_checks list from the API. Probe 2: the distinct check-run names "
  "reported on a recent merged PR - a required context whose name no workflow emits is permanently pending "
  "and a produced context that is not required gates nothing.",
  ["control: confirm the comparator reports a non-empty symmetric difference on a deliberately renamed job in "
   "a scratch workflow"],
  R_FRESH, RT_2S, ["scope-mismatch", "credential-absent", "detector-failure"], False)

u("fail-open-gate-census",
  "Fail-open gate census: which gates can pass while measuring nothing",
  "For every CI gate and local validator, is there an input under which it exits 0 without having examined "
  "anything - an empty input set, a missing optional flag, a swallowed exception, or a skipped tool?",
  ["every gate script and CI step", "each gate's argument defaults",
   "the measured cases: validate.py require_complete defaulting to False, and a CLEAN plus checks:NONE gate"],
  ["B01", "AUD-0041"], M_REF, ROB, "local-parallel", 3000, SCHEMA["finding"],
  "Probe 1: a code read of each gate identifying every early-return and default-off path. Probe 2: an "
  "EXECUTION of each gate against an empty or absent input, recording exit code and whether it printed a "
  "measured count - a gate that exits 0 on empty input with no count is fail-open.",
  ["control: run each gate against a known-bad input and require non-zero; a gate that exits 0 on both empty "
   "and known-bad input is reported as measuring nothing"],
  R_FRESH, RT_2S, ["green-not-live", "detector-failure", "overclaim"], False)

u("gate-detector-control-sweep",
  "Detector-control sweep: plant a known-broken state and require every gate to fire",
  "For each gate, does a deliberately planted defect of the exact class the gate claims to detect make it "
  "turn RED - and does the gate stay GREEN on the unmodified tree?",
  ["the gate inventory from AUD-0041 and AUD-0045", "one planted mutation per gate, matched to its claim",
   "spec _USER-PROMPTS.md:10658 (verify detectors against known-broken and known-good controls)"],
  ["B01", "AUD-0045"], M_TOOL, FULLE, "worktree-isolated", 5400, SCHEMA["detector"],
  "Probe 1: gate exit code on the unmodified scratch worktree (must be 0). Probe 2: gate exit code with the "
  "planted mutation applied (must be non-zero). Both readings are required; either alone measures nothing.",
  ["the sweep IS the both-states test; additionally require that the mutation is reverted and the gate "
   "returns to 0, proving the RED was caused by the mutation and not by scratch-tree contamination"],
  R_XV, RT_NORETRY, ["detector-failure", "green-not-live"], False)

u("workflow-path-filter-audit",
  "Path-filter audit: triggers that exclude the very files the gate protects",
  "For every workflow with a paths or paths-ignore filter, is there a file the gate claims to protect that "
  "the filter would prevent the gate from ever seeing?",
  ["workflow on.push and on.pull_request path filters", "each gate's declared protected file set"],
  ["B01", "AUD-0041"], M_REF, ROB, "local-parallel", 1500, SCHEMA["finding"],
  "Probe 1: evaluate each filter pattern against the gate's protected file list. Probe 2: search recent real "
  "runs for a commit that touched a protected file and confirm the gate job actually ran on it - the pattern "
  "evaluation is the model and the run history is the receipt.",
  ["control: the evaluator must report a miss for a protected file deliberately excluded by a paths-ignore "
   "entry in a fixture workflow"],
  R_FRESH, RT_2S, ["scope-mismatch", "green-not-live"], False)

u("action-pinning-permissions",
  "Third-party GitHub Action pinning and token-permission audit",
  "Is every third-party action pinned to a full commit SHA rather than a tag, and does every workflow declare "
  "a least-privilege permissions block rather than inheriting the default token scope?",
  ["every uses: line in every workflow", "every permissions block, job-level and workflow-level"],
  ["B01", "AUD-0041"], M_SEC, ROB, "local-parallel", 1200, SCHEMA["finding"],
  "Probe 1: syntactic classification of each uses: reference as sha-pinned, tag-pinned, or branch-pinned. "
  "Probe 2: resolve each tag to its current SHA and record it, so a later silent retag is detectable - the "
  "syntax check alone cannot tell you what the tag points at today.",
  ["control: a fixture with a branch-pinned action must be flagged at the highest severity, and a "
   "sha-pinned one must not be flagged"],
  R_FRESH, RT_2S, ["detector-failure", "decay"], False)

u("runner-matrix-vs-support",
  "Runner OS matrix versus the declared cross-platform support contract",
  "Which operating systems and client versions does the declared support contract promise, and which of those "
  "does CI actually exercise today?",
  ["the declared support contract in the charter and README", "the runs-on matrix of every workflow",
   "the measured Windows-only failures that CI on Linux never sees"],
  ["B01", "AUD-0041"], M_AUD, ROB, "local-parallel", 1200, SCHEMA["drift"],
  "Probe 1: the set difference between promised platforms and runs-on values. Probe 2: for each promised "
  "platform absent from CI, name at least one already-measured defect that only that platform exposes - "
  "an unexercised platform with a known live defect is a different severity from one with none.",
  ["control: confirm the comparator flags Windows as promised-but-underexercised given the three recorded "
   "Windows-only CRLF failures; if it reports full coverage, it is not reading the matrix"],
  R_FRESH, RT_2S, ["scope-mismatch", "green-not-live"], False)

# ----------------------------------------------------------------- Lane F: test-suite current state
u("test-gate-coverage-map",
  "Test-file inventory and gate-coverage map: which suites are in no gate at all",
  "Which test files exist in the repo, and for each, which CI gate (if any) would execute it on a pull "
  "request touching its module?",
  ["every test file in the tree", "the CI step inventory from AUD-0041",
   "the measured precedent that 162 of 244 suites ran in no CI gate"],
  ["B01", "AUD-0041"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["drift"],
  "Probe 1: map each test path to the CI steps whose selector would collect it. Probe 2: run each candidate "
  "CI step with --collect-only and take the UNION of actually-collected node IDs - the selector model is the "
  "claim and the collection output is the receipt.",
  ["control: a test file deliberately placed outside every selector must appear in the orphan list; if the "
   "orphan list is empty on that fixture, the mapper is not discriminating"],
  R_XV, RT_UPSTREAM, ["green-not-live", "detector-failure"], False)

u("coverage-baseline",
  "Coverage baseline and per-project threshold enforcement state",
  "What is the measured line and branch coverage per project today, does each project have a "
  ".coverage-thresholds.json, and does its declared enforcement command actually run?",
  ["every .coverage-thresholds.json in the tree",
   "the measured fact that the only one within ~/source depth 3 is qzp-lean",
   "each project's test command"],
  ["B01"], M_TOOL, FULL, "worktree-isolated", 5400, SCHEMA["metric"],
  "Probe 1: run each project's declared enforcement command and capture the coverage report. Probe 2: for "
  "projects with NO thresholds file, emit NOT-CHECKED explicitly rather than a pass - folding absence into a "
  "silent pass is the banned outcome.",
  ["control: run coverage WITHOUT the --coverage flag on one project and confirm the harness reports "
   "NOT-CHECKED rather than a number, proving it cannot mistake a missing measurement for a good one"],
  R_FRESH, RT_UPSTREAM, ["partial-artifact", "overclaim", "detector-failure"], False)

u("test-order-dependence",
  "Order-dependence and flake census via shuffled and repeated runs",
  "Which tests pass in declaration order but fail under a shuffled order, and which produce a different "
  "result across repeated identical runs?",
  ["the full collectible test set", "a seeded shuffle plugin", "N repeated identical runs"],
  ["B01", "AUD-0051"], M_TOOL, FULL, "worktree-isolated", 7200, SCHEMA["finding"],
  "Probe 1: three shuffled runs with distinct recorded seeds. Probe 2: five identical-order repeats, which "
  "separates order dependence from nondeterminism - a single shuffled failure cannot distinguish the two.",
  ["control: the shuffle plugin must actually reorder; assert the recorded collection order differs between "
   "seeds, otherwise a green result means the shuffle never happened"],
  R_FRESH, RT_UPSTREAM, ["concurrency-contention", "detector-failure"], False)

u("network-egress-census",
  "Network-egress dependency census across the test suite",
  "Which tests reach the network during execution, whether or not they claim to be hermetic, and what do they "
  "fetch?",
  ["the full test suite", "an egress-blocking execution environment",
   "the measured precedent of 14 tests silently downloading get-pip.py despite comments saying otherwise"],
  ["B01", "AUD-0051"], M_TOOL, FULL, "worktree-isolated", 5400, SCHEMA["finding"],
  "Probe 1: run the suite with egress blocked and record every test that changes outcome. Probe 2: a socket-"
  "level trace on an unblocked run naming the destination hosts - the blocked run finds tests that DEPEND on "
  "the network and the trace finds tests that merely TOUCH it.",
  ["both-states control: the blocked environment must be proven to block - assert that a deliberate fetch "
   "fails inside it before trusting any test that passes there"],
  R_XV, RT_NORETRY, ["egress-blocked", "detector-failure", "green-not-live"], False)

u("platform-conditional-tests",
  "Platform-conditional test census: Windows-only and POSIX-only suites",
  "Which tests are gated on a platform condition, which platform each requires, and how many tests are "
  "therefore never executed on any CI runner in the current matrix?",
  ["skipif and platform-guard markers across the suite", "the CI runs-on matrix from AUD-0049"],
  ["B01", "AUD-0049"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["inv"],
  "Probe 1: an AST scan of skip and skipif decorators resolving the platform predicate. Probe 2: a diff of "
  "collected-versus-executed node IDs from a real run on each available platform, which catches runtime skips "
  "that no decorator declares.",
  ["control: a runtime-only skip (raised inside the test body) must be found by probe 2 and missed by probe 1; "
   "if both find it, the pair is not independent"],
  R_FRESH, RT_2S, ["scope-mismatch", "detector-failure"], False)

u("skip-xfail-reason-audit",
  "Skip and xfail census with reason validity",
  "For every skipped or xfail-marked test, is the stated reason still true today, and how many are permanently "
  "disabled tests masquerading as temporary?",
  ["every skip and xfail marker with its reason string", "the referenced issue or condition for each",
   "marker age from git blame"],
  ["B01", "AUD-0051"], M_AUD, ROB, "local-parallel", 1800, SCHEMA["finding"],
  "Probe 1: extract each marker with its reason and its git blame age. Probe 2: for a stratified sample, "
  "REMOVE the marker in a scratch worktree and run the test - the only way to know whether the stated reason "
  "still holds is to try it.",
  ["control: an xfail whose underlying bug is fixed must show as XPASS when unmarked; assert at least the "
   "sample is executed rather than reasoned about"],
  R_FRESH, RT_2S, ["stale-premise", "detector-failure"], False)

u("test-runtime-profile",
  "Test-runtime profile and slowest-suite baseline",
  "What is the wall-clock cost of each test module today, which are the slowest, and which are candidates for "
  "the soak and load lanes rather than the per-PR gate?",
  ["a --durations run over the full suite", "per-module aggregate timings"],
  ["B01", "AUD-0051"], M_TOOL, FULL, "worktree-isolated", 5400, SCHEMA["metric"],
  "Probe 1: the runner's own --durations report. Probe 2: an external wall-clock measurement per module "
  "invoked separately, because the in-runner report excludes collection and fixture setup attributed elsewhere.",
  ["record the profile twice and require the ranking of the top 10 to be stable; an unstable ranking means "
   "the measurement is contention-dominated and cannot be used as a baseline"],
  R_FRESH, RT_UPSTREAM, ["concurrency-contention", "detector-failure"], False)

u("assertion-strength-census",
  "Assertion-strength census: tests that never exercise the default they claim to protect",
  "Which tests pass an argument explicitly on every path such that the function's DEFAULT value is never "
  "exercised - the exact shape that let a 1024-to-512 default change survive a 15-of-15 green suite?",
  ["every test call site and the signature defaults of the functions under test",
   "the recorded DEFAULT_MIN_BYTES mutation that survived a green suite"],
  ["B01", "AUD-0051"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: an AST pass computing, per parameter with a default, whether any test invokes the function "
  "without supplying it. Probe 2: for the highest-risk findings, an actual value mutation of the default in a "
  "scratch worktree, requiring the suite to stay GREEN to confirm the hole.",
  ["both-states control: mutate a default that IS covered and require the suite to turn RED, proving the "
   "mutation harness can produce a red at all"],
  R_XV, RT_NORETRY, ["detector-failure", "overclaim", "green-not-live"], False)

# ------------------------------------------------------------- Lane G: harness runtime current state
u("skill-load-trigger-audit",
  "Skill inventory and frontmatter load-trigger correctness",
  "For every skill, does its frontmatter cause the intended load behaviour - always-on for those with no "
  "paths key, lazy for those with one - and which skills were unintentionally demoted by adding a paths glob?",
  ["every SKILL.md frontmatter in the live and repo skill trees",
   "the measured inversion: the 8 files with NO frontmatter are exactly the 8 injected at turn 0",
   "grok inspect --json or the equivalent direct load measurement"],
  ["B01"], M_AUD, ROB, "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: parse the frontmatter of every skill and classify its declared load class. Probe 2: a DIRECT "
  "measurement of which files are actually injected at turn 0 - the inference about load behaviour must lose "
  "to the direct measurement when they disagree.",
  ["control: the direct measurement must be shown to name at least one known always-on file; a measurement "
   "returning an empty always-on set is a broken instrument, not evidence of lazy loading"],
  R_XV, RT_2S, ["stale-premise", "single-signal", "detector-failure"], False)

u("hook-firing-evidence",
  "Hook firing evidence: registered is not the same as firing",
  "For each registered hook, is there direct evidence it fired during a real turn, and for those with none, "
  "does a deliberate trigger event produce an observable effect?",
  ["the manifest parity result from AUD-0013", "hook log or ledger output from recent turns",
   "a controlled trigger event per hook type"],
  ["B01", "AUD-0013"], M_AUD, ROBP, "local-serialized", 2400, SCHEMA["detector"],
  "Probe 1: search the hook logs and event ledger for per-hook fire records. Probe 2: perform a controlled "
  "trigger and observe the effect (an injected context line, a blocked call, a written ledger row) - log "
  "silence alone cannot distinguish a hook that never fires from one that fires silently.",
  ["both-states control: disable one hook in a scratch config, confirm the trigger produces NO effect, "
   "re-enable, and confirm it does"],
  R_XV, RT_NORETRY, ["green-not-live", "detector-failure", "single-signal"], False)

u("mcp-tool-surface-inventory",
  "MCP tool-surface inventory: which tools each configured server exposes and at what cost",
  "For every configured MCP server, how many tools does it expose, what is the token cost of those tool "
  "definitions, and which of them does this program actually need?",
  ["the resolved server list from AUD-0015", "each server's tool listing",
   "the program's declared tool requirements"],
  ["B01", "AUD-0015"], M_AUD, ROP, "local-parallel", 2400, SCHEMA["metric"],
  "Probe 1: the tool count and serialized schema size per server. Probe 2: a usage trace over recent sessions "
  "recording which tools were actually invoked - a large exposed surface with zero invocations is a different "
  "finding from one that is heavily used.",
  ["control: confirm the counter reports a non-zero tool count for a server known to be connected; a zero "
   "across all servers means the enumerator is not reaching them"],
  R_FRESH, RT_2S, ["detector-failure", "scope-mismatch"], False)

u("mcp-process-multiplication",
  "MCP live process census and per-session multiplication cost",
  "How many MCP server processes are alive right now, how many are attributable to each session, and what is "
  "the measured RAM and commit-charge cost of the per-session stdio duplication?",
  ["the live process table with parent-process attribution",
   "the number of concurrently open sessions",
   "the recorded commit-exhaustion incident (23 sessions x 65 servers = 2037 processes)"],
  ["B01", "AUD-0015"], M_AUD, ROP, "local-serialized", 1800, SCHEMA["metric"],
  "Probe 1: the process table grouped by parent session with working-set totals. Probe 2: the system commit "
  "charge and pagefile usage, because RAM alone hides the commit-exhaustion failure mode that actually freezes "
  "the box.",
  ["control: the probe must not match its OWN command line - assert the reported process set excludes any "
   "process whose creation time equals this probe's start time"],
  R_XV, RT_2S, ["detector-failure", "use-vs-mention", "concurrency-contention"], False)

u("always-on-context-budget",
  "Always-on injected-context budget measured in tokens",
  "What is the exact token cost of everything injected into turn 0 - CLAUDE.md, AGENTS.md, unfrontmattered "
  "rules, skill descriptions, tool schemas - and which single item dominates it?",
  ["the measured turn-0 injection set from AUD-0058", "a tokenizer for the target model",
   "per-file byte and token counts"],
  ["B01", "AUD-0058"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["metric"],
  "Probe 1: tokenize each injected file and sum. Probe 2: compare that sum against the session's reported "
  "context occupancy at turn 0, which is a completely different instrument and will expose anything the "
  "file-level enumeration missed.",
  ["control: the two numbers must be within a stated tolerance; a large unexplained gap means the injection "
   "set is incomplete and the enumeration must not be reported as a budget"],
  R_FRESH, RT_2S, ["detector-failure", "partial-artifact"], False)

u("agent-roster-model-audit",
  "Agent roster inventory and model-assignment audit",
  "Which agent definitions exist, what model does each declare, and which substantive roles are assigned a "
  "model below the opus floor for dispatch-judgement work?",
  ["every agent definition and its frontmatter model field",
   "the standing preference that substantive subagents default to Opus",
   "the cross-vendor-dispatch rule that a dispatching agent must never be sonnet"],
  ["B01"], M_AUD, ROB, "local-parallel", 1200, SCHEMA["finding"],
  "Probe 1: frontmatter model field extraction per agent. Probe 2: classify each agent as dispatching or "
  "non-dispatching from its declared tool permissions (does it hold a subagent-spawning or cross-vendor tool), "
  "since the floor applies specifically to dispatchers.",
  ["control: an agent that merely mentions a model name in its prose body must not be classified by that "
   "mention; assert on a fixture containing exactly that"],
  R_FRESH, RT_2S, ["use-vs-mention", "detector-failure"], False)

u("monitor-surface-reachability",
  "Monitor and cockpit surface inventory and reachability",
  "Which monitors exist, which are wired into the mon dispatcher, and which of those actually render live "
  "data rather than an empty or stale pane?",
  ["the mon dispatcher routing table", "every monitor renderer script",
   "the 2026-08-09 observation that 5 panes render via mon cockpit"],
  ["B01"], M_AUD, ROP, "local-serialized", 1800, SCHEMA["finding"],
  "Probe 1: the dispatcher routing table enumerated statically. Probe 2: launch each route once and assert a "
  "non-empty, changing render - a pane that renders a fixed empty frame is indistinguishable from a working "
  "one on a static screenshot.",
  ["control: point one monitor at a deliberately empty data source and confirm it is reported as EMPTY rather "
   "than OK; stall detection from mtimes alone is banned and must not appear in the receipt"],
  R_FRESH, RT_SHELL, ["green-not-live", "detector-failure"], False)

u("ledger-memory-state-inventory",
  "Event-ledger and basic-memory durable-state inventory",
  "What durable program state already exists in the event ledger and in basic-memory, which entries are "
  "relevant to this program, and which contradict the currently pinned ground truth?",
  ["~/.claude/event-ledger/", "basic-memory search over program-relevant terms",
   "the pinned ground-truth block for this program"],
  ["B01"], M_NORM, ["Read", "Grep", "Glob", "Bash", "mcp__basic-memory__search_notes",
                    "mcp__basic-memory__read_note", "mcp__basic-memory__recent_activity"],
  "local-serialized", 2400, SCHEMA["claim"],
  "Probe 1: a keyword search over the ledger files. Probe 2: a semantic search over basic-memory - the two "
  "stores hold objective turn history and semantic decisions respectively and neither substitutes for the "
  "other.",
  ["control: search for a term known to be present in each store and confirm both return a hit before any "
   "empty result is reported as absence"])
U[-1]["rev"] = R_FRESH
U[-1]["rt"] = RT_2S
U[-1]["fc"] = ["stale-premise", "detector-failure", "single-signal"]
U[-1]["oa"] = False

u("scheduled-service-dependency",
  "Scheduled tasks and background services the program depends on",
  "Which Windows scheduled tasks and background services must be running for this program's rails to work, "
  "what is each one's current state, and what is the observed recovery behaviour when one dies?",
  ["the scheduled task list filtered to program-relevant tasks",
   "the MCPAgentMailSupervisor logon task and its health-poll behaviour",
   "any monitor or memory-guard daemon"],
  ["B01"], M_AUD, ROP, "local-serialized", 1800, SCHEMA["inv"],
  "Probe 1: the scheduled-task and service state as reported by the OS. Probe 2: an endpoint health check for "
  "each service that exposes one - a task reported as Running whose endpoint refuses connections is the "
  "finding, and the task state alone cannot show it.",
  ["control: confirm the health probe returns a failure for a deliberately wrong port before trusting any "
   "success it reports"],
  R_FRESH, RT_SHELL, ["green-not-live", "detector-failure"], False)

# ------------------------------------------- Lane H: corpus normalization inputs (Phase 1)
u("prompt-one-artifact-census",
  "Prompt-One artifact census with per-artifact tree location",
  "For each of the 29 contracted Prompt-One artifacts, which tree does it live in, and does the set of 29 hold "
  "within a SINGLE tree or only as the union of two?",
  ["the 29-artifact contract list", "the harness-restore corpus tree", "the repo tree",
   "the recorded caveat that 29/29 only holds as a union"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["inv"],
  "Probe 1: per-artifact existence test in each tree separately, reported as a per-tree count rather than a "
  "union count. Probe 2: sha256 comparison for artifacts present in both trees, so a divergent duplicate is "
  "not counted as one artifact.",
  ["control: the per-tree counts must be reported even when they are lower than 29; a harness that can only "
   "emit the union is incapable of finding this defect"],
  R_XV, RT_2S, ["overclaim", "scope-mismatch", "detector-failure"], False, "1")

u("claim-extraction-canonical",
  "Claim extraction from the corpus into canonical claim records",
  "Extract every material claim from the Prompt-One corpus into a canonical record carrying a stable claim ID, "
  "canonical mechanism, source lineage, confidence, and verification status.",
  ["all 29 Prompt-One artifacts", "the claim-record schema", "spec _USER-PROMPTS.md:10664-10677"],
  ["B01", "AUD-0067"], M_NORM, FULL, "local-parallel", 7200, SCHEMA["claim"],
  "Probe 1: extraction coverage - every heading and every verdict-tagged sentence in the source must map to at "
  "least one record or an explicit NOT-A-CLAIM decision. Probe 2: a reverse trace from a random sample of "
  "records back to their source span, confirming the record says what the source says.",
  ["control: plant a synthetic claim in a scratch copy of one artifact and require the extractor to produce a "
   "record for it; an extractor that misses a planted claim has unknown recall"],
  R_TWO, RT_UPSTREAM, ["partial-artifact", "overclaim", "detector-failure"], False, "1")

u("option-card-body-dedup",
  "Body-level deduplication over the 283 option cards",
  "Do any two of the 283 option cards describe the SAME mechanism under different ids and different wording - "
  "measured on card bodies, not on ids and titles?",
  ["the 283 option cards in 07-OPTION-UNIVERSE with full bodies",
   "the recorded residual that only ids and titles were compared, never bodies",
   "the recorded finding that lexical Jaccard cannot see a full rewrite"],
  ["B01", "AUD-0068"], M_TOOL, FULL, "local-parallel", 5400, SCHEMA["finding"],
  "Probe 1: lexical near-duplicate detection over card bodies with planted-mutant calibration. Probe 2: an "
  "embedding-cosine rescan using the SAME planted mutants as controls, because a full rewrite lands in the "
  "same lexical band as a genuinely distinct card.",
  ["planted-mutant control: insert an exact rename, a paraphrase, and a one-parameter fork; both probes must "
   "catch the rename, and the embedding probe must additionally catch the paraphrase"],
  R_XV, RT_UPSTREAM, ["detector-failure", "overclaim"], False, "1")

u("contradiction-edge-extraction",
  "Contradiction-edge extraction across corpus artifacts",
  "Which pairs of corpus claims directly contradict each other - for example a decision log stating a blocker "
  "in present tense while the referenced document shows it fixed?",
  ["the canonical claim records from AUD-0068",
   "17-DECISION-LOG.md:175 versus the 2026-08-07 MECH re-prefix of doc 13",
   "the four namespaces of M-NN"],
  ["B01", "AUD-0068"], M_NORM, ROB, "local-parallel", 3600, SCHEMA["graph"],
  "Probe 1: pairwise claim comparison producing candidate contradiction edges with the two spans quoted. "
  "Probe 2: an independent temporal check - if one claim postdates the other and describes the same object, "
  "the later one supersedes rather than contradicts, and the edge type must change accordingly.",
  ["control: the known decision-log-versus-doc-13 pair must be emitted as a SUPERSEDED edge, not merely a "
   "contradiction; an extractor that cannot distinguish the two edge types is under-specified"],
  R_TWO, RT_UPSTREAM, ["stale-premise", "detector-failure"], False, "1")

u("support-edge-graph",
  "Support-edge and independent-corroboration graph",
  "For each claim, which other claims independently support it, and how many of those supports are genuinely "
  "independent rather than derived from the same upstream source?",
  ["the canonical claim records", "the source lineage of each claim",
   "the standing rule to rank by independent evidence, not by how many agents repeated an idea"],
  ["B01", "AUD-0068", "AUD-0074"], M_NORM, ROB, "local-parallel", 3600, SCHEMA["graph"],
  "Probe 1: build support edges from explicit citation. Probe 2: collapse supports that share an upstream "
  "source into a single independent signal, then recount - the raw support count and the independent-source "
  "count are different numbers and only the second may be used for ranking.",
  ["control: a claim supported by five records all citing one upstream document must score as ONE independent "
   "support, not five; assert that exact case"],
  R_XV, RT_UPSTREAM, ["overclaim", "single-signal", "detector-failure"], False, "1")

u("confidence-status-normalization",
  "Confidence and verification-status normalization onto one vocabulary",
  "Map every confidence expression and verification status found in the corpus onto the single Sherman-Kent "
  "band plus verdict vocabulary, and list every expression that does not map cleanly.",
  ["all confidence phrases and verdict tags across the corpus",
   "the Sherman-Kent band definitions and the CONFIRMED/REFUTED/PARTIAL/NOT-CHECKED/BLOCKED vocabulary"],
  ["B01", "AUD-0068"], M_NORM, ROB, "local-parallel", 2400, SCHEMA["claim"],
  "Probe 1: lexical mapping of each phrase to a band. Probe 2: an unmapped-residue report listing every "
  "hedge that received no band - a normalizer that maps everything has almost certainly guessed, and the "
  "residue list is the honest output.",
  ["control: a bare should work with no band must land in the residue list, not be silently assigned likely"],
  R_FRESH, RT_UPSTREAM, ["overclaim", "detector-failure"], False, "1")

u("settling-probe-extraction",
  "Settling-probe extraction: every UNVERIFIED gets a named experiment",
  "For every UNVERIFIED or residual claim in the corpus, is there a named, runnable experiment that would "
  "settle it - and for those without one, what is the minimal experiment that would?",
  ["every UNVERIFIED tag and residual statement in the corpus",
   "the recorded distribution showing 40 percent of 127 flags sit in the final 15 percent of their document"],
  ["B01", "AUD-0068"], M_NORM, ROB, "local-parallel", 3600, SCHEMA["claim"],
  "Probe 1: extract each UNVERIFIED with its adjacent sentence and any named experiment. Probe 2: record the "
  "POSITION of each flag within its document, because a flag isolated in a trailing limitations section does "
  "not qualify the recommendation it should be attached to.",
  ["control: a flag placed inline next to its claim and an identical flag placed only in a trailing section "
   "must receive DIFFERENT position verdicts; a probe that scores them the same is not measuring position"],
  R_FRESH, RT_UPSTREAM, ["overclaim", "detector-failure"], False, "1")

u("source-lineage-graph",
  "Source-lineage graph: which artifact derives from which",
  "What is the derivation graph among the corpus artifacts, and which artifacts are downstream of a source "
  "that has since been corrected?",
  ["the 29 artifacts and their internal cross-references",
   "file creation and modification timestamps",
   "the known 2026-08-07 correction applied to doc 13"],
  ["B01", "AUD-0067"], M_NORM, ROB, "local-parallel", 2400, SCHEMA["graph"],
  "Probe 1: citation-derived edges between artifacts. Probe 2: a timestamp ordering check per edge, which "
  "flags any citation pointing at a version of the source that predates a known correction - the citation "
  "graph alone cannot see staleness.",
  ["control: the known doc-13 correction must produce at least one stale-downstream flag; zero flags on that "
   "known case means the timestamp check is inert"],
  R_FRESH, RT_UPSTREAM, ["stale-premise", "detector-failure"], False, "1")

u("stale-premise-sweep",
  "Stale-premise sweep over pinned ground-truth facts with mechanically different re-probes",
  "For each fact currently pinned as program ground truth, is it still true today when re-measured by a probe "
  "MECHANICALLY DIFFERENT from the one that produced it?",
  ["the pinned ground-truth block for this program",
   "the recorded precedent that four briefed VERIFIED GROUND TRUTH facts were false in one run",
   "the recorded precedent that two agents CONFIRMED a false fact by re-running the broken probe"],
  ["B01"], M_REF, ROBP, "local-serialized", 3600, SCHEMA["finding"],
  "Probe 1: for each pinned fact, a re-measurement using a different shell, a different data field, or a "
  "different instrument than the one named in the pin. Probe 2: an explicit record of WHICH probe produced "
  "the original claim - an undeclared source probe means zero signals, not one, and must be reported as such.",
  ["control: re-running the ORIGINALLY NAMED probe must be rejected by the harness rather than counted; "
   "assert the harness refuses a same-fingerprint re-probe"],
  R_TWO, RT_2S, ["stale-premise", "single-signal", "detector-failure"], False, "1")

u("owner-requirement-recovery",
  "Owner-requirement extraction from the transcript: which requirements disappeared",
  "Which owner requirements stated across the 375-message transcript are not represented in any current "
  "artifact, decision, or work unit?",
  ["_USER-PROMPTS.md (1.49 MB, 375 messages)", "OWNER-DECISIONS.md", "the full work-unit catalog",
   "spec _USER-PROMPTS.md:11073 (what owner requirements disappeared)"],
  ["B01", "AUD-0068"], M_NORM, ROB, "local-parallel", 5400, SCHEMA["finding"],
  "Probe 1: extract imperative owner statements from the transcript into a requirement list. Probe 2: for each "
  "requirement, a targeted search of the artifact corpus for a representing decision or unit, reported as "
  "REPRESENTED, SUPERSEDED, or DROPPED with the evidence for each verdict.",
  ["control: plant a synthetic requirement in a scratch transcript copy and confirm it is classified DROPPED; "
   "an extractor that classifies everything as represented has no discriminating power"],
  R_TWO, RT_UPSTREAM, ["overclaim", "detector-failure", "privacy-leak"], False, "1")

# ---------------------------------------------------- Lane I: security, privacy, secrets current state
u("secret-scan-repo-live",
  "Secret-exposure scan of the repository and the live harness trees (read-only)",
  "Does any tracked file, untracked file, or live harness file contain a credential-shaped value - and for "
  "each hit, is it a real secret or a placeholder?",
  ["the full repo tree including history", "the live harness trees",
   "gitleaks and an independent entropy-based scanner",
   "the standing rule: diagnose only, never rotate, never print a value"],
  ["B01"], M_SEC, ROBP, "local-serialized", 3600, SCHEMA["finding"],
  "Probe 1: gitleaks over the working tree and history. Probe 2: an independent entropy-plus-pattern scan, "
  "because the two disagree in both directions - one has rules the other lacks and each produces distinct "
  "false positives. Report the variable name and scope only; never the value.",
  ["control: plant a synthetic high-entropy token in a scratch copy and require BOTH scanners to find it; a "
   "scanner silent on the planted token cannot be trusted on a clean result"],
  R_TWO, RT_NORETRY, ["privacy-leak", "detector-failure", "owner-blocked"], True)

u("corpus-bundle-privacy-scan",
  "Secret and PII scan of the program corpus and command-center artifacts",
  "If the command-center and its corpus were bundled or published today, which files would carry a credential, "
  "a private path, an owner personal detail, or third-party private content?",
  ["command-center/ in full", "the harness-restore corpus", "the transcript excerpts embedded in artifacts",
   "the packaging include list"],
  ["B01", "AUD-0067"], M_SEC, ROB, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: a secret and PII scan over exactly the file set the packaging rules would include. Probe 2: a "
  "manual read of the highest-risk files identified by probe 1 - an automated PII classifier alone will both "
  "miss owner-specific context and over-flag benign paths.",
  ["control: the include-list resolver must be proven correct first - assert it excludes a file the packaging "
   "rules exclude and includes one they include, before any scan result is meaningful"],
  R_TWO, RT_NORETRY, ["privacy-leak", "scope-mismatch", "detector-failure"], True)

u("credential-consumer-audit",
  "Credential-consumer audit: which code reads which variable and how it fails",
  "For every environment variable or credential file the codebase reads, does the consumer validate presence "
  "at startup and fail loudly, or does it silently degrade to a wrong-but-quiet behaviour?",
  ["every os.environ / process.env read and credential-file open in the codebase",
   "each consumer's behaviour when the variable is absent or invalid",
   "the standing preference to fix the CONSUMER so a bad credential cannot break it"],
  ["B01"], M_SEC, ROBP, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: a static enumeration of credential reads with their surrounding validation. Probe 2: an actual "
  "execution of each entry point with the variable UNSET in a scratch environment, recording whether it errors "
  "loudly, errors obscurely, or proceeds silently.",
  ["both-states control: run each entry point with the variable set to a syntactically valid but wrong value "
   "and confirm the failure is distinguishable from the unset case"],
  R_XV, RT_NORETRY, ["credential-absent", "detector-failure", "green-not-live"], False)

u("permission-surface-audit",
  "Permission-surface audit: allow-lists and hook bypass paths",
  "Which command patterns are pre-approved in the permissions allow-lists across all settings scopes, and "
  "which of those would let a caller bypass a hook that is supposed to gate them?",
  ["permissions.allow and permissions.deny in every settings file scope",
   "each hook's matcher pattern",
   "the recorded false-positive class where a guard read a payload body instead of the tool verb"],
  ["B01", "AUD-0016"], M_SEC, ROP, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: enumerate allow entries per scope and compute the effective merged set. Probe 2: for each hook, "
  "construct a command that satisfies an allow entry while matching the hook's intent, and check whether the "
  "hook's matcher actually catches it - the config read is the model and the matcher test is the receipt.",
  ["use-vs-mention control: a command whose PAYLOAD quotes a dangerous string but whose VERB is benign must "
   "NOT be flagged; the two recorded false positives were exactly this shape"],
  R_XV, RT_2S, ["use-vs-mention", "scope-mismatch", "detector-failure"], False)

u("untrusted-autoload-config-audit",
  "Untrusted auto-loaded configuration audit in cloned and vendored trees",
  "Do any cloned, vendored, or agent-scratch trees under the estate carry a .claude, .codex, .mcp.json, hooks "
  "directory, AGENTS.md or CLAUDE.md that would auto-load the moment an agent runs inside them?",
  ["every directory under the estate that is a clone or vendored tree",
   "the auto-load config file name set",
   "the CVE-2026-47751-class precedent that a cloned repo can carry auto-loaded config AND hooks"],
  ["B01", "AUD-0009"], M_SEC, ROB, "local-serialized", 2400, SCHEMA["finding"],
  "Probe 1: a filename search for the auto-load set across every non-owner-authored tree. Probe 2: a content "
  "read of each hit classifying it as inert documentation versus an active hook or MCP registration - the "
  "presence of a file named CLAUDE.md is not by itself a risk finding.",
  ["control: the classifier must rate an AGENTS.md containing only prose as inert and one registering a "
   "PreToolUse command as active; assert both on one fixture"],
  R_TWO, RT_2S, ["detector-failure", "use-vs-mention", "owner-blocked"], True)

# ----------------------------------------------------------- Lane J: platform portability current state
u("windows-path-hazard-census",
  "Windows reserved-name, long-path, and case-collision census",
  "Which paths in the repo and corpus are a Windows reserved device name, exceed the 260-character limit, or "
  "collide with a sibling under case-insensitive comparison?",
  ["every path in the repo and the corpus trees",
   "the Windows reserved name set (NUL, CON, AUX, PRN, COM1-9, LPT1-9)",
   "the recorded crash where os.path.relpath failed on a file literally named NUL"],
  ["B01"], M_TOOL, ROBP, "local-serialized", 1800, SCHEMA["finding"],
  "Probe 1: a path-string classifier over the git index (which is case-sensitive and includes paths the OS "
  "may refuse to stat). Probe 2: a filesystem walk with the extended-length prefix, catching paths the index "
  "does not list. The enumerator must survive a NUL entry rather than crashing.",
  ["control: the enumerator must return a NON-ZERO count on a fixture containing a NUL-named file and a "
   "300-character path; a crash or a zero count is the known failure this unit exists to prevent"],
  R_XV, RT_SCOPE, ["path-length", "detector-failure", "partial-artifact"], False)

u("script-interpreter-audit",
  "Script interpreter and shebang audit",
  "For every executable script in the tree, which interpreter would actually run it on each supported "
  "platform, and which would be invoked bare on Windows where no interpreter is implied?",
  ["every .sh, .ps1, .py, .mjs and extensionless executable in the tree",
   "each invocation site (CI step, hook manifest, plugin manifest)",
   "the known failure class: bare .sh invocation on Windows"],
  ["B01"], M_AUD, ROBP, "local-serialized", 1800, SCHEMA["finding"],
  "Probe 1: shebang and extension classification per script plus the explicit interpreter at each call site. "
  "Probe 2: resolve what the OS would actually execute for a bare invocation in PowerShell 7 - which for a "
  ".sh file is not the shebang, because Windows does not read shebangs.",
  ["control: assert the resolver reports a FAILURE for a bare .sh invocation on Windows and a SUCCESS for the "
   "same script invoked with an explicit bash; a resolver that passes both is reading the shebang, not the OS"],
  R_XV, RT_SHELL, ["shell-quoting", "detector-failure", "green-not-live"], False)

u("hardcoded-path-census",
  "Hardcoded absolute path and path-separator census",
  "Which source files contain a hardcoded absolute path, a drive letter, a home directory, or a hardcoded "
  "path separator that would break on another platform or another user profile?",
  ["every source file in the tree", "path-literal patterns per language"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["finding"],
  "Probe 1: a literal-string scan for drive letters, /home/, /Users/, and backslash separators inside path "
  "contexts. Probe 2: an AST-aware pass that distinguishes a path literal from a regex or a documentation "
  "string, since a backslash in a regex is not a path separator.",
  ["use-vs-mention control: a regex containing a backslash and a docstring containing C: must NOT be flagged, "
   "while an open() on the same literal must be"],
  R_FRESH, RT_2S, ["use-vs-mention", "detector-failure"], False)

u("encoding-bom-mojibake-census",
  "Encoding, BOM, and mojibake census",
  "Which files are not valid UTF-8, carry a byte-order mark, or contain mojibake from a prior double-decode - "
  "and which of those are consumed by a strict parser?",
  ["every text file in the repo and corpus",
   "the consumer of each file (strict JSON/YAML parsers, the plugin manifest reader)",
   "the recorded mojibake repair class from the Meta export work"],
  ["B01"], M_TOOL, ROB, "local-parallel", 1800, SCHEMA["finding"],
  "Probe 1: a decode attempt per file recording BOM presence and any decode error. Probe 2: a mojibake "
  "detector gated on a control - the naive repair one-liner is subtly wrong and must be detector-gated and "
  "applied after parsing, never before.",
  ["control: the mojibake detector must fire on a known double-decoded fixture and stay silent on correctly "
   "encoded non-ASCII text; a detector that flags all non-ASCII is unusable"],
  R_FRESH, RT_SCOPE, ["encoding", "detector-failure"], False)

u("shell-quoting-hazard-census",
  "Shell-quoting hazard census in scripted command bodies",
  "Which scripted or generated command bodies in the codebase contain an apostrophe, a heredoc, a process "
  "substitution, or a caret that would be mangled by the shell that actually runs them?",
  ["every generated or templated shell command in the codebase",
   "the target shell for each (pwsh7, git-bash, sh in CI)",
   "the recorded classes: apostrophe breaking the Bash tool quoting, PowerShell caret escaping a git ref, "
   "and no process substitution in PowerShell"],
  ["B01"], M_TOOL, ROBP, "local-serialized", 1800, SCHEMA["finding"],
  "Probe 1: a pattern scan for the four hazard characters and constructs within command-string contexts. "
  "Probe 2: an actual round-trip execution of a representative sample through each target shell, comparing "
  "the received argv to the intended argv - the pattern scan predicts and the round trip proves.",
  ["control: the round trip must FAIL for a deliberately apostrophe-bearing command in the affected transport "
   "and SUCCEED for the same content passed as a file path"],
  R_XV, RT_SHELL, ["shell-quoting", "detector-failure"], False)

# ---------------------------------------------------------------------- Lane K: baseline metrics
u("startup-latency-baseline",
  "Install, import, and startup latency baseline",
  "What is the measured wall-clock cost today of a cold install, a first import, and a first command "
  "invocation - the numbers any later performance claim must be compared against?",
  ["a clean environment", "the install command", "the first-import and first-command entry points"],
  ["B01"], M_TOOL, FULL, "local-serialized", 3600, SCHEMA["metric"],
  "Probe 1: repeated timed runs reporting median and spread, not a single sample. Probe 2: a process-level "
  "trace attributing the time to install, resolve, import, and execute phases, so a later regression can be "
  "localized rather than merely observed.",
  ["control: the measurement must be taken with no other program job running; assert the machine load metric "
   "recorded alongside each sample, and discard samples taken under contention"],
  R_FRESH, RT_2S, ["concurrency-contention", "detector-failure"], False)

u("package-content-baseline",
  "Shipped-package content and size baseline",
  "If the plugin were built today, exactly which files and how many bytes would the artifact contain - and "
  "does it include .git, caches, logs, transcripts, or credentials?",
  ["the packaging configuration", "a real build into a scratch directory",
   "the spec prohibition at _USER-PROMPTS.md:10842"],
  ["B01"], M_TOOL, FULL, "worktree-isolated", 2400, SCHEMA["metric"],
  "Probe 1: the packaging tool's own file list. Probe 2: unpack the BUILT artifact and enumerate its real "
  "contents - the declared include list and the produced archive routinely disagree, and only the archive is "
  "the receipt.",
  ["control: the unpack enumeration must find a file the include list declares, and must flag any .git or "
   "credential-shaped path; assert on a build with a deliberately added stray file"],
  R_XV, RT_NORETRY, ["privacy-leak", "partial-artifact", "detector-failure"], False)

u("complexity-baseline",
  "Cyclomatic-complexity baseline per module",
  "What is the current complexity distribution across the codebase, which functions exceed the CCN 15 "
  "threshold, and what is the per-module baseline any later refactor must beat?",
  ["every source module", "lizard with a pinned version and -C 15"],
  ["B01"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["metric"],
  "Probe 1: the lizard report at the pinned version. Probe 2: a second analyzer (radon or the equivalent for "
  "each language) over the same set, because analyzers disagree on how they count branches and a single "
  "tool's ranking is not a baseline.",
  ["control: both analyzers must rank the same function as the most complex; if they disagree on the top "
   "entry, record the disagreement rather than reporting one number"],
  R_FRESH, RT_2S, ["detector-failure"], False)

u("static-analysis-baseline",
  "Static-analysis baseline counts with pinned tool versions",
  "What is the exact finding count per rule for ruff, semgrep, and bandit at PINNED versions against the "
  "COMMITTED BLOB bytes, so a later diff is meaningful?",
  ["the pinned tool versions used by CI",
   "the committed blob of every source file via git cat-file -p",
   "the measured CRLF case where a local green and a CI red disagreed on the same commit"],
  ["B01"], M_TOOL, ROB, "local-parallel", 3000, SCHEMA["metric"],
  "Probe 1: run each tool at its CI-pinned version against the blob bytes. Probe 2: run the same tools against "
  "the Windows working tree and record BOTH counts - the divergence between them is itself a finding, and "
  "reporting only the working-tree number reproduces the known false-confidence failure.",
  ["control: confirm the two runs produce different counts for at least one known CRLF-sensitive file; "
   "identical counts everywhere means the blob extraction silently returned worktree bytes"],
  R_XV, RT_2S, ["eol-artifact", "detector-failure", "green-not-live"], False)

u("clean-room-clone-baseline",
  "Clean-room fresh-clone build and test baseline",
  "Starting from a fresh clone into a clean directory with no local caches, does the documented setup, build, "
  "and test sequence succeed - and where exactly does it first diverge from the documentation?",
  ["a fresh clone of main at the pinned SHA", "the documented setup steps in README and RUNBOOK",
   "spec _USER-PROMPTS.md:10655"],
  ["B01", "AUD-0001"], M_XV, FULL, "worktree-isolated", 7200, SCHEMA["detector"],
  "Probe 1: execute the documented commands verbatim in the clean clone and record the first failing step "
  "with its output. Probe 2: compare the produced test result against the in-place baseline result, so an "
  "environment-only difference is distinguishable from a documentation defect.",
  ["control: the clean clone must be proven cache-free - assert the package cache directory is empty or "
   "redirected before the run, otherwise a cached artifact can make a broken setup appear to work"],
  R_FRESH, RT_NORETRY, ["dependency-blocked", "green-not-live", "detector-failure"], False)

# ------------------------------------------------------------------ Lane L: reversibility and freeze
u("rollback-backup-rehearsal",
  "Create rollback backups and rehearse a restore, copying no secrets into the corpus",
  "Create a restorable backup of every tree this program will mutate, then PROVE it restores by rehearsing a "
  "full restore into a scratch location and byte-comparing the result.",
  ["the list of trees the program will mutate", "a backup destination outside the program corpus",
   "spec _USER-PROMPTS.md:10659 (create rollback backups without copying secrets into the program corpus)"],
  ["B01", "AUD-0002", "AUD-0006"], M_TOOL, FULL, "local-serialized", 5400, SCHEMA["detector"],
  "Probe 1: a manifest of the backup with per-file sha256. Probe 2: an actual restore into a scratch path "
  "followed by a byte-level comparison against the source - an untested backup is a claim, not a rollback.",
  ["both-states control: delete a file from the scratch restore and confirm the comparison turns RED; a "
   "comparison that reports success on a damaged restore is measuring nothing"],
  R_TWO, RT_NORETRY, ["partial-artifact", "privacy-leak", "detector-failure"], True)

u("rollback-manifest-reality",
  "ROLLBACK-MANIFEST versus the actual reversibility of already-executed actions",
  "For each action this program has ALREADY executed - the DELETE-ALL of 77 files, the salvage into tools/lib, "
  "the worktree cleanup from 20 to 6 - does the rollback manifest describe a procedure that would actually "
  "restore the prior state?",
  ["command-center/ROLLBACK-MANIFEST.md", "the recorded executed actions and their commits",
   "the current tree state"],
  ["B01", "AUD-0092"], M_AUD, ROB, "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: read each manifest entry and check that every artifact it references still exists. Probe 2: "
  "rehearse the highest-risk entry in a scratch clone and record whether the prior state is byte-recovered - "
  "a documented procedure that has never been run is unverified.",
  ["control: rehearse one entry that is KNOWN to be irreversible and confirm the rehearsal reports failure "
   "rather than a false success"],
  R_TWO, RT_UPSTREAM, ["overclaim", "detector-failure", "owner-blocked"], True)

u("retirement-blast-radius",
  "Retirement blast-radius audit: dangling references left by the DELETE-ALL",
  "After the owner-approved DELETE-ALL removed 77 files across 5 trees, which surviving files, manifests, "
  "tests, CI steps, or documents still reference a deleted path?",
  ["the list of 77 deleted files and their prior paths",
   "the doc-path reference integrity result from AUD-0033",
   "every manifest, import, and CI command line"],
  ["B01", "AUD-0033"], M_AUD, ROB, "local-parallel", 2400, SCHEMA["finding"],
  "Probe 1: search every surviving file for each deleted path string. Probe 2: an execution-level check - run "
  "the import graph and the CI collection and record any resolution error naming a deleted path, because a "
  "reference constructed at runtime from parts will not match a literal string search.",
  ["use-vs-mention control: a deleted path named only inside a changelog entry describing its deletion must "
   "NOT be reported as a dangling reference"],
  R_XV, RT_2S, ["use-vs-mention", "detector-failure", "partial-artifact"], False)

u("freeze-inventory",
  "Launcher and schema freeze inventory with a versioned-migration requirement",
  "Which launchers, prompt templates, and schemas must be frozen the moment the first implementation wave "
  "starts, and what is the exact versioned-migration procedure for changing each one afterwards?",
  ["every launcher and dispatcher entry point", "every schema file the program will validate against",
   "spec _USER-PROMPTS.md:10660 (freeze the launchers and schemas once the first implementation wave starts)",
   "the recorded incident where editing a preamble mid-run left contradictory live instructions"],
  ["B01"], M_TOOL, ROB, "local-parallel", 2400, SCHEMA["inv"],
  "Probe 1: enumerate the freeze set and record a sha256 per file as the freeze anchor. Probe 2: define and "
  "TEST a change-detection check that turns red when any frozen file's hash changes without a version bump - "
  "an inventory with no detector is a list, not a freeze.",
  ["both-states control: modify one frozen file in a scratch copy without bumping its version and confirm the "
   "check fires; bump the version and confirm it passes"],
  R_XV, RT_2S, ["detector-failure", "green-not-live"], False)

u("fresh-profile-harness-baseline",
  "Fresh-user-profile harness-load baseline",
  "Under a clean Windows user profile with no existing harness state, which skills, hooks, rules, plugins and "
  "MCP servers load - and how does that differ from the current profile?",
  ["a clean or sandboxed Windows user profile", "the current profile's measured load set from AUD-0062",
   "spec _USER-PROMPTS.md:10655 (fresh user profile where possible)"],
  ["B01", "AUD-0062"], M_AUD, ROP, "local-serialized", 3600, SCHEMA["drift"],
  "Probe 1: the load set measured in the clean profile. Probe 2: the same measurement in the current profile, "
  "reported as a diff - the clean-profile number alone cannot tell you which of the current profile's "
  "behaviours are accidental local state.",
  ["control: the clean profile must be proven clean - assert the harness state directories are absent or "
   "empty before the measurement, otherwise a leaked profile makes the two runs identical by construction"],
  R_FRESH, RT_NORETRY, ["scope-mismatch", "green-not-live", "detector-failure"], False)


# ------------------------------------------------------------------------------- emit
def build():
    out = []
    for i, d in enumerate(U, start=1):
        uid = "AUD-%04d" % i
        out.append({
            "id": uid,
            "title": d["title"],
            "phase": d["ph"],
            "question_or_target": d["target"],
            "inputs": d["inputs"],
            "dependencies": d["deps"],
            "assigned_model_vendor_role": d["model"],
            "tool_permissions": d["tools"],
            "execution_substrate": d["sub"],
            "timeout_seconds": d["to"],
            "output_path": "command-center/audit/%s-%s.json" % (uid, d["slug"]),
            "output_schema": d["sch"],
            "evidence_requirement": d["ev"],
            "tests_required": d["ts"],
            "reviewer_requirement": d["rev"],
            "completion_sentinel": ("SUCCESS:%s emitted only when the artifact at output_path exists, is "
                                    "non-empty, parses against output_schema, and both named probes are "
                                    "recorded with their verbatim output" % uid),
            "retry_policy": d["rt"],
            "failure_classification": d["fc"],
            "owner_approval_required": d["oa"],
            "bucket": "B02",
            "slice": "AUD-1of1",
        })
    return out


if __name__ == "__main__":
    units = build()
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AUD-1.json")
    with open(dst, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(units, fh, indent=2, ensure_ascii=True)
        fh.write("\n")
    print("wrote", dst, len(units))
