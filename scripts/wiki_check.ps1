<#
  wiki_check.ps1 - one-shot connectivity check (run this FIRST)

  Tries two ways to reach the wiki list page and tells you which one works:
    1) Windows integrated session  (no cookie at all)
    2) cookie from scripts\wiki_auth.txt (if present)

  Then you know how to run wiki_fetch.ps1:
    - Windows auth works   ->  wiki_fetch.ps1 -WindowsAuth
    - cookie needed        ->  put auth in wiki_auth.txt, run wiki_fetch.ps1
#>

[CmdletBinding()]
param(
    [string]$Url = 'https://wiki.hanwhawm.com/collector/pages.action?key=BM001',
    [switch]$SkipCertCheck
)

$ErrorActionPreference = 'Continue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
if ($SkipCertCheck) {
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
}

$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }

function Show-Result([string]$label, $resp, $err) {
    Write-Host "----- $label -----"
    if ($err) { Write-Host "  error : $err"; return $false }
    $final = ''
    try { $final = $resp.BaseResponse.ResponseUri.AbsoluteUri } catch { }
    $hasRoot = ($resp.Content -match 'rootPageId')
    Write-Host ("  status : {0}" -f $resp.StatusCode)
    Write-Host ("  final  : {0}" -f $final)
    Write-Host ("  length : {0}" -f $resp.Content.Length)
    Write-Host ("  rootId : {0}" -f $hasRoot)
    return ($hasRoot -and -not $final.ToLower().Contains('login.action'))
}

# 1) Windows integrated session (no cookie)
Write-Host '[1] trying Windows integrated session (no cookie)...'
$ok1 = $false
try {
    $r = Invoke-WebRequest -Uri $Url -UseDefaultCredentials -UseBasicParsing -TimeoutSec 30
    $ok1 = Show-Result 'windows-auth' $r $null
} catch {
    Show-Result 'windows-auth' $null $_.Exception.Message | Out-Null
}

# 2) cookie file (if present)
$ok2 = $false
$authFile = Join-Path $scriptDir 'wiki_auth.txt'
if (Test-Path $authFile) {
    Write-Host ''
    Write-Host "[2] trying cookie from $authFile ..."
    $raw = Get-Content -Path $authFile -Raw -Encoding UTF8
    # same extraction as wiki_fetch.ps1
    $cookie = ''
    $m = [regex]::Match($raw, "(?is)-H\s+['""]cookie:\s*(.+?)['""]")
    if ($m.Success) { $cookie = $m.Groups[1].Value.Trim() }
    if (-not $cookie) { $m = [regex]::Match($raw, "(?is)(?:-b|--cookie)\s+['""](.+?)['""]"); if ($m.Success) { $cookie = $m.Groups[1].Value.Trim() } }
    if (-not $cookie) { $m = [regex]::Match($raw, "(?im)^\s*cookie:\s*(.+)$"); if ($m.Success) { $cookie = $m.Groups[1].Value.Trim() } }
    if (-not $cookie) { $cookie = ($raw -replace "[\r\n]+", ' ').Trim() }
    Write-Host ("  (cookie extracted: {0} chars)" -f $cookie.Length)
    try {
        $r = Invoke-WebRequest -Uri $Url -Headers @{ Cookie = $cookie } -UseBasicParsing -TimeoutSec 30
        $ok2 = Show-Result 'cookie' $r $null
    } catch {
        Show-Result 'cookie' $null $_.Exception.Message | Out-Null
    }
} else {
    Write-Host ''
    Write-Host "[2] no $authFile -> skipping cookie test"
}

Write-Host ''
Write-Host '============================================================'
if ($ok1) {
    Write-Host ' RESULT: Windows auth WORKS. Run:'
    Write-Host '   powershell -ExecutionPolicy Bypass -File scripts\wiki_fetch.ps1 -WindowsAuth'
} elseif ($ok2) {
    Write-Host ' RESULT: cookie WORKS. Run:'
    Write-Host '   powershell -ExecutionPolicy Bypass -File scripts\wiki_fetch.ps1'
} else {
    Write-Host ' RESULT: neither worked.'
    Write-Host '  - if final URL shows login.action: auth not accepted'
    Write-Host '  - put a fresh cookie (or Copy-as-cURL) into scripts\wiki_auth.txt and retry'
}
Write-Host '============================================================'
