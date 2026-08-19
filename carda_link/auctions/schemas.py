from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class AuctionCreateSchema(BaseModel):
    title: str = Field(..., description="Auction Event Title")
    start_time: datetime = Field(..., description="Bidding Start Time")
    end_time: datetime = Field(..., description="Bidding End Time")
    status: str = Field(default="UPCOMING", description="UPCOMING | ACTIVE | COMPLETED | CANCELLED")


class AuctionUpdateSchema(BaseModel):
    title: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: Optional[str] = None


class LotCreateSchema(BaseModel):
    harvest_batch_id: int = Field(..., description="ID of linked HarvestBatch")
    lot_number: int = Field(..., description="Serial Lot number in auction")
    base_price_per_kg: Decimal = Field(..., description="Base starting price per kg in ₹")


class BidCreateSchema(BaseModel):
    amount_per_kg: Decimal = Field(..., description="Bid amount per kg in ₹")


class BidOutSchema(BaseModel):
    id: int
    lot_id: int
    bidder_id: int
    bidder_email: str
    bidder_name: str
    amount_per_kg: Decimal
    timestamp: datetime


class LotOutSchema(BaseModel):
    id: int
    auction_id: int
    harvest_batch_id: int
    estate_name: str
    grade: str
    weight_kg: Decimal
    lot_number: int
    base_price_per_kg: Decimal
    highest_bid_per_kg: Optional[Decimal] = None
    current_price: Decimal
    is_sold: bool

    @staticmethod
    def from_orm_model(lot):
        estate_name = lot.harvest_batch.estate.name if lot.harvest_batch and lot.harvest_batch.estate else "Unknown Estate"
        grade = lot.harvest_batch.grade if lot.harvest_batch else "UNGRADED"
        weight_kg = lot.harvest_batch.weight_kg if lot.harvest_batch else Decimal("0.00")
        return LotOutSchema(
            id=lot.id,
            auction_id=lot.auction_id,
            harvest_batch_id=lot.harvest_batch_id,
            estate_name=estate_name,
            grade=grade,
            weight_kg=weight_kg,
            lot_number=lot.lot_number,
            base_price_per_kg=lot.base_price_per_kg,
            highest_bid_per_kg=lot.highest_bid_per_kg,
            current_price=lot.current_price,
            is_sold=lot.is_sold,
        )


class AuctionOutSchema(BaseModel):
    id: int
    title: str
    start_time: datetime
    end_time: datetime
    status: str
    status_display: str
    is_active_now: bool
    created_at: datetime
    lot_count: int


class AuctionDetailOutSchema(AuctionOutSchema):
    lots: list[LotOutSchema]


class MessageResponseSchema(BaseModel):
    message: str
    success: bool = True
