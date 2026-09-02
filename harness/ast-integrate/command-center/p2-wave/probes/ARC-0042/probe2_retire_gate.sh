#!/usr/bin/env bash
# Mechanically different probe: awk over the commit-message-shaped citation note.
# Reads Differential-Sha256 (not the JSON payload_sha256 field probe 1 uses).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NOTE="$HERE/fixtures/retirement.note"
if [[ ! -f "$NOTE" ]]; then
  echo "FAILED:ARC-0042-probe2-sh missing $NOTE"
  exit 1
fi

awk_n_rails="$(
  awk '/^Rail: / { n++ } END { print n+0 }' "$NOTE"
)"
awk_n_shas="$(
  awk '/^Differential-Sha256: / { n++ } END { print n+0 }' "$NOTE"
)"
awk_mcp_sha="$(
  awk '
    $1=="Rail:" && $2=="mcp-thread" { hit=1; next }
    hit && $1=="Differential-Sha256:" { print $2; exit }
  ' "$NOTE"
)"
awk_fan_sha="$(
  awk '
    $1=="Rail:" && $2=="exec-fanout" { hit=1; next }
    hit && $1=="Differential-Sha256:" { print $2; exit }
  ' "$NOTE"
)"
awk_mail_sha="$(
  awk '
    $1=="Rail:" && $2=="agent-mail" { hit=1; next }
    hit && $1=="Differential-Sha256:" { print $2; exit }
  ' "$NOTE"
)"

echo "awk_n_rails=${awk_n_rails}"
echo "awk_n_shas=${awk_n_shas}"
echo "awk_mcp_sha=${awk_mcp_sha}"
echo "awk_fan_sha=${awk_fan_sha}"
echo "awk_mail_sha=${awk_mail_sha}"

if [[ "${awk_n_rails}" != "3" || "${awk_n_shas}" != "3" ]]; then
  echo "FAILED:ARC-0042-probe2-sh rails=${awk_n_rails} shas=${awk_n_shas}"
  exit 1
fi
if [[ ${#awk_mcp_sha} -ne 64 || ${#awk_fan_sha} -ne 64 || ${#awk_mail_sha} -ne 64 ]]; then
  echo "FAILED:ARC-0042-probe2-sh sha length"
  exit 1
fi
echo "SUCCESS:ARC-0042-probe2-sh awk citation fields"
exit 0
