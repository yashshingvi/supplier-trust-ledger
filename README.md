# Supplier Trust Ledger (STL) — POC

An append-only, AI-augmented ledger for verifying B2B suppliers and producing explainable trust scores. Built from the [Razorpay Fix My Itch](https://razorpay.com/m/fix-my-itch/) problem: *"Why can't businesses verify new suppliers before purchasing?"*

See [PLAN.md](./PLAN.md) for the full product/architecture rationale (640 lines — architecture diagrams, DB schemas, ML approach, risk matrix, and 6-phase roadmap).

## Stack (POC scope)

- **FastAPI + Uvicorn** — REST API with OpenAPI auto-docs.
- **SQLAlchemy + SQLite** — relational storage with hash-chained ledger events.
- **Single-file HTML/JS dashboard** — served from FastAPI at `/`.
- **scorer.py** — deterministic, explainable 0–1000 trust scoring (no ML dep needed for POC).

## Files

```
supplier-trust-ledger/
├── app/
│   ├── main.py         # FastAPI app, routes, CORS, static mount
│   ├── models.py       # SQLAlchemy models (Supplier, Review, TrustScore, LedgerEvent)
│   ├── database.py     # SQLite engine + session factory
│   ├── schemas.py      # Pydantic request/response models
│   ├── scoring.py      # Score computation + SHAP-style explanation builder
│   ├── verification.py # Verification adapters (PAN, GSTIN, CIN, watchlists)
│   └── ledger.py       # Append-only event recording with hash chaining
├── static/
│   ├── index.html      # Dashboard UI (cards, search, filter, detail drawer)
│   ├── app.js          # Vanilla JS frontend logic
│   └── style.css       # Dashboard styles
├── scorer.py           # CLI: score a supplier JSON
├── seed.py             # Populate DB with 15 demo suppliers + reviews
├── PLAN.md             # Full architecture & implementation plan
├── requirements.txt
├── .gitignore
└── README.md
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Seed the database with demo suppliers
python seed.py

# 3. Run the server
uvicorn app.main:app --reload

# 4. Open the dashboard
#    http://localhost:8000
```

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/` | Dashboard HTML |
| `GET`  | `/api/suppliers` | List suppliers (search by `?q=`, filter by `?band=`) |
| `GET`  | `/api/suppliers/{id}` | Supplier detail + trust score + factors |
| `POST` | `/api/suppliers` | Onboard a new supplier |
| `GET`  | `/api/suppliers/{id}/ledger` | Immutable event history |
| `GET`  | `/api/suppliers/{id}/ledger/verify` | Hash-chain integrity check |
| `POST` | `/api/suppliers/{id}/reviews` | Submit a buyer review |
| `GET`  | `/api/dashboard` | Aggregate stats (count by band, avg score, total suppliers) |

OpenAPI docs live at `/docs` once the server is running.

## How Trust Scoring Works

The score ranges from **0–1000**, anchored at 500. Each factor adds or subtracts from the baseline:

| Factor | Range | Detail |
|--------|-------|--------|
| Identity verification | −0 to +120 | PAN, GSTIN, CIN verified against authoritative sources |
| Business vintage | −20 to +80 | Years since incorporation |
| GST filing discipline | −72 to +72 | On-time monthly return filings (last 12 months) |
| Director stability | −∞ to +30 | Director changes in the last 12 months |
| Watchlist screening | −300 to +40 | Sanctions, defaulter lists, adverse media |
| Buyer reviews | −30 to +120 | Average rating, on-time delivery rate, dispute count |

**Bands:** Excellent (850+) · High (700–849) · Medium (500–699) · Low (<500)

Every score includes per-factor attribution — the dashboard shows exactly what contributed positively and negatively. See `scorer.py` for the full algorithm.

## Limitations (POC scope)

- Single-tenant — no auth or RLS.
- SQLite instead of Postgres (swap by changing `database.py`).
- No async verifications — scoring is synchronous.
- Watchlist screening uses a local stub; production would integrate real APIs (GSTN, MCA, OFAC, etc.).

These are deliberate cuts; the production path is detailed in `PLAN.md`.
