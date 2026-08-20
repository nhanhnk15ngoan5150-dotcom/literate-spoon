from pathlib import Path
from typing import Optional
import json
import sqlite3
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

import pandas as pd

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ============================================================
# Project paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data" / "processed"

SALES_FILE = DATA_DIR / "sales.csv"
STORES_FILE = DATA_DIR / "stores.csv"
PRODUCTS_FILE = DATA_DIR / "products.csv"

DB_FILE = BASE_DIR / "data" / "moneki.db"


# ============================================================
# Ollama / Qwen
# ============================================================

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b-instruct"


# ============================================================
# FastAPI
# ============================================================

app = FastAPI(
    title="Moneki Sales Dashboard API",
    version="2.3.0",
    description="Moneki Sales Dashboard + Qwen Agent",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Conversation Memory
# ============================================================

conversation_memory = {}


def empty_context():
    return {
        "last_question": "",
        "last_tool": "",
        "last_arguments": {},
        "last_result": [],
        "history": [],
    }


def get_conversation_context(conversation_id: str) -> dict:
    return conversation_memory.get(
        conversation_id,
        empty_context(),
    )


def save_conversation_context(
    conversation_id: str,
    question: str,
    tool: str,
    arguments: dict,
    result: list,
):
    old_context = conversation_memory.get(
        conversation_id,
        empty_context(),
    )

    history = old_context.get("history", [])

    history.append(
        {
            "question": question,
            "tool": tool,
            "arguments": arguments,
            "result": result,
        }
    )

    history = history[-20:]

    conversation_memory[conversation_id] = {
        "last_question": question,
        "last_tool": tool,
        "last_arguments": arguments,
        "last_result": result,
        "history": history,
    }


# ============================================================
# SQLite
# ============================================================

def query_db(sql: str, params=()):
    if not DB_FILE.exists():
        raise FileNotFoundError(
            f"SQLite database not found: {DB_FILE}"
        )

    normalized_sql = sql.strip().lower()

    if not (
        normalized_sql.startswith("select")
        or normalized_sql.startswith("with")
    ):
        raise ValueError(
            "Only read-only SELECT queries are allowed."
        )

    conn = sqlite3.connect(DB_FILE)

    try:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            sql,
            params,
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# ============================================================
# Database Schema
# ============================================================

def get_database_schema():
    return """
数据库包含以下主要表：

sales
- date: 销售日期
- amount: 销售金额
- qty: 销售数量
- order_id: 订单ID
- product_id: 商品ID
- store_id: 门店ID

products
- product_id: 商品ID
- product_name: 商品名称
- product_category: 商品分类

stores
- store_id: 门店ID
- store_name: 门店名称

表关系：

sales.product_id = products.product_id
sales.store_id = stores.store_id

业务指标：

销售额：
SUM(sales.amount)

销量：
SUM(sales.qty)

订单数：
COUNT(DISTINCT sales.order_id)

客单价：
SUM(sales.amount) / COUNT(DISTINCT sales.order_id)
"""


# ============================================================
# Ollama / Qwen
# ============================================================

def ask_qwen(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
        },
    }

    request = Request(
        OLLAMA_URL,
        data=json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=120,
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

            return result.get(
                "response",
                "",
            ).strip()

    except HTTPError as exc:
        raise RuntimeError(
            f"Ollama HTTP error: {exc.code}"
        )

    except URLError:
        raise RuntimeError(
            "无法连接 Ollama，请确认 Ollama 正在运行。"
        )


# ============================================================
# Request models
# ============================================================

class AskRequest(BaseModel):
    question: str
    conversation_id: str = "default"


# ============================================================
# Tools
# ============================================================

TOOLS = {

    "product_rank": {
        "description": "查询商品销售额排名。",
        "arguments": [
            "order",
            "limit",
            "category",
            "start_date",
            "end_date",
        ],
    },

    "product_revenue": {
        "description": "查询指定商品销售额。",
        "arguments": [
            "product_name",
            "start_date",
            "end_date",
        ],
    },

    "product_quantity": {
        "description": "查询商品销量或销量排名。",
        "arguments": [
            "product_name",
            "category",
            "order",
            "limit",
            "start_date",
            "end_date",
        ],
    },

    "product_orders": {
        "description": "查询指定商品订单数量。",
        "arguments": [
            "product_name",
            "start_date",
            "end_date",
        ],
    },

    "product_monthly_sales": {
        "description": "查询指定商品每月销售情况。",
        "arguments": [
            "product_name",
            "start_date",
            "end_date",
        ],
    },

    "product_daily_sales": {
        "description": "查询指定商品每日销售情况。",
        "arguments": [
            "product_name",
            "start_date",
            "end_date",
        ],
    },

    "category_rank": {
        "description": "查询商品分类销售额排名。",
        "arguments": [
            "order",
            "limit",
            "start_date",
            "end_date",
        ],
    },

    "category_revenue": {
        "description": "查询指定商品分类销售额。",
        "arguments": [
            "category",
            "start_date",
            "end_date",
        ],
    },

    "store_rank": {
        "description": "查询门店销售额排名。",
        "arguments": [
            "order",
            "limit",
            "start_date",
            "end_date",
        ],
    },

    "store_revenue": {
        "description": "查询指定门店销售额。",
        "arguments": [
            "store_name",
            "start_date",
            "end_date",
        ],
    },

    "daily_sales": {
        "description": "查询每日销售额、订单数和客单价。",
        "arguments": [
            "start_date",
            "end_date",
        ],
    },

    "monthly_sales": {
        "description": "查询每月销售额、订单数、销量和客单价。",
        "arguments": [
            "start_date",
            "end_date",
        ],
    },

    "aov_trend": {
        "description": "查询客单价趋势。",
        "arguments": [
            "start_date",
            "end_date",
        ],
    },

    "dataset_summary": {
        "description": "查询数据集基本信息。",
        "arguments": [],
    },

    "database_fallback": {
        "description": "现有专业Tool无法覆盖时查询数据库。",
        "arguments": [],
    },

    "general_qa": {
        "description": "回答与销售数据库无关的问题。",
        "arguments": [],
    },

    "unknown": {
        "description": "无法判断的问题。",
        "arguments": [],
    },
}


# ============================================================
# Context helper
# ============================================================

def get_relevant_history(context: dict) -> list:
    """
    只保留最近几轮历史，减少串题。
    """

    history = context.get("history", [])

    return history[-5:]


def get_last_result_entity(context: dict):
    """
    从上一轮查询结果中提取商品、门店、分类等实体。

    重要：
    排名类查询不能直接把第一名商品作为下一轮实体，
    否则会导致：

    上一轮：
    什么饮品卖得最好

    得到：
    牛肉poke

    下一轮：
    什么饮料卖得最好

    被错误理解成：
    牛肉poke的相关问题。

    因此排名类 Tool 不自动继承商品实体。
    """

    result = context.get("last_result", [])

    if not result:
        return {}

    last_tool = context.get(
        "last_tool",
        "",
    )

    # ========================================================
    # 关键修复
    # 排名类查询不能自动把第一名作为下一轮实体
    # ========================================================

    if last_tool in {
        "product_rank",
        "product_quantity",
        "category_rank",
        "store_rank",
    }:
        return {}

    first = result[0]

    entity = {}

    if first.get("product_name"):
        entity["product_name"] = first["product_name"]

    if first.get("store_name"):
        entity["store_name"] = first["store_name"]

    if first.get("category"):
        entity["category"] = first["category"]

    if first.get("product_category"):
        entity["category"] = first["product_category"]

    return entity


def is_follow_up_question(question: str) -> bool:
    keywords = [
        "那",
        "那么",
        "这个",
        "那个",
        "它",
        "他",
        "他的",
        "它的",
        "第一个",
        "第二个",
        "第三个",
        "上一轮",
        "刚才",
        "之前",
        "继续",
        "呢",
        "多少",
        "怎么样",
    ]

    return any(
        keyword in question
        for keyword in keywords
    )


# ============================================================
# Hard Rules
# ============================================================

def apply_hard_rules(
    question: str,
    plan: dict,
    conversation_context: dict,
) -> dict:
    """
    Python层确定性规则。

    目的：
    1. 防止Qwen把上一轮实体错误带入新问题。
    2. 对非常明确的饮品/饮料排名问题进行强制路由。
    3. 保留真正追问的上下文能力。
    """

    text = question.strip()

    # ========================================================
    # 规则1
    # 当前问题明确出现“饮品/饮料”并且询问卖得最好
    # 强制走 product_rank。
    #
    # 例如：
    # 什么饮品卖得最好
    # 什么饮料卖得最好
    # 哪个饮品卖得最好
    # 哪个饮料销量最高
    # ========================================================

    beverage_keywords = [
        "饮品",
        "饮料",
    ]

    ranking_keywords = [
        "卖得最好",
        "卖得最多",
        "销量最高",
        "销售额最高",
        "销售额最多",
        "销量最多",
    ]

    has_beverage = any(
        keyword in text
        for keyword in beverage_keywords
    )

    has_ranking = any(
        keyword in text
        for keyword in ranking_keywords
    )

    if has_beverage and has_ranking:

        return {
            "tool": "product_rank",
            "arguments": {
                "order": "desc",
                "limit": 1,
                "category": "饮品",
                "product_name": None,
                "store_name": None,
                "start_date": None,
                "end_date": None,
            },
        }

    # ========================================================
    # 规则2
    # 当前问题明确是“什么商品/哪个商品卖得最好”
    # 不继承上一轮商品。
    # ========================================================

    product_ranking_keywords = [
        "什么商品卖得最好",
        "哪个商品卖得最好",
        "什么商品卖得最多",
        "哪个商品卖得最多",
        "销售额最高的商品",
        "销售额最多的商品",
        "销量最高的商品",
        "销量最多的商品",
    ]

    if any(
        keyword in text
        for keyword in product_ranking_keywords
    ):

        return {
            "tool": "product_rank",
            "arguments": {
                "order": "desc",
                "limit": 1,
                "category": None,
                "product_name": None,
                "store_name": None,
                "start_date": None,
                "end_date": None,
            },
        }

    # ========================================================
    # 规则3
    # 当前问题明确是新的客单价问题，
    # 禁止继承上一轮商品。
    # ========================================================

    aov_keywords = [
        "客单价",
        "平均客单价",
        "客单价趋势",
        "客单价上涨",
        "客单价下降",
    ]

    if any(
        keyword in text
        for keyword in aov_keywords
    ):

        return {
            "tool": "aov_trend",
            "arguments": {
                "start_date": None,
                "end_date": None,
            },
        }

    return plan


# ============================================================
# Agent Planner
# ============================================================

def plan_with_qwen(
    question: str,
    conversation_context: dict,
) -> dict:

    recent_history = get_relevant_history(
        conversation_context
    )

    last_entity = get_last_result_entity(
        conversation_context
    )

    prompt = f"""
你是 Moneki 餐饮销售数据分析 Agent 的任务规划器。

你的任务只有一个：

根据用户当前这一句话，决定调用哪个 Tool，
并提取正确参数。

绝对不要回答用户。

============================================================
可用 Tools
============================================================

{json.dumps(TOOLS, ensure_ascii=False, indent=2)}

============================================================
最近对话
============================================================

{json.dumps(recent_history, ensure_ascii=False, indent=2)}

============================================================
上一轮查询得到的实体
============================================================

{json.dumps(last_entity, ensure_ascii=False, indent=2)}

============================================================
非常重要：上下文规则
============================================================

只有当用户当前问题明显是上一轮问题的追问时，
才允许继承上一轮实体。

例如：

上一轮：
“牛肉Poke在六月的销售额是多少？”

当前：
“那五月呢？”

应该理解为：

“牛肉Poke在五月的销售额是多少？”

应该选择：

product_revenue

product_name = “牛肉Poke”
start_date = “2026-05-01”
end_date = “2026-05-31”

------------------------------------------------------------

例如：

上一轮：
“销售额最高的商品是什么？”

当前：
“他的销量呢？”

应该继承上一轮查询结果中的 product_name。

------------------------------------------------------------

例如：

上一轮：
“销售额最高的商品是什么？”

当前：
“第二个呢？”

应该理解为上一轮结果中的第二个商品。

============================================================
新问题优先规则
============================================================

如果当前问题出现新的明确业务目标，
优先使用当前问题。

例如：

上一轮：
“牛肉Poke六月销售额是多少？”

当前：
“最近客单价是上涨还是下降？”

这是一个全新的问题。

绝对不能继承：

牛肉Poke
六月
销售额

应该选择：

aov_trend

------------------------------------------------------------

如果当前问题是：

“什么饮品卖得最好”

这是新的商品分类排名问题。

绝对不能继承上一轮 product_name。

应该选择：

product_rank

category = “饮品”

order = desc

limit = 1

------------------------------------------------------------

如果当前问题是：

“什么饮料卖得最好”

同样是新的商品分类排名问题。

应该选择：

product_rank

category = “饮品”

order = desc

limit = 1

------------------------------------------------------------

如果当前问题出现：

饮品
饮料

并且同时出现：

卖得最好
卖得最多
销量最高
销量最多
销售额最高
销售额最多

必须优先判断为：

product_rank

category = “饮品”

order = desc

limit = 1

------------------------------------------------------------

如果当前问题没有明确出现具体商品名称，
不要主动从上一轮继承 product_name。

例如：

上一轮：
“牛肉Poke六月销售额是多少？”

当前：
“什么饮料卖得最好？”

不能理解为：

“牛肉Poke什么饮料卖得最好？”

必须重新判断当前问题。

============================================================
防止串题规则
============================================================

【规则1】

如果当前问题包含新的明确业务指标，
优先使用当前问题。

------------------------------------------------------------

【规则2】

如果当前问题明确出现：

客单价
客单价趋势
平均客单价
客单价上涨
客单价下降

必须使用：

aov_trend

------------------------------------------------------------

【规则3】

如果当前问题出现：

销售额最高商品
销售额最多商品
卖得最好的商品
卖得最多的商品

使用：

product_rank

order = desc
limit = 1

------------------------------------------------------------

【规则4】

如果当前问题出现：

销量最高
卖得最多
销售数量最多

使用：

product_quantity

order = desc
limit = 1

------------------------------------------------------------

【规则5】

如果当前问题明确指定商品销售额：

“牛肉Poke六月卖了多少钱”

使用：

product_revenue

------------------------------------------------------------

【规则6】

如果当前问题是：

“牛肉Poke每个月卖多少钱”

使用：

product_monthly_sales

------------------------------------------------------------

【规则7】

如果当前问题是：

“牛肉Poke哪天卖得最好”

使用：

product_daily_sales

------------------------------------------------------------

【规则8】

如果当前问题是：

“哪个分类销售额最高”

使用：

category_rank

------------------------------------------------------------

【规则9】

如果当前问题是：

“哪个门店销售额最高”

使用：

store_rank

------------------------------------------------------------

【规则10】

如果用户询问历史问题：

“我第一个问你的是什么”
“上一轮问了什么”
“刚才问了什么”

使用：

general_qa

============================================================
日期规则
============================================================

2026年6月：

start_date = 2026-06-01
end_date = 2026-06-30

2026年7月：

start_date = 2026-07-01
end_date = 2026-07-31

如果没有日期：

start_date = null
end_date = null

============================================================
输出格式
============================================================

只能输出JSON：

{{
    "tool": "工具名称",
    "arguments": {{
        "order": "desc",
        "limit": 1,
        "product_name": null,
        "category": null,
        "store_name": null,
        "start_date": null,
        "end_date": null
    }}
}}

不要Markdown。
不要解释。
不要SQL。
不要回答用户。

============================================================
当前用户问题
============================================================

{question}
"""

    raw = ask_qwen(prompt).strip()

    try:

        if raw.startswith("```"):
            raw = (
                raw
                .replace("```json", "")
                .replace("```", "")
                .strip()
            )

        plan = json.loads(raw)

    except Exception:

        print("[Agent Planner] Invalid JSON:")
        print(raw)

        return {
            "tool": "unknown",
            "arguments": {},
        }

    tool = plan.get(
        "tool",
        "unknown",
    )

    if tool not in TOOLS:
        tool = "unknown"

    arguments = plan.get(
        "arguments",
        {},
    )

    if not isinstance(arguments, dict):
        arguments = {}

    return {
        "tool": tool,
        "arguments": arguments,
    }


# ============================================================
# Date helper
# ============================================================

def normalize_date(value: Optional[str]):

    if not value:
        return None

    parsed = pd.to_datetime(
        value,
        errors="coerce",
    )

    if pd.isna(parsed):
        return None

    return parsed.strftime("%Y-%m-%d")


def build_date_filter(
    arguments: dict,
    field_name: str = "s.date",
):

    start_date = normalize_date(
        arguments.get("start_date")
    )

    end_date = normalize_date(
        arguments.get("end_date")
    )

    where = []
    params = []

    if start_date:
        where.append(
            f"{field_name} >= ?"
        )
        params.append(start_date)

    if end_date:
        where.append(
            f"{field_name} <= ?"
        )
        params.append(end_date)

    return where, params


# ============================================================
# Product / Category / Store validation
# ============================================================

def resolve_product_name(product_name: Optional[str]):

    if not product_name:
        return None

    products = query_db(
        """
        SELECT product_name
        FROM products
        ORDER BY LENGTH(product_name) DESC
        """
    )

    target = str(product_name).strip().lower()

    for item in products:

        name = str(item["product_name"])

        if name.lower() == target:
            return name

    for item in products:

        name = str(item["product_name"])

        if (
            target in name.lower()
            or name.lower() in target
        ):
            return name

    return None


def resolve_category(category: Optional[str]):

    if not category:
        return None

    categories = query_db(
        """
        SELECT DISTINCT product_category
        FROM products
        WHERE product_category IS NOT NULL
        ORDER BY LENGTH(product_category) DESC
        """
    )

    target = str(category).strip().lower()

    for item in categories:

        name = str(item["product_category"])

        if name.lower() == target:
            return name

    clean_target = target.replace("类", "")

    # ========================================================
    # 饮料 / 饮品兼容
    # ========================================================

    if clean_target in {
        "饮料",
        "饮品",
    }:

        beverage_aliases = {
            "饮料",
            "饮品",
        }

        for item in categories:

            name = str(item["product_category"])
            clean_name = (
                name.lower()
                .replace("类", "")
            )

            if clean_name in beverage_aliases:
                return name

    for item in categories:

        name = str(item["product_category"])

        clean_name = (
            name.lower()
            .replace("类", "")
        )

        if (
            clean_target == clean_name
            or clean_target in clean_name
            or clean_name in clean_target
        ):
            return name

    return None


def resolve_store_name(store_name: Optional[str]):

    if not store_name:
        return None

    stores = query_db(
        """
        SELECT store_name
        FROM stores
        ORDER BY LENGTH(store_name) DESC
        """
    )

    target = str(store_name).strip().lower()

    for item in stores:

        name = str(item["store_name"])

        if name.lower() == target:
            return name

    for item in stores:

        name = str(item["store_name"])

        if (
            target in name.lower()
            or name.lower() in target
        ):
            return name

    return None


# ============================================================
# Tool: Product Rank
# ============================================================

def tool_product_rank(arguments: dict):

    order = arguments.get("order", "desc")

    if order not in {"asc", "desc"}:
        order = "desc"

    try:
        limit = int(arguments.get("limit", 1))
    except Exception:
        limit = 1

    limit = max(1, min(limit, 100))

    category = resolve_category(
        arguments.get("category")
    )

    where, params = build_date_filter(arguments)

    if category:

        where.append(
            "LOWER(p.product_category) = LOWER(?)"
        )

        params.append(category)

    where_sql = ""

    if where:
        where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            p.product_id,
            p.product_name,
            p.product_category,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        {where_sql}
        GROUP BY
            p.product_id,
            p.product_name,
            p.product_category
        ORDER BY revenue {order}
        LIMIT ?
    """

    params.append(limit)

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Product Revenue
# ============================================================

def tool_product_revenue(arguments: dict):

    product_name = resolve_product_name(
        arguments.get("product_name")
    )

    if not product_name:
        return []

    where = [
        "LOWER(p.product_name) = LOWER(?)"
    ]

    params = [product_name]

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            p.product_id,
            p.product_name,
            p.product_category,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        WHERE {" AND ".join(where)}
        GROUP BY
            p.product_id,
            p.product_name,
            p.product_category
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Product Quantity
# ============================================================

def tool_product_quantity(arguments: dict):

    product_name = arguments.get("product_name")
    category = arguments.get("category")

    order = arguments.get("order", "desc")

    if order not in {"asc", "desc"}:
        order = "desc"

    try:
        limit = int(arguments.get("limit", 1))
    except Exception:
        limit = 1

    limit = max(1, min(limit, 100))

    resolved_product = resolve_product_name(product_name)
    resolved_category = resolve_category(category)

    where = []
    params = []

    if resolved_product:

        where.append(
            "LOWER(p.product_name) = LOWER(?)"
        )

        params.append(resolved_product)

    if resolved_category:

        where.append(
            "LOWER(p.product_category) = LOWER(?)"
        )

        params.append(resolved_category)

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    where_sql = ""

    if where:
        where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            p.product_id,
            p.product_name,
            p.product_category,
            SUM(s.qty) AS qty,
            ROUND(SUM(s.amount), 2) AS revenue,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        {where_sql}
        GROUP BY
            p.product_id,
            p.product_name,
            p.product_category
        ORDER BY qty {order}
        LIMIT ?
    """

    params.append(limit)

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Product Orders
# ============================================================

def tool_product_orders(arguments: dict):

    product_name = resolve_product_name(
        arguments.get("product_name")
    )

    if not product_name:
        return []

    where = [
        "LOWER(p.product_name) = LOWER(?)"
    ]

    params = [product_name]

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            p.product_id,
            p.product_name,
            COUNT(DISTINCT s.order_id) AS order_count,
            SUM(s.qty) AS qty,
            ROUND(SUM(s.amount), 2) AS revenue
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        WHERE {" AND ".join(where)}
        GROUP BY
            p.product_id,
            p.product_name
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Product Monthly Sales
# ============================================================

def tool_product_monthly_sales(arguments: dict):

    product_name = resolve_product_name(
        arguments.get("product_name")
    )

    if not product_name:
        return []

    where = [
        "LOWER(p.product_name) = LOWER(?)"
    ]

    params = [product_name]

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            substr(s.date, 1, 7) AS month,
            p.product_name,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        WHERE {" AND ".join(where)}
        GROUP BY
            substr(s.date, 1, 7),
            p.product_name
        ORDER BY month ASC
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Product Daily Sales
# ============================================================

def tool_product_daily_sales(arguments: dict):

    product_name = resolve_product_name(
        arguments.get("product_name")
    )

    if not product_name:
        return []

    where = [
        "LOWER(p.product_name) = LOWER(?)"
    ]

    params = [product_name]

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            s.date,
            p.product_name,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        WHERE {" AND ".join(where)}
        GROUP BY
            s.date,
            p.product_name
        ORDER BY s.date ASC
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Category Rank
# ============================================================

def tool_category_rank(arguments: dict):

    order = arguments.get("order", "desc")

    if order not in {"asc", "desc"}:
        order = "desc"

    try:
        limit = int(arguments.get("limit", 1))
    except Exception:
        limit = 1

    limit = max(1, min(limit, 100))

    where, params = build_date_filter(arguments)

    where_sql = ""

    if where:
        where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            p.product_category AS category,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        {where_sql}
        GROUP BY p.product_category
        ORDER BY revenue {order}
        LIMIT ?
    """

    params.append(limit)

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Category Revenue
# ============================================================

def tool_category_revenue(arguments: dict):

    category = resolve_category(
        arguments.get("category")
    )

    if not category:
        return []

    where = [
        "LOWER(p.product_category) = LOWER(?)"
    ]

    params = [category]

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            p.product_category AS category,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN products p
            ON s.product_id = p.product_id
        WHERE {" AND ".join(where)}
        GROUP BY p.product_category
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Store Rank
# ============================================================

def tool_store_rank(arguments: dict):

    order = arguments.get("order", "desc")

    if order not in {"asc", "desc"}:
        order = "desc"

    try:
        limit = int(arguments.get("limit", 1))
    except Exception:
        limit = 1

    limit = max(1, min(limit, 100))

    where, params = build_date_filter(arguments)

    where_sql = ""

    if where:
        where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            st.store_id,
            st.store_name,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN stores st
            ON s.store_id = st.store_id
        {where_sql}
        GROUP BY
            st.store_id,
            st.store_name
        ORDER BY revenue {order}
        LIMIT ?
    """

    params.append(limit)

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Store Revenue
# ============================================================

def tool_store_revenue(arguments: dict):

    store_name = resolve_store_name(
        arguments.get("store_name")
    )

    if not store_name:
        return []

    where = [
        "LOWER(st.store_name) = LOWER(?)"
    ]

    params = [store_name]

    date_where, date_params = build_date_filter(arguments)

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            st.store_id,
            st.store_name,
            ROUND(SUM(s.amount), 2) AS revenue,
            SUM(s.qty) AS qty,
            COUNT(DISTINCT s.order_id) AS order_count
        FROM sales s
        JOIN stores st
            ON s.store_id = st.store_id
        WHERE {" AND ".join(where)}
        GROUP BY
            st.store_id,
            st.store_name
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Daily Sales
# ============================================================

def tool_daily_sales(arguments: dict):

    where = ["date IS NOT NULL"]
    params = []

    date_where, date_params = build_date_filter(
        arguments,
        field_name="date",
    )

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            date,
            ROUND(SUM(amount), 2) AS revenue,
            COUNT(DISTINCT order_id) AS order_count,
            ROUND(
                SUM(amount) /
                NULLIF(COUNT(DISTINCT order_id), 0),
                2
            ) AS average_order_value
        FROM sales
        WHERE {" AND ".join(where)}
        GROUP BY date
        ORDER BY date ASC
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: Monthly Sales
# ============================================================

def tool_monthly_sales(arguments: dict):

    where = ["date IS NOT NULL"]
    params = []

    date_where, date_params = build_date_filter(
        arguments,
        field_name="date",
    )

    where.extend(date_where)
    params.extend(date_params)

    sql = f"""
        SELECT
            substr(date, 1, 7) AS month,
            ROUND(SUM(amount), 2) AS revenue,
            SUM(qty) AS qty,
            COUNT(DISTINCT order_id) AS order_count,
            ROUND(
                SUM(amount) /
                NULLIF(COUNT(DISTINCT order_id), 0),
                2
            ) AS average_order_value
        FROM sales
        WHERE {" AND ".join(where)}
        GROUP BY substr(date, 1, 7)
        ORDER BY month ASC
    """

    return query_db(
        sql,
        tuple(params),
    )


# ============================================================
# Tool: AOV Trend
# ============================================================

def tool_aov_trend(arguments: dict):

    return tool_daily_sales(arguments)


# ============================================================
# Tool: Dataset Summary
# ============================================================

def tool_dataset_summary(arguments: dict):

    sales_count = query_db(
        "SELECT COUNT(*) AS count FROM sales"
    )[0]["count"]

    store_count = query_db(
        "SELECT COUNT(*) AS count FROM stores"
    )[0]["count"]

    product_count = query_db(
        "SELECT COUNT(*) AS count FROM products"
    )[0]["count"]

    date_range = query_db(
        """
        SELECT
            MIN(date) AS min_date,
            MAX(date) AS max_date
        FROM sales
        """
    )

    return [
        {
            "sales_rows": sales_count,
            "store_count": store_count,
            "product_count": product_count,
            "min_date": date_range[0]["min_date"],
            "max_date": date_range[0]["max_date"],
        }
    ]


# ============================================================
# Database Fallback
# ============================================================

def database_fallback(
    question: str,
    conversation_context: dict,
):

    prompt = f"""
你是Moneki餐饮销售数据库分析助手。

请根据用户问题生成一条只读SQLite查询。

数据库：

{get_database_schema()}

只允许：

SELECT
WITH

禁止：

INSERT
UPDATE
DELETE
DROP
ALTER
CREATE
PRAGMA
ATTACH
DETACH

必须只生成一条SQL。

如果需要商品名称，关联products。

如果需要门店名称，关联stores。

销售额：
SUM(amount)

销量：
SUM(qty)

订单数：
COUNT(DISTINCT order_id)

============================================================
用户问题
============================================================

{question}

============================================================
输出
============================================================

只输出：

{{
    "sql": "SELECT ..."
}}
"""

    raw = ask_qwen(prompt).strip()

    try:

        if raw.startswith("```"):
            raw = (
                raw
                .replace("```json", "")
                .replace("```sql", "")
                .replace("```", "")
                .strip()
            )

        result = json.loads(raw)

        sql = result.get(
            "sql",
            "",
        ).strip()

    except Exception:

        return []

    if not sql:
        return []

    normalized = sql.lower().strip()

    if not (
        normalized.startswith("select")
        or normalized.startswith("with")
    ):
        return []

    forbidden = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "create ",
        "attach ",
        "detach ",
        "pragma ",
        "vacuum ",
        "replace ",
        "truncate ",
    ]

    for keyword in forbidden:

        if keyword in normalized:
            return []

    if ";" in sql.rstrip(";"):
        return []

    try:
        return query_db(sql)
    except Exception:
        return []


