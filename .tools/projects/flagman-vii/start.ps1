$ErrorActionPreference = 'Stop'
$courseVault = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../../..')).Path
$coursePython = Join-Path $courseVault '.tools/venv-whisper/Scripts/python.exe'
$courseScript = Join-Path $PSScriptRoot 'course.py'
$courseData = Join-Path $courseVault '.tools/local/flagman-vii'
$coursePidFile = Join-Path $courseData 'worker.pid'
if (Test-Path -LiteralPath (Join-Path $courseData 'STOP')) {
    throw 'STOP marker exists. Remove it to resume.'
}
if (Test-Path -LiteralPath $coursePidFile) {
    $coursePreviousPid = [int](Get-Content -LiteralPath $coursePidFile)
    if (Get-Process -Id $coursePreviousPid -ErrorAction SilentlyContinue) {
        throw "Worker PID $coursePreviousPid is still running."
    }
}
$courseProcess = Start-Process -FilePath $coursePython -ArgumentList @('-X', 'utf8', ('"' + $courseScript + '"'), 'run') -WorkingDirectory $courseVault -WindowStyle Hidden -RedirectStandardOutput (Join-Path $courseData 'worker.stdout.log') -RedirectStandardError (Join-Path $courseData 'worker.stderr.log') -PassThru
$courseProcess.Id | Set-Content -LiteralPath $coursePidFile -Encoding ASCII
Write-Output "Started worker PID $($courseProcess.Id). Logs: $courseData"
