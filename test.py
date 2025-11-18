import sqlite3
import pandas as pd

conn = sqlite3.connect('data/restaurants.db')
df = pd.read_sql_query("SELECT * FROM restaurants LIMIT 5", conn)
print(df)
conn.close()