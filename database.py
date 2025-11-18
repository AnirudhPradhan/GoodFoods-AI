# database.py
import os
import sqlite3
from datetime import datetime, timedelta
from faker import Faker
import random

MENU_CATEGORIES = ["Starter", "Main", "Dessert", "Beverage"]
LOYALTY_TIERS = ["Silver", "Gold", "Platinum"]

# Indian neighborhoods & cities (sample)
CITIES_NEIGHBORHOODS = {
    "Delhi": ["Connaught Place", "Hauz Khas", "Karol Bagh", "Saket", "Greater Kailash", "Noida Sector 18"],
    "Mumbai": ["Bandra", "Juhu", "Colaba", "Andheri", "Lower Parel", "Powai"],
    "Bengaluru": ["Indiranagar", "Koramangala", "MG Road", "Whitefield", "Jayanagar"],
    "Hyderabad": ["Banjara Hills", "Hitech City", "Jubilee Hills", "Secunderabad"],
    "Chennai": ["Anna Nagar", "T. Nagar", "Adyar", "Velachery"],
    "Kolkata": ["Park Street", "Salt Lake", "Esplanade"],
    "Pune": ["Viman Nagar", "Koregaon Park", "FC Road"]
}

INDIAN_CUISINES = [
    "North Indian", "South Indian", "Punjabi", "Bengali", "Goan", "Kerala", "Hyderabadi",
    "Andhra", "Mughlai", "Street Food", "Mumbai Style", "Kebabs", "Seafood", "Fusion", "Italian", "Chinese"
]

PRICE_TIERS = [
    {"label": "₹", "min": 100, "max": 400},
    {"label": "₹₹", "min": 400, "max": 1200},
    {"label": "₹₹₹", "min": 1200, "max": 2500},
    {"label": "₹₹₹₹", "min": 2500, "max": 10000},
]

def init_db():
    import os

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(BASE_DIR, "data")

    os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(os.path.join(db_dir, 'restaurants.db'), timeout=15)
    c = conn.cursor()
    c.execute('PRAGMA foreign_keys = ON;')

    _create_tables(c)
    _apply_migrations(c)
    conn.commit()

    _seed_restaurants(c)
    _seed_menus(c)
    _seed_loyalty_customers(c)
    _seed_events(c)
    _seed_feedback(c)
    _seed_bookings(c)

    conn.commit()
    conn.close()

def _create_tables(cursor: sqlite3.Cursor):
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS restaurants
           (id INTEGER PRIMARY KEY,
            name TEXT,
            cuisine TEXT,
            city TEXT,
            neighborhood TEXT,
            address TEXT,
            phone TEXT,
            price_label TEXT,
            price_in_inr INTEGER,
            rating REAL,
            capacity INTEGER,
            veg_only INTEGER DEFAULT 0)'''
    )

    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS bookings
           (id INTEGER PRIMARY KEY,
            restaurant_id INTEGER,
            customer_name TEXT,
            time TEXT,
            party_size INTEGER,
            source TEXT DEFAULT 'system',
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id))'''
    )

    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS menus
           (id INTEGER PRIMARY KEY,
            restaurant_id INTEGER,
            item_name TEXT,
            category TEXT,
            price REAL,
            is_signature INTEGER DEFAULT 0,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id))'''
    )

    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS loyalty_customers
           (id INTEGER PRIMARY KEY,
            name TEXT,
            phone TEXT,
            tier TEXT,
            favorite_cuisine TEXT,
            preferred_city TEXT)'''
    )

    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS events
           (id INTEGER PRIMARY KEY,
            restaurant_id INTEGER,
            event_name TEXT,
            event_date TEXT,
            description TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id))'''
    )

    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS feedback
           (id INTEGER PRIMARY KEY,
            restaurant_id INTEGER,
            customer_name TEXT,
            rating REAL,
            comments TEXT,
            created_at TEXT,
            FOREIGN KEY (restaurant_id) REFERENCES restaurants(id))'''
    )

