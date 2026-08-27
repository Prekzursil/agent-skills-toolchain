# G-93: generate skills-index.md (name + first sentence of description) in one pass.
$ErrorActionPreference = 'Stop'
$src = 'C:\Users\Prekzursil\.agents\skills'
$out = 'C:\Users\Prekzursil\.agents\skills-index.md'
$em  = [string][char]0x2014

# Backup-first if an index already exists.
if (Test-Path $out) { Copy-Item $out ($out + '.bak') -Force }

$alldirs = Get-ChildItem -LiteralPath $src -Directory | Sort-Object Name
# Only folders that actually contain a SKILL.md count as skills (skips caches like .ruff_cache).
$dirs = @($alldirs | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'SKILL.md') })
$lines = foreach ($d in $dirs) {
    $sk = Join-Path $d.FullName 'SKILL.md'
    $desc = ''
    if (Test-Path -LiteralPath $sk) {
        $head = @(Get-Content -LiteralPath $sk -TotalCount 12)
        for ($i = 0; $i -lt $head.Count; $i++) {
            if ($head[$i] -match '^description:\s*(.*)$') {
                $val = $Matches[1].Trim()
                # YAML block scalar (>, >-, |): take the next non-empty line.
                if ($val -eq '' -or $val -match '^[>|][+-]?$') {
                    for ($j = $i + 1; $j -lt $head.Count; $j++) {
                        if ($head[$j].Trim() -ne '') { $val = $head[$j].Trim(); break }
                    }
                }
                $desc = $val.Trim(' "''')
                break
            }
        }
    }
    if ($desc -match '^(.*?[.!?])(\s|$)') { $desc = $Matches[1] }
    if ($desc -eq '') { $desc = '(no description)' }
    "- **$($d.Name)** $em $desc"
}

$header = @(
    '# Skills vault name index (G-93)',
    '',
    ('Generated 27.08.2026 from C:\Users\Prekzursil\.agents\skills\ ' + $em + ' one line per skill, no bodies.'),
    'Purpose: name index for runtimes that do not lazy-load the vault.',
    'Regenerate after vault changes: powershell -NoProfile -File C:\Users\Prekzursil\.agents\scripts\gen_skills_index.ps1',
    ''
)
$header + $lines | Set-Content -LiteralPath $out -Encoding UTF8

'total_dirs: ' + $alldirs.Count
'skill_folders_with_SKILL_md: ' + $dirs.Count
'index_entry_lines: ' + $lines.Count
'total_file_lines: ' + (Get-Content -LiteralPath $out | Measure-Object).Count
