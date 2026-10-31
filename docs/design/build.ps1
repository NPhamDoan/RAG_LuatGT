# Build tai lieu thiet ke: render lai PNG tu .drawio roi sinh file Word (.docx).
#
# Cach dung (chay trong thu muc docs/design):
#   .\build.ps1                 # render PNG + build docx
#   .\build.ps1 -SkipRender     # bo qua render, chi build docx
#   .\build.ps1 -SkipDocx       # chi render PNG
#
# Yeu cau:
#   - draw.io desktop (de render PNG)  -> winget install JGraph.Draw
#   - Python + cac goi trong generate-docx.py (python-docx, Pillow)

param(
    [switch]$SkipRender,
    [switch]$SkipDocx
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 1) Render .drawio -> PNG
if (-not $SkipRender) {
    $renderScript = Join-Path $here "diagrams\render.ps1"
    if (-not (Test-Path $renderScript)) {
        throw "Khong tim thay diagrams\render.ps1"
    }
    Write-Host "==> Render diagram sang PNG..." -ForegroundColor Cyan
    & powershell -NoProfile -ExecutionPolicy Bypass -File $renderScript
    if ($LASTEXITCODE -ne 0) { throw "Render PNG that bai (exit $LASTEXITCODE)" }
} else {
    Write-Host "==> Bo qua buoc render PNG (-SkipRender)." -ForegroundColor Yellow
}

# 2) Build Markdown -> Word
if (-not $SkipDocx) {
    $genScript = Join-Path $here "generate-docx.py"
    if (-not (Test-Path $genScript)) {
        throw "Khong tim thay generate-docx.py"
    }

    # Tim python: PATH -> py launcher
    $python = $null
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $python = $cmd.Source }
    if (-not $python) {
        $cmd = Get-Command py -ErrorAction SilentlyContinue
        if ($cmd) { $python = $cmd.Source }
    }
    if (-not $python) { throw "Khong tim thay Python. Cai Python roi chay lai." }

    Write-Host "==> Build tai lieu Word (.docx)..." -ForegroundColor Cyan
    Push-Location $here
    try {
        # Build docx, bo qua bia tu sinh (se ghep bia tu Bia.docx)
        $coverFile = Join-Path $here "Bia.docx"
        if (Test-Path $coverFile) {
            & $python "generate-docx.py" "--skip-cover"
            if ($LASTEXITCODE -ne 0) { throw "Build docx that bai (exit $LASTEXITCODE)" }

            Write-Host "==> Ghep trang bia tu Bia.docx..." -ForegroundColor Cyan
            & $python "prepend-cover.py"
            if ($LASTEXITCODE -ne 0) { throw "Ghep trang bia that bai (exit $LASTEXITCODE)" }
        } else {
            Write-Host "    (Khong thay Bia.docx -> dung bia tu sinh tu Markdown.)" -ForegroundColor Yellow
            & $python "generate-docx.py"
            if ($LASTEXITCODE -ne 0) { throw "Build docx that bai (exit $LASTEXITCODE)" }
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "==> Bo qua buoc build docx (-SkipDocx)." -ForegroundColor Yellow
}

Write-Host "==> Hoan tat." -ForegroundColor Green
Write-Host "    PNG : $here\diagrams\png"
Write-Host "    Docx: $here\tai-lieu-thiet-ke-he-thong.docx"
Write-Host "    (Mo file Word, nhan Ctrl+A roi F9 de cap nhat muc luc va danh muc.)"
