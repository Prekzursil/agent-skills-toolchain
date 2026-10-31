# Independent cross-check (PowerShell hashing lane) of the manifest-vs-live
# sha256 identity for BLD-0014, BLD-0013, BLD-0004, BLD-0005.
$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\Prekzursil\p2-g1'
$sha = [System.Security.Cryptography.SHA256]::Create()
foreach ($uid in 'BLD-0014','BLD-0013','BLD-0004','BLD-0005') {
    $p = "C:\Users\Prekzursil\p2-g1\command-center\receipts\$uid.json"
    $rel = "command-center/receipts/$uid.json"
    $raw = [System.IO.File]::ReadAllBytes($p)
    $txt = [System.Text.Encoding]::UTF8.GetString($raw)
    $lfTxt = $txt.Replace("`r`n", "`n")
    $lfBytes = [System.Text.Encoding]::UTF8.GetBytes($lfTxt)
    $shaLF = ([System.BitConverter]::ToString($sha.ComputeHash($lfBytes))).Replace('-','').ToLower()
    $man = Get-Content "C:\Users\Prekzursil\p2-g1\command-center\p2-wave\probes\$uid\UNIT-ARTIFACT-MANIFEST.json" -Raw | ConvertFrom-Json
    $row = $man.artifacts | Where-Object { $_.path -eq $rel }
    $match = ($shaLF -eq $row.sha256)
    Write-Output ("$uid live_bytes=" + $raw.Length + " norm_bytes=" + $lfBytes.Length +
        " manifest_bytes=" + $row.bytes + " eol=" + $row.eol +
        " SHA_MATCH_NORM=" + $match +
        " manifest_sha=" + $row.sha256.Substring(0,16) + " live_norm=" + $shaLF.Substring(0,16))
}
