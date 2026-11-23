"""Word export only: the desktop app never exports transcript JSON."""
from datetime import datetime
from pathlib import Path
import os
import re
import tempfile

from desktop.transcript import Turn, timestamp


def _clean(text: str) -> str:
    # Word XML cannot contain most ASCII control characters.
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text))


def export_word(source: Path, destination: Path, turns: list[Turn], language: str,
                duration: float, model: str) -> Path:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    destination.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", source.stem).strip(" .")[:120] or "Запись"
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.8)
    section.left_margin = section.right_margin = Inches(0.85)
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(11)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.12
    for style_name in ("Title", "Heading 1", "Heading 2"):
        document.styles[style_name].font.color.rgb = RGBColor(0, 0, 0)
    document.add_paragraph("Расшифровка записи", "Title")
    document.add_paragraph(_clean(source.name))
    document.add_paragraph(
        f"Длительность: {timestamp(duration)}   Язык: {language}\n"
        f"Модель: {model}   Создано: {datetime.now():%d.%m.%Y %H:%M}"
    )
    document.add_paragraph(
        "Автоматическая расшифровка с разделением говорящих. "
        "Время указано от начала исходной записи. Метки участников условные; "
        "ошибки распознавания и разделения голосов требуют проверки."
    )
    document.add_paragraph("Текст записи", "Heading 1")
    names: dict[str, str] = {}
    for turn in turns:
        if turn.speaker == "UNKNOWN":
            speaker = "Говорящий не определён"
        else:
            if turn.speaker not in names:
                names[turn.speaker] = f"Участник {len(names) + 1}"
            speaker = names[turn.speaker]
        header = document.add_paragraph()
        header.paragraph_format.keep_with_next = True
        header.add_run(f"[{timestamp(turn.start)} — {timestamp(turn.end)}]  {speaker}").bold = True
        document.add_paragraph(_clean(turn.text))
    if not turns:
        document.add_paragraph("Речь в записи не обнаружена.")
    footer = section.footer.paragraphs[0]
    footer.alignment = 2
    footer.add_run("Страница ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    # Publish only complete documents, even if the worker is stopped while saving.
    handle, temporary = tempfile.mkstemp(prefix=".tbcm-", suffix=".tmp", dir=destination)
    os.close(handle)
    try:
        document.save(temporary)
        # Timestamp reflects saving, not the beginning of document construction.
        output = destination / f"расшифровка_{name}_{datetime.now():%Y-%m-%d_%H-%M-%S_%f}.docx"
        os.replace(temporary, output)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return output
