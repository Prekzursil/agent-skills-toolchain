# Cloud / host / container triage — varc, container-explorer, cloudgrep, Invictus

Collect and search volatile host state, container filesystems, and cloud/SaaS logs
you are authorized to examine. All read-only, all ad hoc, no always-on collector.

## varc — Volatile Artifact Collector (Cado Security, Apache-2.0 — wrap, do not vendor)

Single static binary that snapshots volatile host state (processes, open files,
network connections, env, loaded modules, select memory) into one zip. Ideal for a
fast, authorized "grab the volatile picture before it's gone" on a host/VM/container.

```
./varc                        # writes output.zip in CWD (run with needed privileges)
python3 ../scripts/evidence_manifest.py output.zip --json > varc.hashes.json
```

## container-explorer (Google, Apache-2.0 — wrap, do not vendor)

Explore containerd/Docker containers **offline from a mounted host image** — list
containers, inspect their layered filesystems, and export a container's files
without starting the runtime.

```
container-explorer -i /mnt/host_image list containers
container-explorer -i /mnt/host_image mount <container-id> /mnt/ctr   # read-only view
container-explorer -i /mnt/host_image export <container-id> ./out/    # export layers
```

## cloudgrep (Cado Security, Apache-2.0 — wrap, do not vendor)

grep across cloud object storage (S3/GCS/Azure Blob) for IOCs without downloading
everything. Uses env-named cloud creds (`${AWS_PROFILE}` etc.) — never inline keys.

```
cloudgrep --bucket owner-logs-bucket --query "198.51.100.23"    # IOC across logs
cloudgrep --bucket owner-logs-bucket --file-size 100000000 --query "InvokeFunction"
```

## Invictus-IR cloud log kit (Microsoft-Extractor-Suite / AWS-/Azure-CLI helpers)

For M365/Entra/AWS/Azure incidents, pull the audit/sign-in/unified logs with the
Invictus tooling (or the provider CLI), then triage the exported JSON/CSV offline.

```
# M365/Entra (PowerShell): export Unified Audit Log + sign-ins for the incident window:
Get-UAL -StartDate 2026-08-01 -EndDate 2026-08-15 -Output ./m365_out
# AWS: pull CloudTrail for the account/region, then jq the events:
aws cloudtrail lookup-events --start-time 2026-08-01 --end-time 2026-08-15 > cloudtrail.json
jq -c '.Events[] | {t:.EventTime,name:.EventName,user:.Username,src:.CloudTrailEvent}' cloudtrail.json
```

## Notes / stop rules

- **Owner cloud / owner tenant only.** Read/collect logs; never mutate cloud config
  or resources from a triage.
- Secrets by **env NAME** only (`${AWS_PROFILE}`, `${AZURE_*}`) — no live values in
  commands, notes, or the manifest.
- Cross-cloud attack-path/enumeration tooling (e.g. cloudfox) is the
  `cloud-container-security` skill's lane, gated by the harness rails — not here.
