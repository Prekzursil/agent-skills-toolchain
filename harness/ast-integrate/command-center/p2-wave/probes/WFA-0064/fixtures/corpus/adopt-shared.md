# ADOPT-AS-IS shared handoff plus canary

## DEFINE `shared.handoff-token`
shared.handoff-token is a workflow mechanism: a typed token passed from one stage to the next so a downstream stage can refuse to run without the upstream receipt. Discriminating example: an empty string is not a token; the receiver checks a named receipt id.

## DEFINE `canary.known-present`
canary.known-present is a workflow mechanism planted so the independent corpus search must find a known-present surviving implementation before any search silence is trusted. Discriminating example: this DEFINE heading in a non-terminal candidate body is the canary hit; a search that misses it is broken and must not certify orphans.
