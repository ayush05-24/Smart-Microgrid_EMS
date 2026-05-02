@echo off
cd /d "%~dp0"
start "Smart Microgrid API" cmd /k ""%~dp0venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"
start "Smart Microgrid Frontend" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev"
