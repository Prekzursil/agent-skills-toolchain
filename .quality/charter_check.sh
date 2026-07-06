#!/usr/bin/env bash
# Charter <-> workflow consistency gate (pure bash).
#
# Fails CI if the closed gate set declared in .quality/charter.yml diverges from the
# `gate-<slug>` step/job markers in .github/workflows/quality.yml. This keeps the
# documented gate model and the actual CI job in lockstep (one-in / one-out discipline),
# mirroring reframe's .quality/charter_check.py and satisfying the QZT reusable-quality.yml
# `bash .quality/charter_check.sh` contract.
#
# Mapping: every gate slug in charter.yml MUST be covered by at least one workflow marker
# `gate-<slug>`, and every `gate-<slug>` marker in the workflow MUST map back to a declared
# gate slug.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
charter="$here/.quality/charter.yml"
workflow="$here/.github/workflows/quality.yml"

[ -f "$charter" ] || { echo "charter_check: missing $charter" >&2; exit 1; }
[ -f "$workflow" ] || { echo "charter_check: missing $workflow" >&2; exit 1; }

# Declared gate slugs from charter.yml (`  - slug: <slug>`), order-preserved.
mapfile -t slugs < <(grep -oE '^[[:space:]]*-[[:space:]]*slug:[[:space:]]*[a-z0-9-]+' "$charter" \
  | sed -E 's/.*slug:[[:space:]]*//')
[ "${#slugs[@]}" -gt 0 ] || { echo "charter_check: no gate slugs parsed from $charter" >&2; exit 1; }

problems=0

# Forward: every charter gate slug has a matching gate-<slug> marker in the workflow.
for s in "${slugs[@]}"; do
  if ! grep -qE "gate-${s}([^a-z0-9-]|\$)" "$workflow"; then
    echo "  - charter gate '${s}' has no matching 'gate-${s}' step/job in quality.yml" >&2
    problems=1
  fi
done

# Reverse: every gate-<slug> marker in the workflow maps back to a declared gate slug.
mapfile -t markers < <(grep -oE 'gate-[a-z0-9-]+' "$workflow" | sed -E 's/^gate-//' | sort -u)
for m in "${markers[@]}"; do
  found=0
  for s in "${slugs[@]}"; do [ "$s" = "$m" ] && found=1 && break; done
  if [ "$found" -ne 1 ]; then
    echo "  - quality.yml has 'gate-${m}' with no matching charter gate" >&2
    problems=1
  fi
done

if [ "$problems" -ne 0 ]; then
  echo "charter_check: FAILED -- charter and quality.yml diverge." >&2
  printf 'charter_check: charter gates : %s\n' "${slugs[*]}" >&2
  printf 'charter_check: workflow gates: %s\n' "${markers[*]}" >&2
  exit 1
fi

echo "charter_check: OK -- ${#slugs[@]} gates consistent: ${slugs[*]}"
