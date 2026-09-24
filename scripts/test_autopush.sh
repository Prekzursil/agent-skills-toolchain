#!/bin/sh
# Controls for the post-commit auto-push hook.
#
# A suite that only proves "it pushed" would pass against a hook that pushes
# blindly and breaks commits. The controls that matter are the ones proving it
# FAILS OPEN and SKIPS unsafe states.
#
# Run: sh scripts/test_autopush.sh

set -u
HOOK="$(cd "$(dirname "$0")" && pwd)/git-hooks/post-commit-autopush"
TMP="${TMPDIR:-/tmp}/autopush-test-$$"
LOG="${HOME}/.agents/logs/autopush.log"
PASS=0
FAIL=0

ok()   { PASS=$((PASS+1)); printf '  PASS %s\n' "$1"; }
bad()  { FAIL=$((FAIL+1)); printf '  FAIL %s -- %s\n' "$1" "$2"; }

[ -f "$HOOK" ] || { echo "FAILED:test - hook not found at $HOOK"; exit 1; }
rm -rf "$TMP"; mkdir -p "$TMP"

newrepo() {
    d="$TMP/$1"
    mkdir -p "$d"
    git init -q --bare "$d/origin.git"
    git clone -q "$d/origin.git" "$d/work" 2>/dev/null
    git -C "$d/work" config user.email t@t
    git -C "$d/work" config user.name t
    mkdir -p "$d/work/.git/hooks"
    cp "$HOOK" "$d/work/.git/hooks/post-commit"
    chmod +x "$d/work/.git/hooks/post-commit"
    echo "$d/work"
}

remote_count() { git -C "$1/origin.git" rev-list --count --all 2>/dev/null || echo 0; }

# ---- A: the core promise. commit -> it is on the remote, unasked.
W=$(newrepo a)
echo 1 > "$W/f.txt"; git -C "$W" add f.txt; git -C "$W" commit -qm one 2>/dev/null
if [ "$(remote_count "$TMP/a")" -ge 1 ]; then ok "A commit auto-pushed"; else bad "A commit auto-pushed" "remote has no commits"; fi

# ---- B: second commit on an already-tracking branch
echo 2 > "$W/g.txt"; git -C "$W" add g.txt; git -C "$W" commit -qm two 2>/dev/null
if [ "$(remote_count "$TMP/a")" -ge 2 ]; then ok "B subsequent commit pushed"; else bad "B subsequent commit pushed" "remote count $(remote_count "$TMP/a")"; fi

# ---- C: FAILS OPEN. broken remote must NOT break the commit.
W=$(newrepo c)
echo 1 > "$W/f.txt"; git -C "$W" add f.txt; git -C "$W" commit -qm one 2>/dev/null
git -C "$W" remote set-url origin "$TMP/c/does-not-exist.git"
echo 2 > "$W/g.txt"; git -C "$W" add g.txt
git -C "$W" commit -qm two >/dev/null 2>&1
RC=$?
LOCAL=$(git -C "$W" rev-list --count HEAD 2>/dev/null)
if [ "$RC" -eq 0 ] && [ "$LOCAL" -eq 2 ]; then ok "C push failure does NOT fail the commit"; else bad "C push failure does NOT fail the commit" "rc=$RC local=$LOCAL"; fi
if tail -20 "$LOG" 2>/dev/null | grep -q 'FAILED:autopush'; then ok "C failure is LOGGED not silent"; else bad "C failure is LOGGED not silent" "no FAILED:autopush in log"; fi

# ---- D: no origin -> skip cleanly, commit still works
W="$TMP/d"; mkdir -p "$W"; git init -q "$W"
git -C "$W" config user.email t@t; git -C "$W" config user.name t
cp "$HOOK" "$W/.git/hooks/post-commit"; chmod +x "$W/.git/hooks/post-commit"
echo 1 > "$W/f.txt"; git -C "$W" add f.txt
git -C "$W" commit -qm one >/dev/null 2>&1
if [ "$?" -eq 0 ] && [ "$(git -C "$W" rev-list --count HEAD)" -eq 1 ]; then ok "D no-origin repo commits fine"; else bad "D no-origin repo commits fine" "commit failed"; fi

# ---- E: mid-REBASE must be SKIPPED, not published half-finished.
#
# NOTE: the obvious test (touch .git/MERGE_HEAD) is UNREACHABLE. Git deletes
# MERGE_HEAD as part of the commit that concludes the merge, so it is already
# gone when post-commit runs -- and that commit is legitimately pushable anyway.
# rebase-merge/ is the marker that genuinely persists: every conflict-resolution
# commit during a rebase fires post-commit while it still exists. That is the
# state where pushing publishes a half-finished tree.
W=$(newrepo e)
echo base > "$W/f.txt"; git -C "$W" add f.txt; git -C "$W" commit -qm base 2>/dev/null
BEFORE=$(remote_count "$TMP/e")
mkdir -p "$W/.git/rebase-merge"
echo x > "$W/h.txt"; git -C "$W" add h.txt
git -C "$W" commit -qm "mid-rebase" >/dev/null 2>&1
AFTER=$(remote_count "$TMP/e")
rm -rf "$W/.git/rebase-merge"
if tail -10 "$LOG" 2>/dev/null | grep -q 'SKIP.*mid-operation'; then ok "E mid-rebase skipped"; else bad "E mid-rebase skipped" "no mid-operation SKIP logged"; fi
if [ "$AFTER" -eq "$BEFORE" ]; then ok "E mid-rebase NOT pushed"; else bad "E mid-rebase NOT pushed" "pushed anyway ($BEFORE -> $AFTER)"; fi

# ---- F: detached HEAD must be skipped
W=$(newrepo f)
echo 1 > "$W/f.txt"; git -C "$W" add f.txt; git -C "$W" commit -qm one 2>/dev/null
SHA=$(git -C "$W" rev-parse HEAD)
git -C "$W" checkout -q --detach "$SHA" 2>/dev/null
echo 2 > "$W/g.txt"; git -C "$W" add g.txt
git -C "$W" commit -qm detached >/dev/null 2>&1
if tail -10 "$LOG" 2>/dev/null | grep -q 'SKIP.*detached'; then ok "F detached HEAD skipped"; else bad "F detached HEAD skipped" "no detached SKIP logged"; fi

# ---- G: the opt-out works
W=$(newrepo g)
echo 1 > "$W/f.txt"; git -C "$W" add f.txt; git -C "$W" commit -qm one 2>/dev/null
BEFORE=$(remote_count "$TMP/g")
echo 2 > "$W/g.txt"; git -C "$W" add g.txt
GIT_AUTOPUSH_OFF=1 git -C "$W" commit -qm two >/dev/null 2>&1
AFTER=$(remote_count "$TMP/g")
if [ "$AFTER" -eq "$BEFORE" ]; then ok "G opt-out honoured"; else bad "G opt-out honoured" "pushed anyway ($BEFORE -> $AFTER)"; fi

rm -rf "$TMP"
printf '\n  %d passed, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] && echo 'SUCCESS:autopush-controls' || echo 'FAILED:autopush-controls'
exit "$FAIL"
