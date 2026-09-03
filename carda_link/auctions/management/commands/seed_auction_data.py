from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from carda_link.auctions.models import Auction
from carda_link.auctions.models import Lot
from carda_link.estates.models import Estate
from carda_link.estates.models import HarvestBatch

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Seed mock cardamom estate, harvest batches, active/upcoming auctions, "
        "lots, and bids for simulation."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.MIGRATE_HEADING("Seeding CardaLink Auction Simulation Data..."),
        )

        # 1. Create Users
        _auctioneer, _ = User.objects.get_or_create(
            email="auctioneer@cardalink.com",
            defaults={
                "name": "Idukki Auctioneer",
                "role": "AUCTIONEER",
                "is_verified": True,
            },
        )

        seller, _ = User.objects.get_or_create(
            email="farmer_idukki@cardalink.com",
            defaults={
                "name": "Ramesh Kumar (Estate Owner)",
                "role": "SELLER",
                "is_verified": True,
            },
        )

        buyer1, _ = User.objects.get_or_create(
            email="buyer_spices1@cardalink.com",
            defaults={
                "name": "Global Spices Traders",
                "role": "BUYER",
                "is_verified": True,
            },
        )

        buyer2, _ = User.objects.get_or_create(
            email="buyer_spices2@cardalink.com",
            defaults={
                "name": "Highland Exporters",
                "role": "BUYER",
                "is_verified": True,
            },
        )

        buyer3, _ = User.objects.get_or_create(
            email="buyer_export@cardalink.com",
            defaults={
                "name": "Green Cardamom Intl",
                "role": "BUYER",
                "is_verified": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("[OK] Verified users created."))

        # 2. Create Estate
        estate, _ = Estate.objects.get_or_create(
            owner=seller,
            name="Green Valley Cardamom Estate",
            defaults={
                "location": "Vandanmedu, Idukki District, Kerala",
                "area_in_acres": Decimal("45.50"),
            },
        )
        self.stdout.write(self.style.SUCCESS(f"[OK] Estate created: {estate.name}"))

        # 3. Create Harvest Batches
        now = timezone.now()
        today = now.date()

        batch1, _ = HarvestBatch.objects.get_or_create(
            estate=estate,
            grade="AGEB",
            weight_kg=Decimal("650.00"),
            defaults={"harvest_date": today - timedelta(days=5)},
        )

        batch2, _ = HarvestBatch.objects.get_or_create(
            estate=estate,
            grade="AGB",
            weight_kg=Decimal("800.00"),
            defaults={"harvest_date": today - timedelta(days=3)},
        )

        batch3, _ = HarvestBatch.objects.get_or_create(
            estate=estate,
            grade="AGS",
            weight_kg=Decimal("450.00"),
            defaults={"harvest_date": today - timedelta(days=2)},
        )

        batch4, _ = HarvestBatch.objects.get_or_create(
            estate=estate,
            grade="UNGRADED",
            weight_kg=Decimal("1200.00"),
            defaults={"harvest_date": today - timedelta(days=1)},
        )

        self.stdout.write(
            self.style.SUCCESS(
                "[OK] 4 Harvest Batches (AGEB, AGB, AGS, UNGRADED) created.",
            ),
        )

        # 4. Create Active Auction
        active_auction, _ = Auction.objects.get_or_create(
            title="Idukki Spices Auction #101 (Live Bidding)",
            defaults={
                "start_time": now - timedelta(hours=1),
                "end_time": now + timedelta(hours=5),
                "status": "ACTIVE",
            },
        )

        # 5. Create Upcoming Auction
        upcoming_auction, _ = Auction.objects.get_or_create(
            title="Premium Export Grade Cardamom Auction #102",
            defaults={
                "start_time": now + timedelta(days=1),
                "end_time": now + timedelta(days=1, hours=6),
                "status": "UPCOMING",
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Active Auction #{active_auction.id} & "
                f"Upcoming Auction #{upcoming_auction.id} created.",
            ),
        )

        # 6. Assign Lots to Active Auction
        lot1, _ = Lot.objects.get_or_create(
            auction=active_auction,
            harvest_batch=batch1,
            defaults={
                "lot_number": 1,
                "base_price_per_kg": Decimal("1850.00"),
            },
        )

        lot2, _ = Lot.objects.get_or_create(
            auction=active_auction,
            harvest_batch=batch2,
            defaults={
                "lot_number": 2,
                "base_price_per_kg": Decimal("1600.00"),
            },
        )

        _lot3, _ = Lot.objects.get_or_create(
            auction=active_auction,
            harvest_batch=batch3,
            defaults={
                "lot_number": 3,
                "base_price_per_kg": Decimal("1450.00"),
            },
        )

        # Assign Lot to Upcoming Auction
        _lot4, _ = Lot.objects.get_or_create(
            auction=upcoming_auction,
            harvest_batch=batch4,
            defaults={
                "lot_number": 1,
                "base_price_per_kg": Decimal("1200.00"),
            },
        )

        self.stdout.write(
            self.style.SUCCESS("[OK] 4 Catalog Lots assigned across auctions."),
        )

        # 7. Seed Initial Bids on Active Lots
        if not lot1.bids.exists():
            lot1.place_bid(bidder=buyer1, amount_per_kg=Decimal("1900.00"))
            lot1.place_bid(bidder=buyer2, amount_per_kg=Decimal("1980.00"))
            lot1.place_bid(bidder=buyer3, amount_per_kg=Decimal("2050.00"))

        if not lot2.bids.exists():
            lot2.place_bid(bidder=buyer2, amount_per_kg=Decimal("1650.00"))

        self.stdout.write(
            self.style.SUCCESS("[OK] Initial realistic bidding sequence created."),
        )
        self.stdout.write(
            self.style.SUCCESS(
                "=== CardaLink Auction Simulation Data Seeding "
                "Completed Successfully! ===",
            ),
        )
