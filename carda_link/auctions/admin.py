from django.contrib import admin

from carda_link.auctions.models import Auction
from carda_link.auctions.models import Bid
from carda_link.auctions.models import Lot


class LotInline(admin.TabularInline):
    model = Lot
    extra = 1
    fields = (
        "lot_number",
        "harvest_batch",
        "base_price_per_kg",
        "highest_bid_per_kg",
        "is_sold",
    )
    readonly_fields = ("highest_bid_per_kg",)


class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    readonly_fields = ("bidder", "amount_per_kg", "timestamp")
    can_delete = False


@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "status",
        "start_time",
        "end_time",
        "created_at",
        "is_active_now",
    )
    list_filter = ("status", "start_time", "end_time")
    search_fields = ("title",)
    inlines = [LotInline]
    actions = ["action_close_auctions", "action_mark_active"]

    @admin.action(description="Close selected auctions and finalize sales")
    def action_close_auctions(self, request, queryset):
        for auction in queryset:
            auction.close_auction()
        self.message_user(request, f"Closed {queryset.count()} auction(s).")

    @admin.action(description="Set selected auctions status to ACTIVE")
    def action_mark_active(self, request, queryset):
        updated = queryset.update(status="ACTIVE")
        self.message_user(request, f"Marked {updated} auction(s) as ACTIVE.")


@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "lot_number",
        "auction",
        "harvest_batch",
        "base_price_per_kg",
        "highest_bid_per_kg",
        "is_sold",
    )
    list_filter = ("is_sold", "auction__status", "harvest_batch__grade")
    search_fields = ("lot_number", "auction__title", "harvest_batch__estate__name")
    inlines = [BidInline]


@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ("id", "lot", "bidder", "amount_per_kg", "timestamp")
    list_filter = ("timestamp",)
    search_fields = ("bidder__email", "bidder__name", "lot__lot_number")
    readonly_fields = ("lot", "bidder", "amount_per_kg", "timestamp")