def _apply_migrations(cursor: sqlite3.Cursor):
    try:
        existing = {}
        cursor.execute("PRAGMA table_info(restaurants);")
        for col in cursor.fetchall():
            existing[col[1]] = col
        if "veg_only" not in existing:
            cursor.execute("ALTER TABLE restaurants ADD COLUMN veg_only INTEGER DEFAULT 0;")
    except Exception:
        pass

def _seed_restaurants(cursor: sqlite3.Cursor):
    cursor.execute('SELECT count(*) FROM restaurants')
    if cursor.fetchone()[0] > 0:
        return

    fake = Faker('en_IN')
    restaurants = []
    for city, neighborhoods in CITIES_NEIGHBORHOODS.items():
        for nb in neighborhoods:
            # create several venues per neighborhood
            for _ in range(random.randint(3, 6)):
                cuisine = random.choice(INDIAN_CUISINES)
                name = f"{fake.last_name()} {random.choice(['Bhojanalay', 'Dhaba', 'Kitchen', 'House', 'Cafe', 'Bistro', 'Tadka'])}"
                price_tier = random.choice(PRICE_TIERS)
                price_label = price_tier["label"]
                avg_price = random.randint(price_tier["min"], price_tier["max"])
                rating = round(random.uniform(3.5, 5.0), 1)
                capacity = random.randint(20, 200)
                address = f"{random.randint(10, 200)} {nb} Road, {city}"
                phone = fake.phone_number()
                veg_only = 1 if cuisine in ["South Indian","Kerala","Bengali"] and random.random() < 0.15 else 0

                restaurants.append((
                    name, cuisine, city, nb, address, phone, price_label, avg_price, rating, capacity, veg_only
                ))

    cursor.executemany(
        'INSERT INTO restaurants (name, cuisine, city, neighborhood, address, phone, price_label, price_in_inr, rating, capacity, veg_only) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        restaurants
    )
    print("Seeded India-focused restaurants.")

def _seed_menus(cursor: sqlite3.Cursor):
    cursor.execute('SELECT count(*) FROM menus')
    if cursor.fetchone()[0] > 0:
        return

    cursor.execute('SELECT id, cuisine FROM restaurants')
    rows = cursor.fetchall()
    fake = Faker('en_IN')

    dishes_by_cuisine = {
        "North Indian": ["Butter Chicken", "Dal Makhani", "Paneer Tikka", "Aloo Paratha"],
        "South Indian": ["Masala Dosa", "Idli Sambhar", "Rasam", "Vada"],
        "Punjabi": ["Sarson Ka Saag", "Chole Bhature", "Lassi", "Tandoori Chicken"],
        "Bengali": ["Fish Curry", "Rosogolla", "Mishti Doi"],
        "Hyderabadi": ["Biryani", "Haleem", "Kebabs"],
        "Andhra": ["Spicy Chicken Fry", "Gongura Mutton"],
        "Mughlai": ["Shahi Paneer", "Korma"],
        "Goan": ["Fish Curry", "Prawn Balchao"],
        "Mumbai Style": ["Vada Pav", "Pav Bhaji", "Bombay Sandwich"],
        "Kebabs": ["Seekh Kebab", "Galouti Kebab"],
        "Seafood": ["Tandoori Prawns", "Fish Fry"],
        "Street Food": ["Chaat", "Pani Puri", "Bhel Puri"],
        "Italian": ["Margherita Pizza", "Pasta Arrabiata"],
        "Chinese": ["Manchurian", "Hakka Noodles"],
        "Fusion": ["Indo-Chinese Fried Rice", "Butter Chicken Pizza"]
    }

    rows_to_insert = []
    for restaurant_id, cuisine in rows:
        choices = dishes_by_cuisine.get(cuisine, list(sum(dishes_by_cuisine.values(), [])))
        for _ in range(random.randint(6, 12)):
            item = random.choice(choices)
            cat = random.choice(MENU_CATEGORIES)
            # price around restaurant price_in_inr
            cursor.execute('SELECT price_in_inr FROM restaurants WHERE id = ?', (restaurant_id,))
            base = cursor.fetchone()[0] or 250
            price = round(max(50, random.gauss(base/4, base/6)), 2)
            sig = 1 if random.random() < 0.08 else 0
            rows_to_insert.append((restaurant_id, item, cat, price, sig))

    cursor.executemany(
        'INSERT INTO menus (restaurant_id, item_name, category, price, is_signature) VALUES (?,?,?,?,?)',
        rows_to_insert
    )
    print("Seeded Indian menus.")

