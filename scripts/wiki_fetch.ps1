<#
  wiki_fetch.ps1 - Internal wiki HTTP batch fetcher (Windows built-in, no Python/pip)

  PURPOSE
    Runs on a closed-network PC that has NO Python and NO pip.
    Uses the built-in Windows HTTP client (Invoke-WebRequest) to issue batch
    GET requests to internal wiki URLs with an auth header, and saves each page
    body as an .html file. The output folder is consumed as-is by:
        python scripts/sync_manual.py --source dir --path <OUT_DIR>
    (run on any machine that has Python + the project).

  FLOW
    1. read config (KEY=VALUE) + auth header value (param / file / prompt)
    2. resolve root page id from the space list page (or config)
    3. collect page ids:
         full  : BFS over the page-tree children endpoint
         -Incremental : ids found on the "recently updated" page only
    4. GET each page body, detect auth-expiry redirect, save page_<id>.html
    5. print a summary

  USAGE
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wiki_fetch.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\wiki_fetch.ps1 -Incremental

  AUTH HEADER VALUE (kept out of config; pick one)
    - pass -AuthValue "<header value>"
    - put it in scripts\wiki_auth.txt (gitignored)
    - or just run and paste it when prompted
#>

[CmdletBinding()]
param(
    # NOTE: do NOT default this to "$PSScriptRoot\..." — $PSScriptRoot is not
    # reliably populated during param binding in Windows PowerShell 5.1, which
    # made the config path resolve to "\wiki_fetch.config.txt" (drive root).
    # Resolved in the body instead, after $scriptDir is determined.
    [string]$ConfigPath = '',
    [string]$AuthValue,
    [switch]$Incremental,
    [switch]$SkipCertCheck
)

$ErrorActionPreference = 'Stop'

