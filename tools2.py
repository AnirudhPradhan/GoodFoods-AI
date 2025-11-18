# tools.py — Full toolset for GoodFoods (search, recommend, book, menus, events, feedback, loyalty, SMS stub)
import os
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

# ---- Ensure DB path is absolute (avoids Windows relative path issues) ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "restaurants.db")
DEFAULT_MAX_RESULTS = 6

# -------------------------
# Internal helpers
# -------------------------
def _connect():
    if not os.path.exists(os.path.dirname(DB_PATH)):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn

def _json(data: Any) -> str:
    # Always return JSON string (agent expects string content)
    return json.dumps(data, ensure_ascii=False)

def _now_iso_minutes():
    return datetime.utcnow().isoformat(timespec="minutes")

# -------------------------
# Availability snapshot
# -------------------------
def _availability_snapshot(restaurant_id: int, time_iso: str):
    """
    Very simple availability heuristic:
      available_seats = capacity - SUM(party_size at exact time)
    Note: times must be exact-match ISO strings (this matches seeded bookings).
    """
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute("SELECT capacity FROM restaurants WHERE id = ?", (restaurant_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"available_seats": 0}
    capacity = row["capacity"] or 0

    cursor.execute("""
        SELECT SUM(party_size) as used
        FROM bookings
        WHERE restaurant_id = ? AND time = ?
    """, (restaurant_id, time_iso))
    used = cursor.fetchone()["used"] or 0
    conn.close()
    return {"available_seats": max(capacity - used, 0), "capacity": capacity, "booked": used}

# -------------------------
# Tools: Search Restaurants
# -------------------------
def search_restaurants(
    cuisine: Optional[str] = None,
    city: Optional[str] = None,
    neighborhood: Optional[str] = None,
    price_label: Optional[str] = None,
    min_rating: Optional[float] = None,
    veg_only: Optional[bool] = None,
    party_size: Optional[int] = None,
    time: Optional[str] = None
):
    """
    Returns up to DEFAULT_MAX_RESULTS restaurants (JSON string).
    """
    conn = _connect()
    cursor = conn.cursor()
    query = """
        SELECT id, name, cuisine, city, neighborhood, address, phone, rating, price_label, price_in_inr, capacity, veg_only
        FROM restaurants WHERE 1=1
    """
    params = []

    if cuisine:
        query += " AND cuisine LIKE ?"
        params.append(f"%{cuisine}%")
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")
    if neighborhood:
        query += " AND neighborhood LIKE ?"
        params.append(f"%{neighborhood}%")
    if price_label:
        query += " AND price_label = ?"
        params.append(price_label)
    if min_rating is not None:
        query += " AND rating >= ?"
        params.append(min_rating)
    if veg_only is not None:
        query += " AND veg_only = ?"
        params.append(1 if veg_only else 0)

    query += " ORDER BY rating DESC, price_in_inr ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    check_time = time or _now_iso_minutes()
    results = []
    for r in rows[:DEFAULT_MAX_RESULTS]:
        snap = _availability_snapshot(r["id"], check_time)
        can_fit = party_size is None or snap["available_seats"] >= party_size

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
            "can_accommodate_party": can_fit,
            "veg_only": bool(r["veg_only"])
        })

    return _json(results)

# -------------------------
# Recommend Restaurants
# -------------------------
def recommend_restaurants(
    city: Optional[str] = None,
    cuisine: Optional[str] = None,
    time: Optional[str] = None,
    party_size: Optional[int] = None
):
    """
    Returns top 3 recommendations (JSON string) with short 'why' justification.
    """
    conn = _connect()
    cursor = conn.cursor()
    query = "SELECT id, name, cuisine, city, neighborhood, rating, price_in_inr, veg_only FROM restaurants WHERE 1=1"
    params = []
    if city:
        query += " AND city LIKE ?"
        params.append(f"%{city}%")
    if cuisine:
        query += " AND cuisine LIKE ?"
        params.append(f"%{cuisine}%")
    query += " ORDER BY rating DESC, price_in_inr ASC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    check_time = time or _now_iso_minutes()
    recs = []
    for r in rows:
        snap = _availability_snapshot(r["id"], check_time)
        if party_size and snap["available_seats"] < party_size:
            # skip if cannot accommodate party
            continue
        recs.append({
            "id": r["id"],
            "name": r["name"],
            "city": r["city"],
            "neighborhood": r["neighborhood"],
            "cuisine": r["cuisine"],
            "rating": r["rating"],
            "avg_price_in_inr": r["price_in_inr"],
            "veg_only": bool(r["veg_only"]),
            "why": f"Rated {r['rating']} · Good fit for {cuisine or 'local tastes'} · Avg spend ~₹{r['price_in_inr']}"
        })
        if len(recs) >= 3:
            break

    return _json(recs)

# -------------------------
# Get Menu for Restaurant
# -------------------------
def get_menu(restaurant_id: int, category: Optional[str] = None):
    conn = _connect()
    cursor = conn.cursor()
    query = "SELECT item_name, category, price, is_signature FROM menus WHERE restaurant_id = ?"
    params = [restaurant_id]
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY is_signature DESC, price ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    menu = [{"item_name": r["item_name"], "category": r["category"], "price": r["price"], "is_signature": bool(r["is_signature"])} for r in rows]
    return _json(menu)

