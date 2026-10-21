try {
    [System.Web.HttpUtility]::UrlEncode('x') | Out-Null
    Write-Output 'HttpUtility: OK in fresh pwsh without Add-Type'
} catch {
    Write-Output ('HttpUtility: FAIL in fresh session: ' + $_.Exception.Message)
}
