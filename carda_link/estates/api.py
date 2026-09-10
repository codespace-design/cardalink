from decimal import Decimal
from typing import List
from typing import Optional

from django.shortcuts import get_object_or_404
from ninja import Field
from ninja import Router
from ninja import Schema

from .models import Estate
from .models import EstatePhoto
from .models import HarvestBatch

router = Router(tags=["Estates & Farm Management"])


class EstatePhotoSchema(Schema):
    id: int
    image_url: str = Field(..., alias="image")
    caption: str
    uploaded_at: str

    @staticmethod
    def resolve_image_url(obj):
        return obj.image.url if obj.image else ""

    @staticmethod
    def resolve_uploaded_at(obj):
        return obj.uploaded_at.isoformat() if obj.uploaded_at else ""


class HarvestBatchSchema(Schema):
    id: int
    harvest_date: str
    weight_kg: Decimal
    grade: str
    grade_display: str
    quality_certificate_url: Optional[str] = None
    created_at: str

    @staticmethod
    def resolve_harvest_date(obj):
        return str(obj.harvest_date)

    @staticmethod
    def resolve_grade_display(obj):
        return obj.get_grade_display()

    @staticmethod
    def resolve_quality_certificate_url(obj):
        return obj.quality_certificate.url if obj.quality_certificate else None

    @staticmethod
    def resolve_created_at(obj):
        return obj.created_at.isoformat() if obj.created_at else ""


class HarvestBatchCreateSchema(Schema):
    harvest_date: str
    weight_kg: Decimal
    grade: Optional[str] = "UNGRADED"


class EstateDetailSchema(Schema):
    id: int
    name: str
    owner_name: str
    phone_number: str
    address: str
    location: str
    area_in_acres: Decimal
    description: str
    primary_photo_url: Optional[str] = None
    created_at: str
    total_harvest_kg: Decimal
    photos: List[EstatePhotoSchema] = []
    harvest_batches: List[HarvestBatchSchema] = []

    @staticmethod
    def resolve_primary_photo_url(obj):
        return obj.primary_photo.url if obj.primary_photo else None

    @staticmethod
    def resolve_created_at(obj):
        return obj.created_at.isoformat() if obj.created_at else ""

    @staticmethod
    def resolve_total_harvest_kg(obj):
        return obj.total_harvest_kg

    @staticmethod
    def resolve_photos(obj):
        return list(obj.photos.all())

    @staticmethod
    def resolve_harvest_batches(obj):
        return list(obj.harvest_batches.all())


class EstateCreateSchema(Schema):
    name: str
    owner_name: Optional[str] = ""
    phone_number: str
    address: str
    location: Optional[str] = "Idukki, Kerala"
    area_in_acres: Decimal
    description: Optional[str] = ""


class EstateUpdateSchema(Schema):
    name: Optional[str] = None
    owner_name: Optional[str] = None
    phone_number: Optional[str] = None
    address: Optional[str] = None
    location: Optional[str] = None
    area_in_acres: Optional[Decimal] = None
    description: Optional[str] = None


@router.get("/health-check")
def estates_health_check(request):
    return {"status": "ok", "module": "Estates & Farm Intelligence"}


@router.get("/", response=List[EstateDetailSchema])
def list_estates(request):
    """List all registered estates with photo galleries and harvest lots."""
    return Estate.objects.select_related("owner").prefetch_related("photos", "harvest_batches").all()


@router.get("/{estate_id}", response=EstateDetailSchema)
def get_estate(request, estate_id: int):
    """Get single estate profile, gallery, and harvest lots."""
    return get_object_or_404(
        Estate.objects.select_related("owner").prefetch_related("photos", "harvest_batches"),
        id=estate_id,
    )


@router.post("/", response={201: EstateDetailSchema})
def create_estate(request, payload: EstateCreateSchema):
    """Register a new cardamom estate."""
    user = request.user if request.user.is_authenticated else None
    if not user:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.first()
    owner_name = payload.owner_name or (user.name if user and getattr(user, "name", None) else "Estate Owner")

    estate = Estate.objects.create(
        owner=user,
        name=payload.name,
        owner_name=owner_name,
        phone_number=payload.phone_number,
        address=payload.address,
        location=payload.location or "Idukki, Kerala",
        area_in_acres=payload.area_in_acres,
        description=payload.description or "",
    )
    return 201, estate


@router.put("/{estate_id}", response=EstateDetailSchema)
def update_estate(request, estate_id: int, payload: EstateUpdateSchema):
    """Update estate information."""
    estate = get_object_or_404(Estate, id=estate_id)
    for field, value in payload.dict(exclude_unset=True).items():
        if value is not None:
            setattr(estate, field, value)
    estate.save()
    return estate


@router.delete("/{estate_id}")
def delete_estate(request, estate_id: int):
    """Delete an estate."""
    estate = get_object_or_404(Estate, id=estate_id)
    estate.delete()
    return {"success": True, "message": f"Estate #{estate_id} deleted."}


@router.get("/{estate_id}/batches", response=List[HarvestBatchSchema])
def list_harvest_batches(request, estate_id: int):
    """List all harvest batches logged for a specific estate."""
    estate = get_object_or_404(Estate, id=estate_id)
    return estate.harvest_batches.all()


@router.post("/{estate_id}/batches", response={201: HarvestBatchSchema})
def create_harvest_batch(request, estate_id: int, payload: HarvestBatchCreateSchema):
    """Log a new harvest batch for an estate."""
    estate = get_object_or_404(Estate, id=estate_id)
    batch = HarvestBatch.objects.create(
        estate=estate,
        harvest_date=payload.harvest_date,
        weight_kg=payload.weight_kg,
        grade=payload.grade or "UNGRADED",
    )
    return 201, batch


@router.delete("/batches/{batch_id}")
def delete_harvest_batch(request, batch_id: int):
    """Delete a harvest batch."""
    batch = get_object_or_404(HarvestBatch, id=batch_id)
    batch.delete()
    return {"success": True, "message": f"Harvest batch #{batch_id} deleted."}
