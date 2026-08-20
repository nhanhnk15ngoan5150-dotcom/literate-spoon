# 连锁餐饮经营数据分析平台

一个基于 **FastAPI + React + SQLite + Pandas + Recharts + Qwen** 构建的连锁餐饮经营数据分析平台。

项目针对门店销售数据进行数据审计、清洗、统计和可视化，并提供 AI 数据助手，使经营人员可以通过自然语言查询营业额、订单、商品、门店、商品分类等经营数据。

---

## 一、项目背景

项目提供了一组连锁餐饮销售数据，包括：

* 销售订单数据
* 门店基础信息
* 商品基础信息

在实际分析前，对原始数据进行了数据审计，发现存在金额缺失、金额格式不统一、重复订单、异常数量以及部分关联数据不存在等情况。

因此项目采用：

```text
原始数据
   ↓
数据审计
   ↓
数据清洗
   ↓
SQLite 数据库
   ↓
FastAPI
   ↓
React 数据看板
```

同时增加 AI 数据助手：

```text
自然语言问题
      ↓
Qwen
      ↓
识别查询意图和查询条件
      ↓
数据库查询
      ↓
结构化查询结果
      ↓
LLM 自然语言解释
```

核心设计原则是：

> **LLM 负责理解和解释，数据库负责提供事实。**

避免让模型直接根据自身知识生成业务数据。

---

## 二、主要功能

### 1. 经营数据看板

提供以下数据维度：

* 总营业额
* 订单量
* 客单价
* 商品销售情况
* 商品分类销售情况
* 门店销售情况
* 销售趋势
* 支付方式等

### 2. AI 数据助手

支持通过自然语言查询业务数据，例如：

```text
哪个品类的营业额最高？
```

```text
牛肉Poke在六月的销售额是多少？
```

```text
最近客单价是上涨还是下降？
```

系统将自然语言问题转换为查询条件，再通过数据库获取真实数据，最后由 LLM 对查询结果进行解释。

### 3. 数据质量处理

针对原始数据中的异常情况进行了审计和清洗，包括：

* 缺失金额处理
* 金额格式统一
* 重复订单检查
* 异常数量检查
* 商品关联检查
* 门店关联检查

原始 CSV 保留在 `data/raw/` 中，清洗后的数据存放在 `data/processed/`。

---

## 三、技术栈

### 后端

* Python
* FastAPI
* Pandas
* SQLite
* Uvicorn

### AI

* Ollama
* Qwen2.5 7B Instruct

### 前端

* React
* Vite
* Axios
* Recharts
* CSS

### 数据处理

* CSV
* Pandas
* SQLite

---

## 四、项目架构

整体架构如下：

```text
                         用户
                          │
             ┌────────────┴────────────┐
             │                         │
          数据看板                  AI 数据助手
             │                         │
             │                    自然语言问题
             │                         │
             │                    Qwen2.5 7B
             │                         │
             │                  查询条件识别
             │                         │
             └────────────┬────────────┘
                          │
                       FastAPI
                          │
                    SQLite / 数据层
                          │
              ┌───────────┴───────────┐
              │                       │
          销售数据                  基础数据
              │                       │
          sales.csv          products.csv / stores.csv
              │
        数据清洗与聚合
              │
        返回结构化结果
              │
        ┌─────┴─────┐
        │           │
     React       LLM解释
        │           │
        └─────┬─────┘
              │
            页面展示
```

数据处理链路：

```text
data/raw/
   │
   ↓
数据审计
   │
   ↓
scripts/data_clean.py
   │
   ↓
data/processed/
   │
   ↓
scripts/init_db.py
   │
   ↓
data/moneki.db
   │
   ↓
FastAPI API
   │
   ├── React Dashboard
   │
   └── AI Data Assistant
```

---

## 五、项目结构

```text
literate-spoon/
│
├── backend/
│   ├── __init__.py
│   ├── main.py
│   └── llm_service.py
│
├── data/
│   ├── raw/
│   │   ├── sales.csv
│   │   ├── stores.csv
│   │   └── products.csv
│   │
│   ├── processed/
│   │   ├── sales.csv
│   │   ├── stores.csv
│   │   └── products.csv
│   │
│   └── moneki.db
│
├── docs/
│   └── audit_report.json
│
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   └── vite.config.js
│
├── scripts/
│   ├── check_db.py
│   ├── data_audit.py
│   ├── data_clean.py
│   ├── init_db.py
│   └── query_db.py
│
├── requirements.txt
├── README.md
├── AI_USAGE.md
├── DEMO.md
└── .gitignore
```

---

## 六、运行环境

建议环境：

* Python 3.10+
* Node.js 18+
* npm
* Ollama

AI 数据助手使用本地 Ollama 运行 Qwen2.5 7B Instruct。

