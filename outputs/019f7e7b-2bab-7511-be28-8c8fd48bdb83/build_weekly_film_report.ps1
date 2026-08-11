$ErrorActionPreference = 'Stop'

$leadPath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\leads_source.csv'
$wordstatPath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\wordstat_source.csv'
$outputPath = 'C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\Левша_пленка_лиды_и_Wordstat_понедельно.xlsx'

$culture = [System.Globalization.CultureInfo]::GetCultureInfo('ru-RU')
$leadRows = Import-Csv -LiteralPath $leadPath -Delimiter ';' -Encoding UTF8
$wordstatRows = Import-Csv -LiteralPath $wordstatPath -Delimiter ';' -Encoding Default

function Parse-RuDate([string]$text) {
    return [datetime]::Parse($text.Trim(), $culture, [System.Globalization.DateTimeStyles]::AllowWhiteSpaces)
}

$periods = foreach ($row in $wordstatRows) {
    $parts = $row.'Период' -split '\s+[–-]\s+'
    if ($parts.Count -ne 2) { throw "Не удалось разобрать период: $($row.'Период')" }
    [pscustomobject]@{
        Start = Parse-RuDate $parts[0]
        End = Parse-RuDate $parts[1]
        Label = $row.'Период'
        Requests = [int]$row.'Числозапросов'
        Share = if ([string]::IsNullOrWhiteSpace($row.'Доля от всехзапросов, %')) { $null } else { [double]::Parse($row.'Доля от всехзапросов, %', $culture) }
    }
}

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false

    $workbook = $excel.Workbooks.Add()
    while ($workbook.Worksheets.Count -lt 4) { [void]$workbook.Worksheets.Add() }
    while ($workbook.Worksheets.Count -gt 4) { $workbook.Worksheets.Item($workbook.Worksheets.Count).Delete() }
    $dashboard = $workbook.Worksheets.Item(1); $dashboard.Name = 'Дашборд'
    $summary = $workbook.Worksheets.Item(2); $summary.Name = 'Недельная сводка'
    $leads = $workbook.Worksheets.Item(3); $leads.Name = 'Исходник — лиды'
    $wordstat = $workbook.Worksheets.Item(4); $wordstat.Name = 'Исходник — Wordstat'

    # Raw leads
    $leadHeaders = @($leadRows[0].PSObject.Properties.Name)
    $leadMatrix = New-Object 'object[,]' ($leadRows.Count + 1), $leadHeaders.Count
    for ($c = 0; $c -lt $leadHeaders.Count; $c++) { $leadMatrix[0,$c] = $leadHeaders[$c] }
    for ($r = 0; $r -lt $leadRows.Count; $r++) {
        for ($c = 0; $c -lt $leadHeaders.Count; $c++) {
            $value = $leadRows[$r].($leadHeaders[$c])
            if ($leadHeaders[$c] -eq 'Дата создания') {
                $leadMatrix[($r + 1),$c] = [datetime]::ParseExact($value, 'dd.MM.yyyy HH:mm:ss', $null).ToOADate()
            } else { $leadMatrix[($r + 1),$c] = $value }
        }
    }
    $leadRange = $leads.Range($leads.Cells(1,1), $leads.Cells($leadRows.Count + 1, $leadHeaders.Count))
    $leadRange.Value2 = $leadMatrix
    $leadDateCol = [array]::IndexOf($leadHeaders, 'Дата создания') + 1
    $leadStageCol = [array]::IndexOf($leadHeaders, 'Стадия') + 1
    $leads.Range("H2:H$($leadRows.Count + 1)").NumberFormatLocal = 'ДД.ММ.ГГГГ чч:мм'
    $leadTable = $leads.ListObjects.Add(1, $leadRange, $null, 1)
    $leadTable.Name = 'tblLeads'; $leadTable.TableStyle = 'TableStyleMedium2'
    $leads.Rows.Item(1).Font.Bold = $true
    $leads.Application.ActiveWindow.SplitRow = 1; $leads.Application.ActiveWindow.FreezePanes = $true
    $leads.Columns.AutoFit() | Out-Null
    for ($c=1; $c -le $leadHeaders.Count; $c++) { if ($leads.Columns.Item($c).ColumnWidth -gt 28) { $leads.Columns.Item($c).ColumnWidth = 28 } }

    # Raw Wordstat
    $wsHeaders = @('Начало недели','Конец недели','Период Wordstat','Число запросов','Доля от всех запросов, %')
    $wsMatrix = New-Object 'object[,]' ($periods.Count + 1), $wsHeaders.Count
    for ($c=0; $c -lt $wsHeaders.Count; $c++) { $wsMatrix[0,$c] = $wsHeaders[$c] }
    for ($r=0; $r -lt $periods.Count; $r++) {
        $wsMatrix[($r+1),0] = $periods[$r].Start.ToOADate(); $wsMatrix[($r+1),1] = $periods[$r].End.ToOADate()
        $wsMatrix[($r+1),2] = $periods[$r].Label; $wsMatrix[($r+1),3] = $periods[$r].Requests; $wsMatrix[($r+1),4] = $periods[$r].Share
    }
    $wsRange = $wordstat.Range($wordstat.Cells(1,1), $wordstat.Cells($periods.Count + 1,5)); $wsRange.Value2 = $wsMatrix
    $wordstat.Range("A2:B$($periods.Count + 1)").NumberFormatLocal = 'ДД.ММ.ГГГГ'; $wordstat.Range("E2:E$($periods.Count + 1)").NumberFormatLocal = '0,000000'
    $wsTable = $wordstat.ListObjects.Add(1, $wsRange, $null, 1); $wsTable.Name = 'tblWordstat'; $wsTable.TableStyle = 'TableStyleMedium4'
    $wordstat.Columns.AutoFit() | Out-Null; $wordstat.Columns.Item(3).ColumnWidth = 36

    # Weekly summary
    $summary.Range('A1:G1').Merge(); $summary.Range('A1').Value2 = 'Левша — плёнка: лиды и спрос Wordstat по неделям'
    $summary.Range('A2:G2').Merge(); $summary.Range('A2').Value2 = 'Периоды заданы выгрузкой Wordstat. Успешный лид = стадия «Качественный лид».'
    $sumHeaders = @('Начало недели','Конец недели','Период Wordstat','Все лиды','Качественные лиды','Запросы Wordstat','Доля качественных')
    $sumMatrix = New-Object 'object[,]' ($periods.Count + 1), 7
    for ($c=0; $c -lt 7; $c++) { $sumMatrix[0,$c] = $sumHeaders[$c] }
    for ($r=0; $r -lt $periods.Count; $r++) {
        $sumMatrix[($r+1),0] = $periods[$r].Start.ToOADate(); $sumMatrix[($r+1),1] = $periods[$r].End.ToOADate()
        $sumMatrix[($r+1),2] = $periods[$r].Label; $sumMatrix[($r+1),5] = $periods[$r].Requests
    }
    $summary.Range($summary.Cells(4,1), $summary.Cells($periods.Count + 4,7)).Value2 = $sumMatrix
    $firstDataRow = 5; $lastDataRow = $periods.Count + 4
    $dateLetter = 'H'; $stageLetter = 'C'
    $summary.Range("D${firstDataRow}:D${lastDataRow}").FormulaR1C1 = '=COUNTIFS(''Исходник — лиды''!R2C8:R4774C8,">="&RC[-3],''Исходник — лиды''!R2C8:R4774C8,"<"&RC[-2]+1)'
    $summary.Range("E${firstDataRow}:E${lastDataRow}").FormulaR1C1 = '=COUNTIFS(''Исходник — лиды''!R2C8:R4774C8,">="&RC[-4],''Исходник — лиды''!R2C8:R4774C8,"<"&RC[-3]+1,''Исходник — лиды''!R2C3:R4774C3,"Качественный лид")'
    $summary.Range("G${firstDataRow}:G${lastDataRow}").FormulaR1C1 = '=IFERROR(RC[-2]/RC[-3],0)'
    $summary.Range("A${firstDataRow}:B${lastDataRow}").NumberFormatLocal = 'ДД.ММ.ГГГГ'; $summary.Range("G${firstDataRow}:G${lastDataRow}").NumberFormatLocal = '0,0%'
    $sumTable = $summary.ListObjects.Add(1, $summary.Range($summary.Cells(4,1),$summary.Cells($lastDataRow,7)), $null, 1); $sumTable.Name = 'tblWeekly'; $sumTable.TableStyle = 'TableStyleMedium2'
    $summary.Range('A1:G1').Interior.Color = 10040012; $summary.Range('A1:G1').Font.Color = 16777215; $summary.Range('A1:G1').Font.Bold = $true; $summary.Range('A1:G1').Font.Size = 16
    $summary.Range('A2:G2').Interior.Color = 15132390; $summary.Range('A2:G2').Font.Color = 5460819
    $summary.Rows.Item(1).RowHeight = 28; $summary.Rows.Item(2).RowHeight = 24
    $summary.Columns.Item(1).ColumnWidth=13; $summary.Columns.Item(2).ColumnWidth=13; $summary.Columns.Item(3).ColumnWidth=36
    for ($c=4; $c -le 7; $c++) { $summary.Columns.Item($c).ColumnWidth=18 }
    $summary.Activate(); $excel.ActiveWindow.SplitRow=4; $excel.ActiveWindow.FreezePanes=$true; $summary.Application.ActiveWindow.Zoom=85

    # Dashboard
    $dashboard.Range('A1:L1').Merge(); $dashboard.Range('A1').Value2 = 'Левша — спрос на плёнку и лиды'
    $dashboard.Range('A2:L2').Merge(); $dashboard.Range('A2').Value2 = 'Недельная аналитика: 27.12.2021–12.07.2026'
    $dashboard.Range('A1:L1').Interior.Color = 10040012; $dashboard.Range('A1:L1').Font.Color=16777215; $dashboard.Range('A1:L1').Font.Bold=$true; $dashboard.Range('A1:L1').Font.Size=18
    $dashboard.Range('A2:L2').Interior.Color = 15132390; $dashboard.Range('A2:L2').Font.Color=5460819
    $dashboard.Range('A4:B4').Merge(); $dashboard.Range('D4:E4').Merge(); $dashboard.Range('G4:H4').Merge(); $dashboard.Range('J4:K4').Merge()
    $dashboard.Range('A4').Value2='Всего лидов'; $dashboard.Range('D4').Value2='Качественных лидов'; $dashboard.Range('G4').Value2='Запросов Wordstat'; $dashboard.Range('J4').Value2='Недель в анализе'
    $dashboard.Range('A5:B6').Merge(); $dashboard.Range('D5:E6').Merge(); $dashboard.Range('G5:H6').Merge(); $dashboard.Range('J5:K6').Merge()
    $dashboard.Range('A5').Formula="=SUM('Недельная сводка'!D${firstDataRow}:D${lastDataRow})"; $dashboard.Range('D5').Formula="=SUM('Недельная сводка'!E${firstDataRow}:E${lastDataRow})"
    $dashboard.Range('G5').Formula="=SUM('Недельная сводка'!F${firstDataRow}:F${lastDataRow})"; $dashboard.Range('J5').Value2=$periods.Count
    foreach($addr in @('A4:B4','D4:E4','G4:H4','J4:K4')) { $dashboard.Range($addr).Interior.Color=10040012; $dashboard.Range($addr).Font.Color=16777215; $dashboard.Range($addr).Font.Bold=$true; $dashboard.Range($addr).HorizontalAlignment=-4108 }
    foreach($addr in @('A5:B6','D5:E6','G5:H6','J5:K6')) { $dashboard.Range($addr).Interior.Color=15921906; $dashboard.Range($addr).Font.Bold=$true; $dashboard.Range($addr).Font.Size=20; $dashboard.Range($addr).HorizontalAlignment=-4108; $dashboard.Range($addr).VerticalAlignment=-4108 }
    $dashboard.Range('A8:D8').Merge(); $dashboard.Range('A8').Value2='Корреляция Пирсона'
    $dashboard.Range('A9:C9').Value2=@('Показатель','Коэффициент r','Интерпретация')
    $dashboard.Range('A10').Value2='Запросы ↔ все лиды'; $dashboard.Range('A11').Value2='Запросы ↔ качественные лиды'
    $dashboard.Range('B10').Formula="=CORREL('Недельная сводка'!F${firstDataRow}:F${lastDataRow},'Недельная сводка'!D${firstDataRow}:D${lastDataRow})"
    $dashboard.Range('B11').Formula="=CORREL('Недельная сводка'!F${firstDataRow}:F${lastDataRow},'Недельная сводка'!E${firstDataRow}:E${lastDataRow})"
    $dashboard.Range('C10').Formula='=IF(ABS(B10)<0.3,"Слабая",IF(ABS(B10)<0.7,"Умеренная","Сильная"))'
    $dashboard.Range('C11').Formula='=IF(ABS(B11)<0.3,"Слабая",IF(ABS(B11)<0.7,"Умеренная","Сильная"))'
    $dashboard.Range('B10:B11').NumberFormatLocal='0,000'
    $dashboard.Range('A8:D8').Interior.Color=10040012; $dashboard.Range('A8:D8').Font.Color=16777215; $dashboard.Range('A8:D8').Font.Bold=$true
    $dashboard.Range('A9:C11').Borders.LineStyle=1; $dashboard.Range('A9:C9').Interior.Color=15132390; $dashboard.Range('A9:C9').Font.Bold=$true

    $chartObj = $dashboard.ChartObjects().Add(20, 245, 850, 430)
    $chart = $chartObj.Chart; $chart.ChartType = -4169; $chart.HasTitle=$true; $chart.ChartTitle.Text='Корреляция недельного спроса и лидов'
    $series1 = $chart.SeriesCollection().NewSeries(); $series1.Name='Все лиды'; $series1.XValues=$summary.Range("F${firstDataRow}:F${lastDataRow}"); $series1.Values=$summary.Range("D${firstDataRow}:D${lastDataRow}")
    $series1.MarkerStyle=8; $series1.MarkerSize=5; $series1.MarkerForegroundColor=10040012; $series1.MarkerBackgroundColor=10040012
    [void]$series1.Trendlines().Add(-4132); $series1.Trendlines().Item(1).DisplayRSquared=$true
    $series2 = $chart.SeriesCollection().NewSeries(); $series2.Name='Качественные лиды'; $series2.XValues=$summary.Range("F${firstDataRow}:F${lastDataRow}"); $series2.Values=$summary.Range("E${firstDataRow}:E${lastDataRow}")
    $series2.MarkerStyle=8; $series2.MarkerSize=4; $series2.MarkerForegroundColor=5287936; $series2.MarkerBackgroundColor=5287936
    $chart.HasLegend=$true; $chart.Legend.Position=-4107
    $chart.Axes(1).HasTitle=$true; $chart.Axes(1).AxisTitle.Text='Запросы Wordstat за неделю'
    $chart.Axes(2).HasTitle=$true; $chart.Axes(2).AxisTitle.Text='Количество лидов за неделю'
    $dashboard.Columns('A:L').ColumnWidth=13; $dashboard.Columns('A').ColumnWidth=25; $dashboard.Columns('C').ColumnWidth=18; $dashboard.Rows('1:2').RowHeight=27
    $dashboard.Range('A13:L14').Merge(); $dashboard.Range('A13').Value2='Примечание: последняя неделя лидов 13–19.07.2026 исключена, так как соответствующего периода нет в выгрузке Wordstat.'
    $dashboard.Range('A13:L14').WrapText=$true; $dashboard.Range('A13:L14').Interior.Color=15794160; $dashboard.Range('A13:L14').Font.Color=5460819
    $dashboard.Activate(); $excel.ActiveWindow.DisplayGridlines=$false; $excel.ActiveWindow.Zoom=90

    $excel.CalculateFull()
    $workbook.SaveAs($outputPath, 51)
    $workbook.Close($true)
    $excel.Quit()
    Write-Output $outputPath
}
finally {
    if ($workbook) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook) } catch {} }
    if ($excel) { try { [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) } catch {} }
    [gc]::Collect(); [gc]::WaitForPendingFinalizers()
}
