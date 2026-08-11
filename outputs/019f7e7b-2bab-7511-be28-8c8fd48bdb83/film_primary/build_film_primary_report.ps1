$ErrorActionPreference = 'Stop'

$templatePath='C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\Левша_пленка_лиды_Wordstat_и_динамика.xlsx'
$leadPath='C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\film_primary\film_primary_leads.csv'
$outputPath='C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\film_primary\Левша_Пленка_только_первичные_лиды.xlsx'
$scatterPreview='C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\film_primary\film_primary_correlation.png'
$wavesPreview='C:\Users\User\YandexDisk\HyperCRM\outputs\019f7e7b-2bab-7511-be28-8c8fd48bdb83\film_primary\film_primary_waves.png'
$culture=[Globalization.CultureInfo]::GetCultureInfo('ru-RU')

$leadRows=Import-Csv -LiteralPath $leadPath -Delimiter ';' -Encoding UTF8
$headers=@($leadRows[0].PSObject.Properties.Name)
$dateCol=[array]::IndexOf($headers,'Дата создания')+1
$stageCol=[array]::IndexOf($headers,'Стадия')+1

$excel=$null; $workbook=$null
try{
    $excel=New-Object -ComObject Excel.Application
    $excel.Visible=$false; $excel.DisplayAlerts=$false; $excel.ScreenUpdating=$false
    $workbook=$excel.Workbooks.Open($templatePath,0,$true)
    $dashboard=$workbook.Worksheets.Item('Дашборд')
    $summary=$workbook.Worksheets.Item('Недельная сводка')
    $leads=$workbook.Worksheets.Item('Исходник — лиды')
    $dynamics=$workbook.Worksheets.Item('Динамика')

    while($leads.ListObjects.Count -gt 0){$leads.ListObjects.Item(1).Delete()}
    $leads.Cells.Clear()
    $matrix=New-Object 'object[,]' ($leadRows.Count+1),$headers.Count
    for($c=0;$c -lt $headers.Count;$c++){$matrix[0,$c]=$headers[$c]}
    for($r=0;$r -lt $leadRows.Count;$r++){
        for($c=0;$c -lt $headers.Count;$c++){
            $value=$leadRows[$r].($headers[$c])
            if(($c+1)-eq $dateCol){$matrix[($r+1),$c]=[datetime]::Parse($value,$culture).ToOADate()}
            else{$matrix[($r+1),$c]=$value}
        }
    }
    $leadRange=$leads.Range($leads.Cells(1,1),$leads.Cells($leadRows.Count+1,$headers.Count))
    $leadRange.Value2=$matrix
    $leads.Range("H2:H$($leadRows.Count+1)").NumberFormatLocal='ДД.ММ.ГГГГ чч:мм'
    $table=$leads.ListObjects.Add(1,$leadRange,$null,1); $table.Name='tblFilmPrimaryLeads'; $table.TableStyle='TableStyleMedium2'
    $leads.Columns.AutoFit()|Out-Null
    for($c=1;$c -le $headers.Count;$c++){if($leads.Columns.Item($c).ColumnWidth -gt 28){$leads.Columns.Item($c).ColumnWidth=28}}

    $firstRow=5; $lastRow=241; $lastLeadRow=$leadRows.Count+1
    $summary.Range("D${firstRow}:D${lastRow}").FormulaR1C1="=COUNTIFS('Исходник — лиды'!R2C${dateCol}:R${lastLeadRow}C${dateCol},`">=`"&RC[-3],'Исходник — лиды'!R2C${dateCol}:R${lastLeadRow}C${dateCol},`"<`"&RC[-2]+1)"
    $summary.Range("E${firstRow}:E${lastRow}").FormulaR1C1="=COUNTIFS('Исходник — лиды'!R2C${dateCol}:R${lastLeadRow}C${dateCol},`">=`"&RC[-4],'Исходник — лиды'!R2C${dateCol}:R${lastLeadRow}C${dateCol},`"<`"&RC[-3]+1,'Исходник — лиды'!R2C${stageCol}:R${lastLeadRow}C${stageCol},`"Качественный лид`")"
    $summary.Range("G${firstRow}:G${lastRow}").FormulaR1C1='=IFERROR(RC[-2]/RC[-3],0)'
    $summary.Range('A1').Value2='Левша — плёнка: только первичные лиды по неделям'
    $summary.Range('A2').Value2='Выборка CRM содержит только первичные лиды. Периоды заданы выгрузкой Wordstat.'

    $dashboard.Range('A1').Value2='Левша — плёнка: первичный спрос и лиды'
    $dashboard.Range('A13').Value2='Примечание: используются только первичные лиды; обращения после 12.07.2026 исключены из недельного анализа.'
    $scatter=$dashboard.ChartObjects().Item(1).Chart
    $scatter.ChartTitle.Text='Плёнка: корреляция спроса и первичных лидов'
    $scatter.SeriesCollection().Item(1).Name='Все первичные лиды'
    $scatter.SeriesCollection().Item(2).Name='Качественные первичные лиды'

    $dynamics.Range('A1').Value2='Плёнка — недельная динамика первичных лидов и спроса'
    $wave=$dynamics.ChartObjects().Item(1).Chart
    $wave.ChartTitle.Text='Плёнка: первичные лиды, качественные лиды и запросы Wordstat'
    $wave.SeriesCollection().Item(1).Name='Первичные лиды'
    $wave.SeriesCollection().Item(2).Name='Качественные первичные лиды'

    $excel.CalculateFull()
    $workbook.SaveAs($outputPath,51)
    [void]$scatter.Export($scatterPreview,'PNG'); [void]$wave.Export($wavesPreview,'PNG')
    $workbook.Close($true); $excel.Quit()
    Write-Output $outputPath
}
finally{
    if($workbook){try{$workbook.Close($false)}catch{}}
    if($excel){try{$excel.Quit()}catch{}}
    foreach($o in @($scatter,$wave,$dynamics,$leads,$summary,$dashboard,$workbook,$excel)){if($o){try{[void][Runtime.InteropServices.Marshal]::ReleaseComObject($o)}catch{}}}
    [gc]::Collect(); [gc]::WaitForPendingFinalizers()
}
