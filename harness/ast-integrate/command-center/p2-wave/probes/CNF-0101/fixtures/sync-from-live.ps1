# fixture stand-in of catalog-named scripts/sync-from-live.ps1
# CNF-0101 MUST NOT execute this against any tree.
param($LiveRoot, $RepoRoot)
# LINE-NO-TRANSFORM: one-directional overwrite, no EOL conversion, no merge.
Copy-Item -Path $LiveRoot -Destination $RepoRoot -Recurse -Force
