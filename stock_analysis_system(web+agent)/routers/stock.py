import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from models.stock_models import AnalyzeRequest, SimpleAnalyzeRequest
from services.stock_analyzer import StockAnalyzer

router = APIRouter()
analyzer = StockAnalyzer()


async def full_analyze_response(stock_code: str, market_cn: str, days: int) -> JSONResponse:
    start = time.time()
    result = await analyzer.analyze(stock_code.strip(), market_cn, days)
    elapsed = int((time.time() - start) * 1000)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "分析失败"))

    if "metadata" in result:
        result["metadata"]["processing_time_ms"] = elapsed

    return JSONResponse(content=result)


async def simple_analyze_response(stock_code: str, market_cn: str, days: int) -> JSONResponse:
    start = time.time()
    result = await analyzer.analyze(stock_code.strip(), market_cn, days)
    elapsed = int((time.time() - start) * 1000)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", "分析失败"))

    d = result["data"]
    rt = d.get("实时行情", {})
    vol = d.get("成交量额", {})
    tech = d.get("技术指标", {})
    ma = tech.get("均线", {})
    rsi = tech.get("rsi", {})
    rec = d.get("投资建议", {})
    basic = d.get("基础信息", {})
    hist = d.get("历史数据", {})

    simple = {
        "status": "success",
        "stock_code": d.get("stock_code"),
        "stock_name": d.get("stock_name"),
        "market": d.get("market"),
        "currency": basic.get("currency"),
        "current_price": rt.get("current_price"),
        "change": rt.get("change"),
        "change_percent": rt.get("change_percent"),
        "open": rt.get("open"),
        "close": rt.get("close"),
        "high": rt.get("high"),
        "low": rt.get("low"),
        "volume": vol.get("volume"),
        "amount": vol.get("amount"),
        "technical_indicators": {
            "ma5": ma.get("ma5"),
            "ma10": ma.get("ma10"),
            "ma20": ma.get("ma20"),
            "rsi": rsi.get("rsi12"),
        },
        "recommendation": rec.get("recommendation"),
        "history": [
            {
                "date": h.get("date"),
                "open": h.get("open"),
                "close": h.get("close"),
                "high": h.get("high"),
                "low": h.get("low"),
                "volume": h.get("volume"),
            }
            for h in hist.get("history", [])
        ],
        "metadata": {
            "api_version": "1.0.0",
            "processing_time_ms": elapsed,
            "data_source": "Baostock + AKshare",
        },
    }
    return JSONResponse(content=simple)


@router.post("/stock/analyze")
async def analyze_stock(body: AnalyzeRequest):
    """
    全球股票综合分析（POST + JSON）

    请求体：`stock_code`, `market`（**美股 / A股 / 港股**，或 US / CN / HK）, `days`
    """
    return await full_analyze_response(body.stock_code, body.market, body.days)


@router.post("/stock/simple")
async def analyze_stock_simple(body: SimpleAnalyzeRequest):
    """
    简易版股票分析（POST + JSON）—— 仅返回核心字段：
    行情快照 + MA5/MA10/MA20/RSI + 投资建议 + 历史K线
    """
    return await simple_analyze_response(body.stock_code, body.market, body.days)


@router.get("/cache/clear")
async def clear_yf_cache():
    """清空 yfinance 内存缓存（调试用）。"""
    from services.yfinance_utils import clear_cache

    clear_cache()
    return {"status": "ok", "message": "缓存已清空，下次查询将重新拉取数据"}


@router.get("/stock/markets")
async def get_supported_markets():
    """返回支持的市场和示例代码"""
    return {
        "markets": [
            {
                "code": "US",
                "name": "美股",
                "description": "美国股票市场（NYSE/NASDAQ）",
                "examples": ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"],
                "format": "英文字母，1-5位",
            },
            {
                "code": "CN",
                "name": "A股",
                "description": "中国A股市场（上交所/深交所）",
                "examples": ["000001", "600000", "300750", "688599"],
                "format": "6位数字",
            },
            {
                "code": "HK",
                "name": "港股",
                "description": "香港股票市场（港交所）",
                "examples": ["00700", "09988", "03690", "01810"],
                "format": "5位数字",
            },
        ]
    }
