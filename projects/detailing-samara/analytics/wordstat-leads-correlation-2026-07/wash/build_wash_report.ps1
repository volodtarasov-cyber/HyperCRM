$ErrorActionPreference = 'Stop'

$basePath = 'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\build_pdr_report.ps1'
$script = Get-Content -LiteralPath $basePath -Raw -Encoding UTF8
$root = 'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07'

$script = $script.Replace("$root\pdr\pdr_source.xls", "$root\wash\wash_source.xls")
$script = $script.Replace("$root\pdr\pdr_leads_source.csv", "$root\wash\wash_leads_source.csv")
$script = $script.Replace("$root\pdr\Левша_PDR_лиды_Wordstat_и_динамика.xlsx", "$root\wash\Левша_Мойка_лиды_Wordstat_и_динамика.xlsx")
$script = $script.Replace("$root\pdr\pdr_correlation_preview.png", "$root\wash\wash_correlation_preview.png")
$script = $script.Replace("$root\pdr\pdr_waves_preview.png", "$root\wash\wash_waves_preview.png")
$script = $script.Replace("Worksheets.Item('Период')", "Worksheets.Item('Лист1')")
$script = $script.Replace('PDR', 'Мойка')

& ([scriptblock]::Create($script))
