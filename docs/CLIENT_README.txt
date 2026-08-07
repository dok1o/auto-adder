Auto Adder 0.3 Portable
=======================

What this package is
--------------------

Auto Adder is a local Windows application for extracting identity data from a sample and filling DOCX, XLSX, and PPTX documents.

Quick start
-----------

1. Download AutoAdderSetup.exe.
2. Run AutoAdderSetup.exe.
3. Open Auto Adder from the desktop shortcut.
4. Add documents for filling.
5. Choose a sample and click "Extract data".
6. Check the extracted fields.
7. Click "Fill documents".

Requirements
------------

- Windows 10/11.
- No Python installation is required.
- OCR from scanned images may require Tesseract if the PDF/image has no readable text layer.

Privacy
-------

- All processing happens locally on the user's PC.
- The app does not upload documents, IIN, names, dates of birth, or extracted fields.
- The portable release does not need internet access for normal use.

Check pack
----------

The check_pack folder contains test files:

- 00_sample_identity.txt
- 01_check_docx.docx
- 02_check_xlsx.xlsx
- 03_check_pptx.pptx

To run an automatic check:

check_pack\run_check.bat
