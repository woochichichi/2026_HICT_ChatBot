param(
    [string]$OutPath = "$env:USERPROFILE\company-ca.pem"
)

$certs = Get-ChildItem -Path Cert:\LocalMachine\Root, Cert:\LocalMachine\CA, Cert:\CurrentUser\Root, Cert:\CurrentUser\CA -ErrorAction SilentlyContinue

$pem = foreach ($cert in $certs) {
    "-----BEGIN CERTIFICATE-----`n" +
    [Convert]::ToBase64String($cert.RawData, 'InsertLineBreaks') +
    "`n-----END CERTIFICATE-----"
}

$pem | Out-File -Encoding ascii $OutPath
Write-Host ("Wrote {0} certificates to {1}" -f $certs.Count, $OutPath)
