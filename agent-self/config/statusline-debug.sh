#!/usr/bin/env bash
# Debug: dump raw statusLine input to a file so we can see the actual schema
input=$(cat)
echo "$input" > /tmp/claude-statusline-debug.json
echo "DEBUG: see /tmp/claude-statusline-debug.json"
