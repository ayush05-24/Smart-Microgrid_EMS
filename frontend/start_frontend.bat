@echo off
cd /d "%~dp0"
npm.cmd run dev >> "%~dp0..\data\outputs\frontend-dev.log" 2>> "%~dp0..\data\outputs\frontend-dev.err.log"
