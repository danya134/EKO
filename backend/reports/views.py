from __future__ import annotations

import json
from pathlib import Path
from datetime import date

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EnvironmentalNonconformity, EnvironmentalPhoto
from .models import EnvironmentalReport
from .pdf import NonconformityRow, PhotoItem, build_environmental_report_pdf
from .serializers import EnvironmentalReportCreateSerializer


def _parse_additional_unit_representatives_json(raw: str) -> list[dict[str, str]]:
    s = (raw or "").strip()
    if not s:
        return []
    try:
        data = json.loads(s)
    except json.JSONDecodeError as e:
        raise ValidationError(
            {"additional_unit_representatives_json": "Некоректний JSON (очікується масив)"}
        ) from e
    if not isinstance(data, list):
        raise ValidationError({"additional_unit_representatives_json": "Очікується JSON-масив"})
    out: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pos = str(item.get("position", "")).strip()
        name = str(item.get("full_name", "")).strip()
        if pos or name:
            out.append({"position": pos, "full_name": name})
    return out


def _additional_reps_for_pdf(report: EnvironmentalReport) -> list[tuple[str, str]]:
    raw = report.additional_unit_representatives or []
    if not isinstance(raw, list):
        return []
    pairs: list[tuple[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        pairs.append(
            (
                str(item.get("position", "") or "").strip(),
                str(item.get("full_name", "") or "").strip(),
            )
        )
    return pairs


class BranchesView(APIView):
    def get(self, request, *args, **kwargs):
        path = Path(__file__).resolve().parent / "branches.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        if not isinstance(data, list):
            data = []
        # повертаємо простий список рядків
        return Response(data, status=status.HTTP_200_OK)


class UnitsView(APIView):
    def get(self, request, *args, **kwargs):
        branch = (request.query_params.get("branch") or "").strip()
        path = Path(__file__).resolve().parent / "units.json"
        data = _load_json(path, default={})
        if not isinstance(data, dict):
            data = {}
        units = data.get(branch, [])
        if not isinstance(units, list):
            units = []

        # Підтримуємо 2 формати:
        # 1) ["Назва дільниці", ...]
        # 2) [{"name": "...", "position": "...", "full_name": "..."}, ...]
        out: list[str] = []
        for u in units:
            if isinstance(u, str):
                name = u.strip()
                if name:
                    out.append(name)
                continue
            if isinstance(u, dict):
                name = str(u.get("name") or "").strip()
                if name:
                    out.append(name)
                continue
        return Response(out, status=status.HTTP_200_OK)


class NonconformityDescriptionsView(APIView):
    def get(self, request, *args, **kwargs):
        path = Path(__file__).resolve().parent / "nonconformity_descriptions.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        if not isinstance(data, list):
            data = []
        data = [x for x in data if isinstance(x, str) and x.strip()]
        return Response(data, status=status.HTTP_200_OK)


class CorrectiveActionsView(APIView):
    def get(self, request, *args, **kwargs):
        path = Path(__file__).resolve().parent / "corrective_actions.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = []
        if not isinstance(data, list):
            data = []
        data = [x for x in data if isinstance(x, str) and x.strip()]
        return Response(data, status=status.HTTP_200_OK)


def _load_json(path: Path, *, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _inspector_pair_from_dict(d: dict) -> dict[str, str]:
    return {
        "position": str(d.get("position") or "").strip(),
        "full_name": str(d.get("full_name") or "").strip(),
    }


def _inspector_unit_key(d: dict) -> str:
    return (str(d.get("дільниця") or d.get("unit") or "")).strip()


def _normalize_inspector_branch_value(raw: object) -> list[dict]:
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict):
        return [raw]
    return []


def _resolve_inspector_autofill(raw: object, *, unit: str) -> dict[str, str]:
    """
    JSON для філії: один об'єкт {position, full_name, дільниця?} або масив таких об'єктів.
    - Якщо передано unit (дільниця) — беремо запис, де «дільниця»/unit точно збігається.
    - Інакше або якщо немає збігу — запис з порожнім «дільниця»/unit (типово для всіх дільниць).
    - Якщо такого немає — перший запис у списку.
    """
    entries = _normalize_inspector_branch_value(raw)
    if not entries:
        return {"position": "", "full_name": ""}
    unit_q = (unit or "").strip()
    if unit_q:
        for e in entries:
            uk = _inspector_unit_key(e)
            if uk and uk == unit_q:
                return _inspector_pair_from_dict(e)
    for e in entries:
        if not _inspector_unit_key(e):
            return _inspector_pair_from_dict(e)
    return _inspector_pair_from_dict(entries[0])


class InspectorAutofillView(APIView):
    """
    GET ?branch=...&unit=... (unit необов'язково — назва дільниці як у списку підрозділів).

    inspector_autofill.json: для ключа філії значення — об'єкт або масив об'єктів з полями
    position, full_name та необов'язково «дільниця» або unit (порожньо = для всіх дільниць філії).
    """

    def get(self, request, *args, **kwargs):
        branch = (request.query_params.get("branch") or "").strip()
        unit = (request.query_params.get("unit") or "").strip()
        path = Path(__file__).resolve().parent / "inspector_autofill.json"
        data = _load_json(path, default={})
        if not isinstance(data, dict):
            data = {}
        raw = data.get(branch) if branch else None
        picked = _resolve_inspector_autofill(raw, unit=unit)
        return Response(picked, status=status.HTTP_200_OK)


class UnitRepresentativeAutofillView(APIView):
    def get(self, request, *args, **kwargs):
        branch = (request.query_params.get("branch") or "").strip()
        unit = (request.query_params.get("unit") or "").strip()
        path = Path(__file__).resolve().parent / "units.json"
        data = _load_json(path, default={})
        if not isinstance(data, dict):
            data = {}

        units = data.get(branch, []) if branch else []
        if not isinstance(units, list):
            units = []

        item: dict = {}
        if unit:
            for u in units:
                if isinstance(u, dict):
                    name = str(u.get("name") or "").strip()
                    if name == unit:
                        item = u
                        break

        main_position = str(item.get("position") or "").strip()
        main_full_name = str(item.get("full_name") or "").strip()

        staff_raw = item.get("staff") or []
        staff: list[dict[str, str]] = []
        if isinstance(staff_raw, list):
            for s in staff_raw:
                if isinstance(s, dict):
                    pos = str(s.get("position") or "").strip()
                    fn = str(s.get("full_name") or "").strip()
                    if pos or fn:
                        staff.append({"position": pos, "full_name": fn})

        # Якщо у дільниці немає основного представника, але є staff —
        # перший зі staff стає основним, решта йдуть у додаткових представників.
        additional = staff
        if not main_position and not main_full_name and staff:
            main_position = staff[0]["position"]
            main_full_name = staff[0]["full_name"]
            additional = staff[1:]

        return Response(
            {
                "position": main_position,
                "full_name": main_full_name,
                "staff": additional,
            },
            status=status.HTTP_200_OK,
        )


class EnvironmentalReportPdfView(APIView):
    """
    POST JSON -> повертає PDF-файл (attachment).

    Приймає:
    - поля шапки/основні поля
    - nonconformities: список рядків таблиці
    - photos: [{caption, order_number, image_base64}]
    """

    def post(self, request, *args, **kwargs):
        serializer = EnvironmentalReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        report: EnvironmentalReport = serializer.save()

        effective_from = str(request.data.get("effective_from") or "").strip()

        nonconf_rows = [
            NonconformityRow(
                order_number=r.order_number,
                description=r.description,
                corrective_actions=r.corrective_actions,
                responsible=r.responsible,
                due_date=r.due_date,
                execution_percent="",
            )
            for r in report.nonconformities.all()
        ]

        photo_items = [
            PhotoItem(caption=p.caption, image_path=p.image.path) for p in report.photos.all()
        ]

        pdf_bytes = build_environmental_report_pdf(
            branch=report.branch,
            revision=report.revision,
            effective_from=effective_from,
            report_date=report.report_date,
            site_name=report.site_name,
            inspection_form=report.inspection_form,
            inspector_full_name=report.inspector_full_name,
            inspector_position=report.inspector_position,
            unit_representative_full_name=report.unit_representative_full_name,
            unit_representative_position=report.unit_representative_position,
            nonconformities=nonconf_rows,
            photo_items=photo_items,
            additional_unit_representatives=_additional_reps_for_pdf(report),
        )

        filename = f"environmental-report-{report.report_date:%Y-%m-%d}.pdf"
        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


class EnvironmentalReportGeneratePdfFormView(APIView):
    """
    POST multipart/form-data -> повертає PDF-файл (attachment).

    Очікує поля:
    - branch, revision, report_date (YYYY-MM-DD)
    - effective_from: необов'язково — рядок для шапки («Діє з: …»); якщо порожньо — підставляється значення за замовчуванням
    - act_date (YYYY-MM-DD), необов’язково: дата складання акта для тексту підстав ВЕК; якщо порожньо — дорівнює report_date
    - site_name, inspector_full_name, unit_representative_full_name
    - nonconformities_json: JSON array [{order_number, description, corrective_actions, responsible, due_date}]
    - photos: кілька файлів (однакове поле photos)
    - additional_unit_representatives_json: необов’язково, JSON array
      [{\"position\": \"...\", \"full_name\": \"...\"}, ...] — додаткові представники підрозділу у блоці підписів
    - analysis_cause_rows_json: необов’язково для звіту, JSON array
      [{\"violation\": \"...\", \"reason\": \"...\", \"corrective\": \"...\"}, ...] — кілька рядків таблиці «Причина…»
    """

    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        data = request.data

        def req_str(key: str) -> str:
            v = (data.get(key) or "").strip()
            if not v:
                raise ValidationError({key: "Це поле обов'язкове"})
            return v

        branch = req_str("branch")
        revision = (data.get("revision") or "").strip()
        effective_from = (data.get("effective_from") or "").strip()
        site_name = req_str("site_name")
        doc_kind = (data.get("doc_kind") or "").strip().lower() or "act"
        if doc_kind not in {"act", "report"}:
            doc_kind = "act"
        inspection_form = (data.get("inspection_form") or "").strip()
        if inspection_form not in {"планова", "позапланова"}:
            inspection_form = "позапланова"
        inspector_position = (data.get("inspector_position") or "").strip() or "Провідний Еколог"
        inspector_full_name = req_str("inspector_full_name")
        unit_representative_position = (data.get("unit_representative_position") or "").strip() or "Начальник дільниці"
        unit_representative_full_name = req_str("unit_representative_full_name")
        additional_reps = _parse_additional_unit_representatives_json(
            str(data.get("additional_unit_representatives_json") or "")
        )

        report_date_raw = req_str("report_date")
        try:
            report_date = date.fromisoformat(report_date_raw)
        except ValueError as e:
            raise ValidationError({"report_date": "Очікується формат YYYY-MM-DD"}) from e

        act_date_raw = (data.get("act_date") or "").strip()
        if act_date_raw:
            try:
                act_date = date.fromisoformat(act_date_raw)
            except ValueError as e:
                raise ValidationError({"act_date": "Очікується формат YYYY-MM-DD"}) from e
        else:
            act_date = report_date

        def _optional_iso_date(key: str):
            raw = (data.get(key) or "").strip()
            if not raw:
                return None
            try:
                return date.fromisoformat(raw)
            except ValueError as e:
                raise ValidationError({key: "Очікується формат YYYY-MM-DD"}) from e

        analysis_proposed_vek = _optional_iso_date("analysis_proposed_vek")
        analysis_proposed_check = _optional_iso_date("analysis_proposed_check")
        analysis_actual = _optional_iso_date("analysis_actual")
        analysis_reason_text = (data.get("analysis_reason_text") or "").strip()
        analysis_violation = (data.get("analysis_violation") or "").strip()
        analysis_corrective_action = (data.get("analysis_corrective_action") or "").strip()

        analysis_cause_rows_parsed: list[tuple[str, str, str]] = []
        acr_raw = (data.get("analysis_cause_rows_json") or "").strip()
        if acr_raw:
            try:
                acr_list = json.loads(acr_raw)
            except json.JSONDecodeError as e:
                raise ValidationError(
                    {"analysis_cause_rows_json": "Некоректний JSON (очікується масив)"}
                ) from e
            if not isinstance(acr_list, list):
                raise ValidationError({"analysis_cause_rows_json": "Очікується JSON-масив"})
            for item in acr_list:
                if not isinstance(item, dict):
                    continue
                v = str(item.get("violation") or "").strip()
                rsn = str(item.get("reason") or "").strip()
                corr = str(item.get("corrective") or "").strip()
                if v or rsn or corr:
                    analysis_cause_rows_parsed.append((v, rsn, corr))

        closure_comments = (data.get("closure_comments") or "").strip()
        closure_raw = (data.get("closure_rows_json") or "[]").strip()
        closure_rows_parsed: list[tuple[str, str]] = []
        try:
            closure_list = json.loads(closure_raw) if closure_raw else []
        except json.JSONDecodeError as e:
            raise ValidationError(
                {"closure_rows_json": "Некоректний JSON (очікується масив)"}
            ) from e
        if not isinstance(closure_list, list):
            raise ValidationError({"closure_rows_json": "Очікується JSON-масив"})
        for item in closure_list:
            if not isinstance(item, dict):
                continue
            ca = str(item.get("corrective_action") or "").strip()
            done = str(item.get("completed") or "").strip().lower()
            if done not in ("yes", "no"):
                done = ""
            if ca or done:
                closure_rows_parsed.append((ca, done))

        nonconf_raw = (data.get("nonconformities_json") or "[]").strip()
        try:
            nonconf_list = json.loads(nonconf_raw) if nonconf_raw else []
        except json.JSONDecodeError as e:
            raise ValidationError(
                {"nonconformities_json": "Некоректний JSON (очікується масив)"}
            ) from e

        if not isinstance(nonconf_list, list):
            raise ValidationError({"nonconformities_json": "Очікується JSON-масив"})

        report = EnvironmentalReport.objects.create(
            branch=branch,
            revision=revision,
            report_date=report_date,
            site_name=site_name,
            inspection_form=inspection_form,
            inspector_full_name=inspector_full_name,
            inspector_position=inspector_position,
            unit_representative_full_name=unit_representative_full_name,
            unit_representative_position=unit_representative_position,
            additional_unit_representatives=additional_reps,
        )

        nonconf_rows: list[NonconformityRow] = []
        for idx, row in enumerate(nonconf_list, start=1):
            if not isinstance(row, dict):
                continue
            due = row.get("due_date") or None
            due_date = None
            if due:
                try:
                    due_date = date.fromisoformat(str(due))
                except ValueError:
                    due_date = None

            execution_percent = str(row.get("execution_percent") or "").strip()

            EnvironmentalNonconformity.objects.create(
                report=report,
                order_number=int(row.get("order_number") or idx),
                description=str(row.get("description") or "").strip(),
                corrective_actions=str(row.get("corrective_actions") or "").strip(),
                responsible=str(row.get("responsible") or "").strip(),
                due_date=due_date,
            )

            nonconf_rows.append(
                NonconformityRow(
                    order_number=int(row.get("order_number") or idx),
                    description=str(row.get("description") or "").strip(),
                    corrective_actions=str(row.get("corrective_actions") or "").strip(),
                    responsible=str(row.get("responsible") or "").strip(),
                    due_date=due_date,
                    execution_percent=execution_percent,
                )
            )

        files = request.FILES.getlist("photos")
        if doc_kind != "report":
            for i, f in enumerate(files, start=1):
                EnvironmentalPhoto.objects.create(
                    report=report,
                    caption=getattr(f, "name", "") or f"Фото {i}",
                    order_number=i,
                    image=f,
                )

        photo_items = [PhotoItem(caption=p.caption, image_path=p.image.path) for p in report.photos.all()]

        pdf_bytes = build_environmental_report_pdf(
            doc_kind=doc_kind,
            branch=report.branch,
            revision=report.revision,
            effective_from=effective_from,
            report_date=report.report_date,
            site_name=report.site_name,
            inspection_form=report.inspection_form,
            inspector_full_name=report.inspector_full_name,
            inspector_position=report.inspector_position,
            unit_representative_full_name=report.unit_representative_full_name,
            unit_representative_position=report.unit_representative_position,
            nonconformities=nonconf_rows,
            photo_items=photo_items,
            additional_unit_representatives=_additional_reps_for_pdf(report),
            act_date=act_date,
            analysis_proposed_vek=analysis_proposed_vek,
            analysis_proposed_check=analysis_proposed_check,
            analysis_actual=analysis_actual,
            analysis_reason_text=analysis_reason_text,
            analysis_violation=analysis_violation,
            analysis_corrective_action=analysis_corrective_action,
            analysis_cause_rows=analysis_cause_rows_parsed if analysis_cause_rows_parsed else None,
            closure_rows=closure_rows_parsed,
            closure_comments=closure_comments,
        )

        resp = HttpResponse(pdf_bytes, content_type="application/pdf")
        filename = "Звіт_Ф-15-02.pdf" if doc_kind == "report" else "Акт_ВЕК.pdf"
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp


class HealthcheckView(APIView):
    def get(self, request, *args, **kwargs):
        return Response({"ok": True}, status=status.HTTP_200_OK)

