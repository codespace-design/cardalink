from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

User = get_user_model()

ACTIVE = 'ACTIVE'
PENDING = 'PENDING'
COMPLETED = 'COMPLETED'
UPCOMING = 'UPCOMING'


class Command(BaseCommand):
    help = 'Seed full demo data for CardaLink admin dashboard testing.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear demo data before seeding.')

    @transaction.atomic
    def handle(self, *args, **options):
        from carda_link.auctions.models import Auction, Bid, Lot
        from carda_link.estates.models import Estate, HarvestBatch
        from carda_link.invoicing.models import Invoice, PlatformSettings
        from carda_link.users.models import AdminActionLog, BuyerProfile, SellerProfile, log_admin_action

        now = timezone.now()
        today = now.date()

        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing demo data...'))
            Invoice.objects.all().delete()
            Bid.objects.all().delete()
            Lot.objects.all().delete()
            Auction.objects.all().delete()
            HarvestBatch.objects.all().delete()
            Estate.objects.all().delete()
            AdminActionLog.objects.all().delete()
            User.objects.filter(is_superuser=False).exclude(email='admin@cardalink.com').delete()
            self.stdout.write(self.style.SUCCESS('Cleared.'))

        # Platform settings
        ps = PlatformSettings.load()
        ps.commission_percent = Decimal('2.50')
        ps.save()

        # Admin user
        admin_user, _ = User.objects.get_or_create(
            email='admin@cardalink.com',
            defaults=dict(name='System Administrator', role=User.Role.ADMIN,
                          status=User.Status.ACTIVE, is_staff=True, is_superuser=True, is_verified=True),
        )
        if not admin_user.has_usable_password():
            admin_user.set_password('Admin@2026!')
            admin_user.save()
        self.stdout.write(self.style.SUCCESS('[OK] Admin & Settings'))

        # Sellers
        SELLERS = [
            ('rajan.puthussery@cardalink.com', 'Rajan Puthussery', '+919447112233', 'Vandanmedu, Idukki, Kerala',
             dict(farm_name='Puthussery Green Valley Farm', farm_location='Vandanmedu', farm_area=Decimal('38.50'), area_unit='ACRE', cardamom_plants=4200)),
            ('biju.varghese@cardalink.com', 'Biju Varghese', '+919447223344', 'Kumily, Idukki, Kerala',
             dict(farm_name='Varghese Highlands Cardamom', farm_location='Kumily', farm_area=Decimal('52.00'), area_unit='ACRE', cardamom_plants=5800)),
            ('thomas.kurian@cardalink.com', 'Thomas Kurian', '+919447334455', 'Rajakkad, Idukki, Kerala',
             dict(farm_name='Kurian Brothers Estate', farm_location='Rajakkad', farm_area=Decimal('28.75'), area_unit='ACRE', cardamom_plants=3100)),
            ('suma.jose@cardalink.com', 'Suma Jose', '+919447445566', 'Nedumkandam, Idukki, Kerala',
             dict(farm_name='Jose Agro Cardamom Estate', farm_location='Nedumkandam', farm_area=Decimal('19.50'), area_unit='ACRE', cardamom_plants=2100)),
        ]
        created_sellers = []
        for email, name, phone, addr, profile in SELLERS:
            u, created = User.objects.get_or_create(email=email, defaults=dict(
                name=name, phone_number=phone, address=addr,
                role=User.Role.SELLER, status=User.Status.ACTIVE, is_verified=True))
            if created:
                u.set_password('Demo@2026!')
                u.save()
            SellerProfile.objects.get_or_create(user=u, defaults=profile)
            created_sellers.append(u)
        self.stdout.write(self.style.SUCCESS('[OK] 4 active sellers'))

        # Buyers
        BUYERS = [
            ('global.spices@cardalink.com', 'Global Spices Pvt Ltd', '+912244556677', 'Kochi, Kerala',
             dict(company_name='Global Spices Pvt Ltd', business_type='Wholesale Exporter', business_address='Kochi Port Trust, Kochi 682009')),
            ('highland.exports@cardalink.com', 'Highland Exports Ltd', '+912244667788', 'Munnar, Kerala',
             dict(company_name='Highland Exports Ltd', business_type='Spice Trader', business_address='Munnar Main Road, Idukki 685565')),
            ('kerala.cardamom@cardalink.com', 'Kerala Cardamom Board', '+912244778899', 'Trivandrum, Kerala',
             dict(company_name='Kerala Cardamom Board', business_type='Government Procurement', business_address='Thiruvananthapuram 695001')),
            ('spice.traders@cardalink.com', 'Eastern Spice Traders', '+912244889900', 'Chennai, Tamil Nadu',
             dict(company_name='Eastern Spice Traders', business_type='Domestic Wholesaler', business_address='T. Nagar, Chennai 600017')),
        ]
        created_buyers = []
        for email, name, phone, addr, profile in BUYERS:
            u, created = User.objects.get_or_create(email=email, defaults=dict(
                name=name, phone_number=phone, address=addr,
                role=User.Role.BUYER, status=User.Status.ACTIVE, is_verified=True))
            if created:
                u.set_password('Demo@2026!')
                u.save()
            BuyerProfile.objects.get_or_create(user=u, defaults=profile)
            created_buyers.append(u)
        self.stdout.write(self.style.SUCCESS('[OK] 4 active buyers'))
        buyer1, buyer2, buyer3, buyer4 = created_buyers

        # Pending registrations
        PENDING_USERS = [
            ('shyam.kumar@cardalink.com', 'Shyam Kumar', '+919988776655', User.Role.SELLER,
             dict(farm_name='Kumar Cardamom Farm', farm_location='Adimali', farm_area=Decimal('15.00'), area_unit='ACRE', cardamom_plants=1500)),
            ('anitha.pillai@cardalink.com', 'Anitha Pillai', '+919988665544', User.Role.SELLER,
             dict(farm_name='Pillai Green Cardamom', farm_location='Kattappana', farm_area=Decimal('22.00'), area_unit='ACRE', cardamom_plants=2300)),
            ('vijay.imports@cardalink.com', 'Vijay Imports Co', '+912233445566', User.Role.BUYER,
             dict(company_name='Vijay Imports Co', business_type='Import Re-export', business_address='Bengaluru 560022')),
        ]
        for email, name, phone, role, profile in PENDING_USERS:
            u, created = User.objects.get_or_create(email=email, defaults=dict(
                name=name, phone_number=phone, role=role, status=User.Status.PENDING, is_verified=False))
            if created:
                u.set_password('Demo@2026!')
                u.save()
            if role == User.Role.SELLER:
                SellerProfile.objects.get_or_create(user=u, defaults=profile)
            else:
                BuyerProfile.objects.get_or_create(user=u, defaults=profile)
        self.stdout.write(self.style.SUCCESS('[OK] 3 pending registrations'))

        # Rejected
        for email, name, phone, role, reason in [
            ('fake.farmer@cardalink.com', 'Fake Farmer', '+919911223344', User.Role.SELLER, 'Fraudulent land documents.'),
            ('blacklist.buyer@cardalink.com', 'Blacklist Buyer Co', '+912299887766', User.Role.BUYER, 'Expired license, duplicate app.'),
        ]:
            u, _ = User.objects.get_or_create(email=email, defaults=dict(
                name=name, phone_number=phone, role=role, status=User.Status.REJECTED,
                rejection_reason=reason, is_verified=False))
            if not u.has_usable_password():
                u.set_password('Demo@2026!')
                u.save()
        self.stdout.write(self.style.SUCCESS('[OK] 2 rejected users'))

        # Suspended
        for email, name, phone, role, reason, verified in [
            ('suspended.trader@cardalink.com', 'Suspended Trader Ltd', '+912299001122', User.Role.BUYER, 'Multiple failed payments.', True),
            ('fraud.seller@cardalink.com', 'Fraud Seller', '+919911334455', User.Role.SELLER, 'Misrepresented batch weights.', False),
        ]:
            u, _ = User.objects.get_or_create(email=email, defaults=dict(
                name=name, phone_number=phone, role=role, status=User.Status.SUSPENDED,
                suspension_reason=reason, is_verified=verified))
            if not u.has_usable_password():
                u.set_password('Demo@2026!')
                u.save()
        self.stdout.write(self.style.SUCCESS('[OK] 2 suspended users'))

        # Estates
        seller1, seller2, seller3, seller4 = created_sellers
        estates = []
        for owner, name, oname, phone, loc, area, desc in [
            (seller1, 'Puthussery Green Valley Estate', 'Rajan Puthussery', '+919447112233',
             'Vandanmedu, Idukki, Kerala', Decimal('38.50'), 'Premier organic cardamom estate. AGEB and AGB grades.'),
            (seller2, 'Varghese Highlands Estate', 'Biju Varghese', '+919447223344',
             'Kumily, Idukki, Kerala', Decimal('52.00'), 'High-altitude plantation at 1500m. Premium AGEB output.'),
            (seller3, 'Kurian Brothers Cardamom Estate', 'Thomas Kurian', '+919447334455',
             'Rajakkad, Idukki, Kerala', Decimal('28.75'), 'Family-run estate established 1985. AGB and AGS grades.'),
            (seller4, 'Jose Agro Cardamom Farm', 'Suma Jose', '+919447445566',
             'Nedumkandam, Idukki, Kerala', Decimal('19.50'), 'Smallholder organic cardamom farm. AGS specialty.'),
        ]:
            est, _ = Estate.objects.get_or_create(owner=owner, name=name, defaults=dict(
                owner_name=oname, phone_number=phone, location=loc, area_in_acres=area, description=desc))
            estates.append(est)
        self.stdout.write(self.style.SUCCESS('[OK] 4 estates'))

        e1, e2, e3, e4 = estates
        batches = []
        BATCH_DATA = [
            (e1, 'AGEB', '650.00', 10), (e1, 'AGB', '800.00', 8), (e1, 'UNGRADED', '420.00', 2),
            (e2, 'AGEB', '920.00', 15), (e2, 'AGS', '550.00', 6), (e2, 'UNGRADED', '680.00', 1),
            (e3, 'AGB', '430.00', 12), (e3, 'AGS1', '310.00', 7), (e3, 'UNGRADED', '280.00', 3),
            (e4, 'AGS', '200.00', 5), (e4, 'UNGRADED', '150.00', 0),
        ]
        for est, grade, wt, days_ago in BATCH_DATA:
            hb, _ = HarvestBatch.objects.get_or_create(
                estate=est, grade=grade, weight_kg=Decimal(wt),
                defaults=dict(harvest_date=today - timedelta(days=days_ago) if days_ago else today))
            batches.append(hb)
        self.stdout.write(self.style.SUCCESS('[OK] 11 harvest batches'))

        ageb1, agb1 = batches[0], batches[1]
        ageb2, ags2 = batches[3], batches[4]
        agb3, ags1_3 = batches[6], batches[7]
        ags4 = batches[9]

        # Auctions
        active_auction, _ = Auction.objects.get_or_create(
            title='Idukki Premium Cardamom Auction #2026-A1 (Live)',
            defaults=dict(start_time=now - timedelta(hours=2), end_time=now + timedelta(hours=4),
                          status='ACTIVE', description='Live bidding for AGEB and AGB premium lots.'))
        upcoming1, _ = Auction.objects.get_or_create(
            title='Spices Board Certified Export Lot Auction #2026-A2',
            defaults=dict(start_time=now + timedelta(days=1), end_time=now + timedelta(days=1, hours=6),
                          status='UPCOMING'))
        upcoming2, _ = Auction.objects.get_or_create(
            title='Western Ghats Bulk Cardamom Auction #2026-A3',
            defaults=dict(start_time=now + timedelta(days=5), end_time=now + timedelta(days=5, hours=8),
                          status='UPCOMING'))
        completed_auction, _ = Auction.objects.get_or_create(
            title='Monsoon Harvest Cardamom Auction #2026-A0',
            defaults=dict(start_time=now - timedelta(days=7),
                          end_time=now - timedelta(days=7) + timedelta(hours=6), status='COMPLETED'))
        Auction.objects.get_or_create(
            title='Emergency Pre-monsoon Lot Clearance (Cancelled)',
            defaults=dict(start_time=now - timedelta(days=3), end_time=now - timedelta(days=2),
                          status='CANCELLED', cancellation_reason='Insufficient lot registrations.'))
        self.stdout.write(self.style.SUCCESS('[OK] 5 auctions'))

        # Lots
        lot_a1, _ = Lot.objects.get_or_create(auction=active_auction, harvest_batch=ageb1,
            defaults=dict(lot_number=1, base_price_per_kg=Decimal('1850.00')))
        lot_a2, _ = Lot.objects.get_or_create(auction=active_auction, harvest_batch=agb1,
            defaults=dict(lot_number=2, base_price_per_kg=Decimal('1600.00')))
        lot_a3, _ = Lot.objects.get_or_create(auction=active_auction, harvest_batch=ageb2,
            defaults=dict(lot_number=3, base_price_per_kg=Decimal('1900.00')))
        Lot.objects.get_or_create(auction=upcoming1, harvest_batch=ags2,
            defaults=dict(lot_number=1, base_price_per_kg=Decimal('1450.00')))
        Lot.objects.get_or_create(auction=upcoming1, harvest_batch=agb3,
            defaults=dict(lot_number=2, base_price_per_kg=Decimal('1550.00')))
        Lot.objects.get_or_create(auction=upcoming2, harvest_batch=ags1_3,
            defaults=dict(lot_number=1, base_price_per_kg=Decimal('1300.00')))
        lot_c1, _ = Lot.objects.get_or_create(auction=completed_auction, harvest_batch=ags4,
            defaults=dict(lot_number=1, base_price_per_kg=Decimal('1400.00'),
                          highest_bid_per_kg=Decimal('1750.00'), is_sold=True))
        self.stdout.write(self.style.SUCCESS('[OK] 7 lots'))

        # Bids
        if not lot_a1.bids.exists():
            lot_a1.place_bid(buyer1, Decimal('1900.00'))
            lot_a1.place_bid(buyer2, Decimal('1980.00'))
            lot_a1.place_bid(buyer3, Decimal('2050.00'))
            lot_a1.place_bid(buyer1, Decimal('2120.00'))
        if not lot_a2.bids.exists():
            lot_a2.place_bid(buyer2, Decimal('1650.00'))
            lot_a2.place_bid(buyer4, Decimal('1720.00'))
        if not lot_a3.bids.exists():
            lot_a3.place_bid(buyer3, Decimal('1950.00'))
            lot_a3.place_bid(buyer1, Decimal('2010.00'))
        self.stdout.write(self.style.SUCCESS('[OK] 10 bids'))

        # Invoices
        lot_c1.refresh_from_db()
        if not Invoice.objects.filter(lot=lot_c1).exists():
            w = ags4.weight_kg
            h = lot_c1.highest_bid_per_kg or Decimal('1750.00')
            total = w * h
            Invoice.objects.create(lot=lot_c1, buyer=buyer2,
                total_amount=total, commission_fee=total * Decimal('0.025'),
                status='PAID', paid_at=now - timedelta(days=6),
                status_note='Payment received via NEFT.', updated_by=admin_user)
        lot_a2.refresh_from_db()
        if lot_a2.highest_bid_per_kg and not Invoice.objects.filter(lot=lot_a2).exists():
            w = agb1.weight_kg
            total = w * lot_a2.highest_bid_per_kg
            Invoice.objects.create(lot=lot_a2, buyer=buyer4,
                total_amount=total, commission_fee=total * Decimal('0.025'),
                status='PENDING', status_note='Awaiting buyer payment.')
        self.stdout.write(self.style.SUCCESS('[OK] Invoices'))

        # Admin logs
        if not AdminActionLog.objects.exists():
            log_admin_action(admin_user, 'APPROVE', seller1, 'Documents verified by Spices Board.')
            log_admin_action(admin_user, 'APPROVE', buyer1, 'KYC complete. License verified.')
            log_admin_action(admin_user, 'APPROVE', seller2, 'Estate inspection passed.')
            log_admin_action(admin_user, 'APPROVE', seller3, 'All paperwork submitted correctly.')
            fake = User.objects.filter(email='fake.farmer@cardalink.com').first()
            if fake:
                log_admin_action(admin_user, 'REJECT', fake, 'Fraudulent documents detected.')
            susp = User.objects.filter(email='suspended.trader@cardalink.com').first()
            if susp:
                log_admin_action(admin_user, 'SUSPEND', susp, 'Multiple payment failures.')
            log_admin_action(admin_user, 'SCHEDULE_AUCTION', active_auction, 'Scheduled per board request.')
            paid_inv = Invoice.objects.filter(status='PAID').first()
            if paid_inv:
                log_admin_action(admin_user, 'MARK_INVOICE_PAID', paid_inv, 'Bank statement confirmed.')
        self.stdout.write(self.style.SUCCESS('[OK] Admin action logs'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('  CardaLink Demo Data Seeded Successfully!'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write('  Admin:      admin@cardalink.com / Admin@2026!')
        self.stdout.write('  Sellers:    ' + str(User.objects.filter(role=User.Role.SELLER, status=User.Status.ACTIVE).count()) + ' active')
        self.stdout.write('  Buyers:     ' + str(User.objects.filter(role=User.Role.BUYER, status=User.Status.ACTIVE).count()) + ' active')
        self.stdout.write('  Pending:    ' + str(User.objects.filter(status=User.Status.PENDING).count()))
        self.stdout.write('  Rejected:   ' + str(User.objects.filter(status=User.Status.REJECTED).count()))
        self.stdout.write('  Suspended:  ' + str(User.objects.filter(status=User.Status.SUSPENDED).count()))
        self.stdout.write('  Estates:    ' + str(Estate.objects.count()))
        self.stdout.write('  Batches:    ' + str(HarvestBatch.objects.count()) + ' (' + str(HarvestBatch.objects.filter(grade='UNGRADED').count()) + ' ungraded)')
        self.stdout.write('  Auctions:   ' + str(Auction.objects.count()))
        self.stdout.write('  Lots:       ' + str(Lot.objects.count()))
        self.stdout.write('  Bids:       ' + str(Bid.objects.count()))
        self.stdout.write('  Invoices:   ' + str(Invoice.objects.count()))
        self.stdout.write('  Logs:       ' + str(AdminActionLog.objects.count()))
        self.stdout.write('')
