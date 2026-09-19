#!/usr/bin/env bash
# critic-v2 gate dry run — MY extracted gate (gate-doc.sh, straight from the document) in a throwaway repo.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"; export VENV="$HERE/myvenv"; TOOLS="$HERE/dry-tools"; REPO="$HERE/dry-repo"; WT="$HERE/dry-repo-wt"
rm -rf "$TOOLS" "$REPO" "$WT"; mkdir -p "$TOOLS"
cp "$HERE/gate-doc.sh" "$TOOLS/gate.sh"; GATE_SHA="$(sha256sum < "$TOOLS/gate.sh" | cut -d' ' -f1)"
G() { bash "$TOOLS/gate.sh" --gate-sha256 "$GATE_SHA" "$@"; }
pass=0; fail=0; chk() { if eval "$2"; then pass=$((pass+1)); echo "PASS $1"; else fail=$((fail+1)); echo "FAIL $1"; fi; }

git init -q "$REPO"; cd "$REPO"; git config user.email t@l; git config user.name t; git config commit.gpgsign false
printf 'import torch\ndef f():\n    return images\n' > app.py
mkdir -p tests; printf 'def test_a():\n    assert 1\ndef test_b():\n    assert 2\n' > tests/test_base.py
git add -A; git commit -qm "base"; BASE="$(git rev-parse HEAD)"
printf '{"base_sha":"%s","baseline_collected":2,"skipped_ids":[]}' "$BASE" > "$TOOLS/baseline.json"
BASE_SHA="$(sha256sum < "$TOOLS/baseline.json" | cut -d' ' -f1)"
PINS=(--baseline "$TOOLS/baseline.json" --baseline-sha256 "$BASE_SHA")
CLEAN() { ( cd "$WT" && BROKEN_SHA="$BASE" G "${PINS[@]}" --clean --self-test --journeys --base "$BASE" --out "$WT/.gate/last_run.json" "$@" ) ; }

echo "== T1 self-pin: wrong --gate-sha256 exits 66"
G --gate-sha256 0000000000000000000000000000000000000000000000000000000000000000 "${PINS[@]}" >/dev/null 2>&1; rc=$?
chk "T1 exit 66 (fail-closed self integrity)" "[ $rc = 66 ]"

echo "== T2 tampered baseline is RED at the pre-step"
G --gate-sha256 "$GATE_SHA" --baseline "$TOOLS/baseline.json" --baseline-sha256 deadbeef >/dev/null 2>&1; rc=$?
chk "T2 exit nonzero + baseline step red" "[ $rc = 1 ] && grep -q '\"name\": \"baseline\"' .gate/last_run.json"

echo "== T3 good tree, detached worktree: --clean --self-test --journeys"
printf 'def f():\n    return 1\n' > app.py
mkdir -p tests/journeys
printf 'import pytest\n@pytest.mark.skip(reason="needs=platform-08a-worker-pure")\ndef test_h1():\n    assert True\n' > tests/journeys/test_h1.py
git add -A; git commit -qm "good tree"
git worktree add --detach "$WT" HEAD >/dev/null 2>&1
CLEAN >/dev/null 2>&1; rc=$?
python3 -c "
import json; d=json.load(open('$WT/.gate/last_run.json'))
st=d.get('red_proof') or {}; jo=d.get('journeys') or {}
steps={s['name']:s['exit_code'] for s in d['steps']}
print('steps:', steps)
print('broken_red:', st.get('broken_red'), 'false_claim_red:', st.get('false_claim_red'))
print('journeys:', jo)
"
chk "T3a exit 0 on the good tree" "[ $rc = 0 ]"
chk "T3b self-test broken_red true" "python3 -c \"import json;print(json.load(open('$WT/.gate/last_run.json'))['red_proof']['broken_red'])\" | grep -q True"
chk "T3c false_claim_red == 'true' (the gate-written fixture reds claim-lint, C-2)" "python3 -c \"import json;print(json.load(open('$WT/.gate/last_run.json'))['red_proof']['false_claim_red'])\" | grep -qx true"
chk "T3d journeys counted the needs= skip (C-4)" "python3 -c \"import json;j=json.load(open('$WT/.gate/last_run.json'));print(j['journeys']['skipped_needs'])\" | grep -q platform-08a-worker-pure"
chk "T3e import-app conditional + non-blocking with api/app.py absent (C-1)" "python3 -c \"import json;d=json.load(open('$WT/.gate/last_run.json'));s=[s for s in d['steps'] if s['name']=='import-app'][0];print(s['blocking'],s['exit_code'])\" | grep -qx '0 0'"

echo "== T4 digest equality: same tree, same args, independent executions"
D1="$(CLEAN 2>/dev/null | awk '/^LEDGER_DIGEST /{print $2}')"
D2="$(CLEAN 2>/dev/null | awk '/^LEDGER_DIGEST /{print $2}')"
S1="$(CLEAN 2>/dev/null | awk '/^LEDGER_SHA256 /{print $2}')"
echo "digest1=${D1:0:16} digest2=${D2:0:16} sha=${S1:0:16}"
chk "T4a two runs, same LEDGER_DIGEST (timestamp-free canon)" "[ \"$D1\" = \"$D2\" ] && [ -n \"$D1\" ]"
chk "T4b LEDGER_SHA256 differs from the digest (timestamps covered)" "[ \"$S1\" != \"$D1\" ]"

echo "== T5 a non-needs journey skip is RED (C-4 the other way)"
cd "$REPO"; git worktree remove --force "$WT" >/dev/null 2>&1
printf 'import pytest\n@pytest.mark.skip(reason="flaky on CI")\ndef test_h2():\n    assert True\n' > tests/journeys/test_h2.py
git add -A; git commit -qm "bad journey"; git worktree add --detach "$WT" HEAD >/dev/null 2>&1
CLEAN >/dev/null 2>&1; rc=$?
python3 -c "import json;j=json.load(open('$WT/.gate/last_run.json'));print('skipped_other:', j['journeys']['skipped_other'], 'steps:', {s['name']:s['exit_code'] for s in j['steps']})"
chk "T5 exit nonzero with skipped_other >= 1" "[ $rc = 1 ]"
cd "$HERE"; echo "== SUMMARY: $pass pass, $fail fail"; [ $fail = 0 ]
