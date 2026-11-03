$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$dataRoot = Join-Path $projectRoot '.tools/local/flagman-vii'
$inventory = Get-Content -LiteralPath (Join-Path $dataRoot 'inventory.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$members = Get-Content -LiteralPath (Join-Path $dataRoot 'archive-members.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$items = @()
foreach ($entry in $inventory.files) {
    if ($entry.extension -eq '.doc') {
        $items += @{path=$entry.path; local_path=(Join-Path $inventory.source $entry.path)}
    }
}
foreach ($entry in $members) {
    if ($entry.extension -eq '.doc') { $items += @{path=$entry.path; local_path=$entry.local_path} }
}
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3
$word.Options.UpdateLinksAtOpen = $false
$results = @()
try {
    $ordinal = 0
    foreach ($entry in $items) {
        $ordinal++
        $document = $null
        try {
            $document = $word.Documents.Open($entry.local_path, $false, $true, $false)
            $body = $document.Content.Text
            $target = Join-Path $dataRoot ('analysis/legacy-doc-' + $ordinal + '.txt')
            [System.IO.File]::WriteAllText($target, $body, [System.Text.UTF8Encoding]::new($false))
            $results += @{path=$entry.path; extracted_path=$target; characters=$body.Length; read_only=$true; macros_disabled=$true}
        } catch {
            $results += @{path=$entry.path; error=$_.Exception.Message}
        } finally {
            if ($null -ne $document) { $document.Close() }
        }
    }
} finally {
    $word.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
$manifest = ConvertTo-Json -InputObject @($results) -Depth 6
[System.IO.File]::WriteAllText((Join-Path $dataRoot 'analysis/legacy-documents.json'), $manifest, [System.Text.UTF8Encoding]::new($false))
$results | ForEach-Object { Write-Output ($_.path + ' | characters=' + $_.characters + ' | error=' + $_.error) }
