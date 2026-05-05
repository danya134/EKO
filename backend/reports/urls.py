from django.urls import path

from .views import (
    BranchesView,
    UnitsView,
    EnvironmentalReportGeneratePdfFormView,
    EnvironmentalReportPdfView,
    HealthcheckView,
)


urlpatterns = [
    path("health/", HealthcheckView.as_view(), name="reports-health"),
    path("branches/", BranchesView.as_view(), name="branches"),
    path("units/", UnitsView.as_view(), name="units"),
    path(
        "environmental-reports/pdf/",
        EnvironmentalReportPdfView.as_view(),
        name="environmental-report-pdf",
    ),
    path(
        "generate-pdf/",
        EnvironmentalReportGeneratePdfFormView.as_view(),
        name="generate-pdf-form",
    ),
]

