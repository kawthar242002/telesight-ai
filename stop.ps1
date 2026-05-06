# ============================================================
#  TeleSight AI — Arrêt de tous les services
#  Usage : .\stop.ps1
# ============================================================

$ROOT = $PSScriptRoot

Write-Host ""
Write-Host "  TeleSight AI — Arrêt en cours..." -ForegroundColor Red
Write-Host ""

# Arrêter les fenêtres PowerShell nommées
$services = @(
    "P1 · Consumer Kafka",
    "P1 · API :8000",
    "P1 · Producer Kafka",
    "P2 · ML API :8001",
    "P3 · RAG Agent :8002",
    "P4 · Dashboard React"
)

foreach ($svc in $services) {
    $procs = Get-Process powershell -ErrorAction SilentlyContinue |
             Where-Object { $_.MainWindowTitle -match [regex]::Escape($svc) }
    if ($procs) {
        $procs | Stop-Process -Force
        Write-Host "  ✔ $svc arrêté" -ForegroundColor Green
    }
}

# Arrêter les processus Python uvicorn / producer / consumer
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    $pythonProcs | Stop-Process -Force
    Write-Host "  ✔ Processus Python arrêtés" -ForegroundColor Green
}

# Arrêter Node.js (dashboard)
$nodeProcs = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcs) {
    $nodeProcs | Stop-Process -Force
    Write-Host "  ✔ Dashboard Node.js arrêté" -ForegroundColor Green
}

# Arrêter Docker Compose
Write-Host "  → Arrêt de l'infrastructure Docker..." -ForegroundColor Gray
Push-Location "$ROOT\partie1_pipeline"
docker-compose down 2>&1 | Out-Null
Pop-Location
Write-Host "  ✔ Docker arrêté" -ForegroundColor Green

Write-Host ""
Write-Host "  Tous les services TeleSight AI sont arrêtés." -ForegroundColor Cyan
Write-Host ""
