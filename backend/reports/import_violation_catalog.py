"""
Імпорт каталогу порушень з JSON (конвертований опитувальник) або Excel.

Запуск:
  python import_violation_catalog.py
  python import_violation_catalog.py ../Лист Microsoft Excel.json
  python import_violation_catalog.py ../АКТ ВЕК для додатку.xlsx
"""
from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

BASE = Path(__file__).resolve().parent
DEFAULT_JSON = BASE.parent / "Лист Microsoft Excel.json"
DEFAULT_XLSX = BASE.parent / "АКТ ВЕК для додатку.xlsx"


def _norm_text(s: str) -> str:
    s = (s or "").replace("\n", " ")
    s = s.replace("\u2019", "'").replace("`", "'")
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.replace(" по ", " за ")
    return s.rstrip(".")


def _load_old_descriptions_from_git() -> list[str]:
    import subprocess

    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:backend/reports/nonconformity_descriptions.json"],
            cwd=BASE.parent.parent,
            text=True,
            encoding="utf-8",
        )
        data = json.loads(raw)
        return [x for x in data if isinstance(x, str) and x.strip()]
    except Exception:
        return []


def _load_old_description_lookup() -> dict[str, str]:
    out: dict[str, str] = {}
    for item in _load_old_descriptions_from_git():
        out[_norm_text(item)] = item.strip()
        if ": " in item:
            viol = item.split(": ", 1)[1]
            out[_norm_text(viol)] = item.strip()
    return out


def _load_old_corrective_lookup() -> dict[str, str]:
    import subprocess

    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:backend/reports/corrective_actions.json"],
            cwd=BASE.parent.parent,
            text=True,
            encoding="utf-8",
        )
        correctives = json.loads(raw)
        descriptions = _load_old_descriptions_from_git()
    except Exception:
        return {}
    out: dict[str, str] = {}
    for desc, corr in zip(descriptions, correctives):
        if isinstance(corr, str) and corr.strip():
            out[_norm_text(corr)] = desc.strip()
    return out


def _strip_risks(normative: str) -> str:
    text = normative or ""
    for marker in (
        "Ризики для підприємства",
        "Ризики та наслідки",
        "Ризики:",
        "Призупинення діяльності",
        "Кримінальна відповідальність",
        "Скарги від громадськості",
    ):
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx]
    return text.strip()


def _looks_like_legal_ref(text: str) -> bool:
    return bool(
        re.search(
            r"(ЗУ|Закон|Кодекс|ПКМУ|Постанов|Наказ|ДСП|статт|ст\.|абз\.|п\.|пункт|Розділ|ВКУ|ЗКУ)",
            text,
            re.IGNORECASE,
        )
    )


def _normalize_ref(ref: str) -> str:
    ref = re.sub(r"\s+", " ", ref).strip()
    ref = ref.replace("ЗУ ЗУ", "ЗУ")
    ref = re.sub(r"^Порушення\s+", "", ref, flags=re.IGNORECASE)
    ref = re.sub(r"^Порушенняст\.\s*", "ст. ", ref, flags=re.IGNORECASE)
    ref = re.sub(r"^Порушенняст\s*", "ст. ", ref, flags=re.IGNORECASE)
    return ref.strip().rstrip(".")


