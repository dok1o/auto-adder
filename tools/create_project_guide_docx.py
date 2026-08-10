from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "AutoAdder_Project_Guide.docx"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_width(cell, width_dxa: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.first_child_found_in("w:tcW")
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width_dxa))
    tc_w.set(qn("w:type"), "dxa")


def add_hyperlink(paragraph, text: str, url: str):
    part = paragraph.part
    rel_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), rel_id)

    run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")

    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    r_pr.append(color)

    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    r_pr.append(underline)

    run.append(r_pr)
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    return hyperlink


def add_code(document: Document, text: str) -> None:
    p = document.add_paragraph()
    p.style = "Code"
    run = p.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)


def add_bullets(document: Document, items: list[str]) -> None:
    for item in items:
        p = document.add_paragraph(style="List Bullet")
        p.add_run(item)


def add_numbered(document: Document, items: list[str]) -> None:
    for item in items:
        p = document.add_paragraph(style="List Number")
        p.add_run(item)


def add_source(document: Document, title: str, url: str, note: str) -> None:
    p = document.add_paragraph(style="List Bullet")
    add_hyperlink(p, title, url)
    p.add_run(f" - {note}")


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths: list[int]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False

    hdr = table.rows[0].cells
    for index, header in enumerate(headers):
        set_cell_width(hdr[index], widths[index])
        set_cell_shading(hdr[index], "E8EEF5")
        paragraph = hdr[index].paragraphs[0]
        run = paragraph.add_run(header)
        run.bold = True

    for row_data in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row_data):
            set_cell_width(cells[index], widths[index])
            cells[index].text = value

    document.add_paragraph()


def setup_styles(document: Document) -> None:
    section = document.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.25

    title = styles["Title"]
    title.font.name = "Calibri"
    title.font.size = Pt(24)
    title.font.bold = True
    title.font.color.rgb = RGBColor(11, 37, 69)
    title.paragraph_format.space_after = Pt(6)

    subtitle = styles["Subtitle"]
    subtitle.font.name = "Calibri"
    subtitle.font.size = Pt(12)
    subtitle.font.color.rgb = RGBColor(85, 85, 85)

    for name, size, color, before, after in [
        ("Heading 1", 16, RGBColor(46, 116, 181), 18, 10),
        ("Heading 2", 13, RGBColor(46, 116, 181), 14, 7),
        ("Heading 3", 12, RGBColor(31, 77, 120), 10, 5),
    ]:
        style = styles[name]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = color
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)

    code = styles.add_style("Code", 1)
    code.font.name = "Consolas"
    code.font.size = Pt(9)
    code.paragraph_format.left_indent = Inches(0.25)
    code.paragraph_format.space_before = Pt(3)
    code.paragraph_format.space_after = Pt(6)


