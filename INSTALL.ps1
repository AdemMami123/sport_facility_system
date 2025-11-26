# Sports Facility Booking System - Installation Script
# Run as Administrator

Write-Host "=================================" -ForegroundColor Cyan
Write-Host "Module Installation Script" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop Odoo Service
Write-Host "[1/5] Stopping Odoo service..." -ForegroundColor Yellow
try {
    Stop-Service -Name "odoo-server-18.0" -Force -ErrorAction Stop
    Write-Host "✓ Odoo service stopped" -ForegroundColor Green
} catch {
    Write-Host "⚠ Could not stop service (may not be running)" -ForegroundColor Yellow
}
Start-Sleep -Seconds 2

# Step 2: Remove old module
Write-Host "[2/5] Removing old module files..." -ForegroundColor Yellow
$targetPath = "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system"
if (Test-Path $targetPath) {
    Remove-Item -Path $targetPath -Recurse -Force
    Write-Host "✓ Old files removed" -ForegroundColor Green
} else {
    Write-Host "✓ No old files found" -ForegroundColor Green
}

# Step 3: Copy new module
Write-Host "[3/5] Copying new module files..." -ForegroundColor Yellow
$sourcePath = "C:\Users\ademm\OneDrive\Desktop\sport_facility_booking_system"
Copy-Item -Path $sourcePath -Destination $targetPath -Recurse -Force
Write-Host "✓ Module files copied" -ForegroundColor Green

# Step 4: Validate XML files
Write-Host "[4/5] Validating XML files..." -ForegroundColor Yellow
$errors = 0
foreach ($file in Get-ChildItem $targetPath -Include *.xml -Recurse) {
    try {
        [xml]$xml = Get-Content $file.FullName -Raw
    } catch {
        Write-Host "  ✗ $($file.Name): ERROR" -ForegroundColor Red
        $errors++
    }
}
if ($errors -eq 0) {
    Write-Host "✓ All XML files valid" -ForegroundColor Green
} else {
    Write-Host "✗ $errors XML file(s) have errors" -ForegroundColor Red
    exit 1
}

# Step 5: Start Odoo Service
Write-Host "[5/5] Starting Odoo service..." -ForegroundColor Yellow
try {
    Start-Service -Name "odoo-server-18.0" -ErrorAction Stop
    Write-Host "✓ Odoo service started" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to start service: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=================================" -ForegroundColor Green
Write-Host "Installation Complete!" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Open Odoo: http://localhost:8069" -ForegroundColor White
Write-Host "2. Login (admin/admin)" -ForegroundColor White
Write-Host "3. Go to Apps menu" -ForegroundColor White
Write-Host "4. Click 'Update Apps List'" -ForegroundColor White
Write-Host "5. Search: Sports Facility" -ForegroundColor White
Write-Host "6. Click Install" -ForegroundColor White
Write-Host ""
