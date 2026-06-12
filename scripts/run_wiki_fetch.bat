@echo off
REM ===================================================================
REM  run_wiki_fetch.bat - double-click launcher for wiki_fetch.ps1
REM  No Python required. Collects wiki page HTML into scripts\wiki_html\
REM  Edit the line below to add -Incremental for daily change-only runs.
REM ===================================================================
echo ============================================================
echo  Wiki HTML batch fetch
echo  - paste the auth header value when prompted
echo  - output goes to: scripts\wiki_html\
echo ============================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0wiki_fetch.ps1"
echo.
echo ============================================================
echo  Finished. Copy the scripts\wiki_html folder to the Python PC.
echo ============================================================
pause
