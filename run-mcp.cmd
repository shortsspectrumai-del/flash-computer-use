@echo off
setlocal
if exist "%~dp0.runtime\playwright" if not defined PLAYWRIGHT_BROWSERS_PATH set "PLAYWRIGHT_BROWSERS_PATH=%~dp0.runtime\playwright"
"%~dp0.venv\Scripts\python.exe" -m d1_computer_use_mcp.server %*
