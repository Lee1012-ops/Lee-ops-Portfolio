"""
技术指标计算服务（纯 pandas/numpy 实现，无需 ta-lib）
"""
import numpy as np
import pandas as pd
from typing import Optional


def _last(series: pd.Series, default=None):
    """取最后一个有效值"""
    s = series.dropna()
    if s.empty:
        return default
    return round(float(s.iloc[-1]), 4)


# ─── 均线 ───────────────────────────────────
def calc_ma(close: pd.Series) -> dict:
    result = {}
    for n in [5, 10, 20, 60, 120, 250]:
        result[f"ma{n}"] = _last(close.rolling(n).mean())
    return result


# ─── MACD ───────────────────────────────────
def calc_macd(close: pd.Series) -> dict:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    macd_hist = (dif - dea) * 2

    dif_val = _last(dif)
    dea_val = _last(dea)
    macd_val = _last(macd_hist)

    # 判断信号
    if dif_val is not None and dea_val is not None:
        if dif_val > dea_val:
            signal = "金叉" if dif_val > 0 else "零轴下金叉"
        else:
            signal = "死叉" if dif_val < 0 else "零轴上死叉"
        trend = "多头" if dif_val > 0 else "空头"
    else:
        signal = trend = "N/A"

    return {
        "dif": dif_val,
        "dea": dea_val,
        "macd": macd_val,
        "signal": signal,
        "trend": trend,
    }


# ─── KDJ ────────────────────────────────────
def calc_kdj(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 9) -> dict:
    low_n = low.rolling(n).min()
    high_n = high.rolling(n).max()
    rsv = (close - low_n) / (high_n - low_n + 1e-9) * 100

    k = pd.Series(index=close.index, dtype=float)
    d = pd.Series(index=close.index, dtype=float)
    k.iloc[0] = d.iloc[0] = 50.0

    for i in range(1, len(rsv)):
        if pd.isna(rsv.iloc[i]):
            k.iloc[i] = k.iloc[i - 1]
            d.iloc[i] = d.iloc[i - 1]
        else:
            k.iloc[i] = 2 / 3 * k.iloc[i - 1] + 1 / 3 * rsv.iloc[i]
            d.iloc[i] = 2 / 3 * d.iloc[i - 1] + 1 / 3 * k.iloc[i]

    j = 3 * k - 2 * d
    k_val = _last(k)
    d_val = _last(d)
    j_val = _last(j)

    if k_val is not None and d_val is not None:
        if k_val > 80 or d_val > 80:
            sig = "超买区域"
        elif k_val < 20 or d_val < 20:
            sig = "超卖区域"
        elif k_val > 50:
            sig = "强势区域"
        else:
            sig = "弱势区域"
    else:
        sig = "N/A"

    return {"k": k_val, "d": d_val, "j": j_val, "signal": sig}


# ─── RSI ────────────────────────────────────
def calc_rsi(close: pd.Series) -> dict:
    def _rsi(period):
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).ewm(com=period - 1, adjust=False).mean()
        loss = (-delta).where(delta < 0, 0.0).ewm(com=period - 1, adjust=False).mean()
        rs = gain / (loss + 1e-9)
        return 100 - 100 / (1 + rs)

    r6 = _last(_rsi(6))
    r12 = _last(_rsi(12))
    r24 = _last(_rsi(24))

    if r6 is not None:
        if r6 > 70:
            sig = "超买"
        elif r6 < 30:
            sig = "超卖"
        elif r6 > 55:
            sig = "中性偏强"
        elif r6 < 45:
            sig = "中性偏弱"
        else:
            sig = "中性"
    else:
        sig = "N/A"

    return {"rsi6": r6, "rsi12": r12, "rsi24": r24, "signal": sig}


# ─── BOLL ───────────────────────────────────
def calc_boll(close: pd.Series, n: int = 20, k: float = 2.0) -> dict:
    mid = close.rolling(n).mean()
    std = close.rolling(n).std()
    upper = mid + k * std
    lower = mid - k * std

    mid_v = _last(mid)
    upper_v = _last(upper)
    lower_v = _last(lower)
    close_v = float(close.iloc[-1]) if not close.empty else None

    if upper_v and lower_v and mid_v:
        width = round((upper_v - lower_v) / mid_v * 100, 2)
        position = round((close_v - lower_v) / (upper_v - lower_v + 1e-9), 4) if close_v else None
    else:
        width = position = None

    if close_v and mid_v:
        if close_v > upper_v:
            sig = "上轨突破"
        elif close_v > mid_v:
            sig = "中轨上方"
        elif close_v < lower_v:
            sig = "下轨突破"
        else:
            sig = "中轨下方"
    else:
        sig = "N/A"

    return {
        "upper": upper_v,
        "mid": mid_v,
        "lower": lower_v,
        "width": width,
        "position": position,
        "signal": sig,
    }


