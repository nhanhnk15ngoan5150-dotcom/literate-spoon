\# 连锁餐饮经营数据分析平台



一个基于 FastAPI + React + Recharts 构建的连锁餐饮经营数据分析平台。



项目针对门店销售数据进行清洗、统计和可视化，为经营人员提供营业额、订单、商品、门店及商品分类等维度的数据分析。



\---



\## 一、项目背景



项目提供了一组连锁餐饮销售数据，包括：



\- 销售订单数据

\- 门店基础信息

\- 商品基础信息



由于原始销售数据存在金额缺失、金额格式不统一、重复订单、异常数量以及部分关联数据不存在等情况，因此项目首先对原始数据进行审计，在不修改原始 CSV 的前提下完成数据分析，并通过 API 提供给前端展示。



\---



\## 二、技术栈



\### 后端



\- Python

\- FastAPI

\- Pandas

\- Uvicorn



\### 前端



\- React

\- Vite

\- Axios

\- Recharts

\- CSS



\### 数据



\- CSV

\- Pandas 数据处理



\---



\## 三、项目结构



```text

moneki-fullstack-assignment/

├── backend/

│   ├── \_\_init\_\_.py

│   └── main.py

│

├── data/

│   ├── raw/

│   │   ├── sales.csv

│   │   ├── stores.csv

│   │   └── products.csv

│   ├── sales.csv

│   ├── stores.csv

│   └── products.csv

│

├── docs/

│   └── audit\_report.json

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

│   └── data\_audit.py

│

├── README.md

└── .gitignore
#如果后面上班能每天都接触这样的话，不像哪些混子公司一样一个项目就知道拖拖拖，我感觉这样的生活会很充实，老板，\[呲牙]

