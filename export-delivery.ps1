<#
.SYNOPSIS
    Gom SOURCE cua cac phase duoc chon vao mot FOLDER delivery (goi giao hang de zip/gui khach).

.DESCRIPTION
    Khac voi build-delivery.ps1 (tao NHANH git), script nay xuat cay source ra FOLDER.
    Dung git worktree + git archive: chi lay file tracked (KHONG kem .git, .venv,
    node_modules, data/chroma, __pycache__, dist, .env). Tu tao backend/.env manifest
    (RETRIEVAL_STRATEGY / QUERY_STEPS / INDEX_STEPS) cho dung phase.
    KHONG dung toi nhanh / working tree hien tai (lam viec tren worktree tam).

    Phase 1 (core) luon co san trong main. Chi can chon them phase 2..5.

.PARAMETER Phases
    Danh sach phase, phan tach boi phay/khoang trang. Vd: "2,4". Bo trong = chi Phase 1.

.PARAMETER Output
    Folder dich. Mac dinh: delivery\<combo> (vd delivery\1-2-4).

.PARAMETER Zip
    Nen folder output thanh <Output>.zip.

.PARAMETER Force
    Ghi de neu folder output da ton tai.

.EXAMPLE
    .\export-delivery.ps1 -Phases "2,4"
    .\export-delivery.ps1 -Phases 2 -Zip
    .\export-delivery.ps1 -Phases "2,4" -Output "C:\giao\ban_A" -Zip -Force
#>
[CmdletBinding()]
param(
    [string]$Phases = "",
    [string]$Output = "",
    [switch]$Zip,
    [switch]$Force,
    [switch]$LinkDeps
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # tat progress-bar Expand-Archive cho gon

# --- Ban do phase: so phase -> nhanh + manifest ------------------------------
$PhaseConfig = @{
    "2" = @{ Branch = "feature/phase-2-hybrid"; Desc = "Hybrid search (BM25 + RRF)"; Retrieval = "hybrid"; QueryStep = ""; IndexStep = "" }
    "4" = @{ Branch = "feature/phase-4-enrich"; Desc = "Enrich chunk luc index";     Retrieval = "";       QueryStep = ""; IndexStep = "enrich" }
    "3" = @{ Branch = "feature/phase-3-normalize"; Desc = "Normalize cau khong dau"; Retrieval = ""; QueryStep = "normalize"; IndexStep = "" }
    # "5" = @{ Branch = "feature/phase-5-ux";        Desc = "UX (auth, toan van...)";  Retrieval = ""; QueryStep = "help_intent"; IndexStep = "" }
}

$TrunkBranch = "main"
$EnvExampleRel = "backend/.env.example"
$EnvFileRel    = "backend/.env"

# --- Helper ------------------------------------------------------------------
function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Lenh git that bai: git $($GitArgs -join ' ')" }
}

function Remove-DirSafe([string]$Path) {
    # Xoa thu muc AN TOAN: dung `rmdir /s /q` (cmd) - KHONG di theo junction nen khong
    # xoa nham noi dung venv/node_modules goc (Remove-Item -Recurse tren PS5.1 co the follow).
    if (Test-Path $Path) { cmd /c rmdir /s /q "$Path" 2>$null }
}

function Test-GitClean {
    return [string]::IsNullOrWhiteSpace((& git status --porcelain))
}

function Set-EnvKey {
    param([string]$Path, [string]$Key, [string]$Value)
    $lines = @()
    if (Test-Path $Path) { $lines = @(Get-Content -Path $Path) }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*$([regex]::Escape($Key))\s*=") { $found = $true; "$Key=$Value" }
        else { $line }
    }
    if (-not $found) { $out = @($out) + "$Key=$Value" }
    Set-Content -Path $Path -Value $out -Encoding UTF8
}

# --- Kiem tra tien de --------------------------------------------------------
& git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) { throw "Khong phai git repo. Chay script o goc du an." }
if (-not (Test-GitClean)) { throw "Working tree chua sach. Commit/stash truoc khi xuat delivery." }

# --- Parse phase -------------------------------------------------------------
$selected = @()
if (-not [string]::IsNullOrWhiteSpace($Phases)) {
    $selected = $Phases -split '[,\s]+' | Where-Object { $_ -ne "" } | Sort-Object -Unique
}
foreach ($p in $selected) {
    if (-not $PhaseConfig.ContainsKey($p)) {
        throw "Phase '$p' chua co cau hinh/nhanh. Ho tro: $($PhaseConfig.Keys -join ', ')"
    }
}

$combo = (@("1") + $selected) -join "-"
if ([string]::IsNullOrWhiteSpace($Output)) { $Output = Join-Path "delivery" $combo }

$phaseListStr = "1 (core)"
if ($selected) { $phaseListStr += ", " + ($selected -join ", ") }

Write-Host ""
Write-Host "=== Xuat delivery folder: $Output ===" -ForegroundColor Cyan
Write-Host "Phase: $phaseListStr"

