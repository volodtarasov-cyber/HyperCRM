$ErrorActionPreference = 'Stop'

$basePath = 'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\build_pdr_report.ps1'
$script = Get-Content -LiteralPath $basePath -Raw -Encoding UTF8

$script = $script.Replace(
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\pdr_source.xls',
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\shvi\shvi_source.xls'
)
$script = $script.Replace(
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\pdr_leads_source.csv',
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\shvi\shvi_leads_source.csv'
)
$script = $script.Replace(
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\Левша_PDR_лиды_Wordstat_и_динамика.xlsx',
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\shvi\Левша_ШВИ_лиды_Wordstat_и_динамика.xlsx'
)
$script = $script.Replace(
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\pdr_correlation_preview.png',
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\shvi\shvi_correlation_preview.png'
)
$script = $script.Replace(
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\pdr\pdr_waves_preview.png',
    'D:\SecondBrain\HyperCRM\projects\detailing-samara\analytics\wordstat-leads-correlation-2026-07\shvi\shvi_waves_preview.png'
)
$script = $script.Replace("Worksheets.Item('Период')", "Worksheets.Item('Лист1')")
$script = $script.Replace('PDR', 'Шумо-виброизоляция')

& ([scriptblock]::Create($script))
