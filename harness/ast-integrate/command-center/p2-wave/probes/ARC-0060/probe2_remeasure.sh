#!/usr/bin/env bash
# Mechanically different counter: awk over inventory.tsv (id vs kind fields).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
TSV="$HERE/inventory.tsv"
if [[ ! -f "$TSV" ]]; then
  echo "FAILED:ARC-0060-probe2-sh missing $TSV"
  exit 1
fi

# Field 1: unique ids whose member_csv contains A9.
awk_unique_ids="$(
  awk -F'\t' 'NR>1 && $3 ~ /(^|,)A9(,|$)/ { print $1 }' "$TSV" | sort -u | wc -l
)"
# Field 2: sum of unique ids per kind (partition of the same set).
awk_kind_sum="$(
  awk -F'\t' 'NR>1 && $3 ~ /(^|,)A9(,|$)/ { k[$2]++; ids[$2,$1]=1 }
    END {
      s=0
      for (kind in k) {
        n=0
        for (key in ids) {
          split(key, a, SUBSEP)
          if (a[1]==kind) n++
        }
        s+=n
      }
      print s
    }' "$TSV"
)"
awk_n_kinds="$(
  awk -F'\t' 'NR>1 && $3 ~ /(^|,)A9(,|$)/ { print $2 }' "$TSV" | sort -u | wc -l
)"

# wc -l may pad; strip spaces.
awk_unique_ids="$(echo "$awk_unique_ids" | tr -d '[:space:]')"
awk_kind_sum="$(echo "$awk_kind_sum" | tr -d '[:space:]')"
awk_n_kinds="$(echo "$awk_n_kinds" | tr -d '[:space:]')"

echo "awk_unique_ids=${awk_unique_ids}"
echo "awk_kind_sum=${awk_kind_sum}"
echo "awk_n_kinds=${awk_n_kinds}"
if [[ "${awk_unique_ids}" != "${awk_kind_sum}" ]]; then
  echo "FAILED:ARC-0060-probe2-sh id_count=${awk_unique_ids} kind_sum=${awk_kind_sum}"
  exit 1
fi
echo "SUCCESS:ARC-0060-probe2-sh awk fields agree"
exit 0