# ============================================================
# General QA
# ============================================================

def general_qa(
    question: str,
    conversation_context: dict,
):

    history = conversation_context.get(
        "history",
        [],
    )

    # ========================================================
    # 历史问题
    # ========================================================

    if (
        "第一个问" in question
        or "第一个问题" in question
        or "第一问" in question
        or "最开始问" in question
        or "第一次问" in question
    ):

        if not history:
            return "当前对话中还没有历史问题。"

        first_question = history[0].get(
            "question",
            "",
        )

        return (
            f'你第一个问我的问题是：'
            f'“{first_question}”'
        )

    if (
        "上一轮" in question
        or "刚才问" in question
        or "之前问" in question
    ):

        if not history:
            return "当前对话中还没有上一轮问题。"

        last_question = history[-1].get(
            "question",
            "",
        )

        return (
            f'你上一轮问我的问题是：'
            f'“{last_question}”'
        )

    prompt = f"""
你是Moneki餐饮经营助手。

直接回答用户问题。

不要虚构Moneki数据库中的数据。

如果问题是普通餐饮经营知识，可以正常回答。

回答简洁。

用户问题：

{question}
"""

    return ask_qwen(prompt).strip()


# ============================================================
# Tool Registry
# ============================================================

TOOL_FUNCTIONS = {

    "product_rank":
        tool_product_rank,

    "category_rank":
        tool_category_rank,

    "store_rank":
        tool_store_rank,

    "product_revenue":
        tool_product_revenue,

    "product_quantity":
        tool_product_quantity,

    "product_orders":
        tool_product_orders,

    "product_monthly_sales":
        tool_product_monthly_sales,

    "product_daily_sales":
        tool_product_daily_sales,

    "category_revenue":
        tool_category_revenue,

    "store_revenue":
        tool_store_revenue,

    "daily_sales":
        tool_daily_sales,

    "monthly_sales":
        tool_monthly_sales,

    "aov_trend":
        tool_aov_trend,

    "dataset_summary":
        tool_dataset_summary,
}