# --- resolve the script's own folder robustly (PSScriptRoot can be empty
#     depending on how the script was launched) ---
$scriptDir = $PSScriptRoot
if (-not $scriptDir) { $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
if (-not $ConfigPath) { $ConfigPath = Join-Path $scriptDir 'wiki_fetch.config.txt' }

# --- TLS 1.2 (older Windows PowerShell defaults to TLS 1.0 -> handshake fail) ---
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- optional: bypass cert validation (corporate CA is usually already trusted,
#     so this should NOT be needed; opt-in only) ---
if ($SkipCertCheck) {
    Write-Host '[warn] certificate validation disabled (-SkipCertCheck)'
    [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
}

# ---------- config ----------

function Read-ConfigFile([string]$path) {
    $cfg = @{}
    if (-not (Test-Path $path)) {
        # config is optional — built-in defaults below cover BM001
        Write-Host "[warn] config file not found: $path (using built-in defaults)"
        return $cfg
    }
    foreach ($line in Get-Content -Path $path -Encoding UTF8) {
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        $i = $t.IndexOf('=')
        if ($i -lt 1) { continue }
        $key = $t.Substring(0, $i).Trim()
        $val = $t.Substring($i + 1).Trim()
        $cfg[$key] = $val
    }
    return $cfg
}

function Get-Cfg($cfg, [string]$key, $default) {
    if ($cfg.ContainsKey($key) -and $cfg[$key] -ne '') { return $cfg[$key] }
    return $default
}

$cfg = Read-ConfigFile $ConfigPath

# built-in defaults cover BM001 so the script works even with no config file
$baseUrl   = (Get-Cfg $cfg 'BASE_URL'   'https://wiki.hanwhawm.com').TrimEnd('/')
$spaceKey  =  Get-Cfg $cfg 'SPACE_KEY'  'BM001'
$listPath  =  Get-Cfg $cfg 'LIST_PATH'  '/collector/pages.action?key={space}'
$recentPath=  Get-Cfg $cfg 'RECENT_PATH' '/pages/recentlyupdated.action?key={space}'
$treePath  =  Get-Cfg $cfg 'TREE_PATH'  '/plugins/pagetree/naturalchildren.action?decorator=none&excerpt=false&sort=position&reverse=false&disableLinks=false&expandCurrent=false'
$viewPath  =  Get-Cfg $cfg 'VIEW_PATH'  '/pages/viewpage.action?pageId={id}'
$authName  =  Get-Cfg $cfg 'AUTH_HEADER_NAME' 'Cookie'
$outDirCfg =  Get-Cfg $cfg 'OUT_DIR'    'wiki_html'
$delayMs   = [int](Get-Cfg $cfg 'DELAY_MS'    '500')
$maxPages  = [int](Get-Cfg $cfg 'MAX_PAGES'   '2000')
$timeoutS  = [int](Get-Cfg $cfg 'TIMEOUT_SEC' '30')
$rootIdCfg =  Get-Cfg $cfg 'ROOT_PAGE_ID' ''

# output dir: relative paths resolve against the script folder, NOT the current
# working dir (running the .bat as admin would otherwise write to System32)
$outDirCfg = $outDirCfg -replace '^\.[\\/]', ''
if ([System.IO.Path]::IsPathRooted($outDirCfg)) {
    $outDir = $outDirCfg
} else {
    $outDir = Join-Path $scriptDir $outDirCfg
}

if ($baseUrl -eq '' -or $spaceKey -eq '') {
    throw 'BASE_URL and SPACE_KEY are required'
}

# --- auth header value: param > file > prompt ---
if (-not $AuthValue) {
    $authFile = Join-Path $scriptDir 'wiki_auth.txt'
    if (Test-Path $authFile) {
        $AuthValue = (Get-Content -Path $authFile -Raw -Encoding UTF8).Trim()
    }
}
if (-not $AuthValue) {
    $AuthValue = Read-Host "Paste $authName header value"
}
if (-not $AuthValue) { throw 'auth header value is empty' }

$headers = @{
    $authName    = $AuthValue
    'User-Agent' = 'wiki-fetch/1.0 (internal batch)'
}

# ---------- http ----------

function Invoke-Page([string]$url) {
    # returns the response HTML; throws 'AUTH_EXPIRED' only if the server
    # REDIRECTED us to the login page (final URI contains login.action).
    # NOTE: do NOT scan the body for 'os_username'/'loginform' — authenticated
    # Confluence pages contain a hidden login form, so body scanning gives a
    # false "auth rejected" on every valid page.
    $resp = Invoke-WebRequest -Uri $url -Headers $headers -UseBasicParsing `
                              -TimeoutSec $timeoutS -MaximumRedirection 5
    $finalUri = ''
    try { $finalUri = $resp.BaseResponse.ResponseUri.AbsoluteUri } catch { }
    if ($finalUri.ToLower().Contains('login.action')) {
        throw 'AUTH_EXPIRED'
    }
    return [string]$resp.Content
}

# ---------- id discovery ----------

function Resolve-RootId([string]$listHtml) {
    if ($rootIdCfg -ne '') { return $rootIdCfg }
    $m = [regex]::Match($listHtml, 'name="rootPageId"\s+value="(\d+)"')
    if ($m.Success) { return $m.Groups[1].Value }
    $m = [regex]::Match($listHtml, 'value="(\d+)"\s+name="rootPageId"')
    if ($m.Success) { return $m.Groups[1].Value }
    return ''
}

function Get-PageIds([string]$html) {
    # all viewpage.action?pageId=NNN occurrences, de-duplicated, order preserved
    $ids = New-Object System.Collections.Generic.List[string]
    $seen = New-Object System.Collections.Generic.HashSet[string]
    foreach ($m in [regex]::Matches($html, 'viewpage\.action\?pageId=(\d+)')) {
        $id = $m.Groups[1].Value
        if ($seen.Add($id)) { [void]$ids.Add($id) }
    }
    return $ids
}

function Collect-TreeIds([string]$rootId) {
    # BFS over the page-tree children endpoint (the static list page only shows
    # expanded nodes; this walks collapsed branches too)
    $ordered = New-Object System.Collections.Generic.List[string]
    $visited = New-Object System.Collections.Generic.HashSet[string]
    $queue   = New-Object System.Collections.Generic.Queue[string]

    [void]$visited.Add($rootId); [void]$ordered.Add($rootId); $queue.Enqueue($rootId)

    while ($queue.Count -gt 0) {
        if ($ordered.Count -ge $maxPages) {
            Write-Host "[warn] tree walk hit MAX_PAGES=$maxPages"
            break
        }
        $pid = $queue.Dequeue()
        $url = "$baseUrl$treePath&hasRoot=true&pageId=$pid&treeId=0&startDepth=0&spaceKey=$spaceKey"
        try {
            $frag = Invoke-Page $url
        } catch {
            if ($_.Exception.Message -eq 'AUTH_EXPIRED') { throw }
            Write-Host "[warn] children fetch failed (pageId=$pid): $($_.Exception.Message)"
            continue
        }
        foreach ($id in (Get-PageIds $frag)) {
            if ($visited.Add($id)) { [void]$ordered.Add($id); $queue.Enqueue($id) }
        }
        Start-Sleep -Milliseconds $delayMs
    }
    return $ordered
}

# ---------- main ----------

Write-Host '============================================================'
Write-Host (" mode      : {0}" -f $(if ($Incremental) { 'incremental' } else { 'full' }))
Write-Host (" base      : {0}" -f $baseUrl)
Write-Host (" space     : {0}" -f $spaceKey)
Write-Host (" out dir   : {0}" -f $outDir)
Write-Host '============================================================'

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# 1) entry page -> page id list
try {
    if ($Incremental) {
        $entryUrl = "$baseUrl$($recentPath.Replace('{space}', $spaceKey))"
        Write-Host "[entry] $entryUrl"
        $entryHtml = Invoke-Page $entryUrl
        $pageIds = Get-PageIds $entryHtml
    } else {
        $entryUrl = "$baseUrl$($listPath.Replace('{space}', $spaceKey))"
        Write-Host "[entry] $entryUrl"
        $entryHtml = Invoke-Page $entryUrl
        $rootId = Resolve-RootId $entryHtml
        if ($rootId -eq '') {
            Write-Host '[warn] rootPageId not found; falling back to ids on the list page'
            $pageIds = Get-PageIds $entryHtml
        } else {
            Write-Host "[tree] rootPageId=$rootId -> walking full tree"
            $pageIds = Collect-TreeIds $rootId
        }
    }
} catch {
    if ($_.Exception.Message -eq 'AUTH_EXPIRED') {
        Write-Host ''
        Write-Host '[ERROR] auth header rejected (bounced to login page).'
        Write-Host '        Refresh the auth header value and run again.'
        exit 2
    }
    throw
}

Write-Host ("[plan] {0} page(s) to fetch" -f $pageIds.Count)

# 2) fetch each body -> save page_<id>.html
$ok = 0; $fail = 0; $i = 0
foreach ($id in $pageIds) {
    $i++
    $url = "$baseUrl$($viewPath.Replace('{id}', $id))"
    $dest = Join-Path $outDir ("page_{0}.html" -f $id)
    try {
        $html = Invoke-Page $url
        # write UTF-8 without BOM so the Python parser reads it cleanly
        [System.IO.File]::WriteAllText($dest, $html, (New-Object System.Text.UTF8Encoding($false)))
        $ok++
        if ($i % 20 -eq 0) { Write-Host ("  fetched {0}/{1}" -f $i, $pageIds.Count) }
    } catch {
        if ($_.Exception.Message -eq 'AUTH_EXPIRED') {
            Write-Host ''
            Write-Host "[ERROR] auth expired mid-run at page $id ($ok saved). Refresh and re-run."
            exit 2
        }
        $fail++
        Write-Host ("[warn] page fetch failed (pageId={0}): {1}" -f $id, $_.Exception.Message)
    }
    Start-Sleep -Milliseconds $delayMs
}

Write-Host '============================================================'
Write-Host (" done: saved {0}, failed {1}, out dir: {2}" -f $ok, $fail, $outDir)
Write-Host ' next (on a Python machine):'
Write-Host ("   python scripts/sync_manual.py --source dir --path `"{0}`"" -f $outDir)
Write-Host '============================================================'
