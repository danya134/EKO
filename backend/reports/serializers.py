import base64
import binascii
from typing import Any

from django.core.files.base import ContentFile
from rest_framework import serializers

from .models import EnvironmentalNonconformity, EnvironmentalPhoto, EnvironmentalReport


class EnvironmentalNonconformitySerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvironmentalNonconformity
        fields = [
            "order_number",
            "description",
            "corrective_actions",
            "responsible",
            "due_date",
        ]


class EnvironmentalPhotoInputSerializer(serializers.Serializer):
    caption = serializers.CharField(required=False, allow_blank=True, default="")
    order_number = serializers.IntegerField(required=False, min_value=1, default=1)

    # JSON-friendly: data URL або "raw" base64. Формат: "data:image/jpeg;base64,...."
    image_base64 = serializers.CharField()

    def _decode_base64(self, value: str) -> ContentFile:
        if ";base64," in value:
            header, b64 = value.split(";base64,", 1)
            ext = header.split("/")[-1] if "/" in header else "png"
        else:
            b64 = value
            ext = "png"

        try:
            raw = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as e:
            raise serializers.ValidationError("Некоректне base64-зображення") from e

        return ContentFile(raw, name=f"photo.{ext}")

    def to_internal_value(self, data: Any):
        ret = super().to_internal_value(data)
        ret["image_file"] = self._decode_base64(ret["image_base64"])
        return ret


class EnvironmentalReportCreateSerializer(serializers.ModelSerializer):
    nonconformities = EnvironmentalNonconformitySerializer(many=True, required=False)
    photos = EnvironmentalPhotoInputSerializer(many=True, required=False)

    class Meta:
        model = EnvironmentalReport
        fields = [
            "branch",
            "revision",
            "report_date",
            "site_name",
            "inspection_form",
            "inspector_position",
            "inspector_full_name",
            "unit_representative_position",
            "unit_representative_full_name",
            "nonconformities",
            "photos",
        ]

    def create(self, validated_data):
        nonconformities = validated_data.pop("nonconformities", [])
        photos = validated_data.pop("photos", [])

        report = EnvironmentalReport.objects.create(**validated_data)

        for row in nonconformities:
            EnvironmentalNonconformity.objects.create(report=report, **row)

        for p in photos:
            EnvironmentalPhoto.objects.create(
                report=report,
                caption=p.get("caption", ""),
                order_number=p.get("order_number", 1),
                image=p["image_file"],
            )

        return report