def _seed_loyalty_customers(cursor: sqlite3.Cursor):
    cursor.execute('SELECT count(*) FROM loyalty_customers')
    if cursor.fetchone()[0] > 0:
        return

    fake = Faker('en_IN')
    cursor.execute('SELECT DISTINCT cuisine, city FROM restaurants')
    combos = cursor.fetchall()

    rows = []
    for _ in range(80):
        cuisine, city = random.choice(combos)
        rows.append((
            fake.name(),
            fake.phone_number(),
            random.choice(LOYALTY_TIERS),
            cuisine,
            city
        ))

    cursor.executemany(
        'INSERT INTO loyalty_customers (name, phone, tier, favorite_cuisine, preferred_city) VALUES (?,?,?,?,?)',
        rows
    )
    print("Seeded loyalty customers.")

def _seed_events(cursor: sqlite3.Cursor):
    cursor.execute('SELECT count(*) FROM events')
    if cursor.fetchone()[0] > 0:
        return

    fake = Faker('en_IN')
    cursor.execute('SELECT id, city FROM restaurants')
    restaurant_ids = cursor.fetchall()

    events = []
    for restaurant_id, city in restaurant_ids:
        if random.random() < 0.25:
            for _ in range(random.randint(1, 2)):
                events.append((
                    restaurant_id,
                    random.choice(['Chef Special Evening', 'Live Ghazal Night', 'Sunday Brunch', 'Wine Pairing']),
                    (datetime.utcnow() + timedelta(days=random.randint(2, 45))).isoformat(),
                    fake.sentence()
                ))

    cursor.executemany(
        'INSERT INTO events (restaurant_id, event_name, event_date, description) VALUES (?,?,?,?)',
        events
    )
    if events:
        print("Seeded events.")

def _seed_feedback(cursor: sqlite3.Cursor):
    cursor.execute('SELECT count(*) FROM feedback')
    if cursor.fetchone()[0] > 0:
        return

    fake = Faker('en_IN')
    cursor.execute('SELECT id FROM restaurants')
    restaurant_ids = [row[0] for row in cursor.fetchall()]

    rows = []
    for _ in range(180):
        restaurant_id = random.choice(restaurant_ids)
        rows.append((
            restaurant_id,
            fake.name(),
            round(random.uniform(3.0, 5.0), 1),
            fake.sentence(nb_words=12),
            datetime.utcnow().isoformat()
        ))

    cursor.executemany(
        'INSERT INTO feedback (restaurant_id, customer_name, rating, comments, created_at) VALUES (?,?,?,?,?)',
        rows
    )
    print("Seeded feedback.")

def _seed_bookings(cursor: sqlite3.Cursor):
    cursor.execute('SELECT count(*) FROM bookings')
    if cursor.fetchone()[0] > 50:
        return

    fake = Faker('en_IN')
    cursor.execute('SELECT id, capacity FROM restaurants')
    restaurants = cursor.fetchall()

    rows = []
    now = datetime.utcnow()
    for restaurant_id, capacity in restaurants[:80]:
        for _ in range(random.randint(1, 4)):
            slot = now + timedelta(hours=random.randint(-48, 96))
            rows.append((
                restaurant_id,
                fake.name(),
                slot.isoformat(timespec='minutes'),
                random.randint(1, min(8, max(2, capacity // 6))),
                'seed'
            ))

    cursor.executemany(
        'INSERT INTO bookings (restaurant_id, customer_name, time, party_size, source) VALUES (?,?,?,?,?)',
        rows
    )
    if rows:
        print("Seeded bookings.")

if __name__ == "__main__":
    init_db()