# --- Dong bo + kiem tra nhanh phase ------------------------------------------
Invoke-Git fetch origin --prune
foreach ($p in $selected) {
    $branch = $PhaseConfig[$p].Branch
    & git rev-parse --verify --quiet "origin/$branch" *> $null
    if ($LASTEXITCODE -ne 0) { throw "Khong tim thay nhanh 'origin/$branch' cho phase $p." }
}

# --- Chuan bi folder output --------------------------------------------------
if (Test-Path $Output) {
    if (-not $Force) { throw "Folder '$Output' da ton tai. Dung -Force de ghi de." }
    Remove-DirSafe $Output
}
New-Item -ItemType Directory -Path $Output -Force | Out-Null

# --- Worktree tam + merge phase + archive ------------------------------------
$tmpWt  = Join-Path ([System.IO.Path]::GetTempPath()) ("ragdlv_" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8))
$tmpZip = Join-Path ([System.IO.Path]::GetTempPath()) ("ragdlv_" + [System.Guid]::NewGuid().ToString("N").Substring(0, 8) + ".zip")

try {
    Write-Host "-> Tao worktree tam tu origin/$TrunkBranch..." -ForegroundColor DarkGray
    Invoke-Git worktree add --detach $tmpWt "origin/$TrunkBranch"

    foreach ($p in $selected) {
        $branch = $PhaseConfig[$p].Branch
        Write-Host "-> Merge phase $p ($branch)..." -ForegroundColor DarkGray
        & git -C $tmpWt merge --no-edit "origin/$branch"
        if ($LASTEXITCODE -ne 0) {
            & git -C $tmpWt merge --abort 2>$null
            throw "Merge phase $p ($branch) bi xung dot."
        }
    }

    Write-Host "-> Archive source (chi file tracked) -> $Output..." -ForegroundColor DarkGray
    & git -C $tmpWt archive --format=zip -o $tmpZip HEAD
    if ($LASTEXITCODE -ne 0) { throw "git archive that bai." }
    Expand-Archive -Path $tmpZip -DestinationPath $Output -Force
}
finally {
    # Buoc don dep - KHONG duoc nem loi (du archive da xong). Windows hay khoa file tam
    # thoi (Defender/handle chua nha) -> retry + fallback rmdir. Tam ha EAP de native
    # stderr khong bien thanh terminating error.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    try {
        if (Test-Path $tmpZip) { Remove-Item -Force $tmpZip -ErrorAction SilentlyContinue }

        if (Test-Path $tmpWt) {
            $removed = $false
            for ($i = 0; $i -lt 6; $i++) {
                git worktree remove --force $tmpWt 2>&1 | Out-Null
                if (-not (Test-Path $tmpWt)) { $removed = $true; break }
                Start-Sleep -Milliseconds 500
                Remove-DirSafe $tmpWt            # fallback: cmd rmdir /s /q
                if (-not (Test-Path $tmpWt)) { $removed = $true; break }
            }
            if (-not $removed) {
                Write-Host "-> Canh bao: chua xoa duoc worktree tam '$tmpWt' (Windows dang khoa file)." -ForegroundColor Yellow
                Write-Host "   Khong sao - delivery da xuat xong. Don sau bang: git worktree prune" -ForegroundColor Yellow
            }
        }
        git worktree prune 2>&1 | Out-Null
    }
    finally {
        $ErrorActionPreference = $prevEAP
    }
}

# --- Tinh manifest + ghi .env trong output -----------------------------------
$retrieval  = "vector"
$querySteps = @()
$indexSteps = @()
foreach ($p in $selected) {
    $cfg = $PhaseConfig[$p]
    if ($cfg.Retrieval) { $retrieval = $cfg.Retrieval }
    if ($cfg.QueryStep) { $querySteps += $cfg.QueryStep }
    if ($cfg.IndexStep) { $indexSteps += $cfg.IndexStep }
}
$queryStepsCsv = ($querySteps | Sort-Object -Unique) -join ","
$indexStepsCsv = ($indexSteps | Sort-Object -Unique) -join ","

$outEnv        = Join-Path $Output $EnvFileRel
$outEnvExample = Join-Path $Output $EnvExampleRel
if (Test-Path $outEnvExample) { Copy-Item $outEnvExample $outEnv -Force }
else { New-Item -ItemType File -Path $outEnv -Force | Out-Null }
Set-EnvKey -Path $outEnv -Key "RETRIEVAL_STRATEGY" -Value $retrieval
Set-EnvKey -Path $outEnv -Key "QUERY_STEPS"        -Value $queryStepsCsv
Set-EnvKey -Path $outEnv -Key "INDEX_STEPS"        -Value $indexStepsCsv

