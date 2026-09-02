---
name: dfir-triage
description: "Use when triaging host, endpoint, Windows event log, network (pcap), cloud, container, or email evidence in an owner-authorized DFIR investigation. Covers EVTX/Sigma (Chainsaw, Hayabusa), artifact parsing (dissect, EZ Tools/KAPE), super-timelines (Plaso), Velociraptor offline collection, tshark/Zeek/Suricata pcap review, cloud/host triage (varc, container-explorer, cloudgrep), and phishing analysis. Memory forensics stays in volatility-3; disk surgery stays in offline-linux-disk-surgery."
license: "This skill ships only Markdown plus one stdlib helper (MIT-style). Every wrapped tool (Chainsaw, Hayabusa, dissect, EZ Tools/KAPE, Plaso, Velociraptor, tshark, Zeek, Suricata, varc, container-explorer, cloudgrep) is third-party OSS under its own license: wrap and invoke it, do not vendor it."
---

# dfir-triage — host / log / network / cloud / email forensics

## Overview

DFIR triage for everything that is NOT already covered by the two sibling skills:

- Memory image work stays in **`volatility-3`** — do not duplicate it here.
- Offline guest-disk inspection/repair stays in **`offline-linux-disk-surgery`** — do not duplicate it here.

This skill wraps the fast-triage CLIs for Windows event logs, forensic artifacts,
super-timelines, offline live-response collection, network captures, cloud/host
logs, and email/phishing. Every tool is invoked ad hoc against evidence you are
authorized to examine; **nothing here runs a daemon, a server, or a C2 channel.**

## Golden rules (read `references/stop-rules.md` before touching evidence)

1. **Owner-authorized evidence only.** Named incident, owned/authorized system, or
   lab range. No third-party hosts. No "just scan this random capture."
2. **Preserve hashes and offsets.** Hash every artifact on intake and again on
   output; record byte offsets/ranges for anything you carve. Use
   `scripts/evidence_manifest.py` so this is mechanical, not remembered.
3. **Work on copies, read-only.** Mount images read-only; operate on write-blocked
   or copied evidence. Never let a tool write back to the original.
4. **No C2, no live response beyond offline collection.** Velociraptor is used as an
   **offline collector only** (self-contained collector binary → zip), never a
   persistent GRR/Velociraptor server or agent callback.
5. **Hand binaries to the RE skills.** When triage surfaces an executable/implant,
   hash it, record where it came from, and pivot to `capa-triage` →
   `malware-analysis-triage` / `reverse-engineering-toolkit`. Do not detonate.

## Quick workflow

1. **Scope + intake.** Confirm authorization and the evidence inventory. Hash
   everything on arrival: `python3 scripts/evidence_manifest.py <files...> --json > intake.json`.
2. **Pick the lane** by evidence type (each has a reference file below):
   - Windows event logs (`.evtx`) → EVTX/Sigma sweep (Chainsaw, Hayabusa).
   - A disk image / KAPE target / `$MFT`, registry, browser, LNK, etc. → artifact parse (dissect, EZ Tools).
   - "What happened, in order?" across many artifacts → super-timeline (Plaso).
   - A live but authorized endpoint → Velociraptor **offline collector**.
   - `.pcap`/`.pcapng` → network forensics (tshark, Zeek, Suricata — all file mode).
   - Cloud/SaaS/container logs → cloud/host triage (varc, container-explorer, cloudgrep, Invictus).
   - A suspicious message → email/phishing triage.
3. **Convergence.** Fold per-lane findings into one timeline; correlate on time,
   host, user, IOC. Grade confidence; flag gaps.
4. **Hand-off.** Binaries → RE skills. IOCs → CTI enrichment. Detections that
   should have fired → detection-as-code / purple-emulation. Re-hash outputs into
   the manifest before you close.

## Reference map

- `references/evtx-sigma.md` — Chainsaw + Hayabusa over `.evtx` with Sigma rules.
- `references/artifact-parse.md` — dissect (one pip, most artifacts) + EZ Tools / KAPE.
- `references/timeline.md` — Plaso (`log2timeline`/`psort`) super-timelines.
- `references/live-response.md` — Velociraptor **offline collector only** (no server).
- `references/network-forensics.md` — tshark / Zeek / Suricata, pcap file mode, 0 daemon.
- `references/cloud-host-triage.md` — varc, container-explorer, cloudgrep, Invictus log kit.
- `references/email-phishing.md` — header auth, `.eml`/`.msg` parse, URL/attachment triage.
- `references/stop-rules.md` — authorization, chain-of-custody, and hand-off boundaries.
- `references/upstream.md` — install one-liners, sibling-skill links, upstream docs.

## Chain-of-custody helper

`scripts/evidence_manifest.py` is a read-only, offline, stdlib-only hasher that
records a digest per file (optionally over a byte `--offset`/`--length` range, so
carved regions keep their provenance):

```
python3 scripts/evidence_manifest.py memory.raw disk.e01 export.zip --json
python3 scripts/evidence_manifest.py disk.dd --offset 1048576 --length 512 --algo sha256
```

It never writes to, moves, or executes evidence. Run it on intake and again on
every artifact you produce; diff the two manifests to prove nothing drifted.

## Common mistakes

- Running a tool that writes back into the original evidence instead of a copy.
- Losing the offset/PID/host mapping between a carved artifact and its source.
- Treating one lane's output as the whole story instead of building a merged timeline.
- Standing up a Velociraptor/GRR server or a live IDS sensor — this skill is 0-daemon.
- Detonating or reversing a sample inline instead of handing it to the RE skills.