# ============================================================
# Chart
# ============================================================

def build_chart(
    tool: str,
    data: list,
):

    if not data:
        return None

    if tool in {
        "product_rank",
        "category_rank",
        "store_rank",
    }:

        return {
            "type": "bar",
            "title": "销售额排名",
            "x_key": (
                "product_name"
                if tool == "product_rank"
                else "category"
                if tool == "category_rank"
                else "store_name"
            ),
            "y_key": "revenue",
            "data": data,
        }

    if tool == "product_quantity":

        return {
            "type": "bar",
            "title": "商品销量排名",
            "x_key": "product_name",
            "y_key": "qty",
            "data": data,
        }

    if tool == "monthly_sales":

        return {
            "type": "line",
            "title": "月度销售趋势",
            "x_key": "month",
            "y_key": "revenue",
            "data": data,
        }

    if tool == "product_monthly_sales":

        return {
            "type": "line",
            "title": "商品月度销售趋势",
            "x_key": "month",
            "y_key": "revenue",
            "data": data,
        }

    if tool in {
        "daily_sales",
        "aov_trend",
    }:

        return {
            "type": "line",
            "title": (
                "客单价趋势"
                if tool == "aov_trend"
                else "每日营业额趋势"
            ),
            "x_key": "date",
            "y_key": (
                "average_order_value"
                if tool == "aov_trend"
                else "revenue"
            ),
            "data": data,
        }

    if tool == "product_daily_sales":

        return {
            "type": "line",
            "title": "商品每日销售趋势",
            "x_key": "date",
            "y_key": "revenue",
            "data": data,
        }

    return None


