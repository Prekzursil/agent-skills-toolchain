#!/usr/bin/env bash
# ASSERTION: under Git Bash (igncr) this CRLF script exits 0; under real WSL/Linux bash `exit 0\r` is a numeric argument error.
echo SUCCESS:git-bash-crlf-cell
exit 0
