#requires -Version 5
<#
  Compatibility entry point only.

  The active Claude registration calls the shared dispatcher directly. This
  wrapper remains so an older sync or cached hook definition cannot revive the
  previous raw conversation capture behavior.
#>
$ErrorActionPreference = 'SilentlyContinue'

try {
    $raw = [Console]::In.ReadToEnd()
    $raw | & python 'C:/Users/Prekzursil/.agents/harness/dispatcher.py' --provider claude --event PreCompact
} catch {
    # Hooks fail open. The shared dispatcher owns operational failure logging.
}

exit 0