# ============================================================
# Final Answer
# ============================================================

def generate_answer(
    question: str,
    plan: dict,
    data: list,
    conversation_context: dict,
) -> str:

    if not data:
        return "暂时没有查询到相关销售数据。"

    tool = plan.get(
        "tool",
        "",
    )

    # ========================================================
    # 特殊处理：客单价趋势
    # ========================================================

    if tool == "aov_trend":

        values = []

        for row in data:

            value = row.get(
                "average_order_value"
            )

            if value is not None:

                try:
                    values.append(
                        float(value)
                    )
                except Exception:
                    pass

        if len(values) >= 2:

            first = values[0]
            last = values[-1]

            if last > first:
                trend = "上涨"
            elif last < first:
                trend = "下降"
            else:
                trend = "基本持平"

            change = last - first

            return (
                f"最近客单价整体呈{trend}趋势。"
                f"从{first:.2f}元变为{last:.2f}元，"
                f"变化{abs(change):.2f}元。"
            )

        return "目前查询到的客单价数据不足以判断趋势。"

    # ========================================================
    # 普通销售数据
    # ========================================================

    prompt = f"""
你是Moneki餐饮经营数据助手。

根据真实查询结果回答用户。

绝对要求：

1. 只能使用真实查询结果中的数据。
2. 不允许编造数字。
3. 不允许修改数字。
4. 不要提及SQL。
5. 不要提及SQLite。
6. 不要提及Python。
7. 不要提及Tool。
8. 不要解释内部流程。
9. 直接回答用户。
10. 如果只有一个结果，直接给结论。
11. 如果用户问销售额，回答销售额。
12. 如果用户问销量，回答销量。
13. 如果用户问订单数，回答订单数。
14. 如果用户问商品名称，回答商品名称。
15. 不要把上一轮无关信息带进当前答案。
16. 当前问题优先级最高。
17. 只有当前问题明确要求上下文时，才使用上一轮信息。
18. 金额使用“元”。

============================================================
当前用户问题
============================================================

{question}

============================================================
当前查询类型
============================================================

{tool}

============================================================
真实查询结果
============================================================

{json.dumps(
    data,
    ensure_ascii=False,
    indent=2,
)}

============================================================

只回答当前用户问题。
"""

    answer = ask_qwen(prompt).strip()

    if not answer:
        return "暂时无法生成回答，请稍后重试。"

    return answer


