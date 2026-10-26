# scan_data.ps1  -  Data inventory for AgriWater project
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\scan_data.ps1 -Path "D:\AgriWaterData"
# Output: console + data_inventory.txt + data_inventory.csv (on Desktop by default)

param(
    [string]$Path = (Get-Location).Path,
    [string]$OutDir = [Environment]::GetFolderPath('Desktop')
)

Add-Type -AssemblyName System.IO.Compression.FileSystem
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$sb = New-Object System.Text.StringBuilder
function Log($t) { Write-Host $t; [void]$sb.AppendLine($t) }

function Get-LineCount($f) {
    $n = 0
    foreach ($l in [System.IO.File]::ReadLines($f)) { $n++ }
    return $n
}

function Get-Delimiter($line) {
    $cands = @(',', ';', "`t", '|')
    $best = ','; $max = -1
    foreach ($c in $cands) {
        $cnt = ($line.ToCharArray() | Where-Object { $_ -eq $c[0] }).Count
        if ($cnt -gt $max) { $max = $cnt; $best = $c }
    }
    return $best
}

function Scan-Text($f) {
    $head = @(Get-Content -LiteralPath $f -TotalCount 80 -Encoding UTF8)
    if ($head.Count -eq 0) { Log "   (empty file)"; return 0 }
    $hdrIdx = 0
    $endIdx = -1
    for ($i = 0; $i -lt $head.Count; $i++) {
        if ($head[$i] -match 'END HEADER') { $endIdx = $i; break }
    }
    if ($endIdx -ge 0) {
        $hdrIdx = $endIdx + 1
        Log "   NASA POWER-style header detected ($($endIdx + 1) metadata lines)"
    } else {
        while ($hdrIdx -lt $head.Count -and ($head[$hdrIdx].Trim() -eq '' -or $head[$hdrIdx].StartsWith('#'))) { $hdrIdx++ }
    }
    if ($hdrIdx -ge $head.Count) { Log "   (could not find header row)"; return 0 }
    $delim = Get-Delimiter $head[$hdrIdx]
    $cols = $head[$hdrIdx].Split($delim)
    $total = Get-LineCount $f
    $rows = $total - $hdrIdx - 1
    Log "   Delimiter : '$delim'"
    Log "   Rows      : $rows"
    Log "   Columns   : $($cols.Count)"
    Log "   Names     : $($cols -join ' | ')"
    for ($k = 1; $k -le 2; $k++) {
        if (($hdrIdx + $k) -lt $head.Count) { Log "   Sample $k  : $($head[$hdrIdx + $k])" }
    }
    return $rows
}

function Scan-Xlsx($f) {
    $zip = [IO.Compression.ZipFile]::OpenRead($f)
    $totalRows = 0
    try {
        $e = $zip.GetEntry('xl/workbook.xml')
        $r = New-Object IO.StreamReader($e.Open()); [xml]$x = $r.ReadToEnd(); $r.Close()
        $names = @($x.workbook.sheets.sheet | ForEach-Object { $_.name })

        $ss = New-Object System.Collections.Generic.List[string]
        $se = $zip.GetEntry('xl/sharedStrings.xml')
        if ($se) {
            $rd = [Xml.XmlReader]::Create($se.Open())
            while (-not $rd.EOF -and $ss.Count -lt 2000) {
                if ($rd.NodeType -eq 'Element' -and $rd.Name -eq 'si') {
                    $ss.Add(($rd.ReadInnerXml() -replace '<[^>]+>', ''))
                } else { [void]$rd.Read() }
            }
            $rd.Close()
        }

        for ($i = 0; $i -lt $names.Count; $i++) {
            $we = $zip.GetEntry("xl/worksheets/sheet$($i + 1).xml")
            if (-not $we) { Log "   Sheet '$($names[$i])': (xml not found)"; continue }
            $rd = [Xml.XmlReader]::Create($we.Open())
            $dim = ''; $hdr = @()
            while ($rd.Read()) {
                if ($rd.NodeType -eq 'Element') {
                    if ($rd.Name -eq 'dimension') { $dim = $rd.GetAttribute('ref') }
                    elseif ($rd.Name -eq 'row') {
                        $rowXml = $rd.ReadOuterXml()
                        foreach ($m in [regex]::Matches($rowXml, '<c\b[^>]*?(/>|>.*?</c>)')) {
                            $cx = $m.Value
                            $v = [regex]::Match($cx, '<v>(.*?)</v>').Groups[1].Value
                            if ($cx -match 't="s"' -and $v -ne '') {
                                $idx = [int]$v
                                if ($idx -lt $ss.Count) { $v = $ss[$idx] }
                            }
                            $hdr += $v
                        }
                        break
                    }
                }
            }
            $rd.Close()
            $rowCount = ''
            if ($dim -match ':[A-Z]+(\d+)$') { $rowCount = [int]$Matches[1] - 1; $totalRows += $rowCount }
            Log "   Sheet '$($names[$i])'  range=$dim  approx rows=$rowCount"
            if ($hdr.Count -gt 0) { Log "      Columns: $($hdr -join ' | ')" }
        }
    } finally { $zip.Dispose() }
    return $totalRows
}

