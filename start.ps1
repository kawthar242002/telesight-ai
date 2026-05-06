# ============================================================
#  TeleSight AI - Demarrage unifie (PowerShell)
#  Lance tout le projet en une seule commande :
#    .\start.ps1
#
#  Options :
#    .\start.ps1 -SkipDocker  -> ne relance pas Docker si deja up
#    .\start.ps1 -SkipTrain   -> ne reentrainera pas les modeles
# ============================================================
param(
    [switch]$SkipDocker,
    [switch]$SkipTrain
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot

# -- Helpers couleurs ---------------------------------------------------------
function Write-Step { param($n, $msg) Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "  [OK] $msg"   -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "  [!!] $msg"   -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "  [X]  $msg"   -ForegroundColor Red }
function Write-Info { param($msg) Write-Host "  --> $msg"    -ForegroundColor Gray }

# -- Banner -------------------------------------------------------------------
Clear-Host
Write-Host ""
Write-Host "  ============================================================" -ForegroundColor Magenta
Write-Host "         TeleSight AI  -  Unified Platform Launcher           " -ForegroundColor Magenta
Write-Host "  ============================================================" -ForegroundColor Magenta
Write-Host ""

# =============================================================================
# ETAPE 0 - Verification et demarrage Ollama
# =============================================================================
Write-Step "0/6" "Verification et demarrage d'Ollama..."

$ollamaRunning = $false
try {
    $resp = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -TimeoutSec 3 -ErrorAction Stop
    Write-OK "Ollama deja actif (v$($resp.version))"
    $ollamaRunning = $true
} catch {
    Write-Warn "Ollama non accessible - tentative de demarrage..."
    $ollamaExe = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollamaExe) {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized -PassThru | Out-Null
        Write-Info "Service Ollama lance, attente 5 secondes..."
        Start-Sleep -Seconds 5
        try {
            $resp = Invoke-RestMethod -Uri "http://localhost:11434/api/version" -TimeoutSec 5
            Write-OK "Ollama demarre avec succes (v$($resp.version))"
            $ollamaRunning = $true
        } catch {
            Write-Err "Impossible de demarrer Ollama ! L'agent RAG fonctionnera sans LLM."
        }
    } else {
        Write-Err "Ollama non installe. Telecharger sur https://ollama.com"
    }
}

# Verifier que le modele tinyllama est disponible
if ($ollamaRunning) {
    Write-Info "Verification du modele tinyllama..."
    $models = & ollama list 2>&1
    if ($models -match "tinyllama") {
        Write-OK "Modele tinyllama present"
    } else {
        Write-Warn "Modele tinyllama absent - telechargement en cours (637 MB)..."
        & ollama pull tinyllama
        Write-OK "Modele tinyllama telecharge"
    }
}

# =============================================================================
# ETAPE 1 - Infrastructure Docker
# =============================================================================
Write-Step "1/6" "Infrastructure Docker (Kafka + PostgreSQL + Redis)..."

if (-not $SkipDocker) {
    try {
        & docker info | Out-Null
    } catch {
        Write-Err "Docker Desktop n'est pas lance. Veuillez le demarrer manuellement."
        Read-Host "Appuyez sur Entree quand Docker est pret"
    }

    Push-Location "$ROOT\partie1_pipeline"
    $running = & docker ps --filter "name=kafka" --format "{{.Names}}" 2>&1
    if ($running -match "kafka") {
        Write-OK "Kafka deja en cours d'execution - pas de redemarrage"
    } else {
        Write-Info "Demarrage des containers..."
        & docker-compose up -d
        Write-Info "Attente 20 secondes pour l'initialisation..."
        Start-Sleep -Seconds 20
        Write-OK "Infrastructure Docker prete"
    }
    Pop-Location
} else {
    Write-Warn "Docker ignore (-SkipDocker)"
}

# =============================================================================
# ETAPE 2 - Preparation des donnees
# =============================================================================
Write-Step "2/6" "Preparation des donnees..."

$dataFile = "$ROOT\data\unified_kpi_with_anomalies.csv"
if (-not (Test-Path $dataFile)) {
    Write-Info "Generation des donnees (premiere fois)..."
    Push-Location "$ROOT\partie1_pipeline"
    & python producer/data_preparation.py
    Pop-Location
    Write-OK "Donnees generees"
} else {
    Write-OK "Donnees deja pretes - etape ignoree"
}

# =============================================================================
# ETAPE 3 - Entrainement ML (seulement si modeles absents)
# =============================================================================
Write-Step "3/6" "Modeles ML..."

$xgbModel = "$ROOT\partie2_ml\models\xgboost_anomaly.pkl"
if (-not (Test-Path $xgbModel) -and -not $SkipTrain) {
    Write-Info "Entrainement des modeles (premiere fois, peut prendre quelques minutes)..."
    Push-Location "$ROOT\partie2_ml"
    & python training/01_prepare_features.py
    & python training/02_train_isolation_forest.py
    & python training/03_train_xgboost.py
    & python training/04_train_lstm.py
    Pop-Location
    Write-OK "Modeles entraines et sauvegardes"
} else {
    Write-OK "Modeles deja entraines - etape ignoree"
}

