"""Curated match table: keyword hits are not matches without a discriminator."""
from __future__ import annotations

# Each row must name an observation that would split same-mechanism from same-symptom.
# Local FC-11303: plugin looks installed; hooks do not fire. Estate precedent: a
# `$schema` key in hooks.json made Codex load ZERO hooks.
# Local FC-11329: skill file exists in repo tree, absent from live skill directory.
# Local marketplace trap (RES-0008): plugin.json version silently wins over marketplace.json.

MATCHES: dict[int | str, dict] = {
    "RES-0014-SEEDED-KNOWN-PRESENT": {
        "issue_ref": "RES-0014-SEEDED-KNOWN-PRESENT",
        "number": 0,
        "classes": ["plugin_installed_hooks_unloaded"],
        "local_class": "FC-11303",
        "verdict": "SAME-MECHANISM",
        "why_not_keyword_only": (
            "The seeded body requires a $schema key that unloads every hook while "
            "installed_plugins.json still lists the plugin — the same token the "
            "estate already measured on Codex."
        ),
        "upstream_reproduction": (
            "Add $schema to hooks.json; plugin remains listed as installed; hook "
            "side-effect count is 0."
        ),
        "local_reproduction": (
            "Catalog TST-0082 / IMP-0039: a $schema key in hooks.json made Codex "
            "load ZERO hooks while everything looked installed."
        ),
        "discriminating_observation": (
            "If hook scripts remain registered in the client's hook table and fail "
            "only at spawn (ENOENT/PATH), this is not FC-11303. FC-11303 requires "
            "the hook table itself to be empty or the hooks.json parse to have "
            "been rejected while the plugin still appears installed."
        ),
        "strongest_caveat": (
            "This row is the operator-seeded detector control, not a GitHub issue. "
            "It proves the search retrieves a known-present record."
        ),
    },
    75972: {
        "issue_ref": "anthropics/claude-code#75972",
        "number": 75972,
        "classes": ["plugin_installed_hooks_unloaded"],
        "local_class": "FC-11303",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "Maintainer reproduction (bcherny, 2026-08-17) names the token: one "
            "unrecognised event name PreSkill causes the entire hooks.json to be "
            "rejected, so SessionStart/Stop/PreToolUse/PostToolUse never fire, "
            "while skills/agents still work and the plugin shows installed+enabled."
        ),
        "upstream_reproduction": (
            "Plugin installed and enabled; cached hooks.json byte-identical to "
            "source; PreToolUse/Bash hook that should block `--no-verify` does not "
            "run. Maintainer: PreSkill is not a supported event; one unrecognised "
            "event name currently rejects the entire hooks.json; failure only "
            "visible in --debug and as 'failed to load' in `claude plugin list`."
        ),
        "local_reproduction": (
            "Estate: a $schema key in hooks.json made Codex load ZERO hooks while "
            "the plugin/config still looked installed (TST-0082, IMP-0039, "
            "WORK-UNIT-CATALOG 79764 / 42621)."
        ),
        "discriminating_observation": (
            "Same symptom (plugin looks installed; zero plugin hooks fire) but "
            "the rejected token differs: Codex $schema (unknown JSON key) vs "
            "Claude Code PreSkill (unknown event name). SAME-MECHANISM would "
            "require observing that a $schema key also dumps Claude Code's "
            "hooks.json, or that Codex also dumps the file on an unknown event "
            "name. That cross-client experiment is not in this corpus. Also "
            "isolating: settings.json-level hooks DO fire (#75972 reporter and "
            "maintainer), so the dispatch engine is not dead — only plugin-sourced "
            "hooks.json registration is."
        ),
        "strongest_caveat": (
            "Open as of fetch. Local precedent is Codex, not Claude Code. Do not "
            "cite as measured same-mechanism."
        ),
    },
    16288: {
        "issue_ref": "anthropics/claude-code#16288",
        "number": 16288,
        "classes": ["plugin_installed_hooks_unloaded"],
        "local_class": "FC-11303",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "External hooks.json referenced from plugin.json never executes; the "
            "same hook in ~/.claude/settings.json does fire. Multiple independent "
            "reporters. This is registration-path failure, not a missing bash."
        ),
        "upstream_reproduction": (
            "plugin.json hooks: ./hooks/hooks.json; SubagentStop command never "
            "creates /tmp/hook-test.log after Task tool. Workaround: define the "
            "same hook in ~/.claude/settings.json — then it fires."
        ),
        "local_reproduction": (
            "FC-11303: plugin appears installed but hooks are unloaded; acceptance "
            "must be a runtime side effect, not a config-file listing (IMP-0460, "
            "TST-0082)."
        ),
        "discriminating_observation": (
            "If moving the identical hook command into user settings.json makes it "
            "fire, the hook engine works and the defect is plugin-sourced loading "
            "(this issue). If settings.json hooks also do not fire, look at PATH/"
            "Git-Bash (decoy class) or a process-wide hook disable. Local Codex "
            "$schema dumps ALL hooks including settings-level; #16288 settings-level "
            "hooks still work — that split keeps this at SAME-SYMPTOM, not "
            "SAME-MECHANISM as the $schema incident."
        ),
        "strongest_caveat": "Still open; comments also describe a loadPluginHooks race.",
    },
    14815: {
        "issue_ref": "anthropics/claude-code#14815",
        "number": 14815,
        "classes": ["plugin_installed_hooks_unloaded", "marketplace_silent_fail"],
        "local_class": "FC-11303",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "Marketplace UI prints '(installed)' and installed_plugins.json contains "
            "the entry, but the Installed tab is empty and commands/hooks are not "
            "available — a state-file vs loader split, not a keyword coincidence."
        ),
        "upstream_reproduction": (
            "Custom marketplace plugin: UI `✔ my-plugin (installed) · 0 installs`; "
            "~/.claude/plugins/installed_plugins.json has the entry and cache "
            "plugin.json exists; plugin commands and hooks are not available."
        ),
        "local_reproduction": (
            "FC-11303 plus marketplace install that can look successful while the "
            "runtime set is empty (IMP-0086 / catalog 64308)."
        ),
        "discriminating_observation": (
            "SAME-MECHANISM with Codex $schema would require hooks.json parse "
            "rejection. Here the tell is contradictory install state (UI installed "
            "+ 0 installs, state file vs loader). If hooks.json would fire once the "
            "loader recognised the install, this is a marketplace/state bug, not a "
            "hooks.json unknown-token dump."
        ),
        "strongest_caveat": "Open; no maintainer-confirmed root cause in the captured comments.",
    },
    46594: {
        "issue_ref": "anthropics/claude-code#46594",
        "number": 46594,
        "classes": ["marketplace_silent_fail", "plugin_installed_hooks_unloaded", "skill_on_disk_not_loaded"],
        "local_class": "FC-11303",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "/plugin marketplace update reports success; /reload-plugins lists the "
            "plugin as loaded; skills, agents, and hooks registered count is 0; "
            "re-install says already installed. Closed as duplicate of #14061."
        ),
        "upstream_reproduction": (
            "Install plugin; author pushes v1.0.0 → v1.1.0; marketplace update "
            "prints success; reload-plugins shows plugin loaded with 0 skills / 0 "
            "hooks; install says already installed."
        ),
        "local_reproduction": (
            "Marketplace path that can look green while the live plugin set is "
            "stale or empty; local RES-0008 is a different silent-green (version "
            "field precedence), IMP-0086 is install handoff."
        ),
        "discriminating_observation": (
            "If plugin.json and marketplace.json versions already agree and the "
            "cache still serves the old tree, this is update-does-not-refresh-"
            "install (this issue), not plugin.json-wins-version (RES-0008 / #54280). "
            "The 0-skills/0-hooks reading while the plugin is listed as loaded is "
            "the FC-11303/FC-11329 symptom; the mechanism is stale install cache, "
            "not $schema parse rejection."
        ),
        "strongest_caveat": "Closed as duplicate; captured comments are bots, not a fix commit.",
    },
    54280: {
        "issue_ref": "anthropics/claude-code#54280",
        "number": 54280,
        "classes": ["marketplace_silent_fail"],
        "local_class": "RES-0008",
        "verdict": "SAME-MECHANISM",
        "why_not_keyword_only": (
            "Named reproduction: plugin.json version 0.1.0-beta.28 vs marketplace.json "
            "1.0.0; Customize panel shows 0.1.0-beta.28; no warning at add, install, "
            "or `claude plugin validate`. That is the RES-0008 trap, not a generic "
            "install failure."
        ),
        "upstream_reproduction": (
            "Disagree the two version fields; installed/displayed version is the "
            "plugin.json value; marketplace.json version is inert. Real-world: "
            "nfrith/als 0.1.0-beta.28 vs 0.1.0-beta.1."
        ),
        "local_reproduction": (
            "RES-0008 question: does plugin.json still silently WIN over the "
            "marketplace entry for version — commits without a version bump ship "
            "nothing while both files pin 0.2.0 (WORK-UNIT-CATALOG 63997)."
        ),
        "discriminating_observation": (
            "SAME-MECHANISM if, when the two files disagree, the installed/"
            "displayed version string equals plugin.json and marketplace.json is "
            "ignored with no warning. If the client honoured marketplace.json, "
            "or warned, this would not match RES-0008. Distinct from #46594 "
            "(cache not refreshed) and from #60725 (validate-green / install-red)."
        ),
        "strongest_caveat": (
            "Closed stale; this worktree did not re-run a live Claude Code binary. "
            "The GitHub reproduction is the second rail, not a local binary trace."
        ),
    },
    83422: {
        "issue_ref": "anthropics/claude-code#83422",
        "number": 83422,
        "classes": ["marketplace_silent_fail", "plugin_installed_hooks_unloaded", "skill_on_disk_not_loaded"],
        "local_class": "FC-11303",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "enabledPlugins in project settings without an installed_plugins.json "
            "row for that path: skills and hooks silently absent, no auto-install. "
            "Second bug: marketplace autoUpdate refreshes the clone but never "
            "updates existing installs."
        ),
        "upstream_reproduction": (
            "Commit enabledPlugins + extraKnownMarketplaces; new repo has no "
            "install record; plugin skills/hooks absent with no warning. "
            "autoUpdate:true advances marketplace lastUpdated; install records stay "
            "pinned (independent Windows reproduction in comments)."
        ),
        "local_reproduction": (
            "Declared-enabled / looks-configured vs actually loaded (FC-11303) and "
            "marketplace update that does not move the live install (IMP-0086 class)."
        ),
        "discriminating_observation": (
            "If installed_plugins.json lacks a row for the project path, absence of "
            "hooks/skills is never-installed, not hooks.json-rejected. The "
            "autoUpdate half is SAME-SYMPTOM as #46594 (clone refreshes, install "
            "does not). Distinct from RES-0008 version-field win: versions need "
            "not disagree for this to bite."
        ),
        "strongest_caveat": "Open; two bugs in one ticket — do not collapse them.",
    },
    44120: {
        "issue_ref": "anthropics/claude-code#44120",
        "number": 44120,
        "classes": ["skill_on_disk_not_loaded"],
        "local_class": "FC-11329",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "skills/my-skill/SKILL.md is on disk; /reload-plugins does not load it "
            "iff plugin contains .claude/; deleting .claude/ from cache makes the "
            "same SKILL.md load. That is a discovery-path switch, not a missing file."
        ),
        "upstream_reproduction": (
            "Plugin with .claude-plugin/plugin.json + skills/my-skill/SKILL.md + "
            ".claude/settings.json; install; reload-plugins does not load skills/; "
            "remove .claude/ from plugin cache; reload-plugins loads pluginName: prefix."
        ),
        "local_reproduction": (
            "FC-11329: skill exists in repo but not in live skill directory "
            "(FAILURE-MODES.json, seeded_classes.py, catalog 42569 / 42578)."
        ),
        "discriminating_observation": (
            "Local FC-11329 is two-tree drift (repo vs live skill directory). This "
            "issue is one plugin tree whose discovery root flips from skills/ to "
            ".claude/skills/ when .claude/ exists. SAME-MECHANISM would require "
            "the estate's 'missing from live directory' to be this discovery-root "
            "flip. On this worktree the local class is repo-vs-live copy, so "
            "SAME-SYMPTOM only. Closed inactive, not verified-fixed."
        ),
        "strongest_caveat": "Closed for inactivity; not a confirmed fix.",
    },
    26254: {
        "issue_ref": "anthropics/claude-code#26254",
        "number": 26254,
        "classes": ["skill_on_disk_not_loaded"],
        "local_class": "FC-11329",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "available_skills metadata lists the skill; /mnt/skills/user/ SKILL.md "
            "is not on the container filesystem. Metadata-registered vs bytes-mounted."
        ),
        "upstream_reproduction": (
            "Claude.ai / Cowork: user and org skills appear in the system prompt "
            "available_skills block with paths; corresponding SKILL.md files are "
            "not mounted; /mnt/skills/user/ does not exist."
        ),
        "local_reproduction": (
            "FC-11329: skill present in one inventory (repo / index) and absent "
            "from the runtime skill directory."
        ),
        "discriminating_observation": (
            "This is a Claude.ai container mount miss, not Claude Code CLI "
            "repo-vs-live two-tree drift. SAME-MECHANISM would require the CLI "
            "live skill directory to be a container mount that can omit SKILL.md "
            "while metadata still lists it. Surface differs (web container vs "
            "local trees) → SAME-SYMPTOM."
        ),
        "strongest_caveat": "Open; web/Cowork surface, not the CLI plugin loader.",
    },
    38670: {
        "issue_ref": "anthropics/claude-code#38670",
        "number": 38670,
        "classes": ["skill_on_disk_not_loaded"],
        "local_class": "FC-11329",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "Reporter later named the token: plugin.json repository/bugs as npm "
            "objects fail manifest validation; skills/commands/agents never "
            "register; hooks and CLAUDE.md still load (different code path)."
        ),
        "upstream_reproduction": (
            "Third-party marketplace plugin shows installed+enabled; / autocomplete "
            "has no plugin prefix commands. Fix: repository and bugs must be "
            "strings, not objects. Error only on fresh session start."
        ),
        "local_reproduction": (
            "Skill files on disk not in the loaded set (FC-11329). Not FC-11303: "
            "hooks DO load."
        ),
        "discriminating_observation": (
            "Hooks fire → this is not FC-11303. Skills absent because manifest "
            "validation silently skipped skill discovery, not because of two-tree "
            "copy drift. SAME-SYMPTOM with FC-11329; SAME-MECHANISM would require "
            "the estate's missing live skill to be a plugin.json schema reject."
        ),
        "strongest_caveat": "Closed inactive after reporter's own manifest fix; VS Code chat panel still diverged.",
    },
    60725: {
        "issue_ref": "anthropics/claude-code#60725",
        "number": 60725,
        "classes": ["marketplace_silent_fail"],
        "local_class": "RES-0008",
        "verdict": "SAME-SYMPTOM",
        "why_not_keyword_only": (
            "`claude plugin validate` is green on marketplace.json only; install "
            "then fails on plugin.json with a temp-cache path. False-green validate, "
            "not a quiet successful install."
        ),
        "upstream_reproduction": (
            "Invalid plugin.json author:string passes validate; install errors "
            "naming ~/.claude/plugins/cache/temp_local_* not the source file. "
            "Reporter links this to #54280 as the same validator blind spot."
        ),
        "local_reproduction": (
            "Marketplace tooling that can look successful while the plugin will "
            "not actually install; related to RES-0008's silent version win because "
            "validate does not look at plugin.json."
        ),
        "discriminating_observation": (
            "Install DOES error (opaque), so this is not a silent successful "
            "install. It is a silent-green validate. Distinct from #46594 (update "
            "prints success and loads 0 skills with no error) and from #54280 "
            "(install succeeds, wrong version, no warning)."
        ),
        "strongest_caveat": "Closed; install is not silent — only validate is.",
    },
}

