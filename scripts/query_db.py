import sqlite3

DB_FILE = r"data/moneki.db"

conn = sqlite3.connect(DB_FILE)

sql = """
SELECT
    p.product_category,

    SUM(s.amount) AS total_sales,

    SUM(s.qty) AS total_qty,

    COUNT(DISTINCT s.order_id) AS total_orders

FROM sales s

JOIN products p
    ON s.product_id = p.product_id

GROUP BY
    p.product_category

ORDER BY
    total_sales DESC
"""

rows = conn.execute(sql).fetchall()

print("=== Category Performance ===")

for row in rows:
    print(row)

conn.close()