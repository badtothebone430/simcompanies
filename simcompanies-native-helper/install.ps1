$ErrorActionPreference = "Stop"

$manifestPath = Join-Path $PSScriptRoot "com.simcompanies.csv_helper.json"
if (-not (Test-Path $manifestPath)) {
  throw "Manifest not found: $manifestPath"
}

$regPath = "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.simcompanies.csv_helper"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "(default)" -Value $manifestPath

$regPathEdge = "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.simcompanies.csv_helper"
New-Item -Path $regPathEdge -Force | Out-Null
Set-ItemProperty -Path $regPathEdge -Name "(default)" -Value $manifestPath

Write-Host "Registered native host manifest: $manifestPath"