# Keyword-retrieved issues that must NOT appear in the match table.
NON_MATCHES: dict[int | str, dict] = {
    81551: {
        "issue_ref": "anthropics/claude-code#81551",
        "number": 81551,
        "reason": "KEYWORD-HIT-NOT-MATCH",
        "discriminating_observation": (
            "Reporter states /reload-plugins reports 0 skills while invocation of "
            "skills/*/SKILL.md works in the same session. The skill is in the "
            "loaded set; the counter only tallies commands/*.md. FC-11329 requires "
            "the skill to be absent from the loaded set, not miscounted."
        ),
    },
    86809: {
        "issue_ref": "anthropics/claude-code#86809",
        "number": 86809,
        "reason": "WITHDRAWN-NOT-A-DEFECT",
        "discriminating_observation": (
            "Reporter closed it: directory-source marketplaces run hooks against "
            "the live source tree, not the cache dir; the canary was written to "
            "the cache, which the hook never executes. Instrumentation error, not "
            "unloaded hooks."
        ),
    },
    39468: {
        "issue_ref": "anthropics/claude-code#39468",
        "number": 39468,
        "reason": "KEYWORD-HIT-NOT-MATCH",
        "discriminating_observation": (
            "YAML frontmatter hooks on SKILL.md/agent files are ignored; the same "
            "command in plugin hooks/hooks.json DOES fire. Plugin-level hooks are "
            "loaded, so this is not FC-11303 (plugin installed, hooks unloaded)."
        ),
    },
    "RES-0014-DECOY-KEYWORD-ONLY": {
        "issue_ref": "RES-0014-DECOY-KEYWORD-ONLY",
        "number": 999001,
        "reason": "KEYWORD-HIT-NOT-MATCH",
        "discriminating_observation": (
            "Title has plugin+installed+hooks, but hooks are registered and fail "
            "at spawn because Git Bash is missing from PATH. FC-11303 requires an "
            "unloaded hook table, not ENOENT on bash.exe."
        ),
    },
}


def match_key(row: dict):
    if row.get("seeded"):
        return "RES-0014-SEEDED-KNOWN-PRESENT"
    if row.get("decoy"):
        return "RES-0014-DECOY-KEYWORD-ONLY"
    return int(row["number"])
