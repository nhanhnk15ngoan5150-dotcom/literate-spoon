import json
from typing import Any, Dict, Optional

from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ============================================================
# Ollama Configuration
# ============================================================

OLLAMA_BASE_URL = "http://127.0.0.1:11434"

OLLAMA_MODEL = "qwen2.5:7b-instruct"


# ============================================================
# Ollama Request
# ============================================================

def call_ollama(
    prompt: str,
    temperature: float = 0.1,
) -> str:
    """
    Call local Ollama model.

    The model is used only for:
    1. Understanding the user's natural-language question
    2. Generating a natural-language response

    Business numbers must come from SQLite/API queries.
    """

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }

    data = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    request = Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=data,
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
        ) from exc

    except URLError as exc:

        raise RuntimeError(
            "无法连接 Ollama，请确认 Ollama 正在运行。"
        ) from exc

    except Exception as exc:

        raise RuntimeError(
            f"Ollama 调用失败：{exc}"
        ) from exc


# ============================================================
# Intent Recognition
# ============================================================

def recognize_intent(
    question: str,
) -> Dict[str, Any]:
    """
    Let Qwen understand the user's question.

    Important:
    Qwen does NOT calculate business numbers here.
    """

    prompt = f"""
你是一个餐饮销售数据分析助手。

你的任务是理解用户的问题，并判断用户想查询什么数据。

用户问题：
{question}

只能从下面这些 intent 中选择一个：

1. top_product
含义：查询销售额最高的商品。
例如：
“什么食物销售额最高？”
“哪个商品卖得最好？”
“销售额最高的菜是什么？”

2. top_category
含义：查询销售额最高的商品品类。
例如：
“哪个品类销售额最高？”
“什么分类卖得最好？”

3. product_revenue
含义：查询某个指定商品在某个时间范围内的销售额。
例如：
“牛肉Poke六月卖了多少钱？”
“牛肉poke在6月销售额多少？”

4. aov_trend
含义：查询客单价最近的上涨或下降趋势。
例如：
“最近客单价是涨还是跌？”
“最近客单价趋势怎么样？”

5. unsupported
含义：无法通过当前销售数据回答的问题。

请严格输出 JSON，不要输出 Markdown，不要输出解释。

JSON 格式：

{{
  "intent": "top_product"
}}

或者：

{{
  "intent": "top_category"
}}

或者：

{{
  "intent": "product_revenue",
  "product_name": "牛肉Poke",
  "month": "2026-06"
}}

或者：

{{
  "intent": "aov_trend",
  "days": 14
}}

或者：

{{
  "intent": "unsupported"
}}

用户问题：
{question}
"""

    response = call_ollama(
        prompt,
        temperature=0,
    )

    # --------------------------------------------------------
    # Try to parse JSON
    # --------------------------------------------------------

    try:

        result = json.loads(response)

        if not isinstance(result, dict):
            raise ValueError(
                "Model response is not a JSON object."
            )

        return result

    except Exception:

        # ----------------------------------------------------
        # If Qwen adds extra text around JSON,
        # try to extract the JSON object.
        # ----------------------------------------------------

        start = response.find("{")
        end = response.rfind("}")

        if start != -1 and end != -1 and end > start:

            json_text = response[
                start:end + 1
            ]

            try:

                result = json.loads(
                    json_text
                )

                if isinstance(result, dict):
                    return result

            except Exception:
                pass

    # --------------------------------------------------------
    # Safe fallback
    # --------------------------------------------------------

    return {
        "intent": "unsupported"
    }


# ============================================================
# Answer Generation
# ============================================================

def generate_answer(
    question: str,
    query_result: Dict[str, Any],
) -> str:
    """
    Generate the final natural-language answer.

    IMPORTANT:
    The numbers in query_result come from SQLite.
    Qwen must not invent or modify them.
    """

    prompt = f"""
你是一个餐饮经营数据分析助手。

请根据下面的真实数据库查询结果回答用户问题。

用户问题：
{question}

真实数据库查询结果：
{json.dumps(
    query_result,
    ensure_ascii=False,
    indent=2,
)}

严格遵守以下规则：

1. 只能使用“真实数据库查询结果”中的数字。
2. 不允许编造销售额、订单数、客单价等数字。
3. 不允许修改数据库查询结果中的数字。
4. 如果查询结果为空，必须明确告诉用户没有找到相关数据。
5. 回答简洁、自然、专业。
6. 不要提到“Prompt”“模型”“JSON”等技术细节。
7. 不要输出 Markdown。
"""

    return call_ollama(
        prompt,
        temperature=0.1,
    )


# ============================================================
# Simple Health Check
# ============================================================

def check_ollama() -> bool:
    """
    Check whether Ollama is available.
    """

    try:

        payload = {
            "model": OLLAMA_MODEL,
            "prompt": "请只回答：OK",
            "stream": False,
            "options": {
                "temperature": 0,
            },
        }

        data = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        request = Request(
            f"{OLLAMA_BASE_URL}/api/generate",
            data=data,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        with urlopen(
            request,
            timeout=30,
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

            return bool(
                result.get("response")
            )

    except Exception:

        return False