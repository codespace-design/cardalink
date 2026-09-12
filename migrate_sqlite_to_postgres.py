import os
import sys
import sqlite3
from pathlib import Path
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import connection, transaction
from django.core.management.color import no_style
from carda_link.users.models import User, SellerProfile, BuyerProfile
from carda_link.estates.models import Estate, HarvestBatch
from carda_link.auctions.models import Auction, Lot, Bid

def run_migration():
    sqlite_path = Path("/app/db.sqlite3")
    if not sqlite_path.exists():
        sqlite_path = Path(__file__).resolve().parent / "db.sqlite3"
    
    print(f"Connecting to SQLite database at: {sqlite_path}")
    sqlite_conn = sqlite3.connect(str(sqlite_path))
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()

    with transaction.atomic():
        user_id_map = {}
        estate_id_map = {}
        batch_id_map = {}
        auction_id_map = {}
        lot_id_map = {}

        # -------------------------------------------------------------
        # 1. Migrate Users
        # -------------------------------------------------------------
        print("\n--- Migrating Users ---")
        sqlite_cur.execute("SELECT * FROM users_user ORDER BY id")
        sqlite_users = sqlite_cur.fetchall()
        for u in sqlite_users:
            email = u["email"].strip().lower()
            password = u["password"]
            
            # Check if user already exists in PostgreSQL
            pg_user = User.objects.filter(email__iexact=email).first()
            if not pg_user:
                pg_user = User(email=email)
            
            # Preserve or set password
            if password:
                pg_user.password = password
            elif not pg_user.password:
                pg_user.set_password("Password@123")
                
            pg_user.name = u["name"] or ""
            pg_user.role = u["role"] or User.Role.BUYER
            pg_user.status = u["status"] or User.Status.PENDING
            pg_user.phone_number = u["phone_number"]
            pg_user.address = u["address"] or ""
            pg_user.license_number = u["license_number"] or ""
            pg_user.is_verified = bool(u["is_verified"])
            pg_user.is_staff = bool(u["is_staff"])
            pg_user.is_superuser = bool(u["is_superuser"])
            pg_user.is_active = (pg_user.status == User.Status.ACTIVE)
            
            # Save avoiding phone number unique collision if duplicate nulls
            try:
                pg_user.save()
            except Exception as e:
                if "phone_number" in str(e).lower():
                    pg_user.phone_number = None
                    pg_user.save()
                else:
                    raise e
                    
            user_id_map[u["id"]] = pg_user.id
            print(f"  [User] SQLite id={u['id']} -> PostgreSQL id={pg_user.id} ({email}, role={pg_user.role}, status={pg_user.status})")

        # -------------------------------------------------------------
        # 2. Migrate Seller Profiles
        # -------------------------------------------------------------
        print("\n--- Migrating Seller Profiles ---")
        sqlite_cur.execute("SELECT * FROM users_sellerprofile")
        for sp in sqlite_cur.fetchall():
            sqlite_uid = sp["user_id"]
            if sqlite_uid in user_id_map:
                pg_uid = user_id_map[sqlite_uid]
                profile, created = SellerProfile.objects.update_or_create(
                    user_id=pg_uid,
                    defaults={
                        "farm_name": sp["farm_name"] or "",
                        "farm_location": sp["farm_location"] or "",
                        "farm_area": sp["farm_area"] or 0,
                        "area_unit": sp["area_unit"] or "ACRE",
                        "cardamom_plants": sp["cardamom_plants"] or 0,
                        "cultivation_details": sp["cultivation_details"] or "",
                    }
                )
                print(f"  [SellerProfile] user_id={pg_uid} ({profile.farm_name}) - {'Created' if created else 'Updated'}")

        # -------------------------------------------------------------
        # 3. Migrate Buyer Profiles
        # -------------------------------------------------------------
        print("\n--- Migrating Buyer Profiles ---")
        sqlite_cur.execute("SELECT * FROM users_buyerprofile")
        for bp in sqlite_cur.fetchall():
            sqlite_uid = bp["user_id"]
            if sqlite_uid in user_id_map:
                pg_uid = user_id_map[sqlite_uid]
                profile, created = BuyerProfile.objects.update_or_create(
                    user_id=pg_uid,
                    defaults={
                        "company_name": bp["company_name"] or "",
                        "business_type": bp["business_type"] or "",
                        "business_address": bp["business_address"] or "",
                        "business_details": bp["business_details"] or "",
                    }
                )
                print(f"  [BuyerProfile] user_id={pg_uid} ({profile.company_name}) - {'Created' if created else 'Updated'}")

        # -------------------------------------------------------------
        # 4. Migrate Estates
        # -------------------------------------------------------------
        print("\n--- Migrating Estates ---")
        sqlite_cur.execute("SELECT * FROM estates_estate ORDER BY id")
        for est in sqlite_cur.fetchall():
            owner_id = user_id_map.get(est["owner_id"])
            if not owner_id:
                # fallback to first seller or admin
                owner = User.objects.filter(role=User.Role.SELLER).first() or User.objects.filter(is_staff=True).first()
                owner_id = owner.id

            estate, created = Estate.objects.update_or_create(
                id=est["id"],
                defaults={
                    "name": est["name"],
                    "location": est["location"] or "",
                    "address": est["address"] or "",
                    "description": est["description"] or "",
                    "owner_name": est["owner_name"] or "",
                    "phone_number": est["phone_number"] or "",
                    "area_in_acres": est["area_in_acres"] or 0,
                    "owner_id": owner_id,
                }
            )
            estate_id_map[est["id"]] = estate.id
            print(f"  [Estate] id={estate.id} ({estate.name}, owner_id={owner_id}) - {'Created' if created else 'Updated'}")

        # -------------------------------------------------------------
        # 5. Migrate Harvest Batches
        # -------------------------------------------------------------
        print("\n--- Migrating Harvest Batches ---")
        sqlite_cur.execute("SELECT * FROM estates_harvestbatch ORDER BY id")
        for hb in sqlite_cur.fetchall():
            estate_id = estate_id_map.get(hb["estate_id"])
            if not estate_id:
                continue
            batch, created = HarvestBatch.objects.update_or_create(
                id=hb["id"],
                defaults={
                    "estate_id": estate_id,
                    "harvest_date": hb["harvest_date"],
                    "weight_kg": hb["weight_kg"],
                    "grade": hb["grade"] or "A",
                }
            )
            batch_id_map[hb["id"]] = batch.id
            print(f"  [HarvestBatch] id={batch.id} (grade={batch.grade}, weight={batch.weight_kg}kg, estate_id={estate_id})")

        # -------------------------------------------------------------
        # 6. Migrate Auctions
        # -------------------------------------------------------------
        print("\n--- Migrating Auctions ---")
        sqlite_cur.execute("SELECT * FROM auctions_auction ORDER BY id")
        for auc in sqlite_cur.fetchall():
            auction, created = Auction.objects.update_or_create(
                id=auc["id"],
                defaults={
                    "title": auc["title"],
                    "start_time": auc["start_time"],
                    "end_time": auc["end_time"],
                    "status": auc["status"],
                }
            )
            auction_id_map[auc["id"]] = auction.id
            print(f"  [Auction] id={auction.id} ({auction.title}, status={auction.status})")

        # -------------------------------------------------------------
        # 7. Migrate Lots
        # -------------------------------------------------------------
        print("\n--- Migrating Lots ---")
        sqlite_cur.execute("SELECT * FROM auctions_lot ORDER BY id")
        for lot in sqlite_cur.fetchall():
            auc_id = auction_id_map.get(lot["auction_id"])
            batch_id = batch_id_map.get(lot["harvest_batch_id"])
            if not auc_id or not batch_id:
                continue
            pg_lot, created = Lot.objects.update_or_create(
                id=lot["id"],
                defaults={
                    "auction_id": auc_id,
                    "harvest_batch_id": batch_id,
                    "lot_number": lot["lot_number"],
                    "base_price_per_kg": lot["base_price_per_kg"],
                    "highest_bid_per_kg": lot["highest_bid_per_kg"],
                    "is_sold": bool(lot["is_sold"]),
                }
            )
            lot_id_map[lot["id"]] = pg_lot.id
            print(f"  [Lot] id={pg_lot.id} (lot_number={pg_lot.lot_number}, auction_id={auc_id})")

        # -------------------------------------------------------------
        # 8. Migrate Bids
        # -------------------------------------------------------------
        print("\n--- Migrating Bids ---")
        sqlite_cur.execute("SELECT * FROM auctions_bid ORDER BY id")
        for bid in sqlite_cur.fetchall():
            bidder_id = user_id_map.get(bid["bidder_id"])
            lot_id = lot_id_map.get(bid["lot_id"])
            if not bidder_id or not lot_id:
                continue
            pg_bid, created = Bid.objects.update_or_create(
                id=bid["id"],
                defaults={
                    "bidder_id": bidder_id,
                    "lot_id": lot_id,
                    "amount_per_kg": bid["amount_per_kg"],
                    "timestamp": bid["timestamp"],
                }
            )
            print(f"  [Bid] id={pg_bid.id} (bidder_id={bidder_id}, lot_id={lot_id}, amount={pg_bid.amount_per_kg})")

        # -------------------------------------------------------------
        # 9. Reset PostgreSQL ID Sequences
        # -------------------------------------------------------------
        print("\n--- Resetting PostgreSQL Primary Key Sequences ---")
        models_to_reset = [User, SellerProfile, BuyerProfile, Estate, HarvestBatch, Auction, Lot, Bid]
        sequence_sql = connection.ops.sequence_reset_sql(no_style(), models_to_reset)
        with connection.cursor() as cursor:
            for sql in sequence_sql:
                cursor.execute(sql)
        print("Sequences reset successfully!")

    print("\nSUCCESS: All SQLite records successfully migrated into PostgreSQL!")

if __name__ == "__main__":
    run_migration()
