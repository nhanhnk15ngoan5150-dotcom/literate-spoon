from pathlib import Path
import sqlite3

import pandas as pd


# ============================================================
# Project paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DB_FILE = PROJECT_ROOT / "data" / "moneki.db"

SALES_FILE = PROCESSED_DIR / "sales.csv"
STORES_FILE = PROCESSED_DIR / "stores.csv"
PRODUCTS_FILE = PROCESSED_DIR / "products.csv"


# ============================================================
# Load processed data
# ============================================================

def load_processed_data():
    """Load cleaned data from the processed layer."""

    sales = pd.read_csv(SALES_FILE)
    stores = pd.read_csv(STORES_FILE)
    products = pd.read_csv(PRODUCTS_FILE)

    return sales, stores, products


# ============================================================
# Create database
# ============================================================

def create_database():
    """Create SQLite database and import processed data."""

    print("=" * 60)
    print("Moneki SQLite database initialization")
    print("=" * 60)

    print("\nLoading processed data...")

    sales, stores, products = load_processed_data()

    print(f"sales: {len(sales)} rows")
    print(f"stores: {len(stores)} rows")
    print(f"products: {len(products)} rows")

    # --------------------------------------------------------
    # Connect to SQLite
    # --------------------------------------------------------

    DB_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(DB_FILE)

    try:
        cursor = connection.cursor()

        # Enable foreign key constraints.
        cursor.execute("PRAGMA foreign_keys = ON;")

        # ----------------------------------------------------
        # Drop existing tables
        # ----------------------------------------------------

        cursor.execute("DROP TABLE IF EXISTS sales")
        cursor.execute("DROP TABLE IF EXISTS products")
        cursor.execute("DROP TABLE IF EXISTS stores")

        # ----------------------------------------------------
        # stores
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE stores (
                store_id TEXT PRIMARY KEY,
                store_name TEXT NOT NULL,
                category TEXT,
                district TEXT
            )
            """
        )

        # ----------------------------------------------------
        # products
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT NOT NULL,
                product_category TEXT,
                unit_price REAL
            )
            """
        )

        # ----------------------------------------------------
        # sales
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                date TEXT NOT NULL,
                store_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                qty INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment TEXT,
                FOREIGN KEY (store_id)
                    REFERENCES stores(store_id),
                FOREIGN KEY (product_id)
                    REFERENCES products(product_id)
            )
            """
        )

        # ----------------------------------------------------
        # Insert dimension tables
        # ----------------------------------------------------

        stores.to_sql(
            "stores",
            connection,
            if_exists="append",
            index=False,
        )

        products.to_sql(
            "products",
            connection,
            if_exists="append",
            index=False,
        )

        # ----------------------------------------------------
        # Insert sales
        # ----------------------------------------------------

        sales.to_sql(
            "sales",
            connection,
            if_exists="append",
            index=False,
        )

        # ----------------------------------------------------
        # Indexes
        # ----------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX idx_sales_date
            ON sales(date)
            """
        )

        cursor.execute(
            """
            CREATE INDEX idx_sales_store
            ON sales(store_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX idx_sales_product
            ON sales(product_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX idx_sales_order
            ON sales(order_id)
            """
        )

        connection.commit()

        print("\nDatabase created successfully.")
        print(f"database: {DB_FILE}")

    finally:
        connection.close()


# ============================================================
# Verification
# ============================================================

def verify_database():
    """Verify imported row counts and basic relationships."""

    print("\nVerifying database...")

    connection = sqlite3.connect(DB_FILE)

    try:
        cursor = connection.cursor()

        for table in ["stores", "products", "sales"]:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table}"
            )

            count = cursor.fetchone()[0]

            print(
                f"{table}: {count} rows"
            )

        # Check invalid foreign keys.
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM sales s
            LEFT JOIN stores st
                ON s.store_id = st.store_id
            WHERE st.store_id IS NULL
            """
        )

        invalid_stores = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM sales s
            LEFT JOIN products p
                ON s.product_id = p.product_id
            WHERE p.product_id IS NULL
            """
        )

        invalid_products = cursor.fetchone()[0]

        print(
            f"invalid store references: {invalid_stores}"
        )

        print(
            f"invalid product references: {invalid_products}"
        )

    finally:
        connection.close()


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    create_database()
    verify_database()

    print("\n" + "=" * 60)
    print("SQLite initialization completed.")
    print("=" * 60)