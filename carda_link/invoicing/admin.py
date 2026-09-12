from django.contrib import admin
from .models import Invoice, PlatformSettings


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["id", "lot", "buyer", "total_amount", "commission_fee", "status", "issued_at", "paid_at", "updated_by"]
    list_filter = ["status", "issued_at", "paid_at"]
    search_fields = ["buyer__email", "lot__lot_number", "id", "status_note"]
    readonly_fields = ["issued_at"]


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ["commission_percent", "updated_at", "updated_by"]
    readonly_fields = ["updated_at"]

    def has_add_permission(self, request):
        # Enforce singleton
        return not PlatformSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
