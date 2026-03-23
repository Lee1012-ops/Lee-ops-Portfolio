# 全球股票分析系统

支持 **A股、美股、港股** 的综合分析平台，包含实时行情、技术指标、财务分析、风险评估、投资建议等模块。

## 项目结构

```
stock_analysis_system/
├── main.py                        # FastAPI 主程序入口
├── requirements.txt               # Python 依赖
├── 启动服务.bat                   # Windows 一键启动脚本
├── models/
│   ├── market.py                  # Market 枚举 US/CN/HK
│   └── stock_models.py            # POST 请求体
├── routers/
│   └── stock.py                   # API 路由
├── services/
│   ├── data_fetcher.py            # 数据获取（yfinance / akshare）
│   ├── technical_analyzer.py      # 技术指标计算
│   └── stock_analyzer.py          # 综合分析协调器
├── templates/
│   └── index.html                 # 前端单页应用
└── static/
    ├── css/style.css              # 样式
    └── js/app.js                  # 前端逻辑
```

## 快速启动

### 方式一：双击 `启动服务.bat`

### 方式二：命令行
```bash
python main.py
```

然后在浏览器打开：**http://localhost:8000**

## API 文档

启动后访问：**http://localhost:8000/docs**

### 核心接口（POST + JSON）

`Content-Type: application/json`，请求体字段：`stock_code`、`market`、`days`。

- **`market`** 推荐使用中文：**`美股`**、**`A股`**、**`港股`**；也兼容英文 **`US`**、**`CN`**、**`HK`**（不区分大小写）。

```
POST /api/stock/analyze
POST /api/stock/simple
```

示例（curl）：

```bash
curl -X POST "http://localhost:8000/api/stock/simple" \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"AAPL","market":"美股","days":30}'
```

### 示例

| 市场 | 代码示例 | 说明 |
|------|---------|------|
| 美股 | AAPL / TSLA / NVDA | 英文代码 |
| A股  | 000001 / 600000 / 300750 | 6位数字 |
| 港股 | 00700 / 09988 / 03690 | 5位数字 |

## 功能模块

| 模块 | 内容 |
|------|------|
| 实时行情 | 价格、涨跌、振幅、换手率、量比 |
| 成交量额 | 成交量/额、MA5/MA10均量 |
| 估值指标 | PE/PB/PS、市值、股息率 |
| 财务指标 | EPS、ROE/ROA、利润率、增速、现金流 |
| 技术指标 | MA均线、MACD、KDJ、RSI、BOLL、ATR、SAR、CCI |
| 风险评估 | 夏普/索提诺/卡玛比率、VaR、最大回撤 |
| 资金流向 | 主力/散户净流入、北向资金（A股） |
| 机构持仓 | 机构持仓比例、Top3持仓机构 |
| 分析师评级 | 评级分布、目标价区间 |
| 投资建议 | 综合评分、买入/卖出建议、投资逻辑、风险提示 |
| 历史数据 | K线数据表格 + 走势图 |

## 数据来源

- **美股**：yfinance（Yahoo Finance）
- **A股**：akshare（东方财富数据）
- **港股**：yfinance（Yahoo Finance .HK）

## Yahoo 限流（Too Many Requests）

若出现 **「数据获取失败: Too Many Requests / Rate limited」**：

1. **等待 1～3 分钟** 后再点「分析」，不要连续快速请求。
2. 程序已内置 **指数退避重试** 与 **约 120 秒内存缓存**（同一标的短时间内重复查询会减轻压力）。
3. 默认已 **关闭** 美股的「分析师推荐 / 机构持仓」等额外 Yahoo 请求；若需要可设置环境变量后再启动：
   - `set STOCK_YF_FULL=1`（Windows CMD）再运行 `python main.py`
4. 可调参数（可选）：
   - `STOCK_YF_CACHE_SEC`：缓存秒数，默认 `120`
   - `STOCK_YF_MAX_RETRIES`：限流时最大重试次数，默认 `6`
   - `STOCK_YF_RETRY_BASE`：首次重试基础等待秒数，默认 `2.0`

## 注意事项

- 数据来自免费公开接口，部分字段（如A股详细财务）可能暂无数据显示为 `—`
- 投资建议仅供参考，不构成实际投资建议
- 建议在网络条件良好时使用，部分数据需访问境外接口
