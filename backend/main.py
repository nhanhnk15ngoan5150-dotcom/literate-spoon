from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# Project paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "raw"

SALES_FILE = DATA_DIR / "sales.csv"
STORES_FILE = DATA_DIR / "stores.csv"
PRODUCTS_FILE = DATA_DIR / "products.csv"


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="Moneki Sales Dashboard API",
    version="1.0.0",
    description="Sales dashboard backend API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Data loading
# ============================================================

def load_data():
    """Load raw CSV files in read-only mode."""

    if not SALES_FILE.exists():
        raise FileNotFoundError(f"Sales file not found: {SALES_FILE}")

    if not STORES_FILE.exists():
        raise FileNotFoundError(f"Stores file not found: {STORES_FILE}")

    if not PRODUCTS_FILE.exists():
        raise FileNotFoundError(f"Products file not found: {PRODUCTS_FILE}")

    sales = pd.read_csv(SALES_FILE)
    stores = pd.read_csv(STORES_FILE)
    products = pd.read_csv(PRODUCTS_FILE)

    return sales, stores, products


# ============================================================
# Date handling
# ============================================================

def parse_single_date(value):
    """
    Parse one date value.

    The source data contains mixed separators such as:
    2026-05-01
    2026/05/01

    We explicitly normalize separators before parsing so that
    pandas does not incorrectly infer the date format.
    """

    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    if not text:
        return pd.NaT

    # Normalize separators.
    text = text.replace("/", "-").replace(".", "-")

    # Explicitly parse YYYY-MM-DD.
    return pd.to_datetime(
        text,
        format="%Y-%m-%d",
        errors="coerce",
    )


