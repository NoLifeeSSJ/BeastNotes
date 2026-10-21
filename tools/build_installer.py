"""Build a self-contained, checksum-verified PowerShell distribution."""
from pathlib import Path
import base64
import hashlib
import io
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = ['app.py', 'studio.py', 'paint.py', 'v4_checks.py', 'requirements.txt', 'README.md', 'tools/build_installer.py']

def payload_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (ROOT / name).read_bytes())
    return buffer.getvalue()

TEMPLATE = r'''# BeastNotes V4 - complete Windows installer. No administrator session required by the script.
# Installs to C:\BeastNotesV4. V3 is not modified. Requires Windows 10/11 and Internet for Python/Qt.
& {
    $ErrorActionPreference = 'Stop'
    $BeastRoot = 'C:\BeastNotesV4'
    $BeastStage = $null
    try {
        Write-Host 'BeastNotes V4 / Studio' -ForegroundColor Magenta
        Write-Host 'Preparing notes, paint, recovery and your desktop shortcut...'
        if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
            throw 'Run this installer in Windows PowerShell on Windows 10 or 11.'
        }
        New-Item -ItemType Directory -Path $BeastRoot -Force | Out-Null
        $BeastPython = Join-Path $BeastRoot '.venv\Scripts\python.exe'
        $BeastFindPython = {
            $BeastCandidates = @('C:\BeastnotesV3\.venv\Scripts\python.exe', 'C:\BeastNotes\.venv\Scripts\python.exe')
            if (Get-Command py -ErrorAction SilentlyContinue) {
                foreach ($BeastVersion in @('-3.12', '-3.13', '-3.11', '-3.10')) {
                    try {
                        $BeastProbe = & py $BeastVersion -c 'import sys; print(sys.executable)' 2>$null
                        if ($LASTEXITCODE -eq 0 -and $BeastProbe) { $BeastCandidates += "$BeastProbe".Trim() }
                    } catch { }
                }
            }
            foreach ($BeastVersion in @('312', '313', '311', '310')) {
                $BeastCandidates += "$env:LOCALAPPDATA\Programs\Python\Python$BeastVersion\python.exe"
            }
            if (Get-Command python -ErrorAction SilentlyContinue) {
                $BeastCandidates += (Get-Command python).Source
            }
            foreach ($BeastCandidate in ($BeastCandidates | Select-Object -Unique)) {
                if (Test-Path -LiteralPath $BeastCandidate) {
                    try {
                        $BeastProbe = & $BeastCandidate -c "import sys,struct; print('BEAST_OK' if (3,10) <= sys.version_info[:2] <= (3,13) and struct.calcsize('P') == 8 else 'NO')" 2>$null
                        if ($LASTEXITCODE -eq 0 -and "$BeastProbe".Trim() -eq 'BEAST_OK') { return $BeastCandidate }
                    } catch { }
                }
            }
            return $null
        }
        if (-not (Test-Path -LiteralPath $BeastPython)) {
            $BeastBasePython = & $BeastFindPython
            if (-not $BeastBasePython) {
                if (Get-Command winget -ErrorAction SilentlyContinue) {
                    Write-Host 'Installing Python 3.12 for your Windows user...' -ForegroundColor Cyan
                    & winget install --exact --id Python.Python.3.12 --scope user --source winget --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
                    if ($LASTEXITCODE -ne 0) { throw 'Python installation failed. Install 64-bit Python 3.12 from python.org, then rerun this script.' }
                    $BeastBasePython = & $BeastFindPython
                }
                if (-not $BeastBasePython) { throw 'Install 64-bit Python 3.12 from https://www.python.org/downloads/windows/ and rerun this installer.' }
            }
            & $BeastBasePython -m venv (Join-Path $BeastRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the V4 Python environment.' }
        }
        # A running V4 must be closed before refreshing its shared Python dependencies.
        $BeastRunning = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
            Where-Object { $_.CommandLine -and $_.CommandLine.Contains($BeastRoot) -and $_.CommandLine.Contains('app.py') }
        if ($BeastRunning) { throw 'Close BeastNotes V4, then rerun this installer. No application files have been replaced.' }
        & $BeastPython -m pip --disable-pip-version-check install --only-binary=:all: 'PySide6-Essentials==6.12.0'
        if ($LASTEXITCODE -ne 0) { throw 'Qt installation failed. Check the Internet connection and output above, then rerun.' }

        $BeastPayload = @'
__PAYLOAD__
'@
        $BeastBytes = [Convert]::FromBase64String($BeastPayload)
        $BeastSha = [Security.Cryptography.SHA256]::Create()
        try { $BeastActualHash = ([BitConverter]::ToString($BeastSha.ComputeHash($BeastBytes))).Replace('-', '').ToLowerInvariant() }
        finally { $BeastSha.Dispose() }
        if ($BeastActualHash -ne '__HASH__') { throw 'The embedded application checksum does not match. Download the complete installer again.' }
        $BeastRelease = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
        $BeastReleases = Join-Path $BeastRoot 'releases'
        New-Item -ItemType Directory -Path $BeastReleases -Force | Out-Null
        $BeastStage = Join-Path $BeastReleases $BeastRelease
        New-Item -ItemType Directory -Path $BeastStage | Out-Null
        $BeastZip = Join-Path $BeastStage 'package.zip'
        [IO.File]::WriteAllBytes($BeastZip, $BeastBytes)
        Expand-Archive -LiteralPath $BeastZip -DestinationPath $BeastStage
        Remove-Item -LiteralPath $BeastZip
        $BeastMain = Join-Path $BeastStage 'app.py'
        Write-Host 'Checking syntax, saving, recovery, paint and navigation...' -ForegroundColor Cyan
        & $BeastPython -m compileall -q $BeastStage
        if ($LASTEXITCODE -ne 0) { throw 'Syntax checks failed. The previous launcher has not been changed.' }
        & $BeastPython $BeastMain --self-test -platform windows
        if ($LASTEXITCODE -ne 0) { throw 'Functional checks failed. The previous launcher has not been changed. See the error above.' }
        $BeastIcon = Join-Path $BeastRoot 'BeastNotesV4.ico'
        & $BeastPython $BeastMain --make-icon $BeastIcon -platform windows
        if ($LASTEXITCODE -ne 0) { throw 'Could not generate the desktop icon.' }
        $BeastPythonw = Join-Path $BeastRoot '.venv\Scripts\pythonw.exe'
        $BeastUtf8 = New-Object System.Text.UTF8Encoding($false)
        $BeastLauncher = Join-Path $BeastRoot 'Launch BeastNotes V4.cmd'
        $BeastCmd = "@echo off`r`ncd /d `"$BeastRoot`"`r`n`"$BeastPython`" `"$BeastMain`" -platform windows`r`nif errorlevel 1 pause`r`n"
        if (Test-Path -LiteralPath $BeastLauncher) {
            Copy-Item -LiteralPath $BeastLauncher -Destination (Join-Path $BeastRoot ('Launch-before-' + $BeastRelease + '.cmd'))
        }
        [IO.File]::WriteAllText(($BeastLauncher + '.pending'), $BeastCmd, $BeastUtf8)
        Move-Item -LiteralPath ($BeastLauncher + '.pending') -Destination $BeastLauncher -Force
        # Per-user shortcuts. The data location is stable across versioned releases.
        try {
            $BeastShell = New-Object -ComObject WScript.Shell
            $BeastDesktop = [Environment]::GetFolderPath('Desktop')
            $BeastPrograms = [Environment]::GetFolderPath('Programs')
            foreach ($BeastLocation in @($BeastDesktop, $BeastPrograms)) {
                if ($BeastLocation -and (Test-Path -LiteralPath $BeastLocation)) {
                    $BeastLink = $BeastShell.CreateShortcut((Join-Path $BeastLocation 'BeastNotes V4.lnk'))
                    $BeastLink.TargetPath = $BeastPythonw
                    $BeastLink.Arguments = '"' + $BeastMain + '" -platform windows'
                    $BeastLink.WorkingDirectory = $BeastRoot
                    $BeastLink.IconLocation = $BeastIcon
                    $BeastLink.Description = 'BeastNotes V4 - notes, paint and connected ideas'
                    $BeastLink.Save()
                }
            }
        } catch {
            Write-Warning ('Shortcut creation was unavailable: ' + $_.Exception.Message + '. Use ' + $BeastLauncher)
        }
        Write-Host ''
        Write-Host 'V4 installed and checks passed.' -ForegroundColor Green
        Write-Host "Your data: $BeastRoot\Data"
        Write-Host 'Use Import inside V4 to copy C:\BeastnotesV3\Data\vault.json or a V3 ZIP backup.'
        Write-Host 'Your V3 installation and notes have not been modified.'
        Start-Process -FilePath $BeastPythonw -ArgumentList ('"' + $BeastMain + '" -platform windows') -WorkingDirectory $BeastRoot
    } catch {
        Write-Host ''
        Write-Host 'Installation stopped:' -ForegroundColor Red
        Write-Host $_.Exception.Message -ForegroundColor Red
        Write-Host 'Your notes have not been deleted. Fix the reported issue and rerun the installer.'
        throw
    }
}
'''

def main():
    payload = payload_bytes()
    encoded = base64.b64encode(payload).decode('ascii')
    wrapped = '\n'.join(encoded[i:i+120] for i in range(0, len(encoded), 120))
    script = TEMPLATE.replace('__PAYLOAD__', wrapped).replace('__HASH__', hashlib.sha256(payload).hexdigest())
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    # BOM for Windows PowerShell 5.1; payload itself is Unicode-safe base64.
    (out / 'Install-BeastNotesV4.ps1').write_text(script, encoding='utf-8-sig')
    (out / 'BeastNotesV4-source.zip').write_bytes(payload)
    print('Built self-contained installer and source ZIP')

if __name__ == '__main__':
    main()
