$ErrorActionPreference = "Stop"

Write-Host "--- Running Ruff lint ---"
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "--- Running Ruff format check ---"
python -m ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "--- Running Pyright type check ---"
pyright src
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "--- Running tests ---"
python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "--- Running security audit ---"
python -m pip_audit -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "`nVerification PASSED" -ForegroundColor Green
