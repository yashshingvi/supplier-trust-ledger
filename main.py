"""Supplier Trust Ledger — FastAPI app.

Serves the supplier list, individual supplier details, and a dashboard
aggregate over a local SQLite database.
"""
from __future__ import annotations

import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "suppliers.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")


app = FastAPI(title="Supplier Trust Ledger", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=503,
            detail="Database not initialized. Run `python seed.py` first.",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


@app.get("/suppliers")
def list_suppliers(
    q: Optional[str] = Query(None, description="Search by supplier name or GSTIN"),
    band: Optional[str] = Query(None, description="Filter by trust band"),
    verified: Optional[bool] = Query(None, description="Filter by verified flag"),
    sort: str = Query("score_desc", description="score_desc|score_asc|name"),
    limit: int = Query(100, ge=1, le=500),
):
    conn = get_conn()
    try:
        sql = "SELECT * FROM suppliers WHERE 1=1"
        params: list = []
        if q:
            sql += " AND (LOWER(name) LIKE ? OR LOWER(gstin) LIKE ?)"
            needle = f"%{q.lower()}%"
            params.extend([needle, needle])
        if band:
            sql += " AND LOWER(trust_band) = ?"
            params.append(band.lower())
        if verified is not None:
            sql += " AND verified = ?"
            params.append(1 if verified else 0)

        if sort == "score_asc":
            sql += " ORDER BY trust_score ASC"
        elif sort == "name":
            sql += " ORDER BY name COLLATE NOCASE ASC"
        else:
            sql += " ORDER BY trust_score DESC"

        sql += " LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return {"count": len(rows), "results": [row_to_dict(r) for r in rows]}
    finally:
        conn.close()


@app.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM suppliers WHERE id = ?", (supplier_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return row_to_dict(row)
    finally:
        conn.close()


@app.get("/dashboard")
def dashboard():
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM suppliers").fetchone()["c"]
        if total == 0:
            return {
                "total_suppliers": 0,
                "verified_count": 0,
                "avg_trust_score": 0,
                "avg_compliance_score": 0,
                "avg_on_time_delivery_pct": 0,
                "total_disputes": 0,
                "by_band": {},
                "top_suppliers": [],
                "bottom_suppliers": [],
            }

        agg = conn.execute(
            """
            SELECT
                SUM(verified) AS verified_count,
                AVG(trust_score) AS avg_trust_score,
                AVG(compliance_score) AS avg_compliance_score,
                AVG(on_time_delivery_pct) AS avg_on_time_delivery_pct,
                SUM(dispute_count) AS total_disputes
            FROM suppliers
            """
        ).fetchone()

        band_rows = conn.execute(
            "SELECT trust_band, COUNT(*) AS c FROM suppliers GROUP BY trust_band"
        ).fetchall()
        by_band = {r["trust_band"]: r["c"] for r in band_rows}

        top = conn.execute(
            "SELECT id, name, trust_score, trust_band FROM suppliers "
            "ORDER BY trust_score DESC LIMIT 5"
        ).fetchall()
        bottom = conn.execute(
            "SELECT id, name, trust_score, trust_band FROM suppliers "
            "ORDER BY trust_score ASC LIMIT 5"
        ).fetchall()

        return {
            "total_suppliers": total,
            "verified_count": int(agg["verified_count"] or 0),
            "avg_trust_score": round(float(agg["avg_trust_score"] or 0), 1),
            "avg_compliance_score": round(float(agg["avg_compliance_score"] or 0), 1),
            "avg_on_time_delivery_pct": round(
                float(agg["avg_on_time_delivery_pct"] or 0), 1
            ),
            "total_disputes": int(agg["total_disputes"] or 0),
            "by_band": by_band,
            "top_suppliers": [row_to_dict(r) for r in top],
            "bottom_suppliers": [row_to_dict(r) for r in bottom],
        }
    finally:
        conn.close()


@app.get("/health")
def health():
    return {"status": "ok", "db_exists": os.path.exists(DB_PATH)}


@app.get("/")
def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"name": "Supplier Trust Ledger", "docs": "/docs"}


if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
