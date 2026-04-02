@echo off
title Smoke Signal Installer
powershell -ExecutionPolicy Bypass -File "%~dp0Install-SmokeSignal.ps1"
pause
