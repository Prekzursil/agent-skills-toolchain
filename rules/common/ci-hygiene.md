---
paths:
  - "**/*.yml"
  - "**/*.yaml"
  - ".github/workflows/**"
  - "**/*.py"
  - "**/conftest.py"
  - "**/pytest.ini"
  - "**/tox.ini"
  - "**/pyproject.toml"
  - "**/noxfile.py"
---
# CI Hygiene (non-negotiables)

Cross-tool rule read by Claude Code · Codex CLI · Antigravity (agy). CI footguns
that make a suite look GREEN while proving nothing (a no-op gate, a hung runner, a
"public site on a private repo"), plus adjacent CI / merge-hygiene traps. All are
ledger-proven — each one shipped a false-positive, a hang, or a wrong
"already-merged" verdict that cost real debugging.

## 1. `python -m X` as a CI gate is a NO-OP without a real `if __name__ == "__main__"`

A workflow step like `run: python -m mypkg.check` (or `python -m mypkg`) does
**nothing** unless the module actually executes on import OR has a
`if __name__ == "__main__":` block wired to a `main()` that walks the data and
**exits non-zero on failure**. Importing a module runs its top-level code, but a
module whose logic lives only in unref'd functions/classes imports cleanly,
prints nothing, and **exits 0** — a permanently green gate that checks nothing.

- **Fix:** every module used as a `python -m` gate MUST end with
  ```python
  def main(argv: list[str] | None = None) -> int:
      root = Path(argv[0]) if argv else Path("data/public")
      files = sorted(root.rglob("*.json"))          # enumerate the ACTUAL inputs
      if not files:                                 # empty walk => FAIL CLOSED
          print("FAILED:mygate no inputs found")
          return 1
      bad = [f for f in files if b"CNP" in f.read_bytes()]   # the per-input check
      for f in bad:
          print(f"FAILED:mygate {f}")
      print("SUCCESS:mygate" if not bad else f"FAILED:mygate violations={len(bad)}")
      return 1 if bad else 0
  if __name__ == "__main__":
      raise SystemExit(main())
  ```
  `main()` must (a) enumerate the actual inputs (files/config/rows), never a
  do-nothing placeholder;
  (b) **fail closed** — any parse error, missing input, or empty walk returns
  non-zero, never "nothing found → pass"; (c) emit a terminal `SUCCESS:`/`FAILED:`
  marker so the log is diffable.
- **Verify the gate can fail:** before trusting a new gate, feed it a known-bad
  input and confirm it exits non-zero. A gate that has never gone red is
  indistinguishable from a no-op.

## 2. A LIVE-network test in the fast CI suite hangs (or flakes) the runner

A test that reaches the network (real HTTP, a live MCP server, `claude mcp list`,
a socket, a cloud API) does not belong in the fast/hermetic suite: it hangs when
the endpoint is slow/down, flakes on rate limits, and makes CI non-reproducible.

- **Fix:** mark it `@pytest.mark.live` (register the marker in `pytest.ini` /
  `pyproject.toml` so it is not an unknown-marker warning) and run the fast suite
  with `-m "not live"`. Put the live checks in a **separate scheduled job**
  (nightly/cron), not the per-PR gate, with a hard per-test timeout.
- **Hermetic CI = block egress + verify a committed snapshot store.** The fast
  job asserts against a **committed fixture/snapshot** (recorded response, golden
  file), never a live call. If a change needs new live data, re-record the
  snapshot deliberately and commit it — do not let CI fetch it at run time.
- Keep any real subprocess/network call behind an **injectable seam** (pass the
  captured output string into the pure parser) so the parser is unit-tested
  hermetically and only the thin adapter is `@live`.

## 3. GitHub Pages on a PRIVATE repo needs Pro — and the published site is PUBLIC

Enabling GitHub Pages on a private repo requires a paid plan (Pro/Team/Enterprise)
on the account, and even then **the rendered Pages site is world-readable** — a
private repo does NOT make its Pages output private. Do not publish coverage
dashboards, internal reports, or anything with hostnames/paths/tokens to Pages
assuming "private repo = private site".

- **Fix:** for a genuinely private artifact use a CI **artifact upload**
  (`actions/upload-artifact`, retention-scoped) or a private object store, not
  Pages. If Pages is required, treat every byte as public and scrub it first.

## 4. Squash-merge rewrites history — `is-ancestor` reports a MERGED branch as NOT merged

When a PR lands via **squash-merge** (this repo's default), GitHub writes ONE new commit onto
`main` with a fresh SHA and the branch's original commits never enter `main`'s history. So
`git merge-base --is-ancestor <branch> main` exits **1 ("not an ancestor")** for a branch that is
fully MERGED — the work landed, those commits did not. Deciding "did this land?" from ancestry then
reports false-behind and re-proposes already-merged work. (Ledger-proven: monitorcore PR-B1/B2/B3,
2026-07-18.)

- **Fix — trust PR state, not commit ancestry.** Ask GitHub: `gh pr view <n> --json state,mergedAt`
  (or `gh pr list --state merged --head <branch>`); `state == MERGED` is the receipt. Reserve
  ancestry checks for genuine fast-forward / rebase merges. Pairs with the stale-branch
  mass-deletion guard in `windows-shell.md` §8d (`git diff origin/main...HEAD --stat` before a PR).

## 5. Pin every gate tool; gitleaks allowlists are PLURAL and mutually exclusive with the singular table

- **Pin each gate tool to an exact version.** CI runs `ruff==0.15.17` (`quality.yml`); a local
  `0.15.x` mismatch formats differently and a green local check can go red in CI. Install pinned
  (`pip install <tool>==<ver>` / `uvx <tool>@<ver>`), never the ambient one. (The CRLF-vs-LF half of
  this story is `windows-shell.md` §8b.)
- **gitleaks: use the plural `[[allowlists]]` array, never the singular `[allowlist]` table, and
  NEVER both.** gitleaks REFUSES to load a config that mixes the two forms and then **silently falls
  back to its defaults** — every waiver gone, every synthetic fixture false-flagged. Plural path
  waivers reach the multi-line `private-key` rule only on **gitleaks >= 8.30** (8.24.3 did not), so
  pin accordingly. The CI action's bundled gitleaks can also differ from a local `8.30.1` (it
  URL-decodes and re-scans percent-encoded strings that local does not), so a local-clean file can
  still flag in CI — verify against the action, not only local.
- **Split PATs by capability.** A token that only TRIGGERS a workflow must not also read auth or
  write Secrets; use two least-privilege PATs (e.g. a dispatch PAT vs a Secrets-write PAT), never
  one broad token.

---
*Deploy: copy to `~/.claude/rules/common/ci-hygiene.md` (imperative-copy sync
model). A one-line pointer belongs in AGENTS.md alongside the §11 windows-shell
pointer — orchestrator's call, not edited here.*
