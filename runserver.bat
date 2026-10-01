@echo off
TITLE Canteen Express - Public Server (DevTunnel)
cd /d "%~dp0"

echo [1/2] Starting Django Development Server on port 8000...
start cmd /k cd /d "%~dp0backend" ^&^& python manage.py runserver

echo Waiting 3 seconds for Django to initialize...
timeout /t 3 /nobreak > nul

echo [2/2] Starting Persistent Microsoft Dev Tunnel (canteen-express)...
echo.

set DT="devtunnel"
if exist "%~dp0devtunnel.exe" set DT="%~dp0devtunnel.exe"

REM Host the permanent 'canteen-express' tunnel
%DT% host canteen-express

pause
