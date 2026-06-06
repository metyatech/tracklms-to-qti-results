$ErrorActionPreference = "Stop"

Write-Output "--- Installing npm dependencies ---"
npm install

Write-Output "--- Running npm verify ---"
npm run verify

Write-Output "--- Running critical security audit ---"
npm audit --audit-level=critical

Write-Output "`nVerification PASSED"
