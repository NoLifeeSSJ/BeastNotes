# BeastNotes V4: download and run the tested Windows installer.
# The release commit and checksum must be updated together for a new release.
& {
    $ErrorActionPreference = 'Stop'

    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'Run this script in Windows PowerShell on Windows 10 or 11.'
    }

    [Net.ServicePointManager]::SecurityProtocol = (
        [Net.ServicePointManager]::SecurityProtocol -bor
        [Net.SecurityProtocolType]::Tls12
    )

    $BeastRelease = 'b3ee566050d4a2090184a55d7446517c9396482f'
    $BeastExpectedHash = 'f3c098ee35ec862e398c54d57fcda129a55d399f88d17381fa68d3b9dbcf4273'
    $BeastUrl = "https://raw.githubusercontent.com/NoLifeeSSJ/BeastNotes/$BeastRelease/dist/Install-BeastNotesV4.ps1"
    $BeastInstaller = Join-Path $env:TEMP (
        'Install-BeastNotesV4-' + [Guid]::NewGuid().ToString('N') + '.ps1'
    )

    Write-Host 'Downloading BeastNotes V4 from GitHub...' -ForegroundColor Cyan
    Invoke-WebRequest -UseBasicParsing -Uri $BeastUrl -OutFile $BeastInstaller

    $BeastActualHash = (Get-FileHash -LiteralPath $BeastInstaller -Algorithm SHA256).Hash
    if ($BeastActualHash -ne $BeastExpectedHash) {
        throw 'The downloaded installer did not pass verification. Run this script again.'
    }

    Write-Host 'Download verified. Starting installation...' -ForegroundColor Green
    $BeastPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    & $BeastPowerShell -NoProfile -ExecutionPolicy Bypass -File $BeastInstaller
    if ($LASTEXITCODE -ne 0) {
        throw 'Installation stopped. Copy the error above into the BeastNotes chat for help.'
    }
}
