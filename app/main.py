from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import ledger, scoring, schemas, verification
from .database import Base, engine, get_db
from .models import LedgerEvent, Review, Supplier, TrustScore

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Supplier Trust Ledger (POC)",
    version="0.1.0",
    description="Append-only ledger + explainable trust scoring for B2B suppliers.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run_verification(db: Session, supplier: Supplier) -> dict:
    """Run the stubbed adapters synchronously and update flags + counters."""
    supplier.pan_verified = verification.verify_pan(supplier.pan)
    supplier.gstin_verified = verification.verify_gstin(supplier.gstin)
    supplier.cin_verified = verification.verify_cin(supplier.cin)
    supplier.watchlist_hit = verification.screen_watchlist(
        supplier.legal_name, supplier.pan
    )

    # co-location: count other suppliers at same pincode
    if supplier.pincode:
        same = (
            db.query(func.count(Supplier.id))
            .filter(Supplier.pincode == supplier.pincode, Supplier.id != supplier.id)
            .scalar()
        )
        supplier.shared_address_count = int(same or 0)

    if supplier.pan_verified and supplier.gstin_verified and not supplier.watchlist_hit:
        supplier.status = "active"
    elif supplier.watchlist_hit:
        supplier.status = "frozen"
    else:
        supplier.status = "pending"

    db.commit()
    db.refresh(supplier)

    findings = {
        "pan_verified": supplier.pan_verified,
        "gstin_verified": supplier.gstin_verified,
        "cin_verified": supplier.cin_verified,
        "watchlist_hit": supplier.watchlist_hit,
        "shared_address_count": supplier.shared_address_count,
    }
    ledger.append_event(
        db, supplier.id, "verification_completed", findings, actor="system"
    )
    return findings


def _recompute_score(db: Session, supplier: Supplier) -> TrustScore:
    result = scoring.compute_score(supplier)
    ts = TrustScore(
        supplier_id=supplier.id,
        score=result["score"],
        band=result["band"],
        model_version=result["model_version"],
        factors=result["factors"],
    )
    db.add(ts)
    db.commit()
    db.refresh(ts)
    ledger.append_event(
        db,
        supplier.id,
        "score_updated",
        {
            "score": ts.score,
            "band": ts.band,
            "model_version": ts.model_version,
            "factor_count": len(result["factors"]),
        },
        actor="system",
    )
    return ts


def _latest_score(db: Session, supplier_id: str) -> Optional[TrustScore]:
    return (
        db.query(TrustScore)
        .filter(TrustScore.supplier_id == supplier_id)
        .order_by(TrustScore.computed_at.desc())
        .first()
    )


def _get_supplier_or_404(db: Session, supplier_id: str) -> Supplier:
    sup = db.query(Supplier).filter(Supplier.id == supplier_id).first()
    if not sup:
        raise HTTPException(status_code=404, detail="supplier not found")
    return sup


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------

@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "service": "supplier-trust-ledger", "version": "0.1.0"}


@app.post("/v1/suppliers", response_model=schemas.SupplierOut, status_code=201)
def create_supplier(payload: schemas.SupplierCreate, db: Session = Depends(get_db)):
    supplier = Supplier(
        legal_name=payload.legal_name,
        display_name=payload.display_name or payload.legal_name,
        pan=payload.pan,
        gstin=payload.gstin,
        cin=payload.cin,
        address=payload.address,
        pincode=payload.pincode,
        category=payload.category,
        incorporated_on=payload.incorporated_on,
        gst_registered_on=payload.gst_registered_on,
        gst_filings_on_time=12,
        gst_filings_total=12,
    )
    db.add(supplier)
    db.commit()
    db.refresh(supplier)

    ledger.append_event(
        db,
        supplier.id,
        "supplier_onboarded",
        {
            "legal_name": supplier.legal_name,
            "pan": supplier.pan,
            "gstin": supplier.gstin,
            "cin": supplier.cin,
        },
        actor="system",
    )
    _run_verification(db, supplier)
    _recompute_score(db, supplier)
    return supplier


@app.get("/v1/suppliers", response_model=list[schemas.SupplierOut])
def list_suppliers(
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Supplier)
    if status_filter:
        query = query.filter(Supplier.status == status_filter)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            func.lower(Supplier.legal_name).like(like)
            | func.lower(Supplier.display_name).like(like)
        )
    return query.order_by(Supplier.onboarded_at.desc()).all()


@app.get("/v1/suppliers/with-scores")
def list_suppliers_with_scores(db: Session = Depends(get_db)):
    """Dashboard-friendly: each supplier with its latest score in one round trip."""
    out = []
    for sup in db.query(Supplier).order_by(Supplier.onboarded_at.desc()).all():
        score = _latest_score(db, sup.id)
        out.append({
            "id": sup.id,
            "legal_name": sup.legal_name,
            "display_name": sup.display_name,
            "category": sup.category,
            "pincode": sup.pincode,
            "status": sup.status,
            "watchlist_hit": sup.watchlist_hit,
            "pan_verified": sup.pan_verified,
            "gstin_verified": sup.gstin_verified,
            "cin_verified": sup.cin_verified,
            "review_count": len(sup.reviews),
            "score": score.score if score else None,
            "band": score.band if score else None,
            "computed_at": score.computed_at.isoformat() if score else None,
        })
    return out


