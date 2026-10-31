# Render tất cả file .drawio trong thư mục này sang PNG (docs/design/diagrams/png/).
# Yêu cầu: draw.io desktop đã cài. Dùng --crop --border 20 để PNG không bị cắt nội dung.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $here "png"
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

# Dò draw.io: PATH -> Program Files -> WindowsApps (bản Store)
$drawio = $null
$cmd = Get-Command drawio -ErrorAction SilentlyContinue
if ($cmd) { $drawio = $cmd.Source }
if (-not $drawio) {
  $candidates = @(
    "G:\Program Files\draw.io\draw.io.exe",
    "C:\Program Files\draw.io\draw.io.exe",
    "$env:LOCALAPPDATA\Programs\draw.io\draw.io.exe"
  )
  foreach ($c in $candidates) { if (Test-Path $c) { $drawio = $c; break } }
}
if (-not $drawio) {
  $store = Get-ChildItem "C:\Program Files\WindowsApps\" -Directory -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -like "draw.io.draw.ioDiagrams*" } |
           Sort-Object Name -Descending | Select-Object -First 1
  if ($store) {
    $exe = Join-Path $store.FullName "app\draw.io.exe"
    if (Test-Path $exe) { $drawio = $exe }
  }
}
if (-not $drawio) { throw "Khong tim thay draw.io. Cai: winget install JGraph.Draw" }

Write-Host "draw.io: $drawio"

Get-ChildItem -Path $here -Filter *.drawio | ForEach-Object {
  $in = $_.FullName
  $out = Join-Path $outDir ($_.BaseName + ".png")
  Write-Host "Render $($_.Name) -> png/$($_.BaseName).png"
  
  # Thêm cờ tắt GPU và dọn luồng stderr để chặn log lỗi Chromium
  & $drawio --export --format png --scale 2 --crop --border 20 --disable-gpu --disable-software-rasterizer --no-sandbox --output $out $in 2>$null
}

Write-Host "Xong. PNG o: $outDir"