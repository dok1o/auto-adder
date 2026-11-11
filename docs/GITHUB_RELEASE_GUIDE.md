# GitHub release for customers

This project is distributed as a one-file Windows installer:

- `AutoAdderSetup.exe`

## Customer download link

After uploading `AutoAdderSetup.exe` to the latest GitHub Release, customers can use this direct link:

```text
https://github.com/OWNER/REPOSITORY/releases/latest/download/AutoAdderSetup.exe
```

Replace:

- `OWNER` with your GitHub username or organization.
- `REPOSITORY` with the repository name.

Example:

```text
https://github.com/my-company/auto-adder/releases/latest/download/AutoAdderSetup.exe
```

Opening this link starts downloading the installer immediately.

## Manual upload

1. Open the repository on GitHub.
2. Go to `Releases`.
3. Click `Draft a new release`.
4. Create a tag, for example `V-0.5`.
5. Set release title to `Auto Adder 0.5`.
6. Upload `dist\AutoAdderSetup.exe`.
7. Publish the release.
8. Send customers the direct download link from the section above.

## What customers do

1. Download `AutoAdderSetup.exe`.
2. Run it.
3. The installer creates a desktop shortcut and opens Auto Adder.

## Privacy note

The app processes documents locally on the user's PC. It does not upload documents or extracted identity data to external services.

The installer contains the portable release with its own local Python runtime and dependencies, so normal use does not require Python installation or internet access.
