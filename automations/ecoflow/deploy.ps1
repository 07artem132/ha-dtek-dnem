# Деплой автоматизацій у HA через REST (/api/config/automation/config/<id>) + reload.
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ha = if ($env:HA_URL) { $env:HA_URL } else { 'http://homeassistant.local:8123' }
$t = (Get-Content "$dir\ha-token.txt" -Raw).Trim()
$h = @{ Authorization = "Bearer $t"; 'Content-Type' = 'application/json; charset=utf-8' }
$items = Get-Content "$dir\automations.json" -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($a in $items) {
  $body = [Text.Encoding]::UTF8.GetBytes(($a | ConvertTo-Json -Depth 50 -Compress))
  try { $r = Invoke-WebRequest -UseBasicParsing -Method Post -Headers $h -Body $body "$ha/api/config/automation/config/$($a.id)"
        "OK   $($a.id): $([Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()))" }
  catch { $s = $_.Exception.Response.GetResponseStream(); "FAIL $($a.id): " + (New-Object IO.StreamReader($s)).ReadToEnd() }
}
