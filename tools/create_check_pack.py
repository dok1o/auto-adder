from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "check_pack"


SAMPLE_TEXT = """Фамилия: Дугашев
Имя: Айсар
Отчество: Русланович
ИИН: 090617552581
Дата рождения: 17.06.2009
Пол: мужской
Гражданство: Казахстан
Национальность: Уйгур
Номер удостоверения: 059990783
Дата выдачи: 14.07.2025
Срок действия: 13.07.2035
Кем выдан: МВД РК
Адрес регистрации: г. Алматы, ул. Абая 10
Должность/роль работника: техник сцены
"""


def reset_output() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)


def write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)


def docx_paragraph(text: str) -> str:
    return f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"


def create_docx(path: Path) -> None:
    lines = [
        "AUTO ADDER CHECK: DOCX",
        "ФИО: {{ФИО}}",
        "Фамилия: {{Фамилия}}",
        "Имя: {{Имя}}",
        "Отчество: {{Отчество}}",
        "ИИН: {{ИИН}}",
        "Дата рождения: {{Дата рождения}}",
        "Пол: {{Пол}}",
        "Гражданство: {{Гражданство}}",
        "Национальность: {{Национальность}}",
        "Номер документа: {{Номер документа}}",
        "Дата выдачи: {{Дата выдачи}}",
        "Срок действия: {{Срок действия}}",
        "Кем выдан: {{Кем выдан}}",
        "Адрес регистрации: {{Адрес регистрации}}",
        "Работник: {{ФИО работника}} / {{ИИН работника}}",
    ]
    body = "".join(docx_paragraph(line) for line in lines)
    # Split placeholder across runs to verify Word run-fragment replacement.
    body += (
        "<w:p><w:r><w:t>Разбитый плейсхолдер: {{Ф</w:t></w:r>"
        "<w:r><w:t>ИО}}</w:t></w:r></w:p>"
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>"
            ),
            "_rels/.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="word/document.xml"/>'
                "</Relationships>"
            ),
            "word/document.xml": (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body>{body}<w:sectPr/></w:body></w:document>"
            ),
        },
    )


def cell(ref: str, text: str) -> str:
    return (
        f'<c r="{ref}" t="inlineStr"><is><t>{escape(text)}</t></is></c>'
    )


def create_xlsx(path: Path) -> None:
    rows = [
        ("Поле", "Значение"),
        ("ФИО", ""),
        ("ИИН", ""),
        ("Дата рождения", ""),
        ("Номер удостоверения", ""),
        ("Дата выдачи", ""),
        ("Срок действия", ""),
        ("Кем выдан", ""),
        ("Адрес регистрации", ""),
        ("Плейсхолдер в строке", "{{ФИО}} / {{ИИН}} / {{Дата рождения}}"),
    ]
    xml_rows = []
    for index, (left, right) in enumerate(rows, 1):
        xml_rows.append(
            f'<row r="{index}">{cell(f"A{index}", left)}{cell(f"B{index}", right)}</row>'
        )
    write_zip(
        path,
        {
            "[Content_Types].xml": (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/xl/workbook.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                '<Override PartName="/xl/worksheets/sheet1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                "</Types>"
            ),
            "_rels/.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="xl/workbook.xml"/>'
                "</Relationships>"
            ),
            "xl/workbook.xml": (
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<sheets><sheet name="Check" sheetId="1" r:id="rId1"/></sheets></workbook>'
            ),
            "xl/_rels/workbook.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                'Target="worksheets/sheet1.xml"/>'
                "</Relationships>"
            ),
            "xl/worksheets/sheet1.xml": (
                '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheetData>' + "".join(xml_rows) + "</sheetData></worksheet>"
            ),
        },
    )


def ppt_text_box(text: str) -> str:
    return (
        "<p:sp><p:nvSpPr><p:cNvPr id=\"2\" name=\"TextBox\"/>"
        "<p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr><p:spPr/>"
        "<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:r>"
        f"<a:t>{escape(text)}</a:t>"
        "</a:r></a:p></p:txBody></p:sp>"
    )


def create_pptx(path: Path) -> None:
    slide_text = "\n".join(
        [
            "AUTO ADDER CHECK: PPTX",
            "ФИО: {{ФИО}}",
            "ИИН: {{ИИН}}",
            "Дата рождения: {{Дата рождения}}",
            "Номер документа: {{Номер документа}}",
            "Дата выдачи: {{Дата выдачи}}",
            "Срок действия: {{Срок действия}}",
            "Орган: {{Орган выдачи}}",
        ]
    )
    split_placeholder = (
        "<p:sp><p:nvSpPr><p:cNvPr id=\"3\" name=\"Split\"/>"
        "<p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr><p:spPr/>"
        "<p:txBody><a:bodyPr/><a:lstStyle/><a:p>"
        "<a:r><a:t>Разбитый плейсхолдер: {{Ф</a:t></a:r>"
        "<a:r><a:t>ИО}}</a:t></a:r>"
        "</a:p></p:txBody></p:sp>"
    )
    write_zip(
        path,
        {
            "[Content_Types].xml": (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/ppt/presentation.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
                '<Override PartName="/ppt/slides/slide1.xml" '
                'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
                "</Types>"
            ),
            "_rels/.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
                'Target="ppt/presentation.xml"/>'
                "</Relationships>"
            ),
            "ppt/presentation.xml": (
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                '<p:sldIdLst><p:sldId id="256" r:id="rId1"/></p:sldIdLst></p:presentation>'
            ),
            "ppt/_rels/presentation.xml.rels": (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" '
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
                'Target="slides/slide1.xml"/>'
                "</Relationships>"
            ),
            "ppt/slides/slide1.xml": (
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                f"<p:cSld><p:spTree>{ppt_text_box(slide_text)}{split_placeholder}</p:spTree></p:cSld></p:sld>"
            ),
        },
    )


def create_runner() -> None:
    docs = [
        str(OUT / "01_check_docx.docx"),
        str(OUT / "02_check_xlsx.xlsx"),
        str(OUT / "03_check_pptx.pptx"),
    ]
    (OUT / "documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "run_check.py").write_text(
        f'''from __future__ import annotations

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
''',
        encoding="utf-8",
    )
    (OUT / "run_check.bat").write_text(
        """@echo off
setlocal
cd /d "%~dp0"

if exist "..\\python\\python.exe" (
  "..\\python\\python.exe" "run_check.py"
  goto :done
)

if exist "..\\.venv\\Scripts\\python.exe" (
  "..\\.venv\\Scripts\\python.exe" "run_check.py"
  goto :done
)

python "run_check.py"

:done
endlocal
""",
        encoding="utf-8",
    )
    (OUT / "README_CHECK.txt").write_text(
        """Auto Adder check pack

1. Run from project root:
   .\\check_pack\\run_check.bat

2. Open these files after the run:
   check_pack\\01_check_docx.docx
   check_pack\\02_check_xlsx.xlsx
   check_pack\\03_check_pptx.pptx

3. Expected result:
   All {{...}} placeholders and Excel field rows should be filled with data from 00_sample_identity.txt.

4. To reset the pack:
   run tools\\create_check_pack.py again.
""",
        encoding="utf-8",
    )


def main() -> None:
    reset_output()
    (OUT / "00_sample_identity.txt").write_text(SAMPLE_TEXT, encoding="utf-8")
    create_docx(OUT / "01_check_docx.docx")
    create_xlsx(OUT / "02_check_xlsx.xlsx")
    create_pptx(OUT / "03_check_pptx.pptx")
    create_runner()
    print(OUT)


if __name__ == "__main__":
    main()
