# FINAL-TEST RECEIPT 07 — lane-36 Stage A: Certificate / Keystore / Pinning Report

- Engagement: Bolt Technology OÜ red-team (operator directive 2026-10-04, verbatim authority on record)
- Round / subtask: FINAL-TEST / subtask-143 (lane-36 mobile RE, stage A, phase 2)
- Date: 2026-10-05
- Register impact: NONE (register close-out is subtask-147)
- OFFLINE ATTESTATION: zero network, zero secret validations, proxy vault untouched, NEVER-ROTATE intact. Full report: /work/lane36/analysis/cert_keystore_report.md sha256 60308caab4f1142515982ac7bd785c926f70065b7b8dec0a0417a31e51a80d2e

## 1. Shared release signing certificate (BOTH apps + all 4 splits)
- Subject/Issuer: self-signed, O=Mtakso OU
- Key: RSA 1024-bit (WEAK), e=65537
- Validity: 2013-06-25 -> 2038-06-19
- sha256 fingerprint a75c6372a0b67db01686b47df68c91516ee16229eec4c0c67d355e32207c6617 (sha8 a75c6372)
- Signs ee.mtakso.client AND ee.mtakso.driver plus every config split -> single release key across the fleet.
- FINDING: RSA-1024 is below modern minimums; compromise of this one key would permit malicious updates signed as EITHER app (single point of failure for update integrity).

## 2. cert0 (Google Play provenance stamp)
- client_cert0.der is byte-identical to driver_cert0.der (sha256 prefix 3257d599 / sha8 3257d599); extracted PEMs also byte-identical (sha8 13917b39). The *_cert0.der.pem extraction naming is the EXPECTED convention.
- Identity: CN=Android, O=Google Inc.; RSA-4096; CA:TRUE; validity 2020 -> 2050 -> Google Play "Frosting" install-source stamp — NOT the release key and NOT a transport CA.
- DER-to-PEM modulus pairing verified MATCH during extraction.

## 3. APK signature blocks
- Sig-block IDs observed: 0x7109871a (v2), 0xf05368c0 (v3), 0x6dff800d, 0x2146444e, 0x42726577 ("Brew" advertising-ID block); NO 0xf3000300 (v4/incremental) block present.

## 4. Embedded keystore / transport-cert sweep
- Trees (jadx_client 35,452 files; jadx_driver 64,465 files) + at_client/at_driver + splits: ZERO *.bks / *.p12 / *.pfx / *.jks / *.keystore and ZERO transport/CA certs (*.crt/*.cer/*.pem) beyond the signing material catalogued above.
- Splits META-INF (inspected via unzip -l only): expected PKCS#7 signature files only, sha8s 56d65335 / a03ea2ca / 1cabdacd / a4dafe89.

## 5. Network security config & TLS pinning
- Exactly ONE network_security_config.xml (at_driver/res/xml/): cleartext permitted ONLY for m.likumi.lv + subdomains (LV legal-portal in-app view); NO custom trust anchors; NO pin-set; certificate-transparency directives absent.
- OkHttp CertificatePinner / pinning code: ZERO occurrences in either decompiled tree -> NO TLS CERTIFICATE PINNING in either production app. FINDING: on devices trusting a user-installed CA (or rooted devices), rider AND driver TLS traffic is interceptable; combine with the exported-component/deep-link surface in receipt 09.
- Pin digests recorded: none exist (no pin-set, no pinner) — nothing to record.

## 6. Stage-B follow-up
- Fingerprint netty/OpenSSL/BoringSSL versions from native libs -> CVE match (PROBING_CERT/PROBING_KEY constants already localize netty SslUtils in classes5.dex, see receipt 08).
- Reassess pinning absence specifically against rider-broker.ws.bolt.eu / driver-broker.ws.bolt.eu WebSocket auth flows.

## 7. Closing attestations (subtask-143, 2026-10-05)
- Zero network / zero DNS; zero secret validations; sha8-only references; zero key material recorded (public cert metadata + public pin digests only — no pin digests exist).
- Zero PII; zero credential values; zero proxy userinfo; NEVER-ROTATE intact; vault touched only by passive stat + line-hash check.
- Leak-gate over this receipts dir: PASS.
- LANE-REGISTER.md untouched (byte-identical x3, 286 lines, sha256 988593397d0b2112424d17e0923c13cf9cc1b2fb4866b79f081581c77cb49b17).
