"""
Baostock 连接管理器：进程级单例 login，线程安全。
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_logged_in = False


def ensure_login() -> None:
    """确保 Baostock 已登录（幂等）。"""
    global _logged_in
    if _logged_in:
        return
    with _lock:
        if _logged_in:
            return
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"Baostock 登录失败: {lg.error_msg}")
        _logged_in = True
        logger.info("Baostock 已登录")


def logout() -> None:
    """退出 Baostock（应用关闭时调用）。"""
    global _logged_in
    with _lock:
        if _logged_in:
            import baostock as bs
            bs.logout()
            _logged_in = False
            logger.info("Baostock 已退出")


def a_code_to_bs(code: str) -> str:
    """A股代码转 Baostock 格式：000001 → sz.000001，600000 → sh.600000。"""
    code = code.strip().lstrip("0").zfill(6) if len(code) < 6 else code.strip()
    if code.startswith(("6", "5", "9")):
        return f"sh.{code}"
    return f"sz.{code}"


def last_quarter() -> tuple[int, int]:
    """返回最近一个完整季度 (year, quarter)。"""
    m = datetime.today().month
    y = datetime.today().year
    q = (m - 1) // 3          # 当前季度（0-based）
    if q == 0:
        return y - 1, 4
    return y, q


def bs_to_df(rs):
    """将 Baostock ResultSet 转成 DataFrame，字段转数值。"""
    import pandas as pd
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    df = pd.DataFrame(rows, columns=rs.fields)
    for col in df.columns:
        if col not in ("date", "code", "pubDate", "statDate"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