# =============================================================================
# ETAPE 4 - Lancement de tous les services
# =============================================================================
Write-Step "4/6" "Lancement des services..."

# Helper pour ouvrir un service dans une nouvelle fenetre PowerShell
function Start-TeleSightService {
    param(
        [string]$Name,
        [string]$Dir,
        [string]$Cmd
    )
    $script = "& { `$Host.UI.RawUI.WindowTitle = '$Name'; Set-Location '$Dir'; $Cmd; Read-Host 'Presse Entree pour fermer' }"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $script -WindowStyle Normal
    Start-Sleep -Milliseconds 800
    Write-OK "$Name demarre"
}

# P1 - Consumer Kafka
Start-TeleSightService -Name "P1 · Consumer Kafka" `
    -Dir "$ROOT\partie1_pipeline" `
    -Cmd "python consumer/kpi_consumer.py"

# P1 - API FastAPI (port 8000)
Start-TeleSightService -Name "P1 · API :8000" `
    -Dir "$ROOT\partie1_pipeline" `
    -Cmd "uvicorn api.main:app --port 8000 --reload"

# Attendre que P1 API soit prete avant de lancer le producer
Start-Sleep -Seconds 4

# P1 - Producer Kafka
Start-TeleSightService -Name "P1 · Producer Kafka" `
    -Dir "$ROOT\partie1_pipeline" `
    -Cmd "python producer/kpi_producer.py"

# P2 - ML API (port 8001)
Start-TeleSightService -Name "P2 · ML API :8001" `
    -Dir "$ROOT\partie2_ml" `
    -Cmd "uvicorn api.ml_api:app --port 8001 --reload"

# P3 - RAG API (port 8002) - inclut ingestion ChromaDB integree + scheduler 30min
Start-TeleSightService -Name "P3 · RAG Agent :8002" `
    -Dir "$ROOT\partie3_rag" `
    -Cmd "uvicorn api.rag_api:app --port 8002 --reload"

# P4 - Dashboard React
$nodeModules = "$ROOT\partie4_dashboard\node_modules"
if (-not (Test-Path $nodeModules)) {
    Write-Info "Installation des dependances npm (premiere fois)..."
    Push-Location "$ROOT\partie4_dashboard"
    & npm install
    Pop-Location
}
Start-TeleSightService -Name "P4 · Dashboard React" `
    -Dir "$ROOT\partie4_dashboard" `
    -Cmd "npm run dev"

# =============================================================================
# ETAPE 5 - Attendre que les services soient prets
# =============================================================================
Write-Step "5/6" "Attente de la disponibilite des APIs..."

function Wait-API {
    param([string]$Name, [string]$Url, [int]$MaxWait = 40)
    $elapsed = 0
    while ($elapsed -lt $MaxWait) {
        try {
            Invoke-RestMethod -Uri $Url -TimeoutSec 2 -ErrorAction Stop | Out-Null
            Write-OK "$Name pret ($Url)"
            return
        } catch {
            Start-Sleep -Seconds 2
            $elapsed += 2
        }
    }
    Write-Warn "$Name non accessible apres ${MaxWait}s ($Url)"
}

Wait-API -Name "P1 API"     -Url "http://localhost:8000/health" -MaxWait 45
Wait-API -Name "P2 ML API"  -Url "http://localhost:8001/health" -MaxWait 45
Wait-API -Name "P3 RAG API" -Url "http://localhost:8002/health" -MaxWait 60

# Ouvrir le dashboard dans le navigateur par defaut
Write-Info "Ouverture du dashboard dans le navigateur..."
Start-Sleep -Seconds 3
Start-Process "http://localhost:3000"

# =============================================================================
# ETAPE 6 - Resume final
# =============================================================================
Write-Step "6/6" "TeleSight AI est operationnel !"
Write-Host ""
Write-Host "  +----------------------------------------------------------+" -ForegroundColor DarkCyan
Write-Host "  |              SERVICES DISPONIBLES                         |" -ForegroundColor DarkCyan
Write-Host "  +----------------------------------------------------------+" -ForegroundColor DarkCyan
Write-Host "  |  Dashboard  -> http://localhost:3000                       |" -ForegroundColor Cyan
Write-Host "  |  P1 API     -> http://localhost:8000/docs                 |" -ForegroundColor Cyan
Write-Host "  |  ML API     -> http://localhost:8001/docs                 |" -ForegroundColor Cyan
Write-Host "  |  RAG Agent  -> http://localhost:8002/docs                 |" -ForegroundColor Cyan
Write-Host "  |  Ollama     -> http://localhost:11434                     |" -ForegroundColor Cyan
Write-Host "  +----------------------------------------------------------+" -ForegroundColor DarkCyan
Write-Host ""

if ($ollamaRunning) {
    Write-Host "  [OK] Ollama actif -> L'agent RAG repond avec tinyllama" -ForegroundColor Green
} else {
    Write-Host "  [!!] Ollama inactif -> Lancez 'ollama serve' pour activer l'agent" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "  ChromaDB : ingestion automatique au demarrage de P3 + toutes les 30 min" -ForegroundColor DarkGray
Write-Host "  Pour tout arreter : lancez .\stop.ps1" -ForegroundColor DarkGray
Write-Host ""
