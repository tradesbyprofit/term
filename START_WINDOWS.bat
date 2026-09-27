@echo off
title J.A.R.V.I.S. // Pinnacle Quantitative Trading Terminal
color 0B

echo ======================================================================
echo    J.A.R.V.I.S. // PINNACLE QUANTITATIVE TRADING TERMINAL (WINDOWS)
echo ======================================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not added to your system PATH!
    echo Please download and install Python from https://www.python.org/
    echo ** IMPORTANT: Check the box "Add Python to PATH" during installation **
    pause
    exit /b 1
)

echo [1/3] Checking dependencies (requests, scipy, numpy, waitress)...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet requests scipy numpy waitress openpyxl

echo [2/3] Syncing latest live Pinnacle lines and limits...
python real_pinnacle_ingest.py

echo [3/3] Launching production WSGI server (Waitress) on http://localhost:8000...
echo.
echo ======================================================================
echo   J.A.R.V.I.S. TERMINAL IS NOW LIVE!
echo   Open in your browser: http://localhost:8000
echo.
echo   To access from your iPhone on the same Wi-Fi:
echo   Find your laptop IP (run 'ipconfig') and open: http://YOUR_PC_IP:8000
echo ======================================================================
echo.

:: Automatically open browser window
start http://localhost:8000

:: Start Waitress WSGI server (Windows native high-performance server)
python -c "from waitress import serve; import wsgi_application; print('Waitress serving on http://0.0.0.0:8000'); serve(wsgi_application.application, host='0.0.0.0', port=8000, threads=6)"

pause
