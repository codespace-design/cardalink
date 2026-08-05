from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Estate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="estates",
    )
    name = models.CharField(_("Estate Name"), max_length=255)
    location = models.CharField(_("Location / District"), max_length=255, default="Idukki, Kerala")
    area_in_acres = models.DecimalField(_("Area (Acres)"), max_digits=8, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class HarvestBatch(models.Model):
    GRADE_CHOICES = [
        ("AGEB", "Alleppey Green Extra Bold"),
        ("AGB", "Alleppey Green Bold"),
        ("AGS", "Alleppey Green Superior"),
        ("UNGRADED", "Ungraded / Mixed"),
    ]

    estate = models.ForeignKey(Estate, on_delete=models.CASCADE, related_name="harvest_batches")
    harvest_date = models.DateField(_("Harvest Date"))
    weight_kg = models.DecimalField(_("Weight (kg)"), max_digits=10, decimal_places=2)
    grade = models.CharField(_("Cardamom Grade"), max_length=20, choices=GRADE_CHOICES, default="UNGRADED")
    quality_certificate = models.FileField(upload_to="certificates/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.estate.name} - {self.grade} ({self.weight_kg} kg)"
