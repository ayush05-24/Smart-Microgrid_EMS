@echo off
cd /d "%~dp0..\.."
"%~dp0..\..\venv\Scripts\python.exe" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 >> "%~dp0..\..\data\outputs\api-server.log" 2>> "%~dp0..\..\data\outputs\api-server.err.log"
