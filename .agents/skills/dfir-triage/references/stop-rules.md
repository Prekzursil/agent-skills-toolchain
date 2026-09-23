# Stop rules — DFIR triage

Read before touching any evidence. These are hard boundaries, not suggestions.

## Authorization

- **Owner-authorized evidence only.** A named incident on an owned/authorized system,
  or a lab range. No third-party hosts, mailboxes, buckets, or captures.
- Discovered assets do NOT auto-enter scope. If scope is ambiguous, **stop and confirm.**
- Secrets/creds by env NAME only; never record live tokens/keys/passwords, including
  ones seen inside evidence.

## Integrity / chain of custody

- **Preserve hashes and offsets.** Hash on intake and on every output with
  `scripts/evidence_manifest.py`; record byte offset/length for anything carved.
- Work on **copies**, read-only. Mount images read-only; keep the original
  write-blocked. Never let a tool write back to source evidence.
- Record the exact command, tool version, and rule-set version/commit for every
  result so a finding is reproducible. Diff intake vs output manifests before closing.

## Capability boundaries

- **No C2, no live response beyond offline collection.** Velociraptor is an *offline
  collector only* — never a server, client-enrollment, or callback channel.
- **No daemons / sensors.** Zeek/Suricata/tshark run in pcap **file mode** only;
  capture is a separate authorized step. No live IDS, span port, or Timesketch server.
- **No detonation.** Do not run, open, or execute samples/attachments/macros inline.

## Hand-offs (stop here, pivot to the right skill)

- Executables / implants / suspicious documents → hash, record provenance, then
  `capa-triage` → `malware-analysis-triage` / `reverse-engineering-toolkit`.
- **Memory images** → `volatility-3` (not this skill).
- **Offline guest-disk repair/growth** → `offline-linux-disk-surgery` (not this skill).
- IOC enrichment / attribution → the CTI lane (`cti-lookup`).
- "This should have been detected" → `detection-as-code` (rule authoring) /
  `purple-emulation` (validate the detection fires). This skill *runs* rules to
  triage; it does not author them.
