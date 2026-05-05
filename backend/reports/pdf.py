from __future__ import annotations

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


FONT_NAME = "DejaVuSerif"
FONT_BOLD = "DejaVuSerif-Bold"
FONT_ITALIC = "DejaVuSerif-Italic"
FONT_BOLD_ITALIC = "DejaVuSerif-BoldItalic"

HEADER_H = 28 * mm
TABLE_SIDE_GAP = 2 * mm


def _candidate_font_paths() -> list[str]:
    candidates: list[str] = []

    # 1) Явна настройка в settings.py
    configured = getattr(settings, "REPORTLAB_FONT_PATH", None)
    if configured:
        # Може бути як файл, так і директорія.
        candidates.append(str(configured))

    # 2) Локальна папка проєкту: BASE_DIR/fonts/...
    base_dir = getattr(settings, "BASE_DIR", None)
    if base_dir:
        candidates.extend(
            [
                os.path.join(str(base_dir), "fonts", "DejaVuSerif.ttf"),
                os.path.join(str(base_dir), "fonts", "DejaVuSerif-Bold.ttf"),
                os.path.join(str(base_dir), "fonts", "DejaVuSerif-Italic.ttf"),
                os.path.join(str(base_dir), "fonts", "DejaVuSerif-BoldItalic.ttf"),
                os.path.join(str(base_dir), "fonts", "dejavu", "DejaVuSerif.ttf"),
                os.path.join(str(base_dir), "fonts", "dejavu", "DejaVuSerif-Bold.ttf"),
                os.path.join(str(base_dir), "fonts", "dejavu", "DejaVuSerif-Italic.ttf"),
                os.path.join(str(base_dir), "fonts", "dejavu", "DejaVuSerif-BoldItalic.ttf"),
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
            r"C:\Windows\Fonts\DejaVuSerif.ttf",
            r"C:\Windows\Fonts\times.ttf",
        ]
    )

    return candidates


def ensure_cyrillic_font_registered() -> None:
    registered = set(pdfmetrics.getRegisteredFontNames())
    if {FONT_NAME, FONT_BOLD, FONT_ITALIC, FONT_BOLD_ITALIC}.issubset(registered):
        return

    # Підбираємо 4 файли шрифтів (normal/bold/italic/boldItalic), щоб жирність/курсив виглядали коректно.
    paths = {os.path.basename(p).lower(): p for p in _candidate_font_paths() if p}
    need = {
        FONT_NAME: paths.get("dejavuserif.ttf"),
        FONT_BOLD: paths.get("dejavuserif-bold.ttf"),
        FONT_ITALIC: paths.get("dejavuserif-italic.ttf"),
        FONT_BOLD_ITALIC: paths.get("dejavuserif-bolditalic.ttf"),
    }

    if not all(p and os.path.exists(p) for p in need.values()):
        # fallback: беремо будь-який знайдений normal, щоб не падати (але жирність може бути слабша)
        fallback = next((p for p in _candidate_font_paths() if p and os.path.exists(p)), None)
        if not fallback:
            raise RuntimeError(
                "Не знайдено TTF-шрифти DejaVuSerif для кирилиці. "
                "Перевірте наявність DejaVuSerif*.ttf або задайте REPORTLAB_FONT_PATH."
            )
        need = {k: fallback for k in need.keys()}

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


def _draw_page_header(
    canv: pdfcanvas.Canvas,
    *,
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
    row1 = grid_h * 0.52
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
    mid_top_text = "Ф-15-01 Акт перевірки виробничої діяльності щодо дотримання вимог природоохоронного законодавства"
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


def build_environmental_report_pdf(
    *,
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
) -> bytes:
    ensure_cyrillic_font_registered()

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

    story = []

    # Блок під колонтитулом (макет як у Word-зразку)
    story.append(_p("<b><i>Акт</i></b>", title_1))
    story.append(_p("<i><u>перевірки виробничої діяльності</u></i>", title_2))
    story.append(_p("<i><u>щодо дотримання вимог природоохоронного законодавства</u></i>", title_2))
    story.append(Spacer(1, 10))

    form_norm = (inspection_form or "").strip().lower()
    form_acc = "позапланову" if form_norm != "планова" else "планову"

    left_block = Table(
        [
            [_p(f"<b>Дата:</b> <b>{report_date:%d.%m.%Y}</b>", label_b)],
            [_p(f"<b>Перевірку провели:</b> <b><i><u>{form_acc}</u></i></b>", label_b)],
            [
                _signature_line(
                    value=inspector_full_name,
                    caption="(ПІБ)",
                    value_style=value_b,
                    caption_style=caption_sm,
                    max_width=doc.width * 0.40,
                )
            ],
            [Spacer(1, 8)],
            [_p("<b>Представник підрозділу:</b>", label_b)],
            [
                _signature_line(
                    value=unit_representative_full_name,
                    caption="(ПІБ)",
                    value_style=value_b,
                    caption_style=caption_sm,
                    max_width=doc.width * 0.40,
                )
            ],
        ],
        colWidths=["*"],
    )
    left_block.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )

    inspector_position = (inspector_position or "").strip() or "Провідний Еколог"
    unit_rep_position = (unit_representative_position or "").strip() or "Начальник дільниці"

    # Пара "ПІБ + Посада" в одному рядку, щоб були на одному рівні
    def _pib_posada_row(*, pib: str, posada: str) -> Table:
        cell_pib = _signature_line(
            value=pib,
            caption="(ПІБ)",
            value_style=value_b,
            caption_style=caption_sm,
            max_width=doc.width * 0.30,
            min_width=24 * mm,
        )
        cell_posada = _signature_line(
            value=posada,
            caption="(Посада)",
            value_style=value_b,
            caption_style=caption_sm,
            max_width=doc.width * 0.30,
            min_width=24 * mm,
        )
        # Зсуваємо "посаду" правіше: додаємо проміжну колонку-спейсер
        row = Table([[cell_pib, Spacer(1, 1), cell_posada]], colWidths=[doc.width * 0.24, doc.width * 0.10, doc.width * 0.26])
        row.setStyle(
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
        return row

    # Лівий блок: підписи в рядок, відступ зліва як у лейблів
    left_pad = 4 * mm
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
            _p("<b>№ п/п</b>", small),
            _p("<b>Опис невідповідності</b>", small),
            _p("<b>Коригуючі дії</b>", small),
            _p("<b>Відповідальний</b>", small),
            _p("<b>Строк виконання</b>", small),
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
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
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

    photos = list(photo_items)
    if photos:
        story.append(PageBreak())
        max_w = doc.width
        # Залишаємо трохи місця під відступи/спейсери, щоб не ловити LayoutError на межі.
        max_h = max(1.0, doc.height - 20)
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
        left_margin=doc.leftMargin,
        right_margin=doc.rightMargin,
    )

    def _canvasmaker(*args, **kwargs):
        return _NumberedCanvas(*args, header_kwargs=header_kwargs, **kwargs)

    doc.build(story, canvasmaker=_canvasmaker)
    return buf.getvalue()

