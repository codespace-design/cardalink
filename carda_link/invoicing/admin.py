from django.contrib import admin
from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lot",
        "buyer",
        "total_amount",
        "commission_fee",
        "status",
        "issued_at",
        "paid_at",
    )
    list_filter = ("status", "issued_at")
    search_fields = ("id", "buyer__email", "buyer__first_name", "buyer__last_name", "lot__lot_number")
    readonly_fields = ("issued_at",)
