#!/usr/bin/env bash
# Claude Code status line — compact conversational (fits terminal width)
input=$(cat)

# --- Auth (cached 60min) ---
ac="/tmp/claude-auth-cache.json"
if [ ! -f "$ac" ] || [ "$(find "$ac" -mmin +60 2>/dev/null)" ]; then
  claude auth status --json 2>/dev/null > "$ac" || echo '{}' > "$ac"
fi
email=$(jq -r '.email // "?"' "$ac" 2>/dev/null)
plan=$(jq -r '.subscriptionType // "?"' "$ac" 2>/dev/null)

# --- Core fields ---
model=$(echo "$input" | jq -r '.model.display_name // .model.id // "?"')
used=$(echo "$input" | jq -r '.context_window.used_percentage // 0')
rem=$(echo "$input" | jq -r '.context_window.remaining_percentage // 100')
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // 0')
five=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')

# Rate limit reset
rl=""
if [ -n "$five" ]; then
  fi=$(printf "%.0f" "$five")
  rs=""
  if [ -n "$five_reset" ]; then
    d=$(( five_reset - $(date +%s) ))
    if [ $d -gt 0 ]; then
      h=$(( d/3600 )); m=$(( (d%3600)/60 ))
      [ $h -gt 0 ] && rs="resets ${h}h${m}m" || rs="resets ${m}m"
    fi
  fi
  rl="5h:${fi}%used"
  [ -n "$rs" ] && rl="$rl ($rs)"
fi
wk=""
[ -n "$seven" ] && wk="weekly:$(( 100 - $(printf '%.0f' "$seven") ))%left"

# Single line output
out="${email} (${plan}) · ${model} · ctx:${used}%/${rem}%rem · value:\$$(printf '%.2f' "$cost")(in plan)"
[ -n "$rl" ] && out="$out · $rl"
[ -n "$wk" ] && out="$out · $wk"

printf "%s" "$out"
