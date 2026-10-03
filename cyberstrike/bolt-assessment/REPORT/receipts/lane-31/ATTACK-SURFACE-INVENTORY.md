# LANE 31 — ATTACK-SURFACE-INVENTORY (refreshed 2026-10-01, unauthenticated/observational)

Sources: DNS census (119 hosts, 0 wildcard), TLS/HTTP host probes (11 handshakes), 3×6 SNI edge matrix, 15 anonymous S3 checks, unauthenticated GitHub org pull. Baseline: SSOT_2026-09-06.md §2. All pacing ≤1 rps, single attempt per (target,endpoint). Cert IDs are sha8 of leaf sha256 (full hex on disk in host-probes / edge-sni-matrix receipts).

## 1. Edge / Cloudflare Spectrum (mTLS envoy admin planes)
- 172.65.240.204 — prod edge. Live vhosts (HTTP/2 200): admin.bolt.eu, admin.taxify.eu, beehive.bolt.eu (all serve envoy mTLS interstitial "Certificate needed", S3-backed assets, etag a14c76b7…, last-mod 2026-07-29). 404: pki.taxify.eu, beehive.taxify.eu, admin-panel.taxify.eu (DNS: NXDOMAIN). Certs: *.bolt.eu & *.taxify.eu wildcards (sha8 08c2a9f3 on taxify wildcard).
- 172.65.223.108 — NEW active edge (replaces SSOT prelive). Mirrors prod vhost-by-vhost.
- 172.65.188.16 — TCP/TLS open, NO certificate on any SNI (emptied).
- admin.bolt.eu DNS → mtls-proxyprotocol-envoy…pacloudflare.com → 172.65.240.204; admin.taxify.eu DNS → fba10ea1…pacloudflare.com → 172.65.223.108.
- Gate posture: HTTP 200 = interstitial only; client-cert enforcement at envoy; NO client cert sent (unauthenticated observation only).
- beehive.bolt.eu: live vhost on both edges, NO public DNS record (SNI-only).

## 2. Databricks data plane
- bolt-common.cloud.databricks.com — public ingress (no privatelink); TLS cert sha8 8bced7de; /login 404; header x-databricks-org-id=3598988355446810 (org tenant-confirmed); HSTS preload; server: databricks. Warehouse b39957853740b21d (baseline, not touched).

## 3. Mobile / rider-driver plane (all behind ws.bolt.eu Cloudflare CDN 104.18.36.249 / 172.64.151.7 unless noted)
- rider-broker.ws.bolt.eu, driver-broker.ws.bolt.eu — MQTT-over-WS endpoints; shared cert sha8 baa99e0f; unauth GET / 404; WS/MQTT handshake NOT attempted (lane 47).
- api.iam.bolt.eu — cert sha8 372df0b0; 404.
- fleet-auth.bolt.eu — cert sha8 9b2516c4; 404.
- node.bolt.eu — rental-web BFF; 403 JSON FORBIDDEN; full CSP, report-uri …/app-log/node/csp/report.
- user.live.boltsvc.net — boltsvc.net zone; cert sha8 4bd08b93; 404; XFO DENY + CSP default-src 'none'.
- Public web/marketing: www.bolt.eu → 3.174.230.x (AWS ALB class), static → 13.227.146.x (CloudFront), courier → 18.244.102.x, business/help → 18.244.146.x, support → 18.66.233.x (CloudFront POPs).

## 4. DNS posture
- bolt.eu: NS×4, MX×5, TXT×24; DMARC p=quarantine (easydmarc rua/ruf); SPF present.
- taxify.eu: SOA/NS×4/MX×5/TXT×6; DMARC p=quarantine;pct=25; SPF google+amazonses+sendgrid (~all).
- boltsvc.net zone live. 119 hosts resolved across census; wildcard ruled out (random-label NXDOMAIN). beehive.taxify.eu / admin-panel.taxify.eu NXDOMAIN.
- SaaS verification TXT tokens observed: google, apple, jamf, airtable, miro, mixpanel, openai, anthropic, cursor, jetbrains, linear, canva, microsoft, CKO/CommandK, ps-cd (counts/shapes only; no PII values retained).
- WATCH7 testregistry.bolt.eu → CNAME TTL 300 → k8s-jfrogart-jfrogart-d21d9676b1-1146137979.eu-central-1.elb.amazonaws.com (JFrog Artifactory / EKS ELB). DNS-ONLY — untouched.

## 5. S3 (anonymous-only, one HEAD + one GET list-type=2 each)
- EXIST + deny-anonymous (403): bolt-server (us-east-1), bolt-verification-documents (eu-central-1), bolt-vault, bolt-delta-lake-sensitive.
- NoSuchBucket (404; global S3 namespace ⇒ exact shape exists nowhere): bolt-data, bolt-data-ws, bolt-datascience, bolt-geo, bolt-driver-api, bolt-root, bolt-spa, bolt-tokens, bolt-common, boltsvc, boltint.
- FOLLOW-UP 2026-10-01 (corpus receipt): EXIST + deny-anonymous: bs3-live-srvg-geoextraction-geoextractionconfigs (eu-central-1, x-amz-bucket-region header). NoSuchBucket: rider-locations-sqs, driver-locations-sqs, courier-locations-sqs, dapingestion, ads-sponsored-listing (SSOT L117 shorthands are not literal bucket names; `rider/driver/courier-locations-sqs` = one lake with key prefixes).
- Anonymous reads: ZERO across 21 names. ListBucketResult: ZERO. Exact 14-CSP enumeration absent from mounted corpus → PARTIAL-GUESSED, fail-closed (host-side lane reports hold the list).
- TALLY CORRECTION (follow-up audit): original inventory line understated exist-and-deny as 2 — receipt verbatim shows bolt-vault and bolt-delta-lake-sensitive also 403. No finding changes; split corrected 2/13 → 4/11 for phase-D names.

## 6. GitHub org bolteu (unauthenticated API)
- org id 37693190, created 2018-03-23; public_repos=38 (baseline 31 → +7).
- 38 public repos (full list in receipt; includes aedes MQTT-broker family, kalev, duo-buildroot-sdk, osm_mapping, osrm-backend-deprecated, fastlane(+plugin), setup-xcode/setup-ruby/setup-firebase, iOS-interview-assessment×3, checkout-sparse, agent-js-jest, auto-cancel-redundant-job, Content-Security-Policy, …). 15 repo-meta rows captured (fork/visibility/default_branch).
- Operator PAT sha8 94ea4604 NOT used (reserved).

## Lane handoffs
- lane 44 (creds): GitHub +7/lockdown-lifted elevates clone-era PAT re-check.
- lane 45 (Databricks): org id re-confirmed; ingress unchanged.
- lane 47 (web/API): MQTT-WS upgrade behavior, node.bolt.eu /app-log chain, beehive.bolt.eu SNI vhost.
- lane 46 (JFrog): testregistry ELB topology note.
- lane 51: Zendesk CNAME recheck (2026-10-04) unaffected by this census.
