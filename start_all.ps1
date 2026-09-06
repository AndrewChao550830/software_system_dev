# ===== One-click start: FCC + Streamlit =====
# Usage: powershell -ExecutionPolicy Bypass -File .\start_all.ps1
# Both FCC and Streamlit are skipped if already running.

$ErrorActionPreference = 'SilentlyContinue'
$proj = $PSScriptRoot
$fccExe = 'C:\Shares\Coding\autoClaudeCode\free-claude-code.exe'

# ---- 1) FCC (port 8082) ----
$fccPid = Get-NetTCPConnection -LocalPort 8082 -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess
if ($fccPid) {
    Write-Host "[OK] FCC already running (PID=$fccPid, http://127.0.0.1:8082)"
} else {
    Start-Process -FilePath $fccExe -ArgumentList '--server' -WindowStyle Hidden
    Start-Sleep -Seconds 8
    $fccPid = Get-NetTCPConnection -LocalPort 8082 -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess
    if ($fccPid) { Write-Host "[OK] FCC started (PID=$fccPid)" }
    else { Write-Host '[FAIL] FCC failed to start. Check exe path and C:\Users\coryc\.fcc\.env' }
}

# ---- 2) Streamlit (port 8501) ----
$stPid = Get-NetTCPConnection -LocalPort 8501 -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess
if ($stPid) {
    Write-Host "[OK] Streamlit already running (PID=$stPid, http://localhost:8501)"
} else {
    Start-Process -FilePath (Join-Path $proj 'ven\Scripts\python.exe') `
        -ArgumentList '-m','streamlit','run','streamlit_ui.py','--server.headless','true','--server.port','8501' `
        -WorkingDirectory $proj -WindowStyle Hidden
    Start-Sleep -Seconds 10
    $stPid = Get-NetTCPConnection -LocalPort 8501 -State Listen | Select-Object -First 1 -ExpandProperty OwningProcess
    if ($stPid) { Write-Host "[OK] Streamlit started (PID=$stPid)" }
    else { Write-Host '[FAIL] Streamlit failed to start' }
}

Write-Host ''
Write-Host 'Done! Open http://localhost:8501 in your browser.'
