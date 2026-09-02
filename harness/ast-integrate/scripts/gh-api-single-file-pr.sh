#!/usr/bin/env bash
# Land a single-file change as a PR via the GitHub Contents API — NO local checkout.
#
# WHY: a fresh `git worktree`/clone of a git-crypt repo fails the smudge filter on
# encrypted files (no key), and a local branch switch can drag along uncommitted
# secrets in the working tree. Doing the change SERVER-SIDE via `gh api` sidesteps
# both: no checkout, no smudge, no chance of committing the working tree's secrets.
#
# Usage:
#   gh-api-single-file-pr.sh <owner/repo> <path/in/repo> <local-new-content-file> \
#       <branch> <commit-msg> <pr-title> [pr-body] [base-branch]
#
# Ends with a §4-style SUCCESS:/FAILED: marker.
set -euo pipefail

REPO="${1:?owner/repo}"; FPATH="${2:?path in repo}"; CONTENT_FILE="${3:?local content file}"
BRANCH="${4:?branch}"; MSG="${5:?commit message}"; TITLE="${6:?pr title}"
BODY="${7:-$MSG}"; BASE="${8:-main}"

command -v gh >/dev/null 2>&1 || { echo "FAILED:gh-api-single-file-pr need-gh-cli" >&2; exit 3; }
[ -f "$CONTENT_FILE" ] || { echo "FAILED:gh-api-single-file-pr content-file-missing=$CONTENT_FILE" >&2; exit 3; }

# 1. base sha
BASE_SHA="$(gh api "repos/$REPO/git/ref/heads/$BASE" --jq .object.sha)" \
  || { echo "FAILED:gh-api-single-file-pr base-ref=$BASE" >&2; exit 1; }

# 2. create the branch ref (ignore 'Reference already exists')
gh api -X POST "repos/$REPO/git/refs" -f "ref=refs/heads/$BRANCH" -f "sha=$BASE_SHA" >/dev/null 2>&1 \
  || echo "note: branch $BRANCH may already exist — reusing" >&2

# 3. current blob sha of the file on base (empty => new file)
FILE_SHA="$(gh api "repos/$REPO/contents/$FPATH?ref=$BASE" --jq .sha 2>/dev/null || true)"

# 4. base64 the new content (no newlines)
B64="$(base64 -w0 "$CONTENT_FILE" 2>/dev/null || base64 "$CONTENT_FILE" | tr -d '\n')"

# 5. PUT the content on the branch
PUT_ARGS=(-X PUT "repos/$REPO/contents/$FPATH" -f "message=$MSG" -f "content=$B64" -f "branch=$BRANCH")
[ -n "$FILE_SHA" ] && PUT_ARGS+=(-f "sha=$FILE_SHA")
gh api "${PUT_ARGS[@]}" >/dev/null \
  || { echo "FAILED:gh-api-single-file-pr put=$FPATH" >&2; exit 1; }

# 6. open the PR
URL="$(gh pr create --repo "$REPO" --base "$BASE" --head "$BRANCH" --title "$TITLE" --body "$BODY" 2>/dev/null)" \
  || { echo "FAILED:gh-api-single-file-pr pr-create (content committed to $BRANCH)" >&2; exit 1; }

echo "SUCCESS:gh-api-single-file-pr $REPO $BRANCH $FPATH -> $URL"
