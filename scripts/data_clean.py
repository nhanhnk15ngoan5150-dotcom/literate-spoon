from pathlib import Path

import pandas as pd


# ============================================================
# Project paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


SALES_FILE = RAW_DIR / "sales.csv"
STORES_FILE = RAW_DIR / "stores.csv"
PRODUCTS_FILE = RAW_DIR / "products.csv"


# ============================================================
# Helpers
# ============================================================

def load_csv(path: Path) -> pd.DataFrame:
    """Read CSV without modifying the source file."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    return pd.read_csv(path)


def normalize_id(series: pd.Series) -> pd.Series:
    """Normalize ID values by trimming spaces and upper-casing."""
    return (
        series
        .astype("string")
        .str.strip()
        .str.upper()
    )


def normalize_date(series: pd.Series) -> pd.Series:
    """
    Normalize supported date formats to YYYY-MM-DD.

    Supported formats:
    - YYYY-MM-DD
    - YYYY/MM/DD
    - YYYY.MM.DD
    - DD-MM-YYYY
    - DD/MM/YYYY
    - DD.MM.YYYY
    """

    def parse_one(value):
        if pd.isna(value):
            return pd.NaT

        text = str(value).strip()

        if not text:
            return pd.NaT

        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
        ]

        for fmt in formats:
            try:
                return pd.to_datetime(
                    text,
                    format=fmt,
                )
            except (ValueError, TypeError):
                continue

        return pd.NaT

    return series.apply(parse_one)


def normalize_amount(series: pd.Series) -> pd.Series:
    """
    Convert amount values to numeric.

    Handles currency symbols and thousands separators.
    """
    text = (
        series
        .astype("string")
        .str.strip()
        .str.replace("¥", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    return pd.to_numeric(
        text,
        errors="coerce",
    )


# ============================================================
# Sales cleaning
# ============================================================

def clean_sales(
    sales: pd.DataFrame,
    stores: pd.DataFrame,
    products: pd.DataFrame,
) -> pd.DataFrame:

    result = sales.copy()

    original_rows = len(result)

    # --------------------------------------------------------
    # 1. Remove completely duplicated rows
    # --------------------------------------------------------

    result = result.drop_duplicates()

    print(
        f"[sales] duplicate rows removed: "
        f"{original_rows - len(result)}"
    )

    # --------------------------------------------------------
    # 2. Normalize IDs
    # --------------------------------------------------------

    result["order_id"] = normalize_id(result["order_id"])
    result["store_id"] = normalize_id(result["store_id"])
    result["product_id"] = normalize_id(result["product_id"])

    # --------------------------------------------------------
    # 3. Normalize dates
    # --------------------------------------------------------

    result["date"] = normalize_date(result["date"])

    invalid_dates = result["date"].isna().sum()

    if invalid_dates:
        print(
            f"[sales] invalid dates removed: "
            f"{invalid_dates}"
        )

    result = result[result["date"].notna()]

    # --------------------------------------------------------
    # 4. Normalize quantity
    # --------------------------------------------------------

    result["qty"] = pd.to_numeric(
        result["qty"],
        errors="coerce",
    )

    invalid_qty = (
        result["qty"].isna()
        | (result["qty"] <= 0)
    ).sum()

    print(
        f"[sales] invalid qty removed: "
        f"{invalid_qty}"
    )

    result = result[
        result["qty"].notna()
        & (result["qty"] > 0)
    ]

    result["qty"] = result["qty"].astype(int)

    # --------------------------------------------------------
    # 5. Normalize amount
    # --------------------------------------------------------

    result["amount"] = normalize_amount(
        result["amount"]
    )

    invalid_amount = (
        result["amount"].isna()
        | (result["amount"] <= 0)
    ).sum()

    print(
        f"[sales] invalid amount removed: "
        f"{invalid_amount}"
    )

    result = result[
        result["amount"].notna()
        & (result["amount"] > 0)
    ]

    # --------------------------------------------------------
    # 6. Validate store foreign key
    # --------------------------------------------------------

    valid_store_ids = set(
        stores["store_id"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    invalid_store_mask = ~result["store_id"].isin(
        valid_store_ids
    )

    invalid_store_count = int(
        invalid_store_mask.sum()
    )

    print(
        f"[sales] invalid store_id removed: "
        f"{invalid_store_count}"
    )

    result = result[
        ~invalid_store_mask
    ]

    # --------------------------------------------------------
    # 7. Validate product foreign key
    # --------------------------------------------------------

    valid_product_ids = set(
        products["product_id"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    invalid_product_mask = ~result["product_id"].isin(
        valid_product_ids
    )

    invalid_product_count = int(
        invalid_product_mask.sum()
    )

    print(
        f"[sales] invalid product_id removed: "
        f"{invalid_product_count}"
    )

    result = result[
        ~invalid_product_mask
    ]

    # --------------------------------------------------------
    # 8. Final formatting
    # --------------------------------------------------------

    result["date"] = result["date"].dt.strftime(
        "%Y-%m-%d"
    )

    result["amount"] = result["amount"].round(2)

    # --------------------------------------------------------
    # 9. Final duplicate check
    #
    # Some rows may become identical after normalization.
    # Remove duplicates only after all cleaning operations.
    # --------------------------------------------------------

    before_final_dedup = len(result)

    result = result.drop_duplicates()

    final_duplicates_removed = (
        before_final_dedup - len(result)
    )

    print(
        f"[sales] final duplicates removed: "
        f"{final_duplicates_removed}"
    )

    # Keep original column order.
    result = result[
        [
            "order_id",
            "date",
            "store_id",
            "product_id",
            "qty",
            "amount",
            "payment",
        ]
    ]

    print(
        f"[sales] rows: "
        f"{original_rows} -> {len(result)}"
    )

    return result


# ============================================================
# Dimension tables
# ============================================================

def clean_stores(
    stores: pd.DataFrame,
) -> pd.DataFrame:

    result = stores.copy()

    result["store_id"] = normalize_id(
        result["store_id"]
    )

    result = result.drop_duplicates(
        subset=["store_id"]
    )

    return result


def clean_products(
    products: pd.DataFrame,
) -> pd.DataFrame:

    result = products.copy()

    result["product_id"] = normalize_id(
        result["product_id"]
    )

    result["unit_price"] = pd.to_numeric(
        products["unit_price"],
        errors="coerce",
    )

    result = result.drop_duplicates(
        subset=["product_id"]
    )

    return result


# ============================================================
# Save
# ============================================================

def save_csv(
    df: pd.DataFrame,
    path: Path,
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        f"saved: {path}"
    )


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)
    print("Moneki data cleaning")
    print("=" * 60)

    print("\nLoading raw data...")

    sales = load_csv(SALES_FILE)
    stores = load_csv(STORES_FILE)
    products = load_csv(PRODUCTS_FILE)

    print(
        f"sales: {len(sales)} rows"
    )
    print(
        f"stores: {len(stores)} rows"
    )
    print(
        f"products: {len(products)} rows"
    )

    # --------------------------------------------------------
    # Clean dimension tables first
    # --------------------------------------------------------

    stores_clean = clean_stores(stores)
    products_clean = clean_products(products)

    # --------------------------------------------------------
    # Clean sales
    # --------------------------------------------------------

    sales_clean = clean_sales(
        sales,
        stores_clean,
        products_clean,
    )

    # --------------------------------------------------------
    # Save processed data
    # --------------------------------------------------------

    print("\nSaving processed data...")

    save_csv(
        sales_clean,
        PROCESSED_DIR / "sales.csv",
    )

    save_csv(
        stores_clean,
        PROCESSED_DIR / "stores.csv",
    )

    save_csv(
        products_clean,
        PROCESSED_DIR / "products.csv",
    )

    print("\nCleaning completed.")
    print("=" * 60)


if __name__ == "__main__":
    main()