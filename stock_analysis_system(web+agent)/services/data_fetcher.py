"""
数据获取服务（Baostock + AKshare，无其他第三方 API 依赖）
  - A股：Baostock 历史K线 + 财务指标 / AKshare 实时行情 + 资金流向
  - 美股：AKshare stock_us_daily（新浪，主）+ stock_us_hist（东方财富，备）
  - 港股：AKshare stock_hk_daily（新浪，主）+ stock_hk_hist（东方财富，备）
  - 实时价格：AKshare spot 接口 → K线数据兜底
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from services.baostock_client import (
    a_code_to_bs, bs_to_df, ensure_login, last_quarter,
)

logger = logging.getLogger(__name__)

# ── 简单内存缓存（减少重复请求） ──────────────────────────────
_cache_lock = threading.Lock()
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 180  # 秒


def _cache_get(key: str):
    with _cache_lock:
        ent = _cache.get(key)
        if ent and ent[0] > time.time():
            return ent[1]
    return None


def _cache_set(key: str, val, ttl: int = _CACHE_TTL):
    with _cache_lock:
        _cache[key] = (time.time() + ttl, val)


# ── 通用工具 ───────────────────────────────────────────────────
def _sf(val, default=None):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


def _si(val, default=None):
    try:
        if val is None:
            return default
        return int(val)
    except Exception:
        return default


def _empty_fund_flow() -> dict:
    today = {k: None for k in [
        "main_net_inflow", "main_inflow", "main_outflow", "main_inflow_ratio",
        "retail_net_inflow", "retail_inflow", "retail_outflow",
        "super_large_inflow", "large_inflow", "medium_inflow", "small_inflow",
    ]}
    return {
        "今日流向": today,
        "5日流向":  {"main_net_inflow": None, "trend": "N/A", "流入天数": None},
        "20日流向": {"main_net_inflow": None, "trend": "N/A", "流入天数": None},
        "北向资金": {k: None for k in [
            "north_inflow_today", "north_holding_ratio",
            "north_holding_shares", "north_5d_inflow", "north_20d_inflow",
        ]},
    }


def _empty_analyst() -> dict:
    return {
        "summary": {
            "total_analysts": 0, "strong_buy": 0, "buy": 0,
            "hold": 0, "sell": 0, "strong_sell": 0, "consensus": "N/A",
        },
        "target_price": {"current": None, "high": None, "low": None,
                         "median": None, "upside": None},
        "ratings_trend": "N/A", "recent_upgrades": 0, "recent_downgrades": 0,
    }


def _empty_institutional() -> dict:
    return {
        "institutional_holding_ratio": None,
        "institutional_holding_shares": None,
        "institution_count": None,
        "recent_quarter_change": None,
        "top_holders": [],
    }


def _norm_ohlcv(raw: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """重命名列 + 将 Date 列设为索引，返回标准 DataFrame。"""
    raw = raw.rename(columns=col_map)
    if "Date" in raw.columns:
        raw["Date"] = pd.to_datetime(raw["Date"])
        raw = raw.set_index("Date")
    elif raw.index.name in ("date", "Date"):
        raw.index = pd.to_datetime(raw.index)
        raw.index.name = "Date"
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col in raw.columns:
            raw[col] = pd.to_numeric(raw[col], errors="coerce")
    return raw.dropna(subset=["Close"])


# ═══════════════════════════════════════════════════════════════
#  A 股（Baostock 历史 + AKshare 实时）
# ═══════════════════════════════════════════════════════════════
def fetch_a_stock(code: str, days: int) -> dict:
    import akshare as ak
    import baostock as bs

    ensure_login()
    bs_code = a_code_to_bs(code)

    # ── 历史 K 线 (Baostock) ─────────────────────────────────
    end_dt   = datetime.today()
    start_dt = end_dt - timedelta(days=days + 250)
    fields   = "date,open,high,low,close,volume,amount,turn,pctChg"
    rs = bs.query_history_k_data_plus(
        bs_code, fields,
        start_date=start_dt.strftime("%Y-%m-%d"),
        end_date=end_dt.strftime("%Y-%m-%d"),
        frequency="d", adjustflag="2",
    )
    hist_df = bs_to_df(rs)
    if hist_df.empty:
        raise ValueError(f"Baostock 无法获取 {code} 历史数据，请确认代码正确")

    hist_df["Date"] = pd.to_datetime(hist_df["date"])
    hist_df.set_index("Date", inplace=True)
    hist_df.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
        "amount": "Amount", "turn": "Turnover", "pctChg": "Pct_change",
    }, inplace=True)

    # ── 实时行情 (AKshare stock_zh_a_spot_em) ───────────────
    stock_name = code
    price = open_p = high = low = pre_close = None
    change = change_pct = turnover = vol_ratio = 0.0
    pe_ttm = pb = market_cap = circ_cap = None

    try:
        cached = _cache_get("a_spot")
        if cached is None:
            spot_df = ak.stock_zh_a_spot_em()
            _cache_set("a_spot", spot_df, ttl=60)
        else:
            spot_df = cached

        row = spot_df[spot_df["代码"] == code]
        if not row.empty:
            r = row.iloc[0]
            stock_name = str(r.get("名称", code))
            price      = _sf(r.get("最新价"))
            open_p     = _sf(r.get("今开"))
            high       = _sf(r.get("最高"))
            low        = _sf(r.get("最低"))
            pre_close  = _sf(r.get("昨收"))
            change     = _sf(r.get("涨跌额"), 0.0)
            change_pct = _sf(r.get("涨跌幅"), 0.0)
            turnover   = _sf(r.get("换手率"))
            vol_ratio  = _sf(r.get("量比"), 1.0)
            pe_ttm     = _sf(r.get("市盈率-动态"))
            pb         = _sf(r.get("市净率"))
            market_cap = _sf(r.get("总市值"))
            circ_cap   = _sf(r.get("流通市值"))
    except Exception as e:
        logger.warning("A股实时行情获取失败: %s", e)

    # K 线兜底
    if price is None:
        price     = _sf(hist_df["Close"].iloc[-1])
        pre_close = _sf(hist_df["Close"].iloc[-2]) if len(hist_df) > 1 else price
        open_p    = _sf(hist_df["Open"].iloc[-1])
        high      = _sf(hist_df["High"].iloc[-1])
        low       = _sf(hist_df["Low"].iloc[-1])
        change    = round(price - pre_close, 2) if price and pre_close else 0.0
        change_pct = round(change / pre_close * 100, 2) if pre_close else 0.0

    vol = _si(hist_df["Volume"].iloc[-1])
    amount = _sf(hist_df.get("Amount", pd.Series([0])).iloc[-1]) or (vol * price if vol and price else None)
    amplitude = round((high - low) / pre_close * 100, 2) if pre_close and high and low else None

    limit_up   = round(pre_close * 1.10, 2) if pre_close else None
    limit_down = round(pre_close * 0.90, 2) if pre_close else None
    if code.startswith(("30", "68")):
        limit_up   = round(pre_close * 1.20, 2) if pre_close else None
        limit_down = round(pre_close * 0.80, 2) if pre_close else None

    exchange = "上交所" if bs_code.startswith("sh") else "深交所"

    # ── 基础信息 (Baostock) ──────────────────────────────────
    try:
        rs2 = bs.query_stock_basic(code=bs_code)
        info_df = bs_to_df(rs2)
        industry = info_df["industry"].iloc[0] if not info_df.empty and "industry" in info_df.columns else "N/A"
        ipoDate  = str(info_df["ipoDate"].iloc[0]) if not info_df.empty and "ipoDate" in info_df.columns else "N/A"
    except Exception:
        industry = ipoDate = "N/A"

    basic = {
        "exchange": exchange,
        "industry": industry,
        "sector": "N/A",
        "currency": "CNY",
        "listing_date": ipoDate,
        "isin": "N/A",
        "website": "N/A",
    }

    realtime = {
        "current_price": round(price, 3) if price else None,
        "open": round(open_p, 3) if open_p else None,
        "close": round(price, 3) if price else None,
        "high": round(high, 3) if high else None,
        "low": round(low, 3) if low else None,
        "pre_close": round(pre_close, 3) if pre_close else None,
        "change": round(change, 3),
        "change_percent": change_pct,
        "amplitude": amplitude,
        "turnover_rate": turnover,
        "volume_ratio": vol_ratio,
        "limit_up": limit_up,
        "limit_down": limit_down,
    }

    vol_ma5  = int(hist_df["Volume"].tail(5).mean())
    vol_ma10 = int(hist_df["Volume"].tail(10).mean())
    vol_ma20 = int(hist_df["Volume"].tail(20).mean())
    avg_amount_20 = _sf(hist_df["Amount"].tail(20).mean()) if "Amount" in hist_df.columns else None

    volume_info = {
        "volume": vol,
        "volume_ma5": vol_ma5,
        "volume_ma10": vol_ma10,
        "amount": round(amount, 0) if amount else None,
        "avg_volume_20d": vol_ma20,
        "avg_amount_20d": round(avg_amount_20, 0) if avg_amount_20 else None,
    }

    valuation = {
        "market_cap": market_cap,
        "market_cap_usd": None,
        "circulating_market_cap": circ_cap,
        "pe_ratio_static": pe_ttm,
        "pe_ttm": pe_ttm,
        "pb_ratio": pb,
        "ps_ratio_ttm": None, "pc_ratio": None, "ev_ebitda": None,
        "dividend_yield": None, "dividend_per_share": None, "payout_ratio": None,
    }

    # ── 财务指标 (Baostock) ──────────────────────────────────
    financials = _fetch_a_financials(bs_code)

    # ── 资金流向 (AKshare) ───────────────────────────────────
    fund_flow = _fetch_a_fund_flow(code, bs_code)

    return {
        "stock_name": stock_name,
        "basic": basic,
        "realtime": realtime,
        "volume_info": volume_info,
        "valuation": valuation,
        "financials": financials,
        "analyst_ratings": _empty_analyst(),
        "institutional": _empty_institutional(),
        "fund_flow": fund_flow,
        "history_df": hist_df,
    }


def _fetch_a_financials(bs_code: str) -> dict:
    """从 Baostock 获取A股最新季度财务指标。"""
    import baostock as bs

    year, quarter = last_quarter()
    result = {k: None for k in [
        "eps_ttm", "eps_diluted", "bvps", "roe", "roa", "roic",
        "gross_margin", "operating_margin", "net_margin", "ebitda_margin",
        "revenue_ttm", "revenue_growth_yoy", "revenue_growth_3y",
        "profit_ttm", "profit_growth_yoy", "profit_growth_3y",
        "debt_to_equity", "current_ratio", "quick_ratio", "free_cash_flow",
    ]}

    try:
        rs = bs.query_profit_data(code=bs_code, year=year, quarter=quarter)
        df = bs_to_df(rs)
        if not df.empty:
            r = df.iloc[0]
            result["roe"]          = _sf(r.get("roeAvg"))
            result["net_margin"]   = _sf(r.get("npMargin"))
            result["gross_margin"] = _sf(r.get("gpMargin"))
            result["eps_ttm"]      = _sf(r.get("epsTTM"))
            result["profit_ttm"]   = _sf(r.get("netProfit"))
            result["revenue_ttm"]  = _sf(r.get("MBRevenue"))
    except Exception as e:
        logger.debug("profit_data 失败: %s", e)

    try:
        rs = bs.query_balance_data(code=bs_code, year=year, quarter=quarter)
        df = bs_to_df(rs)
        if not df.empty:
            r = df.iloc[0]
            result["current_ratio"]  = _sf(r.get("liquidityRatio"))
            result["quick_ratio"]    = _sf(r.get("quickRatio"))
            result["debt_to_equity"] = _sf(r.get("liabilityToAsset"))
    except Exception as e:
        logger.debug("balance_data 失败: %s", e)

    try:
        rs = bs.query_growth_data(code=bs_code, year=year, quarter=quarter)
        df = bs_to_df(rs)
        if not df.empty:
            r = df.iloc[0]
            result["revenue_growth_yoy"] = _sf(r.get("YOYNI"))
            result["profit_growth_yoy"]  = _sf(r.get("YOYEPSBasic"))
    except Exception as e:
        logger.debug("growth_data 失败: %s", e)

    try:
        rs = bs.query_dupont_data(code=bs_code, year=year, quarter=quarter)
        df = bs_to_df(rs)
        if not df.empty:
            r = df.iloc[0]
            result["roa"] = _sf(r.get("dupontROA"))
    except Exception as e:
        logger.debug("dupont_data 失败: %s", e)

    return result


def _fetch_a_fund_flow(code: str, bs_code: str) -> dict:
    """从 AKshare 获取A股资金流向。"""
    try:
        import akshare as ak
        market = "sh" if bs_code.startswith("sh") else "sz"
        df = ak.stock_individual_fund_flow(stock=code, market=market)
        if df is None or df.empty:
            return _empty_fund_flow()

        latest = df.iloc[-1]
        main_net = _sf(latest.get("主力净流入-净额"))
        main_in  = _sf(latest.get("主力净流入-流入"))
        main_out = _sf(latest.get("主力净流入-流出"))
        main_r   = _sf(latest.get("主力净流入-净占比"))

        d5  = df.tail(5)
        d20 = df.tail(20)
        col = "主力净流入-净额"
        mn5  = _sf(d5[col].sum())  if col in d5.columns  else None
        mn20 = _sf(d20[col].sum()) if col in d20.columns else None

        return {
            "今日流向": {
                "main_net_inflow":    main_net,
                "main_inflow":        main_in,
                "main_outflow":       main_out,
                "main_inflow_ratio":  main_r,
                "retail_net_inflow":  _sf(latest.get("散户净流入-净额")),
                "retail_inflow":      None,
                "retail_outflow":     None,
                "super_large_inflow": _sf(latest.get("超大单净流入-流入")),
                "large_inflow":       _sf(latest.get("大单净流入-流入")),
                "medium_inflow":      _sf(latest.get("中单净流入-流入")),
                "small_inflow":       _sf(latest.get("小单净流入-流入")),
            },
            "5日流向":  {"main_net_inflow": mn5,  "trend": "N/A", "流入天数": None},
            "20日流向": {"main_net_inflow": mn20, "trend": "N/A", "流入天数": None},
            "北向资金": {k: None for k in [
                "north_inflow_today", "north_holding_ratio",
                "north_holding_shares", "north_5d_inflow", "north_20d_inflow",
            ]},
        }
    except Exception as e:
        logger.debug("A股资金流向失败: %s", e)
        return _empty_fund_flow()


# ═══════════════════════════════════════════════════════════════
#  美 股（AKshare stock_us_daily 新浪主 + stock_us_hist EM备）
# ═══════════════════════════════════════════════════════════════
def fetch_us_stock(symbol: str, days: int) -> dict:
    import akshare as ak

    symbol     = symbol.upper()
    hist_df    = pd.DataFrame()
    errors: list[str] = []

    # ── 主路径：AKshare stock_us_daily（新浪财经，国内稳定） ──
    try:
        raw = ak.stock_us_daily(symbol=symbol, adjust="qfq")
        if raw is not None and not raw.empty:
            hist_df = _norm_ohlcv(raw, {
                "date": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
            })
            logger.info("美股 %s via AKshare stock_us_daily: %d bars", symbol, len(hist_df))
    except Exception as e:
        errors.append(f"stock_us_daily: {e}")
        logger.info("stock_us_daily 失败，尝试 stock_us_hist: %s", e)

    # ── 备用：AKshare stock_us_hist（东方财富） ──────────────
    if hist_df.empty:
        em_code    = f"105.{symbol}"
        end_date   = datetime.today().strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=days + 250)).strftime("%Y%m%d")
        for prefix in ("105", "106", "107"):
            em = f"{prefix}.{symbol}"
            try:
                raw = ak.stock_us_hist(
                    symbol=em, period="daily",
                    start_date=start_date, end_date=end_date, adjust="qfq",
                )
                if raw is not None and not raw.empty:
                    hist_df = _norm_ohlcv(raw, {
                        "日期": "Date", "开盘": "Open", "收盘": "Close",
                        "最高": "High", "最低": "Low", "成交量": "Volume",
                        "成交额": "Amount", "涨跌幅": "Pct_change",
                    })
                    em_code = em
                    logger.info("美股 %s via stock_us_hist(%s): %d bars", symbol, em, len(hist_df))
                    break
            except Exception as e2:
                errors.append(f"stock_us_hist({em}): {e2}")

    if hist_df.empty:
        raise ValueError(
            f"无法获取美股 {symbol} 历史数据，请确认股票代码正确。"
            f"错误详情: {'; '.join(errors)}"
        )

    # ── 实时行情：AKshare spot → K 线兜底 ───────────────────
    stock_name = symbol
    price = open_p = high = low = pre_close = None
    vol   = None
    pe_ttm = pb = market_cap = None
    currency = "USD"

    try:
        cached = _cache_get("us_spot")
        if cached is None:
            spot_df = ak.stock_us_spot_em()
            _cache_set("us_spot", spot_df, ttl=120)
        else:
            spot_df = cached
        if not spot_df.empty and "代码" in spot_df.columns:
            mask = spot_df["代码"].str.upper().str.endswith(f".{symbol}")
            if mask.any():
                r = spot_df.loc[mask].iloc[0]
                stock_name = str(r.get("名称", symbol))
                price      = _sf(r.get("最新价"))
                open_p     = _sf(r.get("今开"))
                high       = _sf(r.get("最高"))
                low        = _sf(r.get("最低"))
                pe_ttm     = _sf(r.get("市盈率(动)") or r.get("市盈率"))
                pb         = _sf(r.get("市净率"))
                vol        = _si(r.get("成交量(手)") or r.get("成交量"))
    except Exception as e:
        logger.debug("美股实时行情失败: %s", e)

    # K 线最终兜底
    if price is None:
        price = _sf(hist_df["Close"].iloc[-1])
    if pre_close is None:
        pre_close = _sf(hist_df["Close"].iloc[-2]) if len(hist_df) > 1 else price
    if open_p is None:
        open_p = _sf(hist_df["Open"].iloc[-1])
    if high is None:
        high = _sf(hist_df["High"].iloc[-1])
    if low is None:
        low = _sf(hist_df["Low"].iloc[-1])
    if vol is None:
        vol = _si(hist_df["Volume"].iloc[-1])

    amount     = vol * price if vol and price else None
    change     = round(price - pre_close, 4) if price and pre_close else 0.0
    change_pct = round(change / pre_close * 100, 2) if pre_close else 0.0
    amplitude  = round((high - low) / pre_close * 100, 2) if high and low and pre_close else None
    avg_vol_10 = int(hist_df["Volume"].tail(10).mean()) if not hist_df.empty else 0
    vol_ratio  = round(vol / avg_vol_10, 2) if avg_vol_10 and vol else 1.0

    vol_ma5  = int(hist_df["Volume"].tail(5).mean())
    vol_ma10 = int(hist_df["Volume"].tail(10).mean())
    vol_ma20 = int(hist_df["Volume"].tail(20).mean())

    return {
        "stock_name": stock_name,
        "basic": {
            "exchange": "NASDAQ/NYSE", "industry": "N/A", "sector": "N/A",
            "currency": currency, "listing_date": "N/A", "isin": "N/A", "website": "N/A",
        },
        "realtime": {
            "current_price": round(price, 3) if price else None,
            "open":      round(open_p, 3) if open_p else None,
            "close":     round(price, 3) if price else None,
            "high":      round(high, 3) if high else None,
            "low":       round(low, 3) if low else None,
            "pre_close": round(pre_close, 3) if pre_close else None,
            "change":    round(change, 3),
            "change_percent": change_pct,
            "amplitude": amplitude,
            "turnover_rate": None,
            "volume_ratio": vol_ratio,
            "limit_up": None, "limit_down": None,
        },
        "volume_info": {
            "volume": vol, "volume_ma5": vol_ma5, "volume_ma10": vol_ma10,
            "amount": round(amount, 0) if amount else None,
            "avg_volume_20d": vol_ma20, "avg_amount_20d": None,
        },
        "valuation": {
            "market_cap": market_cap, "market_cap_usd": market_cap,
            "circulating_market_cap": None,
            "pe_ratio_static": pe_ttm, "pe_ttm": pe_ttm, "pb_ratio": pb,
            "ps_ratio_ttm": None, "pc_ratio": None, "ev_ebitda": None,
            "dividend_yield": None, "dividend_per_share": None, "payout_ratio": None,
        },
        "financials": {k: None for k in [
            "eps_ttm", "eps_diluted", "bvps", "roe", "roa", "roic",
            "gross_margin", "operating_margin", "net_margin", "ebitda_margin",
            "revenue_ttm", "revenue_growth_yoy", "revenue_growth_3y",
            "profit_ttm", "profit_growth_yoy", "profit_growth_3y",
            "debt_to_equity", "current_ratio", "quick_ratio", "free_cash_flow",
        ]},
        "analyst_ratings": _empty_analyst(),
        "institutional":   _empty_institutional(),
        "fund_flow":        _empty_fund_flow(),
        "history_df":       hist_df,
    }


# ═══════════════════════════════════════════════════════════════
#  港 股（AKshare stock_hk_daily 新浪主 + stock_hk_hist EM备）
# ═══════════════════════════════════════════════════════════════
def fetch_hk_stock(code: str, days: int) -> dict:
    import akshare as ak

    hk_code    = code.zfill(5)
    hist_df    = pd.DataFrame()
    errors: list[str] = []

    # ── 主路径：AKshare stock_hk_daily（新浪财经，国内稳定） ──
    try:
        raw = ak.stock_hk_daily(symbol=hk_code, adjust="qfq")
        if raw is not None and not raw.empty:
            hist_df = _norm_ohlcv(raw, {
                "date": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "volume": "Volume",
                "amount": "Amount",
            })
            logger.info("港股 %s via AKshare stock_hk_daily: %d bars", hk_code, len(hist_df))
    except Exception as e:
        errors.append(f"stock_hk_daily: {e}")
        logger.info("stock_hk_daily 失败，尝试 stock_hk_hist: %s", e)

    # ── 备用：AKshare stock_hk_hist（东方财富） ──────────────
    if hist_df.empty:
        end_date   = datetime.today().strftime("%Y%m%d")
        start_date = (datetime.today() - timedelta(days=days + 250)).strftime("%Y%m%d")
        try:
            raw = ak.stock_hk_hist(
                symbol=hk_code, period="daily",
                start_date=start_date, end_date=end_date, adjust="qfq",
            )
            if raw is not None and not raw.empty:
                hist_df = _norm_ohlcv(raw, {
                    "日期": "Date", "开盘": "Open", "收盘": "Close",
                    "最高": "High", "最低": "Low", "成交量": "Volume",
                    "成交额": "Amount", "涨跌幅": "Pct_change",
                })
                logger.info("港股 %s via stock_hk_hist: %d bars", hk_code, len(hist_df))
        except Exception as e2:
            errors.append(f"stock_hk_hist: {e2}")

    if hist_df.empty:
        raise ValueError(
            f"无法获取港股 {code} 历史数据，请确认股票代码正确。"
            f"错误详情: {'; '.join(errors)}"
        )

    # ── 实时行情：AKshare spot → K 线兜底 ───────────────────
    stock_name = hk_code
    price = open_p = high = low = pre_close = None
    vol   = amount_spot = None
    pe_ttm = pb = market_cap = None

    try:
        cached = _cache_get("hk_spot")
        if cached is None:
            spot_df = ak.stock_hk_spot_em()
            _cache_set("hk_spot", spot_df, ttl=60)
        else:
            spot_df = cached
        row = spot_df[spot_df["代码"] == hk_code]
        if not row.empty:
            r = row.iloc[0]
            stock_name   = str(r.get("名称", hk_code))
            price        = _sf(r.get("最新价"))
            open_p       = _sf(r.get("今开"))
            high         = _sf(r.get("最高"))
            low          = _sf(r.get("最低"))
            pe_ttm       = _sf(r.get("市盈率(动)") or r.get("市盈率"))
            pb           = _sf(r.get("市净率"))
            market_cap   = _sf(r.get("总市值"))
            vol          = _si(r.get("成交量"))
            amount_spot  = _sf(r.get("成交额"))
    except Exception as e:
        logger.debug("港股实时行情失败: %s", e)

    # K 线最终兜底
    if price is None:
        price = _sf(hist_df["Close"].iloc[-1])
    if pre_close is None:
        pre_close = _sf(hist_df["Close"].iloc[-2]) if len(hist_df) > 1 else price
    if open_p is None:
        open_p = _sf(hist_df["Open"].iloc[-1])
    if high is None:
        high = _sf(hist_df["High"].iloc[-1])
    if low is None:
        low = _sf(hist_df["Low"].iloc[-1])
    if vol is None:
        vol = _si(hist_df["Volume"].iloc[-1])

    amount     = amount_spot or (vol * price if vol and price else None)
    change     = round(price - pre_close, 4) if price and pre_close else 0.0
    change_pct = round(change / pre_close * 100, 2) if pre_close else 0.0
    amplitude  = round((high - low) / pre_close * 100, 2) if high and low and pre_close else None

    vol_ma5  = int(hist_df["Volume"].tail(5).mean())
    vol_ma10 = int(hist_df["Volume"].tail(10).mean())
    vol_ma20 = int(hist_df["Volume"].tail(20).mean())

    return {
        "stock_name": stock_name,
        "basic": {
            "exchange": "香港交易所", "industry": "N/A", "sector": "N/A",
            "currency": "HKD", "listing_date": "N/A", "isin": "N/A", "website": "N/A",
        },
        "realtime": {
            "current_price": round(price, 3) if price else None,
            "open":      round(open_p, 3) if open_p else None,
            "close":     round(price, 3) if price else None,
            "high":      round(high, 3) if high else None,
            "low":       round(low, 3) if low else None,
            "pre_close": round(pre_close, 3) if pre_close else None,
            "change":    round(change, 3),
            "change_percent": change_pct,
            "amplitude": amplitude,
            "turnover_rate": None,
            "volume_ratio": None,
            "limit_up": None, "limit_down": None,
        },
        "volume_info": {
            "volume": vol, "volume_ma5": vol_ma5, "volume_ma10": vol_ma10,
            "amount": round(amount, 0) if amount else None,
            "avg_volume_20d": vol_ma20, "avg_amount_20d": None,
        },
        "valuation": {
            "market_cap": market_cap, "market_cap_usd": None,
            "circulating_market_cap": None,
            "pe_ratio_static": pe_ttm, "pe_ttm": pe_ttm, "pb_ratio": pb,
            "ps_ratio_ttm": None, "pc_ratio": None, "ev_ebitda": None,
            "dividend_yield": None, "dividend_per_share": None, "payout_ratio": None,
        },
        "financials": {k: None for k in [
            "eps_ttm", "eps_diluted", "bvps", "roe", "roa", "roic",
            "gross_margin", "operating_margin", "net_margin", "ebitda_margin",
            "revenue_ttm", "revenue_growth_yoy", "revenue_growth_3y",
            "profit_ttm", "profit_growth_yoy", "profit_growth_3y",
            "debt_to_equity", "current_ratio", "quick_ratio", "free_cash_flow",
        ]},
        "analyst_ratings": _empty_analyst(),
        "institutional":   _empty_institutional(),
        "fund_flow":        _empty_fund_flow(),
        "history_df":       hist_df,
    }
