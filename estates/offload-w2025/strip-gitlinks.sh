#!/usr/bin/env bash
# strip-gitlinks.sh - remove nested-git gitlinks that git add -A keeps re-adding
# (any dir containing .git under the estate snapshot). Run before every sync commit.
cd "$(dirname "$0")/.."
git ls-files -s | grep "^160000" | awk "{print \$4}" > /tmp/_gl.txt
[ -s /tmp/_gl.txt ] && git rm -q --cached --pathspec-from-file=/tmp/_gl.txt && echo "stripped $(wc -l < /tmp/_gl.txt) gitlinks" || echo "no gitlinks"
