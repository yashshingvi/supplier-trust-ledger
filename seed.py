"""Seed the SQLite DB with demo suppliers and reviews.

Usage:
    python seed.py
"""
from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.ledger import append_event
from app.models import Review, Supplier, TrustScore, LedgerEvent
from app.scoring import compute_score
from app.verification import screen_watchlist, verify_cin, verify_gstin, verify_pan


DEMO_SUPPLIERS = [
    {
        "legal_name": "Aarav Electronics Pvt Ltd",
        "display_name": "Aarav Electronics",
        "pan": "AABCA1234C",
        "gstin": "29AABCA1234C1Z5",
        "cin": "U31900KA2014PTC123456",
        "address": "12 MG Road, Bengaluru",
        "pincode": "560001",
        "category": "Electronics",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 11),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 10),
        "gst_filings_on_time": 12,
        "director_changes_12m": 0,
        "reviews": [
            {"buyer_name": "Razorpay Capital", "rating": 5, "comment": "Reliable, fast invoicing.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Flipkart B2B", "rating": 4, "comment": "Good quality, occasional delays.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Tata 1mg", "rating": 5, "comment": "Consistent partner.", "on_time_delivery": True, "dispute": False},
        ],
    },
    {
        "legal_name": "Bharat Textiles LLP",
        "display_name": "Bharat Textiles",
        "pan": "BBCDE2345D",
        "gstin": "27BBCDE2345D1Z3",
        "cin": "U17110MH2018LLP234567",
        "address": "44 Mill Road, Mumbai",
        "pincode": "400001",
        "category": "Textiles",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 7),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 6),
        "gst_filings_on_time": 11,
        "director_changes_12m": 1,
        "reviews": [
            {"buyer_name": "Myntra Sourcing", "rating": 4, "comment": "Solid bulk capacity.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Reliance Retail", "rating": 3, "comment": "Quality varies by batch.", "on_time_delivery": False, "dispute": False},
        ],
    },
    {
        "legal_name": "Chola Logistics Pvt Ltd",
        "display_name": "Chola Logistics",
        "pan": "CCDEF3456E",
        "gstin": "33CCDEF3456E1Z8",
        "cin": "U63090TN2020PTC345678",
        "address": "78 Anna Salai, Chennai",
        "pincode": "600002",
        "category": "Logistics",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 4),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 4),
        "gst_filings_on_time": 9,
        "director_changes_12m": 0,
        "reviews": [
            {"buyer_name": "Amazon Transport", "rating": 4, "comment": "Reliable for South India routes.", "on_time_delivery": True, "dispute": False},
        ],
    },
    {
        "legal_name": "Delhi Pharma Distributors",
        "display_name": "Delhi Pharma",
        "pan": "DDEFG4567F",
        "gstin": "07DDEFG4567F1Z2",
        "cin": "U51397DL2015PTC456789",
        "address": "9 Nehru Place, New Delhi",
        "pincode": "110019",
        "category": "Pharma",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 9),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 8),
        "gst_filings_on_time": 12,
        "director_changes_12m": 0,
        "reviews": [
            {"buyer_name": "Apollo Hospitals", "rating": 5, "comment": "Always on time, cold chain intact.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "PharmEasy", "rating": 5, "comment": "Excellent compliance docs.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Netmeds", "rating": 4, "comment": "Good but pricier than peers.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Tata 1mg", "rating": 5, "comment": "Top tier.", "on_time_delivery": True, "dispute": False},
        ],
    },
    {
        "legal_name": "Eastern Spices Co",
        "display_name": "Eastern Spices",
        "pan": "EEFGH5678G",
        "gstin": "INVALID-GSTIN",            # will fail GSTIN verify
        "cin": None,
        "address": "5 Park Street, Kolkata",
        "pincode": "700016",
        "category": "FMCG",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 2),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 2),
        "gst_filings_on_time": 6,
        "director_changes_12m": 2,
        "reviews": [
            {"buyer_name": "BigBasket", "rating": 2, "comment": "Two late shipments this quarter.", "on_time_delivery": False, "dispute": True},
            {"buyer_name": "Zepto", "rating": 3, "comment": "Decent product, weak logistics.", "on_time_delivery": False, "dispute": False},
        ],
    },
    {
        "legal_name": "Shady Traders Pvt Ltd",     # watchlist hit
        "display_name": "Shady Traders",
        "pan": "AAAAA0000A",
        "gstin": "29AAAAA0000A1Z9",
        "cin": "U99999KA2023PTC999999",
        "address": "Unknown",
        "pincode": "560001",
        "category": "General Trade",
        "incorporated_on": datetime.utcnow() - timedelta(days=180),
        "gst_registered_on": datetime.utcnow() - timedelta(days=150),
        "gst_filings_on_time": 2,
        "director_changes_12m": 3,
        "reviews": [
            {"buyer_name": "Anonymous Buyer", "rating": 1, "comment": "Did not deliver. Filed dispute.", "on_time_delivery": False, "dispute": True},
        ],
    },
    {
        "legal_name": "Maharashtra Steel Works",
        "display_name": "MH Steel",
        "pan": "MMNOP6789H",
        "gstin": "27MMNOP6789H1Z4",
        "cin": "U27100MH2010PTC678901",
        "address": "Industrial Area, Pune",
        "pincode": "411001",
        "category": "Manufacturing",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 14),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 13),
        "gst_filings_on_time": 12,
        "director_changes_12m": 0,
        "reviews": [
            {"buyer_name": "L&T Construction", "rating": 5, "comment": "Massive scale, never missed.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Tata Projects", "rating": 4, "comment": "Reliable bulk supplier.", "on_time_delivery": True, "dispute": False},
        ],
    },
    {
        "legal_name": "Konkan Coffee Roasters",
        "display_name": "Konkan Coffee",
        "pan": "KKLMN7890I",
        "gstin": "29KKLMN7890I1Z6",
        "cin": "U15490KA2021PTC789012",
        "address": "Coorg Road",
        "pincode": "571201",
        "category": "F&B",
        "incorporated_on": datetime.utcnow() - timedelta(days=365 * 3),
        "gst_registered_on": datetime.utcnow() - timedelta(days=365 * 3),
        "gst_filings_on_time": 11,
        "director_changes_12m": 1,
        "reviews": [
            {"buyer_name": "Blue Tokai", "rating": 4, "comment": "Good single-origin beans.", "on_time_delivery": True, "dispute": False},
            {"buyer_name": "Third Wave Coffee", "rating": 5, "comment": "Excellent partner.", "on_time_delivery": True, "dispute": False},
        ],
    },
]


