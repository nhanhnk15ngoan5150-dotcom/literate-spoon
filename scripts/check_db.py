import sqlite3

DB_FILE = "data/moneki.db"

conn = sqlite3.connect(DB_FILE)

print("=== Tables ===")

tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

for table in tables:
    print(table)

print("\n=== sales schema ===")

columns = conn.execute(
    "PRAGMA table_info(sales)"
).fetchall()

for column in columns:
    print(column)

conn.close()