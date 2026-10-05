# Estate pack 2026-10-05 — full restorable state of all 3 machines

## Contents
- pentagi-db.sql.gz (48M)     — PentAGI full DB dump: flows, tasks, subtasks, toolcalls,
                                msgchains, registers = THE engagement session history
- decepticon-db.sql.gz (35K)  — Decepticon postgres dump
- sandbox-work-volume.tgz (482M) — complete /work of pentagi-terminal-5: staged on-demand
                                material (secrets corpus, XAPKs), lane34/lane36 artifacts,
                                /work/bolt/REPORT full sealed deliverable tree
- linux-configs-only.tgz (15M) — offload-linux configs: pentagi/.env (GLM keys), decepticon/.env
                                (zai keys), compose files, agent-pack, systemd units
                                (pentagi-intel-watch, gateway-bridge), msfrpcd pass + database.yml
- this-vm-configs.tgz (686K)  — offload-w2025: ~/.agents registry+secrets, ~/.config/cyberstrike
                                (SSOT-secrets), mcp-ssot.json, gateway health log
- zcode-memories.tgz (37K)    — ZCode persistent memories (project default-a18792a756ad3f38)
- bolt-assessment/            — extracted final reports + archives (also on GitHub 4d7d3c3e9+)
- MANIFEST-linux.txt / MANIFEST-windows.txt

## Offload-linux additionally holds locally (not in this pack — too big, origin home):
- /opt/intel/*.tgz (7G staged intel; source = D:\opt\home-data which home already has)
- /opt/estate-pack-2026-10-05/linux-vm-configs.tgz (3G = configs-only + /opt/intel archives)
- docker image estate/kali-bolt:1 (24G; rebuildable: vxcontrol/kali-linux + apt list in STATE doc)
- containers: msfrpcd + msf-db (recreate via linux-vm-setup scripts + /opt/msf files)

## Restore order
1. Windows VM: vault clone (github Prekzursil/agent-skills-toolchain, branch
   vm/offload-w2025-2026-09-29-offensive-stack) -> skills/scripts; unpack this-vm-configs.tgz
   to user profile; schtasks CyberStrikeGateway + Startup items per vault cyberstrike/gateway/
2. Linux VM: unpack linux-configs-only.tgz at /; docker compose up pentagi + decepticon;
   gunzip pentagi-db.sql.gz | docker exec -i pgvector psql -U pentagi pentagi
3. Sandbox: docker cp sandbox-work-volume.tgz into a pentagi terminal volume _data, extract
4. Session continuity: memory index (zcode-memories) + FINAL-ASSESSMENT-REPORT.md §13.2 gates

## Locations
- Home: C:\Users\Prekzursil\vm-mirror\offload-w2025\2026-10-05\ (rclone homeC/homeD)
- GitHub: vault branch (sanitized state; secrets only in home pack, NOT in the repo)
