@echo off
echo ========================================
echo  Sports Facility Module Update Script
echo ========================================
echo.

echo [1/4] Stopping Odoo service...
net stop "odoo-server-18.0"
timeout /t 3 >nul

echo [2/4] Removing old module files...
rd /s /q "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system" 2>nul

echo [3/4] Copying updated module...
xcopy /E /I /Y "C:\Users\ademm\OneDrive\Desktop\sport_facility_booking_system" "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system"

echo [4/4] Starting Odoo service...
net start "odoo-server-18.0"
timeout /t 3 >nul

echo.
echo ========================================
echo  UPDATE COMPLETE!
echo ========================================
echo.
echo Next steps:
echo 1. Open http://localhost:8069
echo 2. Login (admin/admin)
echo 3. Go to Apps ^> Update Apps List
echo 4. Search: Sports Facility
echo 5. Click Install
echo.
pause