# Phase 4 (enrich): chen san goi y cau hinh LLM rieng cho enrich (dang comment).
if ($indexSteps -contains "enrich") {
    $enrichHint = @"

# --- Phase 4 enrich: LLM rieng cho buoc lam giau chunk (TUY CHON) ---
# Bo trong = dung LLM synthesis chinh. Bo comment de dung LLM rieng (vd Ollama local
# de do ton/rate-limit Groq khi index nhieu chunk):
# ENRICH_LLM_PROVIDER=ollama
# ENRICH_LLM_MODEL=qwen3:8b
# ENRICH_OLLAMA_BASE_URL=http://localhost:11434
# ENRICH_LLM_TIMEOUT=120
# ENRICH_CONCURRENCY=2        # so chunk enrich dong thoi (Ollama CPU nen 1-2; Groq co the cao hon)
# ENRICH_OLLAMA_THINK=false   # (Ollama) tat suy luan model thinking (qwen3) -> nhanh ~5x
"@
    Add-Content -Path $outEnv -Value $enrichHint -Encoding UTF8
    Write-Host "-> Da chen goi y ENRICH_* vao $EnvFileRel (phase 4)." -ForegroundColor DarkGray
}

# --- Sinh README-DELIVERY.txt (huong dan chay cho nguoi nhan) ----------------
$readme = @"
=== RAG Tra cuu Luat Giao Thong - Goi giao hang ===
Phase kem theo : $phaseListStr
Manifest       : RETRIEVAL_STRATEGY=$retrieval ; QUERY_STEPS=$queryStepsCsv ; INDEX_STEPS=$indexStepsCsv

--- 1. Cai dat (chay 1 lan) ---
- Yeu cau: Python 3.11+ va Node.js 18+ da cai san.
- Chay: setup.bat
  (tao venv backend + pip install + npm install frontend)

--- 2. Cau hinh API key (backend\.env) ---
- Dung Groq (cloud):
    PRIMARY_LLM_PROVIDER=groq
    PRIMARY_LLM_API_KEY=<dien_key_cua_ban>
- Hoac chay LOCAL bang Ollama:
    PRIMARY_LLM_PROVIDER=ollama
    PRIMARY_LLM_MODEL=qwen3:8b
    OLLAMA_BASE_URL=http://localhost:11434
    PRIMARY_LLM_TIMEOUT=120

--- 3. Chay ---
- Chay: run_all.bat   (backend http://localhost:8000 + frontend http://localhost:5173)
- Mo trinh duyet: http://localhost:5173

--- 4. Nap du lieu (lan dau) ---
- Goi nay KHONG kem CSDL vector (data/chroma).
- Vao trang /admin, upload cac file PDF trong thu muc data\seed de dung index.
- Luu y: lan hoi dau tien se cham vi phai nap model embedding (~2GB) vao RAM.

(File nay sinh tu dong boi export-delivery.ps1)
"@
Set-Content -Path (Join-Path $Output "README-DELIVERY.txt") -Value $readme -Encoding UTF8

# --- Nen (tuy chon) ----------------------------------------------------------
if ($Zip) {
    $zipOut = "$Output.zip"
    if (Test-Path $zipOut) { Remove-Item -Force $zipOut }
    Compress-Archive -Path (Join-Path $Output '*') -DestinationPath $zipOut
    Write-Host "-> Da nen: $zipOut" -ForegroundColor DarkGray
}

# --- Tai dung deps qua junction (CHI de TEST LOCAL cho nhanh, KHONG cai lai) -----
# Junction .venv + node_modules tro ve repo goc -> khoi chay setup.bat.
# Luu y: dat SAU buoc -Zip nen file zip van la source-only (khong kem venv nang).
if ($LinkDeps) {
    $masters = @(
        @{ Src = (Join-Path $PSScriptRoot "backend\.venv");         Dst = (Join-Path $Output "backend\.venv") },
        @{ Src = (Join-Path $PSScriptRoot "frontend\node_modules"); Dst = (Join-Path $Output "frontend\node_modules") }
    )
    foreach ($m in $masters) {
        if (-not (Test-Path $m.Src)) {
            Write-Host "-> LinkDeps: bo qua (khong thay $($m.Src) - chay setup.bat o repo goc truoc)." -ForegroundColor Yellow
            continue
        }
        Remove-DirSafe $m.Dst
        New-Item -ItemType Junction -Path $m.Dst -Target $m.Src | Out-Null
        Write-Host "-> Junction: $($m.Dst) -> $($m.Src)" -ForegroundColor DarkGray
    }
    Write-Host "   Da tai dung deps (venv + node_modules) - KHONG can chay setup.bat." -ForegroundColor DarkGray
}

# --- Tom tat -----------------------------------------------------------------
$fileCount = (Get-ChildItem -Recurse -File $Output).Count
Write-Host ""
Write-Host "[OK] Xuat xong: $Output ($fileCount file)" -ForegroundColor Green
Write-Host "  Phase: $phaseListStr"
Write-Host "  Manifest ($EnvFileRel):"
Write-Host "    RETRIEVAL_STRATEGY = $retrieval"
Write-Host "    QUERY_STEPS        = '$queryStepsCsv'"
Write-Host "    INDEX_STEPS        = '$indexStepsCsv'"
Write-Host ""
Write-Host "  Da tao README-DELIVERY.txt (huong dan chay cho nguoi nhan)."
Write-Host "  Luu y: $EnvFileRel dang la placeholder -> dien GROQ/API key that truoc khi chay."
Write-Host ""
