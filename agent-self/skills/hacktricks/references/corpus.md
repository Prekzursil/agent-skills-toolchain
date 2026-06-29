# HackTricks local corpus

- **Location:** `D:\knowledge\hacktricks\` (override with env `HACKTRICKS_CORPUS`)
  - `hacktricks\src\` — main book (~982 .md): pentest, web, AD, mobile, crypto, forensics, network, OS internals, general dev tricks.
  - `hacktricks-cloud\src\` — cloud book (~589 .md): AWS, GCP, Azure, Kubernetes, CI/CD.
- **Index:** each book's `src\SUMMARY.md` is the full page tree.
- **Sparse:** `--no-cone`, set `/src/**` + `!/src/images/**` (markdown only, images excluded → ~20 MB total).
- **Refresh:** `pwsh scripts/htk_update.ps1`.
- **Search substrate:** host/PowerShell ripgrep (fast). The corpus on `D:` is also reachable from WSL at `/mnt/d/knowledge/hacktricks` if needed (slower over 9p).
- **AI wiki:** `ai.hacktricks.wiki` is NOT a separate open repo — its AI layer is served by the API (see the `hacktricks-api` skill).
- **License:** content is HackTricks, CC BY-NC-SA 4.0 — personal reference only; attribute HackTricks if reused. The skill code itself is MIT.
