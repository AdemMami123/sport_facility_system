# Run this script as Administrator
# Right-click -> Run with PowerShell (as Admin)

Write-Host "Copying module to Odoo addons folder..." -ForegroundColor Green

$source = "C:\Users\ademm\OneDrive\Desktop\sport_facility_booking_system"
$destination = "C:\Program Files\Odoo 18.0.20251006\server\addons\sport_facility_booking_system"

# Remove old version if exists
if (Test-Path $destination) {
    Write-Host "Removing old version..." -ForegroundColor Yellow
    Remove-Item -Path $destination -Recurse -Force
}

# Copy new version
Write-Host "Copying new version with XML fixes..." -ForegroundColor Yellow
Copy-Item -Path $source -Destination $destination -Recurse -Force

Write-Host ""
Write-Host "Module copied successfully!" -ForegroundColor Green
Write-Host "Fixed issues:" -ForegroundColor Cyan
Write-Host "  - All XML files corrected (proper 4/8 space indentation)" -ForegroundColor White
Write-Host "  - Removed trailing whitespace from blank lines" -ForegroundColor White
Write-Host "  - Fixed closing tags in security and data files" -ForegroundColor White
Write-Host ""
Write-Host "Now restart Odoo service:" -ForegroundColor Cyan
Write-Host "  1. Press Win + R" -ForegroundColor White
Write-Host "  2. Type: services.msc" -ForegroundColor White  
Write-Host "  3. Find 'Odoo 18.0'" -ForegroundColor White
Write-Host "  4. Right-click -> Restart" -ForegroundColor White
Write-Host ""
Write-Host "Then in Odoo UI:" -ForegroundColor Cyan
Write-Host "  1. Apps -> Update Apps List" -ForegroundColor White
Write-Host "  2. Search: 'Sports Facility Booking'" -ForegroundColor White
Write-Host "  3. Install the module" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close"
