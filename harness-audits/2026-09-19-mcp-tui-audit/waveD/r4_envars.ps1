# R4: OS-env presence of the referenced variables - names/lengths only, NEVER values
foreach ($n in 'CODACY_ACCOUNT_TOKEN','CODACY_API_TOKEN','CODECOV_TOKEN','CODECOV_BASE_URL','DIGITALOCEAN_API_TOKEN') {
  $p = [Environment]::GetEnvironmentVariable($n, 'Process')
  $u = [Environment]::GetEnvironmentVariable($n, 'User')
  $m = [Environment]::GetEnvironmentVariable($n, 'Machine')
  $fmt = { param($v) if ($null -ne $v) { "len$($v.Length)" } else { "absent" } }
  "{0}: Process={1} User={2} Machine={3}" -f $n, (& $fmt $p), (& $fmt $u), (& $fmt $m)
}
