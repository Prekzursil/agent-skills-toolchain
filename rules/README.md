# `.agents/rules` — Grok extra_rule_dirs target

Grok `config.toml` `[paths] extra_rule_dirs` pointed here when the directory
did not exist. This folder is **not** a copy of `~/.claude/rules` (88 files;
that would blow Grok's 10k-char truncate).

`estate-locks.md` is the rule Grok should load: pointer to `~/AGENTS.md` plus
the HARD deny list (NEVER-ROTATE, private repo, secret files, force-push).
