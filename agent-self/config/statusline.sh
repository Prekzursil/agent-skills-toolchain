#!/bin/bash
# Claude Code status line — shows cwd, git branch, date, and system info
CWD=$(basename "$PWD")
BRANCH=$(git branch --show-current 2>/dev/null || echo "no-git")
DATE=$(date +"%Y-%m-%d %H:%M")
# Memory usage (rough, cross-platform)
if command -v free &>/dev/null; then
  MEM=$(free -m 2>/dev/null | awk '/Mem:/{printf "%d/%dMB", $3, $2}')
elif command -v wmic &>/dev/null; then
  MEM="win"
else
  MEM="?"
fi
echo "$CWD [$BRANCH] | $DATE | mem:$MEM"
