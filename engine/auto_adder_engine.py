#!/usr/bin/env python3
"""Local document engine: extract identity data and fill Office documents."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

META_KEYS = {"Тип образца", "Файл образца", "Формат", "Статус извлечения", "Источник данных"}


def emit(payload: dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def emit_error(message: str, code: int = 1) -> None:
    emit({"ok": False, "error": message})
    raise SystemExit(code)


def module_status(module_name: str) -> dict[str, str | bool]:
    try:
        __import__(module_name)
    except Exception as exc:
        return {"name": module_name, "ok": False, "error": str(exc)}
    return {"name": module_name, "ok": True}


def doctor() -> dict[str, Any]:
    root = Path(__file__).resolve().parent.parent
    modules = [
        module_status("PIL"),
        module_status("pypdf"),
        module_status("pyzbar"),
        module_status("pytesseract"),
        module_status("fitz"),
    ]
    return {
        "ok": True,
        "python": sys.executable,
        "project_root": str(root),
        "engine": str(Path(__file__).resolve()),
        "modules": modules,
        "usage": [
            "python engine/auto_adder_engine.py extract --sample path/to/sample.txt",
            "python engine/auto_adder_engine.py fill --documents-file docs.json --fields-file fields.json",
        ],
    }


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


def normalize_key(text: str) -> str:
    text = text.replace("ё", "е").replace("Ё", "Е")
    text = re.sub(r"[\s\xa0]+", " ", text.strip().lower())
    return re.sub(r"[№#:/\\|()\[\]{}.,;]+", " ", text).strip()


def find_iin(text: str) -> str:
    for match in re.finditer(r"\b(\d{12})\b", text):
        return match.group(1)
    return ""


FIELD_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ИИН", ("иин", "iin", "жсн", "ж с н")),
    ("ФИО", ("фио", "ф и о", "полное имя", "фамилия имя отчество", "аты жони", "аты-жони")),
    ("Фамилия", ("фамилия", "surname", "last name", "тегі")),
    ("Имя", ("имя", "name", "first name", "аты")),
    ("Отчество", ("отчество", "middle name", "әкесінің аты", "отч")),
    ("Дата рождения", ("дата рождения", "д р", "рождения", "birth date", "date of birth", "туган куні", "туған күні")),
    ("Пол", ("пол", "sex", "gender", "жынысы")),
    ("Гражданство", ("гражданство", "citizenship", "nationality", "азаматтығы")),
    ("Национальность", ("национальность", "ұлты", "улты")),
    ("Номер удостоверения/паспорта", ("номер документа", "номер удостоверения", "номер паспорта", "удостоверение", "паспорт", "document number", "passport number", "id number", "no")),
    ("Дата выдачи", ("дата выдачи", "issue date", "date of issue", "берілген күні")),
    ("Срок действия", ("срок действия", "действителен до", "valid until", "expiry date", "expiration date", "қолданылу мерзімі")),
    ("Кем выдан", ("кем выдан", "орган выдачи", "выдавший орган", "authority", "issuer", "берген орган")),
    ("Адрес регистрации", ("адрес регистрации", "адрес прописки", "место жительства", "адрес", "registration address", "мекенжай")),
)


def canonical_key(key: str) -> str:
    normalized = normalize_key(key)
    if not normalized:
        return key.strip()
    for canonical, aliases in FIELD_ALIASES:
        for alias in aliases:
            alias_norm = normalize_key(alias)
            if normalized == alias_norm or normalized.startswith(alias_norm + " "):
                return canonical
    return key.strip()


def normalize_date(value: str) -> str:
    value = value.strip()
    match = re.fullmatch(r"\s*(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})\s*", value)
    if not match:
        return value
    day, month, year = match.groups()
    if len(year) == 2:
        year = ("19" if int(year) > 30 else "20") + year
    return f"{int(day):02d}.{int(month):02d}.{year}"


def clean_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" \t:-—–")
    return normalize_date(value)


def canonicalize_fields(fields: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in fields.items():
        canonical = canonical_key(key)
        cleaned = clean_value(value)
        if cleaned:
            result[canonical] = cleaned

    fio = result.get("ФИО")
    if not fio:
        fio_parts = [result.get("Фамилия", ""), result.get("Имя", ""), result.get("Отчество", "")]
        fio = " ".join(part for part in fio_parts if part).strip()
        if fio:
            result["ФИО"] = fio
    return result


def parse_kz_pdf417(payload: str) -> dict[str, str]:
    """Parse common Kazakhstan ID PDF417 payloads."""
    fields: dict[str, str] = {}
    parts = [p.strip() for p in re.split(r"[|;\n\r\t]+", payload) if p.strip()]
    if not parts:
        return fields

    for part in parts:
        if re.fullmatch(r"\d{12}", part):
            fields.setdefault("ИИН", part)

    if len(parts) >= 4 and re.fullmatch(r"\d{12}", parts[0]):
        fields["ИИН"] = parts[0]
        fields["Фамилия"] = parts[1]
        fields["Имя"] = parts[2]
        fields["Отчество"] = parts[3] if len(parts) > 3 else ""
        fio = " ".join(x for x in (fields.get("Фамилия"), fields.get("Имя"), fields.get("Отчество")) if x)
        if fio:
            fields["ФИО"] = fio
        if len(parts) > 4:
            fields["Дата рождения"] = parts[4]
        if len(parts) > 5:
            fields["Пол"] = parts[5]
        if len(parts) > 6:
            fields["Номер удостоверения/паспорта"] = parts[6]
        if len(parts) > 7:
            fields["Дата выдачи"] = parts[7]
        if len(parts) > 8:
            fields["Срок действия"] = parts[8]
        if len(parts) > 9:
            fields["Кем выдан"] = parts[9]
        return fields

    upper = payload.upper()
    if "IIN" in upper or "ИИН" in upper:
        m = re.search(r"(?:IIN|ИИН)\D*(\d{12})", payload, re.IGNORECASE)
        if m:
            fields["ИИН"] = m.group(1)

    name_match = re.search(
        r"(?:SURNAME|LASTNAME|Фамилия)\D*([A-Za-zА-Яа-яЁё\-]+).*?"
        r"(?:NAME|FIRSTNAME|Имя)\D*([A-Za-zА-Яа-яЁё\-]+)",
        payload,
        re.IGNORECASE | re.DOTALL,
    )
    if name_match:
        fields["Фамилия"] = name_match.group(1)
        fields["Имя"] = name_match.group(2)
        fields["ФИО"] = f"{name_match.group(1)} {name_match.group(2)}".strip()

    return fields


def parse_mrz(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    clean = [re.sub(r"\s+", "", line.upper()) for line in lines if line.strip()]
    if len(clean) < 2:
        return fields

    line1, line2 = clean[0], clean[1]
    if not line1.startswith("P"):
        return fields

    names_part = line1[5:].split("<<", 1)
    if len(names_part) == 2:
        surname = names_part[0].replace("<", " ").strip()
        given = names_part[1].replace("<", " ").strip()
        fields["Фамилия"] = surname.title()
        given_parts = [p for p in given.split() if p]
        if given_parts:
            fields["Имя"] = given_parts[0].title()
            if len(given_parts) > 1:
                fields["Отчество"] = " ".join(p.title() for p in given_parts[1:])
        fields["ФИО"] = " ".join(x for x in (fields.get("Фамилия"), fields.get("Имя"), fields.get("Отчество")) if x)

    doc_number = line2[0:9].replace("<", "").strip()
    nationality = line2[10:13].replace("<", "").strip()
    birth = line2[13:19]
    sex = line2[20:21].replace("<", "")
    expiry = line2[21:27]

    if doc_number:
        fields["Номер удостоверения/паспорта"] = doc_number
    if nationality:
        fields["Гражданство"] = nationality
    if birth.isdigit():
        fields["Дата рождения"] = f"{birth[4:6]}.{birth[2:4]}.19{birth[0:2]}" if int(birth[0:2]) > 30 else f"{birth[4:6]}.{birth[2:4]}.20{birth[0:2]}"
    if sex in {"M", "F"}:
        fields["Пол"] = "мужской" if sex == "M" else "женский"
    if expiry.isdigit():
        fields["Срок действия"] = f"{expiry[4:6]}.{expiry[2:4]}.20{expiry[0:2]}"

    return fields


def decode_barcodes(image_path: Path) -> list[str]:
    try:
        from PIL import Image
        from pyzbar.pyzbar import decode as zbar_decode
    except ImportError:
        return []

    image = Image.open(image_path)
    values: list[str] = []
    for symbol in zbar_decode(image):
        try:
            values.append(symbol.data.decode("utf-8", errors="replace"))
        except Exception:
            continue
    return values


def ocr_text(image_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return ""

    try:
        return pytesseract.image_to_string(Image.open(image_path), lang="rus+eng")
    except Exception:
        try:
            return pytesseract.image_to_string(Image.open(image_path), lang="eng")
        except Exception:
            return ""


def pdf_to_image(pdf_path: Path) -> Path | None:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        return None
    page = doc.load_page(0)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    temp = pdf_path.with_suffix(".page1.png")
    pix.save(temp)
    return temp


def extract_pdf_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        PdfReader = None

    if PdfReader is not None:
        try:
            reader = PdfReader(str(pdf_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text.strip():
                return text
        except Exception:
            pass

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return ""

    try:
        with fitz.open(pdf_path) as doc:
            return "\n".join(page.get_text("text") or "" for page in doc)
    except Exception:
        return ""


def parse_key_value_text(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            fields[canonical_key(key)] = clean_value(value)
        elif ":" in line:
            key, value = line.split(":", 1)
            if len(key.strip()) <= 80 and value.strip():
                fields[canonical_key(key)] = clean_value(value)
        elif ";" in line:
            for chunk in line.split(";"):
                if "=" in chunk:
                    key, value = chunk.split("=", 1)
                    fields[canonical_key(key)] = clean_value(value)
                elif ":" in chunk:
                    key, value = chunk.split(":", 1)
                    if len(key.strip()) <= 80 and value.strip():
                        fields[canonical_key(key)] = clean_value(value)
    if not fields and "," in text:
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        if rows:
            headers = [h.strip() for h in rows[0]]
            if len(rows) > 1:
                values = rows[1]
                for key, value in zip(headers, values):
                    if key:
                        fields[canonical_key(key)] = clean_value(value)
    return fields


def parse_labeled_identity_text(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    compact = re.sub(r"[ \t]+", " ", text)

    for canonical, aliases in FIELD_ALIASES:
        for alias in aliases:
            pattern = re.compile(
                r"(?:^|[\n\r])\s*" + re.escape(alias) + r"\s*(?:[:=№#\-–—]|\s{2,})\s*([^\n\r;|]+)",
                re.IGNORECASE,
            )
            match = pattern.search(compact)
            if match:
                fields.setdefault(canonical, clean_value(match.group(1)))
                break

    iin = find_iin(text)
    if iin:
        fields.setdefault("ИИН", iin)

    for canonical, aliases in (
        ("Дата рождения", ("дата рождения", "birth date", "date of birth")),
        ("Дата выдачи", ("дата выдачи", "issue date", "date of issue")),
        ("Срок действия", ("срок действия", "valid until", "expiry date")),
    ):
        if canonical in fields:
            continue
        alias_pattern = "|".join(re.escape(alias) for alias in aliases)
        match = re.search(
            rf"(?:{alias_pattern})\D{{0,30}}(\d{{1,2}}[./\-]\d{{1,2}}[./\-]\d{{2,4}})",
            compact,
            re.IGNORECASE,
        )
        if match:
            fields[canonical] = normalize_date(match.group(1))

    if "Номер удостоверения/паспорта" not in fields:
        match = re.search(
            r"(?:удостоверени[ея]|паспорт|document|passport|id)\D{0,30}([A-ZА-Я0-9]{5,20})",
            compact,
            re.IGNORECASE,
        )
        if match and not re.fullmatch(r"\d{12}", match.group(1)):
            fields["Номер удостоверения/паспорта"] = match.group(1)

    if "Пол" not in fields:
        match = re.search(r"(?:\bпол\b|sex|gender)\D{0,15}(мужской|женский|male|female|m|f)\b", compact, re.IGNORECASE)
        if match:
            value = match.group(1).lower()
            fields["Пол"] = "мужской" if value in {"мужской", "male", "m"} else "женский"

    return canonicalize_fields(fields)


def parse_identity_text(text: str) -> dict[str, str]:
    mrz_lines = [line for line in text.splitlines() if "<" in line and len(line) >= 30]
    return canonicalize_fields(
        merge_fields(
            parse_kz_pdf417(text),
            parse_mrz(mrz_lines),
            parse_kz_identity_layout(text),
            parse_key_value_text(text),
            parse_labeled_identity_text(text),
        )
    )


def parse_kz_identity_layout(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    lines = [clean_value(line) for line in text.splitlines() if clean_value(line)]
    if not lines:
        return fields

    birth_index: int | None = None
    for index, line in enumerate(lines):
        match = re.search(r"\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\b\s*([МMЖF])?", line, re.IGNORECASE)
        if not match:
            continue
        fields.setdefault("Дата рождения", normalize_date(match.group(1)))
        if match.group(2):
            sex = match.group(2).upper()
            fields.setdefault("Пол", "мужской" if sex in {"М", "M"} else "женский")
        birth_index = index
        break

    if birth_index is not None and birth_index >= 2:
        name_lines = lines[max(0, birth_index - 3):birth_index]
        if len(name_lines) >= 2:
            fields.setdefault("Фамилия", name_lines[0].title())
            fields.setdefault("Имя", name_lines[1].title())
            if len(name_lines) >= 3:
                fields.setdefault("Отчество", name_lines[2].title())

    iin_index: int | None = None
    for index, line in enumerate(lines):
        match = re.fullmatch(r"\d{12}", line)
        if match:
            fields.setdefault("ИИН", line)
            iin_index = index
            break

    if iin_index is not None:
        for line in lines[iin_index + 1:]:
            if re.fullmatch(r"\d{5,12}", line) and line != fields.get("ИИН"):
                fields.setdefault("Номер удостоверения/паспорта", line)
                break

    doc_index = next((i for i, line in enumerate(lines) if line == fields.get("Номер удостоверения/паспорта")), None)
    if doc_index is not None:
        tail = [line for line in lines[doc_index + 1:] if "<" not in line]
        if tail:
            fields.setdefault("Гражданство", tail[0].title())
        if len(tail) > 1 and not re.search(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}", tail[1]):
            fields.setdefault("Национальность", tail[1].title())

    for line in lines:
        match = re.search(
            r"(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\s*[-–—]\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})\s*(.*)",
            line,
        )
        if match:
            fields.setdefault("Дата выдачи", normalize_date(match.group(1)))
            fields.setdefault("Срок действия", normalize_date(match.group(2)))
            issuer = clean_value(match.group(3))
            if issuer:
                fields.setdefault("Кем выдан", issuer)
            break

    return canonicalize_fields(fields)


def extract_from_docx(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    texts = [node.text for node in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t") if node.text]
    joined = "\n".join(texts)
    fields.update(parse_key_value_text(joined))
    fields.update(parse_labeled_identity_text(joined))
    iin = find_iin(joined)
    if iin:
        fields.setdefault("ИИН", iin)
    return canonicalize_fields(fields)


def extract_from_xlsx(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in ss_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                parts = [t.text or "" for t in si.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                shared.append("".join(parts))

        sheet_name = next((n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")), None)
        if not sheet_name:
            return fields
        sheet = ET.fromstring(zf.read(sheet_name))
        rows: list[list[str]] = []
        for row in sheet.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
            current: list[str] = []
            for cell in row.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c"):
                current.append(cell_text(cell, shared))
            if any(x.strip() for x in current):
                rows.append(current)

        for row in rows:
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                fields[canonical_key(row[0])] = clean_value(row[1])
        joined = "\n".join(" ".join(r) for r in rows)
        fields.update(parse_labeled_identity_text(joined))
        iin = find_iin(joined)
        if iin:
            fields.setdefault("ИИН", iin)
    return canonicalize_fields(fields)


def guess_name_from_filename(path: Path) -> str:
    stem = path.stem
    for token in ("договор", "материальной", "ответственности", "заявление", "ипн", "вычет", "образец", "паспорт", "удостовер"):
        stem = re.sub(token, " ", stem, flags=re.IGNORECASE)
    words = [w for w in re.split(r"[\s_\-]+", stem) if w and not re.fullmatch(r"\d{6,}", w)]
    if len(words) >= 2:
        return " ".join(words[-3:])
    return ""


def merge_fields(*groups: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for group in groups:
        for key, value in group.items():
            value = (value or "").strip()
            if value:
                merged[key] = value
    return merged


def alias_fields(fields: dict[str, str]) -> dict[str, str]:
    aliases = dict(fields)
    fio = aliases.get("ФИО") or " ".join(
        x for x in (aliases.get("Фамилия"), aliases.get("Имя"), aliases.get("Отчество")) if x
    ).strip()
    iin = aliases.get("ИИН", "")

    if fio:
        aliases.setdefault("ФИО", fio)
        aliases.setdefault("ФИО работника", fio)
        aliases.setdefault("ФИО физического лица", fio)
    if iin:
        aliases.setdefault("ИИН", iin)
        aliases.setdefault("ИИН работника", iin)
        aliases.setdefault("ИИН физического лица", iin)

    for src, dst in (
        ("Номер удостоверения/паспорта", "Номер удостоверения работника"),
        ("Номер удостоверения/паспорта", "Номер паспорта"),
        ("Номер удостоверения/паспорта", "Номер документа"),
        ("Дата выдачи", "Дата выдачи удостоверения"),
        ("Дата выдачи", "Дата выдачи паспорта"),
        ("Дата рождения", "Дата рождения работника"),
        ("Дата рождения", "Дата рождения физического лица"),
        ("Срок действия", "Срок действия удостоверения"),
        ("Срок действия", "Действителен до"),
        ("Кем выдан", "Кем выдано удостоверение"),
        ("Кем выдан", "Орган выдачи"),
        ("Адрес регистрации", "Адрес регистрации работника"),
        ("Адрес регистрации", "Адрес физического лица"),
        ("Гражданство", "Гражданство работника"),
        ("Пол", "Пол работника"),
        ("Фамилия", "Фамилия работника"),
        ("Имя", "Имя работника"),
        ("Отчество", "Отчество работника"),
    ):
        if aliases.get(src):
            aliases.setdefault(dst, aliases[src])

    aliases.setdefault("Дата договора", datetime.now().strftime("%d.%m.%Y"))
    aliases.setdefault("Дата заявления", datetime.now().strftime("%d.%m.%Y"))
    aliases.setdefault("Работодатель", 'ТОО "ALT SOUND+"')
    aliases.setdefault("Налоговый агент", 'ТОО "ALT SOUND+"')
    aliases.setdefault("БИН налогового агента", "090240020651")
    aliases.setdefault("Вычет ОПВ", "да")
    aliases.setdefault("Вычет ВОСМС", "да")
    return aliases


def extract_identity(sample: Path, sample_kind: str) -> dict[str, Any]:
    ext = sample.suffix.lower()
    source = "эвристика имени файла"
    extracted: dict[str, str] = {}
    temp_image: Path | None = None

    if ext in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}:
        for payload in decode_barcodes(sample):
            parsed = parse_kz_pdf417(payload)
            if parsed:
                extracted = merge_fields(extracted, parsed)
                source = "PDF417/QR штрихкод"
        if not extracted:
            text = ocr_text(sample)
            if text.strip():
                extracted = merge_fields(extracted, parse_identity_text(text))
                source = "локальный OCR"
    elif ext == ".pdf":
        text = extract_pdf_text(sample)
        if text.strip():
            extracted = merge_fields(extracted, parse_identity_text(text))
            source = "текстовый слой PDF"
        if not extracted:
            temp_image = pdf_to_image(sample)
        if not extracted and temp_image and temp_image.exists():
            for payload in decode_barcodes(temp_image):
                parsed = parse_kz_pdf417(payload)
                if parsed:
                    extracted = merge_fields(extracted, parsed)
                    source = "PDF417/QR штрихкод (PDF)"
            if not extracted:
                text = ocr_text(temp_image)
                if text.strip():
                    extracted = merge_fields(extracted, parse_identity_text(text))
                    source = "локальный OCR (PDF)"
    elif ext in {".txt", ".csv"}:
        extracted = parse_identity_text(read_text(sample))
        source = "текстовый файл"
    elif ext in {".docx"}:
        extracted = extract_from_docx(sample)
        source = "Word-образец"
    elif ext in {".xlsx", ".xls"}:
        if ext == ".xlsx":
            extracted = extract_from_xlsx(sample)
            source = "Excel-образец"

    fallback = {
        "ФИО": guess_name_from_filename(sample),
        "ИИН": find_iin(sample.name),
    }
    extracted = canonicalize_fields(merge_fields(fallback, extracted))
    extracted = alias_fields(extracted)

    fields = [
        {"name": "Тип образца", "value": sample_kind},
        {"name": "Файл образца", "value": sample.name},
        {"name": "Формат", "value": ext or "без расширения"},
        {"name": "Источник данных", "value": source},
        {"name": "Статус извлечения", "value": "данные получены локально" if any(k not in META_KEYS for k in extracted) else "нужна проверка вручную"},
    ]

    priority = [
        "ФИО", "ИИН", "Номер удостоверения/паспорта", "Дата рождения", "Пол",
        "Фамилия", "Имя", "Отчество", "Гражданство", "Национальность", "Дата выдачи", "Срок действия", "Кем выдан", "Адрес регистрации",
        "ФИО работника", "ИИН работника", "Номер удостоверения работника", "Номер паспорта", "Номер документа", "Дата выдачи удостоверения",
        "Адрес регистрации работника", "Дата договора", "Должность/роль работника",
        "ФИО физического лица", "ИИН физического лица", "Дата заявления", "Вычет ОПВ", "Вычет ВОСМС",
    ]

    seen = {f["name"] for f in fields}
    for key in priority:
        if key in extracted and key not in seen:
            fields.append({"name": key, "value": extracted[key]})
            seen.add(key)
    for key, value in extracted.items():
        if key not in seen:
            fields.append({"name": key, "value": value})
            seen.add(key)

    if temp_image and temp_image.exists():
        try:
            temp_image.unlink()
        except OSError:
            pass

    return {"ok": True, "fields": fields}


def replace_placeholders(text: str, mapping: dict[str, str]) -> str:
    updated = text
    for key, value in mapping.items():
        if not value:
            continue
        patterns = [
            re.compile(r"\{\{\s*" + re.escape(key) + r"\s*\}\}"),
            re.compile(r"\{\s*" + re.escape(key) + r"\s*\}"),
            re.compile(r"\[\s*" + re.escape(key) + r"\s*\]"),
            re.compile(r"<<\s*" + re.escape(key) + r"\s*>>"),
            re.compile(r"__+\s*" + re.escape(key) + r"\s*__+"),
        ]
        for pattern in patterns:
            updated = pattern.sub(value, updated)
    return updated


def replace_in_text_nodes(root: ET.Element, text_tag: str, mapping: dict[str, str], container_tags: set[str]) -> int:
    replacements = 0
    for parent in root.iter():
        if parent.tag not in container_tags:
            continue
        text_nodes = [node for node in parent.iter(text_tag) if node.text]
        if not text_nodes:
            continue

        original = "".join(node.text or "" for node in text_nodes)
        replaced = replace_placeholders(original, mapping)
        if replaced == original:
            continue

        text_nodes[0].text = replaced
        for node in text_nodes[1:]:
            node.text = ""
        replacements += 1
    return replacements


def replace_single_text_nodes(root: ET.Element, text_tag: str, mapping: dict[str, str]) -> int:
    replacements = 0
    for node in root.iter(text_tag):
        if not node.text:
            continue
        replaced = replace_placeholders(node.text, mapping)
        if replaced != node.text:
            node.text = replaced
            replacements += 1
    return replacements


def replace_xml_payload(
    data: bytes,
    mapping: dict[str, str],
    text_groups: tuple[tuple[str, set[str]], ...],
) -> tuple[bytes, int]:
    raw_text = data.decode("utf-8", errors="ignore")
    raw_replaced = replace_placeholders(raw_text, mapping)
    raw_changed = 1 if raw_replaced != raw_text else 0

    try:
        root = ET.fromstring(raw_replaced.encode("utf-8"))
    except ET.ParseError:
        return raw_replaced.encode("utf-8"), raw_changed

    node_changes = 0
    for text_tag, container_tags in text_groups:
        node_changes += replace_in_text_nodes(root, text_tag, mapping, container_tags)

    if raw_changed or node_changes:
        return ET.tostring(root, encoding="utf-8", xml_declaration=True), raw_changed + node_changes
    return data, 0


def cell_text(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
    if cell_type == "s" and value_node is not None and value_node.text:
        try:
            idx = int(value_node.text)
        except ValueError:
            return ""
        return shared[idx] if idx < len(shared) else ""
    if cell_type == "inlineStr":
        return "".join(
            node.text or ""
            for node in cell.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
        )
    return value_node.text if value_node is not None and value_node.text else ""


def set_cell_text(cell: ET.Element, value: str) -> None:
    for child in list(cell):
        cell.remove(child)
    cell.attrib["t"] = "inlineStr"
    inline = ET.SubElement(cell, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}is")
    text = ET.SubElement(inline, "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
    text.text = value


def fill_docx(source: Path, destination: Path, mapping: dict[str, str]) -> int:
    replacements = 0
    with zipfile.ZipFile(source, "r") as zin:
        out_buffer = io.BytesIO()
        with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(".xml"):
                    data, changed = replace_xml_payload(
                        data,
                        mapping,
                        (
                            (
                                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t",
                                {"{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"},
                            ),
                        ),
                    )
                    replacements += changed
                elif item.filename.endswith(".rels"):
                    text = data.decode("utf-8", errors="ignore")
                    new_text = replace_placeholders(text, mapping)
                    if new_text != text:
                        replacements += 1
                        data = new_text.encode("utf-8")
                zout.writestr(item, data)
        destination.write_bytes(out_buffer.getvalue())
    return replacements


def fill_xlsx(source: Path, destination: Path, mapping: dict[str, str]) -> int:
    changed = 0
    with zipfile.ZipFile(source, "r") as zin:
        out_buffer = io.BytesIO()
        with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            shared: list[str] = []
            shared_path = "xl/sharedStrings.xml"
            if shared_path in zin.namelist():
                ss_root = ET.fromstring(zin.read(shared_path))
                for si in ss_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                    parts = [t.text or "" for t in si.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                    shared.append("".join(parts))

            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.startswith("xl/worksheets/") and item.filename.endswith(".xml"):
                    root = ET.fromstring(data)
                    for row in root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row"):
                        cells = row.findall("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c")
                        values = [cell_text(cell, shared) for cell in cells]
                        if len(values) >= 2:
                            label = values[0].strip()
                            canonical_label = canonical_key(label)
                            for key, new_value in mapping.items():
                                if not new_value:
                                    continue
                                if (
                                    normalize_key(label) == normalize_key(key)
                                    or normalize_key(canonical_label) == normalize_key(canonical_key(key))
                                    or normalize_key(key) in normalize_key(label)
                                ):
                                    set_cell_text(cells[1], new_value)
                                    changed += 1
                                    break
                    changed += replace_single_text_nodes(
                        root,
                        "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t",
                        mapping,
                    )
                    data = ET.tostring(root, encoding="utf-8")
                elif item.filename == shared_path:
                    ss_root = ET.fromstring(zin.read(shared_path))
                    for si in ss_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"):
                        changed += replace_in_text_nodes(
                            si,
                            "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t",
                            mapping,
                            {"{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"},
                        )
                    data = ET.tostring(ss_root, encoding="utf-8")
                elif item.filename.endswith(".xml"):
                    data, xml_changed = replace_xml_payload(
                        data,
                        mapping,
                        (
                            (
                                "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t",
                                {"{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"},
                            ),
                        ),
                    )
                    changed += xml_changed
                zout.writestr(item, data)
        destination.write_bytes(out_buffer.getvalue())
    return changed


def fill_pptx(source: Path, destination: Path, mapping: dict[str, str]) -> int:
    replacements = 0
    with zipfile.ZipFile(source, "r") as zin:
        out_buffer = io.BytesIO()
        with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(".xml"):
                    data, changed = replace_xml_payload(
                        data,
                        mapping,
                        (
                            (
                                "{http://schemas.openxmlformats.org/drawingml/2006/main}t",
                                {"{http://schemas.openxmlformats.org/drawingml/2006/main}p"},
                            ),
                        ),
                    )
                    replacements += changed
                elif item.filename.endswith(".rels"):
                    text = data.decode("utf-8", errors="ignore")
                    new_text = replace_placeholders(text, mapping)
                    if new_text != text:
                        replacements += 1
                        data = new_text.encode("utf-8")
                zout.writestr(item, data)
        destination.write_bytes(out_buffer.getvalue())
    return replacements


def safe_filename_part(value: str, fallback: str = "filled") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", value or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    return cleaned or fallback


def filled_copy_suffix(mapping: dict[str, str]) -> str:
    surname = (
        mapping.get("\u0424\u0430\u043c\u0438\u043b\u0438\u044f")
        or mapping.get("\u0424\u0430\u043c\u0438\u043b\u0438\u044f \u0440\u0430\u0431\u043e\u0442\u043d\u0438\u043a\u0430")
        or ""
    )
    if not surname and mapping.get("\u0424\u0418\u041e"):
        surname = mapping["\u0424\u0418\u041e"].split()[0]
    return safe_filename_part(surname)


def fill_documents(documents: list[Path], fields: list[dict[str, str]]) -> dict[str, Any]:
    mapping = alias_fields({item["name"]: item["value"] for item in fields if item.get("name") and item.get("value")})
    copy_suffix = filled_copy_suffix(mapping)
    results = []
    for doc in documents:
        ext = doc.suffix.lower()
        if ext not in {".docx", ".xlsx", ".pptx"}:
            results.append({"path": str(doc), "ok": False, "error": "Пока поддерживается заполнение только DOCX, XLSX и PPTX"})
            continue

        temp_out = doc.with_name(doc.stem + "_" + copy_suffix + doc.suffix)
        try:
            if ext == ".docx":
                count = fill_docx(doc, temp_out, mapping)
            elif ext == ".xlsx":
                count = fill_xlsx(doc, temp_out, mapping)
            else:
                count = fill_pptx(doc, temp_out, mapping)
            results.append({"path": str(doc), "ok": True, "replacements": count, "filled_copy": str(temp_out)})
        except Exception as exc:
            results.append({"path": str(doc), "ok": False, "error": str(exc)})

    ok_count = sum(1 for r in results if r.get("ok"))
    return {"ok": ok_count > 0, "results": results, "filled": ok_count}


def main() -> None:
    if len(sys.argv) == 1:
        emit(doctor())
        return

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")

    extract_cmd = sub.add_parser("extract")
    extract_cmd.add_argument("--sample", required=True)
    extract_cmd.add_argument("--kind", default="Удостоверение личности")

    fill_cmd = sub.add_parser("fill")
    fill_cmd.add_argument("--documents", help="JSON array of document paths")
    fill_cmd.add_argument("--fields", help="JSON array of {name,value}")
    fill_cmd.add_argument("--documents-file", help="Path to JSON file with document paths")
    fill_cmd.add_argument("--fields-file", help="Path to JSON file with fields")

    args = parser.parse_args()

    if args.command == "doctor":
        emit(doctor())
        return

    if args.command == "extract":
        sample = Path(args.sample)
        if not sample.exists():
            emit_error(f"Файл образца не найден: {sample}")
        emit(extract_identity(sample, args.kind))
        return

    if args.command == "fill":
        if not args.documents_file and not args.documents:
            emit_error("Укажите --documents или --documents-file")
        if not args.fields_file and not args.fields:
            emit_error("Укажите --fields или --fields-file")

        if args.documents_file:
            documents = [Path(p) for p in json.loads(Path(args.documents_file).read_text(encoding="utf-8"))]
        else:
            documents = [Path(p) for p in json.loads(args.documents)]

        if args.fields_file:
            fields = json.loads(Path(args.fields_file).read_text(encoding="utf-8"))
        else:
            fields = json.loads(args.fields)
        if isinstance(fields, dict) and isinstance(fields.get("fields"), list):
            fields = fields["fields"]

        emit(fill_documents(documents, fields))


if __name__ == "__main__":
    main()
