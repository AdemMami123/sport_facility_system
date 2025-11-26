@echo off
REM Run this file as Administrator
REM Right-click -> Run as administrator

echo Fixing module version...
echo.

powershell -Command "$content = Get-Content 'C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system\__manifest__.py' -Raw; $content = $content -replace \"'version': '17\.0\.1\.0\.0'\", \"'version': '18.0.1.0.0'\"; Set-Content 'C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system\__manifest__.py' -Value $content -NoNewline"

if %ERRORLEVEL% EQU 0 (
    echo SUCCESS! Version updated to 18.0.1.0.0
    echo.
    echo Now restart Odoo service:
    echo   1. Press Win + R
    echo   2. Type: services.msc
    echo   3. Find "Odoo 18.0"
    echo   4. Right-click -^> Restart
    echo.
    echo Then in Odoo:
    echo   1. Apps -^> Update Apps List
    echo   2. Search: Sports Facility Booking
    echo   3. Install
) else (
    echo ERROR! Failed to update version.
    echo Make sure you ran this as Administrator!
)

echo.
pause
