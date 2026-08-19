from pathlib import Path
import json
import re
from datetime import datetime

import pandas as pd


# ============================================================
# 项目路径
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RAW_DIR = PROJECT_ROOT / "data" / "raw"
DOCS_DIR = PROJECT_ROOT / "docs"

SALES_FILE = RAW_DIR / "sales.csv"
STORES_FILE = RAW_DIR / "stores.csv"
PRODUCTS_FILE = RAW_DIR / "products.csv"

REPORT_FILE = DOCS_DIR / "audit_report.json"


# ============================================================
# 基础工具
# ============================================================

def load_csv(path: Path) -> pd.DataFrame:
    """只读加载 CSV，不修改源文件。"""
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    return pd.read_csv(path)


def get_column(df: pd.DataFrame, column_name: str):
    """安全获取列。"""
    if column_name not in df.columns:
        return None
    return df[column_name]


def normalize_dtype(dtype) -> str:
    """
    将 pandas dtype 转换为更适合审计报告阅读的类型。
    object/string -> str
    """
    dtype_str = str(dtype)

    if dtype_str in ("object", "string"):
        return "str"

    return dtype_str


def basic_info(df: pd.DataFrame) -> dict:
    """基础数据结构信息。"""
    return {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": [str(c) for c in df.columns],
        "dtypes": {
            str(column): normalize_dtype(dtype)
            for column, dtype in df.dtypes.items()
        },
    }


def missing_value_report(df: pd.DataFrame) -> dict:
    """统计每列缺失值。"""
    result = {}

    total = len(df)

    for column in df.columns:
        missing_count = int(df[column].isna().sum())

        missing_rate = (
            round(missing_count / total, 6)
            if total > 0
            else 0.0
        )

        result[str(column)] = {
            "missing_count": missing_count,
            "missing_rate": missing_rate,
        }

    return result


def duplicate_row_count(df: pd.DataFrame) -> int:
    """统计完全重复的数据行数量。"""
    return int(df.duplicated(keep=False).sum())


def primary_key_duplicate_count(
    df: pd.DataFrame,
    pk_col: str
) -> int:
    """统计主键重复涉及的行数量。"""
    if pk_col not in df.columns:
        return 0

    duplicated = df[pk_col].duplicated(keep=False)

    return int(duplicated.sum())


# ============================================================
# sales.csv：order_id
# ============================================================

def audit_order_id(df: pd.DataFrame) -> dict:
    """审计订单号唯一性。"""

    if "order_id" not in df.columns:
        return {
            "exists": False
        }

    series = df["order_id"]

    total_rows = len(df)
    unique_count = int(series.nunique(dropna=True))

    duplicated_mask = series.duplicated(keep=False)

    duplicate_row_count_value = int(duplicated_mask.sum())

    duplicate_order_id_values = int(
        series[duplicated_mask].nunique(dropna=True)
    )

    return {
        "exists": True,
        "total_rows": total_rows,
        "unique_order_ids": unique_count,

        # 有多少个不同的 order_id 出现重复
        "duplicate_order_id_value_count": duplicate_order_id_values,

        # 这些重复 order_id 一共涉及多少行
        "duplicate_order_id_row_count": duplicate_row_count_value,
    }


# ============================================================
# 日期审计
# ============================================================

