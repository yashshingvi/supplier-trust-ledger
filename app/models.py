from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Text, Boolean, JSON
)
from sqlalchemy.orm import relationship
import uuid

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, default=_uuid)
    legal_name = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    pan = Column(String, nullable=True)
    gstin = Column(String, nullable=True)
    cin = Column(String, nullable=True)
    address = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    category = Column(String, nullable=True)        # e.g. "Electronics", "Textiles"
    incorporated_on = Column(DateTime, nullable=True)
    gst_registered_on = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="pending")   # pending|active|frozen
    onboarded_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # verification flags (populated by stub adapters)
    pan_verified = Column(Boolean, default=False)
    gstin_verified = Column(Boolean, default=False)
    cin_verified = Column(Boolean, default=False)
    watchlist_hit = Column(Boolean, default=False)

    # compliance signals
    gst_filings_on_time = Column(Integer, default=0)   # 0..12 (last 12 months)
    gst_filings_total = Column(Integer, default=12)
    director_changes_12m = Column(Integer, default=0)
    shared_address_count = Column(Integer, default=0)  # other suppliers at same pincode

    reviews = relationship(
        "Review", back_populates="supplier", cascade="all, delete-orphan"
    )
    ledger_events = relationship(
        "LedgerEvent", back_populates="supplier", cascade="all, delete-orphan"
    )
    trust_scores = relationship(
        "TrustScore", back_populates="supplier", cascade="all, delete-orphan"
    )


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True, default=_uuid)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    buyer_name = Column(String, nullable=False)
    rating = Column(Integer, nullable=False)         # 1..5
    comment = Column(Text, nullable=True)
    on_time_delivery = Column(Boolean, default=True)
    dispute = Column(Boolean, default=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    supplier = relationship("Supplier", back_populates="reviews")


class LedgerEvent(Base):
    """Append-only, hash-chained event log per supplier."""
    __tablename__ = "ledger_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    event_type = Column(String, nullable=False)
    actor = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    payload = Column(JSON, nullable=False)
    prev_hash = Column(String, nullable=True)
    payload_hash = Column(String, nullable=False)
    chain_hash = Column(String, nullable=False)

    supplier = relationship("Supplier", back_populates="ledger_events")


class TrustScore(Base):
    __tablename__ = "trust_scores"

    id = Column(String, primary_key=True, default=_uuid)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    score = Column(Integer, nullable=False)
    band = Column(String, nullable=False)
    model_version = Column(String, nullable=False, default="rules-v1")
    computed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    factors = Column(JSON, nullable=False)   # list of {name, contribution, detail}

    supplier = relationship("Supplier", back_populates="trust_scores")
