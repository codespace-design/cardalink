from typing import List, Optional

from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from carda_link.auctions.models import Auction
from carda_link.auctions.models import Bid
from carda_link.auctions.models import Lot
from carda_link.auctions.schemas import AuctionCreateSchema
from carda_link.auctions.schemas import AuctionDetailOutSchema
from carda_link.auctions.schemas import AuctionOutSchema
from carda_link.auctions.schemas import AuctionUpdateSchema
from carda_link.auctions.schemas import BidCreateSchema
from carda_link.auctions.schemas import BidOutSchema
from carda_link.auctions.schemas import LotCreateSchema
from carda_link.auctions.schemas import LotOutSchema
from carda_link.auctions.schemas import MessageResponseSchema
from carda_link.estates.models import HarvestBatch

router = Router(tags=["Auctions & Live Bidding Engine"])


def _serialize_auction(auction: Auction) -> AuctionOutSchema:
    return AuctionOutSchema(
        id=auction.id,
        title=auction.title,
        start_time=auction.start_time,
        end_time=auction.end_time,
        status=auction.status,
        status_display=auction.get_status_display(),
        is_active_now=auction.is_active_now,
        created_at=auction.created_at,
        lot_count=auction.lots.count(),
    )


def _serialize_auction_detail(auction: Auction) -> AuctionDetailOutSchema:
    lots_out = [LotOutSchema.from_orm_model(lot) for lot in auction.lots.select_related("harvest_batch__estate").all()]
    return AuctionDetailOutSchema(
        id=auction.id,
        title=auction.title,
        start_time=auction.start_time,
        end_time=auction.end_time,
        status=auction.status,
        status_display=auction.get_status_display(),
        is_active_now=auction.is_active_now,
        created_at=auction.created_at,
        lot_count=len(lots_out),
        lots=lots_out,
    )


@router.get("/health-check", auth=None)
def auctions_health_check(request):
    return {"status": "ok", "module": "Live Auction Engine"}


@router.get("/", response=List[AuctionOutSchema], auth=None)
def list_auctions(request, status: Optional[str] = None):
    qs = Auction.objects.all()
    if status:
        qs = qs.filter(status=status.upper())
    for auction in qs:
        auction.auto_update_status()
    return [_serialize_auction(a) for a in qs]


@router.post("/", response=AuctionOutSchema, auth=None)
def create_auction(request, payload: AuctionCreateSchema):
    auction = Auction.objects.create(
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=payload.status.upper(),
    )
    return _serialize_auction(auction)


@router.get("/lots/", response=List[LotOutSchema], auth=None)
def list_lots(request, auction_id: Optional[int] = None, is_sold: Optional[bool] = None):
    qs = Lot.objects.select_related("harvest_batch__estate", "auction").all()
    if auction_id is not None:
        qs = qs.filter(auction_id=auction_id)
    if is_sold is not None:
        qs = qs.filter(is_sold=is_sold)
    return [LotOutSchema.from_orm_model(lot) for lot in qs]


@router.get("/{auction_id}/", response=AuctionDetailOutSchema, auth=None)
def retrieve_auction(request, auction_id: int):
    auction = get_object_or_404(Auction, pk=auction_id)
    auction.auto_update_status()
    return _serialize_auction_detail(auction)


@router.patch("/{auction_id}/", response=AuctionOutSchema, auth=None)
def update_auction(request, auction_id: int, payload: AuctionUpdateSchema):
    auction = get_object_or_404(Auction, pk=auction_id)
    for attr, value in payload.dict(exclude_unset=True).items():
        if value is not None:
            if attr == "status":
                value = value.upper()
            setattr(auction, attr, value)
    auction.save()
    return _serialize_auction(auction)


@router.post("/{auction_id}/close/", response=MessageResponseSchema, auth=None)
def close_auction(request, auction_id: int):
    auction = get_object_or_404(Auction, pk=auction_id)
    auction.close_auction()
    return MessageResponseSchema(message=f"Auction '{auction.title}' successfully closed and sold lots finalized.")


@router.post("/{auction_id}/lots/", response=LotOutSchema, auth=None)
def add_lot_to_auction(request, auction_id: int, payload: LotCreateSchema):
    auction = get_object_or_404(Auction, pk=auction_id)
    harvest_batch = get_object_or_404(HarvestBatch, pk=payload.harvest_batch_id)

    if hasattr(harvest_batch, "auction_lot"):
        raise HttpError(400, f"HarvestBatch #{harvest_batch.id} is already assigned to Lot #{harvest_batch.auction_lot.lot_number}.")

    lot = Lot.objects.create(
        auction=auction,
        harvest_batch=harvest_batch,
        lot_number=payload.lot_number,
        base_price_per_kg=payload.base_price_per_kg,
    )
    return LotOutSchema.from_orm_model(lot)


@router.get("/lots/{lot_id}/", response=LotOutSchema, auth=None)
def retrieve_lot(request, lot_id: int):
    lot = get_object_or_404(Lot.objects.select_related("harvest_batch__estate", "auction"), pk=lot_id)
    return LotOutSchema.from_orm_model(lot)


@router.post("/lots/{lot_id}/bids/", response=BidOutSchema, auth=None)
def place_bid_on_lot(request, lot_id: int, payload: BidCreateSchema):
    bidder = request.user if (request.user and request.user.is_authenticated) else None
    if not bidder:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        bidder = User.objects.filter(role="BUYER").first() or User.objects.filter(is_superuser=True).first() or User.objects.first()

    if not bidder:
        raise HttpError(401, "Authentication required to place bids.")

    lot = get_object_or_404(Lot.objects.select_related("auction"), pk=lot_id)
    lot.auction.auto_update_status()

    try:
        bid = lot.place_bid(bidder=bidder, amount_per_kg=payload.amount_per_kg)
    except ValueError as e:
        raise HttpError(400, str(e))

    bidder_name = getattr(bidder, "name", "") or getattr(bidder, "email", "Simulated Buyer")
    return BidOutSchema(
        id=bid.id,
        lot_id=lot.id,
        bidder_id=bidder.id,
        bidder_email=getattr(bidder, "email", "buyer@cardalink.com"),
        bidder_name=bidder_name,
        amount_per_kg=bid.amount_per_kg,
        timestamp=bid.timestamp,
    )


@router.get("/lots/{lot_id}/bids/", response=List[BidOutSchema], auth=None)
def list_lot_bids(request, lot_id: int):
    lot = get_object_or_404(Lot, pk=lot_id)
    bids = lot.bids.select_related("bidder").all()
    out = []
    for b in bids:
        b_name = getattr(b.bidder, "name", "") or b.bidder.email
        out.append(
            BidOutSchema(
                id=b.id,
                lot_id=lot.id,
                bidder_id=b.bidder.id,
                bidder_email=b.bidder.email,
                bidder_name=b_name,
                amount_per_kg=b.amount_per_kg,
                timestamp=b.timestamp,
            )
        )
    return out
