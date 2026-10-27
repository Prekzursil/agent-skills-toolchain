$WorktreeNameMaxChars = 48
function Convert-WorktreeName([string]$raw) {
    $name = ($raw -replace "[^A-Za-z0-9._-]", "-")
    if ($name.Length -gt $WorktreeNameMaxChars) {
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $hashHex = ([BitConverter]::ToString($sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($name)))).Replace("-", "").ToLowerInvariant()
        $name = $name.Substring(0, $WorktreeNameMaxChars - 13) + "-" + $hashHex.Substring(0, 12)
    }
    return $name
}
$long1 = "x" * 4096
$long2 = "y" * 4096
$long3 = "x" * 4095 + "z"
$a = Convert-WorktreeName $long1
$b = Convert-WorktreeName $long1
$c = Convert-WorktreeName $long2
$d = Convert-WorktreeName $long3
$e = Convert-WorktreeName "short-name"
$all = @(); for ($i=0; $i -lt 500; $i++) { $all += Convert-WorktreeName (([guid]::NewGuid().ToString() * 20) + $i) }
$over = ($all | Where-Object { $_.Length -gt 48 }).Count
$uniq = ($all | Sort-Object -Unique).Count
[pscustomobject]@{
    long1_len = $a.Length
    deterministic = ($a -eq $b)
    distinct_longs_distinct = (($a -ne $c) -and ($a -ne $d) -and ($c -ne $d))
    short_untouched = ($e -eq "short-name")
    random500_over_cap = $over
    random500_unique = $uniq
} | ConvertTo-Json -Compress
