param(
    [ValidateSet('setup', 'test', 'top', 'dynamics', 'regions', 'region-tree')]
    [string]$Action = 'test',
    [string]$Phrase,
    [int[]]$RegionIds,
    [ValidateSet('all', 'desktop', 'phone', 'tablet')]
    [string]$Device = 'all',
    [ValidateSet('daily', 'weekly', 'monthly')]
    [string]$Period = 'monthly',
    [string]$FromDate,
    [string]$ToDate,
    [ValidateSet('all', 'cities', 'regions')]
    [string]$RegionType = 'all',
    [string]$OutFile
)

$ErrorActionPreference = 'Stop'
$ApiBase = 'https://api.wordstat.yandex.net/v1'
$SecretDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'HyperCRM'
$TokenFile = Join-Path $SecretDirectory 'wordstat-token.dpapi'

function Save-WordstatToken {
    if (-not (Test-Path -LiteralPath $SecretDirectory)) {
        New-Item -ItemType Directory -Path $SecretDirectory | Out-Null
    }

    $secureToken = Read-Host 'Paste the Wordstat OAuth token (input is hidden)' -AsSecureString
    $secureToken | ConvertFrom-SecureString | Set-Content -LiteralPath $TokenFile -Encoding UTF8
    Write-Host "Token encrypted with Windows DPAPI and saved outside the vault: $TokenFile"
}

function Get-WordstatToken {
    if (-not (Test-Path -LiteralPath $TokenFile)) {
        throw "Token is not configured. Run: powershell -ExecutionPolicy Bypass -File .\.tools\wordstat.ps1 -Action setup"
    }

    $secureToken = Get-Content -LiteralPath $TokenFile -Encoding UTF8 -Raw | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Invoke-WordstatRequest {
    param(
        [Parameter(Mandatory = $true)][string]$Method,
        [hashtable]$Payload = @{}
    )

    $token = Get-WordstatToken
    $headers = @{ Authorization = "Bearer $token" }
    $jsonBody = $Payload | ConvertTo-Json -Depth 6 -Compress

    try {
        return Invoke-RestMethod `
            -Uri "$ApiBase/$Method" `
            -Method Post `
            -Headers $headers `
            -ContentType 'application/json; charset=utf-8' `
            -Body ([Text.Encoding]::UTF8.GetBytes($jsonBody))
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 401 -or $statusCode -eq 403) {
            throw 'Wordstat rejected authorization or API access is not approved yet. Check the token and Yandex support response.'
        }
        if ($statusCode -eq 429) {
            throw 'The personal Wordstat quota is exhausted. Retry later.'
        }
        if ($statusCode -eq 503) {
            throw 'The global Wordstat quota is temporarily exhausted. Retry later.'
        }
        throw
    }
}

if ($Action -eq 'setup') {
    Save-WordstatToken
    exit 0
}

if ($Action -in @('top', 'dynamics', 'regions') -and [string]::IsNullOrWhiteSpace($Phrase)) {
    throw "Action '$Action' requires -Phrase."
}

$result = switch ($Action) {
    'test' { Invoke-WordstatRequest -Method 'getRegionsTree' }
    'region-tree' { Invoke-WordstatRequest -Method 'getRegionsTree' }
    'top' {
        $payload = @{ phrase = $Phrase; devices = @($Device) }
        if ($RegionIds) { $payload.regions = @($RegionIds) }
        Invoke-WordstatRequest -Method 'topRequests' -Payload $payload
    }
    'dynamics' {
        if ([string]::IsNullOrWhiteSpace($FromDate)) {
            throw "Action 'dynamics' requires -FromDate in YYYY-MM-DD format."
        }
        $payload = @{ phrase = $Phrase; period = $Period; fromDate = $FromDate; devices = @($Device) }
        if ($ToDate) { $payload.toDate = $ToDate }
        if ($RegionIds) { $payload.regions = @($RegionIds) }
        Invoke-WordstatRequest -Method 'dynamics' -Payload $payload
    }
    'regions' {
        $payload = @{ phrase = $Phrase; regionType = $RegionType; devices = @($Device) }
        Invoke-WordstatRequest -Method 'regions' -Payload $payload
    }
}

$json = $result | ConvertTo-Json -Depth 12
if ($OutFile) {
    $resolvedOutFile = [IO.Path]::GetFullPath((Join-Path (Get-Location) $OutFile))
    $workspaceRoot = [IO.Path]::GetFullPath((Get-Location).Path)
    if (-not $resolvedOutFile.StartsWith($workspaceRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'OutFile must be inside the current workspace.'
    }
    $json | Set-Content -LiteralPath $resolvedOutFile -Encoding UTF8
    Write-Host "Result saved: $resolvedOutFile"
}
else {
    $json
}
