# Email / phishing triage

Analyze a reported message you are authorized to hold. Work from the **original
`.eml`/`.msg`** (full headers), never a forwarded screenshot. Everything here is
static parsing — **do not click links, do not open attachments, do not detonate.**

## 1. Authentication + transport

Read the header chain top-to-bottom and check alignment:

- `Received:` chain — reconstruct the real path; note the first external hop and any
  mismatch with the claimed sender.
- `Authentication-Results:` — SPF / DKIM / DMARC `pass|fail`; check DKIM `d=` and
  return-path/`From:` **alignment**, not just individual passes.
- `From:` vs `Reply-To:` vs `Return-Path:` — divergence is a classic phishing tell.

```
# Parse an .eml with stdlib or eml_parser; extract headers/URLs/attachments:
python3 -c "import email,sys;m=email.message_from_binary_file(open(sys.argv[1],'rb'));\
print(m.get_all('Received'));print(m['authentication-results'])" sample.eml
pip install eml-parser extract-msg      # eml_parser (.eml), extract-msg (Outlook .msg)
```

## 2. Body: URLs and indicators (DEFANGED)

Extract URLs/domains/IPs and keep them **defanged** in all notes and reports
(`hxxp://evil[.]com`, `1.2.3[.]4`). Refanging for enrichment happens only inside the
CTI lane's tooling.

```
extract-msg --json report.msg > report.json     # headers, body, attachments metadata
# List embedded URLs without following them, then defang before recording.
```

Enrich URLs/domains/IPs for reputation via the **CTI lane** (osint `vt_*`, cve/DNS
email-security, darknet CTI) — this skill triages the message; `cti-lookup` enriches
the indicators.

## 3. Attachments (hash → hand off, never run)

```
# Save attachments to an isolated dir, then hash them into the manifest:
python3 ../scripts/evidence_manifest.py ./attachments/* --json > attachments.hashes.json
```

- Office/PDF/archive/script/exe → **hash, record, and hand to the RE skills**
  (`capa-triage` → `malware-analysis-triage`). Macro/OLE inspection (olevba, oleid)
  is static and lives with the malware-analysis lane.
- Do **not** enable macros, open the file in its native app, or "just see what it
  does." No sandbox detonation with live C2 from this skill.

## Notes / stop rules

- Owner-authorized mailbox/report only; preserve the original message file and its hash.
- Report indicators **defanged**; store no live credentials or tokens seen in headers.
- Output: a short verdict (auth results, sender anomalies, defanged IOCs, attachment
  hashes) plus hand-offs (IOCs → CTI, files → RE, detection gaps → detection-as-code).
