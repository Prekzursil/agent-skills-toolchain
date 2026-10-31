# cc-profiles.psm1 — key-scoped profile merge engine for Claude Code provider switching.
# Touches ONLY manifest-named keys. Never rotates credentials. Token travels as {{ZAI_API_KEY:User}}
# placeholder, resolved live at every apply. Backups + restore-on-exception + semantic diffs only.

$script:ProfilesDir = "$env:USERPROFILE\.claude\profiles"
$script:SettingsPath = "$env:USERPROFILE\.claude\settings.json"
$script:LocalPath = "$env:USERPROFILE\.claude\settings.local.json"
$script:SentinelPath = "$ProfilesDir\state\cc-active-profile"
$script:FailoverScript = "$env:USERPROFILE\.agents\scripts\zai_key_failover.py"
$script:CleanMcpPath = "$ProfilesDir\clean-mcp.json"

function Get-CCSentinel {
    if (Test-Path $script:SentinelPath) {
        $v = (Get-Content $script:SentinelPath -Raw -ErrorAction SilentlyContinue)
        if ($v) { return $v.Trim().ToLower() }
    }
    return "glm"  # fail-open: missing sentinel == glm == today's behavior
}

function Set-CCSentinel([string]$Name) {
    $dir = Split-Path $script:SentinelPath
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    [IO.File]::WriteAllText($script:SentinelPath, $Name, [Text.UTF8Encoding]::new($false))
}

function Resolve-CCToken([string]$Value) {
    # {{ZAI_API_KEY:User}} -> live user-scope env; abort if empty (never bake an empty token)
    if ($Value -eq "{{ZAI_API_KEY:User}}") {
        $tok = [Environment]::GetEnvironmentVariable("ZAI_API_KEY", "User")
        if (-not $tok) { throw "ZAI_API_KEY not set at User scope - cannot resolve GLM token (failover mesh owns it)" }
        return $tok
    }
    return $Value
}

function Mask-Value([string]$V) {
    if (-not $V) { return $V }
    $s = "$V"
    if ($s.Length -gt 12 -and $s -match "^[A-Za-z0-9_\-\.]{12,}$") { return $s.Substring(0, 4) + "...<masked>" }
    return $s
}

function Get-PathValue($Obj, [string]$DotPath) {
    $cur = $Obj
    foreach ($seg in $DotPath.Split(".")) {
        if ($null -eq $cur) { return $null }
        $cur = $cur.PSObject.Properties[$seg]
        if ($cur) { $cur = $cur.Value } else { return $null }
    }
    return $cur
}

function Set-PathValue($Obj, [string]$DotPath, $Value) {
    $segs = $DotPath.Split(".")
    $cur = $Obj
    for ($i = 0; $i -lt $segs.Count - 1; $i++) {
        $p = $cur.PSObject.Properties[$segs[$i]]
        if (-not $p) {
            Add-Member -InputObject $cur -MemberType NoteProperty -Name $segs[$i] -Value (New-Object PSObject)
            $p = $cur.PSObject.Properties[$segs[$i]]
        }
        $cur = $p.Value
    }
    $last = $segs[$segs.Count - 1]
    $p = $cur.PSObject.Properties[$last]
    if ($p) { $p.Value = $Value } else { Add-Member -InputObject $cur -MemberType NoteProperty -Name $last -Value $Value }
}

function Remove-PathValue($Obj, [string]$DotPath) {
    $segs = $DotPath.Split(".")
    $cur = $Obj
    for ($i = 0; $i -lt $segs.Count - 1; $i++) {
        $p = $cur.PSObject.Properties[$segs[$i]]
        if (-not $p) { return }
        $cur = $p.Value
    }
    $cur.PSObject.Properties.Remove($segs[$segs.Count - 1])
}

function ConvertTo-CCJson($Obj) {
    return [IO.File]::WriteAllText; # placeholder never used (kept for clarity)
}

function Save-CCJson($Obj, [string]$Path) {
    $json = ConvertTo-Json -InputObject $Obj -Depth 100
    [IO.File]::WriteAllText($Path, $json, [Text.UTF8Encoding]::new($false))
    # verify parse before returning
    $null = Get-Content $Path -Raw | ConvertFrom-Json
}

