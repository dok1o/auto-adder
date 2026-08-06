# Auto Adder Privacy And Local Processing

## Summary

Auto Adder processes documents locally on the user's Windows PC. Identity documents, HR/tax documents, extracted IIN values, names, dates of birth, and other fields are not uploaded to the internet, cloud services, APIs, telemetry systems, or third parties.

## Code Audit Summary

- No OpenAI API calls or other AI/API service calls.
- No HTTP upload clients for user data such as `requests`, `urllib`, `aiohttp`, or WebSocket code.
- No Windows networking APIs such as `WinHttp`, `WinInet`, or `URLDownload`.
- No telemetry, analytics, login tokens, or hidden background upload flow.
- The C++ app starts only the local Python engine through `CreateProcessW`.
- The Python engine reads local files, extracts fields, and writes filled documents back to local files.

## Where Data Stays

Data stays in:

- The documents selected by the user.
- Backup copies created next to edited documents, such as `*_backup.docx`, `*_backup.xlsx`, and `*_backup.pptx`.
- Temporary Windows files while processing PDFs or images.
- The fields table visible inside the running app.

## Network Behavior

The portable release includes its own local Python runtime and Python dependencies. Normal use does not require internet access.

The fallback `install_deps.bat` can use internet access only if the portable `python` folder is removed and dependencies must be installed with `pip`.

This is dependency download behavior, not document upload behavior.

## OCR And Barcodes

- PDFs with a readable text layer are processed locally without OCR.
- Photos and scanned PDFs may require local Tesseract OCR if no readable text layer exists.
- PDF417, QR, and other barcode formats may require local ZBar support.

These tools work on the user's PC.

## Customer Test Recommendation

Before testing on real personal documents, run the included check pack:

```bat
check_pack\run_check.bat
```
