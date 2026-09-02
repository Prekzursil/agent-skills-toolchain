#!/bin/sh
# Control-bad: process substitution. POSIX sh / PowerShell do not parse <().
cat <(echo hi)