def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed():
    reset_db()
    db = SessionLocal()
    try:
        # First create all suppliers (so co-location counts are accurate)
        created = []
        for spec in DEMO_SUPPLIERS:
            reviews = spec.pop("reviews", [])
            sup = Supplier(**spec)
            sup.pan_verified = verify_pan(sup.pan)
            sup.gstin_verified = verify_gstin(sup.gstin)
            sup.cin_verified = verify_cin(sup.cin)
            sup.watchlist_hit = screen_watchlist(sup.legal_name, sup.pan)
            sup.status = (
                "frozen" if sup.watchlist_hit
                else "active" if (sup.pan_verified and sup.gstin_verified)
                else "pending"
            )
            db.add(sup)
            db.flush()
            created.append((sup, reviews))

        # Co-location counts
        from collections import Counter
        pincode_counts = Counter(s.pincode for s, _ in created if s.pincode)
        for sup, _ in created:
            if sup.pincode:
                sup.shared_address_count = max(0, pincode_counts[sup.pincode] - 1)

        db.commit()

        # Onboarding + verification ledger events
        for sup, reviews in created:
            append_event(db, sup.id, "supplier_onboarded", {
                "legal_name": sup.legal_name, "pan": sup.pan, "gstin": sup.gstin,
            }, actor="system")
            append_event(db, sup.id, "verification_completed", {
                "pan_verified": sup.pan_verified,
                "gstin_verified": sup.gstin_verified,
                "cin_verified": sup.cin_verified,
                "watchlist_hit": sup.watchlist_hit,
                "shared_address_count": sup.shared_address_count,
            }, actor="system")

            # Reviews
            for r in reviews:
                rev = Review(supplier_id=sup.id, **r)
                db.add(rev)
                db.flush()
                append_event(db, sup.id, "review_added", {
                    "buyer_name": rev.buyer_name,
                    "rating": rev.rating,
                    "dispute": rev.dispute,
                    "on_time_delivery": rev.on_time_delivery,
                }, actor=f"buyer:{rev.buyer_name}")

            db.commit()
            db.refresh(sup)

            # Score
            result = compute_score(sup)
            ts = TrustScore(
                supplier_id=sup.id,
                score=result["score"],
                band=result["band"],
                model_version=result["model_version"],
                factors=result["factors"],
            )
            db.add(ts)
            db.commit()
            append_event(db, sup.id, "score_updated", {
                "score": ts.score, "band": ts.band,
                "model_version": ts.model_version,
                "factor_count": len(result["factors"]),
            }, actor="system")
            print(f"  {sup.display_name:30s}  {ts.score:4d}  {ts.band}")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding Supplier Trust Ledger demo data...")
    seed()
    print("Done. Run: uvicorn app.main:app --reload")