def parse_dates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse date column on a copy.
    Original DataFrame is not modified.
    """

    result = df.copy()

    result["parsed_date"] = result["date"].apply(parse_single_date)

    return result


def parse_query_date(value: Optional[str]):
    """Parse API query date using YYYY-MM-DD."""

    if not value:
        return None

    parsed = pd.to_datetime(
        value,
        format="%Y-%m-%d",
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed


# ============================================================
# Amount handling
# ============================================================

def parse_amount(series: pd.Series) -> pd.Series:
    """
    Convert amount values into numeric values.

    Supports values such as:
    100
    100.5
    ¥100
    ￥100
    1,000.50

    Conversion is performed on a copy.
    """

    result = series.astype("string").str.strip()

    result = (
        result
        .str.replace("¥", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    return pd.to_numeric(
        result,
        errors="coerce",
    )


# ============================================================
# Date filter helper
# ============================================================

def filter_by_date(
    sales: pd.DataFrame,
    start_date: Optional[str],
    end_date: Optional[str],
):
    """Filter sales data by date."""

    result = sales

    if start_date:
        start = parse_query_date(start_date)

        if start is None:
            raise ValueError(
                f"Invalid start_date: {start_date}. "
                f"Expected format: YYYY-MM-DD"
            )

        result = result[result["parsed_date"] >= start]

    if end_date:
        end = parse_query_date(end_date)

        if end is None:
            raise ValueError(
                f"Invalid end_date: {end_date}. "
                f"Expected format: YYYY-MM-DD"
            )

        result = result[result["parsed_date"] <= end]

    return result


# ============================================================
# Health
# ============================================================

@app.get("/")
def root():
    return {
        "name": "Moneki Sales Dashboard API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "sales-dashboard-api",
    }


# ============================================================
# Dataset metadata
# ============================================================

@app.get("/api/meta")
def get_meta():
    """Return basic dataset information."""

    sales, stores, products = load_data()

    sales = parse_dates(sales)

    valid_dates = sales["parsed_date"].dropna()

    if valid_dates.empty:
        min_date = None
        max_date = None
    else:
        min_date = valid_dates.min().strftime("%Y-%m-%d")
        max_date = valid_dates.max().strftime("%Y-%m-%d")

    return {
        "sales_rows": int(len(sales)),
        "store_count": int(len(stores)),
        "product_count": int(len(products)),
        "min_date": min_date,
        "max_date": max_date,
    }


# ============================================================
# Daily sales
# ============================================================

@app.get("/api/daily-sales")
def get_daily_sales(
    start_date: Optional[str] = Query(
        default=None,
        description="Start date, e.g. 2026-05-01",
    ),
    end_date: Optional[str] = Query(
        default=None,
        description="End date, e.g. 2026-07-31",
    ),
):
    """
    Return daily:
    - revenue
    - order count
    - average order value
    """

    sales, _, _ = load_data()

    sales = parse_dates(sales)

    try:
        sales = filter_by_date(
            sales,
            start_date,
            end_date,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    sales["numeric_amount"] = parse_amount(
        sales["amount"]
    )

    daily = (
        sales
        .groupby("parsed_date")
        .agg(
            revenue=("numeric_amount", "sum"),
            order_count=("order_id", "nunique"),
        )
        .reset_index()
    )

    daily["average_order_value"] = (
        daily["revenue"]
        / daily["order_count"].replace(0, pd.NA)
    )

    daily["date"] = daily["parsed_date"].dt.strftime(
        "%Y-%m-%d"
    )

    daily = daily[
        [
            "date",
            "revenue",
            "order_count",
            "average_order_value",
        ]
    ]

    daily = daily.fillna(0)

    records = daily.to_dict(
        orient="records"
    )

    for row in records:
        row["revenue"] = round(
            float(row["revenue"]),
            2,
        )
        row["order_count"] = int(
            row["order_count"]
        )
        row["average_order_value"] = round(
            float(row["average_order_value"]),
            2,
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_days": len(records),
        "data": records,
    }


# ============================================================
# Top products
# ============================================================

@app.get("/api/top-products")
def get_top_products(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
):
    """Return top products by revenue."""

    sales, _, products = load_data()

    sales = parse_dates(sales)

    try:
        sales = filter_by_date(
            sales,
            start_date,
            end_date,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    sales["numeric_amount"] = parse_amount(
        sales["amount"]
    )

    result = (
        sales
        .groupby("product_id")
        .agg(
            revenue=("numeric_amount", "sum"),
            qty=("qty", "sum"),
            order_count=("order_id", "nunique"),
        )
        .reset_index()
    )

    result = result.merge(
        products[
            [
                "product_id",
                "product_name",
                "product_category",
            ]
        ],
        on="product_id",
        how="left",
    )

    result = (
        result
        .sort_values(
            "revenue",
            ascending=False,
        )
        .head(limit)
    )

    records = result.to_dict(
        orient="records"
    )

    for row in records:
        row["revenue"] = round(
            float(row["revenue"]),
            2,
        )
        row["qty"] = int(row["qty"])
        row["order_count"] = int(
            row["order_count"]
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "data": records,
    }


# ============================================================
# Store sales
# ============================================================

@app.get("/api/store-sales")
def get_store_sales(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    """Return sales statistics by store."""

    sales, stores, _ = load_data()

    sales = parse_dates(sales)

    try:
        sales = filter_by_date(
            sales,
            start_date,
            end_date,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    sales["numeric_amount"] = parse_amount(
        sales["amount"]
    )

    result = (
        sales
        .groupby("store_id")
        .agg(
            revenue=("numeric_amount", "sum"),
            order_count=("order_id", "nunique"),
            qty=("qty", "sum"),
        )
        .reset_index()
    )

    result = result.merge(
        stores,
        on="store_id",
        how="left",
    )

    result["average_order_value"] = (
        result["revenue"]
        / result["order_count"].replace(
            0,
            pd.NA,
        )
    )

    result = result.sort_values(
        "revenue",
        ascending=False,
    )

    result = result.fillna("")

    records = result.to_dict(
        orient="records"
    )

    for row in records:
        row["revenue"] = round(
            float(row["revenue"]),
            2,
        )
        row["order_count"] = int(
            row["order_count"]
        )
        row["qty"] = int(row["qty"])
        row["average_order_value"] = round(
            float(row["average_order_value"]),
            2,
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "data": records,
    }


# ============================================================
# Category sales
# ============================================================

@app.get("/api/category-sales")
def get_category_sales(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    """Return sales statistics by product category."""

    sales, _, products = load_data()

    sales = parse_dates(sales)

    try:
        sales = filter_by_date(
            sales,
            start_date,
            end_date,
        )
    except ValueError as exc:
        return {"error": str(exc)}

    sales["numeric_amount"] = parse_amount(
        sales["amount"]
    )

    result = sales.merge(
        products[
            [
                "product_id",
                "product_category",
            ]
        ],
        on="product_id",
        how="left",
    )

    result = (
        result
        .groupby(
            "product_category",
            dropna=False,
        )
        .agg(
            revenue=("numeric_amount", "sum"),
            qty=("qty", "sum"),
            order_count=("order_id", "nunique"),
        )
        .reset_index()
        .sort_values(
            "revenue",
            ascending=False,
        )
    )

    result["product_category"] = (
        result["product_category"]
        .fillna("Unknown")
    )

    records = result.to_dict(
        orient="records"
    )

    for row in records:
        row["revenue"] = round(
            float(row["revenue"]),
            2,
        )
        row["qty"] = int(row["qty"])
        row["order_count"] = int(
            row["order_count"]
        )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "data": records,
    }


# ============================================================
# Application entry
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )