from __future__ import annotations

import html
import io
import os
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether
from reportlab.lib.utils import ImageReader


# За замовчуванням — Times New Roman з backend/fonts/ (якщо є всі 4 TTF), інакше — DejaVuSerif з ОС.
FONT_NAME = "TimesNewRoman"
FONT_BOLD = "TimesNewRoman-Bold"
FONT_ITALIC = "TimesNewRoman-Italic"
FONT_BOLD_ITALIC = "TimesNewRoman-BoldItalic"

HEADER_H = 40 * mm
TABLE_SIDE_GAP = 2 * mm
# Під таблицею: поле ПІБ — відступ від правого краю текстового поля (як на бланку).
SIG_PIB_RIGHT_MARGIN = 10 * mm
# Горизонтальна відстань між підкресленими полями «ПІБ» і «Посада» (шапка та блок підписів).
PIB_POSADA_HORIZONTAL_GAP = 30 * mm


def _candidate_font_paths() -> list[str]:
    candidates: list[str] = []

    # 1) Явна настройка в settings.py (файл або каталог)
    configured = getattr(settings, "REPORTLAB_FONT_PATH", None)
    if configured:
        root = str(configured)
        if os.path.isdir(root):
            for fname in (
                "times.ttf",
                "timesbd.ttf",
                "timesi.ttf",
                "timesbi.ttf",
                "DejaVuSerif.ttf",
                "DejaVuSerif-Bold.ttf",
                "DejaVuSerif-Italic.ttf",
                "DejaVuSerif-BoldItalic.ttf",
            ):
                candidates.append(os.path.join(root, fname))
        else:
            candidates.append(root)

    # 2) Локальна папка проєкту: BASE_DIR/fonts/...
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir:
        fonts_dir = os.path.join(str(base_dir), "fonts")
        candidates.extend(
            [
                os.path.join(fonts_dir, "times.ttf"),
                os.path.join(fonts_dir, "timesbd.ttf"),
                os.path.join(fonts_dir, "timesi.ttf"),
                os.path.join(fonts_dir, "timesbi.ttf"),
                os.path.join(fonts_dir, "DejaVuSerif.ttf"),
                os.path.join(fonts_dir, "DejaVuSerif-Bold.ttf"),
                os.path.join(fonts_dir, "DejaVuSerif-Italic.ttf"),
                os.path.join(fonts_dir, "DejaVuSerif-BoldItalic.ttf"),
                os.path.join(fonts_dir, "dejavu", "DejaVuSerif.ttf"),
                os.path.join(fonts_dir, "dejavu", "DejaVuSerif-Bold.ttf"),
                os.path.join(fonts_dir, "dejavu", "DejaVuSerif-Italic.ttf"),
                os.path.join(fonts_dir, "dejavu", "DejaVuSerif-BoldItalic.ttf"),
            ]
        )

    # 3) Типові системні шляхи Linux (Render)
    candidates.extend(
        [
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-BoldItalic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerifCondensed.ttf",
        ]
    )

    # 4) Типові системні шляхи Windows (на випадок локального запуску)
    candidates.extend(
        [
            r"C:\Windows\Fonts\times.ttf",
            r"C:\Windows\Fonts\timesbd.ttf",
            r"C:\Windows\Fonts\timesi.ttf",
            r"C:\Windows\Fonts\timesbi.ttf",
            r"C:\Windows\Fonts\DejaVuSerif.ttf",
        ]
    )

    return candidates


def _existing_font_basemap() -> dict[str, str]:
    """basename(lower) -> перший існуючий шлях."""
    out: dict[str, str] = {}
    for p in _candidate_font_paths():
        if not p or not os.path.isfile(p):
            continue
        key = os.path.basename(p).lower()
        out.setdefault(key, p)
    return out


def ensure_cyrillic_font_registered() -> None:
    global FONT_NAME, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC

    registered = set(pdfmetrics.getRegisteredFontNames())
    if {FONT_NAME, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC}.issubset(registered):
        return

    files = _existing_font_basemap()

    times_need = {
        "TimesNewRoman": "times.ttf",
        "TimesNewRoman-Bold": "timesbd.ttf",
        "TimesNewRoman-Italic": "timesi.ttf",
        "TimesNewRoman-BoldItalic": "timesbi.ttf",
    }
    dejavu_need = {
        "DejaVuSerif": "dejavuserif.ttf",
        "DejaVuSerif-Bold": "dejavuserif-bold.ttf",
        "DejaVuSerif-Italic": "dejavuserif-italic.ttf",
        "DejaVuSerif-BoldItalic": "dejavuserif-bolditalic.ttf",
    }

    need: dict[str, str] = {}
    if all(files.get(bn) for bn in times_need.values()):
        FONT_NAME, FONT_BOLD = "TimesNewRoman", "TimesNewRoman-Bold"
        FONT_ITALIC, FONT_BOLD_ITALIC = "TimesNewRoman-Italic", "TimesNewRoman-BoldItalic"
        need = {reg: files[bn] for reg, bn in times_need.items()}
    elif all(files.get(bn) for bn in dejavu_need.values()):
        FONT_NAME, FONT_BOLD = "DejaVuSerif", "DejaVuSerif-Bold"
        FONT_ITALIC, FONT_BOLD_ITALIC = "DejaVuSerif-Italic", "DejaVuSerif-BoldItalic"
        need = {reg: files[bn] for reg, bn in dejavu_need.items()}
    else:
        fallback = next(iter(files.values()), None)
        if not fallback:
            raise RuntimeError(
                "Не знайдено шрифти для PDF. Додайте у backend/fonts/ усі файли "
                "times.ttf, timesbd.ttf, timesi.ttf, timesbi.ttf або покладіть DejaVuSerif*.ttf."
            )
        FONT_NAME, FONT_BOLD = "DejaVuSerif", "DejaVuSerif-Bold"
        FONT_ITALIC, FONT_BOLD_ITALIC = "DejaVuSerif-Italic", "DejaVuSerif-BoldItalic"
        need = {k: fallback for k in (FONT_NAME, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC)}

    for font_name, font_path in need.items():
        if font_name not in registered:
            pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

    pdfmetrics.registerFontFamily(
        FONT_NAME,
        normal=FONT_NAME,
        bold=FONT_BOLD,
        italic=FONT_ITALIC,
        boldItalic=FONT_BOLD_ITALIC,
    )


