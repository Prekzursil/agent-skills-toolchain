#!/usr/bin/env bash
# Claude Code status line — two-line, threshold-gated operator HUD (beat-the-field build).
#
#   L1 (identity, stable):  SESSION(→Explorer) · [auth if non-default] · model[/1M] · [mode-drift] · goal
#   L2 (telemetry, gated):  ctx:N%[!] · 5h <countdown>[!] · [wk!] · [ag:N⚠age] · [mem!] · [git]
#   + OSC 9;4 tab-ring/taskbar = worst-of {ctx%, 5h-used%, mem%}   (out-of-band, 0 rows)
#
# DESIGN DECISIONS: see out/GRILL-DECISIONS.md (G-1..G-12). Highlights:
#   * ctx% is denominator-aware (shows /1M on the 1M window; 85% of 1M ≈ 850k, not 170k).
#   * silent-until-threshold: cost cut; wk/auth/mem/git/mode-drift appear only when relevant.
#   * ≤2 coloured segments (16-colour, theme-mapped); glyph !/⚠ carries it on mono / NO_COLOR.
#   * SESSION leftmost (notifications eat the right edge). Collapse to 1 line < 80 cols.
#   * SECURITY: session_name / goal / branch are STRIPPED of C0 control bytes before emit
#     (they are user-influenced → escape-injection guard), then wrapped in OUR own colour/OSC.
#   * PERF: one jq parse; heavy reads (find/git) are TTL-cached + existence-gated; atomic cache writes.
#
# Env knobs:  STATUSLINE_SESSION_LINK protocol|file|none · STATUSLINE_COLOR 0|1 · NO_COLOR
#   STATUSLINE_TABRING 0|1 · STATUSLINE_DEFAULT_ACCT <local-part> · STATUSLINE_GOAL_MAX <n> · STATUSLINE_SEP

input=$(cat)
sep="${STATUSLINE_SEP:- · }"
US=$'\x1f'

# cache dir (TMPDIR may be a backslash Windows path from the parent → fall back to /tmp)
cdir="${TMPDIR:-/tmp}"; { [ -d "$cdir" ] && [ -w "$cdir" ]; } || cdir=/tmp

