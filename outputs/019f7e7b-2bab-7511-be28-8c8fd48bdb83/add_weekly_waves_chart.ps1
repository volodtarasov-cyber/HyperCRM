$ErrorActionPreference = 'Stop'

$workbookPath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\Левша_пленка_лиды_и_Wordstat_понедельно.xlsx'
$outputPath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\Левша_пленка_лиды_Wordstat_и_динамика.xlsx'
$previewPath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\weekly_waves_preview.png'

$excel = $null
$workbook = $null
$dynamics = $null
$summary = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false

    $workbook = $excel.Workbooks.Open($workbookPath, 0, $true)
    $summary = $workbook.Worksheets.Item('Недельная сводка')

    foreach ($sheet in @($workbook.Worksheets)) {
        if ($sheet.Name -eq 'Динамика') { $sheet.Delete(); break }
    }
    $dynamics = $workbook.Worksheets.Add()
    $dynamics.Name = 'Динамика'
    $dynamics.Cells.Clear()
    $dynamics.Range('A1:N1').Merge()
    $dynamics.Range('A1').Value2 = 'Недельная динамика спроса и лидов'
    $dynamics.Range('A2:N2').Merge()
    $dynamics.Range('A2').Value2 = 'Лиды и качественные лиды — левая шкала; запросы Wordstat — правая шкала'
    $dynamics.Range('A1:N1').Interior.Color = 10040012
    $dynamics.Range('A1:N1').Font.Color = 16777215
    $dynamics.Range('A1:N1').Font.Bold = $true
    $dynamics.Range('A1:N1').Font.Size = 18
    $dynamics.Range('A1:N1').HorizontalAlignment = -4108
    $dynamics.Range('A2:N2').Interior.Color = 15132390
    $dynamics.Range('A2:N2').Font.Color = 5460819
    $dynamics.Range('A2:N2').HorizontalAlignment = -4108
    $dynamics.Rows.Item(1).RowHeight = 30
    $dynamics.Rows.Item(2).RowHeight = 24
    $dynamics.Columns('A:N').ColumnWidth = 11

    $chartObject = $dynamics.ChartObjects().Add(20, 80, 1120, 560)
    $chart = $chartObject.Chart
    $chart.ChartType = 4
    $chart.HasTitle = $true
    $chart.ChartTitle.Text = 'Лиды, качественные лиды и запросы Wordstat по неделям'
    $chart.HasLegend = $true
    $chart.Legend.Position = -4107

    $firstRow = 5
    $lastRow = 241
    $categories = $summary.Range("A${firstRow}:A${lastRow}")

    $allLeads = $chart.SeriesCollection().NewSeries()
    $allLeads.Name = 'Лиды'
    $allLeads.XValues = $categories
    $allLeads.Values = $summary.Range("D${firstRow}:D${lastRow}")
    $allLeads.Format.Line.ForeColor.RGB = 10040012
    $allLeads.Format.Line.Weight = 1.75
    $allLeads.MarkerStyle = -4142

    $qualified = $chart.SeriesCollection().NewSeries()
    $qualified.Name = 'Качественные лиды'
    $qualified.XValues = $categories
    $qualified.Values = $summary.Range("E${firstRow}:E${lastRow}")
    $qualified.Format.Line.ForeColor.RGB = 5287936
    $qualified.Format.Line.Weight = 1.75
    $qualified.MarkerStyle = -4142

    $requests = $chart.SeriesCollection().NewSeries()
    $requests.Name = 'Запросы Wordstat'
    $requests.XValues = $categories
    $requests.Values = $summary.Range("F${firstRow}:F${lastRow}")
    $requests.AxisGroup = 2
    $requests.Format.Line.ForeColor.RGB = 12611584
    $requests.Format.Line.Weight = 2.25
    $requests.MarkerStyle = -4142

    $chart.Axes(1,1).HasTitle = $true
    $chart.Axes(1,1).AxisTitle.Text = 'Неделя'
    $chart.Axes(1,1).TickLabelSpacing = 13
    $chart.Axes(1,1).TickLabels.NumberFormatLocal = 'МММ ГГ'
    $chart.Axes(2,1).HasTitle = $true
    $chart.Axes(2,1).AxisTitle.Text = 'Количество лидов'
    $chart.Axes(2,2).HasTitle = $true
    $chart.Axes(2,2).AxisTitle.Text = 'Запросы Wordstat'
    $chart.Axes(2,1).MinimumScale = 0
    $chart.Axes(2,2).MinimumScale = 0

    $dynamics.Range('A35:N36').Merge()
    $dynamics.Range('A35').Value2 = 'Шаг данных — 1 неделя. Подписи на оси показаны реже для читаемости; каждая точка линии соответствует отдельной неделе.'
    $dynamics.Range('A35:N36').WrapText = $true
    $dynamics.Range('A35:N36').Interior.Color = 15794160
    $dynamics.Range('A35:N36').Font.Color = 5460819
    $dynamics.Activate()
    $excel.ActiveWindow.DisplayGridlines = $false
    $excel.ActiveWindow.Zoom = 85

    $excel.CalculateFull()
    $workbook.SaveAs($outputPath, 51)
    [void]$chart.Export($previewPath, 'PNG')
    $workbook.Close($true)
    $excel.Quit()
    Write-Output $outputPath
}
finally {
    foreach ($object in @($chart, $chartObject, $dynamics, $summary, $workbook, $excel)) {
        if ($null -ne $object) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($object) } catch {} }
    }
    [gc]::Collect()
    [gc]::WaitForPendingFinalizers()
}
