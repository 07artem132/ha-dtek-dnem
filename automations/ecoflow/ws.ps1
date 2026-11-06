# Виконує список WebSocket-команд HA з ws-cmds.json (масив об'єктів без id) і друкує результати.
param([string]$CmdFile = "ws-cmds.json")
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$t = (Get-Content "$dir\ha-token.txt" -Raw).Trim()
$cmds = Get-Content "$dir\$CmdFile" -Raw -Encoding UTF8 | ConvertFrom-Json
$ws = New-Object System.Net.WebSockets.ClientWebSocket
$ct = [Threading.CancellationToken]::None
$ws.ConnectAsync([Uri](($(if ($env:HA_URL) { $env:HA_URL } else { 'http://homeassistant.local:8123' })) -replace '^http', 'ws') + '/api/websocket', $ct).Wait()
function Recv { $buf = New-Object byte[] 65536; $ms = New-Object IO.MemoryStream
  do { $seg = New-Object ArraySegment[byte] -ArgumentList (,$buf); $r = $ws.ReceiveAsync($seg, $ct).Result; $ms.Write($buf, 0, $r.Count) } while (-not $r.EndOfMessage)
  [Text.Encoding]::UTF8.GetString($ms.ToArray()) }
function Send($s) { $b = [Text.Encoding]::UTF8.GetBytes($s); $ws.SendAsync((New-Object ArraySegment[byte] -ArgumentList (,$b)), 'Text', $true, $ct).Wait() }
Recv | Out-Null
Send (@{ type = 'auth'; access_token = $t } | ConvertTo-Json -Compress); (Recv) -replace '"ha_version".*', ''
$i = 1
foreach ($c in $cmds) { $c | Add-Member -NotePropertyName id -NotePropertyValue $i -Force; Send ($c | ConvertTo-Json -Depth 20 -Compress); "[$i] " + (Recv); $i++ }
$ws.Dispose()