---

## 七、启动项目

### 1. 安装 Python 依赖

进入项目根目录：

```bash
pip install -r requirements.txt
```

---

### 2. 初始化数据库

如果需要重新生成 SQLite 数据库：

```bash
python scripts/init_db.py
```

可以使用：

```bash
python scripts/check_db.py
```

检查数据库是否初始化成功。

---

### 3. 启动 Ollama

确保本机已经安装 Ollama，并准备对应模型：

```bash
ollama pull qwen2.5:7b-instruct
```

启动 Ollama 服务。

默认地址：

```text
http://127.0.0.1:11434
```

---

### 4. 启动后端

在项目根目录执行：

```bash
uvicorn backend.main:app --reload
```

默认后端地址：

```text
http://127.0.0.1:8000
```

API 文档：

```text
http://127.0.0.1:8000/docs
```

---

### 5. 启动前端

进入前端目录：

```bash
cd frontend
```

安装依赖：

```bash
npm install
```

启动：

```bash
npm run dev
```

根据 Vite 输出的地址访问前端页面。

---

## 八、数据可信性设计

项目中的经营数据并不是由 LLM 直接生成。

例如用户询问：

```text
牛肉Poke在六月的销售额是多少？
```

系统需要先确定：

```text
商品 = 牛肉Poke
时间 = 6月
指标 = 销售额
```

然后通过数据库执行实际聚合：

```text
sales
  ↓
关联 products
  ↓
筛选商品
  ↓
筛选时间
  ↓
SUM(amount)
  ↓
返回查询结果
```

最后由 LLM 对查询结果进行自然语言解释。

因此：

```text
数据库 = 事实来源
LLM = 解释层
```

如果 AI 返回的数字存在疑问，可以重新执行数据库查询进行验证。

---

## 九、模糊需求的处理

题目中部分业务需求没有给出完全明确的定义，因此项目按照以下原则自行确定：

### 客单价

定义为：

```text
客单价 = 营业额 / 订单量
```

### “最近”

对于涉及趋势判断的问题，使用数据库中最近的可用统计周期进行比较，而不是让 LLM 自行猜测时间范围。

### “卖得最好”

根据具体问题区分：

* 销售额
* 销量
* 订单量

如果用户没有明确指标，则根据问题语义选择最合理的业务指标。

---

## 十、AI 异常案例

开发过程中发现过一个实际问题：

用户连续询问：

```text
什么饮品卖得最好？
```

AI 曾错误回答：

```text
牛肉Poke卖得最好。
```

但数据库中的商品信息显示：

```text
牛肉Poke
商品类别：主食
```

因此这个回答属于业务语义错误。

进一步排查后发现，问题与多轮对话上下文中的实体继承有关。

修复后，系统在当前问题明确出现“饮品”时，应重新确定：

```text
商品类别 = 饮品
```

而不能继续继承上一轮的商品实体。

详细验证过程见：

`DEMO.md`

---

## 十一、技术选型理由

### FastAPI

后端采用 FastAPI，原因是：

* Python 生态适合数据处理和 AI 调用
* API 开发简单
* 类型声明清晰
* 自带 Swagger 文档
* 方便前后端分离

### React

前端采用 React：

* 组件化开发
* 适合构建数据看板
* 与图表库结合方便
* 后续扩展交互功能成本较低

### Pandas

使用 Pandas 完成数据审计和清洗：

* CSV 处理方便
* 聚合能力强
* 适合快速处理结构化业务数据

### SQLite

本项目数据规模有限，因此没有引入复杂数据库基础设施，使用 SQLite：

* 部署简单
* 无需额外数据库服务
* 支持标准 SQL
* 方便本地开发和演示

### Recharts

数据看板需要展示销售趋势、分类排名等信息，因此使用 Recharts 完成图表可视化。

### Ollama + Qwen

AI 数据助手采用本地 Ollama + Qwen2.5 7B Instruct：

* 本地运行方便
* 不依赖线上 API Key
* 适合开发和演示
* 可以控制模型调用和 Prompt

---

## 十二、AI 使用说明

本项目在开发过程中使用了 AI 编程工具辅助完成部分代码开发、调试和问题分析。

详细使用方式、任务拆解、真实 Prompt、AI 出错案例以及人工决策部分见：

`AI_USAGE.md`

---

## 十三、Demo

三个核心业务问题及 AI 数据可信性验证见：

`DEMO.md`

重点展示：

1. 品类营业额排名
2. 牛肉Poke六月销售额
3. 客单价趋势
4. AI 错误回答的发现和修复


## 十二、风会停，火会灭，中国的牛马不会累！！！《《《求带入行》》》《《白嫖的额度都跑干了》》[玫瑰][玫瑰][玫瑰]