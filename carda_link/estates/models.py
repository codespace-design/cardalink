from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


from django.urls import reverse


class Estate(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="estates",
    )
    name = models.CharField(_("Estate Name"), max_length=255)
    owner_name = models.CharField(
        _("Owner / Contact Person Name"),
        max_length=255,
        blank=True,
        default="",
    )
    phone_number = models.CharField(
        _("Contact Phone Number"),
        max_length=20,
        blank=True,
        default="",
    )
    address = models.TextField(
        _("Estate Full Address"),
        blank=True,
        default="",
    )
    location = models.CharField(
        _("Location / District"),
        max_length=255,
        default="Idukki, Kerala",
    )
    area_in_acres = models.DecimalField(
        _("Area (Acres)"),
        max_digits=8,
        decimal_places=2,
        default=1.00,
    )
    description = models.TextField(
        _("Estate Description / Overview"),
        blank=True,
        default="",
    )
    primary_photo = models.ImageField(
        _("Primary Cover Photo"),
        upload_to="estates/photos/",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("estates:detail", kwargs={"pk": self.pk})

    @property
    def total_harvest_kg(self):
        return sum(batch.weight_kg for batch in self.harvest_batches.all())


class EstatePhoto(models.Model):
    estate = models.ForeignKey(
        Estate,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(_("Estate Photo"), upload_to="estates/gallery/")
    caption = models.CharField(
        _("Photo Caption"),
        max_length=255,
        blank=True,
        default="",
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Photo for {self.estate.name} ({self.id})"


class HarvestBatch(models.Model):
    GRADE_CHOICES = [
        ("AGEB", "Alleppey Green Extra Bold"),
        ("AGB", "Alleppey Green Bold"),
        ("AGS", "Alleppey Green Superior"),
        ("UNGRADED", "Ungraded / Mixed"),
    ]

    estate = models.ForeignKey(
        Estate,
        on_delete=models.CASCADE,
        related_name="harvest_batches",
    )
    harvest_date = models.DateField(_("Harvest Date"))
    weight_kg = models.DecimalField(
        _("Weight (kg)"),
        max_digits=10,
        decimal_places=2,
    )
    grade = models.CharField(
        _("Cardamom Grade"),
        max_length=20,
        choices=GRADE_CHOICES,
        default="UNGRADED",
    )
    quality_certificate = models.FileField(
        upload_to="certificates/",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.estate.name} - {self.grade} ({self.weight_kg} kg)"
