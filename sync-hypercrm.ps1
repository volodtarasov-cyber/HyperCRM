[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot

function Invoke-Git {
    param([string[]]$GitArgs)

    & git -C $repoRoot @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Git failed with exit code ${LASTEXITCODE}: git $($GitArgs -join ' ')"
    }
}

try {
    Write-Host ''
    Write-Host 'HyperCRM: GitHub sync' -ForegroundColor Cyan
    Write-Host "Folder: $repoRoot"

    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'Git was not found. Install Git for Windows and try again.'
    }

    if (-not (Test-Path -LiteralPath (Join-Path $repoRoot '.git'))) {
        throw 'The HyperCRM Git repository was not found next to this script.'
    }

    $unfinished = @(
        'MERGE_HEAD',
        'rebase-merge',
        'rebase-apply',
        'CHERRY_PICK_HEAD'
    ) | Where-Object { Test-Path -LiteralPath (Join-Path $repoRoot ".git/$_") }

    if ($unfinished.Count -gt 0) {
        throw 'An unfinished Git operation was found. Sync stopped to protect local changes.'
    }

    Write-Host '[1/4] Saving local changes...'
    Invoke-Git -GitArgs @('add', '-A')

    & git -C $repoRoot diff --cached --quiet
    if ($LASTEXITCODE -eq 1) {
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
        Invoke-Git -GitArgs @('commit', '-m', "Sync $stamp")
    }
    elseif ($LASTEXITCODE -ne 0) {
        throw 'Could not inspect local changes.'
    }
    else {
        Write-Host 'No local changes.'
    }

    Write-Host '[2/4] Fetching changes from GitHub...'
    Invoke-Git -GitArgs @('fetch', 'origin')

    Write-Host '[3/4] Updating local history...'
    Invoke-Git -GitArgs @('pull', '--rebase', 'origin', 'master')

    Write-Host '[4/4] Pushing changes to GitHub...'
    Invoke-Git -GitArgs @('push', 'origin', 'master')

    Write-Host ''
    Write-Host 'Done: the local folder and GitHub are synchronized.' -ForegroundColor Green
    exit 0
}
catch {
    Write-Host ''
    Write-Host "Sync stopped: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'No files were deleted. Copy this error into Codex for help.' -ForegroundColor Yellow
    exit 1
}