function Scan-Json($f, $sizeMB) {
    if ($sizeMB -gt 50) { Log "   (JSON too large to parse, skipped)"; return 0 }
    $obj = Get-Content -LiteralPath $f -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($obj -is [System.Array]) {
        Log "   Array of $($obj.Count) items"
        if ($obj.Count -gt 0) { Log "   Keys: $(($obj[0].PSObject.Properties.Name) -join ' | ')" }
        return $obj.Count
    } else {
        Log "   Top-level keys: $(($obj.PSObject.Properties.Name) -join ' | ')"
        return 0
    }
}

# ---------------- main ----------------
$files = Get-ChildItem -LiteralPath $Path -Recurse -File -ErrorAction SilentlyContinue
Log "=== DATA INVENTORY ==="
Log "Folder : $Path"
Log "Files  : $($files.Count)"
Log "Date   : $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Log ""
Log "--- Extensions summary ---"
$files | Group-Object { $_.Extension.ToLower() } | Sort-Object Count -Descending | ForEach-Object {
    $mb = [math]::Round((($_.Group | Measure-Object Length -Sum).Sum / 1MB), 2)
    Log ("{0,-10} files={1,-5} size={2} MB" -f $_.Name, $_.Count, $mb)
}
Log ""
Log "--- Details per file ---"

$summary = @()
foreach ($f in $files) {
    $ext = $f.Extension.ToLower()
    $mb = [math]::Round($f.Length / 1MB, 3)
    $rel = $f.FullName.Substring($Path.Length).TrimStart('\')
    Log ""
    Log ">> $rel   [$ext, $mb MB]"
    $rows = ''
    try {
        switch ($ext) {
            { $_ -in '.csv', '.tsv', '.txt', '.dat' } { $rows = Scan-Text $f.FullName }
            { $_ -in '.xlsx', '.xlsm' }               { $rows = Scan-Xlsx $f.FullName }
            '.json'                                    { $rows = Scan-Json $f.FullName $mb }
            default                                    { Log "   (not parsed - size only; tell me what this file is)" }
        }
    } catch {
        Log "   ERROR reading file: $($_.Exception.Message)"
    }
    $summary += [pscustomobject]@{ File = $rel; Ext = $ext; SizeMB = $mb; Rows = $rows }
}

Log ""
Log "--- Summary table ---"
$tbl = ($summary | Format-Table -AutoSize | Out-String)
Log $tbl

$txt = Join-Path $OutDir 'data_inventory.txt'
$csv = Join-Path $OutDir 'data_inventory.csv'
$sb.ToString() | Out-File -FilePath $txt -Encoding UTF8
$summary | Export-Csv -Path $csv -NoTypeInformation -Encoding UTF8
Write-Host "`nSaved: $txt"
Write-Host "Saved: $csv"