function Invoke-CCProfile {
    <#
    .SYNOPSIS  Apply a profile manifest (glm|claude) to the live config, key-scoped, with backup + verify + masked diff.
    #>
    param([Parameter(Mandatory)][ValidateSet("glm", "claude", "unified")][string]$Name)

    $manifestPath = Join-Path $ProfilesDir "$Name.profile.json"
    if (-not (Test-Path $manifestPath)) { throw "manifest missing: $manifestPath" }
    $m = Get-Content $manifestPath -Raw | ConvertFrom-Json

    $settings = Get-Content $script:SettingsPath -Raw | ConvertFrom-Json
    $local = Get-Content $script:LocalPath -Raw | ConvertFrom-Json

    # --- backup (keep 20) ---
    $bdir = Join-Path $ProfilesDir "backups"
    if (-not (Test-Path $bdir)) { New-Item -ItemType Directory -Path $bdir -Force | Out-Null }
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $bs = Join-Path $bdir "settings-$ts.json"
    $bl = Join-Path $bdir "settings.local-$ts.json"
    Copy-Item $script:SettingsPath $bs -Force
    Copy-Item $script:LocalPath $bl -Force
    $old = Get-ChildItem $bdir -Filter "settings-*.json" | Sort-Object Name
    if ($old.Count -gt 20) { $old | Select-Object -First ($old.Count - 20) | Remove-Item -Force }

    $diff = New-Object System.Collections.Generic.List[string]
    try {
        # --- env ops (settings.json env block) ---
        if (-not $settings.PSObject.Properties["env"]) {
            Add-Member -InputObject $settings -MemberType NoteProperty -Name "env" -Value (New-Object PSObject)
        }
        $envObj = $settings.env
        foreach ($k in @($m.env_remove)) {
            $before = $envObj.PSObject.Properties[$k]
            if ($before) {
                $diff.Add(("env.{0}: {1} -> REMOVED" -f $k, (Mask-Value $before.Value)))
                $envObj.PSObject.Properties.Remove($k)
            }
        }
        foreach ($p in $m.env_set.PSObject.Properties) {
            $newVal = Resolve-CCToken $p.Value
            $before = $envObj.PSObject.Properties[$p.Name]
            $diff.Add(("env.{0}: {1} -> {2}" -f $p.Name, ($(if ($before) { Mask-Value $before.Value } else { "<absent>" })), (Mask-Value $newVal)))
            if ($before) { $before.Value = $newVal } else { Add-Member -InputObject $envObj -MemberType NoteProperty -Name $p.Name -Value $newVal }
        }

        # --- top-level ops (settings.json) ---
        foreach ($p in $m.top_set.PSObject.Properties) {
            $before = Get-PathValue $settings $p.Name
            $diff.Add(("{0}: {1} -> {2}" -f $p.Name, ($(if ($null -ne $before) { (Mask-Value (ConvertTo-Json $before -Compress -Depth 6)) } else { "<absent>" })), (Mask-Value (ConvertTo-Json $p.Value -Compress -Depth 6))))
            Set-PathValue $settings $p.Name $p.Value
        }
        foreach ($rp in @($m.top_remove)) {
            $before = Get-PathValue $settings $rp
            if ($null -ne $before) {
                $diff.Add(("{0}: {1} -> REMOVED" -f $rp, (Mask-Value (ConvertTo-Json $before -Compress -Depth 6))))
                Remove-PathValue $settings $rp
            }
        }

        # --- hooks ops (settings.json hooks.<Event> groups) ---
        if (-not $settings.PSObject.Properties["hooks"]) {
            Add-Member -InputObject $settings -MemberType NoteProperty -Name "hooks" -Value (New-Object PSObject)
        }
        foreach ($marker in @($m.hooks_removeMarkers)) {
            foreach ( $evt in $settings.hooks.PSObject.Properties ) {
                $groups = $evt.Value
                if ($groups -isnot [System.Array]) { continue }
                foreach ( $grp in @($groups) ) {
                    if (-not $grp.hooks) { continue }
                    $keep = @()
                    foreach ( $h in @($grp.hooks) ) {
                        if ("$($h.command)" -like "*$marker*") {
                            $diff.Add(("hooks.$($evt.Name): REMOVED entry [ $($h.command) ]"))
                        } else { $keep += $h }
                    }
                    if ($keep.Count -ne @($grp.hooks).Count) {
                        if ($keep.Count -eq 0) { $grp.PSObject.Properties["hooks"].Value = @() }
                        else { $grp.PSObject.Properties["hooks"].Value = $keep }
                    }
                }
            }
        }
        foreach ($add in @($m.hooks_add)) {
            # $add = { matcher: "...", hooks: [ {type,command,timeout,statusMessage} ] }
            $evtName = "StopFailure"
            if ($add.event) { $evtName = $add.event }
            if (-not $settings.hooks.PSObject.Properties[$evtName]) {
                Add-Member -InputObject $settings.hooks -MemberType NoteProperty -Name $evtName -Value @()
            }
            $groups = $settings.hooks.$evtName
            if ($groups -isnot [System.Array]) { $groups = @($groups) }
            $already = $false
            foreach ( $grp in $groups ) {
                foreach ( $h in @($grp.hooks) ) { if ("$($h.command)" -eq "$($add.hooks[0].command)") { $already = $true } }
            }
            if (-not $already) {
                $newGroup = New-Object PSObject
                Add-Member -InputObject $newGroup -MemberType NoteProperty -Name "matcher" -Value $add.matcher
                Add-Member -InputObject $newGroup -MemberType NoteProperty -Name "hooks" -Value @($add.hooks)
                $settings.hooks.$evtName = @($groups) + @($newGroup)
                $diff.Add(("hooks.$($evtName): ADDED group [ matcher $($add.matcher), cmd $($add.hooks[0].command) ]"))
            } else {
                $diff.Add(("hooks.$($evtName): failover entry already present (idempotent skip)"))
            }
        }

        # --- plugins merge (settings.json enabledPlugins) ---
        if (-not $settings.PSObject.Properties["enabledPlugins"]) {
            Add-Member -InputObject $settings -MemberType NoteProperty -Name "enabledPlugins" -Value (New-Object PSObject)
        }
        foreach ( $p in $m.plugins_merge.PSObject.Properties ) {
            $before = $settings.enabledPlugins.PSObject.Properties[$p.Name]
            $diff.Add(("enabledPlugins.{0}: {1} -> {2}" -f $p.Name, ($(if ($before) { $before.Value } else { "<absent>" })), $p.Value))
            if ($before) { $before.Value = $p.Value } else { Add-Member -InputObject $settings.enabledPlugins -MemberType NoteProperty -Name $p.Name -Value ([bool]$p.Value) }
        }

        # --- skills hide/restore (rename-based, zero deletion; forensics: offensive-named skills ride the system-prompt catalog) ---
        $skillsDir = "$env:USERPROFILE\.claude\skills"
        $hideList = @($m.skills_hide)
        foreach ( $pat in $hideList ) {
            if (-not $pat) { continue }
            Get-ChildItem $skillsDir -Directory -Filter $pat -ErrorAction SilentlyContinue | ForEach-Object {
                $off = $_.FullName + ".cc-off"
                if (-not (Test-Path $off)) {
                    Move-Item -LiteralPath $_.FullName -Destination $off
                    $diff.Add(("skills: hidden " + $_.Name + " (claude profile)"))
                }
            }
        }
        if ($hideList.Count -eq 0) {
            # applying a show-everything profile (glm/unified): restore any hidden skills
            Get-ChildItem $skillsDir -Directory -Filter "*.cc-off" -ErrorAction SilentlyContinue | ForEach-Object {
                $back = $_.FullName -replace "\.cc-off$", ""
                if (-not (Test-Path $back)) {
                    Move-Item -LiteralPath $_.FullName -Destination $back
                    $diff.Add(("skills: restored " + $_.Name))
                }
            }
        }

        # --- settings.local.json ops ---
        foreach ( $p in $m.local_set.PSObject.Properties ) {
            $before = Get-PathValue $local $p.Name
            $diff.Add(("local.{0}: {1} -> {2}" -f $p.Name, ($(if ($null -ne $before) { (Mask-Value (ConvertTo-Json $before -Compress -Depth 6)) } else { "<absent>" })), (Mask-Value (ConvertTo-Json $p.Value -Compress -Depth 6))))
            Set-PathValue $local $p.Name $p.Value
        }

        # --- atomic-ish pair write: settings first, then local; any throw restores both ---
        Save-CCJson $settings $script:SettingsPath
        Save-CCJson $local $script:LocalPath
    } catch {
        Write-Warning "APPLY FAILED: $($_.Exception.Message) - restoring both files from backup"
        Copy-Item $bs $script:SettingsPath -Force
        Copy-Item $bl $script:LocalPath -Force
        throw
    }

    Set-CCSentinel $Name
    Write-Host "=== cc-use $Name applied ===" -ForegroundColor Green
    foreach ( $d in $diff ) { Write-Host ("  " + $d) }
    Write-Host ("backups: {0} + {1}" -f $bs, $bl)
    Write-Host ("sentinel: {0} = {1}" -f $script:SentinelPath, (Get-CCSentinel))
    if ($Name -eq "claude") {
        Write-Host "next: launch plain 'claude' and run /login once (subscription OAuth). cc-cc for guaranteed-clean launches." -ForegroundColor Yellow
    }
}