# ============================================================
# AI Data Q&A API
# ============================================================

@app.post("/api/ask")
def ask_question(
    request: AskRequest,
):

    question = request.question.strip()

    conversation_id = (
        request.conversation_id.strip()
        or "default"
    )

    if not question:

        return {
            "success": False,
            "question": question,
            "answer": "请输入你的问题。",
            "data": [],
            "chart": None,
        }

    try:

        # ====================================================
        # Step 1
        # 获取上下文
        # ====================================================

        context = get_conversation_context(
            conversation_id
        )

        # ====================================================
        # Step 2
        # Agent Planner
        # ====================================================

        plan = plan_with_qwen(
            question,
            context,
        )

        # ====================================================
        # Step 2.5
        # Python Hard Rules
        #
        # 这是本次修复最重要的位置。
        #
        # Qwen负责自然语言理解，
        # Python负责对明确问题进行确定性纠正。
        # ====================================================

        plan = apply_hard_rules(
            question,
            plan,
            context,
        )

        tool = plan.get(
            "tool",
            "unknown",
        )

        arguments = plan.get(
            "arguments",
            {},
        )

        print("=" * 70)
        print("[AI Agent]")
        print("Question:", question)
        print("Tool:", tool)
        print("Arguments:", arguments)
        print("=" * 70)

        # ====================================================
        # Step 3
        # General QA
        # ====================================================

        if tool in {
            "general_qa",
            "unknown",
        }:

            answer = general_qa(
                question,
                context,
            )

            save_conversation_context(
                conversation_id,
                question,
                "general_qa",
                {},
                [],
            )

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "data": [],
                "chart": None,
                "tool": "general_qa",
                "arguments": {},
                "conversation_id": conversation_id,
            }

        # ====================================================
        # Step 4
        # Database fallback
        # ====================================================

        if tool == "database_fallback":

            rows = database_fallback(
                question,
                context,
            )

            if rows:

                fallback_plan = {
                    "tool": "database_fallback",
                    "arguments": {},
                }

                answer = generate_answer(
                    question,
                    fallback_plan,
                    rows,
                    context,
                )

                save_conversation_context(
                    conversation_id,
                    question,
                    tool,
                    arguments,
                    rows,
                )

                return {
                    "success": True,
                    "question": question,
                    "answer": answer,
                    "data": rows,
                    "chart": None,
                    "tool": tool,
                    "arguments": arguments,
                    "conversation_id": conversation_id,
                }

            answer = (
                "暂时没有查询到相关销售数据。"
            )

            save_conversation_context(
                conversation_id,
                question,
                tool,
                arguments,
                [],
            )

            return {
                "success": True,
                "question": question,
                "answer": answer,
                "data": [],
                "chart": None,
                "tool": tool,
                "arguments": arguments,
                "conversation_id": conversation_id,
            }

        # ====================================================
        # Step 5
        # Execute Tool
        # ====================================================

        tool_function = TOOL_FUNCTIONS.get(tool)

        if tool_function is None:
            raise ValueError(
                f"Unknown tool: {tool}"
            )

        rows = tool_function(arguments)

        # ====================================================
        # Step 6
        # Generate Answer
        # ====================================================

        answer = generate_answer(
            question,
            plan,
            rows,
            context,
        )

        # ====================================================
        # Step 7
        # Chart
        # ====================================================

        chart = build_chart(
            tool,
            rows,
        )

        # ====================================================
        # Step 8
        # Save Memory
        # ====================================================

        save_conversation_context(
            conversation_id,
            question,
            tool,
            arguments,
            rows,
        )

        return {
            "success": True,
            "question": question,
            "answer": answer,
            "data": rows,
            "chart": chart,
            "tool": tool,
            "arguments": arguments,
            "conversation_id": conversation_id,
        }

    except Exception as exc:

        print(
            f"[AI Q&A ERROR] {exc}"
        )

        return {
            "success": False,
            "question": question,
            "answer": (
                "AI 数据助手暂时无法完成查询，"
                "请确认 Ollama、Qwen 和数据库正常运行。"
            ),
            "data": [],
            "chart": None,
        }


