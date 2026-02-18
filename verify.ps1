$ErrorActionPreference = "Stop"

Write-Output "--- Running PSScriptAnalyzer ---"
Invoke-ScriptAnalyzer -Path ./verify.ps1 -ErrorAction Stop

Write-Output "--- Running Ruff lint ---"
python -m ruff check .

Write-Output "--- Running Ruff format check ---"
python -m ruff format --check .

Write-Output "--- Running Pyright type check ---"
pyright src

Write-Output "--- Running tests ---"
python -m unittest discover -s tests

Write-Output "--- Running security audit ---"
python -m pip_audit -r requirements-dev.txt

Write-Output "`nVerification PASSED"