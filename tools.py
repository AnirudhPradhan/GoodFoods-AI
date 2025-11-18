# tools.py — FULL GoodFoods Tools Engine (with synthetic restaurant fallback)

import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# ---------------------------------------------
# DB PATH (Absolute)
# ---------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "restaurants.db")
DEFAULT_MAX_RESULTS = 6


# ---------------------------------------------
# Internal Helpers
# ---------------------------------------------
def _connect():
    """Ensure DB exists and return connection."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)

def _now_iso_minutes():
    return datetime.utcnow().isoformat(timespec="minutes")


# ---------------------------------------------
# Availability Snapshot
# ---------------------------------------------
def _availability_snapshot(restaurant_id: int, time_iso: str):
    conn = _connect()
    c = conn.cursor()

    c.execute("SELECT capacity FROM restaurants WHERE id=?", (restaurant_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"available_seats": 0}

    capacity = row["capacity"] or 0

    c.execute("""
        SELECT SUM(party_size) AS used
        FROM bookings
        WHERE restaurant_id=? AND time=?
    """, (restaurant_id, time_iso))
    used = c.fetchone()["used"] or 0
    conn.close()

    return {
        "available_seats": max(capacity - used, 0),
        "capacity": capacity,
        "booked": used
    }


# ---------------------------------------------
# SEARCH Restaurants (DB)
# ---------------------------------------------
def search_restaurants(
    cuisine=None, city=None, neighborhood=None, price_label=None,
    min_rating=None, veg_only=None, party_size=None, time=None
):
    conn = _connect()
    c = conn.cursor()

    q = """
    SELECT id, name, cuisine, city, neighborhood, address, phone,
           rating, price_label, price_in_inr, capacity, veg_only
    FROM restaurants WHERE 1=1
    """
    p = []

    if cuisine:
        q += " AND cuisine LIKE ?"
        p.append(f"%{cuisine}%")

    if city:
        q += " AND city LIKE ?"
        p.append(f"%{city}%")

    if neighborhood:
        q += " AND neighborhood LIKE ?"
        p.append(f"%{neighborhood}%")

    if price_label:
        q += " AND price_label=?"
        p.append(price_label)

    if min_rating is not None:
        q += " AND rating>=?"
        p.append(min_rating)

    if veg_only is not None:
        q += " AND veg_only=?"
        p.append(1 if veg_only else 0)

    q += " ORDER BY rating DESC, price_in_inr ASC"
    c.execute(q, p)
    rows = c.fetchall()
    conn.close()

    check_time = time or _now_iso_minutes()

    results = []
    for r in rows[:DEFAULT_MAX_RESULTS]:
        snap = _availability_snapshot(r["id"], check_time)

        results.append({
            "id": r["id"],
            "name": r["name"],
            "cuisine": r["cuisine"],
            "city": r["city"],
            "neighborhood": r["neighborhood"],
            "address": r["address"],
            "phone": r["phone"],
            "rating": r["rating"],
            "price_label": r["price_label"],
            "avg_price_in_inr": r["price_in_inr"],
            "capacity": r["capacity"],
            "available_seats": snap["available_seats"],
            "veg_only": bool(r["veg_only"])
        })

    return _json(results)


# ---------------------------------------------
# SYNTHETIC RESTAURANT INFO  (LLama-generated externally)
# ---------------------------------------------
def synthetic_restaurant_info(name: str, city: str = "Unknown", data: dict = None):
    """
    THIS TOOL DOES NOT GENERATE INFO.
    Llama generates the info, passes it here.
    This tool simply returns the JSON and assigns dummy ID.
    """

    data = data or {}

    dummy = {
        "id": 999999,
        "name": data.get("name", name) + " (Imported)",
        "city": city,
        "neighborhood": data.get("neighborhood", "Unknown"),
        "address": data.get("address", ""),
        "phone": data.get("phone", ""),
        "rating": data.get("rating", 4.2),
        "price_label": data.get("price_label", "₹₹"),
        "avg_price_in_inr": data.get("avg_price_in_inr", 600),
        "capacity": data.get("capacity", 50),
        "veg_only": data.get("veg_only", False),
        "cuisine": data.get("cuisine", "Indian")
    }

    return _json(dummy)


# ---------------------------------------------
# BOOK TABLE
# ---------------------------------------------
def book_table(restaurant_id: int, customer_name: str, time: str, party_size: int):
    try:
        dt = datetime.fromisoformat(time)
        time = dt.isoformat(timespec="minutes")
    except:
        pass

    # DUMMY RESTAURANT BOOKING
    if restaurant_id == 999999:
        return _json({
            "success": True,
            "message": f"Booking confirmed at dummy restaurant for {customer_name}",
            "restaurant_id": restaurant_id,
            "time": time,
            "party_size": party_size
        })

    snap = _availability_snapshot(restaurant_id, time)
    if snap["available_seats"] < party_size:
        return _json({
            "success": False,
            "reason": "Not enough seats",
            "available_seats": snap["available_seats"]
        })

    conn = _connect()
    c = conn.cursor()
    c.execute("""
        INSERT INTO bookings (restaurant_id, customer_name, time, party_size)
        VALUES (?,?,?,?)
    """, (restaurant_id, customer_name, time, party_size))
    conn.commit()
    conn.close()

    return _json({
        "success": True,
        "message": "Booking confirmed",
        "restaurant_id": restaurant_id,
        "time": time,
        "party_size": party_size
    })


# ---------------------------------------------
# TOOL REGISTRY
# ---------------------------------------------
TOOL_REGISTRY = {
    "search_restaurants": search_restaurants,
    "synthetic_restaurant_info": synthetic_restaurant_info,
    "book_table": book_table
}

def execute_tool(name: str, args: Dict[str, Any]):
    func = TOOL_REGISTRY.get(name)
    if not func:
        return _json({"error": "Unknown tool"})
    try:
        return func(**args)
    except Exception as e:
        return _json({"error": str(e)})


# ---------------------------------------------
# SCHEMA for LLM Planning
# ---------------------------------------------
tools_schema = {
    "search_restaurants": {
        "cuisine": "string",
        "city": "string",
        "neighborhood": "string",
        "price_label": "string",
        "min_rating": "number",
        "veg_only": "boolean",
        "party_size": "number",
        "time": "string"
    },
    "synthetic_restaurant_info": {
        "name": "string",
        "city": "string",
        "data": "object"
    },
    "book_table": {
        "restaurant_id": "number",
        "customer_name": "string",
        "time": "string",
        "party_size": "number"
    }
}