def build() -> None:
    document = Document()
    setup_styles(document)

    document.add_paragraph("Auto Adder: подробное руководство по проекту", style="Title")
    document.add_paragraph(
        "Архитектура, назначение файлов, сборка релиза, безопасность и учебная карта.",
        style="Subtitle",
    )

    p = document.add_paragraph()
    p.add_run("Версия документа: ").bold = True
    p.add_run("0.2 / рабочий релиз")
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT

    document.add_heading("1. Коротко: что это за проект", level=1)
    document.add_paragraph(
        "Auto Adder - это локальное Windows-приложение для переноса данных из образца "
        "документа в кадровые, налоговые и похожие офисные документы. Пользователь "
        "выбирает образец, приложение извлекает ИИН, ФИО, дату рождения, номер документа "
        "и другие поля, затем заполняет DOCX, XLSX и PPTX."
    )
    add_code(
        document,
        "Образец -> Python engine -> JSON с полями -> Win32 UI -> заполнение DOCX/XLSX/PPTX",
    )

    document.add_heading("2. Архитектура", level=1)
    add_table(
        document,
        ["Часть", "Где лежит", "За что отвечает"],
        [
            ["Python engine", "engine/auto_adder_engine.py", "Извлечение данных, нормализация полей, заполнение Office-файлов."],
            ["Windows UI", "cpp/AutoAdderWin.cpp", "Окно приложения, кнопки, список документов, запуск engine и показ результата."],
            ["Installer", "setup/AutoAdderSetup.cpp", "Установка в LocalAppData, ярлык на рабочем столе, запуск приложения."],
            ["Build scripts", "tools/*.ps1", "Сборка exe, portable zip и итогового установщика."],
            ["Release output", "dist/AutoAdderSetup.exe", "Главный файл, который скачивает клиент."],
        ],
        [1800, 2600, 4960],
    )

    document.add_heading("3. Как работает engine", level=1)
    document.add_paragraph(
        "Engine - это командная Python-программа с режимами doctor, extract и fill. "
        "Интерфейс C++ запускает ее как отдельный процесс и получает JSON-ответ."
    )
    document.add_heading("3.1 Режим doctor", level=2)
    document.add_paragraph("Проверяет, какой Python используется и доступны ли нужные модули.")
    add_code(document, "python engine/auto_adder_engine.py doctor")

    document.add_heading("3.2 Режим extract", level=2)
    document.add_paragraph(
        "Извлекает данные из образца. Источником может быть TXT/CSV, PDF с текстовым слоем, "
        "PDF/изображение через OCR или barcode, а также уже заполненные DOCX/XLSX."
    )
    add_code(document, "python engine/auto_adder_engine.py extract --sample path\\to\\sample.pdf --kind \"Удостоверение личности\"")

    document.add_heading("3.3 Режим fill", level=2)
    document.add_paragraph(
        "Берет список документов и словарь полей, затем заполняет документы. Перед изменением "
        "создаются backup-файлы, а результат сохраняется рядом с исходником."
    )
    add_code(document, "python engine/auto_adder_engine.py fill --documents-file docs.json --fields-file fields.json")

    document.add_heading("4. Почему DOCX/XLSX/PPTX можно заполнять без Office", level=1)
    document.add_paragraph(
        "Современные Office-файлы являются Open XML-документами: внутри это ZIP-контейнер "
        "с XML-файлами. Поэтому engine может читать и менять XML напрямую через zipfile и "
        "xml.etree.ElementTree. Это позволяет работать локально и не требовать установленный Microsoft Office."
    )

    document.add_heading("5. Как работает C++ приложение", level=1)
    add_bullets(
        document,
        [
            "Создает обычное Win32-окно через Windows API.",
            "Показывает список документов, поле выбора образца и таблицу извлеченных значений.",
            "Ищет Python рядом с приложением: python/python.exe, .venv или системный Python.",
            "Запускает engine через CreateProcessW.",
            "Получает JSON из stdout и превращает его в поля интерфейса.",
            "При заполнении передает engine список документов и текущие поля.",
        ],
    )

    document.add_heading("6. Как работает установщик", level=1)
    add_numbered(
        document,
        [
            "AutoAdderSetup.exe содержит внутри portable zip.",
            "При запуске достает zip во временную папку.",
            "Распаковывает его через tar.exe.",
            "Ищет AutoAdder.exe внутри распакованной структуры.",
            "Копирует приложение в %LOCALAPPDATA%\\AutoAdder.",
            "Создает ярлык Auto Adder.lnk на рабочем столе.",
            "Запускает AutoAdder.exe.",
        ],
    )

    document.add_heading("7. Как собрать релиз", level=1)
    document.add_paragraph("Главная команда сборки:")
    add_code(document, "powershell -NoProfile -ExecutionPolicy Bypass -File tools\\build_installer.ps1 -Version 0.2")
    document.add_paragraph("После сборки главный файл для клиентов:")
    add_code(document, "dist\\AutoAdderSetup.exe")

    document.add_heading("8. Как публиковать на GitHub", level=1)
    add_numbered(
        document,
        [
            "Код проекта пушится в репозиторий.",
            "Большие файлы из dist не коммитятся, потому что GitHub ограничивает обычные файлы 100 MB.",
            "На GitHub создается Release, например v0.2.",
            "В Release вручную загружается dist\\AutoAdderSetup.exe.",
            "Клиент получает прямую ссылку releases/latest/download/AutoAdderSetup.exe.",
        ],
    )
    add_code(document, "https://github.com/dok1o/auto-adder/releases/latest/download/AutoAdderSetup.exe")

    document.add_heading("9. Конфиденциальность", level=1)
    add_bullets(
        document,
        [
            "Документы обрабатываются локально на ПК пользователя.",
            "В коде нет отправки документов, ИИН, ФИО или извлеченных полей в интернет.",
            "Нет OpenAI API, облачных API, telemetry или analytics.",
            "Portable-релиз содержит Python и зависимости, поэтому обычный запуск не требует интернета.",
            "Результаты и backup-файлы остаются рядом с выбранными документами пользователя.",
        ],
    )

    document.add_heading("10. Что учить, чтобы понимать проект", level=1)
    add_table(
        document,
        ["Тема", "Зачем нужна в проекте"],
        [
            ["Python basics", "Понимать engine, словари, списки, функции, файлы."],
            ["argparse/json/re/pathlib", "CLI-команды, JSON-обмен с C++, регулярки и пути."],
            ["Open XML", "Понимать, почему DOCX/XLSX/PPTX можно менять как ZIP + XML."],
            ["PDF extraction", "Доставать текст из PDF через pypdf и PyMuPDF."],
            ["OCR/barcodes", "Работать с изображениями, Tesseract и pyzbar."],
            ["Win32 C++", "Понимать окно, кнопки, message loop и запуск процессов."],
            ["Windows installer", "Понимать resources, LocalAppData и ярлыки .lnk."],
            ["GitHub Releases", "Правильно доставлять exe клиентам."],
        ],
        [2600, 6760],
    )

    document.add_heading("11. Письменные источники", level=1)
    sources = [
        ("Python argparse", "https://docs.python.org/3.12/howto/argparse.html", "командные режимы doctor/extract/fill."),
        ("Python regular expressions", "https://docs.python.org/3.10/howto/regex.html", "поиск ИИН, дат и полей в тексте."),
        ("Python JSON", "https://docs.python.org/3.14/library/json.html", "обмен данными между C++ UI и Python engine."),
        ("Python ElementTree", "https://docs.python.org/3.15/library/xml.etree.elementtree.html", "редактирование XML внутри Office-файлов."),
        ("pypdf text extraction", "https://pypdf.readthedocs.io/en/stable/user/extract-text.html", "извлечение текстового слоя из PDF."),
        ("PyMuPDF text recipes", "https://pymupdf.readthedocs.io/en/latest/recipes-text.html", "PDF fallback, рендеринг страниц и извлечение текста."),
        ("Microsoft Open XML", "https://learn.microsoft.com/it-it/office/open-xml/open-xml-sdk?redirectedfrom=MSDN", "структура DOCX/XLSX/PPTX как Open XML."),
        ("openpyxl tutorial", "https://openpyxl.readthedocs.io/en/stable/tutorial.html", "работа с Excel-файлами."),
        ("python-pptx docs", "https://python-pptx.readthedocs.io/en/stable/", "работа с PowerPoint-файлами."),
        ("pyzbar", "https://pypi.org/project/pyzbar/", "чтение barcode/QR/PDF417."),
        ("Win32 and C++", "https://learn.microsoft.com/en-us/windows/win32/learnwin32/learn-to-program-for-windows", "основа Windows desktop-приложений."),
        ("CreateWindowExW", "https://learn.microsoft.com/ru-ru/windows/win32/api/winuser/nf-winuser-createwindowexw", "создание окон Win32."),
        ("Shell links", "https://learn.microsoft.com/ru-ru/windows/win32/shell/links", "создание ярлыков .lnk."),
        ("GitHub Releases", "https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository?source=post_page---------------------------", "создание релиза и загрузка exe."),
        ("GitHub large files", "https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository?platform=linux", "почему dist не хранится в Git."),
    ]
    for title, url, note in sources:
        add_source(document, title, url, note)

    document.add_heading("12. Видео и практические материалы", level=1)
    videos = [
        ("The Boring Python Office Talk", "https://pyvideo.org/europython-2018/the-boring-python-office-talk-automate-powerpoint-excel-and-pdf-with-python.html", "обзор автоматизации Office/PDF через Python."),
        ("PyImageSearch OCR + Tesseract", "https://pyimagesearch.com/2018/09/17/opencv-ocr-and-text-recognition-with-tesseract/", "практика OCR и распознавания текста."),
        ("Microsoft Win32 learning path", "https://learn.microsoft.com/en-us/windows/win32/learnwin32/learn-to-program-for-windows", "официальный учебный путь по Win32; видео можно искать по этому названию."),
        ("GitHub Releases guide", "https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository?source=post_page---------------------------", "официальный гайд; на YouTube искать: GitHub Releases upload exe asset tutorial."),
    ]
    for title, url, note in videos:
        add_source(document, title, url, note)

    document.add_heading("13. Что улучшать дальше", level=1)
    add_bullets(
        document,
        [
            "Исправить кодировку русских строк в engine и тестовых данных, чтобы исходники были читаемыми.",
            "Добавить нормальные автоматические тесты для extract/fill.",
            "Уменьшить размер portable Python, оставив только реально нужные библиотеки.",
            "Добавить подпись установщика, чтобы Windows меньше пугала клиента.",
            "Сделать версионирование: v0.3, v0.4 и changelog.",
            "Добавить экран настроек и путь для логов/диагностики.",
        ],
    )

    footer = document.sections[0].footer.paragraphs[0]
    footer.text = "Auto Adder project guide"
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    OUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
