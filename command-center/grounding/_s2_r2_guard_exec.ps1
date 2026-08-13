# ROUND 2 / R6: EXECUTABLE both-states proof that the dead_button_crawl main-guard
# is a silent no-op, and that the repair makes it fire.
#
# The defect class (skills/ui-audit/_fix_main_guard.py): the guard compares
# resolve(process.argv[1]) with resolve(__filename).  resolve() is purely lexical,
# so an invocation through a JUNCTION -- which is exactly how the skill is
# documented to be run, `~/.claude/skills` being a junction to `skills.daily` --
# gives argv[1] the link path and import.meta.url the real path.  They never
# match, main() never runs, and the process exits 0 having produced nothing.
#
# PREMISE, measured first by _s2_r2_guardvals.mjs, not assumed:
#   canonical long path -> LEXICAL match true   (guard runs)
#   8.3 short path      -> LEXICAL match TRUE   (Node keeps the short form on BOTH
#                          sides, so this does NOT break the guard -- an earlier
#                          version of this probe assumed it did and reported a
#                          false "GUARD IS FIXED" while the guard was broken)
#   junction path       -> LEXICAL match false  (guard silently skips)  <== the mechanism
#
# Control design: the SAME command runs twice against the SAME inode, once via the
# canonical path and once via the junction.  The canonical leg is the discriminating
# control: if it were also silent the probe itself would be broken, and the script
# says so instead of reporting a verdict.
param([string]$Label = "state")

$ErrorActionPreference = "Continue"
$real = "C:\Users\Prekzursil\source\ast-integrate\skills\ui-audit"
$link = "C:\Users\Prekzursil\AppData\Local\Temp\s2_uiaudit_link"

if (Test-Path $link) { cmd /c rmdir "$link" | Out-Null }
cmd /c mklink /J "$link" "$real" | Out-Null

function Probe([string]$dir, [string]$tag) {
    # --url is deliberately unreachable: we only care whether ANY bytes come out,
    # i.e. whether main() was entered at all, not whether the crawl succeeds.
    $out = & node (Join-Path $dir "dead_button_crawl.mjs") `
        --url "http://127.0.0.1:9/__guard_probe__" --screen g 2>&1 | Out-String
    $code = $LASTEXITCODE
    $n = ($out -replace '\s', '').Length
    $verdict = if ($n -eq 0) { "SILENT  <= main() did NOT run" } else { "RAN     <= main() executed" }
    return [pscustomobject]@{
        Line = ("{0,-10} {1,-8} exit={2,-4} output_chars={3,-6} {4}" -f $tag, $Label, $code, $n, $verdict)
        N    = $n
    }
}

Write-Output "=== dead_button_crawl main-guard, state: $Label ==="
$rReal = Probe $real "CANONICAL"
$rLink = Probe $link "JUNCTION"
Write-Output $rReal.Line
Write-Output $rLink.Line
$nReal = $rReal.N
$nLink = $rLink.N
Write-Output ""
Write-Output "canonical produced output : $($nReal -gt 0)"
Write-Output "junction  produced output : $($nLink -gt 0)"
if ($nReal -le 0) {
    Write-Output "VERDICT[$Label]: INCONCLUSIVE -- even the canonical path was silent; the probe is broken"
} elseif ($nLink -eq 0) {
    Write-Output "VERDICT[$Label]: GUARD IS BROKEN -- same file, junction spelling silently no-ops"
} else {
    Write-Output "VERDICT[$Label]: GUARD IS FIXED -- both spellings enter main()"
}
cmd /c rmdir "$link" | Out-Null
Write-Output "junction removed: $(-not (Test-Path $link))"