@dataclass(frozen=True)
class NonconformityRow:
    order_number: int
    description: str
    corrective_actions: str
    responsible: str
    due_date: Optional[date]
    # Лише для PDF «Звіт» (Ф-15-02): стовпчик «%»; у БД може бути порожнім.
    execution_percent: str = ""


@dataclass(frozen=True)
class PhotoItem:
    caption: str
    image_path: str


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    safe = (text or "").replace("\n", "<br/>")
    return Paragraph(safe, style)


def _scaled_platypus_image(image_path: str, *, max_width: float, max_height: float | None = None) -> Image:
    img_reader = ImageReader(image_path)
    iw, ih = img_reader.getSize()
    if not iw or not ih:
        return Image(image_path)  # на випадок дивних форматів

    scale_w = max_width / float(iw) if max_width else 1.0
    scale_h = (max_height / float(ih)) if (max_height is not None and max_height > 0) else 1.0
    scale = min(scale_w, scale_h, 1.0)

    w = float(iw) * scale
    h = float(ih) * scale
    img = Image(image_path, width=w, height=h)
    img.hAlign = "CENTER"
    return img


def _signature_line(
    *,
    value: str,
    caption: str,
    value_style: ParagraphStyle,
    caption_style: ParagraphStyle,
    line_thickness: float = 0.8,
    max_width: float | None = None,
    min_width: float = 28 * mm,
) -> Table:
    v = (value or "").strip()
    # Підкреслення рівно по тексту (без виходу за межі).
    text_w = pdfmetrics.stringWidth(v or " ", value_style.fontName, value_style.fontSize)
    target_w = text_w + 0.8 * mm
    if not v:
        target_w = min_width
    if max_width is not None:
        target_w = min(target_w, max_width)
    t = Table(
        [[_p(value or "", value_style)], [_p(caption, caption_style)]],
        colWidths=[target_w],
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LINEBELOW", (0, 0), (0, 0), line_thickness, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return t


def _two_signature_lines_row(
    *,
    layout_width: float,
    left_value: str,
    right_value: str,
    left_caption: str,
    right_caption: str,
    value_style: ParagraphStyle,
    caption_style: ParagraphStyle,
    max_width_frac: float = 0.30,
    min_width: float = 24 * mm,
    cell_pad_left: float = 5,
    cell_pad_right: float = 0,
    fixed_gap_between_fields: bool = False,
) -> Table:
    """Два поля з підкресленням по довжині тексту (як у шапці акту).

    fixed_gap_between_fields=True — ширина полів по тексту, між ними PIB_POSADA_HORIZONTAL_GAP
    (шапка акту: ПІБ і посада ближче одне до одного).

    fixed_gap_between_fields=False — рядок на всю ширину сторінки, праве поле вирівняне вправо
    (блок «Підписи» під таблицею, як на бланку).
    """
    mw = float(layout_width) * max_width_frac
    left = _signature_line(
        value=left_value or "",
        caption=left_caption,
        value_style=value_style,
        caption_style=caption_style,
        max_width=mw,
        min_width=min_width,
    )
    right = _signature_line(
        value=right_value or "",
        caption=right_caption,
        value_style=value_style,
        caption_style=caption_style,
        max_width=mw,
        min_width=min_width,
    )
    if fixed_gap_between_fields:
        # Фіксуємо X-позицію правого поля: ширина лівої колонки стала (mw),
        # тому "Посада" у шапці завжди починається в одному й тому ж місці.
        gap = float(PIB_POSADA_HORIZONTAL_GAP)
        left_col_w = mw
        right_col_w = max(1.0, float(layout_width) - left_col_w - gap)
        col_widths = [left_col_w, gap, right_col_w]
        align_right_col = "LEFT"
    else:
        col_widths = [
            layout_width * 0.45,
            layout_width * 0.10,
            layout_width * 0.45,
        ]
        align_right_col = "RIGHT"
    row = Table([[left, Spacer(1, 1), right]], colWidths=col_widths)
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (0, 0), "LEFT"),
                ("ALIGN", (2, 0), (2, 0), align_right_col),
                ("LEFTPADDING", (0, 0), (0, 0), cell_pad_left),
                ("LEFTPADDING", (1, 0), (1, 0), 0),
                ("LEFTPADDING", (2, 0), (2, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("RIGHTPADDING", (2, 0), (2, 0), cell_pad_right),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return row


def _draw_page_header(
    canv: pdfcanvas.Canvas,
    *,
    doc_kind: str = "act",
    branch: str,
    revision: str,
    report_date: date,
    site_name: str,
    page_num: int,
    page_count: int,
    left_margin: float,
    right_margin: float,
) -> None:
    def _fit_paragraph(text: str, *, base_size: float, min_size: float, width: float, height: float, style_kwargs: dict):
        """
        Підбирає розмір шрифту так, щоб Paragraph вмістився у (width x height).
        Якщо не вміщується навіть на min_size — повертає Paragraph з min_size (буде перенос).
        """
        size = base_size
        while size >= min_size:
            st = ParagraphStyle(
                f"_hdr_{id(text)}_{size}",
                fontName=FONT_NAME,
                fontSize=size,
                leading=max(size + 1.5, size * 1.15),
                **style_kwargs,
            )
            p = Paragraph(text or "", st)
            w, h = p.wrap(width, height)
            if h <= height + 0.1:
                return p
            size -= 0.5
        st = ParagraphStyle(
            f"_hdr_{id(text)}_min",
            fontName=FONT_NAME,
            fontSize=min_size,
            leading=max(min_size + 1.5, min_size * 1.15),
            **style_kwargs,
        )
        return Paragraph(text or "", st)

    page_w, page_h = A4
    x0 = left_margin
    x1 = page_w - right_margin
    w = x1 - x0

    # Відступ рамки від країв — використовуємо поля документа,
    # щоб рамка/шапка і контент були узгоджені.
    inset = min(left_margin, right_margin)
    y_top = page_h - inset
    y_bottom = inset
    y0 = y_top - HEADER_H

    # Макет як на фото: окремий рядок з назвою філії + таблиця 2х3 нижче
    col1 = w * 0.28
    col2 = w * 0.52
    col3 = w - col1 - col2

    branch_h = HEADER_H * 0.38
    grid_h = HEADER_H - branch_h
    # Нижній ряд — назва дільниці + підпис; більше висоти, ніж верхньому (формула/дати).
    row1 = grid_h * 0.44
    row2 = grid_h - row1

    # Рамка і сітка (суцільна рамка + внутрішні лінії)
    canv.saveState()
    canv.setStrokeColor(colors.black)
    canv.setLineWidth(0.8)

    # Загальна рамка сторінки (продовження від шапки)
    canv.rect(x0, y_bottom, w, y_top - y_bottom, stroke=1, fill=0)

    canv.rect(x0, y0, w, HEADER_H, stroke=1, fill=0)

    # Горизонтальна лінія між рядком філії та сіткою
    canv.line(x0, y0 + grid_h, x1, y0 + grid_h)
    # Вертикалі сітки тільки в нижній частині (як на фото)
    canv.line(x0 + col1, y0, x0 + col1, y0 + grid_h)
    canv.line(x0 + col1 + col2, y0, x0 + col1 + col2, y0 + grid_h)
    # Горизонталь між 2 рядками сітки
    canv.line(x0, y0 + row2, x1, y0 + row2)

    # Контент — через Table/Paragraph для переносів і гарантованого вміщення
    pad_x = 2.2 * mm
    pad_y = 1.2 * mm

    branch_p = _fit_paragraph(
        f"<b>{(branch or '').strip()}</b>",
        base_size=12,
        min_size=9,
        width=w - 2 * pad_x,
        height=branch_h - 2 * pad_y,
        style_kwargs={"alignment": 1},  # center
    )
    branch_tbl = Table([[branch_p]], colWidths=[w], rowHeights=[branch_h])
    branch_tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), pad_x),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad_x),
                ("TOPPADDING", (0, 0), (-1, -1), pad_y),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad_y),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    branch_tbl.wrapOn(canv, w, branch_h)
    branch_tbl.drawOn(canv, x0, y0 + grid_h)

    # Середня верхня комірка — як на фото (можна буде винести в поле пізніше)
    kind = (doc_kind or "act").strip().lower()
    if kind not in {"act", "report"}:
        kind = "act"
    mid_top_text = (
        "Ф-15-02 Звіт з перевірки виконання коригуючих дій з усунення виявлених невідповідностей"
        if kind == "report"
        else "Ф-15-01 Акт перевірки виробничої діяльності щодо дотримання вимог природоохоронного законодавства"
    )
    left_top = _fit_paragraph(
        f"Редакція документа: {revision or '-'}",
        base_size=12,
        min_size=9,
        width=col1 - 2 * pad_x,
        height=row1 - 2 * pad_y,
        style_kwargs={"alignment": 0},
    )
    mid_top = _fit_paragraph(
        f"<i>{mid_top_text}</i>",
        base_size=12,
        min_size=8.5,
        width=col2 - 2 * pad_x,
        height=row1 - 2 * pad_y,
        style_kwargs={"alignment": 1},
    )
    right_top = Paragraph("", ParagraphStyle("_hdr_empty", fontName=FONT_NAME, fontSize=12, leading=14))

    left_bottom = _fit_paragraph(
        "Діє з: “04” “06” 2018р",
        base_size=12,
        min_size=9,
        width=col1 - 2 * pad_x,
        height=row2 - 2 * pad_y,
        style_kwargs={"alignment": 0},
    )
    mid_bottom = _fit_paragraph(
        f"<b><u>{(site_name or '').strip()}</u></b><br/><font size='8'>(структурний підрозділ)</font>",
        base_size=12,
        min_size=8.5,
        width=col2 - 2 * pad_x,
        height=row2 - 2 * pad_y,
        style_kwargs={"alignment": 1},
    )
    right_bottom = _fit_paragraph(
        f"Сторінка {page_num} з {page_count}",
        base_size=12,
        min_size=9,
        width=col3 - 2 * pad_x,
        height=row2 - 2 * pad_y,
        style_kwargs={"alignment": 1},
    )

    grid_tbl = Table(
        [[left_top, mid_top, right_top], [left_bottom, mid_bottom, right_bottom]],
        colWidths=[col1, col2, col3],
        rowHeights=[row1, row2],
    )
    grid_tbl.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), pad_x),
                ("RIGHTPADDING", (0, 0), (-1, -1), pad_x),
                ("TOPPADDING", (0, 0), (-1, -1), pad_y),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad_y),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    grid_tbl.wrapOn(canv, w, grid_h)
    grid_tbl.drawOn(canv, x0, y0)
    canv.restoreState()


