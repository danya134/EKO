from django.urls import path

from .views import (
    BranchesView,
    UnitsView,
    NonconformityDescriptionsView,
    CorrectiveActionsView,
    InspectorAutofillView,
    UnitRepresentativeAutofillView,
    EnvironmentalReportGeneratePdfFormView,
    EnvironmentalReportPdfView,
    HealthcheckView,
)


urlpatterns = [
    path("health/", HealthcheckView.as_view(), name="reports-health"),
    path("branches/", BranchesView.as_view(), name="branches"),
    path("units/", UnitsView.as_view(), name="units"),
    path(
        "nonconformity-descriptions/",
        NonconformityDescriptionsView.as_view(),
        name="nonconformity-descriptions",
    ),
    path(
        "corrective-actions/",
        CorrectiveActionsView.as_view(),
        name="corrective-actions",
    ),
    path(
        "inspector-autofill/",
        InspectorAutofillView.as_view(),
        name="inspector-autofill",
    ),
    path(
        "unit-representative-autofill/",
        UnitRepresentativeAutofillView.as_view(),
        name="unit-representative-autofill",
    ),
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

