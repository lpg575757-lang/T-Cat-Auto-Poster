$ErrorActionPreference = 'Stop'

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$chrome = $chromeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $chrome) { throw 'Google Chrome was not found.' }

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$profile = Join-Path $root ('.browser-profile\sandbox-' + [guid]::NewGuid().ToString('N'))
$runtime = Join-Path $root '.runtime'
New-Item -ItemType Directory -Force -Path $profile, $runtime | Out-Null
$port = 9333

$arguments = @(
    "--remote-debugging-address=127.0.0.1",
    "--remote-debugging-port=$port",
    "--user-data-dir=$profile",
    '--no-first-run',
    '--no-default-browser-check',
    'https://developers.tiktok.com/'
)
Start-Process -FilePath $chrome -ArgumentList $arguments

$metadata = [ordered]@{ endpoint = "http://127.0.0.1:$port"; profile = $profile }
$metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtime 'cdp.json') -Encoding UTF8
Write-Output "CDP_ENDPOINT=$($metadata.endpoint)"
Write-Output "DedicatedProfile=$profile"
