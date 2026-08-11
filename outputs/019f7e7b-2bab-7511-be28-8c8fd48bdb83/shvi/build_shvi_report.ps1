$ErrorActionPreference = 'Stop'

$basePath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\pdr\build_pdr_report.ps1'
$script = Get-Content -LiteralPath $basePath -Raw -Encoding UTF8

$script = $script.Replace(
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\pdr\pdr_source.xls',
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\shvi\shvi_source.xls'
)
$script = $script.Replace(
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\pdr\pdr_leads_source.csv',
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\shvi\shvi_leads_source.csv'
)
$script = $script.Replace(
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\pdr\Левша_PDR_лиды_Wordstat_и_динамика.xlsx',
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\shvi\Левша_ШВИ_лиды_Wordstat_и_динамика.xlsx'
)
$script = $script.Replace(
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\pdr\pdr_correlation_preview.png',
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\shvi\shvi_correlation_preview.png'
)
$script = $script.Replace(
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\pdr\pdr_waves_preview.png',
    'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\shvi\shvi_waves_preview.png'
)
$script = $script.Replace("Worksheets.Item('Период')", "Worksheets.Item('Лист1')")
$script = $script.Replace('PDR', 'Шумо-виброизоляция')

& ([scriptblock]::Create($script))
