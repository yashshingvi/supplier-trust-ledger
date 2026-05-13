"""Explainable, deterministic trust scoring (rules-v1).

Maps a supplier's signals to a 0..1000 score with per-factor contributions.
A real build would replace this with XGBoost + SHAP (see PLAN.md §6), but the
output shape (`factors: [{name, contribution, detail}]`) is identical so the
UI and ledger contract don't change.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import Supplier

MODEL_VERSION = "rules-v1"

BASELINE = 500  # neutral starting point, 0..1000 scale


def _band(score: int) -> str:
    if score >= 800:
        return "excellent"
    if score >= 650:
        return "high"
    if score >= 450:
        return "medium"
    return "low"


def _years_since(d: datetime | None) -> float:
    if d is None:
        return 0.0
    return max(0.0, (datetime.utcnow() - d).days / 365.25)


def compute_score(supplier: Supplier) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []

    # --- Identity verification (authoritative sources) ---
    id_contrib = 0
    id_bits = []
    if supplier.pan_verified:
        id_contrib += 40
        id_bits.append("PAN")
    if supplier.gstin_verified:
        id_contrib += 60
        id_bits.append("GSTIN")
    if supplier.cin_verified:
        id_contrib += 40
        id_bits.append("CIN")
    factors.append({
        "name": "Identity verification",
        "contribution": id_contrib,
        "detail": (
            f"Verified against authoritative sources: {', '.join(id_bits)}"
            if id_bits else "No authoritative identifier verified"
        ),
    })

    # --- Vintage ---
    yrs = _years_since(supplier.incorporated_on)
    if yrs >= 10:
        vintage = 80
    elif yrs >= 5:
        vintage = 55
    elif yrs >= 2:
        vintage = 30
    elif yrs >= 1:
        vintage = 10
    else:
        vintage = -10
    factors.append({
        "name": "Business vintage",
        "contribution": vintage,
        "detail": f"Incorporated {yrs:.1f} years ago",
    })

    # --- GST compliance ---
    total = supplier.gst_filings_total or 12
    on_time = supplier.gst_filings_on_time or 0
    ratio = on_time / total if total else 0
    if ratio >= 0.95:
        comp = 90
    elif ratio >= 0.8:
        comp = 50
    elif ratio >= 0.5:
        comp = 0
    else:
        comp = -80
    factors.append({
        "name": "GST filing compliance",
        "contribution": comp,
        "detail": f"GSTR-3B filed on time {on_time}/{total} months",
    })

    # --- Watchlist hit ---
    if supplier.watchlist_hit:
        factors.append({
            "name": "Watchlist screening",
            "contribution": -250,
            "detail": "Match found on a sanctions / defaulters list",
        })
    else:
        factors.append({
            "name": "Watchlist screening",
            "contribution": 30,
            "detail": "Clear on OFAC / RBI defaulters / MHA lists",
        })

    # --- Network / co-location risk ---
    sa = supplier.shared_address_count or 0
    if sa >= 20:
        net = -60
    elif sa >= 10:
        net = -30
    elif sa >= 3:
        net = -10
    else:
        net = 15
    factors.append({
        "name": "Address co-location",
        "contribution": net,
        "detail": f"{sa} other suppliers share this pincode",
    })

    # --- Stability (director changes) ---
    dc = supplier.director_changes_12m or 0
    if dc == 0:
        stab = 25
    elif dc == 1:
        stab = 0
    elif dc == 2:
        stab = -25
    else:
        stab = -60
    factors.append({
        "name": "Director stability",
        "contribution": stab,
        "detail": f"{dc} director change(s) in the last 12 months",
    })

    # --- Reviews / buyer behavior ---
    reviews = list(supplier.reviews or [])
    if reviews:
        avg = sum(r.rating for r in reviews) / len(reviews)
        disputes = sum(1 for r in reviews if r.dispute)
        late = sum(1 for r in reviews if not r.on_time_delivery)
        # rating: each star above 3.0 adds 25, each below subtracts 30
        rating_contrib = int(round((avg - 3.0) * 25)) if avg >= 3 else int(round((avg - 3.0) * 30))
        # disputes / late deliveries
        rating_contrib -= disputes * 25
        rating_contrib -= late * 8
        factors.append({
            "name": "Buyer reviews",
            "contribution": rating_contrib,
            "detail": (
                f"{len(reviews)} review(s), avg {avg:.1f}/5"
                + (f", {disputes} dispute(s)" if disputes else "")
                + (f", {late} late delivery(s)" if late else "")
            ),
        })
    else:
        factors.append({
            "name": "Buyer reviews",
            "contribution": -15,
            "detail": "No buyer reviews yet (cold start penalty)",
        })

    total_contrib = sum(f["contribution"] for f in factors)
    raw = BASELINE + total_contrib
    score = max(0, min(1000, raw))

    return {
        "score": int(score),
        "band": _band(score),
        "model_version": MODEL_VERSION,
        "factors": factors,
        "baseline": BASELINE,
        "raw_total": raw,
    }
