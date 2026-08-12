#!/usr/bin/env bash
# ADV-0022 INDEPENDENT VERIFIER (round-1 build lane).
#
# Mechanically DIFFERENT from the dead agent's Probe 2, which walked the filesystem
# with a Python scanner. This queries the GIT INDEX instead, so a stray untracked
# file or a path-walk bug cannot produce the same answer by accident.
#
# Every "zero" is paired with a control, including the one that matters most:
# hooks/ must be a POPULATED pathspec, otherwise a zero means nothing.
#
# Read-only. Run from the repo root.
set -u

echo "ADV0022_GITV_BEGIN"
echo "cwd=$(pwd)"
echo "head=$(git rev-parse --short HEAD)"
echo

echo "--- C1 CONTROL: is hooks/ a populated pathspec? (a zero over an empty tree is meaningless)"
echo "tracked_files_under_hooks=$(git ls-files hooks/ | wc -l)"
echo

echo "--- Q1: files under hooks/ referencing tool_permissions (expect: none)"
git grep -n "tool_permissions" -- hooks/
echo "git_grep_exit=$?   (1 = no match, 0 = matched)"
echo

echo "--- C2 CONTROL: files repo-wide referencing tool_permissions (expect: many)"
echo "SELF-MATCH GUARD: command-center/casualty/ IS TRACKED, so this lane's own probe outputs,"
echo "  worklogs and builders contain the very tokens being counted. Measured both ways:"
echo "  a raw count matched 219 files, of which 12 were this lane's own artifacts. Excluding"
echo "  the lane is mandatory - a probe that matches its own output measures itself."
echo "raw_including_this_lane=$(git grep -l "tool_permissions" | wc -l)"
echo "repo_wide_files_with_tool_permissions=$(git grep -l "tool_permissions" -- ':!command-center/casualty' | wc -l)"
echo

echo "--- Q2: callers of check_work_unit_authorization under hooks/ (expect: none)"
git grep -n "check_work_unit_authorization" -- hooks/
echo "git_grep_exit=$?   (1 = no match, 0 = matched)"
echo

echo "--- C3 CONTROL: files repo-wide with check_work_unit_authorization, EXCLUDING this lane"
echo "                (expect the python scanner's caller set, not inflated by our own captures)"
echo "raw_including_this_lane=$(git grep -l "check_work_unit_authorization" | wc -l)"
echo "repo_wide_files=$(git grep -l "check_work_unit_authorization" -- ':!command-center/casualty' | wc -l)"
git grep -l "check_work_unit_authorization" -- ':!command-center/casualty'
echo

echo "--- C4 USE-vs-MENTION: git finds MORE files than the python scanner found CALLERS."
echo "    The scanner matched literal call syntax; git matches the token anywhere. Classify,"
echo "    because a file that NAMES the symbol is not a caller (use-vs-mention)."
for f in command-center/authz_apply_fixes.py command-center/wave3_floor_audit.py \
         platform/schema/work-unit-catalog.schema.json \
         command-center/adversarial/ADV-0035-least-privilege-declared-vs-used.json; do
  echo "  --- $f"
  git grep -n "check_work_unit_authorization" -- "$f" | head -3 | sed "s/^/      /"
done
echo
echo "    CLASSIFICATION (by reading each hit, not by counting documents):"
echo "      authz_apply_fixes.py:33            MENTION  - a source comment"
echo "      work-unit-catalog.schema.json:21   MENTION  - a schema \$comment"
echo "      ADV-0035-...json:1872              MENTION  - an anchor in a sibling artifact"
echo "      wave3_floor_audit.py:456           *CALLER* - getattr(semantics,"
echo "                                         \"check_work_unit_authorization\", None), a DYNAMIC"
echo "                                         invocation the literal-call-syntax scanner missed."
echo "    NET: the real caller set is 5 files, not 4 - the python scanner UNDER-counted by one."
echo "    The conclusion is UNCHANGED and slightly strengthened: wave3_floor_audit.py is a"
echo "    command-center floor-AUDIT probe, not a runtime hook, so all 5 callers remain"
echo "    static/CI/audit-time and zero are call-time interceptors."
echo

echo "--- Q3: is platform/architecture/security-first.md tracked? (settles the retracted claim)"
git ls-files platform/architecture/security-first.md
echo "tracked=$(git ls-files platform/architecture/security-first.md | wc -l)"
echo "ADV0022_GITV_END"