# -------------------------
# List Upcoming Events
# -------------------------
def list_upcoming_events(city: Optional[str] = None, within_days: int = 30):
    conn = _connect()
    cursor = conn.cursor()
    query = """
        SELECT e.id, e.restaurant_id, e.event_name, e.event_date, e.description, r.name as restaurant_name, r.city
        FROM events e
        JOIN restaurants r ON r.id = e.restaurant_id
        WHERE datetime(e.event_date) >= datetime('now')
    """
    params: List[Any] = []
    if city:
        query += " AND r.city LIKE ?"
        params.append(f"%{city}%")

    # by default fetch within X days
    until = datetime.utcnow() + timedelta(days=within_days)
    query += " ORDER BY e.event_date ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        dt = r["event_date"]
        try:
            # optional filter by within_days
            ed = datetime.fromisoformat(dt)
            if ed > until:
                continue
        except Exception:
            pass
        events.append({
            "id": r["id"],
            "restaurant_id": r["restaurant_id"],
            "restaurant_name": r["restaurant_name"],
            "event_name": r["event_name"],
            "event_date": r["event_date"],
            "description": r["description"],
            "city": r["city"]
        })

    return _json(events)

# -------------------------
# Log Feedback
# -------------------------
def log_feedback(restaurant_id: int, customer_name: str, rating: float, comments: Optional[str] = None):
    conn = _connect()
    cursor = conn.cursor()
    created_at = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO feedback (restaurant_id, customer_name, rating, comments, created_at) VALUES (?,?,?,?,?)",
        (restaurant_id, customer_name, rating, comments or "", created_at)
    )
    conn.commit()
    conn.close()
    return _json({"success": True, "message": "Feedback recorded."})

# -------------------------
# Loyalty Profile
# -------------------------
def get_loyalty_profile(phone: Optional[str] = None, name: Optional[str] = None):
    conn = _connect()
    cursor = conn.cursor()
    if phone:
        cursor.execute("SELECT id, name, phone, tier, favorite_cuisine, preferred_city FROM loyalty_customers WHERE phone LIKE ? LIMIT 1", (f"%{phone}%",))
    elif name:
        cursor.execute("SELECT id, name, phone, tier, favorite_cuisine, preferred_city FROM loyalty_customers WHERE name LIKE ? LIMIT 1", (f"%{name}%",))
    else:
        conn.close()
        return _json({})
    row = cursor.fetchone()
    conn.close()
    if not row:
        return _json({})
    return _json({
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "tier": row["tier"],
        "favorite_cuisine": row["favorite_cuisine"],
        "preferred_city": row["preferred_city"]
    })

# -------------------------
# Book Table
# -------------------------
def book_table(restaurant_id: int, customer_name: str, time: str, party_size: int):
    """
    Attempts to reserve; returns success boolean + message.
    Time should be ISO string (minutes resolution).
    """
    # Normalize time to minutes ISO
    try:
        # if time is not in minutes resolution, convert to minutes resolution
        dt = datetime.fromisoformat(time)
        time_iso = dt.isoformat(timespec="minutes")
    except Exception:
        # if parse fails, use provided string
        time_iso = time

    snap = _availability_snapshot(restaurant_id, time_iso)
    if snap["available_seats"] < party_size:
        return _json({"success": False, "reason": "Not enough seats available", "available_seats": snap["available_seats"]})

    conn = _connect()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO bookings (restaurant_id, customer_name, time, party_size, source) VALUES (?,?,?,?,?)",
        (restaurant_id, customer_name, time_iso, party_size, "agent")
    )
    conn.commit()
    conn.close()
    return _json({"success": True, "message": "Booking confirmed", "restaurant_id": restaurant_id, "time": time_iso, "party_size": party_size})

# -------------------------
# SMS Follow-up (stub)
# -------------------------
def trigger_followup_sms(phone_number: str, message: str):
    """
    Stub that simulates sending SMS. In production, wire to Twilio or similar.
    """
    # For now just log to DB (feedback table) or return a simulated response
    # Do not actually send SMS from here. The agent can present this as 'SMS sent' behaviorally.
    return _json({"success": True, "simulated": True, "message": f"SMS queued to {phone_number}", "body": message})

# -------------------------
# Tool registry & execution
# -------------------------
TOOL_REGISTRY = {
    "search_restaurants": search_restaurants,
    "recommend_restaurants": recommend_restaurants,
    "get_menu": get_menu,
    "list_upcoming_events": list_upcoming_events,
    "log_feedback": log_feedback,
    "get_loyalty_profile": get_loyalty_profile,
    "book_table": book_table,
    "trigger_followup_sms": trigger_followup_sms
}

def execute_tool(tool_name: str, tool_args: Dict[str, Any]):
    if tool_name not in TOOL_REGISTRY:
        return _json({"error": f"Unknown tool: {tool_name}"})
    func = TOOL_REGISTRY[tool_name]
    # The Groq agent expects JSON-serializable return values (strings ok)
    try:
        # Ensure we pass only expected kwargs (defensive)
        result = func(**tool_args)
    except TypeError:
        # Try extracting values as primitive mapping (coerce keys)
        # This supports numeric strings coming from agent
        safe_args = {}
        for k, v in tool_args.items():
            safe_args[k] = v
        result = func(**safe_args)
    return result

# -------------------------
# Tools schema (for planner)
# -------------------------
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
    "recommend_restaurants": {
        "city": "string",
        "cuisine": "string",
        "time": "string",
        "party_size": "number"
    },
    "get_menu": {
        "restaurant_id": "number",
        "category": "string"
    },
    "list_upcoming_events": {
        "city": "string",
        "within_days": "number"
    },
    "log_feedback": {
        "restaurant_id": "number",
        "customer_name": "string",
        "rating": "number",
        "comments": "string"
    },
    "get_loyalty_profile": {
        "phone": "string",
        "name": "string"
    },
    "book_table": {
        "restaurant_id": "number",
        "customer_name": "string",
        "time": "string",
        "party_size": "number"
    },
    "trigger_followup_sms": {
        "phone_number": "string",
        "message": "string"
    }
}
