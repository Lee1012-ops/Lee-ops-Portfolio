"""
yfinance_utils 已停用（替换为 Baostock + AKshare）。
保留空实现供旧代码引用兼容。
"""
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def yfinance_full_extras_enabled() -> bool:
    return False


def get_ticker_history(symbol: str, period: str) -> pd.DataFrame:
    """已废弃，返回空 DataFrame。"""
    logger.debug("get_ticker_history 已废弃，请使用 AKshare/Baostock")
    return pd.DataFrame()


def get_ticker_info(symbol: str) -> dict:
    """已废弃，返回空 dict。"""
    logger.debug("get_ticker_info 已废弃，请使用 AKshare/Baostock")
    return {}


def get_benchmark_history(benchmark_symbol: str, period: str = "30d") -> pd.DataFrame:
    return pd.DataFrame()


def yfinance_call(fn, *, what: str = "yfinance"):
    return fn()


def clear_cache():
    pass
