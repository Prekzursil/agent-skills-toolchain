# Home data copied 2026-10-01

Source: desktop-a60s9gp (100.97.16.36) via rclone SFTP
Target: D:/opt/home-data/ (mirrored to offload-win-mirror)

## Contents
- bolt/ — Bolt engagement research (D: from home, ~908MB)
- bolt-opt/ — D:/opt/bolt from home
- cowork/ — Cowork folder (C: from home, ~1.2GB)
- cs-mcp/ — D:/opt/cs-mcp from home
- cyberstrike-config/ — ~/.config/cyberstrike from home (~11MB)
- cyberstrike-mcp-home/ — D:/opt/cyberstrike-mcp from home (~83MB)
- databricks-harvest/ — Desktop/Codex Useful Prompts/databricks_harvest (~871MB)

## NordVPN/Tailscale stability (root cause + fix)
- NordLynx adds 100.64.0.0/10 route that collides with Tailscale CGNAT
- Home has fix-nord-tailscale-route.ps1 running every 20s (watchdog)
- Script: deletes conflicting route, restarts SFTP serves, ensures firewall
- NordVPN currently OFF on home (owner decision to avoid outages)
- Coexist task: home-nord-tailscale-coexist (every 5 min)