# ============================================================
# Root
# ============================================================

@app.get("/")
def root():

    return {
        "name": "Moneki Sales Dashboard API",
        "version": "2.3.0",
        "status": "running",
    }


# ============================================================
# Health
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "sales-dashboard-api",
        "qwen": OLLAMA_MODEL,
    }


# ============================================================
# CSV Data loading
# ============================================================

def load_data():

    if not SALES_FILE.exists():
        raise FileNotFoundError(
            f"Sales file not found: {SALES_FILE}"
        )

    if not STORES_FILE.exists():
        raise FileNotFoundError(
            f"Stores file not found: {STORES_FILE}"
        )

    if not PRODUCTS_FILE.exists():
        raise FileNotFoundError(
            f"Products file not found: {PRODUCTS_FILE}"
        )

    sales = pd.read_csv(SALES_FILE)
    stores = pd.read_csv(STORES_FILE)
    products = pd.read_csv(PRODUCTS_FILE)

    return (
        sales,
        stores,
        products,
    )


# ============================================================
# Date handling
# ============================================================

def parse_single_date(value):

    if pd.isna(value):
        return pd.NaT

    text = str(value).strip()

    if not text:
        return pd.NaT

    text = (
        text
        .replace("/", "-")
        .replace(".", "-")
    )

    return pd.to_datetime(
        text,
        format="%Y-%m-%d",
        errors="coerce",
    )


