param(
  [string]$PythonLauncher = "py",
  [string]$PythonVersion = "3.12",
  [string]$VenvPath = ".venv-py312",
  [string]$KernelName = "cortex-py312",
  [string]$DisplayName = "Cortex Py312"
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
  param([string]$Message)
  Write-Host ""
  Write-Host "==> $Message"
}

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$venvFullPath = Join-Path $repoRoot $VenvPath

Invoke-Step "Checking Python $PythonVersion availability"
& $PythonLauncher -$PythonVersion --version

Invoke-Step "Creating virtual environment at $venvFullPath"
& $PythonLauncher -$PythonVersion -m venv $venvFullPath

$pythonExe = Join-Path $venvFullPath "Scripts\python.exe"
$pipArgs = @(
  "-m", "pip", "install",
  "--upgrade",
  "pip"
)

Invoke-Step "Upgrading pip"
& $pythonExe @pipArgs

$packages = @(
  "ipykernel",
  "jupyter-ai",
  "ipywidgets",
  "jupyterlab_widgets",
  "widgetsnbextension",
  "pandas",
  "numpy",
  "scikit-learn",
  "matplotlib",
  "seaborn",
  "networkx",
  "plotly",
  "tqdm",
  "pyarrow",
  "fastparquet",
  "torch",
  "torchvision",
  "torchaudio",
  "torch-geometric"
)

Invoke-Step "Installing notebook and ML dependencies"
& $pythonExe -m pip install @packages

Invoke-Step "Registering Jupyter kernel '$DisplayName'"
& $pythonExe -m ipykernel install --user --name $KernelName --display-name $DisplayName

Write-Host ""
Write-Host "Kernel ready."
Write-Host "Python executable: $pythonExe"
Write-Host "Kernel name: $KernelName"
Write-Host "Display name: $DisplayName"
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Restart Jupyter if needed."
Write-Host "2. Open the notebook."
Write-Host "3. Select kernel: $DisplayName"
