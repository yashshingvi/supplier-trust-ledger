"""Stubbed verification adapters.

Real adapters would call GSTN / MCA21 / OFAC etc. For the POC we derive
plausible verification outcomes from the identifiers' shape so the demo
behaves deterministically.
"""
import re

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]$")
CIN_RE = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")


def verify_pan(pan: str | None) -> bool:
    return bool(pan and PAN_RE.match(pan))


def verify_gstin(gstin: str | None) -> bool:
    return bool(gstin and GSTIN_RE.match(gstin))


def verify_cin(cin: str | None) -> bool:
    return bool(cin and CIN_RE.match(cin))


# A tiny in-memory "watchlist" for the demo. Real impl: OFAC + RBI lists.
WATCHLIST_NAMES = {
    "shady traders pvt ltd",
    "phantom exports llp",
}
WATCHLIST_PANS = {"AAAAA0000A"}


def screen_watchlist(legal_name: str | None, pan: str | None) -> bool:
    if legal_name and legal_name.strip().lower() in WATCHLIST_NAMES:
        return True
    if pan and pan in WATCHLIST_PANS:
        return True
    return False
