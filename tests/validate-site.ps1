$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$failures = [System.Collections.Generic.List[string]]::new()
$passes = [System.Collections.Generic.List[string]]::new()

function Assert-Site {
    param(
        [bool]$Condition,
        [string]$Name
    )

    if ($Condition) {
        $passes.Add($Name)
    }
    else {
        $failures.Add($Name)
    }
}

function Read-Page {
    param([string]$Name)

    $path = Join-Path $projectRoot $Name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        return $null
    }

    return Get-Content -LiteralPath $path -Raw -Encoding UTF8
}

$requiredFiles = @(
    'index.html',
    'privacy.html',
    'terms.html',
    'styles.css',
    'README.md',
    '.nojekyll'
)

foreach ($file in $requiredFiles) {
    Assert-Site (Test-Path -LiteralPath (Join-Path $projectRoot $file) -PathType Leaf) "required file: $file"
}

$legacyPlaceholder = 'CONTACT_' + 'EMAIL_REQUIRED'
$repositoryFiles = Get-ChildItem -LiteralPath $projectRoot -Recurse -File -Force |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' }
$legacyMatches = @($repositoryFiles | Select-String -SimpleMatch $legacyPlaceholder)
Assert-Site ($legacyMatches.Count -eq 0) 'repository contains no legacy contact placeholder'

$pages = @{
    'index.html' = Read-Page 'index.html'
    'privacy.html' = Read-Page 'privacy.html'
    'terms.html' = Read-Page 'terms.html'
}

foreach ($entry in $pages.GetEnumerator()) {
    $name = $entry.Key
    $html = $entry.Value
    if ($null -eq $html) {
        continue
    }

    Assert-Site ($html -match '<!doctype html>') "$name uses HTML5 doctype"
    Assert-Site ($html -match '<html lang="en">') "$name declares English"
    Assert-Site ($html -match '<meta charset="UTF-8">') "$name declares UTF-8"
    Assert-Site ($html -match 'name="viewport"\s+content="width=device-width, initial-scale=1"') "$name sets viewport"
    Assert-Site ($html -match '<title>[^<]+</title>') "$name has a title"
    Assert-Site ($html -match 'href="styles\.css"') "$name loads local CSS"
    Assert-Site ($html -match 'href="index\.html"') "$name links Home directly"
    Assert-Site ($html -match 'href="privacy\.html"') "$name links Privacy directly"
    Assert-Site ($html -match 'href="terms\.html"') "$name links Terms directly"
    Assert-Site ($html -notmatch '<script\b') "$name contains no JavaScript"
    Assert-Site ($html -notmatch '(?:src|href)="https?://') "$name contains no external resources"
    Assert-Site ($html -notmatch 'TikTok[- ]?(logo|icon)') "$name contains no TikTok logo reference"

    $links = [regex]::Matches($html, 'href="([^"#]+)"')
    foreach ($link in $links) {
        $href = $link.Groups[1].Value
        if ($href -match '^(mailto:|https?:)') {
            continue
        }
        Assert-Site (Test-Path -LiteralPath (Join-Path $projectRoot $href) -PathType Leaf) "$name resolves $href"
    }
}

$index = $pages['index.html']
if ($null -ne $index) {
    foreach ($section in @('about', 'how-it-works', 'data-and-authorization', 'integration-status')) {
        Assert-Site ($index -match "id=`"$section`"") "index contains #$section"
    }
    foreach ($phrase in @(
        'Prepare your own video',
        'Review publishing details',
        'Authorize your account',
        'Publish with explicit user consent',
        'does not collect your TikTok password',
        'explicit consent'
    )) {
        Assert-Site ($index -match [regex]::Escape($phrase)) "index states: $phrase"
    }
    Assert-Site ($index -match 'currently being integrated') 'index discloses integration status'
    Assert-Site ($index -notmatch '(official TikTok|partnered with TikTok|guaranteed approval|fully automated posting)') 'index avoids prohibited claims'
}

$privacy = $pages['privacy.html']
if ($null -ne $privacy) {
    foreach ($heading in @(
        'Effective date',
        'What information may be processed',
        'TikTok OAuth authentication',
        'Access tokens',
        'Video and post metadata',
        'How information is used',
        'Data storage',
        'Third-party services',
        'Security',
        'Data retention',
        'Your requests and deletion',
        'Changes to this policy',
        'Contact'
    )) {
        Assert-Site ($privacy -match [regex]::Escape($heading)) "privacy covers: $heading"
    }
    Assert-Site ($privacy -match 't4786366@gmail\.com') 'privacy shows public contact email'
    Assert-Site ($privacy -match 'does not currently collect') 'privacy describes current static-site behavior'
    Assert-Site ($privacy -match 'before.*OAuth|OAuth.*before') 'privacy makes future OAuth handling conditional'
}

$terms = $pages['terms.html']
if ($null -ne $terms) {
    foreach ($heading in @(
        'Acceptance of Terms',
        'Description of Service',
        'User Responsibilities',
        'User-owned content only',
        'Prohibited Use',
        'Third-Party Platforms',
        'Intellectual Property',
        'Availability',
        'Disclaimer',
        'Limitation of Liability',
        'Termination',
        'Changes',
        'Contact'
    )) {
        Assert-Site ($terms -match [regex]::Escape($heading)) "terms covers: $heading"
    }
    foreach ($prohibition in @('spam', 'rate limits', 'unauthorized access', 'another person')) {
        Assert-Site ($terms -match [regex]::Escape($prohibition)) "terms prohibits: $prohibition"
    }
    Assert-Site ($terms -match 't4786366@gmail\.com') 'terms shows public contact email'
}

$readme = Read-Page 'README.md'
if ($null -ne $readme) {
    foreach ($phrase in @(
        'http://127.0.0.1:3455/callback/',
        'PKCE',
        'state',
        't4786366@gmail.com',
        'URL Properties',
        'signature file',
        'Production Review',
        'video.publish'
    )) {
        Assert-Site ($readme -match [regex]::Escape($phrase)) "README documents: $phrase"
    }
}

foreach ($pass in $passes) {
    Write-Host "PASS: $pass"
}
foreach ($failure in $failures) {
    Write-Host "FAIL: $failure"
}

Write-Host "RESULT: $($passes.Count) passed, $($failures.Count) failed"
if ($failures.Count -gt 0) {
    exit 1
}