def _extract_normative_ref(normative: str) -> str:
    raw = _strip_risks(normative)
    if not raw:
        return "законодавства"

    first_line = raw.split("\n")[0].strip()
    first_line = re.sub(r"^Порушення\s+", "", first_line, flags=re.IGNORECASE)
    first_line = re.sub(r"^Порушено\s+", "", first_line, flags=re.IGNORECASE)

    if _looks_like_legal_ref(first_line) and len(first_line) <= 220:
        ref = re.split(r"[;:]\s", first_line, maxsplit=1)[0].strip()
        return _normalize_ref(ref)

    m = re.search(
        r'ПКМУ(?:\s+від\s+[\d.]+\s+р\.)?\s*№\s*(\d+)\s*["«]([^"»]+)["»]?',
        raw,
        re.IGNORECASE,
    )
    if m:
        return f'ПКМУ № {m.group(1)} "{m.group(2).strip()}"'

    m = re.search(r"Постанов[аи]\s+КМУ\s+№\s*(\d+)", raw, re.IGNORECASE)
    if m:
        return f"Постанови КМУ № {m.group(1)}"

    m = re.search(
        r'Наказ(?:у)?\s+№\s*(\d+)\s*["«]([^"»]+)["»]?',
        raw,
        re.IGNORECASE,
    )
    if m:
        title = m.group(2).strip()
        point = ""
        pm = re.search(r"п\.?\s*([\d.,\s]+)", raw, re.IGNORECASE)
        if pm:
            point = f" п. {pm.group(1).strip().rstrip('.')}"
        return f"Наказу № {m.group(1)} «{title}»{point}"

    m = re.search(r"Наказ(?:у)?\s+МОЗ\s+№\s*(\d+)", raw, re.IGNORECASE)
    if m:
        return f"Наказу МОЗ № {m.group(1)}"

    m = re.search(r"Наказ(?:у)?\s+Міндовкілля\s+№\s*(\d+)", raw, re.IGNORECASE)
    if m:
        return f"Наказу Міндовкілля № {m.group(1)}"

    m = re.search(
        r'статт[іи]\s+([\d\-,\sі]+?)\s+Закону України\s*[«"]([^»"]+)[»"]',
        raw,
        re.IGNORECASE,
    )
    if m:
        arts = re.sub(r"\s+", " ", m.group(1).strip()).replace(" і ", ", ").rstrip(",")
        return f"статті {arts} Закону України «{m.group(2).strip()}»"

    m = re.search(
        r'вимог\s+статт[іи]\s+([\d\-,\sі]+?)\s+Закону України\s*[«"]([^»"]+)[»"]',
        raw,
        re.IGNORECASE,
    )
    if m:
        arts = re.sub(r"\s+", " ", m.group(1).strip()).replace(" і ", ", ").rstrip(",")
        return f'ЗУ «{m.group(2).strip()}» ст. {arts}'

    m = re.search(
        r'статт[іи]\s+([\d\-,\s]+)\s+(Водного кодексу України|Земельного кодексу України)',
        raw,
        re.IGNORECASE,
    )
    if m:
        return f"статті {m.group(1).strip().rstrip(',')} {m.group(2)}"

    m = re.search(
        r'(?:абз\.\s*\d+\s+)?(?:частини\s+\d+\s+)?ст\.?\s*([\d\-,\s]+)\s+ЗУ\s*[«"]([^»"]+)[»"]',
        raw,
        re.IGNORECASE,
    )
    if m:
        arts = re.sub(r"\s+", " ", m.group(1).strip()).rstrip(",")
        return f'ЗУ "{m.group(2).strip()}" ст. {arts}'

    m = re.search(r"ст\.?\s*([\d\-\.,\s]+)\s+ВКУ", raw, re.IGNORECASE)
    if m:
        return f"Водного кодексу України статті {m.group(1).strip().rstrip('.,')}"

    m = re.search(r"ст\.?\s*([\d\-\.,\s]+)\s+ЗКУ", raw, re.IGNORECASE)
    if m:
        return f"статті {m.group(1).strip().rstrip('.,')} Земельного кодексу України"

    m = re.search(
        r"статт[іи]\s+([\d\-,\s]+)\s+КУ\s*№\s*([\d/]+)",
        raw,
        re.IGNORECASE,
    )
    if m:
        arts = re.sub(r"\s+", " ", m.group(1).strip()).rstrip(".,")
        return f"статті {arts} Кодексу України № {m.group(2)}"

    m = re.search(
        r"Пункти?\s+([\d\-,\s]+)\s+частини\s+[^.]+\s+статт[іи]\s+([\d]+)\s+КУ\s*№\s*([\d/]+)",
        raw,
        re.IGNORECASE,
    )
    if m:
        return (
            f"пункти {m.group(1).strip()} частини першої статті {m.group(2)} "
            f"Кодексу України «Про надра»"
        )

    m = re.search(
        r'ст\.?\s*([\d,\s]+)\s+ЗУ\s*[«"]([^»"]+)[»"]',
        raw,
        re.IGNORECASE,
    )
    if m:
        return f'ЗУ «{m.group(2).strip()}» ст. {m.group(1).strip().rstrip(".,")}'

    m = re.search(r'Закону України\s*[«"]([^»"]+)[»"]', raw, re.IGNORECASE)
    if m:
        return f'Закону України «{m.group(1).strip()}»'

    m = re.search(r"ДСП\s*([\d.\-]+)", raw, re.IGNORECASE)
    if m:
        return f"ДСП {m.group(1)}"

    if _looks_like_legal_ref(first_line) and ":" in first_line:
        return _normalize_ref(first_line.split(":", 1)[0].strip())

    return "законодавства"


