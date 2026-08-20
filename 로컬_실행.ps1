$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in @("-3.13", "-3.12", "-3")) {
            try {
                & py $version --version *> $null
                if ($LASTEXITCODE -eq 0) { return @("py", $version) }
            } catch {}
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        try {
            & python --version *> $null
            if ($LASTEXITCODE -eq 0) { return @("python") }
        } catch {}
    }
    throw "Python 3.12 이상을 찾지 못했습니다. Python을 설치한 뒤 이 파일을 다시 실행해 주세요."
}

$pythonCommand = Find-Python
$venvDirectory = Join-Path $PSScriptRoot ".venv313"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "[1/3] 프로젝트 전용 Python 환경을 만듭니다."
    if ($pythonCommand.Count -eq 2) {
        & $pythonCommand[0] $pythonCommand[1] -m venv $venvDirectory
    } else {
        & $pythonCommand[0] -m venv $venvDirectory
    }
}

Write-Host "[2/3] 필요한 웹 패키지를 확인합니다."
& $venvPython -m pip install -r requirements-web.txt

Write-Host ""
Write-Host "[3/3] 웹 서버를 시작합니다."
& $venvPython run_local.py