# ─── OBV ────────────────────────────────────
def calc_obv(close: pd.Series, volume: pd.Series) -> Optional[float]:
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    obv = (volume * direction).cumsum()
    return _last(obv)


# ─── CCI ────────────────────────────────────
def calc_cci(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 20) -> Optional[float]:
    tp = (high + low + close) / 3
    ma = tp.rolling(n).mean()
    md = tp.rolling(n).apply(lambda x: np.mean(np.abs(x - x.mean())))
    cci = (tp - ma) / (0.015 * md + 1e-9)
    return _last(cci)


# ─── Williams %R ────────────────────────────
def calc_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> Optional[float]:
    high_n = high.rolling(n).max()
    low_n = low.rolling(n).min()
    wr = (high_n - close) / (high_n - low_n + 1e-9) * -100
    return _last(wr)


# ─── ATR ────────────────────────────────────
def calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> Optional[float]:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs()
    ], axis=1).max(axis=1)
    atr = tr.ewm(com=n - 1, adjust=False).mean()
    return _last(atr)


# ─── Parabolic SAR (简化版) ─────────────────
def calc_sar(high: pd.Series, low: pd.Series) -> Optional[float]:
    if len(high) < 5:
        return None
    af_start, af_step, af_max = 0.02, 0.02, 0.2
    uptrend = True
    sar = float(low.iloc[0])
    ep = float(high.iloc[0])
    af = af_start

    for i in range(1, len(high)):
        h, l = float(high.iloc[i]), float(low.iloc[i])
        if uptrend:
            sar = sar + af * (ep - sar)
            sar = min(sar, float(low.iloc[i - 1]), float(low.iloc[max(i - 2, 0)]))
            if l < sar:
                uptrend = False
                sar = ep
                ep = l
                af = af_start
            else:
                if h > ep:
                    ep = h
                    af = min(af + af_step, af_max)
        else:
            sar = sar + af * (ep - sar)
            sar = max(sar, float(high.iloc[i - 1]), float(high.iloc[max(i - 2, 0)]))
            if h > sar:
                uptrend = True
                sar = ep
                ep = h
                af = af_start
            else:
                if l < ep:
                    ep = l
                    af = min(af + af_step, af_max)

    return round(sar, 4)


# ─── 形态识别 ────────────────────────────────
def identify_pattern(close: pd.Series, ma_dict: dict) -> dict:
    price = float(close.iloc[-1])
    ma20 = ma_dict.get("ma20")
    ma60 = ma_dict.get("ma60")
    ma250 = ma_dict.get("ma250")

    # Trend strength
    if ma20 and ma60 and ma250:
        if price > ma20 > ma60 > ma250:
            pattern = "上升通道"
            strength = "强"
        elif price < ma20 < ma60 < ma250:
            pattern = "下降通道"
            strength = "强"
        elif price > ma20 and ma20 > ma60:
            pattern = "短期上升趋势"
            strength = "中"
        elif price < ma20 and ma20 < ma60:
            pattern = "短期下降趋势"
            strength = "中"
        else:
            pattern = "震荡盘整"
            strength = "弱"
    else:
        pattern = "震荡"
        strength = "中"

    # Support and resistance from MAs
    mas = [v for v in [ma_dict.get("ma20"), ma_dict.get("ma60"), ma_dict.get("ma120")] if v]
    support = sorted([m for m in mas if m < price])[-2:] if [m for m in mas if m < price] else []
    resistance = sorted([m for m in mas if m > price])[:2] if [m for m in mas if m > price] else []

    return {
        "pattern": pattern,
        "support_level": support,
        "resistance_level": resistance,
        "trend_strength": strength,
    }


# ─── 综合技术分析 ────────────────────────────
def calculate_technical_indicators(hist_df: pd.DataFrame) -> dict:
    close = hist_df["Close"].astype(float)
    high = hist_df["High"].astype(float)
    low = hist_df["Low"].astype(float)
    volume = hist_df["Volume"].astype(float)

    ma_dict = calc_ma(close)
    macd_dict = calc_macd(close)
    kdj_dict = calc_kdj(high, low, close)
    rsi_dict = calc_rsi(close)
    boll_dict = calc_boll(close)
    obv_val = calc_obv(close, volume)
    cci_val = calc_cci(high, low, close)
    wr_val = calc_williams_r(high, low, close)
    sar_val = calc_sar(high, low)
    atr_val = calc_atr(high, low, close)
    pattern_dict = identify_pattern(close, ma_dict)

    return {
        "均线": ma_dict,
        "macd": macd_dict,
        "kdj": kdj_dict,
        "rsi": rsi_dict,
        "boll": boll_dict,
        "其他指标": {
            "obv": obv_val,
            "cci": cci_val,
            "威廉指标": wr_val,
            "sar": sar_val,
            "atr": atr_val,
        },
        "形态识别": pattern_dict,
    }
