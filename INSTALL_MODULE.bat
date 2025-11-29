@echo off
echo ============================================
echo  Sports Facility Booking System Installer
echo ============================================
echo.

:: Check for admin rights
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo [1/4] Removing old module version...
if exist "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system" (
    rmdir /S /Q "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system"
    echo      Old version removed.
) else (
    echo      No old version found.
)

echo.
echo [2/4] Copying new module files...
xcopy /E /I /Y "C:\Users\ademm\OneDrive\Desktop\sport_facility_booking_system" "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system" >nul
if %errorLevel% EQU 0 (
    echo      Module copied successfully!
) else (
    echo      ERROR: Failed to copy module!
    pause
    exit /b 1
)

echo.
echo [3/4] Verifying installation...
if exist "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system\__manifest__.py" (
    findstr "18.0.1.0.0" "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system\__manifest__.py" >nul
    if %errorLevel% EQU 0 (
        echo      Version 18.0.1.0.0 confirmed!
    ) else (
        echo      WARNING: Version might not be correct!
    )
) else (
    echo      ERROR: __manifest__.py not found!
    pause
    exit /b 1
)

echo.
echo [4/4] Module installation complete!
echo.
echo ============================================
echo  NEXT STEPS:
echo ============================================
echo  1. Restart Odoo service:
echo     - Press Win+R
echo     - Type: services.msc
echo     - Find "Odoo 18.0"
echo     - Right-click -^> Restart
echo.
echo  2. In Odoo (http://localhost:8069):
echo     - Go to Apps
echo     - Click "Update Apps List"
echo     - Search: "Sports Facility Booking"
echo     - Click Install
echo.
echo ============================================
echo.
pause
