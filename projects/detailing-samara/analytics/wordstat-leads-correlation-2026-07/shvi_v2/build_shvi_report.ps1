$ErrorActionPreference = 'Stop'

$basePath = 'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\build_pdr_report.ps1'
$script = Get-Content -LiteralPath $basePath -Raw -Encoding UTF8
$root = 'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07'

$script = $script.Replace("$root\pdr\pdr_source.xls", "$root\shvi_v2\shvi_source.xls")
$script = $script.Replace("$root\pdr\pdr_leads_source.csv", "$root\shvi_v2\shvi_leads_source.csv")
$script = $script.Replace("$root\pdr\Левша_PDR_лиды_Wordstat_и_динамика.xlsx", "$root\shvi_v2\Левша_ШВИ_лиды_Wordstat_и_динамика.xlsx")
$script = $script.Replace("$root\pdr\pdr_correlation_preview.png", "$root\shvi_v2\shvi_correlation_preview.png")
$script = $script.Replace("$root\pdr\pdr_waves_preview.png", "$root\shvi_v2\shvi_waves_preview.png")
$script = $script.Replace("Worksheets.Item('Период')", "Worksheets.Item('Лист1')")
$script = $script.Replace('PDR', 'Шумо-виброизоляция')

& ([scriptblock]::Create($script))
