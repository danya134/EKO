from django.db import models


class EnvironmentalReport(models.Model):
    # Шапка
    branch = models.CharField("Філія", max_length=255)
    revision = models.CharField("Редакція", max_length=64, blank=True, default="")
    report_date = models.DateField("Дата")

    # Основні поля
    site_name = models.CharField("Назва дільниці", max_length=255)
    inspection_form = models.CharField(
        "Форма перевірки",
        max_length=32,
        blank=True,
        default="позапланова",
    )
    expert_full_name = models.CharField("ПІБ експерта", max_length=255, blank=True, default="")
    inspector_full_name = models.CharField("ПІБ перевіряючого (еколог)", max_length=255)
    inspector_position = models.CharField("Посада перевіряючого", max_length=255, blank=True, default="Провідний Еколог")
    unit_representative_full_name = models.CharField(
        "ПІБ представника підрозділу", max_length=255
    )
    unit_representative_position = models.CharField(
        "Посада представника підрозділу", max_length=255, blank=True, default="Начальник дільниці"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Environmental report"
        verbose_name_plural = "Environmental reports"

    def __str__(self) -> str:
        return f"{self.site_name} — {self.report_date:%Y-%m-%d}"


class EnvironmentalNonconformity(models.Model):
    report = models.ForeignKey(
        EnvironmentalReport, on_delete=models.CASCADE, related_name="nonconformities"
    )
    order_number = models.PositiveIntegerField("№ п/п")
    description = models.TextField("Опис невідповідності")
    corrective_actions = models.TextField("Коригуючі дії", blank=True, default="")
    responsible = models.CharField("Відповідальний", max_length=255, blank=True, default="")
    due_date = models.DateField("Строк виконання", null=True, blank=True)

    class Meta:
        verbose_name = "Environmental nonconformity"
        verbose_name_plural = "Environmental nonconformities"
        ordering = ["order_number", "id"]

    def __str__(self) -> str:
        return f"{self.order_number}. {self.description[:50]}"


class EnvironmentalPhoto(models.Model):
    report = models.ForeignKey(
        EnvironmentalReport, on_delete=models.CASCADE, related_name="photos"
    )
    caption = models.CharField("Підпис", max_length=255, blank=True, default="")
    image = models.ImageField("Фото", upload_to="environmental_reports/photos/")
    order_number = models.PositiveIntegerField("Порядок", default=1)

    class Meta:
        verbose_name = "Environmental photo"
        verbose_name_plural = "Environmental photos"
        ordering = ["order_number", "id"]

    def __str__(self) -> str:
        return self.caption or f"Photo #{self.order_number}"