def build_description(
    violation: str,
    normative: str,
    corrective: str,
    old_by_violation: dict[str, str],
    old_by_corrective: dict[str, str],
) -> str:
    viol_key = _norm_text(violation)
    if viol_key in old_by_violation:
        return old_by_violation[viol_key]

    corr_key = _norm_text(corrective)
    if corr_key in old_by_corrective:
        return old_by_corrective[corr_key]

    ref = _extract_normative_ref(normative)
    viol = violation.strip()
    if not viol:
        return f"Порушення {ref}" if ref != "законодавства" else "Порушення законодавства"
    if ref.lower().startswith("порушення "):
        return f"{ref}: {viol}"
    return f"Порушення {ref}: {viol}"


def _field(obj: dict, *names: str) -> str:
    for name in names:
        if name in obj and obj[name] is not None:
            val = str(obj[name]).strip()
            if val and val.lower() != "null":
                return val
    return ""


def load_questionnaire_json(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("null,"):
        text = text[5:].strip().rstrip(",")
    if not text.startswith("["):
        text = "[" + text + "]"
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("Очікується JSON-масив")

    rows: list[dict] = []
    for obj in data:
        if not isinstance(obj, dict):
            continue
        category = _field(obj, "Блок", "блок")
        violation = _field(obj, "Column4", "Виявлена невідповідність")
        normative = _field(obj, "Нормативне обгрунтування ", "Нормативне обгрунтування")
        corrective = _field(obj, "Коригуючі дії", "Коригуючі дії ")

        if violation in ("+", "-", "так", "ні"):
            violation = _field(obj, "Column4")

        if not category or category == "Блок":
            continue
        if not violation and not corrective:
            continue

        rows.append(
            {
                "category": category.strip(),
                "violation": violation,
                "normative": normative,
                "corrective": corrective,
            }
        )
    return rows


def read_questionnaire_rows_xlsx(xlsx_path: Path) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb["Опитувальник"]
    rows: list[dict] = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        vals = list(row)
        category = str(vals[0]).strip() if vals[0] else ""
        violation = str(vals[3]).strip() if len(vals) > 3 and vals[3] else ""
        normative = str(vals[4]).strip() if len(vals) > 4 and vals[4] else ""
        corrective = str(vals[5]).strip() if len(vals) > 5 and vals[5] else ""
        if not category or category == "Блок":
            continue
        if not violation and not corrective:
            continue
        rows.append(
            {
                "category": category,
                "violation": violation,
                "normative": normative,
                "corrective": corrective,
            }
        )
    return rows


def read_questionnaire_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        return load_questionnaire_json(path)
    return read_questionnaire_rows_xlsx(path)


def build_catalog(
    rows: list[dict],
    old_by_violation: dict[str, str],
    old_by_corrective: dict[str, str],
) -> list[dict]:
    buckets: OrderedDict[str, list[dict]] = OrderedDict()
    for row in rows:
        cat = row["category"]
        if cat not in buckets:
            buckets[cat] = []
        description = build_description(
            row["violation"],
            row["normative"],
            row["corrective"],
            old_by_violation,
            old_by_corrective,
        )
        buckets[cat].append(
            {
                "description": description,
                "corrective_action": row["corrective"],
            }
        )
    return [{"category": cat, "items": items} for cat, items in buckets.items()]


def flatten_catalog(catalog: list[dict]) -> tuple[list[str], list[str]]:
    descriptions: list[str] = []
    correctives: list[str] = []
    for block in catalog:
        for item in block["items"]:
            descriptions.append(item["description"])
            correctives.append(item["corrective_action"])
    return descriptions, correctives


def main() -> None:
    if len(sys.argv) > 1:
        source = Path(sys.argv[1])
    elif DEFAULT_JSON.exists():
        source = DEFAULT_JSON
    else:
        source = DEFAULT_XLSX

    if not source.exists():
        raise SystemExit(f"Файл не знайдено: {source}")

    old_by_violation = _load_old_description_lookup()
    old_by_corrective = _load_old_corrective_lookup()
    rows = read_questionnaire_rows(source)
    catalog = build_catalog(rows, old_by_violation, old_by_corrective)

    catalog_path = BASE / "violation_catalog.json"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    descriptions, correctives = flatten_catalog(catalog)
    (BASE / "nonconformity_descriptions.json").write_text(
        json.dumps(descriptions, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (BASE / "corrective_actions.json").write_text(
        json.dumps(correctives, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    total = sum(len(b["items"]) for b in catalog)
    print(f"Джерело: {source.name}")
    print(f"Імпортовано {total} пунктів у {len(catalog)} категорій")
    for block in catalog:
        print(f"  - {block['category']}: {len(block['items'])}")


if __name__ == "__main__":
    main()
