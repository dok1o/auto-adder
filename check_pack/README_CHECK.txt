Auto Adder check pack

1. Run from project root:
   .\check_pack\run_check.bat

2. Open these files after the run:
   check_pack\01_check_docx.docx
   check_pack\02_check_xlsx.xlsx
   check_pack\03_check_pptx.pptx

3. Expected result:
   All {{...}} placeholders and Excel field rows should be filled with data from 00_sample_identity.txt.

4. To reset the pack:
   run tools\create_check_pack.py again.
