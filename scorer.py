"""Trust score computation for the Supplier Trust Ledger POC.

Produces a deterministic, explainable 0..1000 score from a supplier's
tabular attributes plus their buyer reviews. No ML libraries — a transparent
weighted-sum so every contribution can be shown to the user.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


BAND_THRESHOLDS = [
    (850, "Excellent"),
    (700, "High"),
    (500, "Medium"),
    (0, "Low"),
]


@dataclass
class Factor:
    key: str
    label: str
    contribution: int
    detail: str


def _years_since(iso_date: str | None) -> float:
    if not iso_date:
        return 0.0
    try:
        d = datetime.fromisoformat(iso_date.replace("Z", ""))
    except ValueError:
        return 0.0
    return max(0.0, (datetime.utcnow() - d).days / 365.25)


def _band(score: int) -> str:
    for threshold, name in BAND_THRESHOLDS:
        if score >= threshold:
            return name
    return "Low"


def compute_score(supplier: dict, reviews: Iterable[dict]) -> dict:
    """Return {score, band, factors:[{key,label,contribution,detail}]}.

    Anchored at 500. Each factor adds or subtracts from that baseline.
    Final score clamped to [0, 1000].
    """
    reviews = list(reviews)
    factors: list[Factor] = []

    identity_points = 0
    identity_detail_parts = []
    if supplier.get("pan_verified"):
        identity_points += 40
        identity_detail_parts.append("PAN verified")
    if supplier.get("gstin_verified"):
        identity_points += 50
        identity_detail_parts.append("GSTIN verified")
    if supplier.get("cin_verified"):
        identity_points += 30
        identity_detail_parts.append("CIN verified")
    factors.append(Factor(
        key="identity",
        label="Identity verification",
        contribution=identity_points,
        detail=", ".join(identity_detail_parts) or "no identifiers verified",
    ))

    years = _years_since(supplier.get("incorporated_on"))
    if years >= 10:
        vintage_points = 80
    elif years >= 5:
        vintage_points = 50
    elif years >= 2:
        vintage_points = 25
    elif years >= 1:
        vintage_points = 10
    else:
        vintage_points = -20
    factors.append(Factor(
        key="vintage",
        label="Business vintage",
        contribution=vintage_points,
        detail=f"{years:.1f} years since incorporation",
    ))

    on_time = int(supplier.get("gst_filings_on_time", 0))
    on_time = max(0, min(12, on_time))
    compliance_points = (on_time - 6) * 12
    factors.append(Factor(
        key="gst_filings",
        label="GST filing discipline",
        contribution=compliance_points,
        detail=f"{on_time}/12 monthly returns filed on time",
    ))

    changes = int(supplier.get("director_changes_12m", 0))
    if changes == 0:
        stability_points = 30
        stability_detail = "stable director set"
    elif changes == 1:
        stability_points = 0
        stability_detail = "1 director change in 12m"
    else:
        stability_points = -25 * changes
        stability_detail = f"{changes} director changes in 12m"
    factors.append(Factor(
        key="director_stability",
        label="Director stability",
        contribution=stability_points,
        detail=stability_detail,
    ))

    if supplier.get("watchlist_hit"):
        factors.append(Factor(
            key="watchlist",
            label="Watchlist screening",
            contribution=-300,
            detail="appears on a sanctions or defaulter list",
        ))
    else:
        factors.append(Factor(
            key="watchlist",
            label="Watchlist screening",
            contribution=40,
            detail="clean across screened watchlists",
        ))

    if reviews:
        avg_rating = sum(r.get("rating", 0) for r in reviews) / len(reviews)
        review_points = int(round((avg_rating - 3.0) * 60))
        factors.append(Factor(
            key="reviews",
            label="Buyer review rating",
            contribution=review_points,
            detail=f"avg {avg_rating:.2f} across {len(reviews)} review(s)",
        ))

        on_time_rate = sum(1 for r in reviews if r.get("on_time_delivery")) / len(reviews)
        delivery_points = int(round((on_time_rate - 0.7) * 120))
        factors.append(Factor(
            key="delivery",
            label="On-time delivery",
            contribution=delivery_points,
            detail=f"{on_time_rate * 100:.0f}% on-time across buyers",
        ))

        disputes = sum(1 for r in reviews if r.get("dispute"))
        dispute_points = -40 * disputes
        factors.append(Factor(
            key="disputes",
            label="Dispute history",
            contribution=dispute_points,
            detail=f"{disputes} disputed engagement(s)" if disputes else "no disputes",
        ))
    else:
        factors.append(Factor(
            key="reviews",
            label="Buyer review rating",
            contribution=-30,
            detail="no buyer reviews yet",
        ))

    raw = 500 + sum(f.contribution for f in factors)
    score = max(0, min(1000, raw))

    return {
        "score": score,
        "band": _band(score),
        "factors": [f.__dict__ for f in factors],
    }
