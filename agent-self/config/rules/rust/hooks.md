---
paths:
- '**/*.rs'
- '**/Cargo.toml'
permalink: dqverify-repo-20261013/agent-self/config/rules/rust/hooks
---

# Rust Hooks

> This file extends [common/hooks.md](../common/hooks.md) with Rust-specific content.

## PostToolUse Hooks

> **The shipped per-edit hook does NOT validate Rust.** `hooks/per-edit-check/check.py`
> deliberately returns a silent skip for `.rs` (cargo is too heavy for a hook that runs on
> every edit), and `hooks/per-edit-check/test_check.py` pins that silence. So a malformed
> `.rs` edit passes "Per-edit validation" without being checked. Do not read the list below
> as something the toolchain already runs for you.

Opt in per project by configuring these in that project's `settings.json` (or, better, in a
pre-commit hook / CI job where a multi-second cargo invocation is affordable):

- **cargo fmt**: Auto-format `.rs` files after edit
- **cargo clippy**: Run lint checks after editing Rust files
- **cargo check**: Verify compilation after changes (faster than `cargo build`)