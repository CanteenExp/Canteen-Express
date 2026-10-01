@echo off
TITLE Canteen Express - Public Server (Localtunnel)
cd /d "%~dp0"

echo [1/2] Starting Django Development Server on port 8000...
start cmd /k cd /d "%~dp0backend" ^&^& python manage.py runserver

echo Waiting 3 seconds for Django to initialize...
timeout /t 3 /nobreak > nul

echo [2/2] Starting Localtunnel on port 8000 (No login required)...
echo.
npx localtunnel --port 8000 --subdomain canteen-express

pause
