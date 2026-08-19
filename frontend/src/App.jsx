import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import "./App.css";

const API_BASE = "http://127.0.0.1:8000";

const CATEGORY_COLORS = [
  "#2563eb",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#06b6d4",
  "#f97316",
  "#ec4899",
];

function App() {
  const [meta, setMeta] = useState(null);

  const [startDate, setStartDate] = useState("2026-05-01");
  const [endDate, setEndDate] = useState("2026-07-31");

  const [dailySales, setDailySales] = useState([]);
  const [topProducts, setTopProducts] = useState([]);
  const [storeSales, setStoreSales] = useState([]);
  const [categorySales, setCategorySales] = useState([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    loadMeta();
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [startDate, endDate]);

  async function loadMeta() {
    try {
      const response = await axios.get(`${API_BASE}/api/meta`);
      setMeta(response.data);
    } catch (err) {
      console.error(err);
      setError("无法连接后端 API，请确认 FastAPI 正在运行。");
    }
  }

  async function loadDashboard() {
    setLoading(true);
    setError("");

    try {
      const params = {
        start_date: startDate,
        end_date: endDate,
      };

      const [
        dailyResponse,
        productsResponse,
        storesResponse,
        categoriesResponse,
      ] = await Promise.all([
        axios.get(`${API_BASE}/api/daily-sales`, { params }),
        axios.get(`${API_BASE}/api/top-products`, { params }),
        axios.get(`${API_BASE}/api/store-sales`, { params }),
        axios.get(`${API_BASE}/api/category-sales`, { params }),
      ]);

      setDailySales(dailyResponse.data.data || []);
      setTopProducts(productsResponse.data.data || []);
      setStoreSales(storesResponse.data.data || []);
      setCategorySales(categoriesResponse.data.data || []);
    } catch (err) {
      console.error(err);
      setError("加载销售数据失败，请检查后端 API。");
    } finally {
      setLoading(false);
    }
  }

  const summary = useMemo(() => {
    const revenue = dailySales.reduce(
      (sum, item) => sum + Number(item.revenue || 0),
      0
    );

    const orderCount = dailySales.reduce(
      (sum, item) => sum + Number(item.order_count || 0),
      0
    );

    return {
      revenue,
      orderCount,
      averageOrderValue: orderCount ? revenue / orderCount : 0,
    };
  }, [dailySales]);

  function formatMoney(value) {
    return `¥${Number(value || 0).toLocaleString("zh-CN", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }

  return (
    <div className="app">
      {/* =========================
          顶部
      ========================= */}
      <header className="header">
        <div>
          <h1>连锁餐饮经营数据分析平台</h1>
          <p>Moneki Sales Dashboard</p>
        </div>

        {meta && (
          <div className="dataset-info">
            <span>
              销售记录 {Number(meta.sales_rows).toLocaleString()}
            </span>

            <span>
              门店 {meta.store_count}
            </span>

            <span>
              商品 {meta.product_count}
            </span>
          </div>
        )}
      </header>

      <main className="container">
        {/* =========================
            日期筛选
        ========================= */}
        <section className="filter-card">
          <div>
            <label>开始日期</label>

            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </div>

          <div>
            <label>结束日期</label>

            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </div>

          <button onClick={loadDashboard}>
            刷新数据
          </button>

          {loading && (
            <span className="loading">
              数据加载中...
            </span>
          )}
        </section>

        {/* =========================
            错误提示
        ========================= */}
        {error && (
          <div className="error">
            {error}
          </div>
        )}

        {/* =========================
            数据概览
        ========================= */}
        <section className="stats-grid">
          <div className="stat-card">
            <span>总营业额</span>

            <strong>
              {formatMoney(summary.revenue)}
            </strong>

            <small>
              {startDate} 至 {endDate}
            </small>
          </div>

          <div className="stat-card">
            <span>订单数</span>

            <strong>
              {summary.orderCount.toLocaleString()}
            </strong>

            <small>
              按订单号去重统计
            </small>
          </div>

          <div className="stat-card">
            <span>平均客单价</span>

            <strong>
              {formatMoney(summary.averageOrderValue)}
            </strong>

            <small>
              营业额 ÷ 订单数
            </small>
          </div>
        </section>

        {/* =========================
            每日营业额趋势
        ========================= */}
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>每日营业额趋势</h2>

              <p>
                真实 API 数据
              </p>
            </div>
          </div>

          <div className="chart">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <LineChart data={dailySales}>
                <CartesianGrid
                  strokeDasharray="3 3"
                />

                <XAxis dataKey="date" />

                <YAxis />

                <Tooltip
                  formatter={(value) => [
                    formatMoney(value),
                    "营业额",
                  ]}
                />

                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>

        {/* =========================
            Top 商品 + 门店排行
        ========================= */}
        <section className="two-columns">
          {/* Top 10 商品 */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h2>Top 10 商品</h2>

                <p>
                  按销售额排序
                </p>
              </div>
            </div>

            <div className="table-wrapper">
              <table>
                <thead>
                  <tr>
                    <th>排名</th>
                    <th>商品</th>
                    <th>分类</th>
                    <th>销售额</th>
                  </tr>
                </thead>

                <tbody>
                  {topProducts.map(
                    (item, index) => (
                      <tr
                        key={item.product_id}
                      >
                        <td>
                          <span className="rank">
                            {index + 1}
                          </span>
                        </td>

                        <td>
                          {item.product_name ||
                            item.product_id}
                        </td>

                        <td>
                          {item.product_category ||
                            "-"}
                        </td>

                        <td>
                          {formatMoney(
                            item.revenue
                          )}
                        </td>
                      </tr>
                    )
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* 门店销售 */}
          <div className="panel">
            <div className="panel-header">
              <div>
                <h2>门店销售排行</h2>

                <p>
                  按销售额排序
                </p>
              </div>
            </div>

            <div className="chart small-chart">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <BarChart
                  data={storeSales}
                  layout="vertical"
                  margin={{
                    top: 10,
                    right: 20,
                    left: 20,
                    bottom: 10,
                  }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                  />

                  <XAxis type="number" />

                  <YAxis
                    type="category"
                    dataKey="store_name"
                    width={100}
                  />

                  <Tooltip
                    formatter={(value) => [
                      formatMoney(value),
                      "销售额",
                    ]}
                  />

                  <Bar
                    dataKey="revenue"
                    fill="#111827"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>

        {/* =========================
            商品分类销售
        ========================= */}
        <section className="panel category-panel">
          <div className="panel-header">
            <div>
              <h2>商品分类销售</h2>

              <p>
                按商品分类汇总
              </p>
            </div>
          </div>

          <div className="category-content">
            {/* 饼状图 */}
            <div className="category-chart">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <PieChart>
                  <Pie
                    data={categorySales}
                    dataKey="revenue"
                    nameKey="product_category"
                    cx="50%"
                    cy="50%"
                    outerRadius={125}
                    innerRadius={55}
                    paddingAngle={2}
                    label={({ name, percent }) =>
                      `${name} ${(percent * 100).toFixed(
                        1
                      )}%`
                    }
                  >
                    {categorySales.map(
                      (entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={
                            CATEGORY_COLORS[
                              index %
                                CATEGORY_COLORS.length
                            ]
                          }
                        />
                      )
                    )}
                  </Pie>

                  <Tooltip
                    formatter={(value) => [
                      formatMoney(value),
                      "销售额",
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* 右侧分类明细 */}
            <div className="category-legend">
              {categorySales.map(
                (item, index) => (
                  <div
                    className="category-legend-item"
                    key={
                      item.product_category ||
                      `category-${index}`
                    }
                  >
                    <div className="category-legend-left">
                      <span
                        className="category-color"
                        style={{
                          background:
                            CATEGORY_COLORS[
                              index %
                                CATEGORY_COLORS.length
                            ],
                        }}
                      />

                      <span className="category-name">
                        {item.product_category ||
                          "未知分类"}
                      </span>
                    </div>

                    <div className="category-value">
                      <strong>
                        {formatMoney(
                          item.revenue
                        )}
                      </strong>

                      <small>
                        {Number(
                          item.order_count || 0
                        ).toLocaleString()}{" "}
                        个订单
                      </small>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;