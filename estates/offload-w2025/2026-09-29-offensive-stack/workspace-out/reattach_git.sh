#!/bin/bash
# reattach_git.sh - restore git history to the hollowed checkout WITHOUT touching
# the working tree. init + fetch + mixed reset only; no checkout, no clean, no push.
set -e
cd /c/Users/prekzursil/source/agent-skills-toolchain
git init -b main 2>&1
git remote add origin https://github.com/Prekzursil/agent-skills-toolchain.git 2>/dev/null || true
git -c credential.helper='!gh auth git-credential' fetch origin '+refs/heads/*:refs/remotes/origin/*' '+refs/tags/*:refs/tags/*' 2>&1 | tail -3
git reset origin/main 2>&1 | tail -2
git log --oneline -3 2>&1
git status --porcelain | wc -l
echo REATTACH-DONE
