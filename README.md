# BeastNotes V4 / Studio

A local desktop workspace for notes, sketches and connected ideas. Built from the supplied BeastNotes V3 app and its startup/typing updates, with Python and PySide6. No account, cloud service or API key required.

## Install on Windows

For a new PC, open **Windows PowerShell**, paste this complete block and press Enter:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $BeastSetup = Join-Path $env:TEMP ('BeastNotesV4-Setup-' + [Guid]::NewGuid().ToString('N') + '.ps1')
    Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/NoLifeeSSJ/BeastNotes/main/Install.ps1' -OutFile $BeastSetup
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BeastSetup
    if ($LASTEXITCODE -ne 0) { throw 'Installation stopped. See the error above.' }
}
```

The [short setup script](Install.ps1) downloads a tested release from an immutable GitHub commit, checks its SHA-256, then runs the full installer. It installs to `C:\BeastNotesV4`, installs Python through Windows Package Manager if needed, installs Qt, runs application checks, creates the desktop shortcut and opens V4. Internet access is required. If Windows Package Manager is unavailable and no supported Python is installed, the installer gives the official Python download link.

You can also download the complete installer manually:

Download **[Install-BeastNotesV4.ps1](https://github.com/NoLifeeSSJ/BeastNotes/raw/refs/heads/main/dist/Install-BeastNotesV4.ps1)**. Save it to your Downloads folder. If GitHub displays the script instead, click **Download raw file** (the down-arrow button). The script contains the entire application. Open PowerShell in its download folder and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Install-BeastNotesV4.ps1
```

This process-only execution policy does not change your machine's policy. You can also paste the script's complete contents into Windows PowerShell. Windows 10/11, a 64-bit Python 3.10–3.13 and Internet access to PyPI are required. If Python is missing, the installer uses Windows Package Manager to install Python 3.12 for your user, when available. Otherwise it gives the official Python download link. It never disables TLS or package verification.

The installer:

- Uses **`C:\BeastNotesV4`**, with a separate `.venv` and data at **`C:\BeastNotesV4\Data`**.
- Verifies its embedded ZIP checksum, installs pinned Qt, and runs both inherited and V4 functional checks with native Windows Qt before changing the launcher.
- Creates a BeastNotes V4 desktop icon and Start menu shortcut, then launches the app. If your desktop is managed or unavailable, it reports the shortcut error; `Launch BeastNotes V4.cmd` remains available.
- Keeps app releases under `releases`, retaining older releases and a copy of the previous command launcher on repeat installation. Close V4 before rerunning the installer. Existing V4 notes are retained. V3 is never changed.

Writing directly under `C:\` must be permitted by your Windows account. If Windows denies directory creation, ask your administrator to create `C:\BeastNotesV4` with write permission for your account.

## Bring your V3 notes across

In V4, click **Import**, select `C:\BeastnotesV3\Data\vault.json` (beside its `images` folder), or choose a complete V3 ZIP backup. V4 asks before replacing its workspace and makes a complete safety backup first. It reads the source without changing it. For older `notes_tree.json` data, use **More → Import legacy notes**.

V4 retains V3's schema 3 format so notebooks, pages, rich text, images, tags, favourites, bin, links, graph layout and typing scores can be copied. V4's schema number is deliberately not its app version number. Start V3 only against its own data folder, not the same folder V4 is using.

## What changed

- **Paint:** pen, eraser, line, rectangle, ellipse, eyedropper, colour picker, brush widths and 25–200% zoom. Undo/redo history has a memory budget. Import an image, export PNG, or insert into a note. Right-click a note image → **Paint on a copy** to annotate it without rewriting the original asset.
- **Draft recovery:** paint autosaves a local draft after a short pause. Keep draft & close, then reopen Paint to continue. Inserted drawings become ordinary immutable PNG assets included in complete backups. A single unfinished drawing is shared across the workspace. Finish that drawing before editing another image. Erasing paints white; this is a white-canvas raster tool.
- **Quick switching:** Ctrl+K searches page paths and commands; Enter opens the current result. Alt+Left/Right moves through visited pages, retaining cursor/scroll positions during the session.
- **Find and replace:** Ctrl+H searches the current page, wraps at the end, optionally matches case, and replaces all as one undo operation.
- **Page history:** Studio → Page history previews and restores up to 30 previous versions per page, sampled at most once a minute. Restoring makes a complete safety backup first. History is local to `Data/history`; ZIP backups contain the current workspace, not this history or unfinished paint drafts. Copy the entire Data folder with the app closed to preserve these extras.
- **Editing:** duplicate a whole branch with fresh IDs and remapped internal links, Ctrl+S to save, F11 focus mode, debounced workspace search, and Midnight/Dusk display preferences.
- **Retained:** nested drag-and-drop notebooks, rich text, checkboxes, image paste/drop/resize, internal links and backlinks, outline, searchable tags, favourites, trash recovery, graph, portable HTML/text export, complete backups, legacy import and typing practice with Easy/Moderate/Hard difficulty.
- **Qt update:** pinned Qt/PySide6 Essentials 6.12.0, including all modules this app uses, without installing unused Chromium/PDF components.
- **Repairs:** Qt tree tooltip signature and Windows backup flushing from your supplied repair are included. Paint click strokes and zoom coordinates have functional regression checks.

### Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+K | Switch page / run command |
| Ctrl+N / Ctrl+Shift+N | New note / book |
| Ctrl+F / Ctrl+H | Search workspace / find and replace in page |
| Ctrl+S | Save now |
| Ctrl+Shift+D | Duplicate page and children |
| Ctrl+Shift+P | Paint |
| Alt+Left / Alt+Right | Back / forward |
| F11 | Focus mode |
| Ctrl+B / Ctrl+I | Bold / italic |
| Ctrl+Z / Ctrl+Shift+Z | Undo / redo (including paint) |

## Run from source

```bash
python -m venv .venv
# Windows: .venv\Scripts\python.exe instead of .venv/bin/python
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
.venv/bin/python app.py --self-test
```

Python 3.10–3.13 supported. On Linux without a display, set `QT_QPA_PLATFORM=offscreen` for self-tests. Source checkouts keep data beside `app.py`; set `BEASTNOTES_DATA` to override the location. Each data folder uses a Qt single-instance lock. Each cloud task is already isolated; use the existing checkout instead of creating a worktree.

`app.py --self-test` creates temporary data and exercises persistence, images, stable links, bin, complete backup/restore, graph positions, legacy conversion, corruption preservation, then 14 groups of V4 Qt checks for editing, navigation, typing, drawing, draft recovery and backups. It never tests against your real notes. `app.py --smoke-test` opens and closes a real window using the selected data folder; use a temporary `BEASTNOTES_DATA` for this check.

The app was exercised offscreen on Linux during development. The installer repeats functional checks on Windows before activation; desktop shortcut creation and the Windows package-manager path still require a real Windows machine.

## Build the standalone installer

```bash
python tools/build_installer.py
```

Produces the complete PowerShell script and a source ZIP in `dist`. The embedded SHA-256 catches payload corruption; it is not a publisher signature. Build after changing application files or this README. No source files need to be hosted remotely.
