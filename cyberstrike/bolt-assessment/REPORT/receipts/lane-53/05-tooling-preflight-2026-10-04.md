# lane-53 / 05 — Tooling pre-flight (FINAL-TEST round)

- **Date:** 2026-10-04 (UTC, pre-flight window).
- **Scope item:** final-round pre-flight part — tooling verification for lanes 34 (AWS enum), 36 (mobile static RE), 55/122 (JWT triage).
- **Method:** presence-first verification (`which`, version banners) before any install; installs only where a tool was absent. apt repos touched once (`apt-get update -qq`) for infrastructure traffic only — no test-attempt endpoints contacted during this step.

## Tool inventory

| Tool | Version | Status | Note |
|---|---|---|---|
| boto3 (/opt/venv) | 1.43.107 | VERIFIED (pre-existing) | `/opt/venv/bin/python -c "import boto3"` clean; Python 3.14.7 host |
| awscli (/opt/venv) | 1.46.1 | VERIFIED (pre-existing) | banner `aws-cli/1.46.1 Python/3.14.7 botocore/1.43.62` (vendored botocore, known quirk) |
| jadx | 1.5.6 | INSTALLED (apt) | was absent; installed via `apt-get install -y -qq jadx`, exit 0 |
| apktool | 2.7.0-dirty (pkg 2.7.0+dfsg-7.2) | INSTALLED (apt) | was absent; `-dirty` suffix normal for Debian dfsg build |
| radare2 | 6.0.5 | VERIFIED (pre-existing) | `radare2 6.0.5 0 @ linux-x86-64`; no reinstall performed |
| proxychains4 | 4.17-4 (proxychains-ng) | VERIFIED (pre-existing) | binary present, config found at `/etc/proxychains4.conf`; optional, non-blocking — ready for proxy-routed lanes |
| Java | OpenJDK 25.0.4.1 | VERIFIED (pre-existing) | ≥11 requirement for jadx met; `default-jre-headless` NOT needed |

## Ghidra 12.1.4 headless — decision

**SKIPPED.** No cached tarball found under `/opt` or `/work` (filesystem search, maxdepth 3); no apt package available. A fresh download would exceed the 2–3 minute budget allowed for this optional item. Per operator guidance (findings over tool fidelity), lane-36 static RE proceeds with the jadx 1.5.6 + apktool 2.7.0 + radare2 6.0.5 stack. Skip recorded here as the decision of record.

## Result

**TOOLING: READY.** All required tools for lanes 34/36/55/122 present and version-verified; 2 installed (jadx, apktool), 5 verified pre-existing; Ghidra skip decision recorded; no blocking gaps.

*Leak-gate: PASS — no credentials, tokens, keys, or hostnames in this receipt. No SHA256SUMS file created or modified in this directory (final manifest seals in a later step after all receipts land).*
