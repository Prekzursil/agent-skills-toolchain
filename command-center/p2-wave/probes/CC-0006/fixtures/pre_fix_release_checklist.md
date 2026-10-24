# Pre-fix RELEASE-CHECKLIST snippet (known-present control)

Reproduces the catalog-confirmed wrong prescription that lived in
`command-center/RELEASE-CHECKLIST.md` before the CC-0006 fix.

## A. Releasing a change to the command center itself

- [ ] `ruff check .` and `ruff format --check .` at the CI pin (`ruff==0.15.17`), checked
      against the **LF blob** (`git archive`), not the CRLF working tree.
