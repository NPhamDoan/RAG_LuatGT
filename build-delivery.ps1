<#
.SYNOPSIS
    Dung nhanh giao hang (delivery/*) gop cac phase duoc chon, tu trunk `main`.

.DESCRIPTION
    Theo kien truc module (KB muc 13): moi phase la 1 nhanh feature chi THEM file.
    Script nay tao nhanh delivery moi tu main, merge cac nhanh phase duoc chon (merge
    sach vi file roi nhau), cap nhat manifest trong backend/.env (RETRIEVAL_STRATEGY /
    QUERY_STEPS / INDEX_STEPS) de bat dung phase, va tuy chon tag + push.

    Phase 1 (core) luon nam san trong main. Chi can chon them phase 2..5.

.PARAMETER Phases
    Danh sach phase muon kem, phan tach boi dau phay hoac khoang trang. Vd: "2,4" hoac "2 4".
    Bo trong = chi Phase 1 (ban core thuan tu main).

.PARAMETER Tag
    Tao git tag `delivery-<combo>` tren nhanh delivery.

.PARAMETER Push
    Push nhanh delivery (va tag neu co) len origin.

.PARAMETER Force
    Neu nhanh delivery da ton tai (local) thi xoa va dung lai.

.EXAMPLE
    .\build-delivery.ps1 -Phases "2,4"
    .\build-delivery.ps1 -Phases 2 -Tag
    .\build-delivery.ps1 -Phases "2,4" -Tag -Push -Force
#>
[CmdletBinding()]
param(
    [string]$Phases = "",
    [switch]$Tag,
    [switch]$Push,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# --- Ban do phase: so phase -> nhanh + manifest ------------------------------
# Them phase moi (3,5...) = them 1 muc o day khi nhanh feature da ton tai.
$PhaseConfig = @{
    "2" = @{
        Branch    = "feature/phase-2-hybrid"
        Desc      = "Hybrid search (BM25 + RRF)"
        Retrieval = "hybrid"      # dat RETRIEVAL_STRATEGY
        QueryStep = ""            # them vao QUERY_STEPS
        IndexStep = ""            # them vao INDEX_STEPS
    }
    "4" = @{
        Branch    = "feature/phase-4-enrich"
        Desc      = "Enrich chunk luc index"
        Retrieval = ""
        QueryStep = ""
        IndexStep = "enrich"
    }
    "3" = @{
        Branch    = "feature/phase-3-normalize"
        Desc      = "Normalize cau khong dau"
        Retrieval = ""
        QueryStep = "normalize"
        IndexStep = ""
    }
    # "5" = @{ Branch = "feature/phase-5-ux";        Desc = "UX (auth, toan van...)";  Retrieval = ""; QueryStep = "help_intent"; IndexStep = "" }
}

$TrunkBranch = "main"
$EnvFile     = "backend/.env"
$EnvExample  = "backend/.env.example"

# --- Helper ------------------------------------------------------------------
function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "Lenh git that bai: git $($GitArgs -join ' ')" }
}

function Test-GitClean {
    $status = & git status --porcelain
    return [string]::IsNullOrWhiteSpace($status)
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

if (-not (Test-GitClean)) {
    throw "Working tree chua sach. Commit/stash thay doi truoc khi dung delivery."
}

# --- Parse danh sach phase ---------------------------------------------------
$selected = @()
if (-not [string]::IsNullOrWhiteSpace($Phases)) {
    $selected = $Phases -split '[,\s]+' | Where-Object { $_ -ne "" } | Sort-Object -Unique
}

foreach ($p in $selected) {
    if (-not $PhaseConfig.ContainsKey($p)) {
        throw "Phase '$p' chua co cau hinh/nhanh. Cac phase ho tro: $($PhaseConfig.Keys -join ', ')"
    }
}

$combo = (@("1") + $selected) -join "-"     # Phase 1 luon co (trong main)
$deliveryBranch = "delivery/$combo"

$phaseListStr = "1 (core, tu main)"
if ($selected) { $phaseListStr += ", " + ($selected -join ", ") }

Write-Host ""
Write-Host "=== Dung delivery: $deliveryBranch ===" -ForegroundColor Cyan
Write-Host "Phase kem theo: $phaseListStr"

# --- Dong bo + kiem tra nhanh phase ton tai ----------------------------------
Write-Host "-> Fetch origin..." -ForegroundColor DarkGray
Invoke-Git fetch origin --prune

foreach ($p in $selected) {
    $branch = $PhaseConfig[$p].Branch
    & git rev-parse --verify --quiet "origin/$branch" *> $null
    if ($LASTEXITCODE -ne 0) { throw "Khong tim thay nhanh 'origin/$branch' cho phase $p." }
}

# --- Cap nhat main moi nhat --------------------------------------------------
Write-Host "-> Cap nhat $TrunkBranch..." -ForegroundColor DarkGray
Invoke-Git checkout $TrunkBranch
Invoke-Git pull --ff-only origin $TrunkBranch

# --- Tao nhanh delivery (fresh) ----------------------------------------------
$exists = & git rev-parse --verify --quiet "refs/heads/$deliveryBranch"
if ($exists) {
    if (-not $Force) { throw "Nhanh '$deliveryBranch' da ton tai. Dung -Force de dung lai." }
    Write-Host "-> Xoa nhanh cu $deliveryBranch (-Force)..." -ForegroundColor Yellow
    Invoke-Git branch -D $deliveryBranch
}
Write-Host "-> Tao $deliveryBranch tu $TrunkBranch..." -ForegroundColor DarkGray
Invoke-Git checkout -b $deliveryBranch

# --- Merge tung phase --------------------------------------------------------
foreach ($p in $selected) {
    $branch = $PhaseConfig[$p].Branch
    Write-Host "-> Merge phase $p ($branch)..." -ForegroundColor DarkGray
    try {
        Invoke-Git merge --no-edit "origin/$branch"
    }
    catch {
        & git merge --abort 2>$null
        throw "Merge phase $p ($branch) bi xung dot. Da abort. Kiem tra lai nhanh phase."
    }
}

# --- Tinh manifest -----------------------------------------------------------
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

# --- Ghi manifest vao backend/.env (giu nguyen cac key khac nhu API key) -----
if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "-> Chua co $EnvFile, tao tu $EnvExample (nho dien API key)." -ForegroundColor Yellow
        Copy-Item $EnvExample $EnvFile
    }
    else {
        New-Item -ItemType File -Path $EnvFile | Out-Null
    }
}
Set-EnvKey -Path $EnvFile -Key "RETRIEVAL_STRATEGY" -Value $retrieval
Set-EnvKey -Path $EnvFile -Key "QUERY_STEPS"        -Value $queryStepsCsv
Set-EnvKey -Path $EnvFile -Key "INDEX_STEPS"        -Value $indexStepsCsv

# --- Tag (tuy chon) ----------------------------------------------------------
if ($Tag) {
    $tagName = "delivery-$combo"
    & git tag -f $tagName | Out-Null
    Write-Host "-> Da tao tag $tagName" -ForegroundColor DarkGray
}

# --- Push (tuy chon) ---------------------------------------------------------
if ($Push) {
    Write-Host "-> Push $deliveryBranch..." -ForegroundColor DarkGray
    Invoke-Git push -u origin $deliveryBranch
    if ($Tag) { Invoke-Git push -f origin "delivery-$combo" }
}

# --- Tom tat -----------------------------------------------------------------
Write-Host ""
Write-Host "[OK] Xong delivery: $deliveryBranch" -ForegroundColor Green
Write-Host "  Manifest (backend/.env):"
Write-Host "    RETRIEVAL_STRATEGY = $retrieval"
Write-Host "    QUERY_STEPS        = '$queryStepsCsv'"
Write-Host "    INDEX_STEPS        = '$indexStepsCsv'"
Write-Host ""
Write-Host "  Buoc tiep:"
Write-Host "    1. Kiem tra backend/.env da co GROQ API key."
Write-Host "    2. Restart backend de ap manifest."
Write-Host "    3. (tuy chon) chay test: cd backend; .\.venv\Scripts\python.exe -m pytest"
if (-not $Push) { Write-Host "    4. Push thu cong neu can: git push -u origin $deliveryBranch" }
Write-Host ""
