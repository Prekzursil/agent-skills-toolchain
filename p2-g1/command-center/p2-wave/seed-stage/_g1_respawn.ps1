# Windows-side respawn loop for a resumable WSL wave (coordinator 02.09).
# Re-launches the WSL command until its output contains the done marker.
# Usage: powershell -File _g1_respawn.ps1 -IdsWsl /mnt/c/.../ids.txt -Wave wave-name [-Workers 6] [-NoRegen] [-LogPath C:\...\log]
param(
    [Parameter(Mandatory = $true)][string]$IdsWsl,
    [Parameter(Mandatory = $true)][string]$Wave,
    [int]$Workers = 6,
    [switch]$NoRegen,
    [string]$LogPath = "C:\Users\Prekzursil\source\ast-integrate\command-center\p2-wave\ovh-monitor\repair-claude\$Wave.respawn.log",
    [int]$MaxRounds = 200
)
$extra = ""
if ($NoRegen) { $extra = " --no-regen" }
$cmd = "export AST_INTEGRATE_ROOT=`$HOME/p2-g1; export G1_WORKERS=$Workers; cd `$HOME/p2-g1; python3 -u /mnt/c/Users/Prekzursil/source/ast-integrate/command-center/p2-wave/seed-stage/_g1_regen_par.py $IdsWsl $Wave$extra"
for ($round = 1; $round -le $MaxRounds; $round++) {
    Add-Content -Path $LogPath -Value "=== round $round $(Get-Date -Format o) ==="
    $out = & wsl.exe bash -lc $cmd 2>&1
    $out | Add-Content -Path $LogPath
    if (($out | Out-String) -match "DONE $Wave ") {
        Add-Content -Path $LogPath -Value "=== FINISHED $(Get-Date -Format o) ==="
        break
    }
    Start-Sleep -Seconds 20
}
