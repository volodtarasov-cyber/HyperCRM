$ErrorActionPreference = 'Stop'
$publisherVault = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../../..')).Path
$publisherPython = Join-Path $publisherVault '.tools/venv/Scripts/python.exe'
$publisherScript = Join-Path $PSScriptRoot 'social-publisher.py'
$publisherLocal = Join-Path $publisherVault '.tools/local/social-publisher'
$publisherUrl = 'http://127.0.0.1:8766/'

try {
    $publisherState = Invoke-RestMethod -Uri ($publisherUrl + 'api/state') -TimeoutSec 2
    if ($publisherState.platforms -and $publisherState.pack_name) {
        Start-Process $publisherUrl
        exit
    }
} catch {}

New-Item -ItemType Directory -Path $publisherLocal -Force | Out-Null
$publisherProcess = Start-Process -FilePath $publisherPython -ArgumentList @('-X', 'utf8', ('"' + $publisherScript + '"')) -WorkingDirectory $publisherVault -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $publisherLocal 'server.log') -RedirectStandardError (Join-Path $publisherLocal 'server-error.log')

for ($publisherAttempt = 0; $publisherAttempt -lt 50; $publisherAttempt++) {
    if ($publisherProcess.HasExited) {
        throw 'Не удалось открыть инструмент. Подробности: .tools/local/social-publisher/server-error.log'
    }
    try {
        $publisherState = Invoke-RestMethod -Uri ($publisherUrl + 'api/state') -TimeoutSec 1
        if ($publisherState.platforms) {
            Write-Output "Публикация карточек: $publisherUrl"
            exit
        }
    } catch {}
    Start-Sleep -Milliseconds 250
}
throw 'Инструмент запускается дольше ожидаемого. Проверь локальный журнал.'
