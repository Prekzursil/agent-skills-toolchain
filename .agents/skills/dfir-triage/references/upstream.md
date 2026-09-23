# Upstream notes — install one-liners, sibling skills, docs

Wrap-don't-vendor: install the tool on the analyst host (host-gated) and invoke it;
do not commit tool binaries or forks into this repo. If a tool is missing, say so
truthfully and continue with the lanes that are available.

## Sibling DFIR skills (LINK — do not duplicate their scope here)

- **`volatility-3`** — memory image analysis (process/module/injection recovery).
  Anything that lives in RAM goes there, not here.
- **`offline-linux-disk-surgery`** — offline guest-disk inspect / grow / repair with
  qemu-nbd, guestfish, GPT tools, e2fsck, resize2fs. Disk-surgery goes there.
- Binaries surfaced during triage → **`capa-triage`** → **`malware-analysis-triage`** /
  **`reverse-engineering-toolkit`**.

## Install one-liners (host-gated; pick your platform)

```
# dissect — the one pip that parses most artifacts:
pipx install dissect        # or: pip install dissect

# Plaso (super-timeline):
pipx install plaso          # or distro pkg / docker image log2timeline/plaso

# Chainsaw / Hayabusa — download the signed release binary + bundled rules:
#   https://github.com/WithSecureLabs/chainsaw/releases
#   https://github.com/Yamato-Security/hayabusa/releases   (then: hayabusa update-rules)

# Network (usually distro packages):
apt install tshark zeek suricata      # or brew install wireshark zeek suricata

# Cloud/host triage:
#   varc:               https://github.com/cado-security/varc (static release binary)
#   container-explorer: https://github.com/google/container-explorer/releases
pipx install cloudgrep
pip install eml-parser extract-msg    # email/phishing parsing

# Velociraptor OFFLINE COLLECTOR binary only (no server):
#   https://github.com/Velocidex/velociraptor/releases

# EZ Tools / KAPE (Windows):
#   https://ericzimmerman.github.io/   (Get-ZimmermanTools.ps1)   |   KAPE: https://www.kroll.com/kape
```

## Upstream docs

- Chainsaw: https://github.com/WithSecureLabs/chainsaw
- Hayabusa: https://github.com/Yamato-Security/hayabusa
- dissect: https://docs.dissect.tools/
- Plaso: https://plaso.readthedocs.io/
- Velociraptor (offline collector): https://docs.velociraptor.app/docs/offline_triage/
- Zeek: https://docs.zeek.org/  ·  Suricata: https://docs.suricata.io/  ·  tshark: https://www.wireshark.org/docs/man-pages/tshark.html
- varc: https://github.com/cado-security/varc  ·  container-explorer: https://github.com/google/container-explorer
- cloudgrep: https://github.com/cado-security/cloudgrep  ·  Invictus Microsoft-Extractor-Suite: https://github.com/invictus-ir/Microsoft-Extractor-Suite
- EZ Tools: https://ericzimmerman.github.io/  ·  KAPE: https://ericzimmerman.github.io/KapeDocs/

## Helper

`scripts/evidence_manifest.py` — stdlib-only, offline, read-only chain-of-custody
hasher (per-file digest, optional `--offset`/`--length` byte range). Tests:
`scripts/tests/test_evidence_manifest.py` (pytest, tmp-file fakes, no network).
