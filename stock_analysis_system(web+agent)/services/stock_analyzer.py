"""
股票综合分析服务：协调数据获取、技术分析、风险评估和投资建议
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from services.data_fetcher import fetch_us_stock, fetch_a_stock, fetch_hk_stock
from services.technical_analyzer import calculate_technical_indicators
from services.yfinance_utils import get_ticker_history

logger = logging.getLogger(__name__)

MARKET_MAP = {
    "美股": fetch_us_stock,
    "A股": fetch_a_stock,
    "港股": fetch_hk_stock,
}


def _safe_float(val, default=None):
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except Exception:
        return default


class StockAnalyzer:
    async def analyze(self, stock_code: str, market: str, days: int = 30) -> dict:
        if market not in MARKET_MAP:
            return {"status": "error", "message": f"不支持的市场类型: {market}，请使用 A股/美股/港股"}

        try:
            fetcher = MARKET_MAP[market]
            raw = fetcher(stock_code, days)
        except ValueError as e:
            return {"status": "error", "message": str(e)}
        except Exception as e:
            logger.exception("数据获取失败")
            msg = str(e)
            if "too many requests" in msg.lower() or "rate limit" in msg.lower():
                msg += "。Yahoo 接口限流：请等待 1～3 分钟后再试，避免连续快速点击分析；也可稍后在网络稳定时重试。"
            return {"status": "error", "message": f"数据获取失败: {msg}"}

        hist_df: pd.DataFrame = raw.pop("history_df")

        try:
            tech = calculate_technical_indicators(hist_df)
        except Exception as e:
            logger.warning("技术指标计算失败: %s", e)
            tech = {}

        try:
            risk = self._calculate_risk(hist_df, market)
        except Exception as e:
            logger.warning("风险评估失败: %s", e)
            risk = {}

        history_data = self._build_history(hist_df, days)

        try:
            market_compare = self._market_comparison(hist_df, market)
        except Exception as e:
            logger.warning("市场对比计算失败: %s", e)
            market_compare = {}

        try:
            recommendation = self._generate_recommendation(
                raw.get("realtime", {}),
                raw.get("valuation", {}),
                raw.get("financials", {}),
                tech,
                risk,
            )
        except Exception as e:
            logger.warning("投资建议生成失败: %s", e)
            recommendation = {}

        now = datetime.utcnow()
        tz_map = {"美股": "America/New_York", "A股": "Asia/Shanghai", "港股": "Asia/Hong_Kong"}

        result = {
            "status": "success",
            "data": {
                "stock_code": stock_code,
                "stock_name": raw.get("stock_name", stock_code),
                "market": market,
                "基础信息": raw.get("basic", {}),
                "实时行情": raw.get("realtime", {}),
                "成交量额": raw.get("volume_info", {}),
                "估值指标": raw.get("valuation", {}),
                "财务指标": raw.get("financials", {}),
                "技术指标": tech,
                "风险评估": risk,
                "资金流向": raw.get("fund_flow", {}),
                "机构持仓": raw.get("institutional", {}),
                "分析师评级": raw.get("analyst_ratings", {}),
                "投资建议": recommendation,
                "历史数据": history_data,
                "市场对比": market_compare,
                "时间戳": {
                    "data_date": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "data_timezone": tz_map.get(market, "UTC"),
                    "update_time": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
                },
            },
            "metadata": {
                "api_version": "1.0.0",
                "processing_time_ms": None,
                "cache_hit": False,
                "data_source": "yfinance + akshare",
            },
        }
        return result

    # ─── 风险评估 ────────────────────────────────
    def _calculate_risk(self, hist: pd.DataFrame, market: str) -> dict:
        close = hist["Close"].astype(float)
        returns = close.pct_change().dropna()

        if len(returns) < 5:
            return {}

        daily_vol = float(returns.std()) * 100
        annual_vol = daily_vol * np.sqrt(252)

        # Max drawdown (1y / 3y)
        def max_dd(ret_series):
            cum = (1 + ret_series).cumprod()
            roll_max = cum.cummax()
            dd = (cum - roll_max) / roll_max
            return float(dd.min()) * 100

        returns_1y = returns.tail(252)
        returns_3y = returns.tail(756)
        mdd_1y = max_dd(returns_1y)
        mdd_3y = max_dd(returns_3y) if len(returns_3y) > 252 else mdd_1y

        risk_free = 0.04 / 252  # daily risk-free rate
        excess_ret = returns - risk_free

        # Sharpe
        sharpe_1y = float(returns_1y.mean() / (returns_1y.std() + 1e-9) * np.sqrt(252))
        sharpe_3y = float(returns_3y.mean() / (returns_3y.std() + 1e-9) * np.sqrt(252)) if len(returns_3y) > 252 else sharpe_1y

        # Sortino
        downside = returns[returns < 0].std() * np.sqrt(252)
        sortino = float(returns.mean() * 252 / (downside + 1e-9))

        # Calmar
        ann_ret = float((1 + returns.mean()) ** 252 - 1) * 100
        calmar = ann_ret / (abs(mdd_1y) + 1e-9)

        # VaR / CVaR (95%)
        var_95 = float(np.percentile(returns, 5)) * 100
        cvar_95 = float(returns[returns <= np.percentile(returns, 5)].mean()) * 100

        return {
            "beta": None,
            "alpha": None,
            "volatility_daily": round(daily_vol, 2),
            "volatility_annual": round(annual_vol, 2),
            "max_drawdown_1y": round(mdd_1y, 2),
            "max_drawdown_3y": round(mdd_3y, 2),
            "sharpe_ratio_1y": round(sharpe_1y, 2),
            "sharpe_ratio_3y": round(sharpe_3y, 2),
            "sortino_ratio": round(sortino, 2),
            "calmar_ratio": round(calmar, 2),
            "var_95": round(var_95, 2),
            "cvar_95": round(cvar_95, 2),
            "correlation_sp500": None,
            "correlation_nasdaq": None,
        }

    # ─── 历史数据整理 ─────────────────────────────
    def _build_history(self, hist: pd.DataFrame, days: int) -> dict:
        df = hist.tail(days).copy()
        records = []
        for date, row in df.iterrows():
            date_str = str(date)[:10] if hasattr(date, '__str__') else str(date)
            close = _safe_float(row.get("Close"))
            pre_close_series = hist["Close"]
            idx = hist.index.get_loc(date)
            pre_close = float(hist["Close"].iloc[idx - 1]) if idx > 0 else close
            chg_pct = round((close - pre_close) / pre_close * 100, 2) if pre_close and close else 0
            records.append({
                "date": date_str,
                "open": round(_safe_float(row.get("Open"), 0), 4),
                "close": round(close, 4) if close else None,
                "high": round(_safe_float(row.get("High"), 0), 4),
                "low": round(_safe_float(row.get("Low"), 0), 4),
                "volume": int(row.get("Volume", 0)),
                "amount": round(_safe_float(row.get("Amount") or row.get("Close", 0) * row.get("Volume", 0), 0), 0),
                "turnover": _safe_float(row.get("Turnover")),
                "change_percent": chg_pct,
            })

        close_series = df["Close"].dropna().astype(float)
        stats = {}
        if not close_series.empty:
            stats = {
                "avg_close": round(float(close_series.mean()), 4),
                "avg_volume": int(df["Volume"].mean()),
                "total_change_percent": round(
                    (float(close_series.iloc[-1]) - float(close_series.iloc[0])) / float(close_series.iloc[0]) * 100, 2
                ) if len(close_series) > 1 else 0,
                "max_close": round(float(close_series.max()), 4),
                "min_close": round(float(close_series.min()), 4),
                "volatility": round(float(close_series.pct_change().dropna().std()) * 100, 2),
            }

        return {
            "period": f"{days}d",
            "interval": "1d",
            "data_points": len(records),
            "history": records,
            "statistics": stats,
        }

    # ─── 市场对比（AKshare 指数基准） ────────────────────────
    def _market_comparison(self, hist: pd.DataFrame, market: str) -> dict:
        try:
            import akshare as ak
            from datetime import datetime, timedelta

            end_date   = datetime.today().strftime("%Y%m%d")
            start_date = (datetime.today() - timedelta(days=35)).strftime("%Y%m%d")

            if market == "A股":
                bench_name = "上证指数"
                bench_df = ak.stock_zh_index_daily(symbol="sh000001")
                if bench_df is not None and not bench_df.empty:
                    bench_df = bench_df.tail(30)
            elif market == "港股":
                bench_name = "恒生指数"
                bench_df = ak.stock_hk_index_daily_em(symbol="恒生指数")
                if bench_df is not None and not bench_df.empty:
                    bench_df = bench_df.tail(30)
            else:
                # 美股：用纳斯达克指数（AKshare 东方财富美股指数）
                bench_name = "NASDAQ"
                bench_df = ak.stock_us_hist(
                    symbol="105.NDX", period="daily",
                    start_date=start_date, end_date=end_date, adjust="",
                )
                if bench_df is not None and not bench_df.empty:
                    bench_df.rename(columns={"收盘": "close"}, inplace=True)

            if bench_df is None or bench_df.empty:
                return {}

            close_col = "close" if "close" in bench_df.columns else "Close"
            b0 = float(bench_df[close_col].iloc[0])
            b1 = float(bench_df[close_col].iloc[-1])
            bench_ret = round((b1 - b0) / b0 * 100, 2) if b0 else 0.0

            n = min(30, len(hist))
            s0 = float(hist["Close"].iloc[-n])
            s1 = float(hist["Close"].iloc[-1])
            stock_ret = round((s1 - s0) / s0 * 100, 2) if s0 else 0.0

            return {
                "benchmark": bench_name,
                "benchmark_return": bench_ret,
                "stock_return": stock_ret,
                "excess_return": round(stock_ret - bench_ret, 2),
                "relative_strength": round(stock_ret / (bench_ret + 1e-9), 2),
                "sector_rank": "N/A",
            }
        except Exception as e:
            logger.debug("市场对比失败: %s", e)
            return {}

    # ─── 投资建议评分 ─────────────────────────────
    def _generate_recommendation(self, realtime, valuation, financials, tech, risk) -> dict:
        scores = {}

        # 估值评分 (越低越好，相对均值)
        pe = _safe_float(valuation.get("pe_ttm"))
        pb = _safe_float(valuation.get("pb_ratio"))
        val_score = 50
        if pe is not None:
            if pe < 15:
                val_score += 20
            elif pe < 25:
                val_score += 10
            elif pe > 40:
                val_score -= 10
            elif pe > 60:
                val_score -= 20
        if pb is not None:
            if pb < 1.5:
                val_score += 10
            elif pb < 3:
                val_score += 5
            elif pb > 10:
                val_score -= 10
        scores["估值评分"] = max(0, min(100, val_score))

        # 成长性评分
        rev_growth = _safe_float(financials.get("revenue_growth_yoy"))
        profit_growth = _safe_float(financials.get("profit_growth_yoy"))
        growth_score = 50
        if rev_growth is not None:
            growth_score += min(25, rev_growth * 1.5)
        if profit_growth is not None:
            growth_score += min(25, profit_growth * 1.5)
        scores["成长性评分"] = max(0, min(100, int(growth_score)))

        # 盈利能力评分
        roe = _safe_float(financials.get("roe"))
        net_margin = _safe_float(financials.get("net_margin"))
        profit_score = 50
        if roe is not None:
            if roe > 20:
                profit_score += 25
            elif roe > 10:
                profit_score += 15
            elif roe < 0:
                profit_score -= 20
        if net_margin is not None:
            if net_margin > 20:
                profit_score += 20
            elif net_margin > 10:
                profit_score += 10
            elif net_margin < 0:
                profit_score -= 20
        scores["盈利能力评分"] = max(0, min(100, int(profit_score)))

        # 财务健康评分
        de = _safe_float(financials.get("debt_to_equity"))
        cr = _safe_float(financials.get("current_ratio"))
        health_score = 60
        if de is not None:
            if de < 50:
                health_score += 20
            elif de < 100:
                health_score += 10
            elif de > 300:
                health_score -= 20
        if cr is not None:
            if cr > 2:
                health_score += 20
            elif cr > 1:
                health_score += 10
            elif cr < 1:
                health_score -= 15
        scores["财务健康评分"] = max(0, min(100, int(health_score)))

        # 技术面评分
        tech_score = 50
        macd = tech.get("macd", {})
        rsi = tech.get("rsi", {})
        kdj = tech.get("kdj", {})
        boll = tech.get("boll", {})
        pattern = tech.get("形态识别", {})

        if macd.get("signal") == "金叉":
            tech_score += 15
        elif macd.get("signal") == "死叉":
            tech_score -= 15

        rsi6 = _safe_float(rsi.get("rsi6"))
        if rsi6:
            if 40 < rsi6 < 70:
                tech_score += 10
            elif rsi6 > 80:
                tech_score -= 15
            elif rsi6 < 20:
                tech_score += 5  # 超卖反弹机会

        if boll.get("signal") == "中轨上方":
            tech_score += 10
        elif boll.get("signal") == "上轨突破":
            tech_score += 5
        elif boll.get("signal") == "下轨突破":
            tech_score -= 15

        if pattern.get("trend_strength") == "强" and "上升" in pattern.get("pattern", ""):
            tech_score += 15
        elif "下降" in pattern.get("pattern", ""):
            tech_score -= 15

        scores["技术面评分"] = max(0, min(100, int(tech_score)))

        # 资金面评分（暂无精确数据，默认60）
        scores["资金面评分"] = 60

        # 综合评分
        weights = {
            "估值评分": 0.15,
            "成长性评分": 0.20,
            "盈利能力评分": 0.20,
            "财务健康评分": 0.15,
            "技术面评分": 0.20,
            "资金面评分": 0.10,
        }
        composite = sum(scores[k] * weights[k] for k in weights)
        scores["综合评分"] = int(composite)

        # 建议
        comp = scores["综合评分"]
        if comp >= 80:
            rec, confidence, risk_level = "强烈买入", comp, "低"
        elif comp >= 65:
            rec, confidence, risk_level = "买入", comp, "中低"
        elif comp >= 50:
            rec, confidence, risk_level = "持有", comp, "中"
        elif comp >= 35:
            rec, confidence, risk_level = "减持", comp, "中高"
        else:
            rec, confidence, risk_level = "卖出", comp, "高"

        # 目标价
        current_price = _safe_float(realtime.get("current_price"))
        target_price = round(current_price * 1.15, 2) if current_price else None
        target_high = round(current_price * 1.25, 2) if current_price else None
        target_low = round(current_price * 1.05, 2) if current_price else None

        # 投资逻辑
        logics = []
        if scores["成长性评分"] >= 70:
            logics.append("业绩保持较高增速，成长性突出")
        if scores["盈利能力评分"] >= 70:
            logics.append("盈利能力强劲，ROE/净利率处于行业高位")
        if macd.get("trend") == "多头":
            logics.append("MACD处于多头趋势，短期动能向上")
        if _safe_float(rsi.get("rsi6"), 50) < 40:
            logics.append("RSI处于低位，存在技术性反弹机会")
        if scores["估值评分"] >= 70:
            logics.append("当前估值处于历史相对低位，具备安全边际")
        if not logics:
            logics.append("综合评估后给出建议，请结合基本面深入研究")

        # 风险提示
        risks = []
        vol = _safe_float(risk.get("volatility_annual"))
        if vol and vol > 30:
            risks.append(f"年化波动率较高（{vol:.1f}%），短期波动风险较大")
        if _safe_float(valuation.get("pe_ttm"), 0) > 50:
            risks.append("估值偏高，需关注业绩兑现情况")
        if scores["财务健康评分"] < 50:
            risks.append("财务杠杆偏高，需关注偿债能力")
        if not risks:
            risks.append("市场系统性风险及行业政策变动风险")

        return {
            "recommendation": rec,
            "confidence_score": confidence,
            "target_price": target_price,
            "target_price_high": target_high,
            "target_price_low": target_low,
            "risk_level": risk_level,
            "investment_horizon": "中长期",
            "suitable_for": "成长型投资者" if comp >= 65 else "保守型投资者",
            "评分卡": scores,
            "投资逻辑": logics,
            "风险提示": risks,
        }