def parse_dates(df: pd.DataFrame):

    result = df.copy()

    result["parsed_date"] = (
        result["date"].apply(
            parse_single_date
        )
    )

    return result


def parse_query_date(
    value: Optional[str],
):

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
# Amount
# ============================================================

def parse_amount(series: pd.Series):

    result = (
        series
        .astype("string")
        .str.strip()
        .str.replace(
            "¥",
            "",
            regex=False,
        )
        .str.replace(
            "￥",
            "",
            regex=False,
        )
        .str.replace(
            ",",
            "",
            regex=False,
        )
        .str.strip()
    )

    return pd.to_numeric(
        result,
        errors="coerce",
    )


# ============================================================
# DataFrame Date Filter
# ============================================================

def filter_by_date(
    sales: pd.DataFrame,
    start_date: Optional[str],
    end_date: Optional[str],
):

    result = sales

    if start_date:

        start = parse_query_date(
            start_date
        )

        if start is None:
            raise ValueError(
                f"Invalid start_date: {start_date}"
            )

        result = result[
            result["parsed_date"] >= start
        ]

    if end_date:

        end = parse_query_date(
            end_date
        )

        if end is None:
            raise ValueError(
                f"Invalid end_date: {end_date}"
            )

        result = result[
            result["parsed_date"] <= end
        ]

    return result


