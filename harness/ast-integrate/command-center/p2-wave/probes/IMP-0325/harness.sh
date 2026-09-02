#!/usr/bin/env bash
# IMP-0325 shell harness: exercise the documented exit-code matrix.
# Does not use `set -e` because non-zero CLI codes are the measurement.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../../../.." && pwd)"
cd "$REPO"
export PYTHONDONTWRITEBYTECODE=1
CLI=(python3 -B tools/council/cli/main.py)
FIX="command-center/p2-wave/probes/IMP-0325/fixtures"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/imp0325-harness.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

code() {
  python3 -B -c "import sys; sys.path.insert(0, 'tools/council/cli'); import exit_codes as e; print(getattr(e, sys.argv[1]))" "$1"
}

RUN_OK="$(code EXIT_RUN_OK)"
RESUME_OK="$(code EXIT_RESUME_OK)"
INSPECT_OK="$(code EXIT_INSPECT_OK)"
LIST_OK="$(code EXIT_LIST_PRESETS_OK)"
EXPLAIN_OK="$(code EXIT_EXPLAIN_OK)"
COUNCIL_FAILED="$(code EXIT_COUNCIL_FAILED)"
MISSING="$(code EXIT_MISSING_ARTIFACT)"
NO_CK="$(code EXIT_NO_CHECKPOINT)"
NO_PRESETS="$(code EXIT_NO_PRESETS)"
NO_LINEAGE="$(code EXIT_NO_LINEAGE)"
USAGE="$(code EXIT_USAGE)"

fail=0
printf "case\texpected\tactual\tok\n"

row() {
  local name="$1"
  local expected="$2"
  shift 2
  "${CLI[@]}" "$@" >"$TMP/stdout.txt" 2>"$TMP/stderr.txt"
  local actual=$?
  local ok="FAIL"
  if [ "$actual" -eq "$expected" ]; then
    ok="PASS"
  else
    fail=1
  fi
  printf "%s\t%s\t%s\t%s\n" "$name" "$expected" "$actual" "$ok"
}

row run/happy "$RUN_OK" run --spec "$FIX/happy.json" --out "$TMP/happy.json"
row run/failed-council "$COUNCIL_FAILED" run --spec "$FIX/failed-council.json" --out "$TMP/failed.json"
row run/no-write "$MISSING" run --spec "$FIX/no-write.json" --out "$TMP/no-write.json"
row resume/checkpoint "$RESUME_OK" resume --checkpoint "$FIX/checkpoint.json" --out "$TMP/resumed.json"
row resume/missing "$NO_CK" resume --checkpoint "$TMP/does-not-exist.json" --out "$TMP/resume-missing.json"
row inspect/success "$INSPECT_OK" inspect --artifact "$FIX/artifact-success.json"
row inspect/missing "$MISSING" inspect --artifact "$TMP/does-not-exist.json"
row list-presets/default "$LIST_OK" list-presets
row list-presets/empty "$NO_PRESETS" list-presets --catalog "$FIX/empty-presets.json"
row explain/success "$EXPLAIN_OK" explain --artifact "$FIX/artifact-success.json"
row explain/no-rule "$NO_LINEAGE" explain --artifact "$FIX/artifact-no-rule.json"
row unknown/verb "$USAGE" not-a-command

exit "$fail"
