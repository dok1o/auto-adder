from __future__ import annotations

import json
import sys
from pathlib import Path


PACK = Path(__file__).resolve().parent
ROOT = PACK.parent
sys.path.insert(0, str(ROOT / "engine"))

from auto_adder_engine import extract_identity, fill_documents


sample_path = PACK / "00_sample_identity.txt"
document_paths = [
    PACK / "01_check_docx.docx",
    PACK / "02_check_xlsx.xlsx",
    PACK / "03_check_pptx.pptx",
]

extract_payload = extract_identity(sample_path, "Удостоверение личности")
(PACK / "extract_result.json").write_text(
    json.dumps(extract_payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
(PACK / "fields.json").write_text(
    json.dumps(extract_payload["fields"], ensure_ascii=False, indent=2),
    encoding="utf-8",
)

fill_payload = fill_documents(document_paths, extract_payload["fields"])
(PACK / "fill_result.json").write_text(
    json.dumps(fill_payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("Done. Open files in check_pack.")
print("Extraction:", PACK / "extract_result.json")
print("Fill result:", PACK / "fill_result.json")
