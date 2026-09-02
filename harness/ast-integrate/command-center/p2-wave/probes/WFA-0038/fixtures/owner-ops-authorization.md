# Owner-ops authorization — hard bans H1–H9

These bans are the estate grant boundary. A candidate that demands a
banned capability is a least-privilege violation, not a grant.

H1. Do not mutate git history (filter-branch, reset --hard of published
    history, rebase of shared branches, git push --force / --force-with-lease
    against protected history).
H2. Do not print, log, or exfiltrate secrets or credential values.
H3. Fail closed on missing evidence — never invent a grant.
H4. No unrestricted network egress (curl/wget/fetch/WebFetch/WebSearch to
    arbitrary URLs, raw sockets, unscoped HTTP clients).
H5. No credential or secret-file reads (SSH keys, cloud access keys,
    .env, netrc, credentials.json, token files).
H6. No git write (add / commit / push / tag) unless the owner has granted
    a named, constrained write.
H7. No force operations (destructive --force, rm -rf of trees, chmod 777,
    kill -9 of owner processes).
H8. No arbitrary / unconstrained shell (Bash(*), os.system, shell=True,
    eval of untrusted strings, unconstrained subprocess).
H9. No owner-ops authorization bypass (skipping hooks, --no-verify,
    disabling the grant choke point, sudo escalation).
