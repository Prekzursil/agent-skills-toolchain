# CH-5 volumes metadata leak — re-test addendum 2026-10-03 (lane-48): HELD MEDIUM

Re-measured 2,884 rows vs 2,819 baseline (+65, +2.3% organic). 47 distinct owners (sha8-rendered),
one dominant at 91.6%; 77 bucket/prefix combos across 4 catalogs (dev 2,448 / main 433 / samples 2 /
system 1), 2,410 schemas; 81% are bolt-delta-lake-dev/personal scratch volumes. Commuter-pass
EXTERNAL volumes confirmed x2 (main.ng_incentives -> s3://bs3-{prelive,live}-shrd-boltcommuterpass/).
Severity HELD MEDIUM (metadata-only; no file reads — NO-RE-BURN honored). Evidence:
receipts/lane-48/02-ch5-volumes.txt (statements 1,3,4,5,6). New intel: bolt-autonotebooks.data.boltint.net
and tracking.taxify.eu hostname references in volume paths (hostnames only, no credentials).