def _try_parse_single_date(value):
    """
    支持多种日期格式：

    2026-05-01
    2026/05/01
    24-07-2026
    21-06-2026

    返回：
        datetime
        或 None
    """

    if pd.isna(value):
        return None

    text = str(value).strip()

    if not text:
        return None

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y.%m.%d",
        "%d.%m.%Y",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def audit_dates(df: pd.DataFrame) -> dict:
    """日期格式、可解析性及日期范围审计。"""

    if "date" not in df.columns:
        return {
            "exists": False
        }

    raw_dates = df["date"]

    parsed_dates = raw_dates.apply(_try_parse_single_date)

    unparseable_count = int(parsed_dates.isna().sum())

    # 日期分隔符统计
    separator_stats = {
        "-": 0,
        "/": 0,
        ".": 0,
        "other": 0,
    }

    for value in raw_dates.dropna():
        text = str(value).strip()

        if "-" in text:
            separator_stats["-"] += 1
        elif "/" in text:
            separator_stats["/"] += 1
        elif "." in text:
            separator_stats["."] += 1
        else:
            separator_stats["other"] += 1

    valid_dates = [
        value for value in parsed_dates
        if value is not None
    ]

    if valid_dates:
        min_date = min(valid_dates).strftime("%Y-%m-%d")
        max_date = max(valid_dates).strftime("%Y-%m-%d")
    else:
        min_date = None
        max_date = None

    return {
        "exists": True,
        "total_count": int(len(raw_dates)),
        "unparseable_count": unparseable_count,
        "date_format_separator_stats": separator_stats,
        "min_date": min_date,
        "max_date": max_date,
    }


# ============================================================
# 外键审计
# ============================================================

