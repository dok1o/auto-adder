# Auto Adder

Local Windows app for extracting identity data from a sample document and filling DOCX, XLSX, and PPTX files.

## Main Folders

- `engine` - Python document engine.
- `cpp` - Win32 desktop app source.
- `setup` - one-file installer source.
- `assets` - app icon and visual assets.
- `check_pack` - test files for extraction/filling.
- `tools` - build, release, and GitHub helper scripts.
- `docs` - customer readme, privacy note, release notes, GitHub release guide.
- `dist` - ready files for customers.

## Customer Release

Main customer file:

```text
dist\AutoAdderSetup.exe
```

Customer flow:

1. Download `AutoAdderSetup.exe`.
2. Run it.
3. The installer copies Auto Adder to `%LOCALAPPDATA%\AutoAdder`.
4. The installer creates a desktop shortcut named `Auto Adder`.
5. The app opens automatically.

The portable runtime is embedded, so customers do not need to install Python.

## Development Run

For local development:

```bat
START_AUTO_ADDER.bat
```

The app looks for Python in this order:

1. `python\python.exe` next to the app.
2. `.venv\Scripts\python.exe`.
3. System `python.exe`.

## Build App

Open a Visual Studio Developer Command Prompt or run through `VsDevCmd`, then:

```bat
cd cpp
build_msvc.bat
```

Output:

```text
cpp\build\AutoAdder.exe
```

## Build Portable Zip

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_release.ps1 -Version 0.5 -IncludePortablePython
```

Output:

```text
dist\AutoAdder-0.5.zip
```

## Build Installer

`setup\AutoAdderSetup.rc` embeds:

```text
dist\Auto-adder.zip
```

Build:

```bat
cd setup
build_setup_msvc.bat
```

Output:

```text
setup\build\AutoAdderSetup.exe
```

Copy the final installer to:

```text
dist\AutoAdderSetup.exe
```

## Publish To GitHub

See:

```text
docs\GITHUB_RELEASE_GUIDE.md
```

Direct customer download link after publishing:

```text
https://github.com/OWNER/REPOSITORY/releases/latest/download/AutoAdderSetup.exe
```

## Privacy

The app processes documents locally on the user's PC. It does not upload documents or extracted identity data to external services.

See:

```text
docs\PRIVACY_SECURITY.md
```
