# Seeded coverage-control changelog. The extractor MUST find SEED-BC-LEGACY-HOOK-DIR
# here before any live absence claim is trusted.

## 9.9.9

- Added a plugin setting for colour themes
- Fixed a typo in the MCP reconnect banner

## 0.0.0

- Breaking change: Removed plugin manifest field `legacyHookDir`; the client now loads hooks only from `hooks/hooks.json`. Coverage-control seed SEED-BC-LEGACY-HOOK-DIR.

## 1.2.3

- Changed plugin option values (`pluginConfigs`) are no longer read from project-level `.claude/settings.json`; only user, `--settings`, and managed settings are honored