def audit_foreign_key(
    sales_df: pd.DataFrame,
    ref_df: pd.DataFrame,
    fk_col: str,
    ref_pk_col: str
) -> dict:
    """检查 sales 中的外键是否存在于维表主键。"""

    if fk_col not in sales_df.columns:
        return {
            "exists": False
        }

    if ref_pk_col not in ref_df.columns:
        return {
            "exists": True,
            "reference_column_exists": False
        }

    valid_values = set(
        ref_df[ref_pk_col]
        .dropna()
        .astype(str)
        .str.strip()
    )

    values = (
        sales_df[fk_col]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    invalid_mask = ~values.isin(valid_values)

    invalid_count = int(invalid_mask.sum())

    invalid_values = (
        values[invalid_mask]
        .value_counts()
        .to_dict()
    )

    return {
        "exists": True,
        "reference_column_exists": True,
        "invalid_count": invalid_count,
        "invalid_values": {
            str(k): int(v)
            for k, v in invalid_values.items()
        },
    }


# ============================================================
# qty 审计
# ============================================================

def audit_qty(df: pd.DataFrame) -> dict:
    """数量字段审计。"""

    if "qty" not in df.columns:
        return {
            "exists": False
        }

    raw = df["qty"]

    numeric = pd.to_numeric(raw, errors="coerce")

    missing_count = int(raw.isna().sum())

    non_numeric_count = int(
        numeric.isna().sum() - missing_count
    )

    less_or_equal_zero_count = int(
        (numeric <= 0).fillna(False).sum()
    )

    return {
        "exists": True,
        "missing_count": missing_count,
        "non_numeric_count": non_numeric_count,
        "less_or_equal_zero_count": less_or_equal_zero_count,
    }


# ============================================================
# amount 审计
# ============================================================

def audit_amount(df: pd.DataFrame) -> dict:
    """金额字段审计。

    注意：
    所有清洗均在副本 Series 上进行，
    不修改原始 DataFrame。
    """

    if "amount" not in df.columns:
        return {
            "exists": False
        }

    raw = df["amount"]

    missing_count = int(raw.isna().sum())

    # 转成字符串副本
    text = raw.astype("string")

    # 统计货币符号
    currency_symbol_count = int(
        text.str.contains(
            r"[¥￥]",
            regex=True,
            na=False
        ).sum()
    )

    # 清除货币符号和空格
    cleaned = (
        text
        .str.replace("¥", "", regex=False)
        .str.replace("￥", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.strip()
    )

    numeric = pd.to_numeric(
        cleaned,
        errors="coerce"
    )

    non_numeric_mask = (
        numeric.isna()
        & raw.notna()
    )

    non_numeric_count = int(
        non_numeric_mask.sum()
    )

    less_or_equal_zero_count = int(
        (numeric <= 0).fillna(False).sum()
    )

    negative_count = int(
        (numeric < 0).fillna(False).sum()
    )

    zero_count = int(
        (numeric == 0).fillna(False).sum()
    )

    return {
        "exists": True,
        "missing_count": missing_count,
        "currency_symbol_count": currency_symbol_count,
        "non_numeric_count": non_numeric_count,
        "less_or_equal_zero_count": less_or_equal_zero_count,
        "negative_count": negative_count,
        "zero_count": zero_count,
    }


# ============================================================
# sales 总审计
# ============================================================

def audit_sales(
    sales_df: pd.DataFrame,
    stores_df: pd.DataFrame,
    products_df: pd.DataFrame
) -> dict:

    return {
        "basic_info": basic_info(sales_df),

        "missing_values": missing_value_report(
            sales_df
        ),

        "duplicate_rows": duplicate_row_count(
            sales_df
        ),

        "order_id": audit_order_id(
            sales_df
        ),

        "dates": audit_dates(
            sales_df
        ),

        "foreign_keys": {
            "store_id": audit_foreign_key(
                sales_df,
                stores_df,
                "store_id",
                "store_id"
            ),

            "product_id": audit_foreign_key(
                sales_df,
                products_df,
                "product_id",
                "product_id"
            ),
        },

        "qty": audit_qty(
            sales_df
        ),

        "amount": audit_amount(
            sales_df
        ),
    }


# ============================================================
# stores / products 维度表审计
# ============================================================

def audit_dimension_table(
    df: pd.DataFrame,
    pk_col: str
) -> dict:

    return {
        "basic_info": basic_info(df),

        "missing_values": missing_value_report(
            df
        ),

        "duplicate_rows": duplicate_row_count(
            df
        ),

        "primary_key": {
            "column": pk_col,
            "duplicate_count": primary_key_duplicate_count(
                df,
                pk_col
            ),
        },
    }


# ============================================================
# 保存报告
# ============================================================

def save_report(
    report: dict,
    output_path: Path
):
    """保存 JSON 审计报告。"""

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with output_path.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# 主程序
# ============================================================

def main():

    print("开始数据质量审计...")
    print(f"项目根目录: {PROJECT_ROOT}")

    print("\n读取 sales.csv...")
    sales_df = load_csv(SALES_FILE)

    print("读取 stores.csv...")
    stores_df = load_csv(STORES_FILE)

    print("读取 products.csv...")
    products_df = load_csv(PRODUCTS_FILE)

    print("\n开始审计...")

    report = {
        "project": "moneki-fullstack-assignment",

        "audit_version": "1.1",

        "source": {
            "sales": str(
                SALES_FILE.relative_to(PROJECT_ROOT)
            ),
            "stores": str(
                STORES_FILE.relative_to(PROJECT_ROOT)
            ),
            "products": str(
                PRODUCTS_FILE.relative_to(PROJECT_ROOT)
            ),
        },

        "data_integrity": {
            "raw_files_modified": False,
            "note": (
                "审计过程仅读取 data/raw 中的 CSV，"
                "日期、金额、数量转换均在内存副本上完成，"
                "不会修改原始数据。"
            ),
        },

        "sales": audit_sales(
            sales_df,
            stores_df,
            products_df
        ),

        "stores": audit_dimension_table(
            stores_df,
            "store_id"
        ),

        "products": audit_dimension_table(
            products_df,
            "product_id"
        ),
    }

    save_report(
        report,
        REPORT_FILE
    )

    print("\n审计完成！")
    print(f"报告已生成: {REPORT_FILE}")


if __name__ == "__main__":
    try:
        main()

    except FileNotFoundError as e:
        print(f"\n错误：文件不存在")
        print(e)

    except pd.errors.EmptyDataError as e:
        print("\n错误：CSV 文件为空")
        print(e)

    except Exception as e:
        print("\n审计过程中发生错误：")
        print(type(e).__name__, e)
        raise