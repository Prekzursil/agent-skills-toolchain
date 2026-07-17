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

Cross-tool rule read by Claude Code · Codex CLI · Antigravity (agy). Three CI
footguns that make a suite look GREEN while proving nothing (a no-op gate, a
hung runner, a "public site on a private repo"). All three are ledger-proven —
each one shipped a false-positive or a hang that cost real debugging.

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
  `main()` must (a) enumerate the actual inputs (files/config/rows), not a stub;
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

---
*Deploy: copy to `~/.claude/rules/common/ci-hygiene.md` (imperative-copy sync
model). A one-line pointer belongs in AGENTS.md alongside the §11 windows-shell
pointer — orchestrator's call, not edited here.*