# ------------------------------------------------------------ jq fallback ----
if ! command -v jq >/dev/null 2>&1; then
  sid_raw=$(printf '%s' "$input" | tr ',' '\n' \
    | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
  [ -n "$sid_raw" ] && printf 'sess:%s%s(jq missing)' "${sid_raw:0:8}" "$sep" || printf '(jq missing)'
  exit 0
fi

# --------------------------------------------------------- single jq read ----
# Delimiter U+001F (non-whitespace) so absent fields do NOT shift `read` columns.
IFS="$US" read -r sid sname tpath model model_id used ctxsize exceeds \
    five five_reset seven cwd pdir gitwt pr_num pr_url effort ostyle thinking cost dur toks <<EOF
$(printf '%s' "$input" | jq -r '[
    (.session_id//""),(.session_name//""),(.transcript_path//""),
    (.model.display_name // .model.id // "?"),(.model.id//""),
    (.context_window.used_percentage//0),(.context_window.context_window_size//200000),
    (.exceeds_200k_tokens//false),
    (.rate_limits.five_hour.used_percentage//""),(.rate_limits.five_hour.resets_at//""),
    (.rate_limits.seven_day.used_percentage//""),
    (.cwd // .workspace.current_dir // ""),(.workspace.project_dir//""),(.workspace.git_worktree//""),
    (.pr.number//""),(.pr.url//""),
    (.effort.level//""),(.output_style.name//""),(.thinking.enabled//""),
    (.cost.total_cost_usd//0),(.cost.total_duration_ms//0),
    (.context_window.total_input_tokens // .context_window.current_usage.input_tokens // 0)
  ] | map(tostring | gsub("[[:cntrl:]]";"")) | join("\u001f")' 2>/dev/null)
EOF

now=$(date +%s)

# ----------------------------------------------- SECURITY: strip C0 controls --
# EVERY JSON field is control-stripped INSIDE the jq above — map(gsub "[[:cntrl:]]") runs BEFORE the
# delimiter read, so no field can (a) inject an ESC/OSC/BEL escape into the terminal, or (b) carry a
# U+001F that would shift read-columns (the session_name→tpath link-spoof). san() below is the same
# strip for the few values that do NOT pass through that jq: the goal-file text and the cache reads.
san() { printf '%s' "$1" | tr -d '\000-\037\177'; }

# ------------------------------------------------------------- colour setup --
if [ -z "$NO_COLOR" ] && [ "${STATUSLINE_COLOR:-1}" != "0" ]; then
  A=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; Z=$'\033[0m'   # amber / red / dim / reset
else A=""; R=""; D=""; Z=""; fi
ncol=0   # coloured-segment counter (cap ≤2). MUST be mutated in the MAIN shell, never in a $() subshell —
         # a subshell copy of ncol is discarded, so the cap silently fails (measured: 3 coloured segments).
# band VAL AMBER RED -> sets $BAND = ""|amber|red (crossing level, UNCAPPED). Call directly, not via $().
band() { BAND=""; local v="${1%%.*}"; case "$v" in ''|*[!0-9]*) return;; esac
  if [ "$v" -ge "$3" ]; then BAND=red; elif [ "$v" -ge "$2" ]; then BAND=amber; fi; }
# colorize LEVEL TEXT [GLYPH] -> sets $REPLY. The GLYPH (default `!`) is appended on ANY crossing so a mono /
# NO_COLOR / colour-blind reader still sees it; COLOUR is added only while under the ≤2 cap, incrementing ncol
# in the MAIN shell. Call DIRECTLY (never inside $()) or the ncol increment is lost and the cap breaks.
colorize() { local g="${3-!}"; case "$1" in
    red|amber) REPLY="$2$g"; if [ "$ncol" -lt 2 ]; then ncol=$((ncol+1)); [ "$1" = red ] && REPLY="$R$REPLY$Z" || REPLY="$A$REPLY$Z"; fi ;;
    *) REPLY="$2" ;; esac; }

# ---------------------------------------------------- worst-of for tab-ring --
worst=0; wst() { local v="${1%%.*}"; case "$v" in ''|*[!0-9]*) return;; esac; [ "$v" -gt "$worst" ] && worst="$v"; }
# human-readable token count: 252844 -> 252k, 1000000 -> 1.0M
hum() { local n="${1%%.*}"; case "$n" in ''|*[!0-9]*) n=0;; esac
  if [ "$n" -ge 1000000 ]; then local d=$((n/100000)); printf '%d.%dM' $((d/10)) $((d%10))
  elif [ "$n" -ge 1000 ]; then printf '%dk' $((n/1000))
  else printf '%d' "$n"; fi; }

# ================================================================ L1 =========
# --- session label (ALWAYS; leftmost) + OSC-8 link -------------------------
if   [ -n "$sname" ]; then sess_label="$sname"
elif [ -n "$sid"   ]; then sess_label="sess:${sid:0:8}"
else                       sess_label="unnamed"; fi
sess_out="$sess_label"
lm="${STATUSLINE_SESSION_LINK:-protocol}"
if [ -n "$tpath" ] && [ "$lm" != "none" ]; then
  fwd=${tpath//\\//}; fwd=${fwd//%/%25}; fwd=${fwd// /%20}
  case "$fwd" in [A-Za-z]:/*) abs="/$fwd";; /*) abs="$fwd";; *) abs="/$fwd";; esac
  [ "$lm" = "file" ] && url="file://$abs" || url="claude-session://$abs"
  sess_out=$(printf '\033]8;;%s\a%s\033]8;;\a' "$url" "$sess_label")
fi

# --- auth (DEMOTED: only when account != pinned default) -------------------
defacct="${STATUSLINE_DEFAULT_ACCT:-realprekzursil}"
auth=""; ac="$cdir/claude-auth-line.txt"; email=""; plan=""; cat_ts=0
[ -f "$ac" ] && IFS="$US" read -r email plan cat_ts < "$ac" 2>/dev/null
case "$cat_ts" in ''|*[!0-9]*) cat_ts=0;; esac
if [ -z "$email" ] || [ $(( now - cat_ts )) -gt 3600 ]; then
  fresh=$(claude auth status --json 2>/dev/null | jq -r '[(.email//"?"),(.subscriptionType//"?")]|join("\u001f")' 2>/dev/null)
  [ -n "$fresh" ] || fresh="?${US}?"
  printf '%s%s%s' "$fresh" "$US" "$now" > "$ac.tmp.$$" 2>/dev/null && mv -f "$ac.tmp.$$" "$ac" 2>/dev/null
  IFS="$US" read -r email plan <<< "$fresh"
fi
: "${email:=?}"; : "${plan:=?}"; local_part="${email%%@*}"
[ -n "$local_part" ] && [ "$local_part" != "?" ] && auth="$(san "$local_part") ($(san "$plan"))"   # ALWAYS-on (owner wants auth visible); F4: san plan (cache read)

# --- model (+ /1M denominator when the window is not 200k) ------------------
mlabel="$model"
# Only append the window when the model NAME doesn't already state it (e.g. "Opus 4.8 (1M context)").
case "$model" in
  *1[Mm]*|*ontext*) ;;
  *) if   [ "$ctxsize" = "1000000" ]; then mlabel="$model/1M"
     elif [ -n "$ctxsize" ] && [ "$ctxsize" -gt 200000 ] 2>/dev/null; then mlabel="$model/$((ctxsize/1000))k"; fi ;;
esac

# --- mode-drift (only when NOT the expected default) -----------------------
drift=""
# Flag only DEVIATIONS from expected defaults (env-tunable). exp_sty defaults to "default" (the stock output
# style) so a normal session shows nothing; exp_eff defaults to "max" (the owner's norm) so a drop below max
# shows. STATUSLINE_EXPECT_STYLE / STATUSLINE_EXPECT_EFFORT override; thinking-off is always worth flagging.
exp_eff="${STATUSLINE_EXPECT_EFFORT:-max}"; exp_sty="${STATUSLINE_EXPECT_STYLE:-default}"
[ -n "$effort" ] && [ "$effort" != "$exp_eff" ] && drift="${drift:+$drift,}eff:$effort"
[ -n "$ostyle" ] && [ "$ostyle" != "$exp_sty" ] && drift="${drift:+$drift,}$ostyle"
[ "$thinking" = "false" ] && drift="${drift:+$drift,}nothink"

# --- goal (distilled): prefer goal_short from the harness file; else clean raw ---
goal=""
# Gate behind the goal dir (a box without it pays 0). The token = sha256(session_id)[:20] (matches ledger.py);
# it never changes for a session, so CACHE it per session — the sha256sum spawn happens ONCE, not every render.
gdir="$HOME/.agents/state/harness/session-goals"
if [ -n "$sid" ] && [ -d "$gdir" ]; then
  gtoken=""; gtc="$cdir/claude-goaltok-${sid:0:8}.txt"
  if [ -f "$gtc" ]; then read -r gtoken < "$gtc" 2>/dev/null
  elif command -v sha256sum >/dev/null 2>&1; then
    gtoken=$(printf '%s' "$sid" | sha256sum 2>/dev/null | cut -c1-20)
    [ -n "$gtoken" ] && { printf '%s' "$gtoken" > "$gtc.tmp.$$" 2>/dev/null && mv -f "$gtc.tmp.$$" "$gtc" 2>/dev/null; }
  fi
  gfile="$gdir/${gtoken}.json"
  if [ -n "$gtoken" ] && [ -f "$gfile" ]; then
    # goal_short (future field, set by the TDD'd ledger.py follow-up) wins; else clean the raw goal.
    # ONE jq reads both fields; bash truncates (was: 2 jq + head). sed runs only on the raw-clean path.
    IFS="$US" read -r gshort graw <<< "$(jq -r '[(.goal_short//""),(.goal//"")]|map(gsub("[[:cntrl:]]";""))|join("\u001f")' "$gfile" 2>/dev/null)"
    if [ -n "$gshort" ]; then g="$gshort"
    else g=$(printf '%s' "$graw" | sed -e 's/<[^>]*>//g' -e 's/[[:space:]]\{1,\}/ /g' -e 's/^[[:space:]]*//'); g="${g:0:200}"; fi
    g=$(san "$g")
    if [ -n "$g" ]; then
      gmax="${STATUSLINE_GOAL_MAX:-40}"
      [ "${#g}" -gt "$gmax" ] && g="${g:0:$((gmax-1))}…"
      goal="goal:$g"
    fi
  fi
fi

L1=""; add1() { [ -n "$1" ] && L1="${L1:+$L1$sep}$1"; }
add1 "$sess_out"; add1 "$auth"; add1 "$mlabel"; [ -n "$drift" ] && add1 "${D}${drift}${Z}"; add1 "$goal"

# ================================================================ L2 =========
# --- ctx (always): tokens used/max, used%, and room left before auto-compact ---
wst "$used"; band "$used" 75 88; pct=$(printf '%.0f' "${used:-0}" 2>/dev/null || echo 0)
colorize "$BAND" "ctx:$(hum "$toks")/$(hum "$ctxsize") ${pct}%"; ctxseg="$REPLY"
[ "$exceeds" = "true" ] && [ -z "$BAND" ] && ctxseg="$ctxseg${D}+200k${Z}"
# room left before auto-compact fires (STATUSLINE_COMPACT_PCT = trigger %, default 92); lower = closer
comp="${STATUSLINE_COMPACT_PCT:-92}"; till=$(( comp - pct )); [ "$till" -lt 0 ] && till=0
cband=""; [ "$till" -le 15 ] && cband=amber; [ "$till" -le 8 ] && cband=red
colorize "$cband" "cmpct:${till}%left"; ctxseg="$ctxseg$sep$REPLY"

# --- 5h (ALWAYS when present): %left + time-to-empty countdown, colour by used% -----
rl=""
if [ -n "$five" ]; then
  wst "$five"; band "$five" 80 92; fivelvl="$BAND"; rs=""
  fleft=$(( 100 - $(printf '%.0f' "$five" 2>/dev/null || echo 0) ))
  if [ -n "$five_reset" ]; then
    if [[ "$five_reset" =~ ^[0-9]+$ ]]; then ep="$five_reset"; else ep=$(date -d "$five_reset" +%s 2>/dev/null); fi
    if [ -n "$ep" ]; then d=$(( ep-now )); if [ "$d" -gt 0 ]; then h=$((d/3600)); m=$(((d%3600)/60)); [ "$h" -gt 0 ] && rs="${h}h${m}m" || rs="${m}m"; fi; fi
  fi
  colorize "$fivelvl" "5h:${fleft}%${rs:+ $rs}"; rl="$REPLY"
fi

# --- wk (ALWAYS when present): %left, colour by used% ----------------------
wk=""
if [ -n "$seven" ]; then w="${seven%%.*}"; case "$w" in ''|*[!0-9]*) w=0;; esac
  wst "$seven"; band "$seven" 80 92; colorize "$BAND" "wk:$(( 100 - w ))%"; wk="$REPLY"
fi

# --- ag:N⚠age (subagent fan-out+stall; gated + TTL-cached find) -----------
ag=""
if [ -n "$tpath" ]; then
  sdir="${tpath%.jsonl}/subagents"
  if [ -d "$sdir" ]; then
    # ag:N = subagents that WROTE in the last ~2 min = actively running now. No stall-age: a stalled agent
    # and a long-COMPLETED one are indistinguishable from file mtimes alone (both just stop changing), so an
    # "oldest file age" warning was misleading (it flagged 11h-old finished agents). Reliable stall detection
    # would need orchestrator state we don't have. Just the live count, TTL-cached ~10s, gated on the dir.
    agc="$cdir/claude-ag-${sid:0:8}.txt"; ag_ts=0; agn=""
    [ -f "$agc" ] && IFS="$US" read -r agn ag_ts < "$agc" 2>/dev/null
    case "$ag_ts" in ''|*[!0-9]*) ag_ts=0;; esac
    if [ $(( now - ag_ts )) -ge 10 ]; then
      agn=$(find "$sdir" -maxdepth 1 -name 'agent-*.jsonl' -newermt "@$((now-120))" 2>/dev/null | wc -l | tr -d ' ')
      printf '%s%s%s' "$agn" "$US" "$now" > "$agc.tmp.$$" 2>/dev/null && mv -f "$agc.tmp.$$" "$agc" 2>/dev/null
    fi
    [ -n "$agn" ] && [ "$agn" -gt 0 ] 2>/dev/null && ag="ag:$agn"
  fi
fi

# --- mem:N% commit-pressure (from memguard.json; builtin read, staleness-guarded) ---
mem=""
mj="$HOME/.agents/state/harness/memguard.json"
if [ -f "$mj" ]; then
  IFS="$US" read -r mval mts <<< "$(jq -r '[(.commit_pct//""),(.ts//0)]|join("\u001f")' "$mj" 2>/dev/null)"
  case "$mts" in ''|*[!0-9]*) mts=0;; esac
  case "$mval" in *[!0-9.]*|'') mval="";; esac   # F4: numeric-only — a poisoned non-numeric commit_pct renders nothing
  if [ -n "$mval" ] && [ $(( now - mts )) -lt 120 ]; then wst "$mval"; band "$mval" 75 90; colorize "$BAND" "mem:${mval%%.*}%"; mem="$REPLY"; fi
fi

# --- git (native pr/worktree free + branch/dirty via cached, gated git spawn) ---
git_seg=""
gwt=""; [ -n "$gitwt" ] && gwt="wt:$(san "$gitwt")"
prseg=""
if [ -n "$pr_num" ]; then
  # F1 defense-in-depth: only hyperlink pr_url when it's a clean http(s) scheme (control bytes are already
  # gsub-stripped by the main jq; this additionally blocks a hostile non-http scheme like file://\\UNC or javascript:).
  case "$pr_url" in
    https://*|http://*) prseg=$(printf '\033]8;;%s\a#%s↳\033]8;;\a' "$pr_url" "$pr_num") ;;
    *)                  prseg="#$pr_num" ;;
  esac
fi
bd=""
if [ -n "$cwd" ] && { [ -d "$cwd/.git" ] || [ -f "$cwd/.git" ]; }; then
  gc="$cdir/claude-git-${cwd##*/}-${#cwd}.txt"; g_ts=0; bd=""   # cwd-keyed, pure-bash (was: sha256sum|cut spawn)
  [ -f "$gc" ] && IFS="$US" read -r bd g_ts < "$gc" 2>/dev/null
  case "$g_ts" in ''|*[!0-9]*) g_ts=0;; esac
  if [ $(( now - g_ts )) -ge 8 ]; then
    br=$(git -C "$cwd" symbolic-ref --short -q HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
    dirty=""; [ -n "$(git -C "$cwd" status --porcelain 2>/dev/null | head -1)" ] && dirty="*"
    bd="$(san "$br")$dirty"
    printf '%s%s%s' "$bd" "$US" "$now" > "$gc.tmp.$$" 2>/dev/null && mv -f "$gc.tmp.$$" "$gc" 2>/dev/null
  fi
fi
[ -n "$bd" ] && bd=$(san "$bd")   # F4: re-sanitize cache-read path — guarded so no `tr` spawns when not in a repo
gitparts=""; for p in "$bd" "$prseg" "$gwt"; do [ -n "$p" ] && gitparts="${gitparts:+$gitparts$sep}$p"; done
git_seg="$gitparts"

# --- $cost + session duration (ALWAYS when present; owner wants both visible) -----
costseg="\$$(printf '%.2f' "${cost:-0}" 2>/dev/null || echo 0.00)"
durseg=""; dnum="${dur%%.*}"; case "$dnum" in ''|*[!0-9]*) dnum=0;; esac
if [ "$dnum" -gt 0 ]; then
  ds=$(( dnum/1000 )); dh=$(( ds/3600 )); dm=$(( (ds%3600)/60 ))
  [ "$dh" -gt 0 ] && durseg="${dh}h${dm}m" || durseg="${dm}m"
fi

L2=""; add2() { [ -n "$1" ] && L2="${L2:+$L2$sep}$1"; }
add2 "$ctxseg"; add2 "$costseg"; add2 "$durseg"; add2 "$rl"; add2 "$wk"; add2 "$ag"; add2 "$mem"; add2 "$git_seg"

# ================================================= OSC 9;4 tab-ring =========
# worst-of {ctx%, 5h-used%, mem%} -> WT tab ring + taskbar bar. state 1 normal / 4 warn / 2 error.
tabring=""
if [ "${STATUSLINE_TABRING:-1}" != "0" ]; then
  st=1; [ "$worst" -ge 75 ] 2>/dev/null && st=4; [ "$worst" -ge 90 ] 2>/dev/null && st=2
  tabring=$(printf '\033]9;4;%s;%s\a' "$st" "$worst")
fi

# ================================================= assemble + width ==========
# visible width: strip OSC-8 (ESC]8;;…BEL) and CSI-SGR (ESC[…m), count what's left.
vwidth() { local s="$1"; s=$(printf '%s' "$s" | sed -e 's/\x1b]8;;[^\x07]*\x07//g' -e 's/\x1b\[[0-9;]*m//g'); printf '%s' "${#s}"; }
cols="${COLUMNS:-0}"

out="$tabring$L1"$'\n'"$L2"
# Collapse to ONE priority-ordered line when narrow: keep SESSION+ctx+5h, drop the rest right-to-left.
# PERF: raw ${#L} (bytes, incl. escapes) is an UPPER BOUND on visible width, so only pay the vwidth `sed`
# when a line's raw length already exceeds cols — the common (fits) case does zero sed.
if [ "$cols" -gt 0 ] 2>/dev/null && \
   { { [ "${#L1}" -gt "$cols" ] && [ "$(vwidth "$L1")" -gt "$cols" ]; } || \
     { [ "${#L2}" -gt "$cols" ] && [ "$(vwidth "$L2")" -gt "$cols" ]; }; }; then
  one=""; for s in "$sess_out" "$ctxseg" "$rl" "$wk" "$costseg" "$durseg" "$auth" "$goal" "$ag" "$mem" "$mlabel" "$git_seg"; do
    [ -z "$s" ] && continue
    cand="${one:+$one$sep}$s"
    [ "$(vwidth "$cand")" -le "$cols" ] && one="$cand"
  done
  out="$tabring$one"
fi

printf '%s' "$out"
