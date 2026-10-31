#!/bin/bash
# cs-lib.sh -- the BASH half of the Claude Science config seam (cs-lib.ps1 is the PowerShell half).
#
# WHY THIS EXISTS: before it, the seam was PowerShell-only. cs-lib.ps1 had held $CSDistro/$CSUrl/
# $CSSlowMs since the 2026-07-07 hardening, but every .sh script re-hardcoded the port and the
# backup root independently, so changing either meant editing five shell scripts and hoping.
#
# Usage, from any cs-*.sh:
#     . "$(dirname "${BASH_SOURCE[0]}")/cs-lib.sh"
# then use $CS_PORT / $CS_HOST / $CS_URL / $CS_BACKUP_ROOT / $CS_BACKUP_KEY_ROOT / $CS_DISTRO.
#
# PRECEDENCE matches cs-lib.ps1 exactly: environment > cs.conf > the defaults below. That is why
# this does NOT `source cs.conf` -- a plain source would let the file CLOBBER an env override.
# Values already present in the environment are left alone.
#
# LINE ENDINGS: .gitattributes pins `*.sh text eol=lf`. Real WSL/Linux bash rejects CRLF
# (`then\r` parses as a command), and the \r strip below is belt-and-braces for a file that
# somehow reaches a shell with CRLF anyway.

_cs_conf="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cs.conf"
if [ -r "$_cs_conf" ]; then
  while IFS= read -r _cs_line || [ -n "$_cs_line" ]; do
    _cs_line="${_cs_line%$'\r'}"
    case "$_cs_line" in ''|'#'*) continue ;; esac
    case "$_cs_line" in *'='*) ;; *) continue ;; esac
    _cs_k="${_cs_line%%=*}"
    _cs_v="${_cs_line#*=}"
    # env wins: only adopt the file value when the variable is unset or empty.
    if [ -z "${!_cs_k:-}" ]; then export "$_cs_k=$_cs_v"; fi
  done < "$_cs_conf"
fi
unset _cs_conf _cs_line _cs_k _cs_v

# Hard defaults -- identical to cs-lib.ps1's, so a missing/unreadable cs.conf degrades to exactly
# the values these scripts shipped with rather than to empty strings.
: "${CS_HOST:=127.0.0.1}"
: "${CS_PORT:=8000}"
: "${CS_DISTRO:=Ubuntu}"
: "${CS_SLOW_MS:=4000}"
: "${CS_HARD_CAP_MS:=8000}"
: "${CS_BACKUP_ROOT:=/mnt/d/Backups/claude-science}"
: "${CS_BACKUP_KEY_ROOT:=/mnt/d/Backups/claude-science-keys}"
: "${CS_MIN_WSL_DISK_GB:=10}"
: "${CS_MIN_HOST_RAM_GB:=3}"
export CS_HOST CS_PORT CS_DISTRO CS_SLOW_MS CS_HARD_CAP_MS
export CS_BACKUP_ROOT CS_BACKUP_KEY_ROOT CS_MIN_WSL_DISK_GB CS_MIN_HOST_RAM_GB

CS_URL="http://${CS_HOST}:${CS_PORT}/"
export CS_URL

cs_data_dir() { printf '%s' "${CS_DATA_DIR:-$HOME/.claude-science}"; }

cs_find_db() {
  # The operon DB to operate on, chosen DETERMINISTICALLY.
  #
  # BUG THIS FIXES: cs-backup.sh, cs-maintain.sh and cs-doctor.ps1 each did
  #   find "$DD/orgs" -name operon-cli.db | head -1
  # and there are TWO org directories on this box. `find` order is filesystem order, not a
  # guarantee, so the backup could snapshot one org's DB while the doctor pronounced the OTHER
  # one healthy -- both rows green, the wrong file backed up. Newest-mtime wins is a defined,
  # reproducible rule; ties break on path so the answer is stable.
  local dd
  dd="$(cs_data_dir)"
  find "$dd/orgs" -name operon-cli.db -printf '%T@\t%p\n' 2>/dev/null \
    | sort -k1,1nr -k2,2 | head -1 | cut -f2-
}
