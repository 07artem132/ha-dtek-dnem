$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$t = (Get-Content "$dir\..\ha-token.txt" -Raw).Trim()
$h = @{ Authorization = "Bearer $t"; 'Content-Type' = 'application/json; charset=utf-8' }
function Render($tpl) {
  $body = [Text.Encoding]::UTF8.GetBytes((@{ template = $tpl } | ConvertTo-Json -Compress))
  try { $r = Invoke-WebRequest -UseBasicParsing -Method Post -Headers $h -Body $body "$(if ($env:HA_URL) { $env:HA_URL } else { 'http://homeassistant.local:8123' })/api/template"
        return [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) }
  catch { $s = $_.Exception.Response.GetResponseStream(); return "ERROR: " + (New-Object IO.StreamReader($s)).ReadToEnd() } }
$cases = Get-Content "$dir\cases.json" -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($c in $cases) {
  "===== $($c.name)"; $acc = $c.pre; $vars = @()
  foreach ($s in $c.seq) {
    if ($s[2] -ne $null) { $lit = $s[2] } else {
      $val = (Render ($acc + $s[1])).Trim()
      if ($val -match '^ERROR') { "VAR $($s[0]) $val" }
      $lit = if ($val -match '^[\[\{]' -or $val -match '^-?[\d.]+$') { $val } elseif ($val -in 'True','False') { $val.ToLower() } else { '"' + ($val -replace '"','\"') + '"' } }
    $vars += "$($s[0])=$lit"; $acc += "{% set $($s[0]) = $lit %}" }
  "  vars: " + (($vars | ? { $_ -notmatch '^(evs|dtek|ev)' }) -join '; ')
  Render ($acc + $c.msg) }