function Get-CCStatus {
    $s = Get-Content $script:SettingsPath -Raw | ConvertFrom-Json
    $sentinel = Get-CCSentinel
    $glmSig = $false
    if ($s.env -and $s.env.ANTHROPIC_BASE_URL -and "$($s.env.ANTHROPIC_BASE_URL)" -match "z\.ai") { $glmSig = $true }
    if ($s.env -and $s.env.ANTHROPIC_AUTH_TOKEN) { $glmSig = $true }

    Write-Host ("sentinel      : {0}" -f $sentinel)
    Write-Host ("settings model: {0}" -f $s.model)
    Write-Host ("glm signature : {0}" -f $(if ($glmSig) { "PRESENT (env points at z.ai / token set)" } else { "absent" }))
    if ($sentinel -eq "glm" -and -not $glmSig) { Write-Host "DRIFT: sentinel=glm but config lost the GLM signature -> run: cc-use glm" -ForegroundColor Red }
    if ($sentinel -eq "claude" -and $glmSig) { Write-Host "DRIFT: sentinel=claude but config has GLM signature (chelper stomp?) -> run: cc-use claude" -ForegroundColor Red }

    $guard = Select-String -Path $script:FailoverScript -Pattern "SKIP:cc-guard" -SimpleMatch -ErrorAction SilentlyContinue
    Write-Host ("failover guard: {0}" -f $(if ($guard) { "present" } else { "MISSING (re-apply the guard patch)" }))
    $zai = [Environment]::GetEnvironmentVariable("ZAI_API_KEY", "User")
    Write-Host ("ZAI_API_KEY   : {0}" -f $(if ($zai) { "set (len $($zai.Length))" } else { "MISSING - failover mesh needs it" }))
    $shadow = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
    if ($shadow) { Write-Host "SHADOW KEY    : ANTHROPIC_API_KEY reappeared at User scope - deletes OAuth precedence (re-delete or investigate the writer)" -ForegroundColor Red }
    else { Write-Host "shadow key    : absent (good)" }
    $vendor = Join-Path $ProfilesDir "vendor\zai-coding-plugins"
    Write-Host ("vendor re-home: {0}" -f $(if (Test-Path $vendor) { "ok" } else { "MISSING" }))
    if (Test-Path $script:CleanMcpPath) {
        $cm = Get-Content $script:CleanMcpPath -Raw | ConvertFrom-Json -AsHashtable
        $live = Get-Content "$env:USERPROFILE\.claude.json" -Raw | ConvertFrom-Json -AsHashtable
        $excluded = @("McpHub","zai-mcp-server","breach-intel","chroot-virtualizor","zai-lane-a","web-search-prime",
            "binary-ninja-mcp","ghidra-mcp","ida-pro-mcp","frida-mcp","cheatengine","hexstrike-ai","angr",
            "metasploit","sliver","sliver-full","nuclei","burp","cve-mcp","cve","osint","github-security",
            "cloud-audit","mitmproxy","semgrep","hacktricks")
        $disabled = @()
        if ($live.disabledMcpServers) { $disabled = @($live.disabledMcpServers) }
        $expected = @($live.mcpServers.Keys | Where-Object { $excluded -notcontains $_ -and $disabled -notcontains $_ })
        $deliberate = @("McpHub")  # lazy-loading multiplexer, curated offensive-free (config.json .bak-sota)
        $expectSet = @($expected + $deliberate | Select-Object -Unique)
        $nClean = $cm.mcpServers.Keys.Count
        $missing = @($expectSet | Where-Object { $cm.mcpServers.Keys -notcontains $_ })
        $extra = @($cm.mcpServers.Keys | Where-Object { $expectSet -notcontains $_ })
        if ($nClean -ne $expectSet.Count -or $missing.Count -gt 0 -or $extra.Count -gt 0) {
            Write-Host ("clean-mcp     : STALE (clean={0} vs expected={1}{2}{3}) - regenerate" -f $nClean, $expectSet.Count, $(if ($missing.Count) { ", missing: " + ($missing -join ",") } else { "" }), $(if ($extra.Count) { ", extra: " + ($extra -join ",") } else { "" })) -ForegroundColor Yellow
        } else { Write-Host ("clean-mcp     : ok ({0} servers)" -f $nClean) }
    }
}
Export-ModuleMember -Function Invoke-CCProfile, Get-CCStatus, Get-CCSentinel, Set-CCSentinel, Resolve-CCToken
