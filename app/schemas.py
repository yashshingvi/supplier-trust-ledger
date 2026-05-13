from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class SupplierCreate(BaseModel):
    legal_name: str
    display_name: Optional[str] = None
    pan: Optional[str] = None
    gstin: Optional[str] = None
    cin: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    category: Optional[str] = None
    incorporated_on: Optional[datetime] = None
    gst_registered_on: Optional[datetime] = None


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    legal_name: str
    display_name: str
    pan: Optional[str]
    gstin: Optional[str]
    cin: Optional[str]
    address: Optional[str]
    pincode: Optional[str]
    category: Optional[str]
    incorporated_on: Optional[datetime]
    gst_registered_on: Optional[datetime]
    status: str
    onboarded_at: datetime
    pan_verified: bool
    gstin_verified: bool
    cin_verified: bool
    watchlist_hit: bool
    gst_filings_on_time: int
    gst_filings_total: int
    director_changes_12m: int
    shared_address_count: int


class ReviewCreate(BaseModel):
    buyer_name: str = Field(min_length=1, max_length=120)
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    on_time_delivery: bool = True
    dispute: bool = False


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supplier_id: str
    buyer_name: str
    rating: int
    comment: Optional[str]
    on_time_delivery: bool
    dispute: bool
    created_at: datetime


class TrustScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supplier_id: str
    score: int
    band: str
    model_version: str
    computed_at: datetime
    factors: list[dict[str, Any]]


class LedgerEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    supplier_id: str
    event_type: str
    actor: str
    occurred_at: datetime
    payload: dict[str, Any]
    prev_hash: Optional[str]
    payload_hash: str
    chain_hash: str