class _NumberedCanvas(pdfcanvas.Canvas):
    def __init__(self, *args, header_kwargs: dict, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []
        self._header_kwargs = header_kwargs

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for i, state in enumerate(self._saved_page_states, start=1):
            self.__dict__.update(state)
            _draw_page_header(self, page_num=i, page_count=page_count, **self._header_kwargs)
            super().showPage()
        super().save()


def _optional_date_cell(d: Optional[date], *, st: ParagraphStyle) -> Paragraph:
    """Порожня комірка без прочерку, якщо дату не задано."""
    if d:
        return _p(f"<b>{d:%d.%m.%Y}</b>", st)
    return Paragraph("", st)


def _vek_act_basis_paragraph(act_date: date, *, base: ParagraphStyle) -> Paragraph:
    """Дата у тексті підстав — дата складання акта ВЕК (не обов’язково та сама, що дата звіту)."""
    text = (
        "Акт перевірки виробничої діяльності з дотримання природоохоронного законодавства "
        f"від {act_date:%d.%m.%Y} – виробничий екологічний контроль (ВЕК)"
    )
    return _p(text, base)


def _uk_num_word_feminine(n: int) -> str:
    """Числівник для форми «N (слова) невідповідностей» (жіночий рід, 1–20)."""
    words = {
        1: "одна",
        2: "дві",
        3: "три",
        4: "чотири",
        5: "п'ять",
        6: "шість",
        7: "сім",
        8: "вісім",
        9: "дев'ять",
        10: "десять",
        11: "одинадцять",
        12: "дванадцять",
        13: "тринадцять",
        14: "чотирнадцять",
        15: "п'ятнадцять",
        16: "шістнадцять",
        17: "сімнадцять",
        18: "вісімнадцять",
        19: "дев'ятнадцять",
        20: "двадцять",
    }
    if n in words:
        return words[n]
    return str(n)


def _closure_conclusion_text(rows: list[tuple[str, str]], rd: date) -> str:
    """Текст «Кінцеве заключення» за рядками (коригуюча дія, yes|no)."""
    relevant: list[tuple[str, str]] = []
    for t, d in rows:
        ts = (t or "").strip()
        ds = (d or "").strip().lower()
        if not ts or ds not in ("yes", "no"):
            continue
        relevant.append((ts, ds))
    if not relevant:
        return ""
    total = len(relevant)
    yes_n = sum(1 for _, d in relevant if d == "yes")
    no_n = total - yes_n
    ds_fmt = f"{rd:%d.%m.%Y}"
    if no_n == 0:
        return f"Кінцеве заключення: усі невідповідності від {ds_fmt} закриті."
    if yes_n == 0:
        return f"Кінцеве заключення: невідповідності від {ds_fmt} не закриті."
    w = _uk_num_word_feminine(yes_n)
    return (
        f"Кінцеве заключення: {yes_n} ({w}) невідповідностей від {ds_fmt} закриті; "
        f"{no_n} залишаються відкритими."
    )


def build_environmental_report_pdf(
    *,
    doc_kind: str = "act",
    branch: str,
    revision: str,
    report_date: date,
    site_name: str,
    inspection_form: str,
    inspector_full_name: str,
    inspector_position: str,
    unit_representative_full_name: str,
    unit_representative_position: str,
    nonconformities: Iterable[NonconformityRow],
    photo_items: Iterable[PhotoItem],
    additional_unit_representatives: Iterable[tuple[str, str]] | None = None,
    act_date: Optional[date] = None,
    analysis_proposed_vek: Optional[date] = None,
    analysis_proposed_check: Optional[date] = None,
    analysis_actual: Optional[date] = None,
    analysis_reason_text: str = "",
    analysis_violation: str = "",
    analysis_corrective_action: str = "",
    analysis_cause_rows: Iterable[tuple[str, str, str]] | None = None,
    closure_rows: Iterable[tuple[str, str]] | None = None,
    closure_comments: str = "",
) -> bytes:
    ensure_cyrillic_font_registered()

    kind = (doc_kind or "act").strip().lower()
    if kind not in {"act", "report"}:
        kind = "act"

    # У тексті акту ВЕК у підставах — дата складання акта; якщо не передано — як раніше (дата звіту).
    basis_date = act_date if act_date is not None else report_date

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm + HEADER_H + 4 * mm,
        bottomMargin=8 * mm,
        title="Environmental report",
    )

    styles = getSampleStyleSheet()
    base = ParagraphStyle(
        "Base",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=14.5,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=14.5,
        spaceAfter=8,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=14.5,
        spaceBefore=10,
        spaceAfter=6,
    )
    title_1 = ParagraphStyle(
        "Title1",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=14.5,
        alignment=1,  # center
        spaceAfter=0,
    )
    title_2 = ParagraphStyle(
        "Title2",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=14.5,
        alignment=1,  # center
        spaceAfter=0,
    )
    caption_sm = ParagraphStyle(
        "CaptionSm",
        parent=base,
        fontSize=8,
        leading=9.5,
        alignment=1,  # center
        textColor=colors.black,
    )
    label_b = ParagraphStyle(
        "LabelB",
        parent=base,
        fontSize=12,
        leading=14.5,
    )
    value_b = ParagraphStyle(
        "ValueB",
        parent=base,
        fontSize=12,
        leading=14.5,
    )
    small = ParagraphStyle(
        "Small",
        parent=base,
        fontSize=12,
        leading=14.5,
    )
    table_header = ParagraphStyle(
        "TableHeader",
        parent=small,
        alignment=1,  # center
        leading=14.5,
    )
    sig_label = ParagraphStyle(
        "SigLabel",
        parent=small,
        fontSize=12,
        leading=14.5,
        alignment=0,
        spaceAfter=2,
    )

    story = []

    inspector_position = (inspector_position or "").strip() or "Провідний Еколог"
    unit_rep_position = (unit_representative_position or "").strip() or "Начальник дільниці"

    if kind == "report":
        # Ф-15-02 — одна суцільна таблиця без проміжків між блоками (межі спільні).
        story.append(_p("<b><i>Звіт</i></b>", title_1))
        _site_html = html.escape((site_name or "").strip() or "—", quote=False)
        story.append(
            _p(
                "<i><u>"
                f"перевірки виробничої діяльності ({_site_html}) "
                "з дотримання природоохоронного законодавства – виробничий екологічний контроль"
                "</u></i>",
                title_2,
            )
        )
        story.append(Spacer(1, 10))

        banner_style = ParagraphStyle(
            "BannerF15",
            parent=small,
            alignment=1,
            fontName=FONT_BOLD,
        )
        cell_center = ParagraphStyle(
            "F15StagePctCenter",
            parent=base,
            alignment=1,
            leading=14.5,
        )

        W = doc.width
        six = [W / 6] * 6

        rows_nc = list(nonconformities)

        grid_data: list[list] = []

        # рядок 0–1: підстави / назва / дата
        grid_data.append(
            [
                _p("<b>Підстави для звіту (акт ВЕК)</b>", table_header),
                "",
                "",
                _p("<b>Назва підрозділу</b>", table_header),
                "",
                _p("<b>Дата звіту</b>", table_header),
            ]
        )
        grid_data.append(
            [
                _vek_act_basis_paragraph(basis_date, base=base),
                "",
                "",
                _p((site_name or "").strip(), cell_center),
                "",
                _p(f"<b>{report_date:%d.%m.%Y}</b>", cell_center),
            ]
        )

        # рядок 2–3: перевіряючий | представник (по 3 колонки = 50/50)
        grid_data.append(
            [
                _p("<b>Посада та ПІБ перевіряючого</b>", table_header),
                "",
                "",
                _p("<b>Представник підрозділу (посада та ПІБ)</b>", table_header),
                "",
                "",
            ]
        )
        grid_data.append(
            [
                _p(f"{inspector_position} {inspector_full_name}".strip(), cell_center),
                "",
                "",
                _p(f"{unit_rep_position} {unit_representative_full_name}".strip(), cell_center),
                "",
                "",
            ]
        )

        # рядок 4: банер
        grid_data.append(
            [
                _p("<b>СПОСТЕРЕЖУВАНА НЕВІДПОВІДНІСТЬ</b>", banner_style),
                "",
                "",
                "",
                "",
                "",
            ]
        )

        # рядок 5: праворуч один підпис «Стадія виконання %» на всю ширину двох колонок даних
        grid_data.append(
            [
                _p("<b>Виявлена при ВЕК (дата)</b>", table_header),
                "",
                "",
                "",
                _p("<b>Стадія виконання %</b>", table_header),
                "",
            ]
        )

        # рядки даних
        if not rows_nc:
            grid_data.append(
                [
                    _p("—", base),
                    "",
                    "",
                    "",
                    _p("—", cell_center),
                    _p("—", cell_center),
                ]
            )
        else:
            for r in rows_nc:
                pct = (r.execution_percent or "").strip()
                if not pct:
                    pct = "100"
                stage = (r.corrective_actions or "").strip() or "—"
                desc = (r.description or "").strip() or "—"
                grid_data.append(
                    [
                        _p(desc, base),
                        "",
                        "",
                        "",
                        _p(stage, cell_center),
                        _p(pct, cell_center),
                    ]
                )

        main_tbl = Table(grid_data, colWidths=six, repeatRows=6)
        main_tbl.hAlign = "CENTER"
        last_row = len(grid_data) - 1
        ts = [
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("SPAN", (0, 0), (2, 0)),
            ("SPAN", (3, 0), (4, 0)),
            ("SPAN", (0, 1), (2, 1)),
            ("SPAN", (3, 1), (4, 1)),
            ("SPAN", (0, 2), (2, 2)),
            ("SPAN", (3, 2), (5, 2)),
            ("SPAN", (0, 3), (2, 3)),
            ("SPAN", (3, 3), (5, 3)),
            ("SPAN", (0, 4), (5, 4)),
            ("BACKGROUND", (0, 4), (5, 4), colors.whitesmoke),
            ("SPAN", (0, 5), (3, 5)),
            ("SPAN", (4, 5), (5, 5)),
            ("BACKGROUND", (0, 5), (-1, 5), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (0, 0), (-1, 3), "CENTER"),
            ("ALIGN", (0, 4), (5, 4), "CENTER"),
            ("ALIGN", (0, 5), (-1, 5), "CENTER"),
            ("ALIGN", (0, 1), (2, 1), "LEFT"),
            ("ALIGN", (3, 1), (4, 1), "CENTER"),
            ("ALIGN", (5, 1), (5, 1), "CENTER"),
            ("ALIGN", (0, 2), (2, 2), "CENTER"),
            ("ALIGN", (3, 2), (5, 2), "CENTER"),
            ("ALIGN", (0, 3), (2, 3), "CENTER"),
            ("ALIGN", (3, 3), (5, 3), "CENTER"),
            ("ALIGN", (0, 6), (3, last_row), "LEFT"),
            ("ALIGN", (4, 6), (5, last_row), "CENTER"),
            ("TOPPADDING", (0, 4), (5, 4), 6),
            ("BOTTOMPADDING", (0, 4), (5, 4), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        for ri in range(6, len(grid_data)):
            ts.append(("SPAN", (0, ri), (3, ri)))

        main_tbl.setStyle(TableStyle(ts))

        story.append(main_tbl)

        # «Аналіз причин невідповідностей і коригуючі дії» — після блоку невідповідностей
        story.append(Spacer(1, 14))
        analysis_title_st = ParagraphStyle(
            "ReportAnalysisTitle",
            parent=base,
            fontName=FONT_BOLD,
            fontSize=12,
            leading=14.5,
            alignment=1,
            spaceAfter=4,
        )
        story.append(
            _p("<b>АНАЛІЗ ПРИЧИН НЕВІДПОВІДНОСТЕЙ І КОРИГУЮЧІ ДІЇ</b>", analysis_title_st)
        )
        story.append(_p("<i>(заповнюється представниками підрозділу)</i>", title_2))
        story.append(Spacer(1, 6))

        ad_w = doc.width
        acw = [ad_w * 0.25, ad_w * 0.25, ad_w * 0.25, ad_w * 0.25]
        _rep_line = f"{unit_rep_position} {unit_representative_full_name}".strip()
        rep_cell = (
            _p(f"<b>{html.escape(_rep_line, quote=False)}</b>", cell_center)
            if _rep_line
            else Paragraph("", cell_center)
        )

        an_data = [
            [
                _p("<b>Запропонована дата виконання</b>", table_header),
                "",
                _p(
                    "<b>Реальна дата виконання (заповнюється при повному обсязі виконання)</b>",
                    table_header,
                ),
                _p("<b>Представник підрозділу</b>", table_header),
            ],
            [
                _p("<b>Під час проведення ВЕК</b>", table_header),
                _p("<b>При перевірці виконання</b>", table_header),
                "",
                "",
            ],
            [
                _optional_date_cell(analysis_proposed_vek, st=cell_center),
                _optional_date_cell(analysis_proposed_check, st=cell_center),
                _optional_date_cell(analysis_actual, st=cell_center),
                rep_cell,
            ],
        ]
        an_tbl = Table(an_data, colWidths=acw)
        an_tbl.hAlign = "CENTER"
        an_ts = [
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("SPAN", (0, 0), (1, 0)),
            ("SPAN", (2, 0), (2, 1)),
            ("SPAN", (3, 0), (3, 1)),
            # Як у заголовку таблиці «Причина невиконання…»
            ("BACKGROUND", (0, 0), (-1, 1), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 2), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        an_tbl.setStyle(TableStyle(an_ts))
        story.append(an_tbl)

        # Таблиця «Причина…»: 3 колонки — порушення | причина | коригуюча дія
        story.append(Spacer(1, 8))

        def _cause_cell_paragraph(text: str) -> Paragraph:
            s = (text or "").strip()
            return _p(html.escape(s, quote=False), base) if s else Paragraph("", base)

        cause_rows_pdf: list[tuple[str, str, str]] = []
        if analysis_cause_rows is not None:
            for item in analysis_cause_rows:
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                    v = str(item[0] or "").strip()
                    rsn = str(item[1] or "").strip()
                    corr = str(item[2] or "").strip()
                    if v or rsn or corr:
                        cause_rows_pdf.append((v, rsn, corr))
        if not cause_rows_pdf:
            _viol_txt = (analysis_violation or "").strip()
            if not _viol_txt:
                _nc_list = list(nonconformities)
                if _nc_list:
                    _viol_txt = (_nc_list[0].description or "").strip()
            cause_rows_pdf.append(
                (
                    _viol_txt,
                    (analysis_reason_text or "").strip(),
                    (analysis_corrective_action or "").strip(),
                )
            )

        cause_w = doc.width
        cw3 = [cause_w / 3.0, cause_w / 3.0, cause_w / 3.0]
        cause_data = [
            [
                _p("<b>Причина невиконання і передбачувана коригуюча дія</b>", table_header),
                "",
                "",
            ],
        ]
        for v, rsn, corr in cause_rows_pdf:
            cause_data.append(
                [
                    _cause_cell_paragraph(v),
                    _cause_cell_paragraph(rsn),
                    _cause_cell_paragraph(corr),
                ]
            )
        cause_tbl = Table(cause_data, colWidths=cw3)
        cause_tbl.hAlign = "CENTER"
        cause_ts = [
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("SPAN", (0, 0), (2, 0)),
            ("BACKGROUND", (0, 0), (2, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ALIGN", (0, 1), (-1, -1), "LEFT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        cause_tbl.setStyle(TableStyle(cause_ts))
        story.append(cause_tbl)

        # Звіт про закриття невідповідностей (для звіту замість фотофіксації)
        cl_rows_norm: list[tuple[str, str]] = []
        if closure_rows:
            for t_raw, d_raw in closure_rows:
                t = str(t_raw or "").strip()
                d = str(d_raw or "").strip().lower()
                if d not in ("yes", "no"):
                    d = ""
                if t or d:
                    cl_rows_norm.append((t, d))
        rows_for_pdf = cl_rows_norm if cl_rows_norm else [("", "")]

        story.append(Spacer(1, 14))
        story.append(_p("<b>ЗВІТ ПРО ЗАКРИТТЯ НЕВІДПОВІДНОСТЕЙ</b>", analysis_title_st))
        story.append(_p("<i>(заповнюється перевіряючим)</i>", title_2))
        story.append(Spacer(1, 6))

        cl_w = doc.width
        cl_cw = [cl_w * 0.70, cl_w * 0.15, cl_w * 0.15]
        mark_st = ParagraphStyle(
            "ClosureMark",
            parent=base,
            alignment=1,
            fontName=FONT_NAME,
            fontSize=12,
            leading=14.5,
        )
        cl_table_data: list[list] = [
            [
                _p("<b>Коригуючу дію виконано</b>", table_header),
                _p("<b>Так</b>", table_header),
                _p("<b>Ні</b>", table_header),
            ]
        ]
        for i, (text, done) in enumerate(rows_for_pdf, start=1):
            t = (text or "").strip()
            esc = html.escape(t, quote=False) if t else ""
            left_cell = _p(f"{i}. {esc}", base) if t else _p(f"{i}.", base)
            yes_cell = _p("V", mark_st) if done == "yes" else Paragraph("", mark_st)
            no_cell = _p("V", mark_st) if done == "no" else Paragraph("", mark_st)
            cl_table_data.append([left_cell, yes_cell, no_cell])

        cl_tbl = Table(cl_table_data, colWidths=cl_cw)
        cl_tbl.hAlign = "CENTER"
        cl_ts = [
            ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
            ("FONTSIZE", (0, 0), (-1, -1), 12),
            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]
        cl_tbl.setStyle(TableStyle(cl_ts))
        story.append(cl_tbl)

        conc = _closure_conclusion_text(cl_rows_norm, report_date)
        if conc:
            story.append(Spacer(1, 10))
            story.append(_p(conc, base))

        cc_s = (closure_comments or "").strip()
        if cc_s:
            story.append(Spacer(1, 10))
            story.append(_p("<b>Коментарі:</b>", label_b))
            story.append(_p(html.escape(cc_s, quote=False), base))

        story.append(Spacer(1, 12))
        story.append(_p("<b>Перевіряючий</b>", label_b))
        _insp_line = " — ".join(
            x for x in (inspector_position or "", inspector_full_name or "") if (x or "").strip()
        )
        if _insp_line:
            story.append(_p(html.escape(_insp_line, quote=False), base))

        extras_rep = list(additional_unit_representatives or [])
        if extras_rep:
            story.append(Spacer(1, 14))
            story.append(_p("<b>Додаткові представники підрозділу:</b>", label_b))
            for pos, full_name in extras_rep:
                pos_s = (pos or "").strip()
                name_s = (full_name or "").strip()
                if not pos_s and not name_s:
                    continue
                line = f"{pos_s} {name_s}".strip()
                if line:
                    story.append(_p(line, base))

    else:
        # Акт (Ф-15-01) — попередній макет
        story.append(_p("<b><i>Акт</i></b>", title_1))
        story.append(_p("<i><u>перевірки виробничої діяльності</u></i>", title_2))
        story.append(_p("<i><u>щодо дотримання вимог природоохоронного законодавства</u></i>", title_2))
        story.append(Spacer(1, 10))

        form_norm = (inspection_form or "").strip().lower()
        form_acc = "позапланову" if form_norm != "планова" else "планову"

        # Пара "ПІБ + Посада" в одному рядку — підкреслення по довжині тексту (як знизу під таблицею).
        def _pib_posada_row(*, pib: str, posada: str) -> Table:
            return _two_signature_lines_row(
                layout_width=doc.width,
                left_value=pib,
                right_value=posada,
                left_caption="(ПІБ)",
                right_caption="(Посада)",
                value_style=value_b,
                caption_style=caption_sm,
                fixed_gap_between_fields=True,
                min_width=60 * mm,
            )

        # Лівий блок: підписи в рядок, відступ зліва як у лейблів
        left_pad = 3 * mm
        left_block = Table(
            [
                [_p(f"<b>Дата:</b> <b>{report_date:%d.%m.%Y}</b>", label_b)],
                [_p(f"<b>Перевірку провели:</b> <b><i><u>{form_acc}</u></i></b>", label_b)],
                [_pib_posada_row(pib=inspector_full_name, posada=inspector_position)],
                [Spacer(1, 8)],
                [_p("<b>Представник підрозділу:</b>", label_b)],
                [_pib_posada_row(pib=unit_representative_full_name, posada=unit_rep_position)],
            ],
            colWidths=["*"],
        )
        left_block.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), left_pad),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        top_table = Table([[left_block]], colWidths=[doc.width])
        top_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        story.append(top_table)
        story.append(Spacer(1, 10))
        story.append(Paragraph("Таблиця невідповідностей", h2))

        rows = list(nonconformities)
        table_data = [
            [
                _p("<b>№ п/п</b>", table_header),
                _p("<b>Виявлена невідповідність</b>", table_header),
                _p("<b>Коригуючі дії</b>", table_header),
                _p("<b>Відповідальний виконавець</b>", table_header),
                _p("<b>Строк виконання</b>", table_header),
            ]
        ]

        for r in rows:
            dd = r.due_date.strftime("%d.%m.%Y") if r.due_date else ""
            table_data.append(
                [
                    _p(str(r.order_number), base),
                    _p(r.description, base),
                    _p(r.corrective_actions, base),
                    _p(r.responsible, base),
                    _p(dd, base),
                ]
            )

        # Робимо зовнішній зазор між таблицею і рамкою сторінки.
        table_w = max(1.0, doc.width - 2 * TABLE_SIDE_GAP)
        w0 = min(12 * mm, table_w * 0.10)
        rem = max(1.0, table_w - w0)
        col_widths = [w0, rem * 0.38, rem * 0.27, rem * 0.20, rem * 0.15]
        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.hAlign = "CENTER"
        tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                    ("FONTSIZE", (0, 0), (-1, -1), 12),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    ("ALIGN", (0, 1), (0, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]
            )
        )

        story.append(tbl)

        # Підписи під таблицею — одним блоком: якщо не вміщаються внизу сторінки, переносяться разом
        sig_block: list = []
        sig_block.append(Spacer(1, 12))
        sig_block.append(_p("Підписи:", label_b))
        sig_block.append(Spacer(1, 6))

        sig_block.append(_p("Перевіряючий (посада)", sig_label))
        sig_block.append(
            _two_signature_lines_row(
                layout_width=doc.width,
                left_value=inspector_position or "",
                right_value=inspector_full_name or "",
                left_caption="(Посада)",
                right_caption="(ПІБ)",
                value_style=value_b,
                caption_style=caption_sm,
                cell_pad_right=SIG_PIB_RIGHT_MARGIN,
            )
        )
        sig_block.append(Spacer(1, 10))

        sig_block.append(_p("Представник підрозділу (посада)", sig_label))
        sig_block.append(
            _two_signature_lines_row(
                layout_width=doc.width,
                left_value=unit_representative_position or "",
                right_value=unit_representative_full_name or "",
                left_caption="(Посада)",
                right_caption="(ПІБ)",
                value_style=value_b,
                caption_style=caption_sm,
                cell_pad_right=SIG_PIB_RIGHT_MARGIN,
            )
        )

        extras = list(additional_unit_representatives or [])
        for pos, full_name in extras:
            pos_s = (pos or "").strip()
            name_s = (full_name or "").strip()
            if not pos_s and not name_s:
                continue
            sig_block.append(Spacer(1, 10))
            sig_block.append(_p("Представник підрозділу (посада)", sig_label))
            sig_block.append(
                _two_signature_lines_row(
                    layout_width=doc.width,
                    left_value=pos_s,
                    right_value=name_s,
                    left_caption="(Посада)",
                    right_caption="(ПІБ)",
                    value_style=value_b,
                    caption_style=caption_sm,
                    cell_pad_right=SIG_PIB_RIGHT_MARGIN,
                )
            )

        story.append(KeepTogether(sig_block))

    photos = list(photo_items)
    if photos and kind != "report":
        story.append(PageBreak())
        max_w = doc.width
        # Залишаємо місце під Spacer і невеликий буфер, щоб велике фото не виштовхувало блок на нову сторінку.
        max_h = max(1.0, doc.height - 14 - 24)
        photo_blocks = []
        for p in photos:
            block = []
            block.append(_scaled_platypus_image(p.image_path, max_width=max_w, max_height=max_h))
            block.append(Spacer(1, 14))
            photo_blocks.append(KeepTogether(block))

        story.extend(photo_blocks)

    header_kwargs = dict(
        branch=branch,
        revision=revision,
        report_date=report_date,
        site_name=site_name,
        doc_kind=kind,
        left_margin=doc.leftMargin,
        right_margin=doc.rightMargin,
    )

    def _canvasmaker(*args, **kwargs):
        return _NumberedCanvas(*args, header_kwargs=header_kwargs, **kwargs)

    doc.build(story, canvasmaker=_canvasmaker)
    return buf.getvalue()

