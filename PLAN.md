# Supplier Trust Ledger — POC Plan

> An append-only, AI-augmented ledger for verifying B2B suppliers and producing
> explainable trust scores. POC scoped for a 10–12 week build by 1–2 engineers.

---

## 1. Problem & Landscape

### 1.1 Problem statement
Buyers (procurement, payments, lending, marketplaces) repeatedly re-verify the
same suppliers, each in their own silo, with inconsistent evidence and no
shared audit trail. There is no single, tamper-evident record of *what was
verified*, *when*, *by whom*, and *what changed*. The result: duplicated KYB
spend, slow onboarding (often 5–15 days), and weak signal sharing across
buyers in the same network.

The Supplier Trust Ledger (STL) is a system of record that:
1. **Verifies** supplier identity and key attributes against authoritative
   sources (MCA, GSTN, EPFO, sanctions lists, bureaus).
2. **Records** every verification, document, dispute, and transaction event
   as an immutable, hash-chained ledger entry.
3. **Scores** trust on a 0–1000 scale using an explainable ML model.
4. **Shares** signals across consenting buyers (with the supplier's consent).

### 1.2 Competitive landscape — what to learn from
| Player | What's good | What's missing |
|---|---|---|
| Dun & Bradstreet (D-U-N-S) | Global ID, bureau depth | Closed; slow to update; expensive |
| SAP Ariba / Coupa SRM | Embedded in procure-to-pay | Tied to ERP; weak on Indian SMB data |
| EcoVadis | ESG/sustainability scoring | Single dimension; survey-driven |
| Refinitiv World-Check | Sanctions/PEP/adverse media | No financial/operational signal |
| CreditSafe / CRIF / Experian | Credit/financial risk | No fraud-graph or doc verification |
| Khatabook, OkCredit, Vyapar | India SMB-native | Limited authoritative-source integration |
| Persona / Trulioo / Onfido | KYB doc verification | Stateless; no longitudinal ledger |
| HyperVerge / Signzy / Karza / IDfy | Indian KYB APIs | Per-call utilities, not a system of record |

**STL's differentiated wedge**: *append-only ledger* + *explainable score* +
*supplier-consented sharing* + *Indian-first* (GSTN, MCA21, Udyam, EPFO).

### 1.3 Primary signals for trust
- **Identity**: PAN, GSTIN, CIN/LLPIN, Udyam, DIN of directors
- **Legal status**: Active/struck-off (MCA), GST registration status, charges
- **Financial**: GSTR-1/3B turnover, ITR (if shared), bank statements, bureau
- **Compliance**: GST default history, EPFO/ESIC compliance, litigation
- **Watchlists**: OFAC, UN, EU, MHA, RBI defaulters/wilful defaulters, PEP
- **Reputation**: Adverse media, customer disputes, chargebacks
- **Network**: Counterparty graph (who pays whom), shared directors/addresses
- **Behavioral**: On-platform tenure, response time, dispute rate, payment SLA
- **Document authenticity**: Hash, signer cert (DigiLocker / e-Sign), tamper checks

---

## 2. Architecture

### 2.1 Logical view

```
                    ┌──────────────────────────────────────────────┐
                    │  Web App (Next.js)  •  CLI  •  Buyer APIs    │
                    └────────────────────────┬─────────────────────┘
                                             │  HTTPS / JWT
                    ┌────────────────────────▼─────────────────────┐
                    │      FastAPI Gateway (auth, rate limit)      │
                    └─┬───────┬──────────────┬──────────────┬──────┘
                      │       │              │              │
              ┌───────▼──┐ ┌──▼─────────┐ ┌──▼─────────┐ ┌──▼────────┐
              │ Supplier │ │Verification│ │  Scoring   │ │  Ledger   │
              │ Service  │ │  Service   │ │  Service   │ │  Service  │
              └───┬──────┘ └──┬─────────┘ └──┬─────────┘ └─┬─────────┘
                  │           │              │             │
                  │       ┌───▼─────────┐    │             │
                  │       │ Source      │    │             │
                  │       │ Adapters    │◄───┼─ retry q ───┤
                  │       │ (GSTN, MCA, │    │             │
                  │       │  Watchlists)│    │             │
                  │       └───┬─────────┘    │             │
                  │           │              │             │
                  │       ┌───▼─────────┐ ┌──▼─────────┐   │
                  │       │ Doc Parser  │ │ Trust      │   │
                  │       │ (Claude +   │ │ Model      │   │
                  │       │  OCR)       │ │ (XGBoost)  │   │
                  │       └───┬─────────┘ └──┬─────────┘   │
                  │           │              │             │
              ┌───▼───────────▼──────────────▼─────────────▼─────┐
              │           Event Bus (Redis Streams)              │
              └───┬──────────┬────────────────────┬──────────────┘
                  │          │                    │
            ┌─────▼────┐ ┌───▼──────────┐ ┌──────▼──────────┐
            │ Postgres │ │ Object Store │ │  Vector Store   │
            │ +pgvector│ │  (S3/MinIO)  │ │  (pgvector)     │
            │ +ledger  │ │  documents   │ │  doc & adverse  │
            │ tables   │ │              │ │  media embeds   │
            └──────────┘ └──────────────┘ └─────────────────┘
```

### 2.2 Key design decisions

| Decision | Choice | Why |
|---|---|---|
| Sync vs. async verification | Async, event-driven | Source APIs are slow/flaky; ledger needs durable retries |
| Ledger storage | Append-only Postgres table + SHA-256 hash chain | Tamper-evident without blockchain overhead; auditable |
| Service decomposition | Modular monolith for POC, service-ready boundaries | Faster to build; split later when scaling forces it |
| Auth | JWT (short-lived) + refresh tokens; OIDC-ready | Standard; pluggable for SSO later |
| Multi-tenancy | Row-level via `tenant_id` + RLS policies | One DB, isolated per buyer |
| LLM use | Claude (Sonnet 4.6 default; Haiku for bulk OCR cleanup) | Strong doc reasoning, structured outputs |

### 2.3 Append-only ledger semantics
Every state change is a `ledger_event` row. Rows are never updated or deleted.
Each row stores:
- `prev_hash` — SHA-256 of the previous event for this supplier
- `payload_hash` — SHA-256 of the canonicalized JSON payload
- `chain_hash` — `sha256(prev_hash || payload_hash || timestamp)`

A `chain_hash` mismatch on read = tamper detected. Optional daily Merkle root
published to a public location (S3 + signed) for external auditability.

---

## 3. Tech Stack

### 3.1 Recommended stack (POC)

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Best ML ecosystem; team familiarity |
| API framework | **FastAPI** | Async, OpenAPI out of box, Pydantic v2 typing |
| ORM | SQLAlchemy 2.0 + Alembic | Mature; async support; battle-tested migrations |
| DB | PostgreSQL 16 + `pgvector` | Relational + vector in one engine for POC |
| Cache / queue | Redis 7 (Streams + RQ) | Single dep for cache, pubsub, and task queue |
| Object store | MinIO (local) / S3 (prod) | Documents, model artifacts |
| ML — tabular | XGBoost + scikit-learn + SHAP | SOTA on tabular; SHAP gives per-feature attribution |
| ML — embeddings | `bge-small-en-v1.5` (open) | Cheap, good for adverse media search |
| LLM | Anthropic Claude (Sonnet 4.6, Haiku 4.5) | Structured outputs, doc parsing |
| OCR | Tesseract for typed; PaddleOCR for stamps/seals | Cost-effective; ship to Claude for normalization |
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui | Fast iteration; good defaults |
| Charts | Recharts | Sufficient for trust score viz |
| Auth | `fastapi-users` + JWT | Quick to ship; OIDC-extensible |
| Observability | OpenTelemetry → Grafana Tempo + Loki + Prometheus | Single stack; works locally via docker-compose |
| Error tracking | Sentry | Standard |
| Deploy | docker-compose (dev), Fly.io or Railway (demo) | Cheap, fast |
| CI | GitHub Actions | Lint, test, container build, alembic check |

### 3.2 Things explicitly *not* in the POC
- Kubernetes / service mesh
- Blockchain / DLT (we use a hash chain, not a chain)
- Real-time streaming analytics (use batch + cron)
- Mobile apps
- Buyer-side webhook fan-out (manual pull for POC)

---

## 4. Database Design

PostgreSQL is the source of truth. Schema is grouped by bounded context.

### 4.1 Entity overview

```
suppliers ──┬── supplier_identifiers
            ├── supplier_addresses
            ├── supplier_directors
            ├── supplier_documents ── document_extractions
            ├── verification_runs ── verification_findings
            ├── trust_scores ── score_factors (with SHAP values)
            ├── ledger_events  (append-only, hash-chained)
            ├── relationships  (counterparty graph edges)
            └── consents       (data-sharing grants)

tenants ── users ── api_keys
```

### 4.2 Core tables (DDL sketch)

```sql
-- Tenant & user (multi-tenant, RLS-protected)
CREATE TABLE tenants (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A supplier is unique per tenant (a buyer's view). Cross-tenant linkage
-- happens via `global_supplier_id` (the "DUNS-equivalent").
CREATE TABLE global_suppliers (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name    TEXT NOT NULL,
  country_code  CHAR(2) NOT NULL DEFAULT 'IN',
  pan           CHAR(10),
  cin           VARCHAR(21),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (country_code, pan)
);

CREATE TABLE suppliers (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           UUID NOT NULL REFERENCES tenants(id),
  global_supplier_id  UUID REFERENCES global_suppliers(id),
  display_name        TEXT NOT NULL,
  status              TEXT NOT NULL DEFAULT 'pending',  -- pending|active|frozen|rejected
  onboarded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX ON suppliers (tenant_id, status);

CREATE TABLE supplier_identifiers (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id  UUID NOT NULL REFERENCES suppliers(id) ON DELETE CASCADE,
  kind         TEXT NOT NULL,    -- gstin|pan|cin|udyam|iec|tan|llpin|din
  value        TEXT NOT NULL,
  verified_at  TIMESTAMPTZ,
  source       TEXT,             -- gstn|mca|udyam|self_declared
  UNIQUE (supplier_id, kind, value)
);

-- Hash-chained, append-only audit log per supplier
CREATE TABLE ledger_events (
  id              BIGSERIAL PRIMARY KEY,
  supplier_id     UUID NOT NULL REFERENCES suppliers(id),
  event_type      TEXT NOT NULL,   -- onboarded|doc_uploaded|verified|score_updated|...
  actor           TEXT NOT NULL,   -- user:<id> | system | adapter:<name>
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload         JSONB NOT NULL,
  prev_hash       BYTEA,
  payload_hash    BYTEA NOT NULL,
  chain_hash      BYTEA NOT NULL,
  UNIQUE (supplier_id, id)
);
CREATE INDEX ON ledger_events (supplier_id, occurred_at DESC);
-- Enforce immutability at the DB layer
CREATE RULE ledger_no_update AS ON UPDATE TO ledger_events DO INSTEAD NOTHING;
CREATE RULE ledger_no_delete AS ON DELETE TO ledger_events DO INSTEAD NOTHING;

CREATE TABLE supplier_documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id   UUID NOT NULL REFERENCES suppliers(id),
  kind          TEXT NOT NULL,   -- gst_cert|pan_card|coi|bank_stmt|gstr3b|...
  s3_uri        TEXT NOT NULL,
  sha256        BYTEA NOT NULL,
  uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  uploaded_by   UUID,
  extracted     JSONB             -- LLM-extracted structured fields
);

CREATE TABLE verification_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id   UUID NOT NULL REFERENCES suppliers(id),
  adapter       TEXT NOT NULL,   -- gstn|mca|epfo|watchlist|bureau
  status        TEXT NOT NULL,   -- queued|running|ok|failed
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at   TIMESTAMPTZ,
  response_raw  JSONB,
  findings      JSONB            -- normalized {field, claim, observed, match}
);

CREATE TABLE trust_scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id     UUID NOT NULL REFERENCES suppliers(id),
  score           SMALLINT NOT NULL,   -- 0..1000
  band            TEXT NOT NULL,       -- low|medium|high|excellent
  model_version   TEXT NOT NULL,
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  features        JSONB NOT NULL,      -- raw input feature vector
  attributions    JSONB NOT NULL       -- SHAP per-feature contributions
);
CREATE INDEX ON trust_scores (supplier_id, computed_at DESC);

CREATE TABLE relationships (
  from_supplier   UUID NOT NULL REFERENCES suppliers(id),
  to_supplier     UUID NOT NULL REFERENCES suppliers(id),
  edge_type       TEXT NOT NULL,    -- pays|director_shared|address_shared|disputed_with
  weight          REAL NOT NULL DEFAULT 1.0,
  first_seen      TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen       TIMESTAMPTZ,
  PRIMARY KEY (from_supplier, to_supplier, edge_type)
);

CREATE TABLE consents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  supplier_id   UUID NOT NULL REFERENCES suppliers(id),
  grantee_tenant UUID NOT NULL REFERENCES tenants(id),
  scopes        TEXT[] NOT NULL,    -- ['identity','score','documents:gst']
  granted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  revoked_at    TIMESTAMPTZ
);
```

### 4.3 Indexes & performance notes
- All FK columns are indexed.
- `ledger_events` is partitioned by `supplier_id` hash once row count > ~50M.
- `trust_scores.computed_at DESC` index supports "latest score" lookups.
- `pgvector` lives in a sibling table `document_embeddings(doc_id, embedding vector(384))`.

---

## 5. API Design

REST with JSON. OpenAPI auto-generated by FastAPI. All endpoints
tenant-scoped via `Authorization: Bearer <jwt>`; the tenant is encoded in
the token, never in the path.

### 5.1 Routes

```
# Auth
POST   /v1/auth/login                     → {access_token, refresh_token}
POST   /v1/auth/refresh
POST   /v1/auth/api-keys                  → mint server-to-server key

# Suppliers
POST   /v1/suppliers                      → onboard {legal_name, pan, gstin?, ...}
GET    /v1/suppliers/{id}
GET    /v1/suppliers?status=&q=&page=
PATCH  /v1/suppliers/{id}                 → display fields only (ledger-logged)

# Identifiers
POST   /v1/suppliers/{id}/identifiers     → add GSTIN/CIN/PAN; triggers verify
GET    /v1/suppliers/{id}/identifiers

# Documents
POST   /v1/suppliers/{id}/documents       → multipart; returns doc_id
GET    /v1/suppliers/{id}/documents
GET    /v1/documents/{doc_id}/extraction  → structured fields + confidence

# Verification
POST   /v1/suppliers/{id}/verify          → {adapters: ["gstn","mca","watchlist"]}
GET    /v1/suppliers/{id}/verifications
GET    /v1/verifications/{run_id}

# Trust score
GET    /v1/suppliers/{id}/trust-score              → latest
GET    /v1/suppliers/{id}/trust-score/history
POST   /v1/suppliers/{id}/trust-score/recompute    → force recompute
GET    /v1/suppliers/{id}/trust-score/explanation  → SHAP + plain-English

# Ledger
GET    /v1/suppliers/{id}/ledger?since=&type=      → events, newest first
GET    /v1/suppliers/{id}/ledger/verify            → hash-chain integrity check

# Relationships
GET    /v1/suppliers/{id}/network?depth=2

# Consents
POST   /v1/consents                                → supplier grants buyer access
DELETE /v1/consents/{id}                           → revoke

# Admin / system
GET    /v1/health
GET    /v1/metrics                                  (Prometheus)
```

### 5.2 Example: onboarding response

```json
POST /v1/suppliers
{
  "legal_name": "Acme Traders Pvt Ltd",
  "pan": "AABCA1234C",
  "gstin": "29AABCA1234C1Z5",
  "primary_address": { "line1": "...", "pincode": "560001" }
}

→ 201 Created
{
  "id": "9f2c…",
  "status": "pending",
  "trust_score": null,
  "verifications_queued": ["gstn", "mca", "pan_status", "watchlist"],
  "ledger_event_id": 1
}
```

### 5.3 Webhooks (out, for buyer integrations)
- `supplier.score.changed` — band transition (e.g., medium → high)
- `supplier.verification.completed`
- `supplier.adverse_media.detected`
- `supplier.consent.revoked`

Signed with HMAC-SHA256 over the body; receivers verify with shared secret.

---

## 6. ML Approach for Trust Scoring

### 6.1 Target & framing
- **Output**: score in [0, 1000], banded as Low / Medium / High / Excellent.
- **Training label** (POC): a *proxy* — synthesized from a rules baseline +
  any historical labels we can scrape from public defaults (MCA struck-off,
  GST cancellations, IBC filings). For a real launch, we'd label on
  **future** payment defaults / disputes within a 90/180-day window.
- **Frame**: regression to a calibrated 0–1 risk, then linearly mapped to score.

### 6.2 Feature groups (~60 features for v1)

| Group | Examples |
|---|---|
| Identity coherence | name match PAN↔GSTIN↔CIN, address match, director–PAN match |
| Vintage | days since incorporation, days since GST registration |
| Compliance | GSTR-3B filings on time (last 12m), late filings count, EPFO active |
| Financial | declared turnover band, ITR-confirmed turnover, bank avg balance |
| Watchlist | OFAC/UN/MHA hit, RBI defaulter, wilful defaulter |
| Adverse media | semantic match score against negative news corpus |
| Document quality | OCR confidence, signer cert valid, hash match with issuer |
| Network | shared address with struck-off entity (1 / 2-hop), centrality |
| Behavior | on-platform tenure, dispute rate, payment-acceptance latency |
| Stability | director changes in last 12m, address changes, RoC charges |

### 6.3 Models

```
                   ┌───────────────────────────────┐
   tabular feats → │ XGBoost regressor (primary)   │ → risk score [0,1]
                   │  + isotonic calibration       │
                   └──────────────┬────────────────┘
                                  │
   text/news    → embedder → kNN ─┤  (adverse-media feature)
                                  │
   relationship → GraphSAGE  ────┤  (network feature, v2)
   graph        (Phase 4+)        │
                                  ▼
                       Linear map → 0..1000 → band
                                  │
                                  ▼
                       SHAP → per-feature attributions
                       Claude → plain-English rationale
```

**Why XGBoost first**: tabular state of the art, handles missing values
natively, fast to train, SHAP explanations are well-understood. Move to a
deep tabular model (FT-Transformer) only if XGB plateaus.

### 6.4 Explainability
For every score we store:
1. The full input feature vector (`trust_scores.features`).
2. SHAP values per feature (`trust_scores.attributions`).
3. A short natural-language rationale generated by Claude from the top-5
   SHAP contributors (positive and negative).

This is what we display in the UI:

> **Trust score: 742 (High)**
> - **+** GST returns filed on time for 11/12 months (+87)
> - **+** Incorporated 7 years ago, active director set unchanged (+54)
> - **−** One director also serves on a struck-off entity (−32)
> - **−** Address shares a building with 14 other suppliers (−18)

### 6.5 Model lifecycle
- Versioned model artifacts in S3 (`models/trust/v1.2.3.json`).
- `model_version` stamped on every `trust_scores` row.
- Re-score nightly for active suppliers; on-demand on event triggers.
- Champion/challenger evaluation in shadow before promotion.

### 6.6 Where the LLM is (and isn't) load-bearing
- **Used for**: document field extraction, normalization, adverse-media
  classification (zero-shot), rationale generation.
- **Not used for**: the score itself. The score must be deterministic,
  auditable, and cheap to recompute at scale. An LLM in that loop fails
  all three.

---

## 7. Frontend (Next.js)

Minimal, focused screens for the POC:

1. **Suppliers list** — search, filter by band, sort by score.
2. **Supplier detail** — header (name, score, band), tabs for:
   - Overview (key identifiers, status, key dates)
   - Verifications (per-adapter results, retry buttons)
   - Documents (upload, view extracted fields)
   - Trust score (current + history chart + SHAP explanation)
   - Ledger (chronological event stream + "verify chain" button)
   - Network (force-directed graph, depth 1–2)
3. **Onboard supplier** — wizard: identifiers → docs → consent → review.
4. **Settings** — API keys, webhook URLs, team.

Component library: `shadcn/ui`. State: TanStack Query for server state,
Zustand for the bit of client state. No Redux.

---

## 8. Security & Compliance

- **PII**: PAN, Aadhaar (never store full Aadhaar — masked last-4 only).
  Column-level encryption (`pgcrypto`) for `pan`, `bank_account_number`.
- **Tenant isolation**: Postgres RLS on every supplier-scoped table.
- **Authn**: short-lived JWT (15 min) + rotating refresh; API keys hashed
  with Argon2.
- **Authz**: role-based (`admin`, `analyst`, `viewer`, `api`).
- **Audit**: every read of sensitive fields logged to `access_log`.
- **Data residency**: POC runs in `ap-south-1` (India). DPDP-aware: consent
  records in `consents`; "right to be forgotten" implemented as
  cryptographic-shred (delete the per-supplier key, keep hash-chained
  events so the chain remains verifiable but content is unrecoverable).
- **Secrets**: AWS Secrets Manager (prod), `.env` + sops (dev). Never in repo.
- **Threat model docs**: STRIDE pass before Phase 5.

---

## 9. Implementation Roadmap

Assumes 2 engineers + part-time PM/designer. Calendar weeks.

### Phase 0 — Foundations (Week 1)
- Repo scaffold (FastAPI + Next.js monorepo via `uv` and `pnpm`).
- docker-compose: Postgres, Redis, MinIO, Mailhog.
- CI: lint (ruff + mypy + eslint), test, build images.
- Alembic baseline migration.
- OpenTelemetry wired locally to Grafana stack.
- **Exit**: `make up` brings the whole world up; smoke test passes.

### Phase 1 — Core supplier CRUD + ledger (Weeks 2–3)
- Tenants, users, JWT auth.
- Suppliers, identifiers, addresses CRUD.
- Append-only `ledger_events` with hash chain + integrity check endpoint.
- Basic Next.js list + detail (no scoring yet).
- **Exit**: can onboard a supplier; every action shows up in the ledger;
  `GET /ledger/verify` returns `{"valid": true}`.

### Phase 2 — Verification adapters (Weeks 4–5)
- Adapter framework: pluggable, async, retried via Redis queue.
- Adapters (stubbed for POC, swap to real APIs later):
  - GSTN (status, filing history) — start with sandbox/mock
  - MCA21 (company status, directors)
  - PAN status
  - Watchlist (OFAC + a packaged India list)
- Findings normalized into `verification_findings`.
- **Exit**: onboarding triggers all adapters; results visible in UI.

### Phase 3 — Documents + LLM extraction (Weeks 5–6, overlaps)
- S3/MinIO upload with presigned URLs.
- OCR pipeline (Tesseract first, PaddleOCR fallback).
- Claude prompts for structured extraction (GST cert, COI, PAN, bank stmt).
- Document hash recorded in ledger.
- **Exit**: upload a GST certificate → see structured fields with
  confidence in UI within ~10s.

### Phase 4 — Trust score v1 (Weeks 7–8)
- Feature engineering pipeline (Postgres views + Python builder).
- Synthetic labels for bootstrap; XGBoost training notebook.
- Inference service; SHAP attributions stored.
- Claude-generated rationale endpoint.
- Trust-score UI tab with history chart + factor breakdown.
- **Exit**: every supplier has a score; recomputing is < 200ms; the
  rationale reads like something a human analyst wrote.

### Phase 5 — Network + consents (Week 9)
- Relationship extraction from shared identifiers (directors, address, PAN).
- Force-directed graph viz.
- Consent grant/revoke endpoints + UI.
- Buyer-to-buyer score sharing gated on consent.
- **Exit**: supplier can grant Buyer B access to their score; Buyer B sees
  it without re-running verifications.

### Phase 6 — Hardening + demo (Weeks 10–11)
- Security review (STRIDE), pen-test on auth surfaces.
- Load test (target: 1k onboardings/day, p95 < 500ms for score reads).
- Webhooks out (signed).
- Demo data set: 200 synthetic suppliers with realistic distributions.
- Demo script + scripted walkthrough.
- **Exit**: stakeholder demo passes; decision gate for full build.

### Stretch (post-POC)
- GraphSAGE on the relationship graph (Phase 4 v2 features).
- Buyer-side embedded SDK (drop-in React component for onboarding flows).
- Streaming score updates via Server-Sent Events.
- Multi-region active-active.

---

## 10. Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Authoritative-source APIs (GSTN, MCA) gated/expensive | Start with sandbox/mocks; budget for Karza/Signzy/IDfy as fallback aggregators |
| Label scarcity for trust model | Bootstrap with rules + public defaults; instrument for future outcome capture |
| LLM hallucination in doc extraction | Constrain with JSON Schema response; confidence scores; second-pass diff against source text |
| Privacy / DPDP non-compliance | Consent table; crypto-shred for deletion; DPO review before any cross-tenant sharing |
| Score gaming by suppliers | Mix observed signals with declared; weight authoritative > self-reported; monitor distribution drift |
| Ledger integrity vs. operational mistakes (wrong onboarding) | Never edit/delete; emit *correcting* events; UI shows "current value" computed from the chain |

**Open questions to resolve before/during Phase 0:**
1. Who is the first buyer-of-one for the POC demo? Their data shapes Phase 2 adapters.
2. Indian-only for POC, or are we serving cross-border (DUNS, EIN) day one?
3. Do we self-host LLM (cost) or stay on Anthropic API (speed)? Recommend the latter for POC.
4. Are GSTN/MCA direct integrations on the table, or do we go via an aggregator for the POC?
5. Is there a payment-event stream we can subscribe to for the behavioral features?

---

## 11. Success Criteria for the POC

The POC is judged ready to graduate to a funded build if **all** of:

1. **Functional**: can onboard a supplier end-to-end, run all adapters, produce a score with a human-readable rationale, and pass `GET /ledger/verify`.
2. **Performance**: p95 < 500ms on score reads; full onboarding (incl. async verifications) < 60s wall-clock on the demo dataset.
3. **Quality**: trust score has AUC > 0.75 against a held-out set of known-bad suppliers (MCA struck-off + GST-cancelled).
4. **Trust**: ledger integrity check passes after a deliberate tamper test (and *fails* loudly when we tamper).
5. **Demo**: a non-technical stakeholder can drive the UI through the golden path unaided after a 5-minute walkthrough.

---

## 12. Repo Layout (proposed)

```
supplier-trust-ledger/
├── PLAN.md                       (this file)
├── README.md
├── docker-compose.yml
├── Makefile
├── pyproject.toml                (uv workspace root)
├── apps/
│   ├── api/                      FastAPI service
│   │   ├── stl/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   ├── services/
│   │   │   ├── adapters/         GSTN, MCA, watchlist, ...
│   │   │   ├── ledger/           hash-chain helpers
│   │   │   ├── scoring/          features, train, infer, shap
│   │   │   ├── llm/              Claude client + prompts
│   │   │   └── db/               sqlalchemy models, migrations
│   │   ├── tests/
│   │   └── alembic.ini
│   └── web/                      Next.js app
│       ├── app/
│       ├── components/
│       └── lib/
├── packages/
│   └── shared-types/             OpenAPI-generated TS types
├── notebooks/                    EDA & model dev
│   └── 01_trust_model_v1.ipynb
├── infra/
│   ├── docker/
│   └── terraform/                (later)
└── .github/workflows/
```

---

*Last updated: 2026-05-12. Author: STL POC team.*
