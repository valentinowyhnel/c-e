param(
  [int]$Port = 8888,
  [string]$Token = "",
  [string]$NotebookRoot = "C:\Users\dell\Desktop\coco",
  [switch]$Lab
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Token)) {
  $Token = [guid]::NewGuid().ToString("N")
}

$mode = if ($Lab) { "lab" } else { "notebook" }
$root = (Resolve-Path $NotebookRoot).Path

$args = if ($Lab) {
  @(
    "-m",
    "jupyterlab",
    "--ServerApp.allow_origin=https://colab.research.google.com",
    "--ServerApp.allow_remote_access=True",
    "--ServerApp.ip=127.0.0.1",
    "--ServerApp.port=$Port",
    "--ServerApp.open_browser=False",
    "--ServerApp.token=$Token",
    "--ServerApp.root_dir=$root"
  )
} else {
  @(
    "-m",
    "notebook",
    "--ServerApp.allow_origin=https://colab.research.google.com",
    "--ServerApp.allow_remote_access=True",
    "--ServerApp.ip=127.0.0.1",
    "--ServerApp.port=$Port",
    "--ServerApp.open_browser=False",
    "--ServerApp.token=$Token",
    "--ServerApp.root_dir=$root"
  )
}

Write-Host ""
Write-Host "Colab local backend pret a demarrer."
Write-Host "URL a coller dans Google Colab :"
Write-Host "http://localhost:$Port/?token=$Token"
Write-Host ""
Write-Host "Repertoire expose : $root"
Write-Host "Mode : $mode"
Write-Host ""

& python @args