@app.get("/v1/suppliers/{supplier_id}", response_model=schemas.SupplierOut)
def get_supplier(supplier_id: str, db: Session = Depends(get_db)):
    return _get_supplier_or_404(db, supplier_id)


@app.post("/v1/suppliers/{supplier_id}/verify")
def reverify(supplier_id: str, db: Session = Depends(get_db)):
    sup = _get_supplier_or_404(db, supplier_id)
    findings = _run_verification(db, sup)
    ts = _recompute_score(db, sup)
    return {"findings": findings, "score": ts.score, "band": ts.band}


# --- reviews ---------------------------------------------------------------

@app.post("/v1/suppliers/{supplier_id}/reviews", response_model=schemas.ReviewOut, status_code=201)
def add_review(supplier_id: str, payload: schemas.ReviewCreate, db: Session = Depends(get_db)):
    sup = _get_supplier_or_404(db, supplier_id)
    review = Review(
        supplier_id=sup.id,
        buyer_name=payload.buyer_name,
        rating=payload.rating,
        comment=payload.comment,
        on_time_delivery=payload.on_time_delivery,
        dispute=payload.dispute,
    )
    db.add(review)
    db.commit()
    db.refresh(review)

    ledger.append_event(
        db,
        sup.id,
        "review_added",
        {
            "buyer_name": review.buyer_name,
            "rating": review.rating,
            "dispute": review.dispute,
            "on_time_delivery": review.on_time_delivery,
        },
        actor=f"buyer:{review.buyer_name}",
    )
    # refresh supplier (to pick up the new review) and recompute
    db.refresh(sup)
    _recompute_score(db, sup)
    return review


@app.get("/v1/suppliers/{supplier_id}/reviews", response_model=list[schemas.ReviewOut])
def list_reviews(supplier_id: str, db: Session = Depends(get_db)):
    _get_supplier_or_404(db, supplier_id)
    return (
        db.query(Review)
        .filter(Review.supplier_id == supplier_id)
        .order_by(Review.created_at.desc())
        .all()
    )


# --- trust score -----------------------------------------------------------

@app.get("/v1/suppliers/{supplier_id}/trust-score", response_model=schemas.TrustScoreOut)
def get_trust_score(supplier_id: str, db: Session = Depends(get_db)):
    _get_supplier_or_404(db, supplier_id)
    score = _latest_score(db, supplier_id)
    if not score:
        raise HTTPException(status_code=404, detail="no score computed yet")
    return score


@app.get("/v1/suppliers/{supplier_id}/trust-score/history", response_model=list[schemas.TrustScoreOut])
def score_history(supplier_id: str, db: Session = Depends(get_db)):
    _get_supplier_or_404(db, supplier_id)
    return (
        db.query(TrustScore)
        .filter(TrustScore.supplier_id == supplier_id)
        .order_by(TrustScore.computed_at.asc())
        .all()
    )


@app.post("/v1/suppliers/{supplier_id}/trust-score/recompute", response_model=schemas.TrustScoreOut)
def recompute_score(supplier_id: str, db: Session = Depends(get_db)):
    sup = _get_supplier_or_404(db, supplier_id)
    return _recompute_score(db, sup)


@app.get("/v1/suppliers/{supplier_id}/trust-score/explanation")
def score_explanation(supplier_id: str, db: Session = Depends(get_db)):
    sup = _get_supplier_or_404(db, supplier_id)
    score = _latest_score(db, supplier_id)
    if not score:
        raise HTTPException(status_code=404, detail="no score computed yet")

    positives = sorted(
        [f for f in score.factors if f["contribution"] > 0],
        key=lambda f: -f["contribution"],
    )[:3]
    negatives = sorted(
        [f for f in score.factors if f["contribution"] < 0],
        key=lambda f: f["contribution"],
    )[:3]

    lines = [f"Trust score: {score.score} ({score.band.title()})"]
    for f in positives:
        lines.append(f"+ {f['detail']} (+{f['contribution']})")
    for f in negatives:
        lines.append(f"- {f['detail']} ({f['contribution']})")

    return {
        "supplier_id": sup.id,
        "score": score.score,
        "band": score.band,
        "model_version": score.model_version,
        "rationale": "\n".join(lines),
        "factors": score.factors,
    }


# --- ledger ----------------------------------------------------------------

@app.get("/v1/suppliers/{supplier_id}/ledger", response_model=list[schemas.LedgerEventOut])
def get_ledger(supplier_id: str, db: Session = Depends(get_db)):
    _get_supplier_or_404(db, supplier_id)
    return (
        db.query(LedgerEvent)
        .filter(LedgerEvent.supplier_id == supplier_id)
        .order_by(LedgerEvent.id.desc())
        .all()
    )


@app.get("/v1/suppliers/{supplier_id}/ledger/verify")
def verify_ledger(supplier_id: str, db: Session = Depends(get_db)):
    _get_supplier_or_404(db, supplier_id)
    return ledger.verify_chain(db, supplier_id)


# ---------------------------------------------------------------------------
# static dashboard
# ---------------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(STATIC_DIR / "index.html")
