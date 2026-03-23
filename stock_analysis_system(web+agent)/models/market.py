from enum import Enum

# 可选：文档/代码里引用英文代码
class Market(str, Enum):
    US = "US"
    CN = "CN"
    HK = "HK"


MARKET_TO_CN = {
    Market.US: "美股",
    Market.CN: "A股",
    Market.HK: "港股",
}

# 中文标准名（与 StockAnalyzer 一致）
_CN_SET = frozenset({"美股", "A股", "港股"})

# 英文/大小写别名 → 中文
_ALIAS_TO_CN = {
    "us": "美股",
    "cn": "A股",
    "hk": "港股",
}


def market_to_cn(market: Market) -> str:
    return MARKET_TO_CN[market]


def normalize_market_to_cn(value: str) -> str:
    """
    接受 API 输入：
    - 中文：美股、A股、港股
    - 英文：US、CN、HK（大小写不敏感）
    返回 StockAnalyzer 使用的中文市场名。
    """
    v = (value or "").strip()
    if not v:
        raise ValueError("market 不能为空")
    if v in _CN_SET:
        return v
    key = v.lower()
    if key in _ALIAS_TO_CN:
        return _ALIAS_TO_CN[key]
    raise ValueError(
        f"不支持的市场: {value!r}，请使用「美股」「A股」「港股」或 US、CN、HK"
    )
