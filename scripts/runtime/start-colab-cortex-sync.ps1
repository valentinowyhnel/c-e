param(
  [int]$ColabPort = 8888,
  [int]$OrchestratorPort = 18081,
  [string]$Kubeconfig = "C:\Users\dell\Desktop\coco\tmp-kind-kubeconfig.yaml",
  [string]$Secret = "",
  [string]$NotebookRoot = "C:\Users\dell\Desktop\coco",
  [string]$PayloadPath = "examples/verified-colab-result.example.json",
  [switch]$PushTestPayload
)

$ErrorActionPreference = "Stop"

function Require-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Commande introuvable: $name"
  }
}

function Get-FreeTcpPort([int]$PreferredPort) {
  $port = $PreferredPort
  while ($true) {
    $inUse = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if (-not $inUse) {
      return $port
    }
    $port++
  }
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSeconds = 20) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
      if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
        return $response.StatusCode
      }
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  throw "HTTP endpoint not reachable in time: $Url"
}

Require-Command python
Require-Command kubectl

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot "..\..")
$backendScript = Join-Path $repoRoot "scripts\runtime\start-colab-local-backend.ps1"
$clientScript = Join-Path $repoRoot "scripts\runtime\colab_sync_client.py"
$resolvedPayload = Resolve-Path (Join-Path $repoRoot $PayloadPath)

if ([string]::IsNullOrWhiteSpace($Secret)) {
  Write-Warning "Aucun secret Colab fourni. Le test de push sera ignore."
}

$ColabPort = Get-FreeTcpPort $ColabPort
$OrchestratorPort = Get-FreeTcpPort $OrchestratorPort

$token = [guid]::NewGuid().ToString("N")
$backendArgs = @(
  "-ExecutionPolicy", "Bypass",
  "-File", $backendScript,
  "-Port", "$ColabPort",
  "-Token", $token,
  "-NotebookRoot", (Resolve-Path $NotebookRoot).Path,
  "-Lab"
)

$backend = Start-Process -FilePath "powershell" -ArgumentList $backendArgs -PassThru -WindowStyle Hidden
$portForward = Start-Process -FilePath "kubectl" -ArgumentList @(
  "--kubeconfig", $Kubeconfig,
  "port-forward",
  "-n", "cortex-system",
  "svc/cortex-orchestrator",
  "$OrchestratorPort`:8080"
) -PassThru -WindowStyle Hidden

Start-Sleep -Seconds 8

$colabUrl = "http://localhost:$ColabPort/?token=$token"
$orchestratorUrl = "http://127.0.0.1:$OrchestratorPort/v1/training/colab/ingest"
$orchestratorHealthUrl = "http://127.0.0.1:$OrchestratorPort/health"

Write-Host ""
Write-Host "Colab backend URL:"
Write-Host $colabUrl
Write-Host ""
Write-Host "Cortex orchestrator sync URL:"
Write-Host $orchestratorUrl
Write-Host ""
Write-Host "Backend PID: $($backend.Id)"
Write-Host "Port-forward PID: $($portForward.Id)"
Write-Host ""

try {
  $backendCode = Wait-HttpOk $colabUrl 20
  Write-Host "Colab backend HTTP: $backendCode"
} catch {
  Write-Warning "Colab backend non joignable pour l'instant."
}

try {
  $orchCode = Wait-HttpOk $orchestratorHealthUrl 20
  Write-Host "Orchestrator HTTP: $orchCode"
} catch {
  Write-Warning "Orchestrator non joignable sur le port-forward."
}

if ($PushTestPayload -and -not [string]::IsNullOrWhiteSpace($Secret)) {
  Write-Host ""
  Write-Host "Push du payload de test..."
  python $clientScript $resolvedPayload --url $orchestratorUrl --secret $Secret
}

Write-Host ""
Write-Host "Pour arreter:"
Write-Host "Stop-Process -Id $($backend.Id),$($portForward.Id)"
