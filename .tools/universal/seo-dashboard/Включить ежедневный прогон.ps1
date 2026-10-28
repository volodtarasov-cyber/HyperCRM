# Задача планировщика «SEO-дашборд»: каждый день в 08:00 — техаудит заводов и сборка дашборда (daily.py).
# Компьютер был выключен в 08:00 — прогон запустится после включения. Без окна (pythonw).
# Повторный запуск пересоздаёт задачу. Убрать: Unregister-ScheduledTask -TaskName "SEO-дашборд" -Confirm:$false
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyw = Join-Path $here "..\..\venv\Scripts\pythonw.exe" | Resolve-Path
$action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$here\daily.py`"" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -Daily -At 08:00
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName "SEO-дашборд" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Техаудит SEO-заводов и сборка дашборда. HyperCRM/.tools/universal/seo-dashboard/daily.py" -Force | Out-Null
Get-ScheduledTask -TaskName "SEO-дашборд" | Get-ScheduledTaskInfo | Select-Object TaskName, NextRunTime
