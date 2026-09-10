from django.contrib import admin
from django.utils.html import format_html

from .models import Estate
from .models import EstatePhoto
from .models import HarvestBatch


class EstatePhotoInline(admin.TabularInline):
    model = EstatePhoto
    extra = 1
    readonly_fields = ["photo_preview", "uploaded_at"]

    def photo_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 80px; border-radius: 6px;" />', obj.image.url)
        return "-"

    photo_preview.short_description = "Preview"


class HarvestBatchInline(admin.TabularInline):
    model = HarvestBatch
    extra = 0
    fields = ["harvest_date", "weight_kg", "grade", "quality_certificate"]


@admin.register(Estate)
class EstateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner_name",
        "owner",
        "phone_number",
        "location",
        "area_in_acres",
        "photo_count",
        "created_at",
    ]
    list_filter = ["location", "created_at"]
    search_fields = ["name", "owner_name", "phone_number", "address", "location", "owner__email"]
    inlines = [EstatePhotoInline, HarvestBatchInline]

    def photo_count(self, obj):
        return obj.photos.count()

    photo_count.short_description = "Photos"


@admin.register(EstatePhoto)
class EstatePhotoAdmin(admin.ModelAdmin):
    list_display = ["id", "estate", "caption", "uploaded_at", "photo_preview"]
    list_filter = ["uploaded_at"]
    search_fields = ["estate__name", "caption"]

    def photo_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 60px; border-radius: 4px;" />', obj.image.url)
        return "-"

    photo_preview.short_description = "Preview"


@admin.register(HarvestBatch)
class HarvestBatchAdmin(admin.ModelAdmin):
    list_display = ["estate", "harvest_date", "weight_kg", "grade", "created_at"]
    list_filter = ["grade", "harvest_date"]
    search_fields = ["estate__name"]