# ============================================================
# Metadata
# ============================================================

@app.get("/api/meta")
def get_meta():

    sales, stores, products = load_data()

    sales = parse_dates(sales)

    valid_dates = (
        sales["parsed_date"]
        .dropna()
    )

    if valid_dates.empty:

        min_date = None
        max_date = None

    else:

        min_date = (
            valid_dates
            .min()
            .strftime("%Y-%m-%d")
        )

        max_date = (
            valid_dates
            .max()
            .strftime("%Y-%m-%d")
        )

    return {
        "sales_rows": int(len(sales)),
        "store_count": int(len(stores)),
        "product_count": int(len(products)),
        "min_date": min_date,
        "max_date": max_date,
    }


# ============================================================
# Daily Sales API
# ============================================================

@app.get("/api/daily-sales")
def get_daily_sales(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):

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
            revenue=(
                "numeric_amount",
                "sum",
            ),
            order_count=(
                "order_id",
                "nunique",
            ),
        )
        .reset_index()
    )

    daily["average_order_value"] = (
        daily["revenue"]
        /
        daily["order_count"].replace(
            0,
            pd.NA,
        )
    )

    daily["date"] = (
        daily["parsed_date"]
        .dt
        .strftime("%Y-%m-%d")
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
# Top Products API
# ============================================================

@app.get("/api/top-products")
def get_top_products(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
):

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
            revenue=(
                "numeric_amount",
                "sum",
            ),
            qty=(
                "qty",
                "sum",
            ),
            order_count=(
                "order_id",
                "nunique",
            ),
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
# Store Sales API
# ============================================================

@app.get("/api/store-sales")
def get_store_sales(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):

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
            revenue=(
                "numeric_amount",
                "sum",
            ),
            order_count=(
                "order_id",
                "nunique",
            ),
            qty=(
                "qty",
                "sum",
            ),
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
        /
        result["order_count"].replace(
            0,
            pd.NA,
        )
    )

    result = result.sort_values(
        "revenue",
        ascending=False,
    )

    result = result.fillna(0)

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
# Category Sales API
# ============================================================

@app.get("/api/category-sales")
def get_category_sales(
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):

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
            revenue=(
                "numeric_amount",
                "sum",
            ),
            qty=(
                "qty",
                "sum",
            ),
            order_count=(
                "order_id",
                "nunique",
            ),
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
# Application Entry
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        reload=False,
    )